"""Тесты staff auth endpoints и RBAC."""

import json
import uuid
from contextlib import contextmanager
from unittest.mock import MagicMock

import bcrypt
import fakeredis
import jwt
import pytest
from fastapi.testclient import TestClient

from core_api.deps.database import get_db
from core_api.deps.redis import get_redis
from core_api.main import app
from core_api.services.staff_auth import StaffAuthService


@pytest.fixture
def client():
    return TestClient(app)


def _make_staff_account(
    login: str = "admin",
    password: str = "secret123",
    role_value: str = "admin",
    is_active: bool = True,
):
    """Мок объекта StaffAccount."""
    password_hash = bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")

    staff = MagicMock()
    staff.id = uuid.uuid4()
    staff.login = login
    staff.password_hash = password_hash
    staff.role = MagicMock()
    staff.role.value = role_value
    staff.is_active = is_active
    staff.display_name = "Test Staff"
    return staff


@contextmanager
def _override_deps(mock_db=None, mock_redis=None):
    """Подмена FastAPI-зависимостей get_db и get_redis."""
    if mock_db is None:
        mock_db = MagicMock()
    if mock_redis is None:
        mock_redis = MagicMock()

    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_redis] = lambda: mock_redis
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_redis, None)


class TestStaffLogin:
    def test_valid_credentials(self, client: TestClient) -> None:
        staff = _make_staff_account()
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = staff
        mock_redis = MagicMock()

        with _override_deps(mock_db, mock_redis):
            response = client.post(
                "/api/v1/staff/auth/login",
                json={"login": "admin", "password": "secret123"},
            )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["role"] == "admin"
        cookie = response.headers["set-cookie"]
        assert "aura_staff_refresh_token=" in cookie
        assert "HttpOnly" in cookie
        assert "SameSite=strict" in cookie
        assert "Path=/api/v1/staff/auth" in cookie

    def test_wrong_password(self, client: TestClient) -> None:
        staff = _make_staff_account(password="correct_pass")
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = staff
        mock_redis = MagicMock()

        with _override_deps(mock_db, mock_redis):
            response = client.post(
                "/api/v1/staff/auth/login",
                json={"login": "admin", "password": "wrong_pass"},
            )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials"

    def test_nonexistent_login(self, client: TestClient) -> None:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_redis = MagicMock()

        with _override_deps(mock_db, mock_redis):
            response = client.post(
                "/api/v1/staff/auth/login",
                json={"login": "nobody", "password": "pass"},
            )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials"

    def test_inactive_account(self, client: TestClient) -> None:
        staff = _make_staff_account(is_active=False)
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = staff
        mock_redis = MagicMock()

        with _override_deps(mock_db, mock_redis):
            response = client.post(
                "/api/v1/staff/auth/login",
                json={"login": "admin", "password": "secret123"},
            )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials"

    # GRACE-LDD: staff login throttling emits auth marker and redacts secrets.
    def test_wrong_password_is_throttled_by_login(
        self, client: TestClient, grace_logs
    ) -> None:
        staff = _make_staff_account(password="correct_pass")
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = staff
        redis_client = fakeredis.FakeRedis()

        with _override_deps(mock_db, redis_client):
            for _ in range(5):
                response = client.post(
                    "/api/v1/staff/auth/login",
                    json={"login": "admin", "password": "wrong_pass"},
                )
                assert response.status_code == 401

            response = client.post(
                "/api/v1/staff/auth/login",
                json={"login": "admin", "password": "wrong_pass"},
            )

        assert response.status_code == 429
        assert int(response.headers["retry-after"]) > 0
        grace_logs.assert_trajectory(
            ("staff.auth_login", "BLOCK_AUTH_VERIFY")
        )
        captured = "\n".join(grace_logs.lines)
        assert "wrong_pass" not in captured
        assert "correct_pass" not in captured
        assert "refresh_token" not in captured
        assert "access_token" not in captured
        assert not grace_logs.beliefs(status="MISMATCH")

    def test_failed_login_throttling_resets_after_success(
        self, client: TestClient
    ) -> None:
        staff = _make_staff_account(password="correct_pass")
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = staff
        redis_client = fakeredis.FakeRedis()

        with _override_deps(mock_db, redis_client):
            response = client.post(
                "/api/v1/staff/auth/login",
                json={"login": "admin", "password": "wrong_pass"},
            )
            assert response.status_code == 401
            assert redis_client.keys("staff_login_rate:*")

            response = client.post(
                "/api/v1/staff/auth/login",
                json={"login": "admin", "password": "correct_pass"},
            )

        assert response.status_code == 200
        keys = {
            key.decode() if isinstance(key, bytes) else key
            for key in redis_client.keys("staff_login_rate:*")
        }
        assert not any(":login:" in key for key in keys)
        assert any(":ip:" in key for key in keys)

    def test_failed_login_is_throttled_by_source_ip(
        self, client: TestClient
    ) -> None:
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        redis_client = fakeredis.FakeRedis()

        with _override_deps(mock_db, redis_client):
            for idx in range(30):
                response = client.post(
                    "/api/v1/staff/auth/login",
                    json={"login": f"missing-{idx}", "password": "guess"},
                )
                assert response.status_code == 401

            response = client.post(
                "/api/v1/staff/auth/login",
                json={"login": "another-missing", "password": "guess"},
            )

        assert response.status_code == 429
        assert int(response.headers["retry-after"]) > 0


