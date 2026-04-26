# START_MODULE_CONTRACT
#   PURPOSE: Delivery Assignment state machine driver — atomic transitions for
#            the courier-facing lifecycle, with cascading bridge into the Order
#            state machine to keep both aggregates consistent in one txn.
#   SCOPE:   take/pickup/deliver/cancel transitions; available-for-courier feed.
#            State machine: AWAITING_COURIER → COURIER_ASSIGNED → PICKED_UP →
#            DELIVERED, plus CANCELLED branch.
#   DEPENDS: M-SHARED (DeliveryAssignment, Order), M-DATABASE,
#            services.order_lifecycle, services.order_notifications
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §6.3, INV-004, INV-010,
#            INV-016
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   AssignmentTransitionError    - reason-tagged transition error
#   AssignmentAlreadyTakenError  - race-loss specialization (409 already_taken)
#   take_assignment              - AWAITING_COURIER → COURIER_ASSIGNED
#   pickup_assignment            - COURIER_ASSIGNED → PICKED_UP + Order bridge
#   deliver_assignment           - PICKED_UP → DELIVERED + Order bridge
#   cancel_assignment_for_order  - cascade-CANCELLED no-commit helper
#   list_available_for_courier   - feed for courier UI (AWAITING only)
# END_MODULE_MAP
r"""Delivery Assignment state machine — сервисный слой (PDD §6.3, INV-004, INV-010, INV-016).

Управляет жизненным циклом `DeliveryAssignment`:
    AWAITING_COURIER -> COURIER_ASSIGNED -> PICKED_UP -> DELIVERED
                     \-> CANCELLED

`pickup_assignment` / `deliver_assignment` — атомарно каскадируют переход
на `Order` через `transition_order_bridge` (без commit / notify внутри bridge).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from shared.enums import DeliveryAssignmentStatus, OrderStatus
from shared.models import DeliveryAssignment, Order

from core_api.services.order_lifecycle import transition_order_bridge
from core_api.services.order_notifications import send_order_notification

from shared.grace.logging import get_grace_logger

_grace_log = get_grace_logger("CoreApi")


# START_CONTRACT: AssignmentTransitionError
#   PURPOSE: Domain error for delivery-assignment transitions, carrying a
#            machine-readable .reason ("forbidden_transition", "not_owner",
#            "assignment_not_found", "order_not_ready", ...).
#   INPUTS:  reason: str
#   OUTPUTS: Exception with .reason
#   SIDE_EFFECTS: none
#   LINKS:   PDD §6.3, INV-016
# END_CONTRACT: AssignmentTransitionError
class AssignmentTransitionError(Exception):
    """Доменная ошибка Delivery Assignment: переход запрещён/нарушен invariant."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


# START_CONTRACT: AssignmentAlreadyTakenError
#   PURPOSE: Specialization of AssignmentTransitionError for the take_assignment
#            race-loss case (other courier won) — router maps to HTTP 409.
#   INPUTS:  reason: str (default "forbidden_transition")
#   OUTPUTS: Exception with .reason
#   SIDE_EFFECTS: none
# END_CONTRACT: AssignmentAlreadyTakenError
class AssignmentAlreadyTakenError(AssignmentTransitionError):
    """Race: другой курьер успел взять AWAITING-assignment первым (PDD §6.3).

    По семантике — это частный случай `forbidden_transition` (src != AWAITING),
    но отдельный класс позволяет роутеру вернуть 409 с human-readable телом
    `already_taken` и различать race от остальных forbidden-переходов в logs.
    """

    def __init__(self, reason: str = "forbidden_transition") -> None:
        super().__init__(reason)


def _now() -> datetime:
    return datetime.now(UTC)


