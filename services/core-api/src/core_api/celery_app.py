"""Celery-клиент core-api.

Используется как:
- клиент для постановки задач в очередь (`send_task` → payment-worker, sms-worker);
- owner core-api тасок (`core_api.tasks.*`) и их Beat-расписания.

Регистрация воркеров payment-worker/sms-worker живёт в их отдельных codebase;
здесь — только то, что принадлежит core-api.
"""
# START_MODULE_CONTRACT
#   PURPOSE: Celery client + Beat schedule owned by core-api. Dispatches tasks
#            to payment-worker / sms-worker queues and owns the pickup-autoclose
#            periodic job.
#   SCOPE:   App factory configuration: broker/backend URLs, task discovery,
#            Beat schedule entries.
#   DEPENDS: M-SHARED (settings), Celery, Redis broker.
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §6.1 (auto-close),
#            PDD §7.1 Phase 6 item 4
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   celery_app - configured Celery() instance shared by core-api send_task callers and Beat
# END_MODULE_MAP

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
