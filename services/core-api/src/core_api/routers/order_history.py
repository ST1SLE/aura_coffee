"""Маршруты истории заказов и repeat (PDD §7.7).

GET  /api/v1/orders                       → OrderListResponse
POST /api/v1/orders/{order_id}/repeat     → RepeatOrderResult

Оба маршрута авторизованы под ролью CUSTOMER через ROUTE_MATRIX.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from core_api.deps import database as _db_dep
from core_api.deps import redis as _redis_dep
from core_api.deps.auth import get_current_user
from core_api.schemas.order_history import OrderListResponse, RepeatOrderResult
from core_api.services.order_history import list_orders
from core_api.services.order_repeat import (
    NoItemsAvailableError,
    OrderNotFoundError,
    repeat_order,
)

router = APIRouter(prefix="/api/v1/orders", tags=["orders-history"])


# Обёртки для patch-friendly dep resolution (см. routers/cart.py)
def _get_redis():
    yield from _redis_dep.get_redis()


def _get_session():
    yield from _db_dep.get_session()


@router.get("", response_model=OrderListResponse)
def get_own_orders(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(_get_session),
) -> OrderListResponse:
    """Пагинированная история заказов текущего пользователя."""
    return list_orders(
        user_id=current_user["user_id"],
        page=page,
        per_page=per_page,
        db_session=db,
    )


@router.post("/{order_id}/repeat", response_model=RepeatOrderResult)
def post_repeat_order(
    order_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(_get_session),
    redis_client=Depends(_get_redis),
) -> RepeatOrderResult:
    """Повтор исторического заказа: заполняет корзину текущими ценами."""
    try:
        return repeat_order(
            order_id=order_id,
            user_id=current_user["user_id"],
            redis=redis_client,
            db_session=db,
        )
    except OrderNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="order_not_found",
        )
    except NoItemsAvailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