# START_CONTRACT: take_assignment
#   PURPOSE: Atomic take of an AWAITING assignment via conditional UPDATE,
#            preventing duplicate assignment under courier contention.
#   INPUTS:  assignment_id: UUID
#            courier_id: UUID
#            db_session: Session
#   OUTPUTS: DeliveryAssignment (refreshed)
#   SIDE_EFFECTS: DB UPDATE assignments SET courier+status+assigned_at WHERE
#                 status=AWAITING_COURIER + commit. Source: AWAITING_COURIER.
#                 Target: COURIER_ASSIGNED. Race losers → AssignmentAlreadyTakenError.
#   LINKS:   PDD §6.3, INV-004, INV-016
# END_CONTRACT: take_assignment
def take_assignment(
    assignment_id: uuid.UUID,
    courier_id: uuid.UUID,
    db_session: Session,
) -> DeliveryAssignment:
    """AWAITING_COURIER -> COURIER_ASSIGNED для `courier_id` через optimistic lock.

    Атомарный UPDATE ... WHERE status='awaiting_courier' RETURNING *.
    0 строк:
      - assignment отсутствует → AssignmentTransitionError(assignment_not_found);
      - status == COURIER_ASSIGNED → AssignmentAlreadyTakenError (race);
      - остальные non-AWAITING → AssignmentTransitionError(forbidden_transition).
    1 строка: commit + возвращаем обновлённый объект.
    """
    now = _now()
    stmt = (
        update(DeliveryAssignment)
        .where(
            DeliveryAssignment.id == assignment_id,
            DeliveryAssignment.status == DeliveryAssignmentStatus.AWAITING_COURIER,
        )
        .values(
            courier_id=courier_id,
            status=DeliveryAssignmentStatus.COURIER_ASSIGNED,
            assigned_at=now,
        )
        .returning(DeliveryAssignment.id)
        .execution_options(synchronize_session=False)
    )
    result = db_session.execute(stmt)
    updated = result.first()

    if updated is None:
        # UPDATE не затронул ни одной строки — разбираемся почему.
        existing = db_session.get(DeliveryAssignment, assignment_id)
        if existing is None:
            raise AssignmentTransitionError(reason="assignment_not_found")
        if existing.status == DeliveryAssignmentStatus.COURIER_ASSIGNED:
            raise AssignmentAlreadyTakenError()
        raise AssignmentTransitionError(reason="forbidden_transition")

    db_session.commit()
    # Возвращаем свежий объект — после commit identity map expired.
    assignment = db_session.get(DeliveryAssignment, assignment_id)
    _grace_log.belief(
        "delivery.accept",
        "BLOCK_STATE_TRANSITION",
        belief="COURIER_ASSIGNED",
        actual=str(assignment.status),
        assignment_id=str(assignment.id),
    )
    return assignment


# START_CONTRACT: pickup_assignment
#   PURPOSE: COURIER_ASSIGNED → PICKED_UP plus cascade Order READY → IN_DELIVERY
#            in the same transaction; emits SMS notification post-commit.
#   INPUTS:  assignment_id: UUID, courier_id: UUID, db_session: Session
#   OUTPUTS: DeliveryAssignment (refreshed)
#   SIDE_EFFECTS: DB UPDATE assignment + bridge transition_order_bridge
#                 (READY → IN_DELIVERY) + commit; post-commit Celery enqueue
#                 of order notification. Source: COURIER_ASSIGNED.
#                 Target: PICKED_UP. Order ownership enforced (INV-010).
#   LINKS:   PDD §6.1, §6.3, INV-004, INV-010, INV-016
# END_CONTRACT: pickup_assignment
def pickup_assignment(
    assignment_id: uuid.UUID,
    courier_id: uuid.UUID,
    db_session: Session,
) -> DeliveryAssignment:
    """COURIER_ASSIGNED -> PICKED_UP + bridge Order READY -> IN_DELIVERY.

    Последовательность проверок (порядок важен — D4):
        1. assignment_not_found;
        2. forbidden_transition (src != COURIER_ASSIGNED);
        3. not_owner (INV-010: только курьер-владелец);
        4. order_not_ready (Order.status != READY);
        5. мутация + flush;
        6. transition_order_bridge(READY → IN_DELIVERY) — в той же txn;
        7. commit.
    """
    assignment = db_session.get(DeliveryAssignment, assignment_id)
    if assignment is None:
        raise AssignmentTransitionError(reason="assignment_not_found")

    if assignment.status != DeliveryAssignmentStatus.COURIER_ASSIGNED:
        raise AssignmentTransitionError(reason="forbidden_transition")

    if assignment.courier_id != courier_id:
        raise AssignmentTransitionError(reason="not_owner")

    order = db_session.get(Order, assignment.order_id)
    if order is None or order.status != OrderStatus.READY:
        raise AssignmentTransitionError(reason="order_not_ready")

    assignment.status = DeliveryAssignmentStatus.PICKED_UP
    assignment.picked_up_at = _now()
    db_session.flush()

    # Каскад в Order Lifecycle без commit / notify — atomic part one txn.
    transition_order_bridge(
        order.id, OrderStatus.IN_DELIVERY, "courier", db_session
    )

    db_session.commit()
    _grace_log.belief(
        "delivery.pickup",
        "BLOCK_STATE_TRANSITION",
        belief="PICKED_UP",
        actual=str(assignment.status),
        assignment_id=str(assignment.id),
    )
    send_order_notification(order, OrderStatus.IN_DELIVERY)
    return assignment


