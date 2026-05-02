import json
import uuid
from unittest.mock import MagicMock

import fakeredis

from core_api.services.auth import AuthService
from shared.enums import UserStatus
from shared.models.user import User


class TestIssueTokens:
    def test_access_token_decodable(self, auth_svc: AuthService) -> None:
        """issue_tokens возвращает access token с правильными sub и role."""
        user_id = uuid.uuid4()
        pair = auth_svc.issue_tokens(user_id, "customer")
        payload = AuthService.decode_access_token(pair.access_token)
        assert payload["sub"] == str(user_id)
        assert payload["role"] == "customer"

    def test_refresh_token_in_redis(self, auth_svc: AuthService, r: fakeredis.FakeRedis) -> None:
        """Refresh token хранится в Redis как session:{token} с user_id."""
        user_id = uuid.uuid4()
        pair = auth_svc.issue_tokens(user_id)
        raw = r.get(f"session:{pair.refresh_token}")
        assert raw is not None
        data = json.loads(raw)
        assert data["user_id"] == str(user_id)
        assert pair.refresh_token.encode() in r.smembers(f"user_sessions:{user_id}")


class TestRefreshTokenRotation:
    def test_rotation_deletes_old_creates_new(self, auth_svc: AuthService, r: fakeredis.FakeRedis) -> None:
        """Ротация: старый токен удалён, новая пара выпущена, новый refresh в Redis."""
        user_id = uuid.uuid4()
        old_pair = auth_svc.issue_tokens(user_id)
        new_pair = auth_svc.refresh_tokens(old_pair.refresh_token)

        assert new_pair is not None
        assert r.get(f"session:{old_pair.refresh_token}") is None
        assert r.get(f"session:{new_pair.refresh_token}") is not None

    def test_rotation_preserves_user_id(self, auth_svc: AuthService) -> None:
        """Новый access token после ротации содержит тот же user_id."""
        user_id = uuid.uuid4()
        old_pair = auth_svc.issue_tokens(user_id)
        new_pair = auth_svc.refresh_tokens(old_pair.refresh_token)

        assert new_pair is not None
        payload = AuthService.decode_access_token(new_pair.access_token)
        assert payload["sub"] == str(user_id)

    def test_double_use_returns_none(self, auth_svc: AuthService) -> None:
        """Повторное использование ротированного refresh token → None."""
        user_id = uuid.uuid4()
        pair = auth_svc.issue_tokens(user_id)
        auth_svc.refresh_tokens(pair.refresh_token)
        result = auth_svc.refresh_tokens(pair.refresh_token)
        assert result is None

    def test_blocked_user_refresh_revokes_all_sessions(
        self, auth_svc: AuthService, r: fakeredis.FakeRedis
    ) -> None:
        """BLOCKED customer cannot refresh; indexed sessions are revoked."""
        user_id = uuid.uuid4()
        first = auth_svc.issue_tokens(user_id)
        second = auth_svc.issue_tokens(user_id)
        db = MagicMock()
        db.get.return_value = User(
            id=user_id,
            phone_hash="a" * 64,
            status=UserStatus.BLOCKED,
        )

        result = auth_svc.refresh_tokens(first.refresh_token, db=db)

        assert result is None
        assert r.get(f"session:{first.refresh_token}") is None
        assert r.get(f"session:{second.refresh_token}") is None
        assert r.smembers(f"user_sessions:{user_id}") == set()

    def test_blocked_user_refresh_deletes_unindexed_legacy_session(
        self, auth_svc: AuthService, r: fakeredis.FakeRedis
    ) -> None:
        user_id = uuid.uuid4()
        refresh_token = str(uuid.uuid4())
        r.set(
            f"session:{refresh_token}",
            json.dumps({"user_id": str(user_id), "issued_at": "legacy"}),
        )
        db = MagicMock()
        db.get.return_value = User(
            id=user_id,
            phone_hash="d" * 64,
            status=UserStatus.BLOCKED,
        )

        result = auth_svc.refresh_tokens(refresh_token, db=db)

        assert result is None
        assert r.get(f"session:{refresh_token}") is None


class TestLogout:
    def test_logout_deletes_session(self, auth_svc: AuthService, r: fakeredis.FakeRedis) -> None:
        """logout удаляет ключ session:{token} и возвращает True."""
        user_id = uuid.uuid4()
        pair = auth_svc.issue_tokens(user_id)
        result = auth_svc.logout(pair.refresh_token)
        assert result is True
        assert r.get(f"session:{pair.refresh_token}") is None
        assert pair.refresh_token.encode() not in r.smembers(f"user_sessions:{user_id}")

    def test_logout_nonexistent_returns_false(self, auth_svc: AuthService) -> None:
        """logout с несуществующим токеном → False."""
        result = auth_svc.logout("nonexistent-token")
        assert result is False
