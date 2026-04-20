"""Бизнес-логика дашборда админа (PDD §4.5, §7.1 Phase 6 item 1).

Три независимых чистых хелпера:
- compute_range  — диапазон [start, end) в UTC по параметру range
- get_revenue_and_count  — (SUM(total), COUNT(*)) по COMPLETED заказам
- get_popular_items  — топ-10 позиций, сгруппированных по snapshot (INV-014)

Модуль никуда не пишет. Единая точка чтения часов — datetime.now(timezone.utc)
в compute_range; остальные хелперы принимают уже вычисленный диапазон.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from shared.enums import OrderStatus
from shared.models.order import Order
from shared.models.order_item import OrderItem

# Часовой пояс заведения — фиксированно Москва (один магазин, нет TZ-колонки в shop_settings).
TIMEZONE = "Europe/Moscow"


@dataclass(frozen=True)
class PopularItem:
    """Строка результата get_popular_items: снимок имени + суммарное quantity."""

    name_ru: str
    name_en: str
    quantity: int


def compute_range(range_param: Literal["today", "week", "month"]) -> tuple[datetime, datetime]:
    """Возвращает half-open интервал [start, end) в UTC.

    - today:  start = локальная полночь Europe/Moscow текущей даты, переведённая в UTC
    - week:   start = end - 7 дней
    - month:  start = end - 30 дней
    end = datetime.now(timezone.utc), зафиксированный один раз на вызов.
    """
    end = datetime.now(timezone.utc)

    if range_param == "today":
        tz = ZoneInfo(TIMEZONE)
        local_midnight = datetime.combine(date.today(), time.min, tzinfo=tz)
        start = local_midnight.astimezone(timezone.utc)
    elif range_param == "week":
        start = end - timedelta(days=7)
    elif range_param == "month":
        start = end - timedelta(days=30)
    else:  # pragma: no cover — FastAPI Literal отсечёт раньше
        raise ValueError(f"Unknown range: {range_param!r}")

    return start, end


def get_revenue_and_count(db: Session, start: datetime, end: datetime) -> tuple[int, int]:
    """Выручка (SUM(orders.total)) и кол-во COMPLETED заказов в [start, end)."""
    stmt = select(
        func.coalesce(func.sum(Order.total), 0),
        func.count(),
    ).where(
        Order.status == OrderStatus.COMPLETED,
        Order.created_at >= start,
        Order.created_at < end,
    )
    revenue, count = db.execute(stmt).one()
    return int(revenue), int(count)


def get_popular_items(
    db: Session,
    start: datetime,
    end: datetime,
    limit: int = 10,
) -> list[PopularItem]:
    """Топ-`limit` snapshot-групп (name_ru, name_en) по SUM(quantity), DESC.

    Группировка — по snapshot из order_items (INV-014): переименование позиции
    в меню НЕ схлопывает строки за период, обе исторические вариации видны.
    """
    quantity_sum = func.sum(OrderItem.quantity).label("quantity")
    stmt = (
        select(
            OrderItem.menu_item_name_ru,
            OrderItem.menu_item_name_en,
            quantity_sum,
        )
        .join(Order, OrderItem.order_id == Order.id)
        .where(
            Order.status == OrderStatus.COMPLETED,
            Order.created_at >= start,
            Order.created_at < end,
        )
        .group_by(OrderItem.menu_item_name_ru, OrderItem.menu_item_name_en)
        .order_by(desc("quantity"))
        .limit(limit)
    )
    rows = db.execute(stmt).all()
    return [
        PopularItem(name_ru=r[0], name_en=r[1], quantity=int(r[2]))
        for r in rows
    ]
