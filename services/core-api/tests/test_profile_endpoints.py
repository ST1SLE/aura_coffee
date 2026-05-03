"""Тесты profile endpoints.

Запуск: pytest services/core-api/tests/test_profile_endpoints.py -v
"""

import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from core_api.main import app
from core_api.schemas.profile import ProfileResponse
from core_api.services.auth import AuthService


FAKE_USER_ID = uuid.uuid4()
FAKE_PROFILE = ProfileResponse(
    user_id=FAKE_USER_ID,
    phone_masked="+7 *** *** 45 67",
    display_name="Михаил",
    preferred_language="ru",
)

client = TestClient(app)

TEST_SECRET = "aura-coffee-tests-jwt-secret-0001"


def _make_token(role: str = "customer", user_id: uuid.UUID | None = None) -> str:
    """Создание JWT-токена для тестов."""
    uid = user_id or FAKE_USER_ID
    with patch("core_api.services.auth.settings") as mock_settings:
        mock_settings.jwt_secret_key = TEST_SECRET
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.access_token_ttl = 900
        svc = AuthService.__new__(AuthService)
        return svc.create_access_token(uid, role)


def _auth_header(role: str = "customer") -> dict[str, str]:
    return {"Authorization": f"Bearer {_make_token(role)}"}


def _patch_jwt():
    """Патч настроек JWT для middleware."""
    return patch("core_api.services.auth.settings", **{
        "jwt_secret_key": TEST_SECRET,
        "jwt_algorithm": "HS256",
        "access_token_ttl": 900,
    })


class TestGetProfile:
    def test_success(self) -> None:
        with _patch_jwt(), patch("core_api.routers.profile.get_profile", return_value=FAKE_PROFILE):
            response = client.get("/api/v1/profile", headers=_auth_header())

        assert response.status_code == 200
        data = response.json()
        assert data["phone_masked"] == "+7 *** *** 45 67"
        assert data["display_name"] == "Михаил"
        assert data["preferred_language"] == "ru"

    def test_masked_phone_format(self) -> None:
        from core_api.services.profile import _mask_phone

        assert _mask_phone("+79161234567") == "+7 *** *** 45 67"

    def test_unauthenticated(self) -> None:
        response = client.get("/api/v1/profile")
        assert response.status_code == 401

    def test_wrong_role(self) -> None:
        with _patch_jwt():
            response = client.get("/api/v1/profile", headers=_auth_header("admin"))

        assert response.status_code == 403

    def test_profile_not_found(self) -> None:
        with _patch_jwt(), patch("core_api.routers.profile.get_profile", return_value=None):
            response = client.get("/api/v1/profile", headers=_auth_header())

        assert response.status_code == 404


class TestUpdateProfile:
    def test_update_name(self) -> None:
        updated = FAKE_PROFILE.model_copy(update={"display_name": "Миша"})
        with _patch_jwt(), patch("core_api.routers.profile.update_profile", return_value=updated):
            response = client.patch("/api/v1/profile", json={"display_name": "Миша"}, headers=_auth_header())

        assert response.status_code == 200
        assert response.json()["display_name"] == "Миша"

    def test_update_language(self) -> None:
        updated = FAKE_PROFILE.model_copy(update={"preferred_language": "en"})
        with _patch_jwt(), patch("core_api.routers.profile.update_profile", return_value=updated):
            response = client.patch("/api/v1/profile", json={"preferred_language": "en"}, headers=_auth_header())

        assert response.status_code == 200
        assert response.json()["preferred_language"] == "en"

    def test_empty_body_noop(self) -> None:
        with _patch_jwt(), patch("core_api.routers.profile.update_profile", return_value=FAKE_PROFILE):
            response = client.patch("/api/v1/profile", json={}, headers=_auth_header())

        assert response.status_code == 200

    def test_name_too_long(self) -> None:
        with _patch_jwt():
            response = client.patch("/api/v1/profile", json={"display_name": "x" * 101}, headers=_auth_header())

        assert response.status_code == 422

    def test_invalid_language(self) -> None:
        with _patch_jwt():
            response = client.patch("/api/v1/profile", json={"preferred_language": "fr"}, headers=_auth_header())

        assert response.status_code == 422
