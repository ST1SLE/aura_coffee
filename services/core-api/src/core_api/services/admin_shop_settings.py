# START_MODULE_CONTRACT
#   PURPOSE: Admin-only read/update for the singleton ShopSettings row that
#            governs delivery geometry, working hours, loyalty %, prep timers,
#            and ordering pause mode.
#   SCOPE:   get_settings (read), update_settings (replace mutable fields).
#   DEPENDS: M-SHARED (ShopSettings model), M-DATABASE, schemas.shop_settings
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §5.2, §7.1 Phase 6/3, INV-010
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   ShopSettingsNotSeededError - singleton row missing (seed not executed)
#   get_settings               - load id=1 or raise
#   update_settings            - overwrite mutable fields from payload
# END_MODULE_MAP
"""Сервис admin-управления shop_settings (PDD §5.2, §6.1, §7.1 Phase 6 item 3).

Singleton (CHECK id=1). Сервис только читает/обновляет существующую row,
создание новой не предусмотрено — миграция 0005 + seed гарантируют её наличие.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from core_api.schemas.shop_settings import ShopSettingsUpdate
from shared.models.shop_settings import ShopSettings


# START_CONTRACT: ShopSettingsNotSeededError
#   PURPOSE: Signal that the singleton shop_settings row id=1 is absent —
#            indicates broken bootstrap (migration/seed not run).
#   INPUTS:  message: str
#   OUTPUTS: RuntimeError instance.
#   SIDE_EFFECTS: none
# END_CONTRACT: ShopSettingsNotSeededError
class ShopSettingsNotSeededError(RuntimeError):
    """Singleton-row shop_settings отсутствует (seed не запускался)."""


# START_CONTRACT: get_settings
#   PURPOSE: Load the singleton ShopSettings row (id=1).
#   INPUTS:  db: Session
#   OUTPUTS: ShopSettings ORM row.
#   SIDE_EFFECTS: DB SELECT only; raises ShopSettingsNotSeededError if missing.
# END_CONTRACT: get_settings
def get_settings(db: Session) -> ShopSettings:
    row = db.get(ShopSettings, 1)
    if row is None:
        raise ShopSettingsNotSeededError("shop_settings singleton row not found")
    return row


# START_CONTRACT: update_settings
#   PURPOSE: Overwrite mutable fields of ShopSettings (geometry, hours, loyalty %,
#            prep/autoclose timers, ordering pause) from validated admin payload.
#   INPUTS:  db: Session
#            payload: ShopSettingsUpdate
#   OUTPUTS: ShopSettings (updated, in-session)
#   SIDE_EFFECTS: DB UPDATE id=1 + flush. Caller owns commit boundary.
#   LINKS:   PDD §5.2, INV-010 (admin-only, enforced in router)
# END_CONTRACT: update_settings
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
    row.ordering_paused = payload.ordering_paused
    row.working_hours = {
        day: (slot.model_dump() if slot is not None else None)
        for day, slot in payload.working_hours.items()
    }

    db.flush()
    return row
