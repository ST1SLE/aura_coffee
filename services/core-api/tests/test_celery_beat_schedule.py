"""RED: тесты Celery Beat-расписания.

Фиксируют, что `celery_app.conf.beat_schedule` содержит запись
`close-stale-pickups-every-60s`, указывающую на таску `pickup.close_stale`
с интервалом 60 секунд. GREEN-цикл добавит конфигурацию в
`core_api/celery_app.py`.
"""
from __future__ import annotations


def test_beat_schedule_has_pickup_autoclose_entry() -> None:
    from core_api.celery_app import celery_app

    schedule = celery_app.conf.beat_schedule
    assert "close-stale-pickups-every-60s" in schedule


def test_beat_schedule_entry_points_to_task_with_60s_interval() -> None:
    from core_api.celery_app import celery_app

    entry = celery_app.conf.beat_schedule["close-stale-pickups-every-60s"]
    assert entry["task"] == "pickup.close_stale"
    assert entry["schedule"] == 60.0
