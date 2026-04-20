"""RED: GET /api/v1/admin/promocodes — листинг с computed state фильтром.

Сортировка created_at DESC, пагинация (default 20, max 100),
фильтры state={inactive|active|expired|exhausted|all}, code (prefix, CI).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import fakeredis
import pytest
from fastapi.testclient import TestClient

from core_api.main import app


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


def test_list_route_registered() -> None:
    """5.1 — GET /api/v1/admin/promocodes регистрируется ровно 1 раз."""
    matches = [
        route
        for route in app.routes
        if "GET" in (getattr(route, "methods", set()) or set())
        and getattr(route, "path", "") == "/api/v1/admin/promocodes"
    ]
    assert len(matches) == 1


def test_list_default_state_all_returns_every_bucket(
    promo_client, admin_headers, db_session
) -> None:
    """5.2 — default state=all возвращает промокоды из всех 4 бакетов."""
    from tests._factories.promocodes import seed_promocodes_across_states

    buckets = seed_promocodes_across_states(db_session)

    r = promo_client.get("/api/v1/admin/promocodes", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()

    states_returned = {item["state"] for item in body["items"]}
    assert {"inactive", "active", "expired", "exhausted"}.issubset(states_returned)


@pytest.mark.parametrize("state", ["active", "expired", "exhausted", "inactive"])
def test_list_state_filter(promo_client, admin_headers, db_session, state) -> None:
    """5.3-5.6 — ?state=X → каждая строка имеет state==X."""
    from tests._factories.promocodes import seed_promocodes_across_states

    seed_promocodes_across_states(db_session)

    r = promo_client.get(
        f"/api/v1/admin/promocodes?state={state}", headers=admin_headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["items"]) >= 1
    for item in body["items"]:
        assert item["state"] == state


def test_list_code_prefix_case_insensitive(
    promo_client, admin_headers, db_session
) -> None:
    """5.7 — ?code=welc матчит WELCOME10 (case-insensitive prefix)."""
    from tests._factories.promocodes import make_promocode

    make_promocode(db_session, code="WELCOME10")
    db_session.commit()

    r = promo_client.get(
        "/api/v1/admin/promocodes?code=welc", headers=admin_headers
    )
    assert r.status_code == 200, r.text
    codes = {item["code"] for item in r.json()["items"]}
    assert "WELCOME10" in codes


def test_list_per_page_over_100_rejected(promo_client, admin_headers) -> None:
    """5.8 — per_page=101 → 422."""
    r = promo_client.get(
        "/api/v1/admin/promocodes?per_page=101", headers=admin_headers
    )
    assert r.status_code == 422


def test_list_sort_created_at_desc(promo_client, admin_headers, db_session) -> None:
    """5.9 — сортировка created_at DESC."""
    from shared.models.promocode import Promocode

    from tests._factories.promocodes import make_promocode

    t1 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    t2 = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)

    p1 = make_promocode(db_session, code="CODE_T1")
    p2 = make_promocode(db_session, code="CODE_T2")
    db_session.query(Promocode).filter(Promocode.id == p1.id).update(
        {Promocode.created_at: t1}
    )
    db_session.query(Promocode).filter(Promocode.id == p2.id).update(
        {Promocode.created_at: t2}
    )
    db_session.commit()

    r = promo_client.get("/api/v1/admin/promocodes", headers=admin_headers)
    assert r.status_code == 200
    codes = [item["code"] for item in r.json()["items"]]
    # T2 (свежее) должен идти раньше T1 в DESC-порядке
    assert codes.index("CODE_T2") < codes.index("CODE_T1")


def test_list_total_count_after_filter(
    promo_client, admin_headers, db_session
) -> None:
    """5.10 — total_count — count после фильтра state."""
    from tests._factories.promocodes import make_promocode

    now = datetime.now(UTC)
    future = now + timedelta(days=7)
    past = now - timedelta(days=1)

    # 4 active
    for i in range(4):
        make_promocode(
            db_session,
            code=f"ACT{i}",
            is_active=True,
            valid_until=future,
        )
    # 2 expired
    for i in range(2):
        make_promocode(
            db_session,
            code=f"EXP{i}",
            is_active=True,
            valid_until=past,
        )
    db_session.commit()

    r = promo_client.get(
        "/api/v1/admin/promocodes?state=active", headers=admin_headers
    )
    assert r.status_code == 200, r.text
    assert r.json()["total_count"] == 4


def test_list_pagination_slice(promo_client, admin_headers, db_session) -> None:
    """5.11 — page=2&per_page=10 → len==10, total_count=25."""
    from tests._factories.promocodes import make_promocode

    for i in range(25):
        make_promocode(db_session, code=f"PAG{i:02d}")
    db_session.commit()

    r = promo_client.get(
        "/api/v1/admin/promocodes?page=2&per_page=10", headers=admin_headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_count"] == 25
    assert len(body["items"]) == 10
    assert body["page"] == 2
    assert body["per_page"] == 10


def test_list_rejects_barista(promo_client, barista_headers) -> None:
    """5.12 — barista → 403."""
    r = promo_client.get("/api/v1/admin/promocodes", headers=barista_headers)
    assert r.status_code == 403


def test_list_requires_token(promo_client) -> None:
    """5.13 — без токена → 401."""
    r = promo_client.get("/api/v1/admin/promocodes")
    assert r.status_code == 401
