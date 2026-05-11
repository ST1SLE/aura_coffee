"""RED: валидация ShopSettingsUpdate (PDD §5.2, §6.1).

Табличные 422-кейсы для геопозиции, лимитов, процентов и working_hours.
И один happy-path: working_hours.tue = null (выходной) → 200.
"""
from __future__ import annotations

from unittest.mock import patch

import fakeredis
import pytest
from fastapi.testclient import TestClient

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


def _valid_payload(**overrides):
    payload = {
        "shop_lat": "55.7558",
        "shop_lon": "37.6173",
        "delivery_radius_km": "5.0",
        "min_delivery_amount": 50000,
        "free_delivery_threshold": 150000,
        "delivery_fee": 20000,
        "loyalty_percent": 5,
        "default_prep_time_minutes": 15,
        "estimated_delivery_time_minutes": 30,
        "auto_close_minutes": 60,
        "ordering_paused": False,
        "working_hours": {
            "mon": {"open": "08:00", "close": "22:00"},
            "tue": {"open": "08:00", "close": "22:00"},
            "wed": {"open": "08:00", "close": "22:00"},
            "thu": {"open": "08:00", "close": "22:00"},
            "fri": {"open": "08:00", "close": "22:00"},
            "sat": {"open": "08:00", "close": "22:00"},
            "sun": {"open": "08:00", "close": "22:00"},
        },
    }
    payload.update(overrides)
    return payload


def _wh_missing_sunday():
    return {
        "mon": {"open": "08:00", "close": "22:00"},
        "tue": {"open": "08:00", "close": "22:00"},
        "wed": {"open": "08:00", "close": "22:00"},
        "thu": {"open": "08:00", "close": "22:00"},
        "fri": {"open": "08:00", "close": "22:00"},
        "sat": {"open": "08:00", "close": "22:00"},
    }


def _wh_bad_time():
    base = {
        day: {"open": "08:00", "close": "22:00"}
        for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
    }
    base["mon"] = {"open": "25:00", "close": "22:00"}
    return base


def _wh_open_equals_close():
    base = {
        day: {"open": "08:00", "close": "22:00"}
        for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
    }
    base["mon"] = {"open": "10:00", "close": "10:00"}
    return base


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"shop_lat": "91"}, id="lat-91"),
        pytest.param({"shop_lat": "-91"}, id="lat-neg91"),
        pytest.param({"shop_lon": "181"}, id="lon-181"),
        pytest.param({"shop_lon": "-181"}, id="lon-neg181"),
        pytest.param({"loyalty_percent": 101}, id="loyalty-101"),
        pytest.param({"loyalty_percent": -1}, id="loyalty-neg"),
        pytest.param(
            {"free_delivery_threshold": 10000, "min_delivery_amount": 50000},
            id="free-threshold-below-min",
        ),
        pytest.param({"auto_close_minutes": 0}, id="auto-close-0"),
        pytest.param({"auto_close_minutes": 1441}, id="auto-close-1441"),
        pytest.param({"working_hours": _wh_missing_sunday()}, id="wh-missing-sun"),
        pytest.param({"working_hours": _wh_bad_time()}, id="wh-bad-time"),
        pytest.param({"working_hours": _wh_open_equals_close()}, id="wh-open-eq-close"),
    ],
)
def test_put_invalid_payload_returns_422(
    settings_client, admin_headers, db_session, overrides
) -> None:
    """5.1 — перечисленные варианты payload должны давать 422."""
    _seed_default_row(db_session)
    payload = _valid_payload(**overrides)

    response = settings_client.put(
        "/api/v1/admin/settings", headers=admin_headers, json=payload
    )
    assert response.status_code == 422, (
        f"Ожидался 422 для overrides={overrides}, получено {response.status_code}: {response.text}"
    )


def test_working_hours_day_off_accepted(
    settings_client, admin_headers, db_session
) -> None:
    """5.2 — working_hours.tue=null (выходной) — валидный payload → 200."""
    _seed_default_row(db_session)

    wh = {
        day: {"open": "08:00", "close": "22:00"}
        for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
    }
    wh["tue"] = None
    payload = _valid_payload(working_hours=wh)

    response = settings_client.put(
        "/api/v1/admin/settings", headers=admin_headers, json=payload
    )
    assert response.status_code == 200, response.text
    assert response.json()["working_hours"]["tue"] is None
