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


class PromocodeNotFoundError(Exception):
    pass


class PromocodeCodeConflictError(Exception):
    pass


class PromocodeStateConflictError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class PromocodeActivationPreconditionError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class FieldLockedAfterUseError(Exception):
    def __init__(self, field: str) -> None:
        super().__init__(f"field locked after use: {field}")
        self.field = field


# ---------------------------------------------------------------------------
# compute_state (INV-011)
# ---------------------------------------------------------------------------


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


def get_promocode(promocode_id: uuid.UUID, db_session: Session) -> Promocode:
    promo = db_session.get(Promocode, promocode_id)
    if promo is None:
        raise PromocodeNotFoundError(str(promocode_id))
    return promo


_LOCKED_AFTER_USE = {"code", "discount_type", "discount_value"}


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


def deactivate(promocode_id: uuid.UUID, db_session: Session) -> Promocode:
    promo = get_promocode(promocode_id, db_session)
    now = datetime.now(UTC)
    if compute_state(promo, now) == "expired":
        raise PromocodeStateConflictError("promocode expired")
    promo.is_active = False
    db_session.commit()
    db_session.refresh(promo)
    return promo
