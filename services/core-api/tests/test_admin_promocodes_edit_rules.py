"""RED: PATCH /api/v1/admin/promocodes/{id} — правила редактирования (PDD §6.6).

current_uses == 0 — всё редактируется.
current_uses > 0 — только valid_until, max_uses, max_uses_per_user,
                   min_order_amount, is_active. Попытка менять
                   code/discount_type/discount_value → 422 с
                   type="field_locked_after_use" и field=<имя>.
"""
from __future__ import annotations

import uuid
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


def _extract_field_from_detail(detail) -> tuple[str | None, str | None]:
    """Ищем type/field либо в detail[i], либо прямо в detail (flat shape)."""
    if isinstance(detail, list):
        for item in detail:
            if isinstance(item, dict) and "field" in item:
                return item.get("type"), item.get("field")
        return None, None
    if isinstance(detail, dict):
        return detail.get("type"), detail.get("field")
    return None, None


def test_patch_route_registered() -> None:
    """7.1 — PATCH /api/v1/admin/promocodes/{promocode_id}."""
    matches = [
        route
        for route in app.routes
        if "PATCH" in (getattr(route, "methods", set()) or set())
        and getattr(route, "path", "") == "/api/v1/admin/promocodes/{promocode_id}"
    ]
    assert len(matches) == 1


def test_patch_unused_all_fields_editable(
    promo_client, admin_headers, db_session
) -> None:
    """7.2 — current_uses=0 → code/discount_value/valid_until редактируются."""
    from tests._factories.promocodes import make_promocode

    promo = make_promocode(db_session, code="OLD", discount_value=10)
    db_session.commit()

    new_until = (datetime.now(UTC) + timedelta(days=30)).isoformat()
    r = promo_client.patch(
        f"/api/v1/admin/promocodes/{promo.id}",
        json={"code": "NEW", "discount_value": 25, "valid_until": new_until},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["code"] == "NEW"
    assert body["discount_value"] == 25


@pytest.mark.parametrize(
    "payload,field_name",
    [
        ({"code": "NEWCODE"}, "code"),
        ({"discount_type": "fixed_amount"}, "discount_type"),
        ({"discount_value": 99}, "discount_value"),
    ],
)
def test_patch_used_rejects_locked_field(
    promo_client, admin_headers, db_session, payload, field_name
) -> None:
    """7.3-7.5 — current_uses>0 → locked поля дают 422 field_locked_after_use."""
    from tests._factories.promocodes import make_promocode

    promo = make_promocode(db_session, code="USED", discount_value=10, current_uses=1)
    db_session.commit()

    r = promo_client.patch(
        f"/api/v1/admin/promocodes/{promo.id}",
        json=payload,
        headers=admin_headers,
    )
    assert r.status_code == 422, r.text
    body = r.json()
    err_type, err_field = _extract_field_from_detail(body.get("detail"))
    assert err_type == "field_locked_after_use", f"Неожиданный type: {err_type}"
    assert err_field == field_name, f"Неожиданное field: {err_field}"


def test_patch_used_accepts_valid_until(
    promo_client, admin_headers, db_session
) -> None:
    """7.6 — current_uses>0 → valid_until всё ещё редактируется."""
    from tests._factories.promocodes import make_promocode

    promo = make_promocode(
        db_session,
        code="USEDVU",
        current_uses=2,
        valid_until=datetime.now(UTC) + timedelta(days=1),
    )
    db_session.commit()

    new_until = (datetime.now(UTC) + timedelta(days=60)).isoformat()
    r = promo_client.patch(
        f"/api/v1/admin/promocodes/{promo.id}",
        json={"valid_until": new_until},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text


def test_patch_used_accepts_is_active(
    promo_client, admin_headers, db_session
) -> None:
    """7.7 — current_uses>0 (не expired, не exhausted) → is_active редактируется."""
    from tests._factories.promocodes import make_promocode

    promo = make_promocode(
        db_session,
        code="USEDIA",
        current_uses=1,
        is_active=False,
        valid_until=datetime.now(UTC) + timedelta(days=7),
        max_uses=10,
    )
    db_session.commit()

    r = promo_client.patch(
        f"/api/v1/admin/promocodes/{promo.id}",
        json={"is_active": True},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text


def test_patch_merged_dates_must_be_ordered(
    promo_client, admin_headers, db_session
) -> None:
    """7.8 — после слияния patch'а valid_from < valid_until (INV)."""
    from tests._factories.promocodes import make_promocode

    now = datetime.now(UTC)
    t1 = now - timedelta(days=2)
    t3 = now + timedelta(days=3)
    t4 = now + timedelta(days=10)  # > t3

    promo = make_promocode(db_session, code="DATES", valid_from=t1, valid_until=t3)
    db_session.commit()

    # Сдвигаем valid_from так, чтобы он оказался > существующего valid_until
    r = promo_client.patch(
        f"/api/v1/admin/promocodes/{promo.id}",
        json={"valid_from": t4.isoformat()},
        headers=admin_headers,
    )
    assert r.status_code == 422


def test_patch_failed_lock_leaves_row_unchanged(
    promo_client, admin_headers, db_session
) -> None:
    """7.9 — 422 при locked-поле не меняет ряд (INV-004)."""
    from tests._factories.promocodes import make_promocode

    promo = make_promocode(db_session, code="OLDCODE", current_uses=1)
    db_session.commit()

    r = promo_client.patch(
        f"/api/v1/admin/promocodes/{promo.id}",
        json={"code": "NEWCODE"},
        headers=admin_headers,
    )
    assert r.status_code == 422

    # Читаем через GET — code не должен поменяться
    r2 = promo_client.get(
        f"/api/v1/admin/promocodes/{promo.id}", headers=admin_headers
    )
    assert r2.status_code == 200
    assert r2.json()["code"] == "OLDCODE"


def test_patch_rejects_barista(promo_client, barista_headers) -> None:
    """7.10 — barista → 403."""
    r = promo_client.patch(
        f"/api/v1/admin/promocodes/{uuid.uuid4()}",
        json={"is_active": True},
        headers=barista_headers,
    )
    assert r.status_code == 403


def test_patch_unknown_id_returns_404(promo_client, admin_headers) -> None:
    """7.11 — неизвестный uuid → 404."""
    r = promo_client.patch(
        f"/api/v1/admin/promocodes/{uuid.uuid4()}",
        json={"is_active": True},
        headers=admin_headers,
    )
    assert r.status_code == 404
