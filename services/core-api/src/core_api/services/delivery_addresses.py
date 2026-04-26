# START_MODULE_CONTRACT
#   PURPOSE: Customer CRUD over saved DeliveryAddress entries with strict
#            ownership enforcement (foreign id → 404, never 403, INV-013) and
#            singleton-default invariant (one default per user, partial unique
#            index on DB level).
#   SCOPE:   list/create/update/delete; default flag promotion with atomic
#            demotion of the previous default.
#   DEPENDS: M-SHARED (DeliveryAddress, ShopSettings), M-DATABASE,
#            schemas.delivery_address, services.validators.delivery
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §3, §5.2, INV-008, INV-013
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   DeliveryAddressNotFound - missing or owned-by-other (INV-013)
#   list_for_user           - default-first, then created_at ASC
#   create_for_user         - validates radius + handles default promotion
#   update_for_user         - PATCH owned address; default promotion safe
#   delete_for_user         - delete owned address
# END_MODULE_MAP
"""Сервисный слой для сохранённых адресов доставки (PDD §3, §5.2).

Бизнес-логика CRUD для `delivery_addresses`:
- владелец — только текущий пользователь (чужой id → 404, НЕ 403; INV-013);
- Haversine-валидация радиуса на create через validators.delivery (INV-008);
- флаг is_default атомарно демотит прошлый default (одно id-владельца — один дефолт;
  дополнительно защищён partial unique index на уровне БД).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from core_api.schemas.delivery_address import (
    DeliveryAddressCreate,
    DeliveryAddressUpdate,
)
from core_api.services.validators.delivery import validate_delivery_address
from shared.models import DeliveryAddress, ShopSettings


# START_CONTRACT: DeliveryAddressNotFound
#   PURPOSE: Raised when address id is missing or owned by another user.
#            Mapped to HTTP 404 (never 403) — INV-013.
#   INPUTS:  message: str
#   OUTPUTS: Exception instance.
#   SIDE_EFFECTS: none
#   LINKS:   INV-013
# END_CONTRACT: DeliveryAddressNotFound
class DeliveryAddressNotFound(Exception):
    """Адрес не найден ИЛИ принадлежит другому пользователю (маппится в HTTP 404)."""


def _get_shop_settings(db: Session) -> ShopSettings:
    settings = db.get(ShopSettings, 1)
    if settings is None:
        raise RuntimeError("ShopSettings row id=1 is missing")
    return settings


# START_CONTRACT: list_for_user
#   PURPOSE: List all saved addresses for a user, default-first then oldest.
#   INPUTS:  db: Session, user_id: UUID
#   OUTPUTS: list[DeliveryAddress]
#   SIDE_EFFECTS: DB SELECT only.
# END_CONTRACT: list_for_user
def list_for_user(db: Session, user_id: uuid.UUID) -> list[DeliveryAddress]:
    stmt = (
        select(DeliveryAddress)
        .where(DeliveryAddress.user_id == user_id)
        .order_by(
            DeliveryAddress.is_default.desc(),
            DeliveryAddress.created_at.asc(),
        )
    )
    return list(db.execute(stmt).scalars().all())


def _demote_current_default(
    db: Session, user_id: uuid.UUID, exclude_id: uuid.UUID | None = None
) -> None:
    stmt = select(DeliveryAddress).where(
        DeliveryAddress.user_id == user_id,
        DeliveryAddress.is_default.is_(True),
    )
    if exclude_id is not None:
        stmt = stmt.where(DeliveryAddress.id != exclude_id)
    for row in db.execute(stmt).scalars().all():
        row.is_default = False


# START_CONTRACT: create_for_user
#   PURPOSE: Insert a new address for the caller; validates Haversine radius
#            and atomically demotes any prior default before inserting one.
#   INPUTS:  db: Session, user_id: UUID, payload: DeliveryAddressCreate
#   OUTPUTS: DeliveryAddress (refreshed)
#   SIDE_EFFECTS: DB INSERT + optional UPDATE on prior default. Caller owns commit.
#                 Raises validation error when address is outside radius.
#   LINKS:   PDD §7.3, INV-008, INV-013
# END_CONTRACT: create_for_user
def create_for_user(
    db: Session,
    user_id: uuid.UUID,
    payload: DeliveryAddressCreate,
) -> DeliveryAddress:
    shop_settings = _get_shop_settings(db)
    validate_delivery_address(payload.lat, payload.lon, shop_settings)

    if payload.is_default:
        _demote_current_default(db, user_id)
        db.flush()  # Демотим прошлый default ПЕРЕД промоутом, чтобы partial unique не упал.

    addr = DeliveryAddress(
        user_id=user_id,
        label=payload.label,
        address_text=payload.address_text,
        lat=payload.lat,
        lon=payload.lon,
        apartment=payload.apartment,
        entrance=payload.entrance,
        floor=payload.floor,
        comment=payload.comment,
        is_default=payload.is_default,
    )
    db.add(addr)
    db.flush()
    db.refresh(addr)
    return addr


def _get_owned(
    db: Session, user_id: uuid.UUID, address_id: uuid.UUID
) -> DeliveryAddress:
    stmt = select(DeliveryAddress).where(
        DeliveryAddress.id == address_id,
        DeliveryAddress.user_id == user_id,
    )
    row = db.execute(stmt).scalar_one_or_none()
    if row is None:
        raise DeliveryAddressNotFound(str(address_id))
    return row


# START_CONTRACT: update_for_user
#   PURPOSE: PATCH an owned address; promoting to default atomically demotes
#            the previous default for this user.
#   INPUTS:  db: Session, user_id: UUID, address_id: UUID,
#            payload: DeliveryAddressUpdate
#   OUTPUTS: DeliveryAddress (refreshed)
#   SIDE_EFFECTS: DB UPDATE(s); raises DeliveryAddressNotFound on missing/foreign.
#   LINKS:   INV-013
# END_CONTRACT: update_for_user
def update_for_user(
    db: Session,
    user_id: uuid.UUID,
    address_id: uuid.UUID,
    payload: DeliveryAddressUpdate,
) -> DeliveryAddress:
    addr = _get_owned(db, user_id, address_id)

    data = payload.model_dump(exclude_unset=True)

    if data.get("is_default") is True:
        _demote_current_default(db, user_id, exclude_id=addr.id)
        db.flush()  # Демотим прошлый default ПЕРЕД промоутом, чтобы partial unique не упал.

    for key, value in data.items():
        setattr(addr, key, value)

    db.flush()
    db.refresh(addr)
    return addr


# START_CONTRACT: delete_for_user
#   PURPOSE: Delete an owned saved address.
#   INPUTS:  db: Session, user_id: UUID, address_id: UUID
#   OUTPUTS: None
#   SIDE_EFFECTS: DB DELETE; raises DeliveryAddressNotFound on missing/foreign.
#   LINKS:   INV-013
# END_CONTRACT: delete_for_user
def delete_for_user(
    db: Session, user_id: uuid.UUID, address_id: uuid.UUID
) -> None:
    addr = _get_owned(db, user_id, address_id)
    db.delete(addr)
    db.flush()
