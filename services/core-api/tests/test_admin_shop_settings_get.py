"""RED: GET /api/v1/admin/settings (PDD §5.2, §7.1 Phase 6 item 3, INV-010).

Admin-only чтение singleton-строки shop_settings, включая новое поле
auto_close_minutes из миграции 0008. Target-импорты — внутри тел тестов;
до создания роутера они падают.
"""
from __future__ import annotations

from unittest.mock import patch

import fakeredis
import pytest
from fastapi.testclient import TestClient

from core_api.main import app


@pytest.fixture
def settings_client(db_session):
    """TestClient поверх PG-сессии db_session. Redis — fake."""
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
    """Сидируем singleton-row с дефолтами + auto_close_minutes=60."""
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


def test_get_route_registered() -> None:
    """3.1a — GET /api/v1/admin/settings регистрируется ровно один раз."""
    matches = [
        route
        for route in app.routes
        if "GET" in (getattr(route, "methods", set()) or set())
        and getattr(route, "path", "") == "/api/v1/admin/settings"
    ]
    assert len(matches) == 1, (
        f"Ожидался один GET /api/v1/admin/settings, найдено: {len(matches)}"
    )


def test_admin_get_returns_default_snapshot(
    settings_client, admin_headers, db_session
) -> None:
    """3.1b — admin получает полный snapshot с auto_close_minutes=60."""
    _seed_default_row(db_session)

    response = settings_client.get("/api/v1/admin/settings", headers=admin_headers)
    assert response.status_code == 200, response.text

    body = response.json()
    # Все существующие поля
    for field in (
        "shop_lat",
        "shop_lon",
        "delivery_radius_km",
        "min_delivery_amount",
        "free_delivery_threshold",
        "delivery_fee",
        "loyalty_percent",
        "default_prep_time_minutes",
        "estimated_delivery_time_minutes",
        "working_hours",
        "updated_at",
    ):
        assert field in body, f"Поле {field!r} отсутствует в ответе: {body}"

    # Новое поле миграции 0008
    assert body["auto_close_minutes"] == 60

    # working_hours — 7 дней, каждый с open/close
    assert set(body["working_hours"].keys()) == {
        "mon",
        "tue",
        "wed",
        "thu",
        "fri",
        "sat",
        "sun",
    }
