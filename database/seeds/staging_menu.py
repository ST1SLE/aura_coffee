"""Closed-staging menu seed for production-shaped smoke tests.

This is not the final public catalog. It inserts only non-PII shop settings and
a small draft menu so closed staging can exercise menu, cart, checkout estimate,
and fake-payment order creation before the owner provides the approved menu.

Run manually on closed staging:
    python -m database.seeds.staging_menu
"""

# START_MODULE_CONTRACT
#   PURPOSE: Idempotently seed the minimum closed-staging catalog needed for
#            production-shaped customer smoke tests before final menu assets
#            exist.
#   SCOPE:   STAGING ONLY. Upserts shop_settings, visible draft categories,
#            draft menu items, size options, modifiers, and modifier links.
#            Does not create customers, staff, orders, payments, promos, or
#            PII-bearing rows.
#   DEPENDS: M-DATABASE (menu/shop_settings schema), database.seeds.shop_settings,
#            sqlalchemy, stdlib.
#   LINKS:   docs/shipping-website/README.md Stage 2, PDD §5.2 menu/settings,
#            INV-013, INV-014, INV-015.
#   ROLE:    SCRIPT
#   MAP_MODE: LOCALS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   STAGING_CATEGORIES - draft public category specs
#   STAGING_MODIFIERS  - draft modifier specs
#   STAGING_ITEMS      - draft menu item specs with sizes and modifier keys
#   run                - upsert shop settings and minimal staging menu
# END_MODULE_MAP

from __future__ import annotations

import os
import sys
from typing import Any

from sqlalchemy import create_engine, text

from database.seeds import shop_settings as shop_settings_seed

STAGING_CATEGORIES = (
    {
        "key": "coffee",
        "type": "drink",
        "name_ru": "Кофе (staging)",
        "name_en": "Coffee (staging)",
        "sort_order": 0,
        "is_visible": True,
    },
    {
        "key": "bakery",
        "type": "food",
        "name_ru": "Выпечка (staging)",
        "name_en": "Bakery (staging)",
        "sort_order": 10,
        "is_visible": True,
    },
)

STAGING_MODIFIERS = (
    {
        "key": "oat",
        "name_ru": "Овсяное молоко (staging)",
        "name_en": "Oat milk (staging)",
        "price": 7000,
        "available": True,
        "sort_order": 0,
    },
    {
        "key": "vanilla",
        "name_ru": "Ванильный сироп (staging)",
        "name_en": "Vanilla syrup (staging)",
        "price": 5000,
        "available": True,
        "sort_order": 10,
    },
)

STAGING_ITEMS = (
    {
        "key": "cappuccino",
        "category_key": "coffee",
        "name_ru": "Капучино (staging)",
        "name_en": "Cappuccino (staging)",
        "description_ru": "Черновая позиция для проверки меню, корзины и оплаты.",
        "description_en": "Draft item for menu, cart, and payment smoke tests.",
        "base_price": 52000,
        "available": True,
        "archived": False,
        "sort_order": 0,
        "image_url": None,
        "media_type": "video",
        "media_url": "/media/menu/cappuccino-qa/hero.mp4",
        "media_poster_url": "/media/menu/cappuccino-qa/poster.webp",
        "inventory_quantity": None,
        "sizes": (
            {"label": "S", "price": 52000, "available": True},
            {"label": "M", "price": 60000, "available": True},
            {"label": "L", "price": 68000, "available": True},
        ),
        "modifier_keys": ("oat", "vanilla"),
    },
    {
        "key": "croissant",
        "category_key": "bakery",
        "name_ru": "Круассан (staging)",
        "name_en": "Croissant (staging)",
        "description_ru": "Черновая выпечка без размера для проверки корзины.",
        "description_en": "Draft bakery item without sizes for cart smoke tests.",
        "base_price": 28000,
        "available": True,
        "archived": False,
        "sort_order": 0,
        "image_url": "/media/menu/cappuccino-qa/poster.webp",
        "media_type": None,
        "media_url": None,
        "media_poster_url": None,
        "inventory_quantity": None,
        "sizes": (),
        "modifier_keys": (),
    },
)


def _category_id(conn, spec: dict[str, Any]) -> int:
    params = {
        "type": spec["type"],
        "name_ru": spec["name_ru"],
        "name_en": spec["name_en"],
        "sort_order": spec["sort_order"],
        "is_visible": spec["is_visible"],
    }
    existing = conn.execute(
        text("SELECT id FROM categories WHERE name_en = :name_en"),
        {"name_en": params["name_en"]},
    ).first()
    if existing is not None:
        conn.execute(
            text(
                """
                UPDATE categories
                SET type = :type, name_ru = :name_ru, sort_order = :sort_order,
                    is_visible = :is_visible, updated_at = now()
                WHERE id = :id
                """
            ),
            {**params, "id": existing.id},
        )
        return int(existing.id)

    return int(
        conn.execute(
            text(
                """
                INSERT INTO categories (
                    type, name_ru, name_en, sort_order, is_visible
                )
                VALUES (:type, :name_ru, :name_en, :sort_order, :is_visible)
                RETURNING id
                """
            ),
            params,
        ).scalar_one()
    )


