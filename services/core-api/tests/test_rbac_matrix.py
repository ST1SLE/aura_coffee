"""Тесты логики сопоставления маршрутов в RBAC middleware.

Запуск: pytest services/core-api/tests/test_rbac_matrix.py -v
"""

from core_api.middleware.rbac import _compile_pattern, _is_public, _match_route


class TestCompilePattern:
    def test_exact_path(self) -> None:
        pattern = _compile_pattern("/api/v1/profile")
        assert pattern.match("/api/v1/profile")
        assert not pattern.match("/api/v1/profile/extra")

    def test_param_placeholder(self) -> None:
        pattern = _compile_pattern("/api/v1/menu/{item_id}")
        assert pattern.match("/api/v1/menu/123")
        assert pattern.match("/api/v1/menu/abc-def")
        assert not pattern.match("/api/v1/menu/123/edit")
        assert not pattern.match("/api/v1/menu/")


class TestMatchRoute:
    def test_exact_match(self) -> None:
        matrix = {
            ("GET", "/api/v1/profile"): {"customer"},
        }
        assert _match_route("GET", "/api/v1/profile", matrix) == {"customer"}

    def test_no_match_returns_none(self) -> None:
        matrix = {
            ("GET", "/api/v1/profile"): {"customer"},
        }
        assert _match_route("POST", "/api/v1/profile", matrix) is None
        assert _match_route("GET", "/api/v1/other", matrix) is None

    def test_parameterized_match(self) -> None:
        matrix = {
            ("GET", "/api/v1/menu/{item_id}"): {"admin"},
        }
        roles = _match_route("GET", "/api/v1/menu/some-uuid", matrix)
        assert roles == {"admin"}

    def test_longest_prefix_precedence(self) -> None:
        matrix = {
            ("GET", "/api/v1/menu"): {"customer", "admin"},
            ("GET", "/api/v1/menu/{item_id}"): {"admin"},
        }
        # /api/v1/menu — точное совпадение с коротким паттерном
        assert _match_route("GET", "/api/v1/menu", matrix) == {"customer", "admin"}
        # /api/v1/menu/123 — совпадает с более длинным паттерном
        assert _match_route("GET", "/api/v1/menu/123", matrix) == {"admin"}

    def test_method_mismatch(self) -> None:
        matrix = {
            ("POST", "/api/v1/orders"): {"customer"},
        }
        assert _match_route("GET", "/api/v1/orders", matrix) is None


class TestIsPublic:
    def test_public_route_matches(self) -> None:
        assert _is_public("GET", "/health")

    def test_protected_route_not_public(self) -> None:
        assert not _is_public("GET", "/api/v1/profile")

    def test_method_matters(self) -> None:
        assert not _is_public("GET", "/api/v1/auth/send-code")
        assert _is_public("POST", "/api/v1/auth/send-code")


# ===========================================================================
# 9.x — Корзина: матрица RBAC (cart-redis-pricing-red)
# ===========================================================================

_CART_ROUTES = [
    ("GET",    "/api/v1/cart"),
    ("DELETE", "/api/v1/cart"),
    ("POST",   "/api/v1/cart/items"),
    ("PATCH",  "/api/v1/cart/items/{line_id}"),
    ("DELETE", "/api/v1/cart/items/{line_id}"),
]


class TestCartRbac:
    """9.1 Каждый маршрут корзины должен быть в ROUTE_MATRIX с ролью CUSTOMER."""

    def test_cart_routes_are_in_route_matrix(self) -> None:
        from core_api.rbac_matrix import ROUTE_MATRIX, CUSTOMER

        for method, pattern in _CART_ROUTES:
            assert (method, pattern) in ROUTE_MATRIX, (
                f"Маршрут ({method}, {pattern!r}) отсутствует в ROUTE_MATRIX"
            )
            roles = ROUTE_MATRIX[(method, pattern)]
            assert roles == {CUSTOMER}, (
                f"Маршрут ({method}, {pattern!r}) должен разрешать только CUSTOMER, "
                f"получено: {roles}"
            )

    def test_cart_routes_absent_from_public_routes(self) -> None:
        """9.2 Маршруты корзины не должны быть публичными."""
        from core_api.rbac_matrix import PUBLIC_ROUTES

        for method, pattern in _CART_ROUTES:
            assert (method, pattern) not in PUBLIC_ROUTES, (
                f"Маршрут ({method}, {pattern!r}) не должен быть в PUBLIC_ROUTES"
            )


# ===========================================================================
# Yandex Maps proxy (PDD §7.3, §8.3) — только CUSTOMER, не публичный
# ===========================================================================

_YANDEX_MAPS_ROUTES = [
    ("GET", "/api/v1/maps/suggest"),
    ("GET", "/api/v1/maps/geocode"),
]


class TestYandexMapsRbac:
    def test_yandex_maps_routes_registered_for_customer_only(self) -> None:
        from core_api.rbac_matrix import CUSTOMER, PUBLIC_ROUTES, ROUTE_MATRIX

        for method, pattern in _YANDEX_MAPS_ROUTES:
            assert (method, pattern) in ROUTE_MATRIX, (
                f"Маршрут ({method}, {pattern!r}) отсутствует в ROUTE_MATRIX"
            )
            assert ROUTE_MATRIX[(method, pattern)] == {CUSTOMER}, (
                f"Маршрут ({method}, {pattern!r}) должен разрешать только CUSTOMER"
            )
            assert (method, pattern) not in PUBLIC_ROUTES, (
                f"Маршрут ({method}, {pattern!r}) не должен быть в PUBLIC_ROUTES"
            )
