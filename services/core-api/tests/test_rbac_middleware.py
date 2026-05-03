"""Тесты RBAC middleware.

Запуск: pytest services/core-api/tests/test_rbac_middleware.py -v
"""

import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from core_api.main import app
from core_api.services.auth import AuthService

client = TestClient(app)

TEST_SECRET = "aura-coffee-tests-jwt-secret-0001"


def _make_token(role: str, *, expired: bool = False) -> str:
    """Создание JWT-токена для тестов."""
    mock_attrs = {
        "jwt_secret_key": TEST_SECRET,
        "jwt_algorithm": "HS256",
        "access_token_ttl": -1 if expired else 900,
    }
    with patch("core_api.services.auth.settings") as mock_settings:
        for k, v in mock_attrs.items():
            setattr(mock_settings, k, v)
        svc = AuthService.__new__(AuthService)
        return svc.create_access_token(uuid.uuid4(), role)


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestValidRoleAccess:
    @patch("core_api.services.auth.settings")
    def test_customer_accesses_profile(self, mock_settings) -> None:
        mock_settings.jwt_secret_key = TEST_SECRET
        mock_settings.jwt_algorithm = "HS256"
        token = _make_token("customer")
        with patch("core_api.routers.profile.get_profile", return_value=None):
            response = client.get("/api/v1/profile", headers=_auth_header(token))
        # 404 — профиль не найден, но middleware пропустил
        assert response.status_code == 404


class TestInvalidRole:
    @patch("core_api.services.auth.settings")
    def test_admin_denied_from_customer_endpoint(self, mock_settings) -> None:
        mock_settings.jwt_secret_key = TEST_SECRET
        mock_settings.jwt_algorithm = "HS256"
        token = _make_token("admin")
        response = client.get("/api/v1/profile", headers=_auth_header(token))
        assert response.status_code == 403
        assert response.json()["detail"] == "Insufficient permissions"


class TestMissingToken:
    def test_no_auth_header_on_protected_route(self) -> None:
        response = client.get("/api/v1/profile")
        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"


class TestExpiredToken:
    @patch("core_api.services.auth.settings")
    def test_expired_jwt_returns_401(self, mock_settings) -> None:
        mock_settings.jwt_secret_key = TEST_SECRET
        mock_settings.jwt_algorithm = "HS256"
        token = _make_token("customer", expired=True)
        response = client.get("/api/v1/profile", headers=_auth_header(token))
        assert response.status_code == 401


class TestOptionsPassthrough:
    def test_options_request_bypasses_auth(self) -> None:
        response = client.options("/api/v1/profile")
        # Не 401/403 — middleware пропустил OPTIONS
        assert response.status_code != 401
        assert response.status_code != 403


class TestDefaultDeny:
    @patch("core_api.services.auth.settings")
    def test_unlisted_route_denied_with_valid_token(self, mock_settings) -> None:
        mock_settings.jwt_secret_key = TEST_SECRET
        mock_settings.jwt_algorithm = "HS256"
        token = _make_token("customer")
        response = client.get("/api/v1/nonexistent", headers=_auth_header(token))
        assert response.status_code == 403
        assert response.json()["detail"] == "Insufficient permissions"

    def test_unlisted_route_without_auth(self) -> None:
        response = client.get("/api/v1/nonexistent")
        assert response.status_code == 401


class TestPublicRoutes:
    def test_health_no_auth_required(self) -> None:
        response = client.get("/health")
        assert response.status_code == 200

    def test_send_code_no_auth_required(self) -> None:
        # Ожидаем 422 (тело не передано), а не 401
        response = client.post("/api/v1/auth/send-code")
        assert response.status_code != 401
