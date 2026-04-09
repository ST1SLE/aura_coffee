"""Тесты UserService.

Требуют запущенной PostgreSQL с примененными миграциями.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from shared.enums import UserStatus


class TestUserService:
    """Unit-тесты с мокнутой БД."""

    @patch("core_api.services.user.settings")
    def test_create_new_user(self, mock_settings) -> None:
        mock_settings.encryption_key = "a" * 64

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        from core_api.services.user import UserService

        svc = UserService(mock_db)
        result = svc.get_or_create_user("+79161234567", "fakehash")

        assert result.is_new is True
        assert result.status == UserStatus.PENDING_VERIFICATION
        assert mock_db.add.called
        assert mock_db.commit.called

    @patch("core_api.services.user.settings")
    def test_existing_user(self, mock_settings) -> None:
        mock_settings.encryption_key = "a" * 64

        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.status = UserStatus.ACTIVE

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        from core_api.services.user import UserService

        svc = UserService(mock_db)
        result = svc.get_or_create_user("+79161234567", "fakehash")

        assert result.is_new is False
        assert result.status == UserStatus.ACTIVE

    def test_activate_pending_user(self) -> None:
        mock_user = MagicMock()
        mock_user.status = UserStatus.PENDING_VERIFICATION

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        from core_api.services.user import UserService

        svc = UserService(mock_db)
        result = svc.activate_user(uuid.uuid4())

        assert result is True
        assert mock_user.status == UserStatus.ACTIVE
        assert mock_db.commit.called

    def test_activate_already_active(self) -> None:
        mock_user = MagicMock()
        mock_user.status = UserStatus.ACTIVE

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        from core_api.services.user import UserService

        svc = UserService(mock_db)
        result = svc.activate_user(uuid.uuid4())

        assert result is False

    def test_blocked_user_status(self) -> None:
        mock_user = MagicMock()
        mock_user.status = UserStatus.BLOCKED

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user

        from core_api.services.user import UserService

        svc = UserService(mock_db)
        status = svc.get_user_status("somehash")

        assert status == UserStatus.BLOCKED
