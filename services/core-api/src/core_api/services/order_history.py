"""Сервис list_orders — пагинированная история заказов пользователя (PDD §7.7).

Дополнительно: staff-scoped helpers для admin-orders-api (PDD §4.5, INV-010):
- list_orders_for_staff: пагинированный фид заказов всех клиентов.
- get_order_for_staff: одиночный заказ без ownership-check.
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from core_api.schemas.order_history import OrderListResponse, OrderResponse
from shared.enums import OrderStatus, OrderType
from shared.models.order import Order


# Финальные статусы — для них фид сортируется по updated_at DESC (PDD §5.4).
_FINALIZED_STATUSES = {OrderStatus.COMPLETED, OrderStatus.CANCELLED}


class OrderNotFoundForStaffError(Exception):
    """Заказ с таким id отсутствует — staff-вариант (отделён от customer-scoped ошибки)."""


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


def list_orders_for_staff(
    *,
    status_filter: OrderStatus | str,
    type_filter: OrderType | None,
    page: int,
    per_page: int,
    db_session: Session,
) -> OrderListResponse:
    """Staff-scoped фид: видны заказы всех пользователей (INV-010).

    Семантика status_filter:
    - "active" → status NOT IN (COMPLETED, CANCELLED), хитит partial index из PDD §5.4.
    - конкретный OrderStatus → status = <value>.

    Сортировка:
    - финальные (COMPLETED, CANCELLED) → updated_at DESC;
    - остальные (включая "active") → created_at DESC.
    """
    where_clauses = []
    if status_filter == "active":
        where_clauses.append(Order.status.notin_(_FINALIZED_STATUSES))
        order_by = Order.created_at.desc()
    else:
        # На этом пути status_filter уже OrderStatus (валидируется в роутере).
        where_clauses.append(Order.status == status_filter)
        if status_filter in _FINALIZED_STATUSES:
            order_by = Order.updated_at.desc()
        else:
            order_by = Order.created_at.desc()

    if type_filter is not None:
        where_clauses.append(Order.type == type_filter)

    total = db_session.execute(
        select(func.count()).select_from(Order).where(*where_clauses)
    ).scalar_one()

    rows = (
        db_session.execute(
            select(Order)
            .where(*where_clauses)
            .options(selectinload(Order.items))
            .order_by(order_by)
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


def get_order_for_staff(
    *,
    order_id: uuid.UUID,
    db_session: Session,
) -> OrderResponse:
    """Одиночный заказ без ownership-check (INV-010, S-ADMIN-003)."""
    row = db_session.execute(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.items))
    ).scalar_one_or_none()

    if row is None:
        raise OrderNotFoundForStaffError(f"order {order_id} not found")

    return OrderResponse.model_validate(row)
