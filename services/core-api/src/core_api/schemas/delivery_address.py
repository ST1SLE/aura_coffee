"""Pydantic-схемы для CRUD сохранённых адресов доставки (PDD §3, §5.2)."""
# START_MODULE_CONTRACT
#   PURPOSE: DTOs for the customer's saved delivery addresses CRUD.
#   SCOPE:   Pydantic create/update/read models. No business logic.
#   DEPENDS: pydantic v2.
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §3, §5.2, §7.3,
#            INV-013 (address text is PII — only return to address owner)
#   ROLE:    TYPES
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   DeliveryAddressCreate  - POST body for creating a new saved address
#   DeliveryAddressUpdate  - PATCH body (partial; lat/lon immutable here)
#   DeliveryAddressRead    - response projection of DeliveryAddress
# END_MODULE_MAP

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
