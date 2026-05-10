"""Import the reviewed Stage 3 menu catalog CSV packet.

Run on closed staging after validating `docs/shipping-website/menu-catalog`:
    ALLOW_MENU_CATALOG_IMPORT=1 python -m database.seeds.menu_catalog \
      --catalog-dir docs/shipping-website/menu-catalog \
      --replace-existing
"""

# START_MODULE_CONTRACT
#   PURPOSE: Guarded import for the owner-filled menu/media CSV packet used to
#            replace the closed-staging draft menu before customer smoke tests.
#   SCOPE:   Upserts categories, menu items, size options, modifiers, and
#            item/modifier links from CSV files. Optionally hides existing menu
#            categories/items first. Does not touch orders, order_items,
#            payments, users, staff, loyalty, promocodes, notifications, SMS,
#            or provider secrets.
#   DEPENDS: SQLAlchemy, stdlib csv/argparse, database menu schema.
#   LINKS:   docs/shipping-website/README.md Stage 3, PDD §5.2,
#            database/AGENTS.md seed data, INV-013, INV-014, INV-015.
#   ROLE:    SCRIPT
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   Catalog        - parsed CSV packet container
#   load_catalog   - read and normalize menu catalog CSV files
#   run            - guarded DB import entry point
#   main           - CLI entry point
# END_MODULE_MAP

from __future__ import annotations

import argparse
import csv
import os
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import bindparam, create_engine, text

ALLOWED_ENV_VALUES = {"dev", "development", "local", "test", "staging"}

CSV_FILES = {
    "categories.csv",
    "items.csv",
    "sizes.csv",
    "modifiers.csv",
    "item_modifiers.csv",
}


# START_CONTRACT: Catalog
#   PURPOSE: Hold normalized row groups from the Stage 3 menu catalog CSV packet.
#   INPUTS:  categories/items/sizes/modifiers/item_modifiers — parsed CSV rows.
#   OUTPUTS: Catalog instance used by the guarded import path.
#   SIDE_EFFECTS: none.
#   LINKS:   docs/shipping-website/menu-catalog/README.md, PDD §5.2.
# END_CONTRACT: Catalog
@dataclass(frozen=True)
class Catalog:
    categories: list[dict[str, str]]
    items: list[dict[str, str]]
    sizes: list[dict[str, str]]
    modifiers: list[dict[str, str]]
    item_modifiers: list[dict[str, str]]


def _read_csv(catalog_dir: Path, filename: str) -> list[dict[str, str]]:
    path = catalog_dir / filename
    with path.open(newline="", encoding="utf-8") as handle:
        return [
            {key: (value or "").strip() for key, value in row.items()}
            for row in csv.DictReader(handle)
        ]


def _as_bool(value: str) -> bool:
    return value.strip().lower() == "true"


def _as_int(value: str) -> int:
    return int(value.strip())


def _blank_as_none(value: str) -> str | None:
    normalized = value.strip()
    return normalized or None


def _guard_environment() -> None:
    env_value = (
        os.environ.get("AURA_ENV") or os.environ.get("APP_ENV") or ""
    ).lower()
    if os.environ.get("ALLOW_MENU_CATALOG_IMPORT") == "1" or env_value in ALLOWED_ENV_VALUES:
        return
    raise RuntimeError(
        "Refusing menu catalog import outside dev/test/local/staging. Set "
        "ALLOW_MENU_CATALOG_IMPORT=1 for an intentional closed-staging import."
    )


# START_CONTRACT: load_catalog
#   PURPOSE: Read normalized Stage 3 menu catalog CSV rows from disk.
#   INPUTS:  catalog_dir: Path — directory containing the five required CSVs.
#   OUTPUTS: Catalog — in-memory row groups keyed by file role.
#   SIDE_EFFECTS: Reads CSV files only; no DB writes.
#   LINKS:   docs/shipping-website/menu-catalog/README.md.
# END_CONTRACT: load_catalog
def load_catalog(catalog_dir: Path) -> Catalog:
    missing = sorted(filename for filename in CSV_FILES if not (catalog_dir / filename).is_file())
    if missing:
        raise RuntimeError(f"catalog is missing required files: {', '.join(missing)}")
    return Catalog(
        categories=_read_csv(catalog_dir, "categories.csv"),
        items=_read_csv(catalog_dir, "items.csv"),
        sizes=_read_csv(catalog_dir, "sizes.csv"),
        modifiers=_read_csv(catalog_dir, "modifiers.csv"),
        item_modifiers=_read_csv(catalog_dir, "item_modifiers.csv"),
    )


