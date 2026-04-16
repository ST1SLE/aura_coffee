"""RED: тесты валидаторов доставки (PDD §7.3 шаг 3, §7.4 шаг 1, INV-008, INV-009).

Контракты:
- `validate_delivery_address(lat, lon, shop_settings)`:
    Haversine distance между (shop_lat, shop_lon) и (lat, lon).
    Earth radius = 6371 км (PDD §7.3 шаг 3).
    distance > delivery_radius_km → raise DeliveryRadiusError.
- `validate_min_delivery_amount(subtotal, shop_settings)`:
    subtotal < shop_settings.min_delivery_amount → raise MinimumDeliveryAmountError.

Pure tests: никаких DB, SimpleNamespace stub для ShopSettings.
"""
from __future__ import annotations

from types import SimpleNamespace as Ns

import pytest


def _shop_moscow() -> Ns:
    """Shop coords ~Москва, радиус 5 км."""
    return Ns(
        shop_lat=55.7558,
        shop_lon=37.6173,
        delivery_radius_km=5.0,
        min_delivery_amount=50000,
        free_delivery_threshold=150000,
        delivery_fee=20000,
    )


# ---------------------------------------------------------------------------
# validate_delivery_address (PDD §7.3 шаг 3, INV-008)
# ---------------------------------------------------------------------------


def test_validate_delivery_address_inside_radius_accepts() -> None:
    from core_api.services.validators import validate_delivery_address

    # (55.7600, 37.6200) — ~0.5 км от центра, в зоне 5 км
    result = validate_delivery_address(55.7600, 37.6200, _shop_moscow())
    assert result is None


def test_validate_delivery_address_outside_radius_raises() -> None:
    from core_api.services.validators import validate_delivery_address
    from core_api.services.validators.exceptions import DeliveryRadiusError

    # (55.9000, 37.6173) — ~16 км от центра, вне 5 км
    with pytest.raises(DeliveryRadiusError):
        validate_delivery_address(55.9000, 37.6173, _shop_moscow())


def test_validate_delivery_address_earth_radius_6371_sanity() -> None:
    """Проверка константы: адрес == shop coords → distance=0 → проход без raise."""
    from core_api.services.validators import validate_delivery_address

    shop = _shop_moscow()
    result = validate_delivery_address(shop.shop_lat, shop.shop_lon, shop)
    assert result is None


# ---------------------------------------------------------------------------
# validate_min_delivery_amount (PDD §7.4 шаг 1, INV-009)
# ---------------------------------------------------------------------------


def test_validate_min_delivery_amount_below_raises() -> None:
    from core_api.services.validators import validate_min_delivery_amount
    from core_api.services.validators.exceptions import MinimumDeliveryAmountError

    with pytest.raises(MinimumDeliveryAmountError):
        validate_min_delivery_amount(40000, _shop_moscow())


def test_validate_min_delivery_amount_equal_accepts() -> None:
    """INV-009 boundary: строгое неравенство — subtotal == min accepts."""
    from core_api.services.validators import validate_min_delivery_amount

    result = validate_min_delivery_amount(50000, _shop_moscow())
    assert result is None


def test_validate_min_delivery_amount_above_accepts() -> None:
    from core_api.services.validators import validate_min_delivery_amount

    result = validate_min_delivery_amount(200000, _shop_moscow())
    assert result is None
