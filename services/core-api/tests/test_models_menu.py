"""RED: тесты SQLAlchemy-моделей меню в shared.models.menu.

Тесты ДОЛЖНЫ падать с AttributeError до добавления классов в menu.py.
Тесты на relationships (4.5–4.7) требуют PostgreSQL и пропускаются на SQLite.
"""

import os

import pytest
import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL", "")

_IS_SQLITE = TEST_DB_URL.startswith("sqlite")


# ---------------------------------------------------------------------------
# 4.1 Category
# ---------------------------------------------------------------------------

def test_category_model_declares_columns() -> None:
    from shared.models.menu import Category

    mapper = sa_inspect(Category)
    col_names = {c.key for c in mapper.mapper.columns}
    assert col_names >= {"id", "type", "name_ru", "name_en", "sort_order", "is_visible", "created_at", "updated_at"}
    assert mapper.mapper.mapped_table.name == "categories"


# ---------------------------------------------------------------------------
# 4.2 MenuItem
# ---------------------------------------------------------------------------

def test_menu_item_model_declares_columns() -> None:
    from shared.models.menu import MenuItem

    mapper = sa_inspect(MenuItem)
    col_names = {c.key for c in mapper.mapper.columns}
    required = {
        "id", "category_id", "name_ru", "name_en",
        "description_ru", "description_en", "base_price",
        "image_url", "available", "archived", "sort_order",
        "created_at", "updated_at",
    }
    assert col_names >= required
    assert mapper.mapper.mapped_table.name == "menu_items"

    # FK на categories.id
    fk_tables = {
        list(col.foreign_keys)[0].column.table.name
        for col in mapper.mapper.columns
        if col.foreign_keys
    }
    assert "categories" in fk_tables


# ---------------------------------------------------------------------------
# 4.3 SizeOption
# ---------------------------------------------------------------------------

def test_size_option_model_declares_columns() -> None:
    from shared.models.menu import SizeOption

    mapper = sa_inspect(SizeOption)
    col_names = {c.key for c in mapper.mapper.columns}
    assert col_names >= {"id", "menu_item_id", "label", "price", "available"}
    assert mapper.mapper.mapped_table.name == "size_options"

    # FK на menu_items.id
    fk_tables = {
        list(col.foreign_keys)[0].column.table.name
        for col in mapper.mapper.columns
        if col.foreign_keys
    }
    assert "menu_items" in fk_tables


# ---------------------------------------------------------------------------
# 4.4 Modifier (без group_id)
# ---------------------------------------------------------------------------

def test_modifier_model_declares_columns() -> None:
    from shared.models.menu import Modifier

    mapper = sa_inspect(Modifier)
    col_names = {c.key for c in mapper.mapper.columns}
    assert col_names >= {"id", "name_ru", "name_en", "price", "available", "sort_order"}
    assert "group_id" not in col_names
    assert mapper.mapper.mapped_table.name == "modifiers"


# ---------------------------------------------------------------------------
# 4.5 Category.menu_items relationship
# ---------------------------------------------------------------------------

@pytest.mark.skipif(_IS_SQLITE, reason="Тест на relationships требует PostgreSQL")
def test_category_menu_items_relationship(migrated_db_session) -> None:
    from shared.models.menu import Category, MenuItem

    cat = Category(type="drink", name_ru="Напитки", name_en="Drinks")
    migrated_db_session.add(cat)
    migrated_db_session.flush()

    item1 = MenuItem(category_id=cat.id, name_ru="Латте", name_en="Latte", base_price=35000)
    item2 = MenuItem(category_id=cat.id, name_ru="Капучино", name_en="Cappuccino", base_price=32000)
    migrated_db_session.add_all([item1, item2])
    migrated_db_session.flush()

    migrated_db_session.refresh(cat)
    assert len(cat.menu_items) == 2


# ---------------------------------------------------------------------------
# 4.6 SizeOption CASCADE delete
# ---------------------------------------------------------------------------

@pytest.mark.skipif(_IS_SQLITE, reason="Тест на cascade требует PostgreSQL")
def test_menu_item_size_options_cascade_delete(migrated_db_session) -> None:
    from shared.models.menu import Category, MenuItem, SizeOption

    cat = Category(type="drink", name_ru="Напитки", name_en="Drinks")
    migrated_db_session.add(cat)
    migrated_db_session.flush()

    item = MenuItem(category_id=cat.id, name_ru="Латте", name_en="Latte", base_price=35000)
    migrated_db_session.add(item)
    migrated_db_session.flush()

    size = SizeOption(menu_item_id=item.id, label="M", price=35000)
    migrated_db_session.add(size)
    migrated_db_session.flush()
    size_id = size.id

    migrated_db_session.delete(item)
    migrated_db_session.flush()
    migrated_db_session.expire_all()  # сбрасываем кэш сессии, чтобы получить актуальные данные из БД

    result = migrated_db_session.get(SizeOption, size_id)
    assert result is None, "SizeOption должен быть удалён вместе с MenuItem (CASCADE)"


# ---------------------------------------------------------------------------
# 4.7 MenuItem ↔ Modifier M:N
# ---------------------------------------------------------------------------

@pytest.mark.skipif(_IS_SQLITE, reason="Тест на M:N требует PostgreSQL")
def test_menu_item_modifiers_many_to_many(migrated_db_session) -> None:
    from shared.models.menu import Category, MenuItem, Modifier

    cat = Category(type="drink", name_ru="Напитки", name_en="Drinks")
    migrated_db_session.add(cat)
    migrated_db_session.flush()

    item = MenuItem(category_id=cat.id, name_ru="Латте", name_en="Latte", base_price=35000)
    mod1 = Modifier(name_ru="Сироп ваниль", name_en="Vanilla syrup", price=5000)
    mod2 = Modifier(name_ru="Доп. шот", name_en="Extra shot", price=7000)
    migrated_db_session.add_all([item, mod1, mod2])
    migrated_db_session.flush()

    item.modifiers.append(mod1)
    item.modifiers.append(mod2)
    migrated_db_session.flush()

    migrated_db_session.refresh(item)
    assert len(item.modifiers) == 2
