"""Проверки сида initial_admin: создаёт одну строку и идемпотентен."""

from __future__ import annotations

import pathlib
import sys

import bcrypt
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from tests.conftest import _TEST_DB_URL

# Подкидываем корень репо в sys.path, чтобы импортировать database.seeds
_REPO_ROOT = pathlib.Path(__file__).parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from database.seeds import initial_admin  # noqa: E402


pytestmark = pytest.mark.skipif(
    _TEST_DB_URL.startswith("sqlite"),
    reason="Требует PostgreSQL (TEST_DATABASE_URL)",
)


def _alembic_cfg() -> Config:
    alembic_ini = str(_REPO_ROOT / "database" / "alembic.ini")
    cfg = Config(alembic_ini)
    cfg.set_main_option("sqlalchemy.url", _TEST_DB_URL)
    return cfg


@pytest.fixture
def migrated_empty_db(_ensure_test_database):
    """Чистая БД на head без seed-данных."""
    cfg = _alembic_cfg()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")

    engine = create_engine(_TEST_DB_URL)
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM staff_accounts"))
    finally:
        engine.dispose()
    yield


def test_seed_creates_admin_row(migrated_empty_db, monkeypatch):
    monkeypatch.setenv("ADMIN_LOGIN", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "pw")

    initial_admin.run(database_url=_TEST_DB_URL)

    engine = create_engine(_TEST_DB_URL)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT login, password_hash FROM staff_accounts")
            ).all()
        assert len(rows) == 1
        login, password_hash = rows[0]
        assert login == "admin"
        assert bcrypt.checkpw(b"pw", password_hash.encode("utf-8"))
    finally:
        engine.dispose()


def test_seed_is_idempotent(migrated_empty_db, monkeypatch):
    monkeypatch.setenv("ADMIN_LOGIN", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "pw")

    initial_admin.run(database_url=_TEST_DB_URL)
    initial_admin.run(database_url=_TEST_DB_URL)

    engine = create_engine(_TEST_DB_URL)
    try:
        with engine.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM staff_accounts")
            ).scalar()
        assert count == 1
    finally:
        engine.dispose()
