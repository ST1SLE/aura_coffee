"""Интеграционные тесты auth endpoints.

Требуют запущенных PostgreSQL и Redis.
Запуск: pytest services/core-api/tests/test_auth_endpoints.py -v
"""

from unittest.mock import MagicMock, patch
import uuid

import pytest
from fastapi import HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

from core_api.deps.auth import get_current_user
from core_api.routers.auth import logout as logout_route
from core_api.routers.auth import refresh as refresh_route
from core_api.routers.auth import send_code, verify_code
from core_api.schemas.auth import RefreshRequest, SendCodeRequest, VerifyCodeRequest
from core_api.services.auth import AuthService
from core_api.services.otp import OTPService
from core_api.services.user import UserInfo
from core_api.utils.crypto import hash_phone
from shared.enums import OTPStatus, UserStatus
from shared.models.user import User


def _request_with_cookie(name: str | None = None, value: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if name is not None and value is not None:
        headers.append((b"cookie", f"{name}={value}".encode()))
    return Request({"type": "http", "headers": headers})


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

    # GRACE-LDD: rate-limit denial must not mint a second OTP or enqueue SMS.
    def test_atomic_rate_limit_blocks_second_send_code(self, r, grace_logs) -> None:
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

            first = send_code(SendCodeRequest(phone=phone), db=db, r=r)
            with pytest.raises(HTTPException) as exc_info:
                send_code(SendCodeRequest(phone=phone), db=db, r=r)

        assert first == {"message": "OTP sent"}
        assert exc_info.value.status_code == 429
        celery_cls.return_value.send_task.assert_called_once()
        user_service.get_or_create_user.assert_called_once()

        grace_logs.assert_trajectory(("auth.otp_request", "BLOCK_OTP_GEN"))
        assert len(grace_logs.blocks(fn="auth.otp_request", blk="BLOCK_OTP_GEN")) == 1
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

    # GRACE-LDD: blocked users cannot regain sessions after a valid OTP verify.
    def test_blocked_user_verify_rejects_token_issue(self, r, grace_logs) -> None:
        phone = "+79991234567"
        phone_hash = hash_phone(phone)
        otp_svc = OTPService(r)
        code = otp_svc.create_otp(phone_hash)
        otp_svc.update_otp_status(phone_hash, OTPStatus.SENT)

        with patch("core_api.routers.auth.UserService") as user_service_cls:
            user_service = user_service_cls.return_value
            user_service.get_or_create_user.return_value = UserInfo(
                user_id=uuid.uuid4(),
                status=UserStatus.BLOCKED,
                is_new=False,
            )

            with pytest.raises(HTTPException) as exc_info:
                verify_code(
                    VerifyCodeRequest(phone=phone, code=code),
                    response=Response(),
                    db=MagicMock(),
                    r=r,
                )

        assert exc_info.value.status_code == 403
        grace_logs.assert_trajectory(
            ("auth.otp_request", "BLOCK_OTP_GEN"),
            ("auth.otp_verify", "BLOCK_AUTH_VERIFY"),
        )
        assert grace_logs.beliefs(status="MISMATCH") == []
        captured = "\n".join(grace_logs.lines)
        assert phone not in captured
        assert phone_hash not in captured
        assert code not in captured

    # GRACE-LDD: successful OTP verify issues refresh as HttpOnly cookie.
    def test_success_sets_http_only_refresh_cookie(self, r, grace_logs) -> None:
        phone = "+79991234567"
        phone_hash = hash_phone(phone)
        user_id = uuid.uuid4()
        otp_svc = OTPService(r)
        code = otp_svc.create_otp(phone_hash)
        otp_svc.update_otp_status(phone_hash, OTPStatus.SENT)
        response = Response()

        with patch("core_api.routers.auth.UserService") as user_service_cls:
            user_service = user_service_cls.return_value
            user_service.get_or_create_user.return_value = UserInfo(
                user_id=user_id,
                status=UserStatus.ACTIVE,
                is_new=False,
            )

            result = verify_code(
                VerifyCodeRequest(phone=phone, code=code),
                response=response,
                db=MagicMock(),
                r=r,
            )

        cookie = response.headers["set-cookie"]
        assert result.access_token
        assert result.refresh_token
        assert "aura_customer_refresh_token=" in cookie
        assert "HttpOnly" in cookie
        assert "SameSite=strict" in cookie
        assert "Path=/api/v1/auth" in cookie

        grace_logs.assert_trajectory(
            ("auth.otp_request", "BLOCK_OTP_GEN"),
            ("auth.otp_verify", "BLOCK_AUTH_VERIFY"),
        )
        captured = "\n".join(grace_logs.lines)
        assert phone not in captured
        assert phone_hash not in captured
        assert code not in captured
        assert result.refresh_token not in captured


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

    def test_blocked_user_refresh_rejects_and_revokes_session(self, r) -> None:
        user_id = uuid.uuid4()
        auth_svc = AuthService(r)
        pair = auth_svc.issue_tokens(user_id)
        db = MagicMock()
        db.get.return_value = User(
            id=user_id,
            phone_hash="b" * 64,
            status=UserStatus.BLOCKED,
        )

        with pytest.raises(HTTPException) as exc_info:
            refresh_route(
                request=_request_with_cookie(),
                response=Response(),
                body=RefreshRequest(refresh_token=pair.refresh_token),
                r=r,
                db=db,
            )

        assert exc_info.value.status_code == 401
        assert r.get(f"session:{pair.refresh_token}") is None

    def test_refresh_uses_http_only_cookie_and_rotates_cookie(self, r) -> None:
        user_id = uuid.uuid4()
        auth_svc = AuthService(r)
        pair = auth_svc.issue_tokens(user_id)
        db = MagicMock()
        db.get.return_value = User(
            id=user_id,
            phone_hash="d" * 64,
            status=UserStatus.ACTIVE,
        )
        response = Response()

        result = refresh_route(
            request=_request_with_cookie(
                "aura_customer_refresh_token",
                pair.refresh_token,
            ),
            response=response,
            body=None,
            r=r,
            db=db,
        )

        assert result.access_token
        assert result.refresh_token != pair.refresh_token
        assert r.get(f"session:{pair.refresh_token}") is None
        assert r.get(f"session:{result.refresh_token}") is not None
        cookie = response.headers["set-cookie"]
        assert f"aura_customer_refresh_token={result.refresh_token}" in cookie
        assert "HttpOnly" in cookie

    def test_refresh_without_body_or_cookie_rejects_and_clears_cookie(self, r) -> None:
        response = Response()

        with pytest.raises(HTTPException) as exc_info:
            refresh_route(
                request=_request_with_cookie(),
                response=response,
                body=None,
                r=r,
                db=MagicMock(),
            )

        assert exc_info.value.status_code == 401
        cookie = response.headers["set-cookie"]
        assert "aura_customer_refresh_token=" in cookie
        assert "Max-Age=0" in cookie


class TestAccessTokenStatus:
    def test_known_blocked_customer_token_rejected(self, r) -> None:
        user_id = uuid.uuid4()
        auth_svc = AuthService(r)
        token = auth_svc.create_access_token(user_id)
        db = MagicMock()
        db.get.return_value = User(
            id=user_id,
            phone_hash="c" * 64,
            status=UserStatus.BLOCKED,
        )

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=token,
        )
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(credentials=credentials, db=db)

        assert exc_info.value.status_code == 401


class TestLogout:
    def test_unauthenticated(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": "test"},
        )
        assert response.status_code in (401, 403)

    def test_logout_revokes_cookie_refresh_and_clears_cookie(self, r) -> None:
        user_id = uuid.uuid4()
        auth_svc = AuthService(r)
        pair = auth_svc.issue_tokens(user_id)
        response = Response()

        result = logout_route(
            request=_request_with_cookie(
                "aura_customer_refresh_token",
                pair.refresh_token,
            ),
            response=response,
            body=None,
            current_user={"sub": str(user_id), "role": "customer"},
            r=r,
        )

        assert result == {"message": "Logged out"}
        assert r.get(f"session:{pair.refresh_token}") is None
        cookie = response.headers["set-cookie"]
        assert "aura_customer_refresh_token=" in cookie
        assert "Max-Age=0" in cookie
