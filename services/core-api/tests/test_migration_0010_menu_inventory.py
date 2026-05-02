"""Migration 0010: finite inventory field on menu_items."""

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
    command.downgrade(alembic_cfg, "0009")
    engine.dispose()


def _columns(engine, table: str) -> dict[str, dict]:
    return {c["name"]: c for c in inspect(engine).get_columns(table)}


def test_upgrade_adds_nullable_inventory_quantity_with_check(migrated_engine) -> None:
    cols = _columns(migrated_engine, "menu_items")
    assert "inventory_quantity" in cols
    assert cols["inventory_quantity"]["nullable"] is True

    with migrated_engine.connect() as conn:
        tx = conn.begin()
        try:
            category_id = conn.execute(
                text(
                    "INSERT INTO categories (type, name_ru, name_en) "
                    "VALUES ('food', 'Еда', 'Food') RETURNING id"
                )
            ).scalar_one()
            with pytest.raises(Exception):
                conn.execute(
                    text(
                        "INSERT INTO menu_items "
                        "(category_id, name_ru, name_en, base_price, inventory_quantity) "
                        "VALUES (:category_id, 'x', 'x', 100, -1)"
                    ),
                    {"category_id": category_id},
                )
        finally:
            tx.rollback()


def test_downgrade_removes_inventory_quantity(alembic_cfg: Config) -> None:
    engine = create_engine(TEST_DB_URL)
    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, "0009")

    cols = _columns(engine, "menu_items")
    assert "inventory_quantity" not in cols
    engine.dispose()
