"""Tests for the guarded Stage 3 menu catalog import seed."""

from __future__ import annotations

import pathlib
import sys

from sqlalchemy import create_engine, text

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
for path in (REPO_ROOT,):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from database.seeds import menu_catalog  # noqa: E402

CATALOG_DIR = REPO_ROOT / "docs" / "shipping-website" / "menu-catalog"


def _create_menu_schema(engine) -> None:
    ddl = (
        """
        CREATE TABLE categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            name_ru TEXT NOT NULL,
            name_en TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            is_visible BOOLEAN NOT NULL DEFAULT true,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE menu_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL REFERENCES categories(id),
            name_ru TEXT NOT NULL,
            name_en TEXT NOT NULL,
            description_ru TEXT,
            description_en TEXT,
            base_price INTEGER NOT NULL DEFAULT 0,
            image_url TEXT,
            available BOOLEAN NOT NULL DEFAULT true,
            archived BOOLEAN NOT NULL DEFAULT false,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            media_type TEXT,
            media_url TEXT,
            media_poster_url TEXT,
            inventory_quantity INTEGER
        )
        """,
        """
        CREATE TABLE modifiers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name_ru TEXT NOT NULL,
            name_en TEXT NOT NULL,
            price INTEGER NOT NULL DEFAULT 0,
            available BOOLEAN NOT NULL DEFAULT true,
            sort_order INTEGER NOT NULL DEFAULT 0
        )
        """,
        """
        CREATE TABLE size_options (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            menu_item_id INTEGER NOT NULL REFERENCES menu_items(id) ON DELETE CASCADE,
            label TEXT NOT NULL,
            price INTEGER NOT NULL DEFAULT 0,
            available BOOLEAN NOT NULL DEFAULT true,
            UNIQUE (menu_item_id, label)
        )
        """,
        """
        CREATE TABLE menu_item_modifiers (
            menu_item_id INTEGER NOT NULL REFERENCES menu_items(id) ON DELETE CASCADE,
            modifier_id INTEGER NOT NULL REFERENCES modifiers(id) ON DELETE CASCADE,
            PRIMARY KEY (menu_item_id, modifier_id)
        )
        """,
    )
    with engine.begin() as conn:
        for statement in ddl:
            conn.execute(text(statement))


def _counts(conn) -> dict[str, int]:
    return {
        "categories": conn.execute(text("SELECT COUNT(*) FROM categories")).scalar_one(),
        "items": conn.execute(text("SELECT COUNT(*) FROM menu_items")).scalar_one(),
        "sizes": conn.execute(text("SELECT COUNT(*) FROM size_options")).scalar_one(),
        "modifiers": conn.execute(text("SELECT COUNT(*) FROM modifiers")).scalar_one(),
        "links": conn.execute(text("SELECT COUNT(*) FROM menu_item_modifiers")).scalar_one(),
    }


def test_menu_catalog_imports_current_packet_idempotently(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AURA_ENV", "test")
    database_url = f"sqlite:///{tmp_path / 'menu.db'}"
    engine = create_engine(database_url)
    _create_menu_schema(engine)
    engine.dispose()

    result = menu_catalog.run(
        database_url,
        catalog_dir=CATALOG_DIR,
        replace_existing=True,
    )
    assert result == {
        "categories": 11,
        "items": 53,
        "sizes": 104,
        "modifiers": 4,
        "item_modifier_links": 28,
    }

    menu_catalog.run(database_url, catalog_dir=CATALOG_DIR, replace_existing=True)

    engine = create_engine(database_url)
    try:
        with engine.connect() as conn:
            assert _counts(conn) == {
                "categories": 11,
                "items": 53,
                "sizes": 104,
                "modifiers": 4,
                "links": 28,
            }
            cappuccino = conn.execute(
                text(
                    """
                    SELECT id, base_price, media_type, media_url, media_poster_url
                    FROM menu_items
                    WHERE name_en = 'Cappuccino'
                    """
                )
            ).mappings().one()
            assert cappuccino["base_price"] == 25000
            assert cappuccino["media_type"] == "video"
            assert cappuccino["media_url"] == "/media/menu/cappuccino/hero.mp4"
            assert cappuccino["media_poster_url"] == "/media/menu/cappuccino/poster.webp"
            sizes = conn.execute(
                text(
                    """
                    SELECT label, price
                    FROM size_options
                    WHERE menu_item_id = :item_id
                    ORDER BY label
                    """
                ),
                {"item_id": cappuccino["id"]},
            ).all()
            assert sizes == [("L", 29900), ("M", 27000), ("S", 25000)]
            link_count = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM menu_item_modifiers
                    WHERE menu_item_id = :item_id
                    """
                ),
                {"item_id": cappuccino["id"]},
            ).scalar_one()
            assert link_count == 4
    finally:
        engine.dispose()
