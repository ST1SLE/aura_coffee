"""Сид singleton-строки shop_settings с дефолтами из PDD §5.2.

Идемпотентен: INSERT ... ON CONFLICT (id) DO UPDATE SET ... — повторный запуск
возвращает таблицу к каноническим дефолтам.

Запуск вручную:
    python -m database.seeds.shop_settings
"""

# START_MODULE_CONTRACT
#   PURPOSE: One-shot seed that upserts the singleton shop_settings row
#            (id=1) with canonical defaults from PDD §5.2 — coordinates,
#            delivery radius, fees, loyalty %, prep / delivery times,
#            working hours.
#   SCOPE:   Invoked at deploy time (and re-invoked by phase4_manual_test
#            seed) to guarantee the singleton row exists before any
#            checkout / Haversine validation runs.
#   DEPENDS: M-SHARED (shop_settings schema with CHECK (id = 1)),
#            alembic-applied migrations, sqlalchemy, stdlib (json, os, sys).
#   LINKS:   docs/development-plan.xml M-DATABASE, PDD §3 (Shop terminology),
#            PDD §5.2 (Settings/shop_settings singleton),
#            database/AGENTS.md "Singleton shop_settings".
#   ROLE:    SCRIPT
#   MAP_MODE: LOCALS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   DEFAULT_WORKING_HOURS - mon..sun -> {open: "08:00", close: "22:00"} dict
#   DEFAULTS              - canonical PDD §5.2 defaults bound to SQL params
#   run                   - upsert singleton row id=1 (ON CONFLICT DO UPDATE)
# END_MODULE_MAP

from __future__ import annotations

import json
import os
import sys

from sqlalchemy import create_engine, text

DEFAULT_WORKING_HOURS = {
    day: {"open": "08:00", "close": "22:00"}
    for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
}

DEFAULTS = {
    "id": 1,
    "shop_lat": 55.7558,
    "shop_lon": 37.6173,
    "delivery_radius_km": 5,
    "min_delivery_amount": 50000,
    "free_delivery_threshold": 150000,
    "delivery_fee": 20000,
    "loyalty_percent": 5,
    "default_prep_time_minutes": 15,
    "estimated_delivery_time_minutes": 30,
    "auto_close_minutes": 60,
    "working_hours": json.dumps(DEFAULT_WORKING_HOURS),
}


# START_CONTRACT: run
#   PURPOSE: Upsert the singleton shop_settings row (id=1) with the PDD §5.2
#            defaults. Repeated invocations RESET the row to canonical values
#            — this is intentional for fresh worktrees and CI.
#   INPUTS:  database_url: str | None — explicit connection URL; falls back to
#            os.environ["DATABASE_URL"] when None.
#   OUTPUTS: None
#   SIDE_EFFECTS: INSERT ... ON CONFLICT (id) DO UPDATE on shop_settings.
#                 Idempotent for shape, but DESTRUCTIVE for any operator-tuned
#                 values: rerunning overwrites delivery_radius_km, fees, etc.
#                 Raises RuntimeError if DATABASE_URL is missing. Engine is
#                 disposed in a finally block.
#   LINKS:   PDD §5.2 (shop_settings, CHECK (id = 1)),
#            INV-014 (does not touch order_items at seed time).
# END_CONTRACT: run
def run(database_url: str | None = None) -> None:
    url = database_url or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")

    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO shop_settings (
                        id, shop_lat, shop_lon, delivery_radius_km,
                        min_delivery_amount, free_delivery_threshold, delivery_fee,
                        loyalty_percent, default_prep_time_minutes,
                        estimated_delivery_time_minutes, auto_close_minutes,
                        working_hours, updated_at
                    ) VALUES (
                        :id, :shop_lat, :shop_lon, :delivery_radius_km,
                        :min_delivery_amount, :free_delivery_threshold, :delivery_fee,
                        :loyalty_percent, :default_prep_time_minutes,
                        :estimated_delivery_time_minutes, :auto_close_minutes,
                        CAST(:working_hours AS jsonb), now()
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        shop_lat = EXCLUDED.shop_lat,
                        shop_lon = EXCLUDED.shop_lon,
                        delivery_radius_km = EXCLUDED.delivery_radius_km,
                        min_delivery_amount = EXCLUDED.min_delivery_amount,
                        free_delivery_threshold = EXCLUDED.free_delivery_threshold,
                        delivery_fee = EXCLUDED.delivery_fee,
                        loyalty_percent = EXCLUDED.loyalty_percent,
                        default_prep_time_minutes = EXCLUDED.default_prep_time_minutes,
                        estimated_delivery_time_minutes = EXCLUDED.estimated_delivery_time_minutes,
                        auto_close_minutes = EXCLUDED.auto_close_minutes,
                        working_hours = EXCLUDED.working_hours,
                        updated_at = now()
                    """
                ),
                DEFAULTS,
            )
    finally:
        engine.dispose()


if __name__ == "__main__":
    run()
    sys.stdout.write("shop_settings seed applied\n")
