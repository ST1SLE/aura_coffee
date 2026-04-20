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


@router.get("/assignments/available")
def get_available_assignments(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(_get_session),
) -> list[dict]:
    """Список AWAITING_COURIER assignments — видит каждый курьер."""
    return list_available_for_courier(db)


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
