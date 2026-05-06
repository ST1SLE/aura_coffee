#!/usr/bin/env python3
"""Validate the Stage 3 menu catalog CSV packet before import/deploy."""

# START_MODULE_CONTRACT
#   PURPOSE: Validate owner-supplied menu/media CSV files before any staging or
#            production database import is attempted.
#   SCOPE:   Structural CSV validation only: stable codes, required fields,
#            price/inventory/boolean enums, cross-file references, and local
#            public media path shape. Optional filesystem existence checks for
#            referenced media assets.
#   DEPENDS: Python stdlib (argparse, csv, pathlib, re, sys).
#   LINKS:   docs/shipping-website/README.md Stage 3, PDD §5.2 menu tables,
#            PDD §5.1 prices in kopecks, INV-014, INV-015.
#   ROLE:    TOOLING
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   main - CLI entry point for catalog validation
# END_MODULE_MAP

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_BOOL_VALUES = {"true", "false"}
_CATEGORY_TYPES = {"drink", "food", "merch", "modifier"}
_SIZE_LABELS = {"S", "M", "L"}
_MEDIA_TYPES = {"", "image", "video"}

_HEADERS = {
    "categories.csv": [
        "category_code",
        "type",
        "name_ru",
        "name_en",
        "sort_order",
        "is_visible",
    ],
    "items.csv": [
        "item_code",
        "category_code",
        "name_ru",
        "name_en",
        "description_ru",
        "description_en",
        "base_price_kopecks",
        "available",
        "archived",
        "sort_order",
        "inventory_quantity",
        "media_type",
        "media_url",
        "media_poster_url",
        "image_url",
    ],
    "sizes.csv": ["item_code", "size_label", "price_kopecks", "available"],
    "modifiers.csv": [
        "modifier_code",
        "name_ru",
        "name_en",
        "price_kopecks",
        "available",
        "sort_order",
    ],
    "item_modifiers.csv": ["item_code", "modifier_code"],
}


def _read_csv(catalog_dir: Path, filename: str) -> tuple[list[dict[str, str]], list[str]]:
    path = catalog_dir / filename
    if not path.exists():
        return [], [f"{filename}: missing required file"]

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        expected = _HEADERS[filename]
        if reader.fieldnames != expected:
            return [], [
                f"{filename}: header mismatch; expected {','.join(expected)}"
            ]
        return list(reader), []


def _is_blank(value: str | None) -> bool:
    return value is None or value.strip() == ""


def _require(value: str | None, *, filename: str, row: int, column: str, errors: list[str]) -> str:
    normalized = "" if value is None else value.strip()
    if normalized == "":
        errors.append(f"{filename}:{row}: {column} is required")
    return normalized


def _check_slug(value: str, *, filename: str, row: int, column: str, errors: list[str]) -> None:
    if not _SLUG_RE.fullmatch(value):
        errors.append(
            f"{filename}:{row}: {column} must be lowercase slug characters"
        )


def _check_bool(value: str, *, filename: str, row: int, column: str, errors: list[str]) -> None:
    if value not in _BOOL_VALUES:
        errors.append(f"{filename}:{row}: {column} must be true or false")


def _check_int(
    value: str,
    *,
    filename: str,
    row: int,
    column: str,
    errors: list[str],
    allow_blank: bool = False,
) -> None:
    if allow_blank and _is_blank(value):
        return
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        errors.append(f"{filename}:{row}: {column} must be an integer")
        return
    if parsed < 0:
        errors.append(f"{filename}:{row}: {column} must be >= 0")


def _check_media_path(
    value: str,
    *,
    filename: str,
    row: int,
    column: str,
    item_code: str,
    media_root: Path | None,
    require_media_files: bool,
    errors: list[str],
) -> None:
    if _is_blank(value):
        return
    if not value.startswith(f"/media/menu/{item_code}/"):
        errors.append(
            f"{filename}:{row}: {column} must start with /media/menu/{item_code}/"
        )
        return
    if "?" in value or "#" in value or "://" in value:
        errors.append(f"{filename}:{row}: {column} must be a local public path")
        return
    if require_media_files:
        if media_root is None:
            errors.append("--require-media-files needs --media-root")
            return
        relative = value.removeprefix("/media/menu/")
        if not (media_root / relative).is_file():
            errors.append(f"{filename}:{row}: {column} file is missing: {value}")


