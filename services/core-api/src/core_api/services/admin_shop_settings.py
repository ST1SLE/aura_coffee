"""Сервис admin-управления shop_settings (PDD §5.2, §6.1, §7.1 Phase 6 item 3).

Singleton (CHECK id=1). Сервис только читает/обновляет существующую row,
создание новой не предусмотрено — миграция 0005 + seed гарантируют её наличие.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from core_api.schemas.shop_settings import ShopSettingsUpdate
from shared.models.shop_settings import ShopSettings


class ShopSettingsNotSeededError(RuntimeError):
    """Singleton-row shop_settings отсутствует (seed не запускался)."""


def get_settings(db: Session) -> ShopSettings:
    row = db.get(ShopSettings, 1)
    if row is None:
        raise ShopSettingsNotSeededError("shop_settings singleton row not found")
    return row


def update_settings(db: Session, payload: ShopSettingsUpdate) -> ShopSettings:
    row = get_settings(db)

    row.shop_lat = payload.shop_lat
    row.shop_lon = payload.shop_lon
    row.delivery_radius_km = payload.delivery_radius_km
    row.min_delivery_amount = payload.min_delivery_amount
    row.free_delivery_threshold = payload.free_delivery_threshold
    row.delivery_fee = payload.delivery_fee
    row.loyalty_percent = payload.loyalty_percent
    row.default_prep_time_minutes = payload.default_prep_time_minutes
    row.estimated_delivery_time_minutes = payload.estimated_delivery_time_minutes
    row.auto_close_minutes = payload.auto_close_minutes
    row.working_hours = {
        day: (slot.model_dump() if slot is not None else None)
        for day, slot in payload.working_hours.items()
    }

    db.flush()
    return row
