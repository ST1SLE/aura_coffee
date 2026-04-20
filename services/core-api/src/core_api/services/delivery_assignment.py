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


class AssignmentTransitionError(Exception):
    """Доменная ошибка Delivery Assignment: переход запрещён/нарушен invariant."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


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
    return db_session.get(DeliveryAssignment, assignment_id)


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
    send_order_notification(order, OrderStatus.IN_DELIVERY)
    return assignment


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
    send_order_notification(order, OrderStatus.COMPLETED)
    return assignment


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
