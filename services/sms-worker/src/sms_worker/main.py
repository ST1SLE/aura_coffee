from celery import Celery

from sms_worker.settings import settings

celery_app = Celery(
    "sms_worker",
    broker=settings.redis_url,
)

celery_app.autodiscover_tasks(["sms_worker", "sms_worker.tasks"])
