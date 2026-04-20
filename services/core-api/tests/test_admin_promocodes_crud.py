"""RED: admin-promocodes CRUD — schemas + create + detail (PDD §6.6, INV-010).

Все таргет-импорты — ВНУТРИ тел тестов. Факт отсутствия реализации вылезает
по тесту, а не на уровне коллекции.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import get_args
from unittest.mock import patch

import fakeredis
import pytest
from fastapi.testclient import TestClient

from core_api.main import app


# ---------------------------------------------------------------------------
# TestClient с PG-сессией
# ---------------------------------------------------------------------------


@pytest.fixture
def promo_client(db_session):
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


def _base_create_payload(**overrides):
    future = (datetime.now(UTC) + timedelta(days=7)).isoformat()
    payload = {
        "code": "welcome10",
        "discount_type": "percent",
        "discount_value": 10,
        "min_order_amount": 0,
        "valid_until": future,
    }
    payload.update(overrides)
    return payload


# ===========================================================================
# 3.x — Pydantic schema contract
# ===========================================================================


def test_schemas_module_importable() -> None:
    """3.1 — schemas/promocode.py существует и экспортирует нужные символы."""
    from core_api.schemas.promocode import (  # noqa: F401
        PromocodeCreate,
        PromocodeListResponse,
        PromocodeResponse,
        PromocodeState,
        PromocodeUpdate,
    )

    assert PromocodeCreate is not None
    assert PromocodeUpdate is not None
    assert PromocodeResponse is not None
    assert PromocodeListResponse is not None
    assert PromocodeState is not None


def test_promocode_update_all_fields_optional() -> None:
    """3.2 — PromocodeUpdate() без аргументов не падает."""
    from core_api.schemas.promocode import PromocodeUpdate

    # Должно пройти без ValidationError
    PromocodeUpdate()


def test_promocode_state_literal_values() -> None:
    """3.3 — PromocodeState = Literal['inactive','active','expired','exhausted']."""
    from core_api.schemas.promocode import PromocodeState

    values = set(get_args(PromocodeState))
    assert values == {"inactive", "active", "expired", "exhausted"}


# ===========================================================================
# 4.x — POST /api/v1/admin/promocodes
# ===========================================================================


def test_create_route_registered() -> None:
    """4.1 — POST /api/v1/admin/promocodes должен быть зарегистрирован ровно раз."""
    matches = [
        route
        for route in app.routes
        if "POST" in (getattr(route, "methods", set()) or set())
        and getattr(route, "path", "") == "/api/v1/admin/promocodes"
    ]
    assert len(matches) == 1, (
        f"Ожидался ровно 1 POST /api/v1/admin/promocodes, нашли {len(matches)}"
    )


def test_create_happy_path_uppercases_code(promo_client, admin_headers) -> None:
    """4.2 — сервер канонизует code до UPPER, is_active=false, current_uses=0."""
    payload = _base_create_payload(code="welcome10")
    r = promo_client.post(
        "/api/v1/admin/promocodes", json=payload, headers=admin_headers
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["code"] == "WELCOME10"
    assert body["is_active"] is False
    assert body["current_uses"] == 0
    assert "state" in body


def test_create_duplicate_code_returns_409(promo_client, admin_headers) -> None:
    """4.3 — одинаковый code (с учётом UPPER) → 409."""
    p1 = _base_create_payload(code="DUP")
    p2 = _base_create_payload(code="dup")
    r1 = promo_client.post("/api/v1/admin/promocodes", json=p1, headers=admin_headers)
    assert r1.status_code == 201, r1.text
    r2 = promo_client.post("/api/v1/admin/promocodes", json=p2, headers=admin_headers)
    assert r2.status_code == 409


def test_create_rejects_bad_pattern(promo_client, admin_headers) -> None:
    """4.4 — code не матчит ^[A-Z0-9_-]+$ → 422."""
    r = promo_client.post(
        "/api/v1/admin/promocodes",
        json=_base_create_payload(code="bad code!"),
        headers=admin_headers,
    )
    assert r.status_code == 422


def test_create_percent_over_100_rejected(promo_client, admin_headers) -> None:
    """4.5 — percent, discount_value>100 → 422."""
    r = promo_client.post(
        "/api/v1/admin/promocodes",
        json=_base_create_payload(code="PCT", discount_type="percent", discount_value=150),
        headers=admin_headers,
    )
    assert r.status_code == 422


def test_create_fixed_amount_non_positive_rejected(promo_client, admin_headers) -> None:
    """4.6 — fixed_amount, discount_value=0 → 422."""
    r = promo_client.post(
        "/api/v1/admin/promocodes",
        json=_base_create_payload(
            code="FIX0", discount_type="fixed_amount", discount_value=0
        ),
        headers=admin_headers,
    )
    assert r.status_code == 422


def test_create_dates_inverted_rejected(promo_client, admin_headers) -> None:
    """4.7 — valid_from > valid_until → 422."""
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    future = (datetime.now(UTC) + timedelta(days=7)).isoformat()
    r = promo_client.post(
        "/api/v1/admin/promocodes",
        json=_base_create_payload(code="DATES", valid_from=future, valid_until=past),
        headers=admin_headers,
    )
    assert r.status_code == 422


def test_create_per_user_over_max_uses_rejected(promo_client, admin_headers) -> None:
    """4.8 — max_uses_per_user > max_uses → 422."""
    r = promo_client.post(
        "/api/v1/admin/promocodes",
        json=_base_create_payload(code="QUOTA", max_uses=10, max_uses_per_user=20),
        headers=admin_headers,
    )
    assert r.status_code == 422


def test_create_requires_admin_rejects_barista(promo_client, barista_headers) -> None:
    """4.9 — barista → 403 (INV-010)."""
    r = promo_client.post(
        "/api/v1/admin/promocodes",
        json=_base_create_payload(code="BAR"),
        headers=barista_headers,
    )
    assert r.status_code == 403


def test_create_requires_token(promo_client) -> None:
    """4.10 — без Authorization → 401."""
    r = promo_client.post(
        "/api/v1/admin/promocodes", json=_base_create_payload(code="NOTOK")
    )
    assert r.status_code == 401


# ===========================================================================
# 6.x — GET /api/v1/admin/promocodes/{id}
# ===========================================================================


def test_detail_route_registered() -> None:
    """6.1 — GET /api/v1/admin/promocodes/{promocode_id}."""
    matches = [
        route
        for route in app.routes
        if "GET" in (getattr(route, "methods", set()) or set())
        and getattr(route, "path", "") == "/api/v1/admin/promocodes/{promocode_id}"
    ]
    assert len(matches) == 1, (
        f"Ожидался ровно 1 GET /api/v1/admin/promocodes/{{promocode_id}}, нашли {len(matches)}"
    )


def test_detail_happy_returns_state_field(promo_client, admin_headers, db_session) -> None:
    """6.2 — body содержит поле state (INACTIVE у свежесозданного)."""
    from tests._factories.promocodes import make_promocode

    promo = make_promocode(db_session)
    db_session.commit()

    r = promo_client.get(
        f"/api/v1/admin/promocodes/{promo.id}", headers=admin_headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # is_active=False, не expired, не exhausted → inactive
    assert body["state"] == "inactive"
    assert body["code"] == promo.code


def test_detail_unknown_id_returns_404(promo_client, admin_headers) -> None:
    """6.3 — random uuid → 404."""
    r = promo_client.get(
        f"/api/v1/admin/promocodes/{uuid.uuid4()}", headers=admin_headers
    )
    assert r.status_code == 404


def test_detail_rejects_customer(promo_client, customer_headers) -> None:
    """6.4 — customer → 403."""
    r = promo_client.get(
        f"/api/v1/admin/promocodes/{uuid.uuid4()}", headers=customer_headers
    )
    assert r.status_code == 403