def _hide_existing_menu(conn) -> None:
    conn.execute(
        text(
            """
            UPDATE menu_items
            SET available = false, archived = true, updated_at = CURRENT_TIMESTAMP
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE categories
            SET is_visible = false, updated_at = CURRENT_TIMESTAMP
            """
        )
    )


def _category_id(conn, row: dict[str, str]) -> int:
    params = {
        "type": row["type"],
        "name_ru": row["name_ru"],
        "name_en": row["name_en"],
        "sort_order": _as_int(row["sort_order"]),
        "is_visible": _as_bool(row["is_visible"]),
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
                    is_visible = :is_visible, updated_at = CURRENT_TIMESTAMP
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


def _modifier_id(conn, row: dict[str, str]) -> int:
    params = {
        "name_ru": row["name_ru"],
        "name_en": row["name_en"],
        "price": _as_int(row["price_kopecks"]),
        "available": _as_bool(row["available"]),
        "sort_order": _as_int(row["sort_order"]),
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


def _menu_item_id(conn, *, category_id: int, row: dict[str, str]) -> int:
    params = {
        "category_id": category_id,
        "name_ru": row["name_ru"],
        "name_en": row["name_en"],
        "description_ru": _blank_as_none(row["description_ru"]),
        "description_en": _blank_as_none(row["description_en"]),
        "base_price": _as_int(row["base_price_kopecks"]),
        "available": _as_bool(row["available"]),
        "archived": _as_bool(row["archived"]),
        "sort_order": _as_int(row["sort_order"]),
        "image_url": _blank_as_none(row["image_url"]),
        "media_type": _blank_as_none(row["media_type"]),
        "media_url": _blank_as_none(row["media_url"]),
        "media_poster_url": _blank_as_none(row["media_poster_url"]),
        "inventory_quantity": (
            None if row["inventory_quantity"] == "" else _as_int(row["inventory_quantity"])
        ),
    }
    existing = conn.execute(
        text("SELECT id FROM menu_items WHERE name_en = :name_en"),
        {"name_en": params["name_en"]},
    ).first()
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
                    updated_at = CURRENT_TIMESTAMP
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


def _sync_sizes(conn, *, menu_item_id: int, rows: list[dict[str, str]]) -> None:
    labels = tuple(row["size_label"] for row in rows)
    if labels:
        stmt = text(
            """
            DELETE FROM size_options
            WHERE menu_item_id = :menu_item_id AND label NOT IN :labels
            """
        ).bindparams(bindparam("labels", expanding=True))
        conn.execute(stmt, {"menu_item_id": menu_item_id, "labels": labels})
    else:
        conn.execute(
            text("DELETE FROM size_options WHERE menu_item_id = :menu_item_id"),
            {"menu_item_id": menu_item_id},
        )

    for row in rows:
        params = {
            "menu_item_id": menu_item_id,
            "label": row["size_label"],
            "price": _as_int(row["price_kopecks"]),
            "available": _as_bool(row["available"]),
        }
        existing = conn.execute(
            text(
                """
                SELECT id FROM size_options
                WHERE menu_item_id = :menu_item_id AND label = :label
                """
            ),
            params,
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
                {**params, "id": existing.id},
            )
            continue
        conn.execute(
            text(
                """
                INSERT INTO size_options (menu_item_id, label, price, available)
                VALUES (:menu_item_id, :label, :price, :available)
                """
            ),
            params,
        )


def _sync_modifier_links(
    conn,
    *,
    menu_item_id: int,
    modifier_ids: list[int],
) -> None:
    conn.execute(
        text("DELETE FROM menu_item_modifiers WHERE menu_item_id = :menu_item_id"),
        {"menu_item_id": menu_item_id},
    )
    for modifier_id in modifier_ids:
        conn.execute(
            text(
                """
                INSERT INTO menu_item_modifiers (menu_item_id, modifier_id)
                VALUES (:menu_item_id, :modifier_id)
                """
            ),
            {"menu_item_id": menu_item_id, "modifier_id": modifier_id},
        )


# START_CONTRACT: run
#   PURPOSE: Import the owner-reviewed menu catalog into a guarded database.
#   INPUTS:  database_url: str | None — explicit DB URL or DATABASE_URL env.
#            catalog_dir: Path | None — CSV packet directory.
#            replace_existing: bool — archive/hide existing menu rows first.
#   OUTPUTS: dict[str, int] — imported row counts by catalog role.
#   SIDE_EFFECTS: INSERT/UPDATE categories, menu_items, size_options,
#                 modifiers, menu_item_modifiers. When replace_existing is
#                 true, archives existing menu_items and hides categories
#                 before importing. No PII, secrets, orders, or order_items are
#                 touched.
#   LINKS:   docs/shipping-website/README.md Stage 3, PDD §5.2, INV-014.
# END_CONTRACT: run
def run(
    database_url: str | None = None,
    *,
    catalog_dir: Path | None = None,
    replace_existing: bool = False,
) -> dict[str, int]:
    _guard_environment()

    url = database_url or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")

    catalog_path = catalog_dir or Path("docs/shipping-website/menu-catalog")
    catalog = load_catalog(catalog_path)
    sizes_by_item: dict[str, list[dict[str, str]]] = {}
    for row in catalog.sizes:
        sizes_by_item.setdefault(row["item_code"], []).append(row)
    modifier_codes_by_item: dict[str, list[str]] = {}
    for row in catalog.item_modifiers:
        modifier_codes_by_item.setdefault(row["item_code"], []).append(row["modifier_code"])

    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            if replace_existing:
                _hide_existing_menu(conn)

            category_ids = {
                row["category_code"]: _category_id(conn, row)
                for row in catalog.categories
            }
            modifier_ids = {
                row["modifier_code"]: _modifier_id(conn, row)
                for row in catalog.modifiers
            }

            for row in catalog.items:
                item_id = _menu_item_id(
                    conn,
                    category_id=category_ids[row["category_code"]],
                    row=row,
                )
                _sync_sizes(
                    conn,
                    menu_item_id=item_id,
                    rows=sizes_by_item.get(row["item_code"], []),
                )
                _sync_modifier_links(
                    conn,
                    menu_item_id=item_id,
                    modifier_ids=[
                        modifier_ids[code]
                        for code in modifier_codes_by_item.get(row["item_code"], [])
                    ],
                )
    finally:
        engine.dispose()

    return {
        "categories": len(catalog.categories),
        "items": len(catalog.items),
        "sizes": len(catalog.sizes),
        "modifiers": len(catalog.modifiers),
        "item_modifier_links": len(catalog.item_modifiers),
    }


# START_CONTRACT: main
#   PURPOSE: CLI wrapper for the guarded menu catalog import.
#   INPUTS:  argv: list[str] | None — command-line arguments.
#   OUTPUTS: int — process exit code.
#   SIDE_EFFECTS: Delegates to run(); writes only sanitized count summaries.
#   LINKS:   docs/shipping-website/README.md Stage 3.
# END_CONTRACT: main
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import Aura Coffee menu catalog CSVs.")
    parser.add_argument(
        "--catalog-dir",
        type=Path,
        default=Path("docs/shipping-website/menu-catalog"),
    )
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="Archive/hide existing menu rows before importing the catalog.",
    )
    args = parser.parse_args(argv)

    counts = run(catalog_dir=args.catalog_dir, replace_existing=args.replace_existing)
    print("menu_catalog import applied")
    for key in sorted(counts):
        print(f"{key}={counts[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
