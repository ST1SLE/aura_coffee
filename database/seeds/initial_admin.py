"""Сид начального админа.

Читает ADMIN_LOGIN и ADMIN_PASSWORD из окружения, хеширует пароль bcrypt
и вставляет строку в staff_accounts. Идемпотентно: ON CONFLICT DO NOTHING.

Запуск вручную:
    python -m database.seeds.initial_admin
"""

from __future__ import annotations

import os
import sys
import uuid

import bcrypt
from sqlalchemy import create_engine, text


def run(database_url: str | None = None) -> None:
    url = database_url or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")

    admin_login = os.environ.get("ADMIN_LOGIN")
    admin_password = os.environ.get("ADMIN_PASSWORD")
    if not admin_login or not admin_password:
        raise RuntimeError(
            "ADMIN_LOGIN and ADMIN_PASSWORD env vars are required for initial admin seed"
        )

    password_hash = bcrypt.hashpw(
        admin_password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")

    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO staff_accounts (id, login, password_hash, role, display_name, is_active)
                    VALUES (:id, :login, :password_hash, :role, :display_name, true)
                    ON CONFLICT (login) DO NOTHING
                    """
                ),
                {
                    "id": uuid.uuid4(),
                    "login": admin_login,
                    "password_hash": password_hash,
                    "role": "admin",
                    "display_name": "Admin",
                },
            )
    finally:
        engine.dispose()


if __name__ == "__main__":
    run()
    sys.stdout.write("initial_admin seed applied\n")
