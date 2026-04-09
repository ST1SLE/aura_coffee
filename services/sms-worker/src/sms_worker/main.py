from celery import Celery
from kombu import Queue

from sms_worker.settings import settings

celery_app = Celery(
    "sms_worker",
    broker=settings.redis_url,
)

celery_app.conf.task_queues = [Queue("sms")]
celery_app.conf.task_default_queue = "sms"

celery_app.autodiscover_tasks(["sms_worker.tasks"])
