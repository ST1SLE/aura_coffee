"""Схемы для admin-promocodes-api (PDD §6.6, INV-010, INV-011).

Computed `state` вычисляется в сервисе; здесь — только контракт.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from shared.enums import PromocodeDiscountType

PromocodeState = Literal["inactive", "active", "expired", "exhausted"]

_CODE_PATTERN = re.compile(r"^[A-Z0-9_-]+$")

CodeStr = Annotated[str, StringConstraints(min_length=1, max_length=64)]


def _check_discount_bounds(
    discount_type: PromocodeDiscountType | None,
    discount_value: int | None,
) -> None:
    if discount_value is None or discount_type is None:
        return
    if discount_value <= 0:
        raise ValueError("discount_value must be positive")
    if discount_type == PromocodeDiscountType.PERCENT and discount_value > 100:
        raise ValueError("percent discount_value must be <= 100")


def _check_dates(valid_from: datetime | None, valid_until: datetime | None) -> None:
    if valid_from is not None and valid_until is not None and valid_from >= valid_until:
        raise ValueError("valid_from must be strictly before valid_until")


def _check_quotas(max_uses: int | None, max_uses_per_user: int | None) -> None:
    if (
        max_uses is not None
        and max_uses_per_user is not None
        and max_uses_per_user > max_uses
    ):
        raise ValueError("max_uses_per_user must be <= max_uses")


class PromocodeCreate(BaseModel):
    code: CodeStr
    discount_type: PromocodeDiscountType
    discount_value: int
    min_order_amount: int = 0
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    max_uses: int | None = None
    max_uses_per_user: int | None = None

    @field_validator("code", mode="before")
    @classmethod
    def _canonicalize_code(cls, v: object) -> object:
        if isinstance(v, str):
            up = v.upper()
            if not _CODE_PATTERN.match(up):
                raise ValueError("code must match ^[A-Z0-9_-]+$ after uppercasing")
            return up
        return v

    @model_validator(mode="after")
    def _check_invariants(self) -> "PromocodeCreate":
        _check_discount_bounds(self.discount_type, self.discount_value)
        _check_dates(self.valid_from, self.valid_until)
        _check_quotas(self.max_uses, self.max_uses_per_user)
        if self.min_order_amount < 0:
            raise ValueError("min_order_amount must be >= 0")
        return self


class PromocodeUpdate(BaseModel):
    code: CodeStr | None = None
    discount_type: PromocodeDiscountType | None = None
    discount_value: int | None = None
    min_order_amount: int | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    max_uses: int | None = None
    max_uses_per_user: int | None = None
    is_active: bool | None = None

    @field_validator("code", mode="before")
    @classmethod
    def _canonicalize_code(cls, v: object) -> object:
        if v is None:
            return v
        if isinstance(v, str):
            up = v.upper()
            if not _CODE_PATTERN.match(up):
                raise ValueError("code must match ^[A-Z0-9_-]+$ after uppercasing")
            return up
        return v

    @model_validator(mode="after")
    def _check_invariants(self) -> "PromocodeUpdate":
        if self.discount_type is not None and self.discount_value is not None:
            _check_discount_bounds(self.discount_type, self.discount_value)
        elif self.discount_value is not None and self.discount_value <= 0:
            raise ValueError("discount_value must be positive")
        if self.min_order_amount is not None and self.min_order_amount < 0:
            raise ValueError("min_order_amount must be >= 0")
        return self


class PromocodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    discount_type: PromocodeDiscountType
    discount_value: int
    min_order_amount: int
    valid_from: datetime | None
    valid_until: datetime | None
    max_uses: int | None
    max_uses_per_user: int | None
    current_uses: int
    is_active: bool
    created_at: datetime
    state: PromocodeState


class PromocodeListResponse(BaseModel):
    items: list[PromocodeResponse]
    total_count: int
    page: int = Field(ge=1)
    per_page: int = Field(ge=1, le=100)
