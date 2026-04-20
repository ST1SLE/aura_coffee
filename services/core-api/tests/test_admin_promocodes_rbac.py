"""RED: RBAC-матрица для admin-promocodes-api (PDD §6.6, INV-010, INV-011).

Все шесть эндпоинтов /api/v1/admin/promocodes/* должны быть ADMIN-only.
Barista/courier/customer → 403. Никакие из них не в PUBLIC_ROUTES.
DELETE эндпоинта не должно быть (archive-style, §6.6).
"""
from __future__ import annotations

import inspect

from core_api.main import app
from core_api.rbac_matrix import ADMIN, PUBLIC_ROUTES, ROUTE_MATRIX


ADMIN_PROMO_ROWS = [
    ("POST", "/api/v1/admin/promocodes"),
    ("GET", "/api/v1/admin/promocodes"),
    ("GET", "/api/v1/admin/promocodes/{promocode_id}"),
    ("PATCH", "/api/v1/admin/promocodes/{promocode_id}"),
    ("POST", "/api/v1/admin/promocodes/{promocode_id}/activate"),
    ("POST", "/api/v1/admin/promocodes/{promocode_id}/deactivate"),
]


def test_rbac_matrix_rows_admin_only() -> None:
    """10.1 — все 6 строк ROUTE_MATRIX с set ровно {ADMIN}."""
    for key in ADMIN_PROMO_ROWS:
        assert key in ROUTE_MATRIX, f"Маршрут {key} отсутствует в ROUTE_MATRIX"
        assert ROUTE_MATRIX[key] == {ADMIN}, (
            f"Маршрут {key} должен разрешать только ADMIN, получено: {ROUTE_MATRIX[key]}"
        )


def test_rbac_none_of_six_routes_public() -> None:
    """10.2 — ни один из шести не в PUBLIC_ROUTES."""
    for key in ADMIN_PROMO_ROWS:
        assert key not in PUBLIC_ROUTES, f"Маршрут {key} не должен быть публичным"


def test_no_delete_route_registered() -> None:
    """10.3 — DELETE /api/v1/admin/promocodes/... не должно существовать."""
    for route in app.routes:
        methods = getattr(route, "methods", set()) or set()
        path = getattr(route, "path", "")
        if "DELETE" in methods and path.startswith("/api/v1/admin/promocodes"):
            raise AssertionError(
                f"Найден запрещённый DELETE-маршрут: {path} (archive-style, §6.6)"
            )


def test_validators_promocode_module_unchanged_signature() -> None:
    """10.4 — checkout-side validator не должен измениться по сигнатуре."""
    from core_api.services.validators.promocode import validate_promocode

    params = list(inspect.signature(validate_promocode).parameters)
    assert params == ["code", "user_id", "subtotal", "db_session"], (
        f"Сигнатура validate_promocode изменилась: {params}"
    )
