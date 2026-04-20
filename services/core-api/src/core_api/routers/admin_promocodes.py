"""Admin promocodes router (PDD §6.6, INV-010, INV-011).

Шесть эндпоинтов под /api/v1/admin/promocodes. ADMIN-only (RBACMiddleware).
Состояние вычисляется сервисом; здесь — только транспорт.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from core_api.deps import database as _db_dep
from core_api.schemas.promocode import (
    PromocodeCreate,
    PromocodeListResponse,
    PromocodeResponse,
    PromocodeState,
    PromocodeUpdate,
)
from core_api.services.admin_promocodes import (
    FieldLockedAfterUseError,
    PromocodeActivationPreconditionError,
    PromocodeCodeConflictError,
    PromocodeNotFoundError,
    PromocodeStateConflictError,
    activate as _activate,
    compute_state,
    create_promocode,
    deactivate as _deactivate,
    get_promocode,
    list_promocodes,
    update_promocode,
)
from shared.models.promocode import Promocode

router = APIRouter(prefix="/api/v1/admin", tags=["admin-promocodes"])


def _get_session():
    yield from _db_dep.get_session()


_STATE_VALUES = {"inactive", "active", "expired", "exhausted", "all"}


def _to_response(promo: Promocode, now: datetime) -> PromocodeResponse:
    return PromocodeResponse.model_validate(
        {
            "id": promo.id,
            "code": promo.code,
            "discount_type": promo.discount_type,
            "discount_value": promo.discount_value,
            "min_order_amount": promo.min_order_amount,
            "valid_from": promo.valid_from,
            "valid_until": promo.valid_until,
            "max_uses": promo.max_uses,
            "max_uses_per_user": promo.max_uses_per_user,
            "current_uses": promo.current_uses,
            "is_active": promo.is_active,
            "created_at": promo.created_at,
            "state": compute_state(promo, now),
        }
    )


@router.post(
    "/promocodes",
    response_model=PromocodeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_admin_promocode(
    body: PromocodeCreate,
    db: Session = Depends(_get_session),
) -> PromocodeResponse:
    try:
        promo = create_promocode(body, db)
    except PromocodeCodeConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="promocode_code_conflict",
        ) from exc
    return _to_response(promo, datetime.now(UTC))


@router.get("/promocodes", response_model=PromocodeListResponse)
def list_admin_promocodes(
    state: str | None = Query(None),
    code: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(_get_session),
) -> PromocodeListResponse:
    if state is not None and state not in _STATE_VALUES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"invalid state filter: {state!r}",
        )
    now = datetime.now(UTC)
    return list_promocodes(
        state_filter=state,
        code_prefix=code,
        page=page,
        per_page=per_page,
        db_session=db,
        now=now,
    )


@router.get("/promocodes/{promocode_id}", response_model=PromocodeResponse)
def get_admin_promocode(
    promocode_id: uuid.UUID,
    db: Session = Depends(_get_session),
) -> PromocodeResponse:
    try:
        promo = get_promocode(promocode_id, db)
    except PromocodeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="promocode_not_found",
        ) from exc
    return _to_response(promo, datetime.now(UTC))


@router.patch("/promocodes/{promocode_id}", response_model=PromocodeResponse)
def patch_admin_promocode(
    promocode_id: uuid.UUID,
    body: PromocodeUpdate,
    db: Session = Depends(_get_session),
) -> PromocodeResponse:
    try:
        promo = update_promocode(promocode_id, body, db)
    except PromocodeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="promocode_not_found",
        ) from exc
    except FieldLockedAfterUseError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[{"type": "field_locked_after_use", "field": exc.field}],
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return _to_response(promo, datetime.now(UTC))


@router.post(
    "/promocodes/{promocode_id}/activate",
    response_model=PromocodeResponse,
)
def activate_admin_promocode(
    promocode_id: uuid.UUID,
    db: Session = Depends(_get_session),
) -> PromocodeResponse:
    try:
        promo = _activate(promocode_id, db)
    except PromocodeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="promocode_not_found",
        ) from exc
    except PromocodeActivationPreconditionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.reason,
        ) from exc
    except PromocodeStateConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.reason,
        ) from exc
    return _to_response(promo, datetime.now(UTC))


@router.post(
    "/promocodes/{promocode_id}/deactivate",
    response_model=PromocodeResponse,
)
def deactivate_admin_promocode(
    promocode_id: uuid.UUID,
    db: Session = Depends(_get_session),
) -> PromocodeResponse:
    try:
        promo = _deactivate(promocode_id, db)
    except PromocodeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="promocode_not_found",
        ) from exc
    except PromocodeStateConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.reason,
        ) from exc
    return _to_response(promo, datetime.now(UTC))
