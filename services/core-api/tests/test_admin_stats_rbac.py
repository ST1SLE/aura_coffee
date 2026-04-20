"""RED: тесты RBAC-матрицы и роутера GET /api/v1/admin/stats (dashboard-api-red).

- Матричные тесты падают KeyError до GREEN.
- Роутерные тесты падают 403/401 (middleware RBACMiddleware отклоняет
  неизвестный путь как default-deny) — в GREEN роутер регистрируется и
  422 начинает приходить для range=bogus.
"""
from __future__ import annotations


# ===========================================================================
# 4.x — RBAC matrix + router contract tests
# ===========================================================================


def test_admin_stats_matrix_row_is_admin_only() -> None:
    """4.1 — ROUTE_MATRIX[('GET','/api/v1/admin/stats')] == {ADMIN}."""
    from core_api.rbac_matrix import ADMIN, ROUTE_MATRIX

    assert ROUTE_MATRIX[("GET", "/api/v1/admin/stats")] == {ADMIN}


def test_admin_stats_matrix_row_excludes_barista_courier_customer() -> None:
    """4.2 — BARISTA, COURIER, CUSTOMER отсутствуют в row stats."""
    from core_api.rbac_matrix import BARISTA, COURIER, CUSTOMER, ROUTE_MATRIX

    roles = ROUTE_MATRIX[("GET", "/api/v1/admin/stats")]
    assert BARISTA not in roles
    assert COURIER not in roles
    assert CUSTOMER not in roles


def test_admin_stats_route_not_public() -> None:
    """4.3 — маршрут /admin/stats не должен быть в PUBLIC_ROUTES."""
    from core_api.rbac_matrix import PUBLIC_ROUTES

    assert ("GET", "/api/v1/admin/stats") not in PUBLIC_ROUTES


def test_admin_stats_requires_authorization(client) -> None:
    """4.4 — без заголовка Authorization → 401."""
    response = client.get("/api/v1/admin/stats")
    assert response.status_code == 401


def test_admin_stats_rejects_barista(client, barista_headers) -> None:
    """4.5 — barista JWT → 403."""
    response = client.get("/api/v1/admin/stats", headers=barista_headers)
    assert response.status_code == 403


def test_admin_stats_rejects_courier(client, courier_headers) -> None:
    """4.6 — courier JWT → 403."""
    response = client.get("/api/v1/admin/stats", headers=courier_headers)
    assert response.status_code == 403


def test_admin_stats_rejects_customer(client, customer_headers) -> None:
    """4.7 — customer JWT → 403."""
    response = client.get("/api/v1/admin/stats", headers=customer_headers)
    assert response.status_code == 403


def test_admin_stats_rejects_unknown_range(client, admin_headers) -> None:
    """4.8 — admin + range=bogus → 422 (после GREEN).

    В RED-фазе маршрут не зарегистрирован: RBACMiddleware вернёт 403 по
    default-deny (unknown route для admin-префикса). Это нормально —
    тест всё равно будет "failing" против ожидаемого 422 и флипнется в
    GREEN, когда FastAPI'евская валидация Literal вернёт 422.
    """
    response = client.get(
        "/api/v1/admin/stats",
        params={"range": "bogus"},
        headers=admin_headers,
    )
    assert response.status_code == 422
