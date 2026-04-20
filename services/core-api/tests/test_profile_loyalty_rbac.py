"""RED: RBAC-матрица + end-to-end isolation для customer-loyalty-api (INV-010)."""
from __future__ import annotations

from unittest.mock import patch

import fakeredis
import pytest
from fastapi.testclient import TestClient

from core_api.main import app
from core_api.rbac_matrix import (
    ADMIN,
    BARISTA,
    COURIER,
    CUSTOMER,
    PUBLIC_ROUTES,
    ROUTE_MATRIX,
)
from shared.enums import LoyaltyTransactionType
from tests._factories.loyalty import (
    make_user_with_loyalty,
    seed_n_transactions,
)
from tests._helpers.jwt import auth_headers_for_user


# ===========================================================================
# 8.x — RBAC matrix row tests
# ===========================================================================


def test_balance_matrix_row_allows_customer_only() -> None:
    """8.1 — ROUTE_MATRIX[('GET', '/api/v1/profile/loyalty')] == {CUSTOMER}."""
    key = ("GET", "/api/v1/profile/loyalty")
    assert key in ROUTE_MATRIX, f"Маршрут {key} отсутствует в ROUTE_MATRIX"
    assert ROUTE_MATRIX[key] == {CUSTOMER}


def test_transactions_matrix_row_allows_customer_only() -> None:
    """8.2 — ROUTE_MATRIX[('GET', '/api/v1/profile/loyalty/transactions')] == {CUSTOMER}."""
    key = ("GET", "/api/v1/profile/loyalty/transactions")
    assert key in ROUTE_MATRIX, f"Маршрут {key} отсутствует в ROUTE_MATRIX"
    assert ROUTE_MATRIX[key] == {CUSTOMER}


def test_loyalty_routes_not_in_public_routes() -> None:
    """8.3 — оба маршрута не в PUBLIC_ROUTES."""
    for key in (
        ("GET", "/api/v1/profile/loyalty"),
        ("GET", "/api/v1/profile/loyalty/transactions"),
    ):
        assert key not in PUBLIC_ROUTES


def test_existing_profile_get_matrix_row_untouched() -> None:
    """8.4 — GET /api/v1/profile всё ещё разрешает CUSTOMER."""
    key = ("GET", "/api/v1/profile")
    assert key in ROUTE_MATRIX
    assert CUSTOMER in ROUTE_MATRIX[key]


def test_balance_rejects_admin_barista_courier_rbac_matrix() -> None:
    """8.5 — balance-маршрут не содержит ADMIN/BARISTA/COURIER."""
    key = ("GET", "/api/v1/profile/loyalty")
    roles = ROUTE_MATRIX.get(key, set())
    assert ADMIN not in roles
    assert BARISTA not in roles
    assert COURIER not in roles


# ===========================================================================
# 7.x — end-to-end isolation test (user A не видит транзакции user B)
# ===========================================================================


@pytest.fixture
def loyalty_client(db_session):
    fake_redis = fakeredis.FakeRedis()

    def _override_redis():
        yield fake_redis

    def _override_db():
        yield db_session

    with (
        patch("core_api.deps.redis.get_redis", side_effect=_override_redis),
        patch("core_api.deps.database.get_session", side_effect=_override_db),
        patch("core_api.deps.database.get_db", side_effect=_override_db),
    ):
        with TestClient(app) as c:
            yield c
    fake_redis.flushall()


def test_user_A_cannot_see_user_B_transactions(loyalty_client, db_session) -> None:
    """7.1 — customer JWT user A возвращает только транзакции user A (INV-010)."""
    user_a, _ = make_user_with_loyalty(db_session, balance=0)
    user_b, _ = make_user_with_loyalty(db_session, balance=0)
    a_seed = seed_n_transactions(
        db_session, user=user_a, count=2, type=LoyaltyTransactionType.ACCRUAL
    )
    b_seed = seed_n_transactions(
        db_session, user=user_b, count=3, type=LoyaltyTransactionType.ACCRUAL
    )
    db_session.commit()

    headers = auth_headers_for_user(user_a.id, role="customer")
    response = loyalty_client.get(
        "/api/v1/profile/loyalty/transactions", headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    returned_ids = {item["id"] for item in body["items"]}
    a_ids = {str(i) for i in a_seed.ids}
    b_ids = {str(i) for i in b_seed.ids}
    assert returned_ids.issubset(a_ids)
    assert returned_ids.isdisjoint(b_ids)
