"""RED: RBAC для /api/v1/admin/settings (PDD §5.2, §7.1, INV-010).

GET и PUT доступны только ADMIN. Barista/courier/customer → 403.
Без токена → 401. Маршруты присутствуют в ROUTE_MATRIX, не в PUBLIC_ROUTES.
"""
from __future__ import annotations

from unittest.mock import patch

import fakeredis
import pytest
from fastapi.testclient import TestClient

from core_api.main import app
from core_api.rbac_matrix import ADMIN, PUBLIC_ROUTES, ROUTE_MATRIX


ADMIN_SETTINGS_ROWS = [
    ("GET", "/api/v1/admin/settings"),
    ("PUT", "/api/v1/admin/settings"),
]


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


def _put_payload():
    return {
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
        "working_hours": {
            day: {"open": "08:00", "close": "22:00"}
            for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
        },
    }


# ---------------------------------------------------------------------------
# 6.x — RBAC matrix contract
# ---------------------------------------------------------------------------


def test_rbac_matrix_admin_only() -> None:
    """6.0a — обе строки ROUTE_MATRIX содержат ровно {ADMIN}."""
    for key in ADMIN_SETTINGS_ROWS:
        assert key in ROUTE_MATRIX, f"Маршрут {key} отсутствует в ROUTE_MATRIX"
        assert ROUTE_MATRIX[key] == {ADMIN}, (
            f"Маршрут {key} должен разрешать только ADMIN, получено: {ROUTE_MATRIX[key]}"
        )


def test_rbac_routes_not_public() -> None:
    """6.0b — оба маршрута не в PUBLIC_ROUTES."""
    for key in ADMIN_SETTINGS_ROWS:
        assert key not in PUBLIC_ROUTES, f"{key} не должен быть публичным"


# ---------------------------------------------------------------------------
# 6.1 — GET RBAC
# ---------------------------------------------------------------------------


def test_get_forbidden_for_barista(settings_client, barista_headers) -> None:
    response = settings_client.get("/api/v1/admin/settings", headers=barista_headers)
    assert response.status_code == 403, response.text


def test_get_forbidden_for_courier(settings_client, courier_headers) -> None:
    response = settings_client.get("/api/v1/admin/settings", headers=courier_headers)
    assert response.status_code == 403, response.text


def test_get_forbidden_for_customer(settings_client, customer_headers) -> None:
    response = settings_client.get("/api/v1/admin/settings", headers=customer_headers)
    assert response.status_code == 403, response.text


def test_get_unauthorized_without_token(settings_client) -> None:
    response = settings_client.get("/api/v1/admin/settings")
    assert response.status_code == 401, response.text


# ---------------------------------------------------------------------------
# 6.2 — PUT RBAC
# ---------------------------------------------------------------------------


def test_put_forbidden_for_barista(settings_client, barista_headers) -> None:
    response = settings_client.put(
        "/api/v1/admin/settings", headers=barista_headers, json=_put_payload()
    )
    assert response.status_code == 403, response.text


def test_put_forbidden_for_courier(settings_client, courier_headers) -> None:
    response = settings_client.put(
        "/api/v1/admin/settings", headers=courier_headers, json=_put_payload()
    )
    assert response.status_code == 403, response.text


def test_put_forbidden_for_customer(settings_client, customer_headers) -> None:
    response = settings_client.put(
        "/api/v1/admin/settings", headers=customer_headers, json=_put_payload()
    )
    assert response.status_code == 403, response.text


def test_put_unauthorized_without_token(settings_client) -> None:
    response = settings_client.put("/api/v1/admin/settings", json=_put_payload())
    assert response.status_code == 401, response.text
