# START_MODULE_CONTRACT
#   PURPOSE: Pure-read admin dashboard helpers: time-range computation, revenue
#            and order count aggregation, popular menu items by snapshot name.
#   SCOPE:   compute_range, get_revenue_and_count, get_popular_items.
#   DEPENDS: M-SHARED (Order, OrderItem, OrderStatus), M-DATABASE
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §4.5, §7.1 Phase 6/1, INV-014
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   PopularItem            - dataclass row (name_ru, name_en, quantity)
#   compute_range          - half-open UTC [start, end) for today/week/month
#   get_revenue_and_count  - SUM(total) + COUNT(*) over COMPLETED orders
#   get_popular_items      - top-N OrderItem snapshots by quantity (INV-014)
# END_MODULE_MAP
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


# START_CONTRACT: PopularItem
#   PURPOSE: Result row for get_popular_items — a snapshot bilingual name pair
#            with summed quantity. Snapshot fields keep historical name even if
#            the menu item is later renamed (INV-014).
#   INPUTS:  name_ru: str, name_en: str, quantity: int
#   OUTPUTS: frozen dataclass instance.
#   SIDE_EFFECTS: none
# END_CONTRACT: PopularItem
@dataclass(frozen=True)
class PopularItem:
    """Строка результата get_popular_items: снимок имени + суммарное quantity."""

    name_ru: str
    name_en: str
    quantity: int


# START_CONTRACT: compute_range
#   PURPOSE: Translate "today"/"week"/"month" into a half-open UTC interval
#            [start, end), with `today` anchored to local Europe/Moscow midnight.
#   INPUTS:  range_param: Literal["today","week","month"]
#   OUTPUTS: (start: datetime, end: datetime) — both UTC.
#   SIDE_EFFECTS: reads wall clock once via datetime.now(UTC).
# END_CONTRACT: compute_range
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


# START_CONTRACT: get_revenue_and_count
#   PURPOSE: Aggregate SUM(orders.total) and COUNT(*) for COMPLETED orders in
#            the [start, end) window.
#   INPUTS:  db: Session
#            start, end: datetime (UTC, half-open)
#   OUTPUTS: (revenue: int, count: int) — both ≥ 0.
#   SIDE_EFFECTS: DB SELECT only.
# END_CONTRACT: get_revenue_and_count
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


# START_CONTRACT: get_popular_items
#   PURPOSE: Top-N snapshot groups (name_ru, name_en) by SUM(quantity) over
#            COMPLETED orders in [start, end) — INV-014 keeps historical names.
#   INPUTS:  db: Session
#            start, end: datetime
#            limit: int — defaults to 10
#   OUTPUTS: list[PopularItem] sorted by quantity DESC.
#   SIDE_EFFECTS: DB SELECT only.
#   LINKS:   PDD §4.5, INV-014
# END_CONTRACT: get_popular_items
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
