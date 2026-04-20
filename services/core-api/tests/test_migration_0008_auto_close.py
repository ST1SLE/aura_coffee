"""RED: тесты миграции 0008_shop_settings_auto_close (PDD §6.1, §7.1 Phase 6).

Миграция добавляет колонку shop_settings.auto_close_minutes INTEGER NOT NULL
DEFAULT 60. Требует реальный PostgreSQL (TEST_DATABASE_URL). На sqlite —
skip. Все тесты ДОЛЖНЫ падать до создания 0008 и обновления seed-а.
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
        pytest.skip("Тесты миграции требуют PostgreSQL")
    cfg = Config(ALEMBIC_INI)
    cfg.set_main_option("sqlalchemy.url", TEST_DB_URL)
    return cfg


@pytest.fixture(scope="module")
def upgraded_engine(alembic_cfg: Config):
    """upgrade head → колонка auto_close_minutes должна появиться."""
    engine = create_engine(TEST_DB_URL)
    command.upgrade(alembic_cfg, "head")
    yield engine
    # teardown — downgrade до 0007, чтобы не оставлять колонку другим тестам
    command.downgrade(alembic_cfg, "0007")
    engine.dispose()


def _shop_settings_columns(engine) -> dict[str, dict]:
    return {c["name"]: c for c in inspect(engine).get_columns("shop_settings")}


def test_upgrade_adds_auto_close_minutes_column(upgraded_engine) -> None:
    """2.1 — upgrade head создаёт колонку auto_close_minutes."""
    cols = _shop_settings_columns(upgraded_engine)
    assert "auto_close_minutes" in cols, (
        "Миграция 0008 должна добавить shop_settings.auto_close_minutes"
    )

    col = cols["auto_close_minutes"]
    col_type = str(col["type"]).upper()
    assert "INT" in col_type, (
        f"auto_close_minutes должен быть INTEGER, получено: {col_type}"
    )
    assert col["nullable"] is False, "auto_close_minutes должен быть NOT NULL"

    default = str(col.get("default") or "").lower()
    assert "60" in default, (
        f"auto_close_minutes должен иметь server default 60, получено: {default!r}"
    )


def test_downgrade_drops_auto_close_minutes_column(alembic_cfg: Config) -> None:
    """2.2 — отдельный прогон: up → down до 0007 → колонка исчезла."""
    if _IS_SQLITE:
        pytest.skip("Тесты миграции требуют PostgreSQL")

    engine = create_engine(TEST_DB_URL)
    try:
        command.upgrade(alembic_cfg, "head")
        command.downgrade(alembic_cfg, "0007")

        cols = _shop_settings_columns(engine)
        assert "auto_close_minutes" not in cols, (
            "downgrade 0008→0007 должен убрать колонку auto_close_minutes"
        )
    finally:
        # Возвращаем БД в head, чтобы другие тесты не падали.
        command.upgrade(alembic_cfg, "head")
        engine.dispose()


def test_seed_row_has_auto_close_default(upgraded_engine) -> None:
    """2.3 — seed singleton-строки проставляет auto_close_minutes=60."""
    from database.seeds.shop_settings import run

    run(TEST_DB_URL)

    with upgraded_engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT id, auto_close_minutes FROM shop_settings WHERE id = 1"
            )
        ).one()

    assert row.id == 1
    assert row.auto_close_minutes == 60, (
        f"seed должен проставить auto_close_minutes=60, получено: {row.auto_close_minutes}"
    )
