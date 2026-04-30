"""Migration 0009: presentational media fields on menu_items."""

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from tests.conftest import _TEST_DB_URL as TEST_DB_URL

ALEMBIC_INI = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "database", "alembic.ini"
)


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


@pytest.fixture(scope="module")
def alembic_cfg(_ensure_test_database) -> Config:
    if _is_sqlite(TEST_DB_URL):
        pytest.skip("Тесты миграции требуют PostgreSQL, пропущено при SQLite")
    cfg = Config(ALEMBIC_INI)
    cfg.set_main_option("sqlalchemy.url", TEST_DB_URL)
    return cfg


@pytest.fixture(scope="module")
def migrated_engine(alembic_cfg: Config):
    engine = create_engine(TEST_DB_URL)
    command.upgrade(alembic_cfg, "head")
    yield engine
    command.downgrade(alembic_cfg, "0008")
    engine.dispose()


def _get_columns(engine, table: str) -> dict[str, dict]:
    cols = inspect(engine).get_columns(table)
    return {c["name"]: c for c in cols}


def test_upgrade_adds_nullable_menu_media_fields(migrated_engine) -> None:
    cols = _get_columns(migrated_engine, "menu_items")
    for name in ("media_type", "media_url", "media_poster_url"):
        assert name in cols
        assert cols[name]["nullable"] is True

    with migrated_engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT enumlabel FROM pg_enum "
                "JOIN pg_type ON pg_enum.enumtypid = pg_type.oid "
                "WHERE pg_type.typname = 'menu_media_type' "
                "ORDER BY enumsortorder"
            )
        )
        labels = [row[0] for row in result]
    assert labels == ["image", "video"]


def test_media_migration_does_not_touch_order_or_financial_tables(
    migrated_engine,
) -> None:
    tables_to_check = (
        "order_items",
        "orders",
        "payments",
        "loyalty_accounts",
        "delivery_assignments",
    )
    table_names = set(inspect(migrated_engine).get_table_names())
    for table in tables_to_check:
        if table not in table_names:
            continue
        cols = _get_columns(migrated_engine, table)
        assert {"media_type", "media_url", "media_poster_url"}.isdisjoint(cols)


def test_downgrade_removes_media_fields_and_enum(alembic_cfg: Config) -> None:
    engine = create_engine(TEST_DB_URL)
    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, "0008")

    cols = _get_columns(engine, "menu_items")
    for name in ("media_type", "media_url", "media_poster_url"):
        assert name not in cols

    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT typname FROM pg_type "
                "WHERE typname = 'menu_media_type' AND typtype = 'e'"
            )
        )
        remaining = [row[0] for row in result]
    assert remaining == []
    engine.dispose()
