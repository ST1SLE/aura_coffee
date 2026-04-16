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
