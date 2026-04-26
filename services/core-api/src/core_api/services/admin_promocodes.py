# START_MODULE_CONTRACT
#   PURPOSE: Admin-side CRUD + activate/deactivate for Promocode aggregate, with
#            computed state (PDD §6.6) as the single source of truth.
#   SCOPE:   create/list/get/update/activate/deactivate; lifecycle transitions
#            implicit via compute_state (inactive↔active, expired, exhausted).
#   DEPENDS: M-SHARED (Promocode model), M-DATABASE, schemas.promocode
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §6.6, INV-004, INV-010, INV-011
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   PromocodeNotFoundError              - aggregate id missing
#   PromocodeCodeConflictError          - unique 'code' collision on create
#   PromocodeStateConflictError         - activate/deactivate forbidden by state
#   PromocodeActivationPreconditionError- precondition (e.g. valid_until) not met
#   FieldLockedAfterUseError            - locked field touched after first use
#   compute_state                       - PDD §6.6 derivation rule
#   create_promocode                    - INSERT with is_active=False
#   list_promocodes                     - paginated, optional state/code filters
#   get_promocode                       - load by id or raise
#   update_promocode                    - PATCH with locked-after-use check
#   activate                            - inactive→active (state-machine)
#   deactivate                          - active→inactive (state-machine)
# END_MODULE_MAP
"""Admin promocodes service (PDD §6.6, INV-004, INV-010, INV-011).

Computed `state` — единственный источник истины для состояния промокода.
Никаких DB-колонок status. Одна транзакция на write-op (INV-004).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core_api.schemas.promocode import (
    PromocodeCreate,
    PromocodeListResponse,
    PromocodeResponse,
    PromocodeUpdate,
)
from shared.models.promocode import Promocode

StateStr = Literal["inactive", "active", "expired", "exhausted"]


# ---------------------------------------------------------------------------
# Domain exceptions
# ---------------------------------------------------------------------------


# START_CONTRACT: PromocodeNotFoundError
#   PURPOSE: Raised when promocode aggregate is missing — router maps to HTTP 404.
#   INPUTS:  message: str — typically the missing id.
#   OUTPUTS: Exception instance.
#   SIDE_EFFECTS: none
# END_CONTRACT: PromocodeNotFoundError
class PromocodeNotFoundError(Exception):
    pass


# START_CONTRACT: PromocodeCodeConflictError
#   PURPOSE: Raised on UNIQUE(code) IntegrityError — router maps to HTTP 409.
#   INPUTS:  message: str — colliding code.
#   OUTPUTS: Exception instance.
#   SIDE_EFFECTS: none
# END_CONTRACT: PromocodeCodeConflictError
class PromocodeCodeConflictError(Exception):
    pass


# START_CONTRACT: PromocodeStateConflictError
#   PURPOSE: Raised when activate/deactivate forbidden by computed state (PDD §6.6).
#   INPUTS:  reason: str — short machine code (e.g. "promocode expired").
#   OUTPUTS: Exception instance with .reason.
#   SIDE_EFFECTS: none
#   LINKS:   PDD §6.6, INV-016
# END_CONTRACT: PromocodeStateConflictError
class PromocodeStateConflictError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


# START_CONTRACT: PromocodeActivationPreconditionError
#   PURPOSE: Raised when activate() called on promocode missing required fields
#            (e.g. valid_until) — PDD §6.6 inactive→active precondition.
#   INPUTS:  reason: str
#   OUTPUTS: Exception instance with .reason.
#   SIDE_EFFECTS: none
# END_CONTRACT: PromocodeActivationPreconditionError
class PromocodeActivationPreconditionError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


# START_CONTRACT: FieldLockedAfterUseError
#   PURPOSE: Raised when update_promocode tries to mutate immutable-after-use
#            fields (code, discount_type, discount_value) — INV-011 / INV-014 spirit.
#   INPUTS:  field: str — locked field name.
#   OUTPUTS: Exception with .field.
#   SIDE_EFFECTS: none
# END_CONTRACT: FieldLockedAfterUseError
class FieldLockedAfterUseError(Exception):
    def __init__(self, field: str) -> None:
        super().__init__(f"field locked after use: {field}")
        self.field = field


# ---------------------------------------------------------------------------
# compute_state (INV-011)
# ---------------------------------------------------------------------------


# START_CONTRACT: compute_state
#   PURPOSE: Derive promocode state per PDD §6.6 priority (expired > exhausted >
#            active > inactive). The single source of truth for status — no DB
#            'status' column.
#   INPUTS:  promo: Promocode — ORM row
#            now:   datetime  — caller-fixed clock
#   OUTPUTS: StateStr — one of {"inactive","active","expired","exhausted"}.
#   SIDE_EFFECTS: none (pure derivation)
#   LINKS:   PDD §6.6, INV-011, INV-016
# END_CONTRACT: compute_state
def compute_state(promo: Promocode, now: datetime) -> StateStr:
    """expired > exhausted > active > inactive (PDD §6.6)."""
    if promo.valid_until is not None and now > promo.valid_until:
        return "expired"
    if promo.max_uses is not None and promo.current_uses >= promo.max_uses:
        return "exhausted"
    if promo.is_active and (promo.valid_from is None or now >= promo.valid_from):
        return "active"
    return "inactive"


def _to_response(promo: Promocode, now: datetime) -> PromocodeResponse:
    return PromocodeResponse(
        id=promo.id,
        code=promo.code,
        discount_type=promo.discount_type,
        discount_value=promo.discount_value,
        min_order_amount=promo.min_order_amount,
        valid_from=promo.valid_from,
        valid_until=promo.valid_until,
        max_uses=promo.max_uses,
        max_uses_per_user=promo.max_uses_per_user,
        current_uses=promo.current_uses,
        is_active=promo.is_active,
        created_at=promo.created_at,
        state=compute_state(promo, now),
    )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


# START_CONTRACT: create_promocode
#   PURPOSE: Insert a new Promocode row in 'inactive' state (is_active=False).
#   INPUTS:  data: PromocodeCreate — validated payload
#            db_session: Session  — open SQLAlchemy session
#   OUTPUTS: Promocode — refreshed ORM row.
#   SIDE_EFFECTS: DB INSERT + commit (single transaction, INV-004); on UNIQUE
#                 collision → rollback + PromocodeCodeConflictError.
#   LINKS:   PDD §6.6 initial state, INV-004
# END_CONTRACT: create_promocode
def create_promocode(data: PromocodeCreate, db_session: Session) -> Promocode:
    promo = Promocode(
        code=data.code,
        discount_type=data.discount_type,
        discount_value=data.discount_value,
        min_order_amount=data.min_order_amount,
        valid_from=data.valid_from,
        valid_until=data.valid_until,
        max_uses=data.max_uses,
        max_uses_per_user=data.max_uses_per_user,
        current_uses=0,
        is_active=False,
    )
    db_session.add(promo)
    try:
        db_session.commit()
    except IntegrityError as exc:
        db_session.rollback()
        raise PromocodeCodeConflictError(data.code) from exc
    db_session.refresh(promo)
    return promo


# START_CONTRACT: list_promocodes
#   PURPOSE: Paginated promocode list, filtered by computed state and/or
#            case-insensitive code prefix.
#   INPUTS:  state_filter: str|None — "all"/"inactive"/"active"/"expired"/"exhausted"
#            code_prefix:  str|None — ILIKE prefix
#            page, per_page: int    — pagination
#            db_session:   Session
#            now:          datetime — clock for compute_state
#   OUTPUTS: PromocodeListResponse — items + total_count + page meta.
#   SIDE_EFFECTS: DB SELECT only.
#   LINKS:   PDD §6.6, INV-010 (admin-only — enforced in router)
# END_CONTRACT: list_promocodes
def list_promocodes(
    *,
    state_filter: str | None,
    code_prefix: str | None,
    page: int,
    per_page: int,
    db_session: Session,
    now: datetime,
) -> PromocodeListResponse:
    stmt = select(Promocode)
    if code_prefix:
        # ILIKE prefix match (case-insensitive)
        stmt = stmt.where(Promocode.code.ilike(f"{code_prefix}%"))
    stmt = stmt.order_by(Promocode.created_at.desc())
    all_rows = db_session.execute(stmt).scalars().all()

    if state_filter and state_filter != "all":
        filtered = [p for p in all_rows if compute_state(p, now) == state_filter]
    else:
        filtered = list(all_rows)

    total = len(filtered)
    start = (page - 1) * per_page
    end = start + per_page
    page_rows = filtered[start:end]

    return PromocodeListResponse(
        items=[_to_response(p, now) for p in page_rows],
        total_count=total,
        page=page,
        per_page=per_page,
    )


# START_CONTRACT: get_promocode
#   PURPOSE: Load Promocode by id or raise PromocodeNotFoundError.
#   INPUTS:  promocode_id: UUID
#            db_session:  Session
#   OUTPUTS: Promocode
#   SIDE_EFFECTS: DB SELECT only.
# END_CONTRACT: get_promocode
def get_promocode(promocode_id: uuid.UUID, db_session: Session) -> Promocode:
    promo = db_session.get(Promocode, promocode_id)
    if promo is None:
        raise PromocodeNotFoundError(str(promocode_id))
    return promo


_LOCKED_AFTER_USE = {"code", "discount_type", "discount_value"}


# START_CONTRACT: update_promocode
#   PURPOSE: PATCH a Promocode; enforces locked-after-use fields once
#            current_uses>0 and post-merge invariants on date/quota windows.
#   INPUTS:  promocode_id: UUID
#            patch: PromocodeUpdate — partial payload
#            db_session: Session
#   OUTPUTS: Promocode (refreshed)
#   SIDE_EFFECTS: DB UPDATE + commit (INV-004); on locked field → rollback +
#                 FieldLockedAfterUseError; on invariant violation → ValueError.
#   LINKS:   PDD §6.6, INV-011, INV-014 (immutability of priced artifacts)
# END_CONTRACT: update_promocode
def update_promocode(
    promocode_id: uuid.UUID,
    patch: PromocodeUpdate,
    db_session: Session,
) -> Promocode:
    promo = get_promocode(promocode_id, db_session)
    patch_data = patch.model_dump(exclude_unset=True)

    if promo.current_uses > 0:
        for field in _LOCKED_AFTER_USE:
            if field in patch_data:
                raise FieldLockedAfterUseError(field)

    for field, value in patch_data.items():
        setattr(promo, field, value)

    # Post-merge invariants
    if (
        promo.valid_from is not None
        and promo.valid_until is not None
        and promo.valid_from >= promo.valid_until
    ):
        db_session.rollback()
        raise ValueError("valid_from must be strictly before valid_until")
    if (
        promo.max_uses is not None
        and promo.max_uses_per_user is not None
        and promo.max_uses_per_user > promo.max_uses
    ):
        db_session.rollback()
        raise ValueError("max_uses_per_user must be <= max_uses")

    db_session.commit()
    db_session.refresh(promo)
    return promo


# START_CONTRACT: activate
#   PURPOSE: State transition inactive → active for a Promocode (PDD §6.6).
#   INPUTS:  promocode_id: UUID
#            db_session: Session
#   OUTPUTS: Promocode (refreshed)
#   SIDE_EFFECTS: DB UPDATE is_active=True + commit. Source: inactive.
#                 Target: active. Rejects when computed state is expired/exhausted.
#   LINKS:   PDD §6.6, INV-016, INV-004
# END_CONTRACT: activate
def activate(promocode_id: uuid.UUID, db_session: Session) -> Promocode:
    promo = get_promocode(promocode_id, db_session)
    if promo.valid_until is None:
        raise PromocodeActivationPreconditionError("valid_until required")
    now = datetime.now(UTC)
    state = compute_state(promo, now)
    if state == "expired":
        raise PromocodeStateConflictError("promocode expired")
    if state == "exhausted":
        raise PromocodeStateConflictError("promocode exhausted")
    promo.is_active = True
    db_session.commit()
    db_session.refresh(promo)
    return promo


# START_CONTRACT: deactivate
#   PURPOSE: State transition active → inactive for a Promocode (PDD §6.6).
#   INPUTS:  promocode_id: UUID
#            db_session: Session
#   OUTPUTS: Promocode (refreshed)
#   SIDE_EFFECTS: DB UPDATE is_active=False + commit. Source: active.
#                 Target: inactive. Rejects when computed state is expired.
#   LINKS:   PDD §6.6, INV-016, INV-004
# END_CONTRACT: deactivate
def deactivate(promocode_id: uuid.UUID, db_session: Session) -> Promocode:
    promo = get_promocode(promocode_id, db_session)
    now = datetime.now(UTC)
    if compute_state(promo, now) == "expired":
        raise PromocodeStateConflictError("promocode expired")
    promo.is_active = False
    db_session.commit()
    db_session.refresh(promo)
    return promo
