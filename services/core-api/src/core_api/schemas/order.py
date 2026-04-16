"""Pydantic-схемы заказов (PDD §5.2, §6.1, §7.7)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from shared.enums import OrderStatus, OrderType


class DeliveryAddress(BaseModel):
    """Адрес доставки (INV-013: живёт только в JSONB-снимках, не в колонках)."""

    text: str
    lat: float
    lon: float
    apartment: str | None = None
    entrance: str | None = None
    floor: str | None = None
    comment: str | None = None


class CreateOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: OrderType
    delivery_address: DeliveryAddress | None = None
    requested_time: datetime | None = None
    promocode_code: str | None = None
    points_to_use: int = Field(default=0, ge=0)


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    menu_item_name_ru: str
    menu_item_name_en: str
    size_label: str | None = None
    unit_price: int
    modifiers_snapshot: list[Any] = Field(default_factory=list)
    quantity: int
    line_total: int


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: OrderStatus
    type: OrderType
    items: list[OrderItemResponse] = Field(default_factory=list)
    subtotal: int
    discount_amount: int
    points_used: int
    delivery_fee: int
    total: int
    estimated_accrual: int
    confirmation_url: str | None = None
    requested_time: datetime | None = None
    estimated_ready_at: datetime | None = None
    cancelled_by: str | None = None
    cancelled_at: datetime | None = None
    created_at: datetime


class OrderListResponse(BaseModel):
    items: list[OrderResponse]
    total_count: int
    page: int
    per_page: int


class OrderStatusUpdate(BaseModel):
    new_status: OrderStatus


class CancelOrderRequest(BaseModel):
    reason: str | None = None


class SkippedItem(BaseModel):
    name: str
    reason: str


class RepeatOrderResult(BaseModel):
    added_to_cart: int
    skipped: list[SkippedItem] = Field(default_factory=list)