def _validate_catalog(
    catalog_dir: Path,
    *,
    media_root: Path | None = None,
    require_media_files: bool = False,
) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    loaded: dict[str, list[dict[str, str]]] = {}
    for filename in _HEADERS:
        rows, file_errors = _read_csv(catalog_dir, filename)
        loaded[filename] = rows
        errors.extend(file_errors)
    if errors:
        return errors, {}

    category_codes: set[str] = set()
    for index, row in enumerate(loaded["categories.csv"], start=2):
        code = _require(
            row.get("category_code"),
            filename="categories.csv",
            row=index,
            column="category_code",
            errors=errors,
        )
        _check_slug(
            code,
            filename="categories.csv",
            row=index,
            column="category_code",
            errors=errors,
        )
        if code in category_codes:
            errors.append(f"categories.csv:{index}: duplicate category_code {code}")
        category_codes.add(code)
        category_type = _require(
            row.get("type"),
            filename="categories.csv",
            row=index,
            column="type",
            errors=errors,
        )
        if category_type not in _CATEGORY_TYPES:
            errors.append(f"categories.csv:{index}: unsupported category type")
        _require(
            row.get("name_ru"),
            filename="categories.csv",
            row=index,
            column="name_ru",
            errors=errors,
        )
        _require(
            row.get("name_en"),
            filename="categories.csv",
            row=index,
            column="name_en",
            errors=errors,
        )
        _check_int(
            row.get("sort_order", ""),
            filename="categories.csv",
            row=index,
            column="sort_order",
            errors=errors,
        )
        _check_bool(
            row.get("is_visible", ""),
            filename="categories.csv",
            row=index,
            column="is_visible",
            errors=errors,
        )

    item_codes: set[str] = set()
    for index, row in enumerate(loaded["items.csv"], start=2):
        code = _require(
            row.get("item_code"),
            filename="items.csv",
            row=index,
            column="item_code",
            errors=errors,
        )
        _check_slug(
            code,
            filename="items.csv",
            row=index,
            column="item_code",
            errors=errors,
        )
        if code in item_codes:
            errors.append(f"items.csv:{index}: duplicate item_code {code}")
        item_codes.add(code)
        category_code = _require(
            row.get("category_code"),
            filename="items.csv",
            row=index,
            column="category_code",
            errors=errors,
        )
        if category_code not in category_codes:
            errors.append(f"items.csv:{index}: unknown category_code {category_code}")
        for column in ("name_ru", "name_en"):
            _require(
                row.get(column),
                filename="items.csv",
                row=index,
                column=column,
                errors=errors,
            )
        _check_int(
            row.get("base_price_kopecks", ""),
            filename="items.csv",
            row=index,
            column="base_price_kopecks",
            errors=errors,
        )
        _check_bool(
            row.get("available", ""),
            filename="items.csv",
            row=index,
            column="available",
            errors=errors,
        )
        _check_bool(
            row.get("archived", ""),
            filename="items.csv",
            row=index,
            column="archived",
            errors=errors,
        )
        _check_int(
            row.get("sort_order", ""),
            filename="items.csv",
            row=index,
            column="sort_order",
            errors=errors,
        )
        _check_int(
            row.get("inventory_quantity", ""),
            filename="items.csv",
            row=index,
            column="inventory_quantity",
            errors=errors,
            allow_blank=True,
        )
        media_type = (row.get("media_type") or "").strip()
        if media_type not in _MEDIA_TYPES:
            errors.append(f"items.csv:{index}: media_type must be image, video, or blank")
        media_url = (row.get("media_url") or "").strip()
        media_poster_url = (row.get("media_poster_url") or "").strip()
        image_url = (row.get("image_url") or "").strip()
        if media_type == "video" and (_is_blank(media_url) or _is_blank(media_poster_url)):
            errors.append(
                f"items.csv:{index}: video items require media_url and media_poster_url"
            )
        if media_type == "image" and _is_blank(media_url) and _is_blank(image_url):
            errors.append(
                f"items.csv:{index}: image items require media_url or image_url"
            )
        for column, value in (
            ("media_url", media_url),
            ("media_poster_url", media_poster_url),
            ("image_url", image_url),
        ):
            _check_media_path(
                value,
                filename="items.csv",
                row=index,
                column=column,
                item_code=code,
                media_root=media_root,
                require_media_files=require_media_files,
                errors=errors,
            )

    size_keys: set[tuple[str, str]] = set()
    for index, row in enumerate(loaded["sizes.csv"], start=2):
        item_code = _require(
            row.get("item_code"),
            filename="sizes.csv",
            row=index,
            column="item_code",
            errors=errors,
        )
        if item_code not in item_codes:
            errors.append(f"sizes.csv:{index}: unknown item_code {item_code}")
        label = _require(
            row.get("size_label"),
            filename="sizes.csv",
            row=index,
            column="size_label",
            errors=errors,
        )
        if label not in _SIZE_LABELS:
            errors.append(f"sizes.csv:{index}: size_label must be S, M, or L")
        key = (item_code, label)
        if key in size_keys:
            errors.append(f"sizes.csv:{index}: duplicate size for {item_code}/{label}")
        size_keys.add(key)
        _check_int(
            row.get("price_kopecks", ""),
            filename="sizes.csv",
            row=index,
            column="price_kopecks",
            errors=errors,
        )
        _check_bool(
            row.get("available", ""),
            filename="sizes.csv",
            row=index,
            column="available",
            errors=errors,
        )

    modifier_codes: set[str] = set()
    for index, row in enumerate(loaded["modifiers.csv"], start=2):
        code = _require(
            row.get("modifier_code"),
            filename="modifiers.csv",
            row=index,
            column="modifier_code",
            errors=errors,
        )
        _check_slug(
            code,
            filename="modifiers.csv",
            row=index,
            column="modifier_code",
            errors=errors,
        )
        if code in modifier_codes:
            errors.append(f"modifiers.csv:{index}: duplicate modifier_code {code}")
        modifier_codes.add(code)
        for column in ("name_ru", "name_en"):
            _require(
                row.get(column),
                filename="modifiers.csv",
                row=index,
                column=column,
                errors=errors,
            )
        _check_int(
            row.get("price_kopecks", ""),
            filename="modifiers.csv",
            row=index,
            column="price_kopecks",
            errors=errors,
        )
        _check_bool(
            row.get("available", ""),
            filename="modifiers.csv",
            row=index,
            column="available",
            errors=errors,
        )
        _check_int(
            row.get("sort_order", ""),
            filename="modifiers.csv",
            row=index,
            column="sort_order",
            errors=errors,
        )

    link_keys: set[tuple[str, str]] = set()
    for index, row in enumerate(loaded["item_modifiers.csv"], start=2):
        item_code = _require(
            row.get("item_code"),
            filename="item_modifiers.csv",
            row=index,
            column="item_code",
            errors=errors,
        )
        modifier_code = _require(
            row.get("modifier_code"),
            filename="item_modifiers.csv",
            row=index,
            column="modifier_code",
            errors=errors,
        )
        if item_code not in item_codes:
            errors.append(
                f"item_modifiers.csv:{index}: unknown item_code {item_code}"
            )
        if modifier_code not in modifier_codes:
            errors.append(
                f"item_modifiers.csv:{index}: unknown modifier_code {modifier_code}"
            )
        key = (item_code, modifier_code)
        if key in link_keys:
            errors.append(
                f"item_modifiers.csv:{index}: duplicate link {item_code}/{modifier_code}"
            )
        link_keys.add(key)

    counts = {
        "categories": len(category_codes),
        "items": len(item_codes),
        "sizes": len(size_keys),
        "modifiers": len(modifier_codes),
        "item_modifier_links": len(link_keys),
    }
    return errors, counts


# START_CONTRACT: main
#   PURPOSE: CLI entry point for validating the owner menu catalog packet.
#   INPUTS:  argv: list[str] | None — command-line args or None for sys.argv.
#   OUTPUTS: int — process exit code; 0 if valid, 1 if validation failed.
#   SIDE_EFFECTS: Reads CSV files and optionally media files; writes sanitized
#                 validation summary/errors to stdout/stderr. No secrets or PII.
#   LINKS:   docs/shipping-website/README.md Stage 3, INV-015.
# END_CONTRACT: main
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate Aura Coffee Stage 3 menu catalog CSV files."
    )
    parser.add_argument("catalog_dir", type=Path)
    parser.add_argument("--media-root", type=Path)
    parser.add_argument("--require-media-files", action="store_true")
    args = parser.parse_args(argv)

    errors, counts = _validate_catalog(
        args.catalog_dir,
        media_root=args.media_root,
        require_media_files=args.require_media_files,
    )
    if errors:
        print("menu catalog validation failed", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("menu catalog validation passed")
    for key in sorted(counts):
        print(f"{key}={counts[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
