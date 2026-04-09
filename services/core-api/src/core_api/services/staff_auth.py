import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
import redis
from sqlalchemy.orm import Session

from core_api.settings import settings
from shared.models.staff_account import StaffAccount


@dataclass
class StaffTokenPair:
    access_token: str
    refresh_token: str
    role: str


class StaffAuthService:
    def __init__(self, db: Session, redis_client: redis.Redis) -> None:
        self._db = db
        self._redis = redis_client

    def authenticate(self, login: str, password: str) -> StaffTokenPair | None:
        """Аутентификация по логину/паролю. Возвращает токены или None."""
        staff = (
            self._db.query(StaffAccount)
            .filter(StaffAccount.login == login)
            .first()
        )
        if staff is None:
            return None
        if not staff.is_active:
            return None
        if not bcrypt.checkpw(
            password.encode("utf-8"),
            staff.password_hash.encode("utf-8"),
        ):
            return None

        return self._issue_tokens(staff.id, staff.role.value)

    def refresh_tokens(self, refresh_token: str) -> StaffTokenPair | None:
        """Ротация refresh token: валидация → удаление → новая пара."""
        key = f"staff_refresh:{refresh_token}"
        raw = self._redis.get(key)
        if raw is None:
            return None

        self._redis.delete(key)
        session_data = json.loads(raw)
        staff_id = uuid.UUID(session_data["staff_id"])
        role = session_data["role"]
        return self._issue_tokens(staff_id, role)

    def logout(self, refresh_token: str) -> bool:
        """Удаление staff refresh token из Redis."""
        return bool(self._redis.delete(f"staff_refresh:{refresh_token}"))

    def _issue_tokens(self, staff_id: uuid.UUID, role: str) -> StaffTokenPair:
        """Выпуск пары access + refresh токенов для сотрудника."""
        access_token = self._create_access_token(staff_id, role)
        refresh_token = self._create_refresh_token(staff_id, role)
        return StaffTokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            role=role,
        )

    def _create_access_token(self, staff_id: uuid.UUID, role: str) -> str:
        """JWT access token с ролью сотрудника."""
        now = datetime.now(UTC)
        payload = {
            "sub": str(staff_id),
            "role": role,
            "iat": now,
            "exp": now + timedelta(seconds=settings.access_token_ttl),
        }
        return jwt.encode(
            payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )

    def _create_refresh_token(self, staff_id: uuid.UUID, role: str) -> str:
        """Opaque UUID refresh token для сотрудника, хранится в Redis."""
        token = str(uuid.uuid4())
        session_data = json.dumps({
            "staff_id": str(staff_id),
            "role": role,
            "issued_at": datetime.now(UTC).isoformat(),
        })
        self._redis.set(
            f"staff_refresh:{token}",
            session_data,
            ex=settings.refresh_token_ttl,
        )
        return token
