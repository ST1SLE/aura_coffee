"""Проверки: миграции runnable без ADMIN_* и не сеятят админа.

Гарантирует, что 0003 — это schema-only миграция, а сид админа
вынесен в ``database/seeds/initial_admin.py``.
"""

from __future__ import annotations

import os
import pathlib

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from tests.conftest import _TEST_DB_URL


pytestmark = pytest.mark.skipif(
    _TEST_DB_URL.startswith("sqlite"),
    reason="Требует PostgreSQL (TEST_DATABASE_URL)",
)


def _alembic_cfg() -> Config:
    alembic_ini = str(
        pathlib.Path(__file__).parents[3] / "database" / "alembic.ini"
    )
    cfg = Config(alembic_ini)
    cfg.set_main_option("sqlalchemy.url", _TEST_DB_URL)
    return cfg


@pytest.fixture
def clean_db(_ensure_test_database):
    """Приводит тестовую БД к пустому состоянию перед тестом."""
    cfg = _alembic_cfg()
    command.downgrade(cfg, "base")
    yield
    # После теста оставляем head для последующих фикстур
    command.upgrade(cfg, "head")


def test_upgrade_head_without_admin_env_vars(clean_db, monkeypatch):
    # Снимаем ADMIN_* из окружения — миграции не должны их требовать.
    monkeypatch.delenv("ADMIN_LOGIN", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)

    cfg = _alembic_cfg()
    command.upgrade(cfg, "head")  # не должен бросить RuntimeError


def test_upgrade_head_no_admin_row_seeded(clean_db, monkeypatch):
    monkeypatch.delenv("ADMIN_LOGIN", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)

    cfg = _alembic_cfg()
    command.upgrade(cfg, "head")

    engine = create_engine(_TEST_DB_URL)
    try:
        with engine.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM staff_accounts")
            ).scalar()
        assert count == 0, "0003 must be schema-only; seed lives in database/seeds"
    finally:
        engine.dispose()
