"""RED: тесты block_user сервиса + route POST /api/v1/admin/users/{id}/block.

Блок-сервис каскадит на существующий services.order_cancel.cancel_order.
Чтобы не ходить в Celery broker, патчим модуль-уровневый
`core_api.services.order_cancel.celery_app.send_task`.

Все target-импорты — внутри тестов (RED).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

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
def celery_send_task_mock():
    """Мокаем celery_app.send_task на модуле order_cancel."""
    with patch(
        "core_api.services.order_cancel.celery_app.send_task",
        new_callable=MagicMock,
    ) as m:
        yield m


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
# 4.x — block_user service tests
# ===========================================================================


def test_block_user_symbol_absent() -> None:
    """4.1 — символ block_user должен существовать после GREEN."""
    from core_api.services.admin_users import block_user  # noqa: F401

    assert callable(block_user)


def test_invalid_user_state_error_symbol_absent() -> None:
    """4.2 — domain error InvalidUserStateError должен экспортироваться."""
    from core_api.services.admin_users import InvalidUserStateError  # noqa: F401

    assert issubclass(InvalidUserStateError, Exception)


def test_block_user_happy_path_with_three_active_orders(
    db_session, celery_send_task_mock
) -> None:
    """4.3 — ACTIVE user + 3 активных заказа → BLOCKED + cancelled_orders_count=3."""
    from core_api.services.admin_users import block_user

    user = make_user_with_profile(
        db_session, status=UserStatus.ACTIVE, display_name="ActiveBlocker"
    )
    seed_orders_across_statuses(
        db_session,
        user=user,
        counts={
            (OrderStatus.CREATED, OrderType.PICKUP): 1,
            (OrderStatus.PAID, OrderType.PICKUP): 1,
            (OrderStatus.PREPARING, OrderType.PICKUP): 1,
        },
    )
    db_session.commit()

    response = block_user(db=db_session, user_id=user.id)

    assert response.status == "blocked"
    assert response.cancelled_orders_count == 3

    refreshed_user = db_session.get(User, user.id)
    assert refreshed_user.status == UserStatus.BLOCKED

    orders = db_session.query(Order).filter(Order.user_id == user.id).all()
    for order in orders:
        assert order.status == OrderStatus.CANCELLED


def test_block_user_completed_and_cancelled_orders_are_not_touched(
    db_session, celery_send_task_mock
) -> None:
    """4.4 — COMPLETED и CANCELLED остаются как есть; cancelled_orders_count=1."""
    from core_api.services.admin_users import block_user

    user = make_user_with_profile(db_session, status=UserStatus.ACTIVE, display_name="U")
    seeded = seed_orders_across_statuses(
        db_session,
        user=user,
        counts={
            (OrderStatus.PAID, OrderType.PICKUP): 1,
            (OrderStatus.COMPLETED, OrderType.PICKUP): 1,
            (OrderStatus.CANCELLED, OrderType.PICKUP): 1,
        },
    )
    db_session.commit()

    response = block_user(db=db_session, user_id=user.id)

    assert response.cancelled_orders_count == 1

    [completed_id] = seeded.order_ids_by_bucket[(OrderStatus.COMPLETED, OrderType.PICKUP)]
    [cancelled_id] = seeded.order_ids_by_bucket[(OrderStatus.CANCELLED, OrderType.PICKUP)]
    completed = db_session.get(Order, completed_id)
    cancelled = db_session.get(Order, cancelled_id)
    assert completed.status == OrderStatus.COMPLETED
    assert cancelled.status == OrderStatus.CANCELLED


def test_block_user_in_delivery_orders_are_skipped_silently(
    db_session, celery_send_task_mock
) -> None:
    """4.5 — IN_DELIVERY skip silently; cancel_order для него НЕ вызывается."""
    from core_api.services.admin_users import block_user

    user = make_user_with_profile(db_session, status=UserStatus.ACTIVE, display_name="U")
    seeded = seed_orders_across_statuses(
        db_session,
        user=user,
        counts={
            (OrderStatus.PAID, OrderType.PICKUP): 1,
            (OrderStatus.IN_DELIVERY, OrderType.DELIVERY): 1,
        },
    )
    db_session.commit()

    response = block_user(db=db_session, user_id=user.id)

    assert response.cancelled_orders_count == 1

    [in_delivery_id] = seeded.order_ids_by_bucket[
        (OrderStatus.IN_DELIVERY, OrderType.DELIVERY)
    ]
    in_delivery = db_session.get(Order, in_delivery_id)
    assert in_delivery.status == OrderStatus.IN_DELIVERY


def test_block_user_idempotent_when_already_blocked(
    db_session, celery_send_task_mock
) -> None:
    """4.6 — повторный block для BLOCKED → no-op, count=0, celery не дёргается."""
    from core_api.services.admin_users import block_user

    user = make_user_with_profile(
        db_session, status=UserStatus.BLOCKED, display_name="Already"
    )
    db_session.commit()

    response = block_user(db=db_session, user_id=user.id)

    assert response.status == "blocked"
    assert response.cancelled_orders_count == 0
    assert celery_send_task_mock.call_count == 0


def test_block_user_pending_verification_raises_invalid_state(db_session) -> None:
    """4.7 — PENDING_VERIFICATION → InvalidUserStateError."""
    from core_api.services.admin_users import InvalidUserStateError, block_user

    user = make_user_with_profile(
        db_session, status=UserStatus.PENDING_VERIFICATION, display_name="P"
    )
    db_session.commit()

    with pytest.raises(InvalidUserStateError):
        block_user(db=db_session, user_id=user.id)


def test_block_user_deleted_raises_invalid_state(db_session) -> None:
    """4.8 — DELETED → InvalidUserStateError."""
    from core_api.services.admin_users import InvalidUserStateError, block_user

    user = make_user_with_profile(
        db_session, status=UserStatus.DELETED, display_name="D"
    )
    db_session.commit()

    with pytest.raises(InvalidUserStateError):
        block_user(db=db_session, user_id=user.id)


def test_block_user_tombstone_raises_invalid_state(db_session) -> None:
    """4.9 — tombstoned user (deleted_at IS NOT NULL) → InvalidUserStateError."""
    from core_api.services.admin_users import InvalidUserStateError, block_user

    user = make_user_with_profile(
        db_session,
        status=UserStatus.ACTIVE,
        display_name="T",
        deleted_at=datetime.now(tz=UTC),
    )
    db_session.commit()

    with pytest.raises(InvalidUserStateError):
        block_user(db=db_session, user_id=user.id)


# ===========================================================================
# 4.10–4.15 — POST /api/v1/admin/users/{user_id}/block router tests
# ===========================================================================


def test_block_user_route_registered() -> None:
    """4.10 — POST /api/v1/admin/users/{user_id}/block зарегистрирован (GREEN target)."""
    matches = []
    for route in app.routes:
        methods = getattr(route, "methods", set()) or set()
        path = getattr(route, "path", "")
        if "POST" in methods and path == "/api/v1/admin/users/{user_id}/block":
            matches.append(route)

    assert len(matches) == 1, (
        f"Ожидался ровно 1 POST /api/v1/admin/users/{{user_id}}/block, нашли {len(matches)}"
    )


def test_block_user_route_rejects_no_auth(admin_users_client) -> None:
    """4.11 — без Authorization header → 401."""
    response = admin_users_client.post(f"/api/v1/admin/users/{uuid.uuid4()}/block")
    assert response.status_code == 401


def test_block_user_route_rejects_barista(admin_users_client, barista_headers) -> None:
    """4.12 — barista → 403 (INV-010)."""
    response = admin_users_client.post(
        f"/api/v1/admin/users/{uuid.uuid4()}/block", headers=barista_headers
    )
    assert response.status_code == 403


def test_block_user_route_happy_path_returns_200_and_count(
    admin_users_client, admin_headers, db_session, celery_send_task_mock
) -> None:
    """4.13 — ADMIN POST /block ACTIVE-user с 3 активными orders → 200, count=3."""
    user = make_user_with_profile(
        db_session, status=UserStatus.ACTIVE, display_name="RouteBlocker"
    )
    seed_orders_across_statuses(
        db_session,
        user=user,
        counts={
            (OrderStatus.CREATED, OrderType.PICKUP): 1,
            (OrderStatus.PAID, OrderType.PICKUP): 1,
            (OrderStatus.PREPARING, OrderType.PICKUP): 1,
        },
    )
    db_session.commit()

    response = admin_users_client.post(
        f"/api/v1/admin/users/{user.id}/block", headers=admin_headers
    )
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "blocked"
    assert body["cancelled_orders_count"] == 3


def test_block_user_route_409_on_pending_verification(
    admin_users_client, admin_headers, db_session
) -> None:
    """4.14 — PENDING_VERIFICATION → 409 invalid_user_state."""
    user = make_user_with_profile(
        db_session, status=UserStatus.PENDING_VERIFICATION, display_name="P"
    )
    db_session.commit()

    response = admin_users_client.post(
        f"/api/v1/admin/users/{user.id}/block", headers=admin_headers
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "invalid_user_state"


def test_block_user_route_404_on_unknown_user_id(
    admin_users_client, admin_headers
) -> None:
    """4.15 — несуществующий user_id → 404."""
    response = admin_users_client.post(
        f"/api/v1/admin/users/{uuid.uuid4()}/block", headers=admin_headers
    )
    assert response.status_code == 404
