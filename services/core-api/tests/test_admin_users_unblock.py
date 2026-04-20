"""RED: тесты unblock_user сервиса + route POST /api/v1/admin/users/{id}/unblock."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import fakeredis
import pytest
from fastapi.testclient import TestClient

from core_api.main import app
from shared.enums import OrderStatus, OrderType, UserStatus
from shared.models.order import Order
from shared.models.user import User
from tests._factories.admin_users import make_user_with_profile
from tests._factories.orders import seed_orders_across_statuses


@pytest.fixture
def admin_users_client(db_session):
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


# ===========================================================================
# 5.x — unblock_user service tests
# ===========================================================================


def test_unblock_user_symbol_absent() -> None:
    """5.1 — символ unblock_user должен существовать после GREEN."""
    from core_api.services.admin_users import unblock_user  # noqa: F401

    assert callable(unblock_user)


def test_unblock_user_happy_path_flips_to_active(db_session) -> None:
    """5.2 — BLOCKED → ACTIVE, count=0."""
    from core_api.services.admin_users import unblock_user

    user = make_user_with_profile(
        db_session, status=UserStatus.BLOCKED, display_name="Blocked"
    )
    db_session.commit()

    response = unblock_user(db=db_session, user_id=user.id)

    assert response.status == "active"
    assert response.cancelled_orders_count == 0

    refreshed = db_session.get(User, user.id)
    assert refreshed.status == UserStatus.ACTIVE


def test_unblock_user_idempotent_when_active(db_session) -> None:
    """5.3 — ACTIVE → no-op, остаётся ACTIVE."""
    from core_api.services.admin_users import unblock_user

    user = make_user_with_profile(
        db_session, status=UserStatus.ACTIVE, display_name="Active"
    )
    db_session.commit()

    response = unblock_user(db=db_session, user_id=user.id)

    assert response.status == "active"
    assert response.cancelled_orders_count == 0

    refreshed = db_session.get(User, user.id)
    assert refreshed.status == UserStatus.ACTIVE


def test_unblock_user_pending_verification_raises_invalid_state(db_session) -> None:
    """5.4 — PENDING_VERIFICATION → InvalidUserStateError."""
    from core_api.services.admin_users import InvalidUserStateError, unblock_user

    user = make_user_with_profile(
        db_session, status=UserStatus.PENDING_VERIFICATION, display_name="P"
    )
    db_session.commit()

    with pytest.raises(InvalidUserStateError):
        unblock_user(db=db_session, user_id=user.id)


def test_unblock_user_deleted_raises_invalid_state(db_session) -> None:
    """5.5 — DELETED → InvalidUserStateError."""
    from core_api.services.admin_users import InvalidUserStateError, unblock_user

    user = make_user_with_profile(
        db_session, status=UserStatus.DELETED, display_name="D"
    )
    db_session.commit()

    with pytest.raises(InvalidUserStateError):
        unblock_user(db=db_session, user_id=user.id)


def test_unblock_user_tombstone_raises_invalid_state(db_session) -> None:
    """5.6 — tombstoned user → InvalidUserStateError."""
    from core_api.services.admin_users import InvalidUserStateError, unblock_user

    user = make_user_with_profile(
        db_session,
        status=UserStatus.ACTIVE,
        display_name="T",
        deleted_at=datetime.now(tz=UTC),
    )
    db_session.commit()

    with pytest.raises(InvalidUserStateError):
        unblock_user(db=db_session, user_id=user.id)


def test_unblock_user_does_not_resurrect_cancelled_orders(db_session) -> None:
    """5.7 — unblock НЕ воскрешает CANCELLED orders (каскад один раз)."""
    from core_api.services.admin_users import unblock_user

    user = make_user_with_profile(
        db_session, status=UserStatus.BLOCKED, display_name="U"
    )
    seeded = seed_orders_across_statuses(
        db_session,
        user=user,
        counts={(OrderStatus.CANCELLED, OrderType.PICKUP): 2},
    )
    db_session.commit()

    response = unblock_user(db=db_session, user_id=user.id)

    assert response.status == "active"
    refreshed = db_session.get(User, user.id)
    assert refreshed.status == UserStatus.ACTIVE

    for oid in seeded.order_ids_by_bucket[(OrderStatus.CANCELLED, OrderType.PICKUP)]:
        order = db_session.get(Order, oid)
        assert order.status == OrderStatus.CANCELLED


# ===========================================================================
# 5.8–5.13 — POST /api/v1/admin/users/{user_id}/unblock router tests
# ===========================================================================


def test_unblock_user_route_registered() -> None:
    """5.8 — POST /api/v1/admin/users/{user_id}/unblock регистрируется ровно один раз."""
    matches = []
    for route in app.routes:
        methods = getattr(route, "methods", set()) or set()
        path = getattr(route, "path", "")
        if "POST" in methods and path == "/api/v1/admin/users/{user_id}/unblock":
            matches.append(route)

    assert len(matches) == 1, (
        f"Ожидался ровно 1 POST /api/v1/admin/users/{{user_id}}/unblock, нашли {len(matches)}"
    )


def test_unblock_user_route_rejects_no_auth(admin_users_client) -> None:
    """5.9 — без Authorization header → 401."""
    response = admin_users_client.post(f"/api/v1/admin/users/{uuid.uuid4()}/unblock")
    assert response.status_code == 401


def test_unblock_user_route_rejects_customer(
    admin_users_client, customer_headers
) -> None:
    """5.10 — customer → 403."""
    response = admin_users_client.post(
        f"/api/v1/admin/users/{uuid.uuid4()}/unblock", headers=customer_headers
    )
    assert response.status_code == 403


def test_unblock_user_route_happy_path_returns_200(
    admin_users_client, admin_headers, db_session
) -> None:
    """5.11 — ADMIN unblock BLOCKED → 200, status=active."""
    user = make_user_with_profile(
        db_session, status=UserStatus.BLOCKED, display_name="Blocked"
    )
    db_session.commit()

    response = admin_users_client.post(
        f"/api/v1/admin/users/{user.id}/unblock", headers=admin_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "active"


def test_unblock_user_route_409_on_pending_verification(
    admin_users_client, admin_headers, db_session
) -> None:
    """5.12 — PENDING_VERIFICATION → 409."""
    user = make_user_with_profile(
        db_session, status=UserStatus.PENDING_VERIFICATION, display_name="P"
    )
    db_session.commit()

    response = admin_users_client.post(
        f"/api/v1/admin/users/{user.id}/unblock", headers=admin_headers
    )
    assert response.status_code == 409


def test_unblock_user_route_404_on_unknown_user_id(
    admin_users_client, admin_headers
) -> None:
    """5.13 — несуществующий user_id → 404."""
    response = admin_users_client.post(
        f"/api/v1/admin/users/{uuid.uuid4()}/unblock", headers=admin_headers
    )
    assert response.status_code == 404
