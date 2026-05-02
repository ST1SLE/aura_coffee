"""Маршруты admin-users-api (PDD §6.5, §7.1 item 2, INV-010).

RBAC: только {ADMIN}, прописано в rbac_matrix.ROUTE_MATRIX.
401/403 обрабатывает RBACMiddleware — здесь явных auth-deps нет.

Error → HTTP mapping:
    UserNotFoundError        → 404
    InvalidUserStateError    → 409 detail="invalid_user_state"
    InsufficientBalanceError → 422 detail="insufficient_balance"
"""
from __future__ import annotations

# START_MODULE_CONTRACT
#   PURPOSE: HTTP routes for admin user management under
#            /api/v1/admin/users — list, detail, block/unblock, delete blocked
#            users, and loyalty adjustment.
#   SCOPE:   User lifecycle transitions (PDD §6.5) and ADMIN_ADJUSTMENT
#            loyalty mutations. Cascading order cancellation on block/delete
#            (PDD §7.6).
#   DEPENDS: M-DATABASE (Session), Redis, core_api.services.admin_users,
#            core_api.services.auth, RBACMiddleware (ADMIN-only via
#            rbac_matrix.ROUTE_MATRIX).
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §6.5, §7.1 item 2,
#            §7.6, INV-002, INV-004 (atomic loyalty), INV-010, INV-013
#            (PII isolation), INV-016.
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   router                       - APIRouter("/api/v1/admin/users", tags=["admin-users"])
#   list_admin_users             - GET  /api/v1/admin/users
#   get_admin_user_detail        - GET  /api/v1/admin/users/{user_id}
#   block_admin_user             - POST /api/v1/admin/users/{user_id}/block
#   unblock_admin_user           - POST /api/v1/admin/users/{user_id}/unblock
#   adjust_admin_user_loyalty    - POST /api/v1/admin/users/{user_id}/loyalty/adjust
#   delete_admin_user            - DELETE /api/v1/admin/users/{user_id}
# END_MODULE_MAP

import uuid
from typing import Literal

import redis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from core_api.deps import database as _db_dep
from core_api.deps import redis as _redis_dep
from core_api.schemas.admin_users import (
    BlockUserResponse,
    LoyaltyAdjustRequest,
    LoyaltyAdjustResponse,
    UserDetailResponse,
    UserListResponse,
)
from core_api.schemas.account_deletion import AccountDeletionResponse
from core_api.services.account_deletion import (
    AccountDeletionActiveOrderError,
    AccountDeletionInvalidStateError,
    AccountDeletionNotFoundError,
    delete_blocked_customer_account,
)
from core_api.services.auth import AuthService
from core_api.services.admin_users import (
    InsufficientBalanceError,
    InvalidUserStateError,
    UserNotFoundError,
    adjust_loyalty,
    block_user,
    get_user_detail,
    list_users,
    unblock_user,
)
from shared.grace.logging import get_grace_logger

router = APIRouter(prefix="/api/v1/admin/users", tags=["admin-users"])
_grace_log = get_grace_logger("CoreApi")


# Обёртка для patch-friendly dep resolution (см. routers/admin_orders.py)
def _get_session():
    yield from _db_dep.get_session()


def _get_redis():
    yield from _redis_dep.get_redis()


StatusFilter = Literal[
    "active", "blocked", "pending_verification", "deleted", "all"
]


# START_CONTRACT: list_admin_users
#   PURPOSE: Paginated user list with status filter and free-text search.
#   INPUTS:  status: StatusFilter (query), search: str|None, page, per_page,
#            Session.
#   OUTPUTS: 200 UserListResponse.
#   SIDE_EFFECTS: none (read-only DB query).
#   LINKS:   PDD §4.5, §6.5, INV-002, INV-010, INV-013, services.admin_users.
# END_CONTRACT: list_admin_users
@router.get("", response_model=UserListResponse)
def list_admin_users(
    status: StatusFilter = Query("all"),
    search: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(_get_session),
) -> UserListResponse:
    """Пагинированный список пользователей для админки (PDD §4.5, §6.5)."""
    return list_users(
        db=db,
        status=status,
        search=search,
        page=page,
        per_page=per_page,
    )


# START_CONTRACT: get_admin_user_detail
#   PURPOSE: Return profile + loyalty + active orders snapshot for one user.
#   INPUTS:  user_id: UUID, Session.
#   OUTPUTS: 200 UserDetailResponse; 404 user_not_found.
#   SIDE_EFFECTS: none.
#   LINKS:   PDD §6.5, INV-002, INV-010, INV-013, services.admin_users.
# END_CONTRACT: get_admin_user_detail
@router.get("/{user_id}", response_model=UserDetailResponse)
def get_admin_user_detail(
    user_id: uuid.UUID,
    db: Session = Depends(_get_session),
) -> UserDetailResponse:
    """Карточка пользователя: profile + loyalty + активные заказы."""
    try:
        return get_user_detail(db=db, user_id=user_id)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found"
        ) from exc


