"""HTTP-эндпоинты курьерской панели (PDD §6.3, INV-010).

5 маршрутов под `/api/v1/courier/...`, доступны только роли COURIER
(см. `rbac_matrix.ROUTE_MATRIX`). Доменные ошибки из сервиса
`delivery_assignment` проецируются в HTTP-коды:
    - `assignment_not_found` → 404,
    - `not_owner`            → 403,
    - остальные (forbidden_transition / order_not_ready / already_taken) → 409.

Модуль-уровневые импорты сервисных функций — публичный патч-пойнт для тестов
(`patch.object(router_mod, "take_assignment", stub)`).
"""
from __future__ import annotations

# START_MODULE_CONTRACT
#   PURPOSE: HTTP routes for the courier panel under /api/v1/courier
#            — list available, list mine, take, pickup, deliver assignments.
#   SCOPE:   Delivery assignment state-machine transitions
#            (AWAITING_COURIER → COURIER_ASSIGNED → PICKED_UP → DELIVERED)
#            and matching Order transitions (PDD §6.1, §6.3).
#   DEPENDS: M-SHARED (enums.DeliveryAssignmentStatus, models.DeliveryAssignment),
#            M-DATABASE, core_api.services.delivery_assignment,
#            core_api.deps.{auth,database}, RBACMiddleware (COURIER-only).
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §6.1, §6.3,
#            INV-002, INV-010 (role isolation), INV-016 (state transitions).
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   router                       - APIRouter("/api/v1/courier", tags=["courier"])
#   get_available_assignments    - GET  /api/v1/courier/assignments/available
#   get_my_assignments           - GET  /api/v1/courier/assignments/mine
#   post_take_assignment         - POST /api/v1/courier/assignments/{assignment_id}/take
#   post_pickup_assignment       - POST /api/v1/courier/assignments/{assignment_id}/pickup
#   post_deliver_assignment      - POST /api/v1/courier/assignments/{assignment_id}/deliver
# END_MODULE_MAP

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core_api.deps import database as _db_dep
from core_api.deps.auth import get_current_user
from core_api.services.delivery_assignment import (
    AssignmentAlreadyTakenError,
    AssignmentTransitionError,
    deliver_assignment,
    list_available_for_courier,
    pickup_assignment,
    take_assignment,
)
from shared.enums import DeliveryAssignmentStatus
from shared.models import DeliveryAssignment

router = APIRouter(prefix="/api/v1/courier", tags=["courier"])


def _get_session():
    yield from _db_dep.get_session()


def _assignment_error_to_http(exc: AssignmentTransitionError) -> HTTPException:
    # AssignmentAlreadyTakenError проверяем отдельно в вызывающем коде — body
    # должен содержать "already_taken", хотя reason может быть "forbidden_transition".
    if exc.reason == "assignment_not_found":
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"reason": exc.reason},
        )
    if exc.reason == "not_owner":
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"reason": exc.reason},
        )
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"reason": exc.reason},
    )


# START_CONTRACT: get_available_assignments
#   PURPOSE: List AWAITING_COURIER assignments visible to any courier.
#   INPUTS:  current_user (get_current_user), Session.
#   OUTPUTS: 200 list[dict] of available assignments.
#   SIDE_EFFECTS: none (read-only DB query).
#   LINKS:   PDD §6.3, INV-002, INV-010, services.delivery_assignment.
# END_CONTRACT: get_available_assignments
@router.get("/assignments/available")
def get_available_assignments(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(_get_session),
) -> list[dict]:
    """Список AWAITING_COURIER assignments — видит каждый курьер."""
    return list_available_for_courier(db)