class TestStaffRefresh:
    def test_valid_refresh(self, client: TestClient) -> None:
        staff_id = uuid.uuid4()
        session_data = json.dumps({
            "staff_id": str(staff_id),
            "role": "barista",
            "issued_at": "2026-01-01T00:00:00+00:00",
        })
        mock_redis = MagicMock()
        mock_redis.get.return_value = session_data.encode()
        mock_db = MagicMock()
        staff = _make_staff_account(role_value="barista")
        staff.id = staff_id
        mock_db.query.return_value.filter.return_value.first.return_value = staff

        with _override_deps(mock_db, mock_redis):
            response = client.post(
                "/api/v1/staff/auth/refresh",
                json={"refresh_token": "valid-token"},
            )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        mock_redis.delete.assert_called_once()
        assert "aura_staff_refresh_token=" in response.headers["set-cookie"]

    def test_valid_refresh_from_http_only_cookie(self, client: TestClient) -> None:
        staff_id = uuid.uuid4()
        session_data = json.dumps({
            "staff_id": str(staff_id),
            "role": "barista",
            "issued_at": "2026-01-01T00:00:00+00:00",
        })
        mock_redis = MagicMock()
        mock_redis.get.return_value = session_data.encode()
        mock_db = MagicMock()
        staff = _make_staff_account(role_value="barista")
        staff.id = staff_id
        mock_db.query.return_value.filter.return_value.first.return_value = staff

        with _override_deps(mock_db, mock_redis):
            response = client.post(
                "/api/v1/staff/auth/refresh",
                json={},
                cookies={"aura_staff_refresh_token": "cookie-token"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        mock_redis.delete.assert_called_once()
        cookie = response.headers["set-cookie"]
        assert "aura_staff_refresh_token=" in cookie
        assert "HttpOnly" in cookie

    def test_inactive_staff_refresh_revokes_sessions(self) -> None:
        staff_id = uuid.uuid4()
        refresh_token = "stale-staff-refresh"
        redis_client = fakeredis.FakeRedis()
        redis_client.set(
            f"staff_refresh:{refresh_token}",
            json.dumps({
                "staff_id": str(staff_id),
                "role": "barista",
                "issued_at": "2026-01-01T00:00:00+00:00",
            }),
        )
        redis_client.sadd(f"staff_sessions:{staff_id}", refresh_token)
        staff = _make_staff_account(role_value="barista", is_active=False)
        staff.id = staff_id
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = staff

        result = StaffAuthService(mock_db, redis_client).refresh_tokens(refresh_token)

        assert result is None
        assert redis_client.get(f"staff_refresh:{refresh_token}") is None
        assert redis_client.smembers(f"staff_sessions:{staff_id}") == set()

    def test_inactive_staff_refresh_deletes_unindexed_legacy_session(self) -> None:
        staff_id = uuid.uuid4()
        refresh_token = "legacy-staff-refresh"
        redis_client = fakeredis.FakeRedis()
        redis_client.set(
            f"staff_refresh:{refresh_token}",
            json.dumps({
                "staff_id": str(staff_id),
                "role": "courier",
                "issued_at": "legacy",
            }),
        )
        staff = _make_staff_account(role_value="courier", is_active=False)
        staff.id = staff_id
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = staff

        result = StaffAuthService(mock_db, redis_client).refresh_tokens(refresh_token)

        assert result is None
        assert redis_client.get(f"staff_refresh:{refresh_token}") is None

    def test_expired_token(self, client: TestClient) -> None:
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_db = MagicMock()

        with _override_deps(mock_db, mock_redis):
            response = client.post(
                "/api/v1/staff/auth/refresh",
                json={"refresh_token": "expired"},
            )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid or expired refresh token"

    def test_replayed_token(self, client: TestClient) -> None:
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_db = MagicMock()

        with _override_deps(mock_db, mock_redis):
            response = client.post(
                "/api/v1/staff/auth/refresh",
                json={"refresh_token": "already-used"},
            )
        assert response.status_code == 401


class TestStaffLogout:
    def test_successful_logout(self, client: TestClient) -> None:
        from core_api.settings import settings

        token_payload = {
            "sub": str(uuid.uuid4()),
            "role": "admin",
        }
        access_token = jwt.encode(
            token_payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )
        mock_redis = MagicMock()
        mock_db = MagicMock()

        with _override_deps(mock_db, mock_redis):
            response = client.post(
                "/api/v1/staff/auth/logout",
                json={"refresh_token": "token-to-delete"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
        assert response.status_code == 200
        assert response.json()["detail"] == "Logged out"
        assert "aura_staff_refresh_token=" in response.headers["set-cookie"]
        assert "Max-Age=0" in response.headers["set-cookie"]

    def test_logout_uses_cookie_refresh_and_clears_cookie(
        self, client: TestClient
    ) -> None:
        from core_api.settings import settings

        token_payload = {
            "sub": str(uuid.uuid4()),
            "role": "admin",
        }
        access_token = jwt.encode(
            token_payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )
        mock_redis = MagicMock()
        mock_db = MagicMock()

        with _override_deps(mock_db, mock_redis):
            response = client.post(
                "/api/v1/staff/auth/logout",
                json={},
                cookies={"aura_staff_refresh_token": "cookie-token"},
                headers={"Authorization": f"Bearer {access_token}"},
            )

        assert response.status_code == 200
        mock_redis.delete.assert_called_with("staff_refresh:cookie-token")
        cookie = response.headers["set-cookie"]
        assert "aura_staff_refresh_token=" in cookie
        assert "Max-Age=0" in cookie

    def test_unauthenticated(self, client: TestClient) -> None:
        mock_db = MagicMock()
        mock_redis = MagicMock()

        with _override_deps(mock_db, mock_redis):
            response = client.post(
                "/api/v1/staff/auth/logout",
                json={"refresh_token": "test"},
            )
        assert response.status_code in (401, 403)


class TestRequireRole:
    """Тесты RBAC-зависимости require_role через реальный эндпоинт."""

    @pytest.fixture
    def rbac_app(self):
        """Тестовое приложение с защищённым эндпоинтом."""
        from fastapi import Depends, FastAPI

        from core_api.deps.rbac import require_role

        app = FastAPI()

        @app.get("/admin-only")
        def admin_only(user: dict = Depends(require_role("admin"))):
            return {"ok": True, "role": user["role"]}

        @app.get("/staff")
        def staff_endpoint(
            user: dict = Depends(require_role("admin", "barista")),
        ):
            return {"ok": True, "role": user["role"]}

        return TestClient(app)

    def _make_token(self, role: str) -> str:
        from core_api.settings import settings

        payload = {"sub": str(uuid.uuid4()), "role": role}
        return jwt.encode(
            payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )

    def test_authorized_role(self, rbac_app: TestClient) -> None:
        token = self._make_token("admin")
        response = rbac_app.get(
            "/admin-only", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200

    def test_unauthorized_role(self, rbac_app: TestClient) -> None:
        token = self._make_token("barista")
        response = rbac_app.get(
            "/admin-only", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Insufficient permissions"

    def test_no_auth_header(self, rbac_app: TestClient) -> None:
        response = rbac_app.get("/admin-only")
        assert response.status_code in (401, 403)

    def test_customer_denied_on_staff_endpoint(self, rbac_app: TestClient) -> None:
        token = self._make_token("customer")
        response = rbac_app.get(
            "/staff", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403

    def test_multi_role_access(self, rbac_app: TestClient) -> None:
        token = self._make_token("barista")
        response = rbac_app.get(
            "/staff", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
