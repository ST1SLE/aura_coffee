"""HTTP-роуты заказов (PDD §7.1 item 2).

POST /api/v1/orders — создание заказа из Redis-корзины (201 / 400 / 409 / 422 / 401 / 403).
GET  /api/v1/orders/{order_id} — деталь заказа для polling confirmation_url
                                (200 / 404 foreign-or-unknown / 401 / 403).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core_api.deps import database as _db_dep
from core_api.deps import redis as _redis_dep
from core_api.deps.auth import get_current_user
from core_api.schemas.order import (
    CreateOrderRequest,
    OrderItemResponse,
    OrderResponse,
)
from core_api.services.checkout import EmptyCartError, create_order
from shared.models import Order, OrderItem, Payment

orders_router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


# Обёртки: обращаемся к атрибутам модуля в момент вызова — чтобы тесты
# могли патчить core_api.deps.redis.get_redis / core_api.deps.database.get_session.
def _get_redis():
    yield from _redis_dep.get_redis()


def _get_session():
    yield from _db_dep.get_session()


@orders_router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_order(
    request: CreateOrderRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(_get_session),
    redis_client=Depends(_get_redis),
) -> OrderResponse:
    """Создать заказ из текущей корзины пользователя."""
    try:
        return create_order(
            user_id=current_user["user_id"],
            request=request,
            redis_client=redis_client,
            db_session=db,
        )
    except EmptyCartError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        # Ошибки валидаторов (stop-list / delivery / promocode / time-slot) → 409
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@orders_router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(_get_session),
) -> OrderResponse:
    """Деталь своего заказа. Чужой или несуществующий → 404 (INV-013)."""
    order = (
        db.query(Order)
        .filter(
            Order.id == order_id,
            Order.user_id == current_user["user_id"],
        )
        .first()
    )
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Order not found"
        )

    items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    payment = db.query(Payment).filter(Payment.order_id == order.id).first()

    items_resp = [OrderItemResponse.model_validate(oi) for oi in items]

    return OrderResponse(
        id=order.id,
        status=order.status,
        type=order.type,
        items=items_resp,
        subtotal=order.subtotal,
        discount_amount=order.discount_amount,
        points_used=order.points_used,
        delivery_fee=order.delivery_fee,
        total=order.total,
        estimated_accrual=order.estimated_accrual,
        confirmation_url=(payment.confirmation_url if payment is not None else None),
        requested_time=order.requested_time,
        estimated_ready_at=order.estimated_ready_at,
        cancelled_by=order.cancelled_by,
        cancelled_at=order.cancelled_at,
        created_at=order.created_at or datetime.now(tz=UTC),
    )
