"""RED: PUT /api/v1/admin/settings — full-snapshot update (PDD §5.2, §6.1).

Admin-only обновление singleton-строки. PATCH не поддерживается (избегаем
JSONB-merge на working_hours). Singleton-инвариант (CHECK id=1) должен
отвергать попытку вставить второй row.
"""
from __future__ import annotations

import time
from unittest.mock import patch

import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from core_api.main import app


@pytest.fixture
def settings_client(db_session):
    def _override_db():
        yield db_session

    fake_redis = fakeredis.FakeRedis()

    def _override_redis():
        yield fake_redis

    with (
        patch("core_api.deps.redis.get_redis", side_effect=_override_redis),
        patch("core_api.deps.database.get_session", side_effect=_override_db),
        patch("core_api.deps.database.get_db", side_effect=_override_db),
    ):
        with TestClient(app) as c:
            yield c
    fake_redis.flushall()


def _seed_default_row(db_session) -> None:
    from shared.models.shop_settings import ShopSettings

    existing = db_session.get(ShopSettings, 1)
    if existing is not None:
        db_session.delete(existing)
        db_session.flush()

    row = ShopSettings(
        id=1,
        shop_lat=55.7558,
        shop_lon=37.6173,
        delivery_radius_km=5,
        min_delivery_amount=50000,
        free_delivery_threshold=150000,
        delivery_fee=20000,
        loyalty_percent=5,
        default_prep_time_minutes=15,
        estimated_delivery_time_minutes=30,
        auto_close_minutes=60,
        working_hours={
            day: {"open": "08:00", "close": "22:00"}
            for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
        },
    )
    db_session.add(row)
    db_session.commit()


def _valid_put_payload(**overrides):
    payload = {
        "shop_lat": "59.9343",
        "shop_lon": "30.3351",
        "delivery_radius_km": "10.5",
        "min_delivery_amount": 80000,
        "free_delivery_threshold": 250000,
        "delivery_fee": 25000,
        "loyalty_percent": 7,
        "default_prep_time_minutes": 20,
        "estimated_delivery_time_minutes": 45,
        "auto_close_minutes": 90,
        "working_hours": {
            "mon": {"open": "09:00", "close": "21:00"},
            "tue": {"open": "09:00", "close": "21:00"},
            "wed": {"open": "09:00", "close": "21:00"},
            "thu": {"open": "09:00", "close": "21:00"},
            "fri": {"open": "09:00", "close": "21:00"},
            "sat": {"open": "10:00", "close": "22:00"},
            "sun": {"open": "10:00", "close": "22:00"},
        },
    }
    payload.update(overrides)
    return payload


def test_put_route_registered() -> None:
    """4.1a — PUT /api/v1/admin/settings регистрируется ровно один раз."""
    matches = [
        route
        for route in app.routes
        if "PUT" in (getattr(route, "methods", set()) or set())
        and getattr(route, "path", "") == "/api/v1/admin/settings"
    ]
    assert len(matches) == 1, (
        f"Ожидался один PUT /api/v1/admin/settings, найдено: {len(matches)}"
    )


def test_admin_put_updates_all_fields(
    settings_client, admin_headers, db_session
) -> None:
    """4.1b — admin обновляет весь snapshot, updated_at двигается вперёд."""
    _seed_default_row(db_session)

    # Снимаем текущий updated_at до PUT
    get_before = settings_client.get("/api/v1/admin/settings", headers=admin_headers)
    assert get_before.status_code == 200, get_before.text
    before_updated_at = get_before.json()["updated_at"]

    # Небольшая задержка, чтобы timestamp сдвинулся
    time.sleep(0.01)

    payload = _valid_put_payload()
    response = settings_client.put(
        "/api/v1/admin/settings", headers=admin_headers, json=payload
    )
    assert response.status_code == 200, response.text

    body = response.json()
    # Числовые поля точно совпали
    assert body["min_delivery_amount"] == 80000
    assert body["free_delivery_threshold"] == 250000
    assert body["delivery_fee"] == 25000
    assert body["loyalty_percent"] == 7
    assert body["default_prep_time_minutes"] == 20
    assert body["estimated_delivery_time_minutes"] == 45
    assert body["auto_close_minutes"] == 90
    # working_hours уехали
    assert body["working_hours"]["mon"] == {"open": "09:00", "close": "21:00"}
    # updated_at продвинулся
    assert body["updated_at"] != before_updated_at


def test_singleton_check_rejects_second_row(db_session) -> None:
    """4.2 — попытка вставить вторую строку (id=2) ломается CHECK id=1."""
    from shared.models.shop_settings import ShopSettings

    # auto_close_minutes — новое поле; отсутствие атрибута в модели
    # гарантирует AttributeError до GREEN-цикла (RED).
    row = ShopSettings(
        id=2,
        shop_lat=55.7558,
        shop_lon=37.6173,
        delivery_radius_km=5,
        min_delivery_amount=50000,
        free_delivery_threshold=150000,
        delivery_fee=20000,
        loyalty_percent=5,
        default_prep_time_minutes=15,
        estimated_delivery_time_minutes=30,
        auto_close_minutes=60,
        working_hours={
            day: {"open": "08:00", "close": "22:00"}
            for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
        },
    )
    db_session.add(row)

    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()
