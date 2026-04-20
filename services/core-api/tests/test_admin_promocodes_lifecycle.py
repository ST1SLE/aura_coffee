"""RED: compute_state + activate/deactivate lifecycle (PDD §6.6).

compute_state — чистая функция, единый источник истины для вычисляемого
state ('inactive'/'active'/'expired'/'exhausted'). Priority: expired >
exhausted > active > inactive.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import fakeredis
import pytest
from fastapi.testclient import TestClient

from core_api.main import app
from shared.enums import PromocodeDiscountType
from shared.models.promocode import Promocode


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


def _build_promo(**overrides) -> Promocode:
    """Конструирует Promocode в памяти (без session.add) для compute_state тестов."""
    defaults = {
        "id": uuid.uuid4(),
        "code": "CHECK",
        "discount_type": PromocodeDiscountType.PERCENT,
        "discount_value": 10,
        "min_order_amount": 0,
        "valid_from": None,
        "valid_until": None,
        "max_uses": None,
        "max_uses_per_user": None,
        "current_uses": 0,
        "is_active": True,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Promocode(**defaults)


# ===========================================================================
# 2.x — compute_state
# ===========================================================================


def test_compute_state_symbol_absent() -> None:
    """2.1 — compute_state должен существовать в services.admin_promocodes."""
    from core_api.services.admin_promocodes import compute_state  # noqa: F401

    assert callable(compute_state)


def test_compute_state_expired_beats_everything() -> None:
    """2.2 — valid_until в прошлом побеждает exhausted/active."""
    from core_api.services.admin_promocodes import compute_state

    now = datetime(2026, 4, 20, 12, 0, tzinfo=UTC)
    promo = _build_promo(
        valid_until=now - timedelta(days=1),
        max_uses=5,
        current_uses=5,
        is_active=True,
    )
    assert compute_state(promo, now) == "expired"


def test_compute_state_exhausted_when_not_expired() -> None:
    """2.3 — current_uses >= max_uses (не expired) → exhausted."""
    from core_api.services.admin_promocodes import compute_state

    now = datetime(2026, 4, 20, 12, 0, tzinfo=UTC)
    promo = _build_promo(
        valid_until=now + timedelta(days=1),
        max_uses=5,
        current_uses=5,
        is_active=True,
    )
    assert compute_state(promo, now) == "exhausted"


def test_compute_state_active_happy() -> None:
    """2.4 — is_active=True, valid_from <= now < valid_until, current_uses < max_uses."""
    from core_api.services.admin_promocodes import compute_state

    now = datetime(2026, 4, 20, 12, 0, tzinfo=UTC)
    promo = _build_promo(
        is_active=True,
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=1),
        max_uses=10,
        current_uses=0,
    )
    assert compute_state(promo, now) == "active"


def test_compute_state_inactive_when_is_active_false() -> None:
    """2.5 — is_active=False, остальное здоровое → inactive."""
    from core_api.services.admin_promocodes import compute_state

    now = datetime(2026, 4, 20, 12, 0, tzinfo=UTC)
    promo = _build_promo(
        is_active=False,
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=1),
    )
    assert compute_state(promo, now) == "inactive"


def test_compute_state_inactive_before_valid_from() -> None:
    """2.6 — is_active=True, но valid_from в будущем → inactive."""
    from core_api.services.admin_promocodes import compute_state

    now = datetime(2026, 4, 20, 12, 0, tzinfo=UTC)
    promo = _build_promo(
        is_active=True,
        valid_from=now + timedelta(days=1),
        valid_until=now + timedelta(days=10),
    )
    assert compute_state(promo, now) == "inactive"


# ===========================================================================
# 8.x — POST /{id}/activate
# ===========================================================================


def test_activate_route_registered() -> None:
    """8.1 — POST /{id}/activate зарегистрирован."""
    matches = [
        route
        for route in app.routes
        if "POST" in (getattr(route, "methods", set()) or set())
        and getattr(route, "path", "")
        == "/api/v1/admin/promocodes/{promocode_id}/activate"
    ]
    assert len(matches) == 1


def test_activate_requires_valid_until(
    promo_client, admin_headers, db_session
) -> None:
    """8.2 — valid_until IS NULL → 422."""
    from tests._factories.promocodes import make_promocode

    promo = make_promocode(db_session, code="NOVU", valid_until=None, is_active=False)
    db_session.commit()

    r = promo_client.post(
        f"/api/v1/admin/promocodes/{promo.id}/activate", headers=admin_headers
    )
    assert r.status_code == 422


def test_activate_expired_rejected(promo_client, admin_headers, db_session) -> None:
    """8.3 — expired → 409."""
    from tests._factories.promocodes import make_promocode

    promo = make_promocode(
        db_session,
        code="EXPACT",
        valid_until=datetime.now(UTC) - timedelta(days=1),
        is_active=False,
    )
    db_session.commit()

    r = promo_client.post(
        f"/api/v1/admin/promocodes/{promo.id}/activate", headers=admin_headers
    )
    assert r.status_code == 409


def test_activate_exhausted_rejected(
    promo_client, admin_headers, db_session
) -> None:
    """8.4 — exhausted → 409."""
    from tests._factories.promocodes import make_promocode

    promo = make_promocode(
        db_session,
        code="EXHACT",
        valid_until=datetime.now(UTC) + timedelta(days=7),
        max_uses=5,
        current_uses=5,
        is_active=False,
    )
    db_session.commit()

    r = promo_client.post(
        f"/api/v1/admin/promocodes/{promo.id}/activate", headers=admin_headers
    )
    assert r.status_code == 409


def test_activate_happy_sets_is_active_true(
    promo_client, admin_headers, db_session
) -> None:
    """8.5 — happy path: 200, is_active=true, state=active."""
    from tests._factories.promocodes import make_promocode

    promo = make_promocode(
        db_session,
        code="HAPPY",
        valid_until=datetime.now(UTC) + timedelta(days=7),
        max_uses=10,
        current_uses=0,
        is_active=False,
    )
    db_session.commit()

    r = promo_client.post(
        f"/api/v1/admin/promocodes/{promo.id}/activate", headers=admin_headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_active"] is True
    assert body["state"] == "active"

    db_session.expire_all()
    reread = db_session.get(Promocode, promo.id)
    assert reread is not None and reread.is_active is True


def test_activate_rejects_barista(promo_client, barista_headers) -> None:
    """8.6 — barista → 403."""
    r = promo_client.post(
        f"/api/v1/admin/promocodes/{uuid.uuid4()}/activate",
        headers=barista_headers,
    )
    assert r.status_code == 403


def test_activate_unknown_id_returns_404(promo_client, admin_headers) -> None:
    """8.7 — неизвестный id → 404."""
    r = promo_client.post(
        f"/api/v1/admin/promocodes/{uuid.uuid4()}/activate",
        headers=admin_headers,
    )
    assert r.status_code == 404


# ===========================================================================
# 9.x — POST /{id}/deactivate
# ===========================================================================


def test_deactivate_route_registered() -> None:
    """9.1 — POST /{id}/deactivate зарегистрирован."""
    matches = [
        route
        for route in app.routes
        if "POST" in (getattr(route, "methods", set()) or set())
        and getattr(route, "path", "")
        == "/api/v1/admin/promocodes/{promocode_id}/deactivate"
    ]
    assert len(matches) == 1


def test_deactivate_expired_rejected(
    promo_client, admin_headers, db_session
) -> None:
    """9.2 — деактивация expired → 409."""
    from tests._factories.promocodes import make_promocode

    promo = make_promocode(
        db_session,
        code="EXPDEACT",
        valid_until=datetime.now(UTC) - timedelta(days=1),
        is_active=True,
    )
    db_session.commit()

    r = promo_client.post(
        f"/api/v1/admin/promocodes/{promo.id}/deactivate", headers=admin_headers
    )
    assert r.status_code == 409


def test_deactivate_happy_sets_is_active_false(
    promo_client, admin_headers, db_session
) -> None:
    """9.3 — happy path: 200, is_active=false."""
    from tests._factories.promocodes import make_promocode

    promo = make_promocode(
        db_session,
        code="DEACT",
        valid_until=datetime.now(UTC) + timedelta(days=7),
        is_active=True,
    )
    db_session.commit()

    r = promo_client.post(
        f"/api/v1/admin/promocodes/{promo.id}/deactivate", headers=admin_headers
    )
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is False


def test_deactivate_unknown_id_returns_404(promo_client, admin_headers) -> None:
    """9.4 — random uuid → 404."""
    r = promo_client.post(
        f"/api/v1/admin/promocodes/{uuid.uuid4()}/deactivate",
        headers=admin_headers,
    )
    assert r.status_code == 404


def test_deactivate_rejects_customer(promo_client, customer_headers) -> None:
    """9.5 — customer → 403."""
    r = promo_client.post(
        f"/api/v1/admin/promocodes/{uuid.uuid4()}/deactivate",
        headers=customer_headers,
    )
    assert r.status_code == 403
