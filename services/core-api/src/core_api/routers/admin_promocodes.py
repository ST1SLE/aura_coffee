"""Admin promocodes router (PDD §6.6, INV-010, INV-011).

Шесть эндпоинтов под /api/v1/admin/promocodes. ADMIN-only (RBACMiddleware).
Состояние вычисляется сервисом; здесь — только транспорт.
"""
from __future__ import annotations

# START_MODULE_CONTRACT
#   PURPOSE: HTTP routes for ADMIN promocode CRUD + activation/deactivation
#            under /api/v1/admin/promocodes (PDD §6.6 PromocodeLifecycle).
#   SCOPE:   Create, list, get, patch, activate, deactivate. Lifecycle state
#            (active/inactive/expired/exhausted) is computed by the service.
#   DEPENDS: M-SHARED (models.Promocode), M-DATABASE (Session),
#            core_api.services.admin_promocodes, RBACMiddleware (ADMIN-only
#            via rbac_matrix.ROUTE_MATRIX).
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §6.6, INV-002,
#            INV-010, INV-011 (immutable fields after first use).
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   router                       - APIRouter("/api/v1/admin", tags=["admin-promocodes"])
#   create_admin_promocode       - POST   /api/v1/admin/promocodes
#   list_admin_promocodes        - GET    /api/v1/admin/promocodes
#   get_admin_promocode          - GET    /api/v1/admin/promocodes/{promocode_id}
#   patch_admin_promocode        - PATCH  /api/v1/admin/promocodes/{promocode_id}
#   activate_admin_promocode     - POST   /api/v1/admin/promocodes/{promocode_id}/activate
#   deactivate_admin_promocode   - POST   /api/v1/admin/promocodes/{promocode_id}/deactivate
# END_MODULE_MAP

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from core_api.deps import database as _db_dep
from core_api.schemas.promocode import (
    PromocodeCreate,
    PromocodeListResponse,
    PromocodeResponse,
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


# START_CONTRACT: create_admin_promocode
#   PURPOSE: Create a new promocode row.
#   INPUTS:  body: PromocodeCreate (JSON), Session.
#   OUTPUTS: 201 PromocodeResponse; 409 promocode_code_conflict.
#   SIDE_EFFECTS: DB insert into promocodes.
#   LINKS:   PDD §6.6, INV-002, INV-010, services.admin_promocodes.
# END_CONTRACT: create_admin_promocode
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


# START_CONTRACT: list_admin_promocodes
#   PURPOSE: Paginated promocode list, filterable by computed state and
#            code prefix.
#   INPUTS:  state (query, optional one of {inactive,active,expired,
#            exhausted,all}), code (query prefix), page, per_page, Session.
#   OUTPUTS: 200 PromocodeListResponse; 422 invalid state filter.
#   SIDE_EFFECTS: none (read-only DB query).
#   LINKS:   PDD §6.6, INV-002, INV-010, services.admin_promocodes.
# END_CONTRACT: list_admin_promocodes
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


# START_CONTRACT: get_admin_promocode
#   PURPOSE: Get a single promocode by id.
#   INPUTS:  promocode_id: UUID, Session.
#   OUTPUTS: 200 PromocodeResponse; 404 promocode_not_found.
#   SIDE_EFFECTS: none.
#   LINKS:   PDD §6.6, INV-002, INV-010, services.admin_promocodes.
# END_CONTRACT: get_admin_promocode
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


# START_CONTRACT: patch_admin_promocode
#   PURPOSE: Partial update of a promocode. Locked fields after first use
#            (current_uses>0) are rejected with 422 (INV-011).
#   INPUTS:  promocode_id: UUID, body: PromocodeUpdate, Session.
#   OUTPUTS: 200 PromocodeResponse; 404 not found;
#            422 field_locked_after_use / validation error.
#   SIDE_EFFECTS: DB update of promocode row.
#   LINKS:   PDD §6.6, INV-002, INV-010, INV-011, services.admin_promocodes.
# END_CONTRACT: patch_admin_promocode
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


# START_CONTRACT: activate_admin_promocode
#   PURPOSE: Transition a promocode to ACTIVE if preconditions hold
#            (PDD §6.6: not expired, not exhausted, has dates).
#   INPUTS:  promocode_id: UUID, Session.
#   OUTPUTS: 200 PromocodeResponse; 404 not found;
#            422 activation precondition; 409 state conflict.
#   SIDE_EFFECTS: DB update — is_active=True (state-machine transition).
#   LINKS:   PDD §6.6, INV-002, INV-010, INV-016, services.admin_promocodes.
# END_CONTRACT: activate_admin_promocode
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


# START_CONTRACT: deactivate_admin_promocode
#   PURPOSE: Transition a promocode to INACTIVE.
#   INPUTS:  promocode_id: UUID, Session.
#   OUTPUTS: 200 PromocodeResponse; 404 not found; 409 state conflict.
#   SIDE_EFFECTS: DB update — is_active=False (state-machine transition).
#   LINKS:   PDD §6.6, INV-002, INV-010, INV-016, services.admin_promocodes.
# END_CONTRACT: deactivate_admin_promocode
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
