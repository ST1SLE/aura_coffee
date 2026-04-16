"""RED: тесты валидатора временных слотов (PDD §7.5, INV-007).

Контракт `validate_time_slot(requested_time, order_type, shop_settings, now=None)`:
- ASAP (requested_time=None): `estimated = now + prep_time` (+ delivery_time если DELIVERY).
  Если вне рабочих часов — найти следующее открытие ≤24ч иначе raise.
- Конкретное время: в будущем, ≥ prep_time от now, в рабочих часах.
- Возвращает estimated_ready_at: datetime.
- Поднимает TimeSlotValidationError из core_api.services.validators.exceptions.

Clock injection: тесты передают `now=datetime(...)` явно — freezegun не в deps.

Работаем в UTC: shop_settings.working_hours["thu"] = {"open":"08:00","close":"22:00"}
интерпретируется как UTC для RED-контракта. Сдвиг под таймзону магазина — GREEN-рефайн.
"""
from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace as Ns

import pytest


def _shop_thu() -> Ns:
    """ShopSettings stub: четверг открыт 08:00–22:00, остальные дни так же."""
    return Ns(
        working_hours={
            "mon": {"open": "08:00", "close": "22:00"},
            "tue": {"open": "08:00", "close": "22:00"},
            "wed": {"open": "08:00", "close": "22:00"},
            "thu": {"open": "08:00", "close": "22:00"},
            "fri": {"open": "08:00", "close": "22:00"},
            "sat": {"open": "08:00", "close": "22:00"},
            "sun": {"open": "08:00", "close": "22:00"},
        },
        default_prep_time_minutes=15,
        estimated_delivery_time_minutes=30,
    )


def test_validate_time_slot_asap_pickup_in_working_hours() -> None:
    from shared.enums import OrderType

    from core_api.services.validators import validate_time_slot

    now = datetime(2026, 4, 16, 10, 0, 0, tzinfo=UTC)  # четверг
    result = validate_time_slot(None, OrderType.PICKUP, _shop_thu(), now=now)
    assert result == datetime(2026, 4, 16, 10, 15, 0, tzinfo=UTC)


def test_validate_time_slot_asap_delivery_adds_estimated_delivery_time() -> None:
    from shared.enums import OrderType

    from core_api.services.validators import validate_time_slot

    now = datetime(2026, 4, 16, 10, 0, 0, tzinfo=UTC)
    result = validate_time_slot(None, OrderType.DELIVERY, _shop_thu(), now=now)
    # 10:00 + 15 (prep) + 30 (delivery) = 10:45
    assert result == datetime(2026, 4, 16, 10, 45, 0, tzinfo=UTC)


def test_validate_time_slot_asap_closed_opens_same_day() -> None:
    """PDD §7.5 шаг 2: кофейня закрыта, ближайшее открытие ≤24ч → opening + prep."""
    from shared.enums import OrderType

    from core_api.services.validators import validate_time_slot

    now = datetime(2026, 4, 16, 2, 0, 0, tzinfo=UTC)  # четверг 02:00 — закрыто
    result = validate_time_slot(None, OrderType.PICKUP, _shop_thu(), now=now)
    # Открытие в 08:00 + prep 15 мин = 08:15
    assert result == datetime(2026, 4, 16, 8, 15, 0, tzinfo=UTC)


def test_validate_time_slot_asap_closed_gt_24h_raises() -> None:
    """PDD §7.5 шаг 2: если следующее открытие >24ч — ASAP недоступен → raise.

    Настройка: все 7 дней недели закрыты (пустые working_hours).
    """
    from shared.enums import OrderType

    from core_api.services.validators import validate_time_slot
    from core_api.services.validators.exceptions import TimeSlotValidationError

    shop = Ns(
        working_hours={},  # полностью закрыто
        default_prep_time_minutes=15,
        estimated_delivery_time_minutes=30,
    )
    now = datetime(2026, 4, 16, 2, 0, 0, tzinfo=UTC)
    with pytest.raises(TimeSlotValidationError):
        validate_time_slot(None, OrderType.PICKUP, shop, now=now)


def test_validate_time_slot_explicit_in_past_raises() -> None:
    from shared.enums import OrderType

    from core_api.services.validators import validate_time_slot
    from core_api.services.validators.exceptions import TimeSlotValidationError

    now = datetime(2026, 4, 16, 10, 0, 0, tzinfo=UTC)
    past = datetime(2026, 4, 16, 9, 0, 0, tzinfo=UTC)
    with pytest.raises(TimeSlotValidationError):
        validate_time_slot(past, OrderType.PICKUP, _shop_thu(), now=now)


def test_validate_time_slot_explicit_below_prep_time_raises() -> None:
    from shared.enums import OrderType

    from core_api.services.validators import validate_time_slot
    from core_api.services.validators.exceptions import TimeSlotValidationError

    now = datetime(2026, 4, 16, 10, 0, 0, tzinfo=UTC)
    too_soon = datetime(2026, 4, 16, 10, 10, 0, tzinfo=UTC)  # < now + prep(15)
    with pytest.raises(TimeSlotValidationError):
        validate_time_slot(too_soon, OrderType.PICKUP, _shop_thu(), now=now)


def test_validate_time_slot_explicit_outside_hours_raises() -> None:
    from shared.enums import OrderType

    from core_api.services.validators import validate_time_slot
    from core_api.services.validators.exceptions import TimeSlotValidationError

    now = datetime(2026, 4, 16, 10, 0, 0, tzinfo=UTC)
    after_close = datetime(2026, 4, 16, 23, 0, 0, tzinfo=UTC)  # 23:00, закрыто
    with pytest.raises(TimeSlotValidationError):
        validate_time_slot(after_close, OrderType.PICKUP, _shop_thu(), now=now)


def test_validate_time_slot_explicit_in_hours_accepts() -> None:
    from shared.enums import OrderType

    from core_api.services.validators import validate_time_slot

    now = datetime(2026, 4, 16, 10, 0, 0, tzinfo=UTC)
    requested = datetime(2026, 4, 16, 14, 0, 0, tzinfo=UTC)
    result = validate_time_slot(requested, OrderType.PICKUP, _shop_thu(), now=now)
    assert result == requested
