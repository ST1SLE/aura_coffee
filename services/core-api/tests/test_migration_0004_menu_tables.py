"""RED: тесты миграции 0004_menu_tables.

Требуют реального PostgreSQL. Используют TEST_DATABASE_URL из env
(или DATABASE_URL, если он указывает на Postgres).
Пропускаются при SQLite (нельзя проверять PG-специфичные типы).

Все тесты ДОЛЖНЫ падать с AssertionError до создания миграции 0004.
"""

import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


# Путь к alembic.ini относительно корня репозитория
ALEMBIC_INI = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "database", "alembic.ini"
)

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL", "")


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


@pytest.fixture(scope="module")
def alembic_cfg() -> Config:
    if _is_sqlite(TEST_DB_URL):
        pytest.skip("Тесты миграции требуют PostgreSQL, пропущено при SQLite")
    cfg = Config(ALEMBIC_INI)
    cfg.set_main_option("sqlalchemy.url", TEST_DB_URL)
    return cfg


@pytest.fixture(scope="module")
def migrated_engine(alembic_cfg: Config):
    """Запускает upgrade head, возвращает engine. После модуля — rollback к 0003."""
    engine = create_engine(TEST_DB_URL)
    command.upgrade(alembic_cfg, "head")
    yield engine
    command.downgrade(alembic_cfg, "0003")
    engine.dispose()


def _get_table_names(engine) -> list[str]:
    return inspect(engine).get_table_names()


def _get_columns(engine, table: str) -> dict[str, dict]:
    cols = inspect(engine).get_columns(table)
    return {c["name"]: c for c in cols}


def _get_pk_constraint(engine, table: str) -> dict:
    return inspect(engine).get_pk_constraint(table)


def _get_foreign_keys(engine, table: str) -> list[dict]:
    return inspect(engine).get_foreign_keys(table)


def _get_unique_constraints(engine, table: str) -> list[dict]:
    return inspect(engine).get_unique_constraints(table)


def _get_indexes(engine, table: str) -> list[dict]:
    return inspect(engine).get_indexes(table)


# ---------------------------------------------------------------------------
# 3.1 categories
# ---------------------------------------------------------------------------

def test_upgrade_creates_categories_table(migrated_engine) -> None:
    assert "categories" in _get_table_names(migrated_engine)

    cols = _get_columns(migrated_engine, "categories")
    assert set(cols) >= {"id", "type", "name_ru", "name_en", "sort_order", "is_visible", "created_at", "updated_at"}

    # PG enum category_type с нужными значениями
    with migrated_engine.connect() as conn:
        result = conn.execute(
            text("SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_enum.enumtypid = pg_type.oid WHERE pg_type.typname = 'category_type' ORDER BY enumsortorder")
        )
        labels = [row[0] for row in result]
    assert labels == ["drink", "food", "merch", "modifier"]


# ---------------------------------------------------------------------------
# 3.2 menu_items
# ---------------------------------------------------------------------------

def test_upgrade_creates_menu_items_table(migrated_engine) -> None:
    assert "menu_items" in _get_table_names(migrated_engine)

    cols = _get_columns(migrated_engine, "menu_items")
    required = {
        "id", "category_id", "name_ru", "name_en",
        "description_ru", "description_en", "base_price",
        "image_url", "available", "archived", "sort_order",
        "created_at", "updated_at",
    }
    assert set(cols) >= required

    # nullable columns
    assert cols["description_ru"]["nullable"] is True
    assert cols["description_en"]["nullable"] is True
    assert cols["image_url"]["nullable"] is True

    # defaults
    assert cols["available"]["default"] is not None
    assert cols["archived"]["default"] is not None

    # FK → categories.id ON DELETE RESTRICT
    fks = _get_foreign_keys(migrated_engine, "menu_items")
    cat_fk = next((fk for fk in fks if "categories" in fk["referred_table"]), None)
    assert cat_fk is not None, "Нет FK на categories"
    assert cat_fk["options"].get("ondelete", "").upper() in ("RESTRICT", "NO ACTION")

    # CHECK base_price >= 0
    with migrated_engine.connect() as conn:
        try:
            conn.execute(text("INSERT INTO menu_items (category_id, name_ru, name_en, base_price) VALUES (1, 'x', 'x', -1)"))
            conn.rollback()
            pytest.fail("CHECK base_price >= 0 не работает")
        except Exception:
            conn.rollback()


# ---------------------------------------------------------------------------
# 3.3 size_options
# ---------------------------------------------------------------------------

