"""RED: тесты хелпера compute_range (dashboard-api-red).

Все импорты target-символов выполняются ВНУТРИ тел тестов — в RED-фазе
модуль core_api.services.admin_stats отсутствует, и import на уровне
модуля сорвал бы сборку файла.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest


# ===========================================================================
# 1.x — compute_range helper tests
# ===========================================================================


def test_compute_range_symbol_absent() -> None:
    """1.1 — символ compute_range должен существовать после GREEN."""
    from core_api.services.admin_stats import compute_range  # noqa: F401

    assert callable(compute_range)


def test_compute_range_today_starts_at_europe_moscow_midnight() -> None:
    """1.2 — "today" стартует в полночь Europe/Moscow, переведённую в UTC."""
    from core_api.services.admin_stats import compute_range

    start, _end = compute_range("today")

    moscow = ZoneInfo("Europe/Moscow")
    expected_start = datetime.combine(date.today(), time.min, tzinfo=moscow).astimezone(UTC)
    assert start == expected_start

    # Сдвиг +3ч: start НЕ должен совпасть с UTC-полночью того же календарного дня.
    utc_midnight = datetime.combine(date.today(), time.min, tzinfo=timezone.utc)
    assert start != utc_midnight


def test_compute_range_today_end_is_now_utc() -> None:
    """1.3 — end близок к текущему UTC-времени и имеет tzinfo=UTC."""
    from core_api.services.admin_stats import compute_range

    _start, end = compute_range("today")

    now = datetime.now(timezone.utc)
    assert end.tzinfo == timezone.utc
    assert abs((now - end).total_seconds()) < 2


def test_compute_range_week_spans_seven_days() -> None:
    """1.4 — week = [now - 7d, now)."""
    from core_api.services.admin_stats import compute_range

    start, end = compute_range("week")

    assert abs((end - start) - timedelta(days=7)) < timedelta(seconds=2)
    now = datetime.now(timezone.utc)
    assert abs((now - end).total_seconds()) < 2


def test_compute_range_month_spans_thirty_days() -> None:
    """1.5 — month = [now - 30d, now)."""
    from core_api.services.admin_stats import compute_range

    start, end = compute_range("month")

    assert abs((end - start) - timedelta(days=30)) < timedelta(seconds=2)


@pytest.mark.parametrize("range_param", ["today", "week", "month"])
def test_compute_range_returns_half_open_interval_with_start_lt_end(range_param: str) -> None:
    """1.6 — для любого диапазона выполняется start < end (half-open)."""
    from core_api.services.admin_stats import compute_range

    start, end = compute_range(range_param)
    assert start < end
