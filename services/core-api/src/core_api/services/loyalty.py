# START_MODULE_CONTRACT
#   PURPOSE: Customer-scoped read-only loyalty queries — current balance and
#            transaction history. Defence-in-depth: re-applies user_id filter
#            even though router already enforces auth (INV-002, INV-010).
#   SCOPE:   get_balance, list_transactions.
#   DEPENDS: M-SHARED (LoyaltyAccount, LoyaltyTransaction), M-DATABASE,
#            schemas.loyalty
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §3, §5.2, INV-002, INV-010
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   LoyaltyAccountMissingError - integrity issue: account row missing
#   get_balance                - balance + lifetime_accrued
#   list_transactions          - paginated DESC feed
# END_MODULE_MAP
"""Customer-scoped read-only сервис лояльности (PDD §3, §5.2, §7.1 Phase 5).

Фильтрация по user_id — defence-in-depth (INV-002, INV-010): сервис не
доверяет handler-у и повторно применяет WHERE user_id = :user_id.
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core_api.schemas.loyalty import (
    LoyaltyBalanceResponse,
    LoyaltyTransactionListResponse,
    LoyaltyTransactionResponse,
)
from shared.enums import LoyaltyTransactionType
from shared.models.loyalty_account import LoyaltyAccount
from shared.models.loyalty_transaction import LoyaltyTransaction


# START_CONTRACT: LoyaltyAccountMissingError
#   PURPOSE: Signal that loyalty_accounts row is absent for an active user —
#            indicates a data-integrity incident; router maps to HTTP 500.
#   INPUTS:  message: str
#   OUTPUTS: Exception instance.
#   SIDE_EFFECTS: none
# END_CONTRACT: LoyaltyAccountMissingError
class LoyaltyAccountMissingError(Exception):
    """loyalty_accounts row отсутствует — data-integrity issue.

    Row обязан создаваться при ACTIVE-регистрации (Phase 1). Эта ошибка
    сигнализирует инцидент, на API-boundary → HTTP 500.
    """


# START_CONTRACT: get_balance
#   PURPOSE: Read current balance + lifetime accrual sum for a user.
#   INPUTS:  user_id: UUID, db_session: Session
#   OUTPUTS: LoyaltyBalanceResponse
#   SIDE_EFFECTS: DB SELECT only; raises LoyaltyAccountMissingError if account
#                 row missing.
#   LINKS:   INV-003, INV-013
# END_CONTRACT: get_balance
def get_balance(
    *, user_id: uuid.UUID, db_session: Session
) -> LoyaltyBalanceResponse:
    """Возвращает balance + lifetime_accrued (SUM только ACCRUAL-транзакций)."""
    account = db_session.get(LoyaltyAccount, user_id)
    if account is None:
        raise LoyaltyAccountMissingError(
            f"loyalty_accounts row отсутствует для user_id={user_id}"
        )

    lifetime = db_session.execute(
        select(func.coalesce(func.sum(LoyaltyTransaction.amount), 0)).where(
            LoyaltyTransaction.user_id == user_id,
            LoyaltyTransaction.type == LoyaltyTransactionType.ACCRUAL,
        )
    ).scalar_one()

    return LoyaltyBalanceResponse(
        balance=int(account.balance),
        lifetime_accrued=int(lifetime),
    )


# START_CONTRACT: list_transactions
#   PURPOSE: Paginated DESC feed of loyalty transactions for one user.
#   INPUTS:  user_id: UUID, page: int, per_page: int, db_session: Session
#   OUTPUTS: LoyaltyTransactionListResponse
#   SIDE_EFFECTS: DB SELECTs only.
#   LINKS:   INV-002, INV-010, INV-013
# END_CONTRACT: list_transactions
def list_transactions(
    *,
    user_id: uuid.UUID,
    page: int,
    per_page: int,
    db_session: Session,
) -> LoyaltyTransactionListResponse:
    """Пагинированный DESC-фид транзакций конкретного user-а."""
    total = db_session.execute(
        select(func.count())
        .select_from(LoyaltyTransaction)
        .where(LoyaltyTransaction.user_id == user_id)
    ).scalar_one()

    rows = (
        db_session.execute(
            select(LoyaltyTransaction)
            .where(LoyaltyTransaction.user_id == user_id)
            .order_by(LoyaltyTransaction.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        .scalars()
        .all()
    )

    items = [LoyaltyTransactionResponse.model_validate(row) for row in rows]
    return LoyaltyTransactionListResponse(
        items=items,
        page=page,
        per_page=per_page,
        total=int(total),
    )
