"""Интеграционные тесты auth endpoints.

Требуют запущенных PostgreSQL и Redis.
Запуск: pytest services/core-api/tests/test_auth_endpoints.py -v
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from core_api.routers.auth import send_code
from core_api.schemas.auth import SendCodeRequest
from core_api.utils.crypto import hash_phone


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

    # GRACE-LDD: asserts OTP generation marker and INV-013 public response/log redaction.
    def test_success_does_not_return_phone_hash_and_logs_redacted(self, r, grace_logs) -> None:
        phone = "+79991234567"
        expected_hash = hash_phone(phone)
        db = MagicMock()

        with (
            patch("core_api.routers.auth.UserService") as user_service_cls,
            patch("core_api.services.otp.secrets.randbelow", return_value=123456),
            patch("celery.Celery") as celery_cls,
        ):
            user_service = user_service_cls.return_value
            user_service.get_user_status.return_value = None
            user_service.get_or_create_user.return_value = MagicMock()

            response = send_code(SendCodeRequest(phone=phone), db=db, r=r)

        assert response == {"message": "OTP sent"}
        celery_cls.return_value.send_task.assert_called_once()
        assert celery_cls.return_value.send_task.call_args.kwargs["args"][0] == expected_hash

        grace_logs.assert_trajectory(("auth.otp_request", "BLOCK_OTP_GEN"))
        assert grace_logs.beliefs(status="MISMATCH") == []
        captured = "\n".join(grace_logs.lines)
        assert phone not in captured
        assert expected_hash not in captured
        assert "123456" not in captured


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
