"""Celery-таска `pickup.close_stale` — обёртка над сервисом `pickup_autoclose`.

Запускается Celery Beat каждые 60 секунд (см. `celery_app.beat_schedule`).
Тонкая обёртка: открывает сессию БД, зовёт сервис, возвращает count.
"""
from __future__ import annotations

from datetime import datetime, timezone

from core_api.celery_app import celery_app


@celery_app.task(name="pickup.close_stale")
def close_stale_pickups_task() -> int:
    # Импорты внутри функции — избегаем цикла с services.pickup_autoclose,
    # который импортируется при сборке task registry (в некоторых случаях).
    from core_api.deps.database import SessionLocal
    from core_api.services import pickup_autoclose as svc

    with SessionLocal() as db:
        return svc.close_stale_pickups(db, datetime.now(timezone.utc))
