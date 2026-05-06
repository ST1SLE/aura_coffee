"""Tests for the Stage 3 menu catalog validator."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPO_ROOT / "scripts" / "production" / "validate-menu-catalog.py"
CATALOG_DIR = REPO_ROOT / "docs" / "shipping-website" / "menu-catalog"


def _load_validator():
    spec = importlib.util.spec_from_file_location("validate_menu_catalog", VALIDATOR_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_menu_catalog_template_validates() -> None:
    validator = _load_validator()

    errors, counts = validator._validate_catalog(CATALOG_DIR)

    assert errors == []
    assert counts == {
        "categories": 2,
        "items": 2,
        "sizes": 3,
        "modifiers": 2,
        "item_modifier_links": 2,
    }


def test_menu_catalog_validator_rejects_broken_references(tmp_path: Path) -> None:
    validator = _load_validator()
    for filename, headers in validator._HEADERS.items():
        (tmp_path / filename).write_text(",".join(headers) + "\n", encoding="utf-8")

    (tmp_path / "categories.csv").write_text(
        "\n".join(
            [
                ",".join(validator._HEADERS["categories.csv"]),
                "coffee,drink,Name RU,Coffee,0,true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "items.csv").write_text(
        "\n".join(
            [
                ",".join(validator._HEADERS["items.csv"]),
                (
                    "Bad Code,missing,Name RU,Cappuccino,,,52000,true,false,0,,"
                    "video,/media/menu/cappuccino/hero.mp4,,"
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "item_modifiers.csv").write_text(
        "\n".join(
            [
                ",".join(validator._HEADERS["item_modifiers.csv"]),
                "cappuccino,missing-modifier",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    errors, _counts = validator._validate_catalog(tmp_path)

    assert any("item_code must be lowercase slug characters" in e for e in errors)
    assert any("unknown category_code missing" in e for e in errors)
    assert any("video items require media_url and media_poster_url" in e for e in errors)
    assert any("unknown modifier_code missing-modifier" in e for e in errors)
