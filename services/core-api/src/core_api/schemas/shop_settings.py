"""Pydantic-схемы настроек магазина (PDD §5.2, §6.1).

ShopSettingsResponse — read-only snapshot singleton-row.
ShopSettingsUpdate — full-snapshot body для PUT /api/v1/admin/settings.
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


DAY_KEYS: tuple[str, ...] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


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
    auto_close_minutes: int
    working_hours: dict
    updated_at: datetime


class WorkingHoursSlot(BaseModel):
    """Слот рабочих часов дня: {"open":"HH:MM","close":"HH:MM"}, open < close."""

    model_config = ConfigDict(extra="forbid")

    open: str
    close: str

    @field_validator("open", "close")
    @classmethod
    def _validate_time_format(cls, value: str) -> str:
        if not _TIME_RE.match(value):
            raise ValueError("время должно быть в формате HH:MM (00-23:00-59)")
        return value

    @model_validator(mode="after")
    def _open_before_close(self) -> "WorkingHoursSlot":
        # Лексикографическое сравнение строк HH:MM эквивалентно временному
        # сравнению, так как формат фиксированной ширины с ведущими нулями.
        if self.open >= self.close:
            raise ValueError("open должен быть строго меньше close")
        return self


class ShopSettingsUpdate(BaseModel):
    """Полный snapshot для PUT /api/v1/admin/settings."""

    model_config = ConfigDict(extra="forbid")

    shop_lat: Decimal = Field(ge=Decimal("-90"), le=Decimal("90"))
    shop_lon: Decimal = Field(ge=Decimal("-180"), le=Decimal("180"))
    delivery_radius_km: Decimal = Field(ge=Decimal("0.1"), le=Decimal("50"))
    min_delivery_amount: int = Field(ge=0)
    free_delivery_threshold: int = Field(ge=0)
    delivery_fee: int = Field(ge=0)
    loyalty_percent: int = Field(ge=0, le=100)
    default_prep_time_minutes: int = Field(ge=1)
    estimated_delivery_time_minutes: int = Field(ge=1)
    auto_close_minutes: int = Field(ge=1, le=1440)
    working_hours: dict[str, WorkingHoursSlot | None]

    @model_validator(mode="after")
    def _validate_invariants(self) -> "ShopSettingsUpdate":
        # working_hours: ровно 7 дней mon..sun
        if set(self.working_hours.keys()) != set(DAY_KEYS):
            missing = set(DAY_KEYS) - set(self.working_hours.keys())
            extra = set(self.working_hours.keys()) - set(DAY_KEYS)
            raise ValueError(
                f"working_hours: ожидались ключи {set(DAY_KEYS)}, "
                f"отсутствуют: {missing}, лишние: {extra}"
            )
        # free_delivery_threshold ≥ min_delivery_amount
        if self.free_delivery_threshold < self.min_delivery_amount:
            raise ValueError(
                "free_delivery_threshold должен быть >= min_delivery_amount"
            )
        return self
