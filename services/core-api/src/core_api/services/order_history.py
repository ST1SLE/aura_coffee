"""Сервис list_orders — пагинированная история заказов пользователя (PDD §7.7)."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from core_api.schemas.order_history import OrderListResponse, OrderResponse
from shared.models.order import Order


def list_orders(
    *,
    user_id: uuid.UUID,
    page: int = 1,
    per_page: int = 20,
    db_session: Session,
) -> OrderListResponse:
    """Возвращает заказы пользователя, DESC по created_at, с eager-load items.

    Два SQL-запроса: count(*) для total_count + SELECT с selectinload для items.
    """
    total = db_session.execute(
        select(func.count()).select_from(Order).where(Order.user_id == user_id)
    ).scalar_one()

    rows = (
        db_session.execute(
            select(Order)
            .where(Order.user_id == user_id)
            .options(selectinload(Order.items))
            .order_by(Order.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        .scalars()
        .all()
    )

    orders = [OrderResponse.model_validate(row) for row in rows]
    return OrderListResponse(
        orders=orders,
        total_count=int(total),
        page=page,
        per_page=per_page,
    )
