"""Celery-клиент core-api.

Используется как:
- клиент для постановки задач в очередь (`send_task` → payment-worker, sms-worker);
- owner core-api тасок (`core_api.tasks.*`) и их Beat-расписания.

Регистрация воркеров payment-worker/sms-worker живёт в их отдельных codebase;
здесь — только то, что принадлежит core-api.
"""
from celery import Celery

from core_api.settings import settings

celery_app = Celery(
    "core_api",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["core_api.tasks.pickup_autoclose"],
)

# Beat-расписание: pickup-auto-close каждые 60 секунд
# (PDD §6.1 row "Автозакрытие по таймеру", §7.1 Phase 6 item 4).
celery_app.conf.beat_schedule = {
    "close-stale-pickups-every-60s": {
        "task": "pickup.close_stale",
        "schedule": 60.0,
    },
}
