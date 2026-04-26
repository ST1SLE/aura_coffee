"""Pydantic v2 DTOs для admin-users-api (PDD §6.5, §7.1 item 2, INV-013).

INV-013: ни одна DTO НЕ выставляет phone / phone_hash / deleted_at.
"""
# START_MODULE_CONTRACT
#   PURPOSE: Request/response DTOs for the admin-users-api (list, detail,
#            block/unblock, loyalty manual adjust).
#   SCOPE:   Pydantic models, no behaviour beyond validators on LoyaltyAdjustRequest.
#   DEPENDS: pydantic v2, M-SHARED (LoyaltyTransactionType enum).
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §6.5, §7.1 Phase 6 item 2,
#            INV-010, INV-013 (NO phone/phone_hash/deleted_at exposed)
#   ROLE:    TYPES
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   UserSummary             - list-row projection of a User for admin
#   UserListResponse        - paginated GET /admin/users body
#   LoyaltyTransactionItem  - read-only projection of LoyaltyTransaction
#   UserDetailResponse      - GET /admin/users/{id} body
#   BlockUserResponse       - POST /block and /unblock body
#   LoyaltyAdjustRequest    - body of manual points adjust (delta != 0, reason)
#   LoyaltyAdjustResponse   - response of manual points adjust
# END_MODULE_MAP

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from shared.enums import LoyaltyTransactionType


class UserSummary(BaseModel):
    """Краткая запись пользователя в списке для админки."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    display_name: str | None
    loyalty_balance: int
    created_at: datetime


class UserListResponse(BaseModel):
    """Пагинированный ответ GET /api/v1/admin/users."""

    model_config = ConfigDict(from_attributes=True)

    items: list[UserSummary]
    total_count: int
    page: int
    per_page: int


class LoyaltyTransactionItem(BaseModel):
    """Одна запись в последних 20 транзакциях на странице user detail.

    order_id / user_id НЕ экспортируются: ссылка на заказ — задача admin-orders.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: LoyaltyTransactionType
    amount: int
    balance_after: int
    description: str | None
    created_at: datetime


class UserDetailResponse(BaseModel):
    """Ответ GET /api/v1/admin/users/{user_id}."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    display_name: str | None
    language: str
    created_at: datetime
    loyalty_balance: int
    loyalty_transactions: list[LoyaltyTransactionItem]
    active_orders_count: int


class BlockUserResponse(BaseModel):
    """Ответ POST /block и POST /unblock."""

    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    status: Literal["blocked", "active"]
    cancelled_orders_count: int


class LoyaltyAdjustRequest(BaseModel):
    """Тело POST /loyalty/adjust (INV-004: delta и reason валидируются на layer DTO)."""

    delta: int = Field(..., description="Подписанная дельта баллов, не может быть 0")
    reason: str = Field(..., min_length=1, max_length=500)

    @field_validator("delta")
    @classmethod
    def _delta_not_zero(cls, v: int) -> int:
        if v == 0:
            raise ValueError("delta must not be zero")
        return v


class LoyaltyAdjustResponse(BaseModel):
    """Ответ POST /loyalty/adjust."""

    model_config = ConfigDict(from_attributes=True)

    transaction_id: uuid.UUID
    new_balance: int
    delta: int
