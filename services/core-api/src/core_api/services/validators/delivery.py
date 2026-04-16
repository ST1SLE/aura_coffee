"""Delivery-валидаторы — PDD §7.3 шаг 3 (INV-008) и §7.4 шаг 1 (INV-009).

Чистые функции: никаких DB-запросов. ShopSettings передаётся готовым объектом.
"""
from __future__ import annotations

import math
from typing import Any

from .exceptions import DeliveryRadiusError, MinimumDeliveryAmountError

_EARTH_RADIUS_KM = 6371.0


def validate_delivery_address(
    lat: float,
    lon: float,
    shop_settings: Any,
) -> None:
    """Проверяет, что адрес в пределах delivery_radius_km (Haversine, R=6371 км).

    Raises DeliveryRadiusError, если distance > delivery_radius_km (строгое).
    """
    shop_lat = float(shop_settings.shop_lat)
    shop_lon = float(shop_settings.shop_lon)

    phi1 = math.radians(shop_lat)
    phi2 = math.radians(lat)
    dphi = math.radians(lat - shop_lat)
    dlambda = math.radians(lon - shop_lon)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance_km = _EARTH_RADIUS_KM * c

    radius = float(shop_settings.delivery_radius_km)
    if distance_km > radius:
        raise DeliveryRadiusError(
            f"distance {distance_km:.2f} km > radius {radius} km",
        )


def validate_min_delivery_amount(subtotal: int, shop_settings: Any) -> None:
    """subtotal < min_delivery_amount → raise (строго); равенство принимается."""
    min_amount = int(shop_settings.min_delivery_amount)
    if subtotal < min_amount:
        raise MinimumDeliveryAmountError(
            f"subtotal {subtotal} below min_delivery_amount {min_amount}",
        )
