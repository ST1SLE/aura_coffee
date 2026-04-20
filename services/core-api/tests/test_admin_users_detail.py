"""RED: тесты staff-scoped detail пользователя (admin-users-api).

Импорты target-символов (get_user_detail, UserNotFoundError,
schemas LoyaltyTransactionItem) — внутри тестов.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import fakeredis
import pytest
from fastapi.testclient import TestClient

from core_api.main import app
from shared.enums import LoyaltyTransactionType, OrderStatus, OrderType, UserStatus
from tests._factories.admin_users import (
    make_user_with_loyalty_and_profile,
    make_user_with_profile,
)
from tests._factories.loyalty import seed_n_transactions
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
# 3.x — get_user_detail service tests
# ===========================================================================


def test_get_user_detail_symbol_absent() -> None:
    """3.1 — символ get_user_detail должен существовать после GREEN."""
    from core_api.services.admin_users import get_user_detail  # noqa: F401

    assert callable(get_user_detail)


def test_get_user_detail_user_not_found_error_symbol_absent() -> None:
    """3.2 — domain error UserNotFoundError должен экспортироваться из сервиса."""
    from core_api.services.admin_users import UserNotFoundError  # noqa: F401

    assert issubclass(UserNotFoundError, Exception)


def test_get_user_detail_happy_path_returns_merged_shape(db_session) -> None:
    """3.3 — detail объединяет user + profile + loyalty + active_orders_count."""
    from core_api.services.admin_users import get_user_detail

    user, _account = make_user_with_loyalty_and_profile(
        db_session,
        balance=500,
        status=UserStatus.ACTIVE,
        display_name="Alice",
        preferred_language="en",
    )
    # 5 loyalty транзакций
    seed_n_transactions(
        db_session,
        user=user,
        count=5,
        type=LoyaltyTransactionType.ACCRUAL,
        amount=100,
    )
    # 2 active + 3 completed orders
    seed_orders_across_statuses(
        db_session,
        user=user,
        counts={
            (OrderStatus.PREPARING, OrderType.PICKUP): 1,
            (OrderStatus.PAID, OrderType.PICKUP): 1,
            (OrderStatus.COMPLETED, OrderType.PICKUP): 3,
        },
    )
    db_session.commit()

    result = get_user_detail(db=db_session, user_id=user.id)

    assert result.status == "active"
    assert result.display_name == "Alice"
    assert result.language == "en"
    assert result.loyalty_balance == 500
    assert result.active_orders_count == 2
    assert len(result.loyalty_transactions) == 5


def test_get_user_detail_returns_last_20_loyalty_transactions_desc(db_session) -> None:
    """3.4 — последние 20 loyalty транзакций, DESC по created_at."""
    from core_api.services.admin_users import get_user_detail

    user, _ = make_user_with_loyalty_and_profile(
        db_session, balance=0, status=UserStatus.ACTIVE, display_name="U"
    )
    seeded = seed_n_transactions(
        db_session,
        user=user,
        count=25,
        type=LoyaltyTransactionType.ACCRUAL,
        amount=10,
    )
    db_session.commit()

    result = get_user_detail(db=db_session, user_id=user.id)

    assert len(result.loyalty_transactions) == 20
    # DESC по created_at
    created_ats = [tx.created_at for tx in result.loyalty_transactions]
    assert created_ats == sorted(created_ats, reverse=True)
    # Это именно последние 20 вставленных
    expected_last_20_ids = set(seeded.ids[-20:])
    returned_ids = {tx.id for tx in result.loyalty_transactions}
    assert returned_ids == expected_last_20_ids


def test_get_user_detail_tombstone_raises_user_not_found(db_session) -> None:
    """3.5 — tombstoned user (deleted_at IS NOT NULL) → UserNotFoundError (INV-013)."""
    from core_api.services.admin_users import UserNotFoundError, get_user_detail

    user = make_user_with_profile(
        db_session,
        status=UserStatus.ACTIVE,
        display_name="T",
        deleted_at=datetime.now(tz=UTC),
    )
    db_session.commit()

    with pytest.raises(UserNotFoundError):
        get_user_detail(db=db_session, user_id=user.id)


def test_get_user_detail_unknown_id_raises_user_not_found(db_session) -> None:
    """3.6 — несуществующий id → UserNotFoundError."""
    from core_api.services.admin_users import UserNotFoundError, get_user_detail

    with pytest.raises(UserNotFoundError):
        get_user_detail(db=db_session, user_id=uuid.uuid4())


def test_get_user_detail_active_orders_count_excludes_completed_and_cancelled(
    db_session,
) -> None:
    """3.7 — active_orders_count = заказы NOT IN (COMPLETED, CANCELLED)."""
    from core_api.services.admin_users import get_user_detail

    user = make_user_with_profile(
        db_session, status=UserStatus.ACTIVE, display_name="U"
    )
    seed_orders_across_statuses(
        db_session,
        user=user,
        counts={
            (OrderStatus.CREATED, OrderType.PICKUP): 1,
            (OrderStatus.PAID, OrderType.PICKUP): 1,
            (OrderStatus.PREPARING, OrderType.PICKUP): 1,
            (OrderStatus.READY, OrderType.PICKUP): 1,
            (OrderStatus.IN_DELIVERY, OrderType.DELIVERY): 1,
            (OrderStatus.COMPLETED, OrderType.PICKUP): 1,
            (OrderStatus.CANCELLED, OrderType.PICKUP): 1,
        },
    )
    db_session.commit()

    result = get_user_detail(db=db_session, user_id=user.id)

    # CREATED + PAID + PREPARING + READY + IN_DELIVERY = 5
    assert result.active_orders_count == 5


def test_get_user_detail_response_has_no_phone_or_phone_hash_or_deleted_at_fields(
    db_session,
) -> None:
    """3.8 — UserDetailResponse НЕ раскрывает phone / phone_hash / deleted_at."""
    from core_api.services.admin_users import get_user_detail

    user, _ = make_user_with_loyalty_and_profile(
        db_session, balance=10, status=UserStatus.ACTIVE, display_name="U"
    )
    db_session.commit()

    result = get_user_detail(db=db_session, user_id=user.id)

    dumped = result.model_dump()
    assert "phone" not in dumped
    assert "phone_hash" not in dumped
    assert "deleted_at" not in dumped


def test_loyalty_transaction_item_omits_user_id_and_order_id(db_session) -> None:
    """3.9 — LoyaltyTransactionItem.model_fields не содержит user_id/order_id."""
    from core_api.schemas.admin_users import LoyaltyTransactionItem

    fields = set(LoyaltyTransactionItem.model_fields.keys())
    assert "user_id" not in fields
    assert "order_id" not in fields
    # Но должны быть базовые поля
    for required in {"id", "type", "amount", "balance_after", "created_at"}:
        assert required in fields, f"LoyaltyTransactionItem должен содержать {required}"


# ===========================================================================
# 7.13, 7.14 — route-level RBAC for GET /api/v1/admin/users/{user_id}
# ===========================================================================


def test_admin_users_detail_rejects_no_auth(admin_users_client) -> None:
    """7.13 — GET /api/v1/admin/users/<uuid> без headers → 401."""
    response = admin_users_client.get(f"/api/v1/admin/users/{uuid.uuid4()}")
    assert response.status_code == 401


@pytest.mark.parametrize(
    "role_fixture",
    ["barista_headers", "courier_headers", "customer_headers"],
)
def test_admin_users_detail_rejects_non_admin_roles(
    admin_users_client, request, role_fixture
) -> None:
    """7.14 — GET /api/v1/admin/users/<uuid> для не-ADMIN → 403 (INV-010)."""
    headers = request.getfixturevalue(role_fixture)
    response = admin_users_client.get(
        f"/api/v1/admin/users/{uuid.uuid4()}", headers=headers
    )
    assert response.status_code == 403


def test_admin_users_detail_route_registered() -> None:
    """GET /api/v1/admin/users/{user_id} регистрируется ровно один раз (GREEN target)."""
    matches = []
    for route in app.routes:
        methods = getattr(route, "methods", set()) or set()
        path = getattr(route, "path", "")
        if "GET" in methods and path == "/api/v1/admin/users/{user_id}":
            matches.append(route)

    assert len(matches) == 1, (
        f"Ожидался ровно 1 GET /api/v1/admin/users/{{user_id}}, нашли {len(matches)}"
    )
