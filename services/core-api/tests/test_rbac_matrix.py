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
