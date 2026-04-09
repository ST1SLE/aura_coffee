import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
import redis

from core_api.settings import settings


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str


class AuthService:
    def __init__(self, redis_client: redis.Redis) -> None:
        self._redis = redis_client

    def create_access_token(self, user_id: uuid.UUID, role: str = "customer") -> str:
        """JWT access token: HS256, TTL из настроек."""
        now = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "role": role,
            "iat": now,
            "exp": now + timedelta(seconds=settings.access_token_ttl),
        }
        return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    def create_refresh_token(self, user_id: uuid.UUID) -> str:
        """Opaque UUID refresh token, хранится в Redis с TTL 7 дней."""
        token = str(uuid.uuid4())
        session_data = json.dumps({
            "user_id": str(user_id),
            "issued_at": datetime.now(UTC).isoformat(),
        })
        self._redis.set(
            f"session:{token}",
            session_data,
            ex=settings.refresh_token_ttl,
        )
        return token

    def issue_tokens(self, user_id: uuid.UUID, role: str = "customer") -> TokenPair:
        """Выпуск пары access + refresh токенов."""
        return TokenPair(
            access_token=self.create_access_token(user_id, role),
            refresh_token=self.create_refresh_token(user_id),
        )

    def refresh_tokens(self, refresh_token: str) -> TokenPair | None:
        """Ротация: валидация старого refresh → удаление → выпуск новой пары."""
        key = f"session:{refresh_token}"
        raw = self._redis.get(key)
        if raw is None:
            return None

        self._redis.delete(key)
        session_data = json.loads(raw)
        user_id = uuid.UUID(session_data["user_id"])
        return self.issue_tokens(user_id)

    def logout(self, refresh_token: str) -> bool:
        """Удаление refresh token из Redis."""
        return bool(self._redis.delete(f"session:{refresh_token}"))

    @staticmethod
    def decode_access_token(token: str) -> dict:
        """Декодирование и валидация JWT access token."""
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