def _modifier_id(conn, spec: dict[str, Any]) -> int:
    params = {
        "name_ru": spec["name_ru"],
        "name_en": spec["name_en"],
        "price": spec["price"],
        "available": spec["available"],
        "sort_order": spec["sort_order"],
    }
    existing = conn.execute(
        text("SELECT id FROM modifiers WHERE name_en = :name_en"),
        {"name_en": params["name_en"]},
    ).first()
    if existing is not None:
        conn.execute(
            text(
                """
                UPDATE modifiers
                SET name_ru = :name_ru, price = :price, available = :available,
                    sort_order = :sort_order
                WHERE id = :id
                """
            ),
            {**params, "id": existing.id},
        )
        return int(existing.id)

    return int(
        conn.execute(
            text(
                """
                INSERT INTO modifiers (name_ru, name_en, price, available, sort_order)
                VALUES (:name_ru, :name_en, :price, :available, :sort_order)
                RETURNING id
                """
            ),
            params,
        ).scalar_one()
    )


def _menu_item_id(conn, *, category_id: int, spec: dict[str, Any]) -> int:
    existing = conn.execute(
        text("SELECT id FROM menu_items WHERE name_en = :name_en"),
        {"name_en": spec["name_en"]},
    ).first()
    params = {
        "category_id": category_id,
        "name_ru": spec["name_ru"],
        "name_en": spec["name_en"],
        "description_ru": spec["description_ru"],
        "description_en": spec["description_en"],
        "base_price": spec["base_price"],
        "available": spec["available"],
        "archived": spec["archived"],
        "sort_order": spec["sort_order"],
        "image_url": spec["image_url"],
        "media_type": spec["media_type"],
        "media_url": spec["media_url"],
        "media_poster_url": spec["media_poster_url"],
        "inventory_quantity": spec["inventory_quantity"],
    }
    if existing is not None:
        conn.execute(
            text(
                """
                UPDATE menu_items
                SET category_id = :category_id, name_ru = :name_ru,
                    description_ru = :description_ru,
                    description_en = :description_en, base_price = :base_price,
                    available = :available, archived = :archived,
                    sort_order = :sort_order, image_url = :image_url,
                    media_type = :media_type, media_url = :media_url,
                    media_poster_url = :media_poster_url,
                    inventory_quantity = :inventory_quantity,
                    updated_at = now()
                WHERE id = :id
                """
            ),
            {**params, "id": existing.id},
        )
        return int(existing.id)

    return int(
        conn.execute(
            text(
                """
                INSERT INTO menu_items (
                    category_id, name_ru, name_en, description_ru, description_en,
                    base_price, available, archived, sort_order, image_url,
                    media_type, media_url, media_poster_url, inventory_quantity
                )
                VALUES (
                    :category_id, :name_ru, :name_en, :description_ru,
                    :description_en, :base_price, :available, :archived,
                    :sort_order, :image_url, :media_type, :media_url,
                    :media_poster_url, :inventory_quantity
                )
                RETURNING id
                """
            ),
            params,
        ).scalar_one()
    )


def _size_id(conn, *, menu_item_id: int, spec: dict[str, Any]) -> int:
    existing = conn.execute(
        text(
            """
            SELECT id FROM size_options
            WHERE menu_item_id = :menu_item_id AND label = :label
            """
        ),
        {"menu_item_id": menu_item_id, "label": spec["label"]},
    ).first()
    if existing is not None:
        conn.execute(
            text(
                """
                UPDATE size_options
                SET price = :price, available = :available
                WHERE id = :id
                """
            ),
            {**spec, "id": existing.id},
        )
        return int(existing.id)

    return int(
        conn.execute(
            text(
                """
                INSERT INTO size_options (menu_item_id, label, price, available)
                VALUES (:menu_item_id, :label, :price, :available)
                RETURNING id
                """
            ),
            {**spec, "menu_item_id": menu_item_id},
        ).scalar_one()
    )


def _link_modifier(conn, *, menu_item_id: int, modifier_id: int) -> None:
    conn.execute(
        text(
            """
            INSERT INTO menu_item_modifiers (menu_item_id, modifier_id)
            VALUES (:menu_item_id, :modifier_id)
            ON CONFLICT DO NOTHING
            """
        ),
        {"menu_item_id": menu_item_id, "modifier_id": modifier_id},
    )


# START_CONTRACT: run
#   PURPOSE: Upsert the closed-staging shop settings and minimal draft menu.
#   INPUTS:  database_url: str | None — explicit connection URL; falls back to
#            os.environ["DATABASE_URL"] when None.
#   OUTPUTS: None.
#   SIDE_EFFECTS: INSERT/UPDATE categories, menu_items, size_options,
#                 modifiers, menu_item_modifiers, and shop_settings. No PII,
#                 staff, order, payment, loyalty, promo, or notification rows.
#   LINKS:   docs/shipping-website/README.md Stage 2, PDD §5.2, INV-013,
#            INV-014, INV-015.
# END_CONTRACT: run
def run(database_url: str | None = None) -> None:
    url = database_url or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")

    shop_settings_seed.run(url)

    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            category_ids = {
                spec["key"]: _category_id(conn, spec) for spec in STAGING_CATEGORIES
            }
            modifier_ids = {
                spec["key"]: _modifier_id(conn, spec) for spec in STAGING_MODIFIERS
            }
            for item_spec in STAGING_ITEMS:
                item_id = _menu_item_id(
                    conn,
                    category_id=category_ids[item_spec["category_key"]],
                    spec=item_spec,
                )
                for size_spec in item_spec["sizes"]:
                    _size_id(conn, menu_item_id=item_id, spec=size_spec)
                for modifier_key in item_spec["modifier_keys"]:
                    _link_modifier(
                        conn,
                        menu_item_id=item_id,
                        modifier_id=modifier_ids[modifier_key],
                    )
    finally:
        engine.dispose()


if __name__ == "__main__":
    run()
    sys.stdout.write("staging_menu seed applied\n")
