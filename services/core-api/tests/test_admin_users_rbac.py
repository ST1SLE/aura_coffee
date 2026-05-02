"""RED: тесты RBAC-матрицы для admin-users-api (PDD §6.5, INV-010).

Проверяем, что GREEN добавит строки ROUTE_MATRIX под /api/v1/admin/users/*
c ролью {ADMIN} и НЕ добавит их в PUBLIC_ROUTES. Заодно сторожим
существующие customer-scoped /api/v1/profile/* маршруты — они не должны
расшириться ролями.

Route-level 401/403 тесты для GET /api/v1/admin/users и
GET /api/v1/admin/users/{user_id} лежат в test_admin_users_list.py
и test_admin_users_detail.py соответственно (7.9–7.14).
"""
from __future__ import annotations

from core_api.rbac_matrix import (
    ADMIN,
    CUSTOMER,
    PUBLIC_ROUTES,
    ROUTE_MATRIX,
)


ADMIN_USERS_ROUTES = [
    ("GET", "/api/v1/admin/users"),
    ("GET", "/api/v1/admin/users/{user_id}"),
    ("POST", "/api/v1/admin/users/{user_id}/block"),
    ("POST", "/api/v1/admin/users/{user_id}/unblock"),
    ("DELETE", "/api/v1/admin/users/{user_id}"),
    ("POST", "/api/v1/admin/users/{user_id}/loyalty/adjust"),
]


def test_admin_users_list_row_is_admin_only() -> None:
    """7.1 — ROUTE_MATRIX[('GET', '/api/v1/admin/users')] == {ADMIN}."""
    assert ROUTE_MATRIX[("GET", "/api/v1/admin/users")] == {ADMIN}


def test_admin_users_detail_row_is_admin_only() -> None:
    """7.2 — ROUTE_MATRIX[('GET', '/api/v1/admin/users/{user_id}')] == {ADMIN}."""
    assert ROUTE_MATRIX[("GET", "/api/v1/admin/users/{user_id}")] == {ADMIN}


def test_admin_users_block_row_is_admin_only() -> None:
    """7.3 — ROUTE_MATRIX[('POST', '/api/v1/admin/users/{user_id}/block')] == {ADMIN}."""
    assert ROUTE_MATRIX[("POST", "/api/v1/admin/users/{user_id}/block")] == {ADMIN}


def test_admin_users_unblock_row_is_admin_only() -> None:
    """7.4 — ROUTE_MATRIX[('POST', '/api/v1/admin/users/{user_id}/unblock')] == {ADMIN}."""
    assert ROUTE_MATRIX[("POST", "/api/v1/admin/users/{user_id}/unblock")] == {ADMIN}


def test_admin_users_delete_row_is_admin_only() -> None:
    """7.4a — ROUTE_MATRIX[('DELETE', '/api/v1/admin/users/{user_id}')] == {ADMIN}."""
    assert ROUTE_MATRIX[("DELETE", "/api/v1/admin/users/{user_id}")] == {ADMIN}


def test_admin_users_loyalty_adjust_row_is_admin_only() -> None:
    """7.5 — ROUTE_MATRIX[('POST', '/api/v1/admin/users/{user_id}/loyalty/adjust')] == {ADMIN}."""
    assert ROUTE_MATRIX[
        ("POST", "/api/v1/admin/users/{user_id}/loyalty/adjust")
    ] == {ADMIN}


def test_admin_users_routes_not_public() -> None:
    """7.6 — ни один admin-users маршрут не должен быть в PUBLIC_ROUTES."""
    for key in ADMIN_USERS_ROUTES:
        assert key not in PUBLIC_ROUTES, (
            f"Маршрут {key} не должен быть публичным"
        )


def test_existing_customer_profile_row_untouched() -> None:
    """7.7 — GET /api/v1/profile остаётся {CUSTOMER}."""
    key = ("GET", "/api/v1/profile")
    assert key in ROUTE_MATRIX
    assert ROUTE_MATRIX[key] == {CUSTOMER}


def test_customer_profile_delete_row_is_customer_only() -> None:
    """7.7a — DELETE /api/v1/profile остаётся customer-only."""
    key = ("DELETE", "/api/v1/profile")
    assert key in ROUTE_MATRIX
    assert ROUTE_MATRIX[key] == {CUSTOMER}


def test_existing_customer_profile_loyalty_row_untouched() -> None:
    """7.8 — GET /api/v1/profile/loyalty остаётся {CUSTOMER}."""
    key = ("GET", "/api/v1/profile/loyalty")
    assert key in ROUTE_MATRIX
    assert ROUTE_MATRIX[key] == {CUSTOMER}
