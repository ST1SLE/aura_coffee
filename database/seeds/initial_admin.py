"""Сид начального админа.

Читает ADMIN_LOGIN и ADMIN_PASSWORD из окружения, хеширует пароль bcrypt
и вставляет строку в staff_accounts. Идемпотентно: ON CONFLICT DO NOTHING.

Запуск вручную:
    python -m database.seeds.initial_admin
"""

# START_MODULE_CONTRACT
#   PURPOSE: One-shot seed that inserts the initial admin row into
#            staff_accounts using ADMIN_LOGIN/ADMIN_PASSWORD from the
#            environment. Idempotent — safe to run on every boot.
#   SCOPE:   Invoked by the docker-compose db-seed service after db-migrate,
#            and manually via `python -m database.seeds.initial_admin`.
#   DEPENDS: M-SHARED (staff_accounts schema), alembic-applied migrations,
#            sqlalchemy, bcrypt, stdlib (os, sys, uuid).
#   LINKS:   docs/development-plan.xml M-DATABASE, PDD §5.2 (Tables/Users),
#            INV-002 (auth — password hashed with bcrypt, never plaintext),
#            database/AGENTS.md "Running the initial admin seed".
#   ROLE:    SCRIPT
#   MAP_MODE: LOCALS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   run - read ADMIN_LOGIN/ADMIN_PASSWORD env vars and upsert one staff_accounts
#         row with role='admin' (ON CONFLICT (login) DO NOTHING).
# END_MODULE_MAP

from __future__ import annotations

import os
import sys
import uuid

import bcrypt
from sqlalchemy import create_engine, text


# START_CONTRACT: run
#   PURPOSE: Insert (or no-op) a single admin row into staff_accounts. Bcrypt-
#            hashes the password before INSERT — plaintext never touches DB.
#   INPUTS:  database_url: str | None — explicit connection URL; falls back to
#            os.environ["DATABASE_URL"] when None.
#   OUTPUTS: None
#   SIDE_EFFECTS: idempotent INSERT into staff_accounts with
#                 ON CONFLICT (login) DO NOTHING. Raises RuntimeError if
#                 DATABASE_URL, ADMIN_LOGIN, or ADMIN_PASSWORD is missing.
#                 Engine is disposed in a finally block.
#   LINKS:   PDD §5.2 (staff_accounts), INV-002 (auth), INV-014 (does not touch
#            order_items at seed time).
# END_CONTRACT: run
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
