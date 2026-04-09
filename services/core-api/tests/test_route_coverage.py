"""Тест покрытия маршрутов матрицей RBAC.

Каждый зарегистрированный маршрут FastAPI должен быть либо в ROUTE_MATRIX, либо в PUBLIC_ROUTES.
Запуск: pytest services/core-api/tests/test_route_coverage.py -v
"""

from core_api.main import app
from core_api.middleware.rbac import _compile_pattern
from core_api.rbac_matrix import PUBLIC_ROUTES, ROUTE_MATRIX


# Внутренние маршруты FastAPI — не подлежат RBAC
_INTERNAL_PREFIXES = ("/docs", "/redoc", "/openapi.json")


def _all_registered_routes() -> set[tuple[str, str]]:
    """Все маршруты FastAPI, исключая внутренние (docs, redoc, openapi)."""
    routes: set[tuple[str, str]] = set()
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            if route.path.startswith(_INTERNAL_PREFIXES):
                continue
            for method in route.methods:
                if method == "HEAD":
                    continue
                routes.add((method, route.path))
    return routes


def _is_covered(method: str, path: str) -> bool:
    """Проверка, покрыт ли маршрут матрицей или публичным списком."""
    all_rules = set(ROUTE_MATRIX.keys()) | PUBLIC_ROUTES
    for rule_method, rule_pattern in all_rules:
        if rule_method != method:
            continue
        if _compile_pattern(rule_pattern).match(path):
            return True
    return False


class TestRouteCoverage:
    def test_all_routes_covered(self) -> None:
        registered = _all_registered_routes()
        uncovered = {
            (m, p) for m, p in registered if not _is_covered(m, p)
        }
        assert uncovered == set(), (
            f"Маршруты не покрыты RBAC матрицей: {uncovered}. "
            "Добавьте их в ROUTE_MATRIX или PUBLIC_ROUTES."
        )
