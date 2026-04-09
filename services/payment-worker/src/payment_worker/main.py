from celery import Celery
from kombu import Queue

from payment_worker.settings import settings

celery_app = Celery(
    "payment_worker",
    broker=settings.redis_url,
)

celery_app.conf.task_queues = [Queue("payments")]
celery_app.conf.task_default_queue = "payments"

celery_app.autodiscover_tasks(["payment_worker"])
