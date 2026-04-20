"""Маршруты admin-users-api (PDD §6.5, §7.1 item 2, INV-010).

RBAC: только {ADMIN}, прописано в rbac_matrix.ROUTE_MATRIX.
401/403 обрабатывает RBACMiddleware — здесь явных auth-deps нет.

Error → HTTP mapping:
    UserNotFoundError        → 404
    InvalidUserStateError    → 409 detail="invalid_user_state"
    InsufficientBalanceError → 422 detail="insufficient_balance"
"""
from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from core_api.deps import database as _db_dep
from core_api.schemas.admin_users import (
    BlockUserResponse,
    LoyaltyAdjustRequest,
    LoyaltyAdjustResponse,
    UserDetailResponse,
    UserListResponse,
)
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

router = APIRouter(prefix="/api/v1/admin/users", tags=["admin-users"])


# Обёртка для patch-friendly dep resolution (см. routers/admin_orders.py)
def _get_session():
    yield from _db_dep.get_session()


StatusFilter = Literal[
    "active", "blocked", "pending_verification", "deleted", "all"
]


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


@router.post("/{user_id}/block", response_model=BlockUserResponse)
def block_admin_user(
    user_id: uuid.UUID,
    db: Session = Depends(_get_session),
) -> BlockUserResponse:
    """ACTIVE → BLOCKED + каскад отмены заказов (PDD §6.5, §7.6)."""
    try:
        return block_user(db=db, user_id=user_id)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found"
        ) from exc
    except InvalidUserStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="invalid_user_state"
        ) from exc


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
