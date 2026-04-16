"""RED: тесты расширения pricing chain (PDD §7.2 шаги 2–6, INV-003, INV-011).

Все тесты ДОЛЖНЫ падать с ImportError до реализации новых функций в pricing.py:
apply_promocode, apply_loyalty_points, compute_delivery_fee, compute_order_total,
compute_estimated_accrual.

Импорты делаются внутри тела каждой функции — import-time ошибки surface
как падение конкретного теста, а не как collection error всего файла.

Контрактные стабы для Promocode и ShopSettings — SimpleNamespace: GREEN-код
читает только атрибуты (.discount_type, .discount_value, .min_delivery_amount,
.free_delivery_threshold, .delivery_fee), поэтому тесты не тянут ORM.
"""
from __future__ import annotations

from types import SimpleNamespace as Ns

import pytest

# ---------------------------------------------------------------------------
# Группа 2. apply_promocode (PDD §7.2 шаг 2)
# ---------------------------------------------------------------------------


def test_apply_promocode_none_returns_zero_and_subtotal() -> None:
    from core_api.services.pricing import apply_promocode

    assert apply_promocode(100000, None) == (0, 100000)


def test_apply_promocode_percent_floor_division() -> None:
    from shared.enums import PromocodeDiscountType
    from core_api.services.pricing import apply_promocode

    promo = Ns(discount_type=PromocodeDiscountType.PERCENT, discount_value=10)
    # floor(30333 * 10 / 100) = 3033
    assert apply_promocode(30333, promo) == (3033, 27300)


def test_apply_promocode_percent_zero_value_yields_zero_discount() -> None:
    from shared.enums import PromocodeDiscountType
    from core_api.services.pricing import apply_promocode

    promo = Ns(discount_type=PromocodeDiscountType.PERCENT, discount_value=0)
    assert apply_promocode(50000, promo) == (0, 50000)


def test_apply_promocode_fixed_amount_within_subtotal() -> None:
    from shared.enums import PromocodeDiscountType
    from core_api.services.pricing import apply_promocode

    promo = Ns(discount_type=PromocodeDiscountType.FIXED_AMOUNT, discount_value=5000)
    assert apply_promocode(30000, promo) == (5000, 25000)


def test_apply_promocode_fixed_amount_caps_at_subtotal() -> None:
    from shared.enums import PromocodeDiscountType
    from core_api.services.pricing import apply_promocode

    promo = Ns(discount_type=PromocodeDiscountType.FIXED_AMOUNT, discount_value=100000)
    assert apply_promocode(30000, promo) == (30000, 0)


# ---------------------------------------------------------------------------
# Группа 3. apply_loyalty_points (PDD §7.2 шаг 3)
# ---------------------------------------------------------------------------


def test_apply_loyalty_points_no_request_returns_zero() -> None:
    from core_api.services.pricing import apply_loyalty_points

    assert apply_loyalty_points(after_promo=20000, requested_points=0, user_balance=50000) == (0, 20000)


def test_apply_loyalty_points_request_below_balance_and_after_promo() -> None:
    from core_api.services.pricing import apply_loyalty_points

    assert apply_loyalty_points(after_promo=20000, requested_points=5000, user_balance=50000) == (5000, 15000)


def test_apply_loyalty_points_request_exceeds_balance_uses_balance() -> None:
    """Клиент запросил больше баланса — используем весь баланс, НЕ ошибка."""
    from core_api.services.pricing import apply_loyalty_points

    assert apply_loyalty_points(after_promo=20000, requested_points=50000, user_balance=15000) == (15000, 5000)


def test_apply_loyalty_points_cap_at_after_promo() -> None:
    """max_redeemable = min(balance, after_promo) — крышка по after_promo."""
    from core_api.services.pricing import apply_loyalty_points

    assert apply_loyalty_points(after_promo=10000, requested_points=50000, user_balance=50000) == (10000, 0)


def test_apply_loyalty_points_zero_balance() -> None:
    from core_api.services.pricing import apply_loyalty_points

    assert apply_loyalty_points(after_promo=20000, requested_points=5000, user_balance=0) == (0, 20000)


# ---------------------------------------------------------------------------
# Группа 4. compute_delivery_fee / compute_order_total / compute_estimated_accrual
# (PDD §7.2 шаги 4–6, §7.4, INV-003, INV-009)
# ---------------------------------------------------------------------------


def _shop_default() -> Ns:
    return Ns(min_delivery_amount=50000, free_delivery_threshold=150000, delivery_fee=20000)


def test_compute_delivery_fee_below_min_raises() -> None:
    from core_api.services.pricing import compute_delivery_fee
    from core_api.services.validators.exceptions import MinimumDeliveryAmountError

    with pytest.raises(MinimumDeliveryAmountError):
        compute_delivery_fee(40000, _shop_default())


def test_compute_delivery_fee_equal_to_min_returns_delivery_fee() -> None:
    from core_api.services.pricing import compute_delivery_fee

    assert compute_delivery_fee(50000, _shop_default()) == 20000


def test_compute_delivery_fee_above_free_threshold_returns_zero() -> None:
    from core_api.services.pricing import compute_delivery_fee

    assert compute_delivery_fee(200000, _shop_default()) == 0


def test_compute_delivery_fee_between_min_and_threshold_returns_fee() -> None:
    from core_api.services.pricing import compute_delivery_fee

    assert compute_delivery_fee(100000, _shop_default()) == 20000


def test_compute_order_total_sums_after_points_and_delivery() -> None:
    from core_api.services.pricing import compute_order_total

    assert compute_order_total(after_points=12345, delivery_fee=20000) == 32345


def test_compute_order_total_zero_delivery_for_pickup() -> None:
    from core_api.services.pricing import compute_order_total

    assert compute_order_total(after_points=12345, delivery_fee=0) == 12345


def test_compute_estimated_accrual_floor_division() -> None:
    """INV-003: начисление = floor(after_points × loyalty_percent / 100).

    after_points — сумма за товары после вычета промокода и баллов, БЕЗ delivery_fee.
    """
    from core_api.services.pricing import compute_estimated_accrual

    # floor(10050 * 5 / 100) = 502
    assert compute_estimated_accrual(after_points=10050, loyalty_percent=5) == 502


def test_compute_estimated_accrual_zero_when_fully_points_paid() -> None:
    """INV-003: если заказ на 100% оплачен баллами, начисление = 0."""
    from core_api.services.pricing import compute_estimated_accrual

    assert compute_estimated_accrual(after_points=0, loyalty_percent=5) == 0


def test_compute_estimated_accrual_zero_loyalty_percent() -> None:
    from core_api.services.pricing import compute_estimated_accrual

    assert compute_estimated_accrual(after_points=10000, loyalty_percent=0) == 0
