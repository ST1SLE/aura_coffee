"""Migration 0012 adds shop_settings.ordering_paused.

The flag is an operator-controlled launch/maintenance hold. It must be
non-null, default false, and seeded false so public ordering is not paused by
schema deployment alone.
"""
from __future__ import annotations

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from tests.conftest import _TEST_DB_URL as TEST_DB_URL

ALEMBIC_INI = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "database", "alembic.ini"
)

_IS_SQLITE = TEST_DB_URL.startswith("sqlite")


@pytest.fixture(scope="module")
def alembic_cfg(_ensure_test_database) -> Config:
    if _IS_SQLITE:
        pytest.skip("Migration tests require PostgreSQL")
    cfg = Config(ALEMBIC_INI)
    cfg.set_main_option("sqlalchemy.url", TEST_DB_URL)
    return cfg


@pytest.fixture(scope="module")
def upgraded_engine(alembic_cfg: Config):
    engine = create_engine(TEST_DB_URL)
    command.upgrade(alembic_cfg, "head")
    yield engine
    command.downgrade(alembic_cfg, "0011")
    engine.dispose()


def _shop_settings_columns(engine) -> dict[str, dict]:
    return {c["name"]: c for c in inspect(engine).get_columns("shop_settings")}


def test_upgrade_adds_ordering_paused_column(upgraded_engine) -> None:
    cols = _shop_settings_columns(upgraded_engine)
    assert "ordering_paused" in cols
    col = cols["ordering_paused"]
    assert col["nullable"] is False
    assert "false" in str(col.get("default") or "").lower()


def test_downgrade_drops_ordering_paused_column(alembic_cfg: Config) -> None:
    if _IS_SQLITE:
        pytest.skip("Migration tests require PostgreSQL")

    engine = create_engine(TEST_DB_URL)
    try:
        command.upgrade(alembic_cfg, "head")
        command.downgrade(alembic_cfg, "0011")
        cols = _shop_settings_columns(engine)
        assert "ordering_paused" not in cols
    finally:
        command.upgrade(alembic_cfg, "head")
        engine.dispose()


def test_seed_row_has_ordering_paused_false(upgraded_engine) -> None:
    from database.seeds.shop_settings import run

    run(TEST_DB_URL)

    with upgraded_engine.connect() as conn:
        row = conn.execute(
            text("SELECT id, ordering_paused FROM shop_settings WHERE id = 1")
        ).one()

    assert row.id == 1
    assert row.ordering_paused is False
