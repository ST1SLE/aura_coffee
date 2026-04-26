"""Маршруты customer-loyalty-api (PDD §3, §5.2, §7.1 Phase 5 item 2).

GET /api/v1/profile/loyalty              → LoyaltyBalanceResponse
GET /api/v1/profile/loyalty/transactions → LoyaltyTransactionListResponse

RBAC: только {CUSTOMER} — прописано в rbac_matrix.ROUTE_MATRIX.
"""
from __future__ import annotations

# START_MODULE_CONTRACT
#   PURPOSE: HTTP routes for the customer loyalty surface under
#            /api/v1/profile/loyalty — current balance + transaction feed.
#   SCOPE:   Read-only views of the user's loyalty balance and history.
#            CUSTOMER-only via rbac_matrix.ROUTE_MATRIX.
#   DEPENDS: M-DATABASE (Session), core_api.services.loyalty,
#            core_api.deps.{auth,database}.
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §3, §5.2, §7.1
#            Phase 5 item 2, INV-002, INV-013 (own-data only).
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   router                         - APIRouter("/api/v1/profile/loyalty", tags=["loyalty"])
#   get_my_loyalty_balance         - GET /api/v1/profile/loyalty
#   list_my_loyalty_transactions   - GET /api/v1/profile/loyalty/transactions
# END_MODULE_MAP

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from core_api.deps import database as _db_dep
from core_api.deps.auth import get_current_user
from core_api.schemas.loyalty import (
    LoyaltyBalanceResponse,
    LoyaltyTransactionListResponse,
)
from core_api.services.loyalty import (
    LoyaltyAccountMissingError,
    get_balance,
    list_transactions,
)

router = APIRouter(prefix="/api/v1/profile/loyalty", tags=["loyalty"])


# Обёртка для patch-friendly dep resolution (см. routers/order_history.py)
def _get_session():
    yield from _db_dep.get_session()


# START_CONTRACT: get_my_loyalty_balance
#   PURPOSE: Return current balance + lifetime_accrued for the customer.
#   INPUTS:  current_user, Session.
#   OUTPUTS: 200 LoyaltyBalanceResponse; 500 if loyalty account missing.
#   SIDE_EFFECTS: none.
#   LINKS:   PDD §3, INV-002, INV-013, services.loyalty.
# END_CONTRACT: get_my_loyalty_balance
@router.get("", response_model=LoyaltyBalanceResponse)
def get_my_loyalty_balance(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(_get_session),
) -> LoyaltyBalanceResponse:
    """Текущий баланс + lifetime_accrued для customer-а."""
    try:
        return get_balance(user_id=current_user["user_id"], db_session=db)
    except LoyaltyAccountMissingError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="loyalty_account_missing",
        ) from exc


# START_CONTRACT: list_my_loyalty_transactions
#   PURPOSE: Paginated DESC feed of loyalty transactions for the customer.
#   INPUTS:  page (1+), per_page (1..100), current_user, Session.
#   OUTPUTS: 200 LoyaltyTransactionListResponse.
#   SIDE_EFFECTS: none.
#   LINKS:   PDD §3, §7.1 Phase 5 item 2, INV-002, INV-013, services.loyalty.
# END_CONTRACT: list_my_loyalty_transactions
@router.get("/transactions", response_model=LoyaltyTransactionListResponse)
def list_my_loyalty_transactions(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(_get_session),
) -> LoyaltyTransactionListResponse:
    """Пагинированный DESC-фид транзакций текущего customer-а."""
    return list_transactions(
        user_id=current_user["user_id"],
        page=page,
        per_page=per_page,
        db_session=db,
    )
