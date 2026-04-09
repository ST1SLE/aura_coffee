"""Интеграционные тесты auth endpoints.

Требуют запущенных PostgreSQL и Redis.
Запуск: pytest services/core-api/tests/test_auth_endpoints.py -v
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """TestClient с мокнутыми зависимостями БД и Redis."""
    from core_api.main import app

    return TestClient(app)


@pytest.fixture
def mock_deps():
    """Мок всех внешних зависимостей для изолированных тестов."""
    mock_db = MagicMock()
    mock_redis = MagicMock()

    with (
        patch("core_api.routers.auth.get_db", return_value=iter([mock_db])),
        patch("core_api.routers.auth.get_redis", return_value=iter([mock_redis])),
    ):
        yield mock_db, mock_redis


class TestSendCode:
    def test_invalid_phone(self, client: TestClient) -> None:
        with (
            patch("core_api.routers.auth.get_db", return_value=iter([MagicMock()])),
            patch("core_api.routers.auth.get_redis", return_value=iter([MagicMock()])),
        ):
            response = client.post("/api/v1/auth/send-code", json={"phone": "123"})
            assert response.status_code == 422


class TestVerifyCode:
    def test_invalid_phone(self, client: TestClient) -> None:
        with (
            patch("core_api.routers.auth.get_db", return_value=iter([MagicMock()])),
            patch("core_api.routers.auth.get_redis", return_value=iter([MagicMock()])),
        ):
            response = client.post(
                "/api/v1/auth/verify-code",
                json={"phone": "bad", "code": "123456"},
            )
            assert response.status_code == 422


class TestRefresh:
    def test_invalid_token(self, client: TestClient) -> None:
        mock_redis = MagicMock()
        mock_redis.get.return_value = None

        with patch("core_api.routers.auth.get_redis", return_value=iter([mock_redis])):
            response = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": "nonexistent"},
            )
            assert response.status_code == 401


class TestLogout:
    def test_unauthenticated(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": "test"},
        )
        assert response.status_code in (401, 403)
