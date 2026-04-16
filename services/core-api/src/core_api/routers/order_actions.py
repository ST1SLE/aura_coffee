"""HTTP-эндпоинты staff-действий над заказом (PDD §6.1, §7.6).

- PATCH /api/v1/orders/{order_id}/status — смена статуса (staff).
- POST  /api/v1/orders/{order_id}/cancel — отмена (customer-own-order / admin).

Модуль-уровневые ссылки `transition_order` и `cancel_order` — публичный
патч-пойнт для тестов.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core_api.deps import database as _db_dep
from core_api.deps.auth import get_current_user
from core_api.schemas.order import CancelOrderRequest, OrderResponse, OrderStatusUpdate
from core_api.services.order_cancel import OrderCancelError, cancel_order
from core_api.services.order_lifecycle import (
    OrderTransitionError,
    transition_order,
)
from shared.models import Order

router = APIRouter(prefix="/api/v1/orders", tags=["order-actions"])


def _get_session():
    yield from _db_dep.get_session()


def _transition_error_to_http(exc: OrderTransitionError) -> HTTPException:
    if exc.reason == "order_not_found":
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"reason": exc.reason})
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"reason": exc.reason})


def _cancel_error_to_http(exc: OrderCancelError) -> HTTPException:
    if exc.reason == "order_not_found":
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"reason": exc.reason})
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"reason": exc.reason})


@router.patch("/{order_id}/status", response_model=OrderResponse)
def patch_order_status(
    order_id: uuid.UUID,
    body: OrderStatusUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(_get_session),
) -> OrderResponse:
    """Переход статуса заказа (BARISTA / COURIER / ADMIN)."""
    try:
        updated = transition_order(order_id, body.new_status, current_user["role"], db)
    except OrderTransitionError as exc:
        raise _transition_error_to_http(exc)
    return updated


@router.post("/{order_id}/cancel", response_model=OrderResponse)
def post_order_cancel(
    order_id: uuid.UUID,
    body: CancelOrderRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(_get_session),
) -> OrderResponse:
    """Отмена заказа (CUSTOMER-own-order / ADMIN). INV-010, INV-005."""
    role = current_user["role"]

    # Для клиента — проверяем, что заказ принадлежит ему (INV-010).
    if role == "customer":
        order = db.get(Order, order_id)
        if order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail={"reason": "order_not_found"}
            )
        if order.user_id != current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
            )

    try:
        updated = cancel_order(order_id, role, body.reason, db)
    except OrderCancelError as exc:
        raise _cancel_error_to_http(exc)
    return updated
