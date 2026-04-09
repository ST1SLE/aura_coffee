"""Тест: verify-code возвращает 409 когда OTP в статусе CREATED.

Изолированный unit-тест — не требует PostgreSQL и Redis.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from core_api.services.otp import VerifyResponse, VerifyResult


@pytest.fixture
def client():
    from core_api.main import app

    return TestClient(app)


def _mock_verify_returning(result: VerifyResult, remaining: int | None = None):
    """Создаёт мок OTPService.verify_otp с заданным результатом."""
    mock_otp_svc = MagicMock()
    mock_otp_svc.verify_otp.return_value = VerifyResponse(
        result=result, remaining_attempts=remaining
    )
    return mock_otp_svc


class TestVerifyCode409:
    """HTTP 409 при попытке верификации до доставки SMS."""

    def test_returns_409_when_otp_status_created(self, client: TestClient) -> None:
        mock_otp_svc = _mock_verify_returning(VerifyResult.INVALID_STATUS)

        with (
            patch("core_api.routers.auth.get_db", return_value=iter([MagicMock()])),
            patch("core_api.routers.auth.get_redis", return_value=iter([MagicMock()])),
            patch(
                "core_api.routers.auth.OTPService", return_value=mock_otp_svc
            ),
        ):
            response = client.post(
                "/api/v1/auth/verify-code",
                json={"phone": "+79991234567", "code": "123456"},
            )

        assert response.status_code == 409
        assert response.json()["detail"] == "OTP not yet delivered"

    def test_409_not_returned_for_sent_otp(self, client: TestClient) -> None:
        """Когда OTP в статусе SENT и код неверный — 401, не 409."""
        mock_otp_svc = _mock_verify_returning(VerifyResult.WRONG_CODE, remaining=4)

        with (
            patch("core_api.routers.auth.get_db", return_value=iter([MagicMock()])),
            patch("core_api.routers.auth.get_redis", return_value=iter([MagicMock()])),
            patch(
                "core_api.routers.auth.OTPService", return_value=mock_otp_svc
            ),
        ):
            response = client.post(
                "/api/v1/auth/verify-code",
                json={"phone": "+79991234567", "code": "000000"},
            )

        assert response.status_code == 401
        assert "Wrong code" in response.json()["detail"]

    def test_409_documented_in_openapi_schema(self, client: TestClient) -> None:
        """409 задокументирован в OpenAPI schema endpoint'а."""
        response = client.get("/openapi.json")
        schema = response.json()
        verify_responses = schema["paths"]["/api/v1/auth/verify-code"]["post"][
            "responses"
        ]
        assert "409" in verify_responses
