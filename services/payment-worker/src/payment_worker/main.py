# START_MODULE_CONTRACT
#   PURPOSE: Celery application bootstrap for the payment_worker process —
#            wires the broker, declares the `payments` queue, autodiscovers
#            tasks, and validates Settings at worker boot so misconfigured
#            live-mode (empty creds / sandbox URL) fails fast instead of at
#            first request.
#   SCOPE:   Celery app singleton + boot-time safety-rail signal handler.
#            Imported by tasks.py and yukassa_fake.py to register tasks.
#   DEPENDS: celery, kombu, payment_worker.settings, payment_worker.yukassa_fake
#   LINKS:   docs/development-plan.xml M-PAYMENT-WORKER, PDD §4.2, INV-015
#            (no secrets in code; safety-rail enforces non-empty creds at boot)
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   celery_app - Celery application instance (broker bound to REDIS_URL,
#                default queue `payments`)
# END_MODULE_MAP

import os

from celery import Celery
from kombu import Queue

celery_app = Celery(
    "payment_worker",
    broker=os.getenv("REDIS_URL", "redis://redis:6379/0"),
)

celery_app.conf.task_queues = [Queue("payments")]
celery_app.conf.task_default_queue = "payments"

celery_app.autodiscover_tasks(["payment_worker"])

# Принудительная регистрация fake-callback: autodiscover ищет только
# `payment_worker.tasks`, но `yukassa_fake_callback` живёт в `yukassa_fake.py`.
# Без этого импорта fake-backend ломается с KeyError в консьюмере.
from payment_worker import yukassa_fake  # noqa: E402, F401


# Boot-time safety-rail: при старте воркера валидируем Settings, чтобы
# мисконфиг (live + пустые creds / sandbox URL) ронял процесс сразу. Не
# делаем это на импорт — тесты импортируют main без валидных creds.
from celery.signals import worker_init  # noqa: E402


@worker_init.connect
def _validate_settings_on_boot(**_kwargs):
    import sys

    from payment_worker.settings import Settings

    try:
        Settings()  # type: ignore[call-arg]
    except Exception as exc:
        print(f"FATAL: payment-worker settings invalid: {exc}", file=sys.stderr)
        sys.exit(1)
