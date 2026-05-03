"""JWT-хелперы для тестов: детерминированный sub по user_id.

Основной conftest.py выдаёт JWT со случайным `sub` — это мешает тестам,
которые проверяют per-user isolation (например, 403/404 на чужих заказах).
Эти функции позволяют построить токен с заданным user_id.
"""
from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import jwt as pyjwt


def _jwt_secret() -> str:
    """Тот же секрет, что использует сервер (settings.jwt_secret_key из env)."""
    return os.environ.get("JWT_SECRET_KEY", "aura-coffee-tests-jwt-secret-0001")


def make_jwt_for_user(user_id: uuid.UUID, role: str = "customer") -> str:
    """JWT access token с заданным user_id в `sub`."""
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(seconds=900),
    }
    return pyjwt.encode(payload, _jwt_secret(), algorithm="HS256")


def auth_headers_for_user(user_id: uuid.UUID, role: str = "customer") -> dict[str, str]:
    """Удобный шорткат: готовые Authorization headers."""
    return {"Authorization": f"Bearer {make_jwt_for_user(user_id, role)}"}