def test_upgrade_creates_size_options_table(migrated_engine) -> None:
    assert "size_options" in _get_table_names(migrated_engine)

    cols = _get_columns(migrated_engine, "size_options")
    assert set(cols) >= {"id", "menu_item_id", "label", "price", "available"}

    # FK → menu_items.id ON DELETE CASCADE
    fks = _get_foreign_keys(migrated_engine, "size_options")
    item_fk = next((fk for fk in fks if "menu_items" in fk["referred_table"]), None)
    assert item_fk is not None
    assert item_fk["options"].get("ondelete", "").upper() == "CASCADE"

    # UNIQUE (menu_item_id, label)
    uqs = _get_unique_constraints(migrated_engine, "size_options")
    unique_cols = [set(uq["column_names"]) for uq in uqs]
    assert {"menu_item_id", "label"} in unique_cols

    # PG enum size_label
    with migrated_engine.connect() as conn:
        result = conn.execute(
            text("SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_enum.enumtypid = pg_type.oid WHERE pg_type.typname = 'size_label' ORDER BY enumsortorder")
        )
        labels = [row[0] for row in result]
    assert labels == ["S", "M", "L"]

    # CHECK price >= 0
    with migrated_engine.connect() as conn:
        try:
            conn.execute(text("INSERT INTO size_options (menu_item_id, label, price) VALUES (1, 'S', -1)"))
            conn.rollback()
            pytest.fail("CHECK price >= 0 не работает")
        except Exception:
            conn.rollback()


# ---------------------------------------------------------------------------
# 3.4 modifiers
# ---------------------------------------------------------------------------

def test_upgrade_creates_modifiers_table(migrated_engine) -> None:
    assert "modifiers" in _get_table_names(migrated_engine)

    cols = _get_columns(migrated_engine, "modifiers")
    assert set(cols) >= {"id", "name_ru", "name_en", "price", "available", "sort_order"}
    # Нет group_id и нет modifier_groups
    assert "group_id" not in cols
    assert "modifier_groups" not in _get_table_names(migrated_engine)

    # CHECK price >= 0
    with migrated_engine.connect() as conn:
        try:
            conn.execute(text("INSERT INTO modifiers (name_ru, name_en, price) VALUES ('x', 'x', -1)"))
            conn.rollback()
            pytest.fail("CHECK price >= 0 не работает")
        except Exception:
            conn.rollback()


# ---------------------------------------------------------------------------
# 3.5 menu_item_modifiers (junction)
# ---------------------------------------------------------------------------

def test_upgrade_creates_junction_table(migrated_engine) -> None:
    assert "menu_item_modifiers" in _get_table_names(migrated_engine)

    pk = _get_pk_constraint(migrated_engine, "menu_item_modifiers")
    assert set(pk["constrained_columns"]) == {"menu_item_id", "modifier_id"}

    fks = _get_foreign_keys(migrated_engine, "menu_item_modifiers")
    tables = {fk["referred_table"] for fk in fks}
    assert "menu_items" in tables
    assert "modifiers" in tables

    for fk in fks:
        assert fk["options"].get("ondelete", "").upper() == "CASCADE", (
            f"FK на {fk['referred_table']} должен иметь ON DELETE CASCADE"
        )


# ---------------------------------------------------------------------------
# 3.6 indexes
# ---------------------------------------------------------------------------

def test_upgrade_creates_indexes(migrated_engine) -> None:
    item_indexes = {idx["name"]: idx for idx in _get_indexes(migrated_engine, "menu_items")}

    assert "ix_menu_items_category_sort" in item_indexes, "Индекс ix_menu_items_category_sort не создан"
    assert set(item_indexes["ix_menu_items_category_sort"]["column_names"]) == {"category_id", "sort_order"}

    assert "ix_menu_items_active" in item_indexes, "Partial-индекс ix_menu_items_active не создан"
    # Partial index dialect_options хранит выражение WHERE
    partial_idx = item_indexes["ix_menu_items_active"]
    dialect_opts = partial_idx.get("dialect_options", {})
    postgresql_where = dialect_opts.get("postgresql_where", "")
    assert "archived" in str(postgresql_where).lower(), (
        f"Partial index должен содержать 'archived' в предикате, получено: {postgresql_where!r}"
    )

    size_indexes = {idx["name"]: idx for idx in _get_indexes(migrated_engine, "size_options")}
    assert "ix_size_options_menu_item" in size_indexes, "Индекс ix_size_options_menu_item не создан"


# ---------------------------------------------------------------------------
# 3.7 downgrade removes everything
# ---------------------------------------------------------------------------

def test_downgrade_removes_everything(alembic_cfg: Config) -> None:
    """Отдельный прогон: up → down → проверяем отсутствие таблиц и enum-ов."""
    engine = create_engine(TEST_DB_URL)
    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, "0003")

    tables = _get_table_names(engine)
    for table in ("categories", "menu_items", "size_options", "modifiers", "menu_item_modifiers"):
        assert table not in tables, f"Таблица {table} должна быть удалена после downgrade"

    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT typname FROM pg_type WHERE typname IN ('category_type', 'size_label') AND typtype = 'e'")
        )
        remaining = [row[0] for row in result]
    assert remaining == [], f"Enum-ы должны быть удалены после downgrade: {remaining}"

    engine.dispose()
