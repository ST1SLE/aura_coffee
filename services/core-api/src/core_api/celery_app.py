"""Celery-клиент core-api.

Используется только для постановки задач в очередь (`send_task`).
Регистрация воркеров живёт в services/payment-worker и services/sms-worker.
"""
from celery import Celery

from core_api.settings import settings

celery_app = Celery("core_api", broker=settings.redis_url)
