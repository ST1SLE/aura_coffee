"""Сид singleton-строки shop_settings с дефолтами из PDD §5.2.

Идемпотентен: INSERT ... ON CONFLICT (id) DO UPDATE SET ... — повторный запуск
возвращает таблицу к каноническим дефолтам.

Запуск вручную:
    python -m database.seeds.shop_settings
"""

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
