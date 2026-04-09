from celery import Celery

from payment_worker.settings import settings

celery_app = Celery(
    "payment_worker",
    broker=settings.redis_url,
)

celery_app.autodiscover_tasks(["payment_worker"])
