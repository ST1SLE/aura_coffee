"""Pydantic-схемы заказов (PDD §5.2, §6.1, §7.7)."""
# START_MODULE_CONTRACT
#   PURPOSE: Order DTOs covering create/read, status update, cancel and repeat.
#            Holds the XOR validator for delivery vs. saved-address selection.
#   SCOPE:   Pydantic models + a model_validator on CreateOrderRequest.
#   DEPENDS: pydantic v2, M-SHARED (OrderStatus, OrderType enums).
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §5.2, §6.1 (order FSM),
#            §7.7 (repeat order); INV-013 (delivery_address only inside snapshot,
#            never as PII columns); INV-014 (order_items snapshots)
#   ROLE:    TYPES
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   DeliveryAddress       - inline delivery snapshot (text/lat/lon/details)
#   CreateOrderRequest    - POST /api/v1/orders body w/ delivery XOR validator
#   OrderItemResponse     - one line snapshot in OrderResponse (INV-014)
#   OrderResponse         - full order projection (header + items)
#   OrderListResponse     - paginated GET /api/v1/orders body
#   OrderStatusUpdate     - PATCH /orders/{id}/status body
#   CancelOrderRequest    - POST /orders/{id}/cancel body
#   SkippedItem           - one skipped entry from RepeatOrderResult
#   RepeatOrderResult     - POST /orders/{id}/repeat response
# END_MODULE_MAP

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    delivery_address_id: UUID | None = None
    requested_time: datetime | None = None
    promocode_code: str | None = None
    points_to_use: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _check_delivery_address_xor(self) -> "CreateOrderRequest":
        # XOR: для доставки должно быть выставлено РОВНО одно из двух полей.
        if self.type == OrderType.DELIVERY:
            has_inline = self.delivery_address is not None
            has_id = self.delivery_address_id is not None
            if has_inline == has_id:
                raise ValueError(
                    "For type=delivery, set exactly one of delivery_address "
                    "or delivery_address_id (both or neither is invalid)."
                )
        return self


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
