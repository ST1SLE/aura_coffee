# START_MODULE_CONTRACT
#   PURPOSE: Pure pricing primitives reused by cart and checkout — no DB, no
#            Redis, no FastAPI. Encodes PDD §7.2 chain steps and INV-008/009.
#   SCOPE:   line/subtotal/promo/loyalty/delivery_fee/total/accrual computations.
#   DEPENDS: M-SHARED (PromocodeDiscountType enum), services.validators.exceptions
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §7.2, §7.4,
#            INV-003, INV-009, INV-011, INV-014
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   compute_line_total          - line price = unit_price × quantity
#   compute_subtotal            - sum of line totals
#   apply_promocode             - PERCENT/FIXED discount
#   apply_loyalty_points        - cap & subtract points
#   compute_delivery_fee        - INV-009 + free-threshold
#   compute_order_total         - after_points + delivery_fee
#   compute_estimated_accrual   - floor(after_points × loyalty% / 100)
# END_MODULE_MAP
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


# START_CONTRACT: compute_line_total
#   PURPOSE: Compute the price of a cart line: unit_price × quantity, where
#            unit_price = (size_price or base_price) + sum(modifier_prices).
#   INPUTS:  base_price: int, size_price: int | None,
#            modifier_prices: Iterable[int], quantity: int
#   OUTPUTS: int (kopecks, ≥ 0)
#   SIDE_EFFECTS: none; ValueError on negative inputs or quantity < 1.
#   LINKS:   PDD §7.2, INV-014
# END_CONTRACT: compute_line_total
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


# START_CONTRACT: compute_subtotal
#   PURPOSE: Sum line totals into cart subtotal.
#   INPUTS:  line_totals: Iterable[int]
#   OUTPUTS: int (≥ 0)
#   SIDE_EFFECTS: none; ValueError on negative entry.
#   LINKS:   PDD §7.2
# END_CONTRACT: compute_subtotal
def compute_subtotal(line_totals: Iterable[int]) -> int:
    """Сумма всех line_total позиций корзины."""
    totals = list(line_totals)
    for t in totals:
        if t < 0:
            raise ValueError(f"line_total не может быть отрицательным: {t}")
    return sum(totals)


# START_CONTRACT: apply_promocode
#   PURPOSE: Apply PERCENT (floor) or FIXED_AMOUNT promo discount, capped at
#            subtotal. Returns (discount, after_promo).
#   INPUTS:  subtotal: int, promocode: Any | None
#   OUTPUTS: tuple[int, int]
#   SIDE_EFFECTS: none.
#   LINKS:   PDD §7.2, INV-011
# END_CONTRACT: apply_promocode
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


# START_CONTRACT: apply_loyalty_points
#   PURPOSE: Cap points usage by min(requested, balance, after_promo); subtract
#            from after_promo. Pure helper — no balance mutation.
#   INPUTS:  after_promo: int, requested_points: int, user_balance: int
#   OUTPUTS: tuple[int, int] — (points_used, after_points).
#   SIDE_EFFECTS: none.
#   LINKS:   PDD §7.2
# END_CONTRACT: apply_loyalty_points
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


# START_CONTRACT: compute_delivery_fee
#   PURPOSE: Resolve delivery fee per PDD §7.4 — below min raises
#            MinimumDeliveryAmountError; above free_threshold returns 0;
#            otherwise returns shop_settings.delivery_fee.
#   INPUTS:  subtotal: int, shop_settings: Any
#   OUTPUTS: int (≥ 0)
#   SIDE_EFFECTS: none; raises MinimumDeliveryAmountError.
#   LINKS:   PDD §7.4, INV-009
# END_CONTRACT: compute_delivery_fee
def compute_delivery_fee(subtotal: int, shop_settings: Any) -> int:
    """Возвращает стоимость доставки — PDD §7.4 шаг 1, INV-009.

    subtotal < min_delivery_amount → raise MinimumDeliveryAmountError.
    subtotal >= free_delivery_threshold → 0 (бесплатная).
    Иначе → delivery_fee.
    """
    min_amount = int(shop_settings.min_delivery_amount)
    if subtotal < min_amount:
        raise MinimumDeliveryAmountError(
            subtotal=subtotal,
            min_amount=min_amount,
        )
    if subtotal >= int(shop_settings.free_delivery_threshold):
        return 0
    return int(shop_settings.delivery_fee)


# START_CONTRACT: compute_order_total
#   PURPOSE: Final amount to charge: after_points + delivery_fee.
#   INPUTS:  after_points: int, delivery_fee: int
#   OUTPUTS: int (≥ 0)
#   SIDE_EFFECTS: none.
#   LINKS:   PDD §7.2
# END_CONTRACT: compute_order_total
def compute_order_total(after_points: int, delivery_fee: int) -> int:
    """Итоговая сумма к оплате — PDD §7.2 шаг 5."""
    return after_points + delivery_fee


# START_CONTRACT: compute_estimated_accrual
#   PURPOSE: Estimate loyalty accrual = floor(after_points × loyalty_percent / 100).
#            Base excludes promo discount, points used, and delivery fee per INV-003.
#   INPUTS:  after_points: int, loyalty_percent: int
#   OUTPUTS: int (≥ 0)
#   SIDE_EFFECTS: none.
#   LINKS:   INV-003
# END_CONTRACT: compute_estimated_accrual
def compute_estimated_accrual(after_points: int, loyalty_percent: int) -> int:
    """Предварительное начисление баллов — INV-003.

    База — after_points (исключены и promo_discount, и points_used, и delivery).
    Формула: floor(after_points × percent / 100).
    """
    return (after_points * loyalty_percent) // 100