# START_CONTRACT: get_my_assignments
#   PURPOSE: Return the active assignments (COURIER_ASSIGNED / PICKED_UP)
#            owned by the current courier.
#   INPUTS:  current_user, Session.
#   OUTPUTS: 200 list[dict].
#   SIDE_EFFECTS: none.
#   LINKS:   PDD §6.3, INV-002, INV-010, INV-013 (courier sees only own
#            delivery rows).
# END_CONTRACT: get_my_assignments
@router.get("/assignments/mine")
def get_my_assignments(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(_get_session),
) -> list[dict]:
    """Текущие активные assignments этого курьера (COURIER_ASSIGNED / PICKED_UP)."""
    courier_id = current_user["user_id"]
    rows = (
        db.query(DeliveryAssignment)
        .filter(
            DeliveryAssignment.courier_id == courier_id,
            DeliveryAssignment.status.in_(
                [
                    DeliveryAssignmentStatus.COURIER_ASSIGNED,
                    DeliveryAssignmentStatus.PICKED_UP,
                ]
            ),
        )
        .all()
    )
    return [
        {
            "id": str(r.id),
            "order_id": str(r.order_id),
            "status": r.status.value,
            "assigned_at": r.assigned_at.isoformat() if r.assigned_at else None,
            "picked_up_at": r.picked_up_at.isoformat() if r.picked_up_at else None,
        }
        for r in rows
    ]


# START_CONTRACT: post_take_assignment
#   PURPOSE: AWAITING_COURIER → COURIER_ASSIGNED transition with optimistic
#            lock — only the first courier wins.
#   INPUTS:  assignment_id: UUID, current_user, Session.
#   OUTPUTS: 200 {"status": "courier_assigned"}; 404 not found;
#            403 not_owner; 409 already_taken / forbidden_transition.
#   SIDE_EFFECTS: DB update on delivery_assignment row.
#   LINKS:   PDD §6.3, INV-002, INV-010, INV-016, services.delivery_assignment.
# END_CONTRACT: post_take_assignment
@router.post("/assignments/{assignment_id}/take")
def post_take_assignment(
    assignment_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(_get_session),
) -> dict:
    """Забрать AWAITING_COURIER → COURIER_ASSIGNED (optimistic lock)."""
    courier_id = current_user["user_id"]
    try:
        take_assignment(assignment_id, courier_id, db)
    except AssignmentAlreadyTakenError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"reason": "already_taken"},
        )
    except AssignmentTransitionError as exc:
        raise _assignment_error_to_http(exc)
    return {"status": "courier_assigned"}


# START_CONTRACT: post_pickup_assignment
#   PURPOSE: COURIER_ASSIGNED → PICKED_UP transition + Order → IN_DELIVERY.
#   INPUTS:  assignment_id: UUID, current_user, Session.
#   OUTPUTS: 200 {"status": "picked_up"}; 404; 403; 409.
#   SIDE_EFFECTS: DB updates on delivery_assignment + order
#                 (atomic within service, INV-004 / INV-016).
#   LINKS:   PDD §6.1, §6.3, INV-002, INV-010, INV-016,
#            services.delivery_assignment.
# END_CONTRACT: post_pickup_assignment
@router.post("/assignments/{assignment_id}/pickup")
def post_pickup_assignment(
    assignment_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(_get_session),
) -> dict:
    """Забрать заказ у бариста — COURIER_ASSIGNED → PICKED_UP (+ Order → IN_DELIVERY)."""
    courier_id = current_user["user_id"]
    try:
        pickup_assignment(assignment_id, courier_id, db)
    except AssignmentAlreadyTakenError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"reason": "already_taken"},
        )
    except AssignmentTransitionError as exc:
        raise _assignment_error_to_http(exc)
    return {"status": "picked_up"}


# START_CONTRACT: post_deliver_assignment
#   PURPOSE: PICKED_UP → DELIVERED transition + Order → COMPLETED + loyalty
#            accrual.
#   INPUTS:  assignment_id: UUID, current_user, Session.
#   OUTPUTS: 200 {"status": "delivered"}; 404; 403; 409.
#   SIDE_EFFECTS: Atomic DB writes — assignment, order, loyalty balance,
#                 loyalty transaction (INV-004 single transaction).
#   LINKS:   PDD §6.1, §6.3, INV-002, INV-004, INV-010, INV-016,
#            services.delivery_assignment.
# END_CONTRACT: post_deliver_assignment
@router.post("/assignments/{assignment_id}/deliver")
def post_deliver_assignment(
    assignment_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(_get_session),
) -> dict:
    """Вручить клиенту — PICKED_UP → DELIVERED (+ Order → COMPLETED + loyalty)."""
    courier_id = current_user["user_id"]
    try:
        deliver_assignment(assignment_id, courier_id, db)
    except AssignmentAlreadyTakenError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"reason": "already_taken"},
        )
    except AssignmentTransitionError as exc:
        raise _assignment_error_to_http(exc)
    return {"status": "delivered"}
