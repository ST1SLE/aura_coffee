"""Pydantic-схемы customer-loyalty-api (PDD §3, §5.2, §7.1 Phase 5 item 2)."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from shared.enums import LoyaltyTransactionType


class LoyaltyBalanceResponse(BaseModel):
    """Баланс лояльности customer-а."""

    balance: int
    lifetime_accrued: int


class LoyaltyTransactionResponse(BaseModel):
    """Одна транзакция лояльности — read-only проекция LoyaltyTransaction."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: LoyaltyTransactionType
    amount: int
    balance_after: int
    order_id: uuid.UUID | None
    description: str | None
    created_at: datetime


class LoyaltyTransactionListResponse(BaseModel):
    """Пагинированный фид транзакций."""

    items: list[LoyaltyTransactionResponse]
    page: int
    per_page: int
    total: int
