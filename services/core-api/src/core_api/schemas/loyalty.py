"""Pydantic-схемы customer-loyalty-api (PDD §3, §5.2, §7.1 Phase 5 item 2)."""
# START_MODULE_CONTRACT
#   PURPOSE: Customer-side loyalty DTOs: balance + paginated transaction feed.
#   SCOPE:   Read-only Pydantic projections.
#   DEPENDS: pydantic v2, M-SHARED (LoyaltyTransactionType enum).
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §3, §5.2,
#            §7.1 Phase 5 item 2, INV-004 (financial atomicity)
#   ROLE:    TYPES
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   LoyaltyBalanceResponse        - balance + lifetime_accrued projection
#   LoyaltyTransactionResponse    - one transaction row
#   LoyaltyTransactionListResponse - paginated transaction feed
# END_MODULE_MAP

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
