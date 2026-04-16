"""Тонкий модуль постановки SMS-уведомлений о смене статуса заказа.

Конкретная реализация sms-worker шлёт из Phase 5; здесь — только enqueue.
Тесты monkey-patch’ат `send_order_notification`.
"""
from __future__ import annotations

from shared.enums import OrderStatus

from core_api.celery_app import celery_app


def send_order_notification(
    order, new_status: OrderStatus, reason: str | None = None
) -> None:
    """Ставит задачу в sms-worker на отправку уведомления о новом статусе."""
    celery_app.send_task(
        "sms_worker.order_status_changed",
        args=[str(order.id), new_status.value, reason],
    )