# START_CONTRACT: deliver_assignment
#   PURPOSE: PICKED_UP → DELIVERED plus cascade Order IN_DELIVERY → COMPLETED;
#            triggers loyalty accrual via _apply_transition (INV-003).
#   INPUTS:  assignment_id: UUID, courier_id: UUID, db_session: Session
#   OUTPUTS: DeliveryAssignment (refreshed)
#   SIDE_EFFECTS: DB UPDATE assignment + bridge IN_DELIVERY → COMPLETED
#                 + commit; post-commit notification dispatch. Source: PICKED_UP.
#                 Target: DELIVERED.
#   LINKS:   PDD §6.1, §6.3, INV-003, INV-004, INV-010, INV-016
# END_CONTRACT: deliver_assignment
def deliver_assignment(
    assignment_id: uuid.UUID,
    courier_id: uuid.UUID,
    db_session: Session,
) -> DeliveryAssignment:
    """PICKED_UP -> DELIVERED + bridge Order IN_DELIVERY -> COMPLETED.

    Аналогично pickup: assignment_not_found → forbidden_transition →
    not_owner → order mismatch → мутация → flush → bridge → commit.
    `_accrue_loyalty` сработает внутри `_apply_transition` (INV-003).
    """
    assignment = db_session.get(DeliveryAssignment, assignment_id)
    if assignment is None:
        raise AssignmentTransitionError(reason="assignment_not_found")

    if assignment.status != DeliveryAssignmentStatus.PICKED_UP:
        raise AssignmentTransitionError(reason="forbidden_transition")

    if assignment.courier_id != courier_id:
        raise AssignmentTransitionError(reason="not_owner")

    order = db_session.get(Order, assignment.order_id)
    if order is None or order.status != OrderStatus.IN_DELIVERY:
        raise AssignmentTransitionError(reason="order_not_ready")

    assignment.status = DeliveryAssignmentStatus.DELIVERED
    assignment.delivered_at = _now()
    db_session.flush()

    transition_order_bridge(
        order.id, OrderStatus.COMPLETED, "courier", db_session
    )

    db_session.commit()
    _grace_log.belief(
        "delivery.deliver",
        "BLOCK_STATE_TRANSITION",
        belief="DELIVERED",
        actual=str(assignment.status),
        assignment_id=str(assignment.id),
    )
    send_order_notification(order, OrderStatus.COMPLETED)
    return assignment


# START_CONTRACT: cancel_assignment_for_order
#   PURPOSE: Cascade-cancel a pending assignment when the parent order is being
#            cancelled. No-op for terminal states; never commits (caller owns).
#   INPUTS:  order_id: UUID, db_session: Session
#   OUTPUTS: DeliveryAssignment | None — the cancelled row, or None.
#   SIDE_EFFECTS: DB UPDATE on assignment row only; flush. Source: AWAITING_COURIER
#                 or COURIER_ASSIGNED. Target: CANCELLED.
#   LINKS:   PDD §6.3, INV-004
# END_CONTRACT: cancel_assignment_for_order
def cancel_assignment_for_order(
    order_id: uuid.UUID,
    db_session: Session,
) -> DeliveryAssignment | None:
    """Каскадная отмена assignment при отмене заказа (PDD §6.3, INV-004).

    AWAITING_COURIER / COURIER_ASSIGNED → CANCELLED + cancelled_at.
    PICKED_UP / DELIVERED / CANCELLED / отсутствует → None (no-op).
    НЕ коммитит — commit делает caller (`order_cancel.cancel_order`).
    """
    assignment = (
        db_session.query(DeliveryAssignment)
        .filter(DeliveryAssignment.order_id == order_id)
        .one_or_none()
    )
    if assignment is None:
        return None

    if assignment.status not in (
        DeliveryAssignmentStatus.AWAITING_COURIER,
        DeliveryAssignmentStatus.COURIER_ASSIGNED,
    ):
        return None

    assignment.status = DeliveryAssignmentStatus.CANCELLED
    assignment.cancelled_at = _now()
    db_session.flush()
    return assignment


# START_CONTRACT: list_available_for_courier
#   PURPOSE: Return AWAITING-COURIER assignments joined with their orders for
#            the courier-side feed (id, order_id, total, requested_time, snapshot).
#   INPUTS:  db_session: Session
#   OUTPUTS: list[dict] — minimal projection per row.
#   SIDE_EFFECTS: DB SELECT only.
#   LINKS:   PDD §6.3, INV-010
# END_CONTRACT: list_available_for_courier
def list_available_for_courier(db_session: Session) -> list[dict]:
    """JOIN assignments (AWAITING_COURIER) × orders → view-строки.

    Возвращает список dict'ов с полями, которые видит курьер в списке:
    `id` (assignment), `order_id` (order uuid), `total`, `requested_time`,
    `delivery_address_snapshot`.
    """
    stmt = (
        select(
            DeliveryAssignment.id,
            Order.id.label("order_id"),
            Order.total,
            Order.requested_time,
            Order.delivery_address_snapshot,
        )
        .join(Order, Order.id == DeliveryAssignment.order_id)
        .where(DeliveryAssignment.status == DeliveryAssignmentStatus.AWAITING_COURIER)
    )
    rows = db_session.execute(stmt).all()
    return [
        {
            "id": row.id,
            "order_id": row.order_id,
            "total": row.total,
            "requested_time": row.requested_time,
            "delivery_address_snapshot": row.delivery_address_snapshot,
        }
        for row in rows
    ]
