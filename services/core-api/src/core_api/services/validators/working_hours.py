"""Working-hours / time-slot validator — PDD §7.5.

validate_time_slot(requested_time, order_type, shop_settings, now=None).

Clock injection через `now` (freezegun не в dev-deps). В GREEN-реализации
работаем в UTC; timezone-aware рефайн — в отдельном change.
"""
from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from typing import Any

from shared.enums import OrderType

from .exceptions import TimeSlotValidationError

_WEEKDAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _parse_hhmm(value: str) -> time:
    hh, mm = value.split(":")
    return time(int(hh), int(mm))


def _hours_for(dt: datetime, working_hours: dict[str, Any]) -> tuple[time, time] | None:
    key = _WEEKDAY_KEYS[dt.weekday()]
    entry = working_hours.get(key)
    if not entry:
        return None
    return _parse_hhmm(entry["open"]), _parse_hhmm(entry["close"])


def _is_within_hours(dt: datetime, working_hours: dict[str, Any]) -> bool:
    hours = _hours_for(dt, working_hours)
    if hours is None:
        return False
    open_t, close_t = hours
    return open_t <= dt.time() < close_t


def _next_opening_within_24h(
    now: datetime,
    working_hours: dict[str, Any],
) -> datetime | None:
    """Ищет ближайшее открытие ≤24ч от now.

    Проверяет текущий день (если открытие ещё впереди) и следующий день.
    Если открытия в этом интервале нет — возвращает None.
    """
    deadline = now + timedelta(hours=24)

    today_hours = _hours_for(now, working_hours)
    if today_hours is not None:
        open_t, _ = today_hours
        opening_today = datetime.combine(now.date(), open_t, tzinfo=now.tzinfo)
        if now <= opening_today <= deadline:
            return opening_today

    next_day = now + timedelta(days=1)
    tomorrow_hours = _hours_for(next_day, working_hours)
    if tomorrow_hours is not None:
        open_t, _ = tomorrow_hours
        opening_tomorrow = datetime.combine(next_day.date(), open_t, tzinfo=now.tzinfo)
        if opening_tomorrow <= deadline:
            return opening_tomorrow

    return None


def validate_time_slot(
    requested_time: datetime | None,
    order_type: OrderType,
    shop_settings: Any,
    now: datetime | None = None,
) -> datetime:
    """Возвращает estimated_ready_at.

    ASAP: now + prep (+ delivery_time для DELIVERY). Вне часов — ищет следующее
    открытие ≤24ч, иначе raise.

    Конкретное время: в будущем, ≥ prep от now, в рабочих часах.
    """
    if now is None:
        now = datetime.now(UTC)

    prep = timedelta(minutes=int(shop_settings.default_prep_time_minutes))
    delivery_extra = (
        timedelta(minutes=int(shop_settings.estimated_delivery_time_minutes))
        if order_type == OrderType.DELIVERY
        else timedelta(0)
    )
    full_lead = prep + delivery_extra
    working_hours = shop_settings.working_hours or {}

    if requested_time is None:
        estimated = now + full_lead
        if _is_within_hours(estimated, working_hours):
            return estimated
        opening = _next_opening_within_24h(now, working_hours)
        if opening is None:
            raise TimeSlotValidationError("No opening within 24h")
        return opening + full_lead

    if requested_time <= now:
        raise TimeSlotValidationError("requested_time in the past")
    if requested_time - now < prep:
        raise TimeSlotValidationError("requested_time below prep_time")
    if not _is_within_hours(requested_time, working_hours):
        raise TimeSlotValidationError("requested_time outside working hours")
    return requested_time
