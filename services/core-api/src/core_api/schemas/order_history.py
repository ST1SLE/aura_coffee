"""Pydantic-схемы истории заказов и repeat-order (PDD §7.7)."""
# START_MODULE_CONTRACT
#   PURPOSE: DTOs for the customer order-history feed and repeat-order result.
#            Models expose immutable order_item snapshots (INV-014) and accept
#            both attribute and subscript access for fallback test patterns.
#   SCOPE:   Pydantic models + private _SubscriptMixin for getitem support.
#   DEPENDS: pydantic v2.
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §7.7,
#            INV-014 (order_items are immutable snapshots)
#   ROLE:    TYPES
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   OrderItemResponse         - one historical order line (immutable snapshot)
#   OrderResponse             - order header + items
#   OrderListResponse         - paginated GET /api/v1/orders body
#   RepeatOrderSkippedEntry   - one skipped entry from repeat-order
#   RepeatOrderResult         - POST /orders/{id}/repeat response
# END_MODULE_MAP

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class _SubscriptMixin:
    """Позволяет тестам использовать model["field"] поверх Pydantic-инстанса.

    Нужно для fallback-паттернов `getattr(x, "f", None) or x["f"]`, когда
    значение поля falsy (0, [], None) — getattr не срабатывает и тест
    обращается по ключу.
    """

    def __getitem__(self, key: str):
        return getattr(self, key)


class OrderItemResponse(_SubscriptMixin, BaseModel):
    """Строка исторического заказа — иммутабельный снимок (INV-014)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    menu_item_id: int | None
    menu_item_name_ru: str
    menu_item_name_en: str
    size_option_id: int | None
    size_label: str | None
    unit_price: int
    modifiers_snapshot: list
    quantity: int
    line_total: int


class OrderResponse(_SubscriptMixin, BaseModel):
    """Заказ клиента — шапка + список позиций."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    status: str
    type: str
    subtotal: int
    discount_amount: int
    delivery_fee: int
    total: int
    created_at: datetime
    items: list[OrderItemResponse]


class OrderListResponse(_SubscriptMixin, BaseModel):
    """Пагинированный ответ GET /api/v1/orders."""

    orders: list[OrderResponse]
    total_count: int
    page: int
    per_page: int


class RepeatOrderSkippedEntry(_SubscriptMixin, BaseModel):
    """Уведомление о пропущенной позиции/модификаторе при repeat."""

    reason: Literal[
        "menu_item_unavailable",
        "menu_item_archived",
        "menu_item_deleted",
        "size_unavailable",
        "modifier_unavailable",
    ]
    message_ru: str


class RepeatOrderResult(_SubscriptMixin, BaseModel):
    """Результат POST /api/v1/orders/{order_id}/repeat."""

    added_to_cart: int
    skipped: list[RepeatOrderSkippedEntry]