# START_CONTRACT: block_admin_user
#   PURPOSE: ACTIVE → BLOCKED transition + cascade-cancel of all active
#            orders for that user (PDD §6.5 + §7.6).
#   INPUTS:  user_id: UUID, Session, Redis client.
#   OUTPUTS: 200 BlockUserResponse; 404 not found; 409 invalid_user_state.
#   SIDE_EFFECTS: DB updates — user.status, plus cascade order cancellations;
#                 Redis session revocation for the blocked customer.
#   LINKS:   PDD §6.5, §7.6, INV-002, INV-010, INV-016, services.admin_users.
# END_CONTRACT: block_admin_user
@router.post("/{user_id}/block", response_model=BlockUserResponse)
def block_admin_user(
    user_id: uuid.UUID,
    db: Session = Depends(_get_session),
    r: redis.Redis = Depends(_get_redis),
) -> BlockUserResponse:
    """ACTIVE → BLOCKED + каскад отмены заказов (PDD §6.5, §7.6)."""
    try:
        response = block_user(db=db, user_id=user_id)
        AuthService(r).revoke_user_sessions(user_id)
        return response
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found"
        ) from exc
    except InvalidUserStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="invalid_user_state"
        ) from exc


# START_CONTRACT: unblock_admin_user
#   PURPOSE: BLOCKED → ACTIVE transition (no cascading side effects).
#   INPUTS:  user_id: UUID, Session.
#   OUTPUTS: 200 BlockUserResponse; 404 not found; 409 invalid_user_state.
#   SIDE_EFFECTS: DB update — user.status.
#   LINKS:   PDD §6.5, INV-002, INV-010, INV-016, services.admin_users.
# END_CONTRACT: unblock_admin_user
@router.post("/{user_id}/unblock", response_model=BlockUserResponse)
def unblock_admin_user(
    user_id: uuid.UUID,
    db: Session = Depends(_get_session),
) -> BlockUserResponse:
    """BLOCKED → ACTIVE без каскада (PDD §6.5, INV-016)."""
    try:
        return unblock_user(db=db, user_id=user_id)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found"
        ) from exc
    except InvalidUserStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="invalid_user_state"
        ) from exc


# START_CONTRACT: adjust_admin_user_loyalty
#   PURPOSE: ADMIN_ADJUSTMENT loyalty mutation (positive or negative)
#            within a single SELECT … FOR UPDATE transaction.
#   INPUTS:  user_id: UUID, body: LoyaltyAdjustRequest (delta, reason),
#            Session.
#   OUTPUTS: 200 LoyaltyAdjustResponse; 404 not found;
#            409 invalid_user_state; 422 insufficient_balance.
#   SIDE_EFFECTS: DB writes — loyalty balance + transactions row,
#                 atomic single transaction (INV-004).
#   LINKS:   PDD §6.5, §7.x loyalty, INV-002, INV-004, INV-010,
#            services.admin_users.
# END_CONTRACT: adjust_admin_user_loyalty
@router.post("/{user_id}/loyalty/adjust", response_model=LoyaltyAdjustResponse)
def adjust_admin_user_loyalty(
    user_id: uuid.UUID,
    body: LoyaltyAdjustRequest,
    db: Session = Depends(_get_session),
) -> LoyaltyAdjustResponse:
    """ADMIN_ADJUSTMENT: одна атомарная tx с SELECT … FOR UPDATE (INV-004)."""
    try:
        return adjust_loyalty(
            db=db, user_id=user_id, delta=body.delta, reason=body.reason
        )
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found"
        ) from exc
    except InvalidUserStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="invalid_user_state"
        ) from exc
    except InsufficientBalanceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="insufficient_balance",
        ) from exc


# START_CONTRACT: delete_admin_user
#   PURPOSE: Admin deletion of a BLOCKED customer account via PDD §6.5
#            BLOCKED→DELETED, preserving order history while removing PII.
#   INPUTS:  user_id: UUID, Session, Redis client.
#   OUTPUTS: 200 AccountDeletionResponse; 404 not found; 409 invalid state or
#            active_order_not_deletable.
#   SIDE_EFFECTS: DB tombstone/PII cleanup, cancellable order cancellations,
#                 loyalty zeroing, Redis session revocation.
#   LINKS:   PDD §6.5, INV-002, INV-010, INV-013, INV-016,
#            services.account_deletion.
# END_CONTRACT: delete_admin_user
@router.delete("/{user_id}", response_model=AccountDeletionResponse)
def delete_admin_user(
    user_id: uuid.UUID,
    db: Session = Depends(_get_session),
    r: redis.Redis = Depends(_get_redis),
) -> AccountDeletionResponse:
    _grace_log.block(
        "admin.users.delete",
        "BLOCK_AUTH_VERIFY",
        "admin account deletion authorized",
        user_id=str(user_id),
    )
    try:
        response = delete_blocked_customer_account(db=db, user_id=user_id)
        AuthService(r).revoke_user_sessions(user_id)
        return response
    except AccountDeletionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found"
        ) from exc
    except AccountDeletionActiveOrderError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="active_order_not_deletable",
        ) from exc
    except AccountDeletionInvalidStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="invalid_user_state"
        ) from exc
