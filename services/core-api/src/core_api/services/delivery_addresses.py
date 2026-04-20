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


class DeliveryAddressNotFound(Exception):
    """Адрес не найден ИЛИ принадлежит другому пользователю (маппится в HTTP 404)."""


def _get_shop_settings(db: Session) -> ShopSettings:
    settings = db.get(ShopSettings, 1)
    if settings is None:
        raise RuntimeError("ShopSettings row id=1 is missing")
    return settings


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


def delete_for_user(
    db: Session, user_id: uuid.UUID, address_id: uuid.UUID
) -> None:
    addr = _get_owned(db, user_id, address_id)
    db.delete(addr)
    db.flush()
