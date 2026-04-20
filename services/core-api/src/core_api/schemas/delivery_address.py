"""Pydantic-схемы для CRUD сохранённых адресов доставки (PDD §3, §5.2)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DeliveryAddressCreate(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    address_text: str = Field(min_length=1, max_length=500)
    lat: float
    lon: float
    apartment: str | None = Field(default=None, max_length=20)
    entrance: str | None = Field(default=None, max_length=20)
    floor: str | None = Field(default=None, max_length=20)
    comment: str | None = Field(default=None, max_length=500)
    is_default: bool = False


class DeliveryAddressUpdate(BaseModel):
    # Все поля опциональны; lat/lon не меняются через PATCH (отдельный флоу).
    model_config = ConfigDict(extra="forbid")

    label: str | None = Field(default=None, min_length=1, max_length=100)
    address_text: str | None = Field(default=None, min_length=1, max_length=500)
    apartment: str | None = Field(default=None, max_length=20)
    entrance: str | None = Field(default=None, max_length=20)
    floor: str | None = Field(default=None, max_length=20)
    comment: str | None = Field(default=None, max_length=500)
    is_default: bool | None = None


class DeliveryAddressRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    label: str
    address_text: str
    lat: float
    lon: float
    apartment: str | None = None
    entrance: str | None = None
    floor: str | None = None
    comment: str | None = None
    is_default: bool
    created_at: datetime
    updated_at: datetime
