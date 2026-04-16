"""Чистые функции расчёта стоимости (PDD §7.2 шаг 1).

Модуль намеренно не импортирует SQLAlchemy, Redis, FastAPI или Pydantic —
только стандартная библиотека и typing. Это позволяет переиспользовать
функции как в корзине (Phase 2), так и в checkout (Phase 3) без fan-out зависимостей.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from shared.enums import PromocodeDiscountType

from core_api.services.validators.exceptions import MinimumDeliveryAmountError


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


def apply_promocode(subtotal: int, promocode: Any | None) -> tuple[int, int]:
    """Возвращает (discount, after_promo) — PDD §7.2 шаг 2, INV-011.

    PERCENT: floor(subtotal × discount_value / 100).
    FIXED_AMOUNT: discount_value (с кэпом до subtotal).
    None: (0, subtotal).
    """
    if promocode is None:
        return 0, subtotal
    if promocode.discount_type == PromocodeDiscountType.PERCENT:
        discount = (subtotal * int(promocode.discount_value)) // 100
    else:
        discount = int(promocode.discount_value)
    discount = min(discount, subtotal)
    return discount, subtotal - discount


def apply_loyalty_points(
    after_promo: int,
    requested_points: int,
    user_balance: int,
) -> tuple[int, int]:
    """Возвращает (points_used, after_points) — PDD §7.2 шаг 3.

    Кэп: min(requested, balance, after_promo). Никогда не возбуждает исключений
    — проверка достаточности баллов на уровне checkout-оркестратора.
    """
    used = min(requested_points, user_balance, after_promo)
    return used, after_promo - used


def compute_delivery_fee(subtotal: int, shop_settings: Any) -> int:
    """Возвращает стоимость доставки — PDD §7.4 шаг 1, INV-009.

    subtotal < min_delivery_amount → raise MinimumDeliveryAmountError.
    subtotal >= free_delivery_threshold → 0 (бесплатная).
    Иначе → delivery_fee.
    """
    if subtotal < int(shop_settings.min_delivery_amount):
        raise MinimumDeliveryAmountError(
            f"subtotal {subtotal} below min_delivery_amount "
            f"{shop_settings.min_delivery_amount}",
        )
    if subtotal >= int(shop_settings.free_delivery_threshold):
        return 0
    return int(shop_settings.delivery_fee)


def compute_order_total(after_points: int, delivery_fee: int) -> int:
    """Итоговая сумма к оплате — PDD §7.2 шаг 5."""
    return after_points + delivery_fee


def compute_estimated_accrual(after_points: int, loyalty_percent: int) -> int:
    """Предварительное начисление баллов — INV-003.

    База — after_points (исключены и promo_discount, и points_used, и delivery).
    Формула: floor(after_points × percent / 100).
    """
    return (after_points * loyalty_percent) // 100
