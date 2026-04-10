"""Чистые функции расчёта стоимости (PDD §7.2 шаг 1).

Модуль намеренно не импортирует SQLAlchemy, Redis, FastAPI или Pydantic —
только стандартная библиотека и typing. Это позволяет переиспользовать
функции как в корзине (Phase 2), так и в checkout (Phase 3) без fan-out зависимостей.
"""
from __future__ import annotations

from collections.abc import Iterable


def _compute_unit_price(
    base_price: int,
    size_price: int | None,
    modifier_prices: Iterable[int],
) -> int:
    """Вычисляет unit_price по формуле PDD §7.2 шаг 1 (design D3)."""
    modifier_list = list(modifier_prices)
    for p in modifier_list:
        if p < 0:
            raise ValueError(f"Цена модификатора не может быть отрицательной: {p}")
    if base_price < 0:
        raise ValueError(f"base_price не может быть отрицательным: {base_price}")
    if size_price is not None and size_price < 0:
        raise ValueError(f"size_price не может быть отрицательным: {size_price}")
    effective = size_price if size_price is not None else base_price
    return effective + sum(modifier_list)


def compute_line_total(
    base_price: int,
    size_price: int | None,
    modifier_prices: Iterable[int],
    quantity: int,
) -> int:
    """Стоимость строки корзины: unit_price × quantity."""
    if quantity < 1:
        raise ValueError(f"quantity должен быть >= 1, получено: {quantity}")
    unit_price = _compute_unit_price(base_price, size_price, modifier_prices)
    return unit_price * quantity


def compute_subtotal(line_totals: Iterable[int]) -> int:
    """Сумма всех line_total позиций корзины."""
    totals = list(line_totals)
    for t in totals:
        if t < 0:
            raise ValueError(f"line_total не может быть отрицательным: {t}")
    return sum(totals)
