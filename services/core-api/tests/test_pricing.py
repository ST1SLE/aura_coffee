"""RED: тесты модуля core_api.services.pricing.

Все тесты ДОЛЖНЫ падать с AttributeError до реализации функций в pricing.py.
"""
from __future__ import annotations

import ast
import pathlib

import pytest


# ---------------------------------------------------------------------------
# 2.1 Базовая цена, нет размера и модификаторов
# ---------------------------------------------------------------------------

def test_compute_line_total_base_price_only() -> None:
    from core_api.services.pricing import compute_line_total

    assert compute_line_total(base_price=15000, size_price=None, modifier_prices=[], quantity=1) == 15000


# ---------------------------------------------------------------------------
# 2.2 Размер перекрывает базовую цену
# ---------------------------------------------------------------------------

def test_compute_line_total_size_overrides_base() -> None:
    from core_api.services.pricing import compute_line_total

    assert compute_line_total(15000, 20000, [], 1) == 20000


# ---------------------------------------------------------------------------
# 2.3 Явный ноль в size_price — всё равно используется (не None)
# ---------------------------------------------------------------------------

def test_compute_line_total_size_zero_overrides_base() -> None:
    from core_api.services.pricing import compute_line_total

    assert compute_line_total(15000, 0, [], 1) == 0


# ---------------------------------------------------------------------------
# 2.4 Модификаторы суммируются к unit_price
# ---------------------------------------------------------------------------

def test_compute_line_total_modifiers_sum() -> None:
    from core_api.services.pricing import compute_line_total

    assert compute_line_total(15000, None, [3000, 5000], 1) == 23000


# ---------------------------------------------------------------------------
# 2.5 quantity умножает unit_price
# ---------------------------------------------------------------------------

def test_compute_line_total_quantity_multiplies() -> None:
    from core_api.services.pricing import compute_line_total

    # (20000 + 3000) * 4 = 92000
    assert compute_line_total(15000, 20000, [3000], 4) == 92000


# ---------------------------------------------------------------------------
# 2.6 Нулевые модификаторы не меняют результат
# ---------------------------------------------------------------------------

def test_compute_line_total_zero_modifiers_no_change() -> None:
    from core_api.services.pricing import compute_line_total

    assert compute_line_total(10000, None, [0, 0, 0], 2) == 20000


# ---------------------------------------------------------------------------
# 2.7 Отрицательная базовая цена — ValueError
# ---------------------------------------------------------------------------

def test_compute_line_total_rejects_negative_base() -> None:
    from core_api.services.pricing import compute_line_total

    with pytest.raises(ValueError):
        compute_line_total(-1, None, [], 1)


# ---------------------------------------------------------------------------
# 2.8 Отрицательный модификатор — ValueError
# ---------------------------------------------------------------------------

def test_compute_line_total_rejects_negative_modifier() -> None:
    from core_api.services.pricing import compute_line_total

    with pytest.raises(ValueError):
        compute_line_total(1, None, [-1], 1)


# ---------------------------------------------------------------------------
# 2.9 quantity == 0 — ValueError
# ---------------------------------------------------------------------------

def test_compute_line_total_rejects_zero_quantity() -> None:
    from core_api.services.pricing import compute_line_total

    with pytest.raises(ValueError):
        compute_line_total(1, None, [], 0)


# ---------------------------------------------------------------------------
# 2.10 Пустой список → subtotal == 0
# ---------------------------------------------------------------------------

def test_compute_subtotal_empty_is_zero() -> None:
    from core_api.services.pricing import compute_subtotal

    assert compute_subtotal([]) == 0


# ---------------------------------------------------------------------------
# 2.11 Сумма нескольких значений
# ---------------------------------------------------------------------------

def test_compute_subtotal_sums_values() -> None:
    from core_api.services.pricing import compute_subtotal

    assert compute_subtotal([10000, 25000, 5000]) == 40000


# ---------------------------------------------------------------------------
# 2.12 Отрицательный line_total — ValueError
# ---------------------------------------------------------------------------

def test_compute_subtotal_rejects_negative() -> None:
    from core_api.services.pricing import compute_subtotal

    with pytest.raises(ValueError):
        compute_subtotal([10000, -1])


# ---------------------------------------------------------------------------
# 2.13 pricing.py не импортирует никаких фреймворков
# ---------------------------------------------------------------------------

def test_pricing_module_has_no_framework_imports() -> None:
    pricing_path = (
        pathlib.Path(__file__).parents[1]
        / "src" / "core_api" / "services" / "pricing.py"
    )
    assert pricing_path.exists(), "pricing.py ещё не создан"

    source = pricing_path.read_text()
    tree = ast.parse(source)

    forbidden_prefixes = (
        "sqlalchemy", "redis", "fastapi", "pydantic",
        "core_api.models", "shared.models",
    )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for bad in forbidden_prefixes:
                    assert not alias.name.startswith(bad), (
                        f"pricing.py импортирует запрещённый модуль {alias.name!r}"
                    )
        elif isinstance(node, ast.ImportFrom) and node.module:
            for bad in forbidden_prefixes:
                assert not node.module.startswith(bad), (
                    f"pricing.py импортирует из запрещённого модуля {node.module!r}"
                )
