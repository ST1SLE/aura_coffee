"""RED: тесты RBAC-матрицы для admin-orders-api (PDD §4.5, INV-010).

Проверяем, что GREEN добавит строки ROUTE_MATRIX для /api/v1/admin/orders*
с ролями {ADMIN, BARISTA} и НЕ добавит их в PUBLIC_ROUTES. Также сторожим
существующие customer-scoped маршруты — они НЕ должны измениться.
"""
from __future__ import annotations

import inspect

from core_api.rbac_matrix import (
    ADMIN,
    BARISTA,
    CUSTOMER,
    PUBLIC_ROUTES,
    ROUTE_MATRIX,
)


def test_admin_orders_list_matrix_row_allows_admin_and_barista_only() -> None:
    """6.1 — ROUTE_MATRIX[('GET', '/api/v1/admin/orders')] == {ADMIN, BARISTA}."""
    key = ("GET", "/api/v1/admin/orders")
    assert key in ROUTE_MATRIX, f"Маршрут {key} отсутствует в ROUTE_MATRIX"
    assert ROUTE_MATRIX[key] == {ADMIN, BARISTA}, (
        f"Маршрут {key} должен разрешать только ADMIN+BARISTA, "
        f"получено: {ROUTE_MATRIX[key]}"
    )


def test_admin_orders_detail_matrix_row_allows_admin_and_barista_only() -> None:
    """6.2 — ROUTE_MATRIX[('GET', '/api/v1/admin/orders/{order_id}')] == {ADMIN, BARISTA}."""
    key = ("GET", "/api/v1/admin/orders/{order_id}")
    assert key in ROUTE_MATRIX, f"Маршрут {key} отсутствует в ROUTE_MATRIX"
    assert ROUTE_MATRIX[key] == {ADMIN, BARISTA}, (
        f"Маршрут {key} должен разрешать только ADMIN+BARISTA, "
        f"получено: {ROUTE_MATRIX[key]}"
    )


def test_admin_orders_routes_not_public() -> None:
    """6.3 — admin-orders маршруты не должны быть в PUBLIC_ROUTES."""
    for key in (
        ("GET", "/api/v1/admin/orders"),
        ("GET", "/api/v1/admin/orders/{order_id}"),
    ):
        assert key not in PUBLIC_ROUTES, (
            f"Маршрут {key} не должен быть публичным"
        )


def test_existing_customer_list_orders_signature_has_user_id() -> None:
    """6.4 — list_orders (customer-scoped) не должен потерять user_id параметр."""
    from core_api.services.order_history import list_orders

    params = inspect.signature(list_orders).parameters
    assert "user_id" in params, (
        "Customer-scoped list_orders должен по-прежнему принимать user_id"
    )


def test_existing_customer_order_detail_row_untouched() -> None:
    """6.5 — матрица для GET /api/v1/orders/{order_id} всё ещё разрешает CUSTOMER."""
    key = ("GET", "/api/v1/orders/{order_id}")
    assert key in ROUTE_MATRIX, f"Маршрут {key} исчез из ROUTE_MATRIX"
    assert CUSTOMER in ROUTE_MATRIX[key], (
        f"Customer-scoped detail route {key} должен оставаться разрешённым для CUSTOMER"
    )
