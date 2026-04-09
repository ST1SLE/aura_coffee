"""Тесты profile endpoints.

Запуск: pytest services/core-api/tests/test_profile_endpoints.py -v
"""

import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from core_api.deps.auth import get_current_user
from core_api.main import app
from core_api.schemas.profile import ProfileResponse


FAKE_USER_ID = uuid.uuid4()
FAKE_PROFILE = ProfileResponse(
    user_id=FAKE_USER_ID,
    phone_masked="+7 *** *** 45 67",
    display_name="Михаил",
    preferred_language="ru",
)

client = TestClient(app)


def _override_auth(user_id: uuid.UUID = FAKE_USER_ID, role: str = "customer"):
    """Подмена get_current_user через dependency_overrides."""
    def _dep():
        return {"user_id": user_id, "role": role}
    return _dep


class TestGetProfile:
    def test_success(self) -> None:
        app.dependency_overrides[get_current_user] = _override_auth()
        with patch("core_api.routers.profile.get_profile", return_value=FAKE_PROFILE):
            response = client.get("/api/v1/profile")
        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["phone_masked"] == "+7 *** *** 45 67"
        assert data["display_name"] == "Михаил"
        assert data["preferred_language"] == "ru"

    def test_masked_phone_format(self) -> None:
        from core_api.services.profile import _mask_phone

        assert _mask_phone("+79161234567") == "+7 *** *** 45 67"

    def test_unauthenticated(self) -> None:
        app.dependency_overrides.clear()
        response = client.get("/api/v1/profile")
        assert response.status_code in (401, 403)

    def test_wrong_role(self) -> None:
        app.dependency_overrides[get_current_user] = _override_auth(role="admin")
        response = client.get("/api/v1/profile")
        app.dependency_overrides.clear()

        assert response.status_code == 403

    def test_profile_not_found(self) -> None:
        app.dependency_overrides[get_current_user] = _override_auth()
        with patch("core_api.routers.profile.get_profile", return_value=None):
            response = client.get("/api/v1/profile")
        app.dependency_overrides.clear()

        assert response.status_code == 404


class TestUpdateProfile:
    def test_update_name(self) -> None:
        app.dependency_overrides[get_current_user] = _override_auth()
        updated = FAKE_PROFILE.model_copy(update={"display_name": "Миша"})
        with patch("core_api.routers.profile.update_profile", return_value=updated):
            response = client.patch("/api/v1/profile", json={"display_name": "Миша"})
        app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json()["display_name"] == "Миша"

    def test_update_language(self) -> None:
        app.dependency_overrides[get_current_user] = _override_auth()
        updated = FAKE_PROFILE.model_copy(update={"preferred_language": "en"})
        with patch("core_api.routers.profile.update_profile", return_value=updated):
            response = client.patch("/api/v1/profile", json={"preferred_language": "en"})
        app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json()["preferred_language"] == "en"

    def test_empty_body_noop(self) -> None:
        app.dependency_overrides[get_current_user] = _override_auth()
        with patch("core_api.routers.profile.update_profile", return_value=FAKE_PROFILE):
            response = client.patch("/api/v1/profile", json={})
        app.dependency_overrides.clear()

        assert response.status_code == 200

    def test_name_too_long(self) -> None:
        app.dependency_overrides[get_current_user] = _override_auth()
        response = client.patch("/api/v1/profile", json={"display_name": "x" * 101})
        app.dependency_overrides.clear()

        assert response.status_code == 422

    def test_invalid_language(self) -> None:
        app.dependency_overrides[get_current_user] = _override_auth()
        response = client.patch("/api/v1/profile", json={"preferred_language": "fr"})
        app.dependency_overrides.clear()

        assert response.status_code == 422
