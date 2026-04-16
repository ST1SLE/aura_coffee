"""Pydantic-схема настроек магазина (PDD §5.2)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ShopSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    shop_lat: float | Decimal
    shop_lon: float | Decimal
    delivery_radius_km: float | Decimal | int
    min_delivery_amount: int
    free_delivery_threshold: int
    delivery_fee: int
    loyalty_percent: int
    default_prep_time_minutes: int
    estimated_delivery_time_minutes: int
    working_hours: dict
    updated_at: datetime
