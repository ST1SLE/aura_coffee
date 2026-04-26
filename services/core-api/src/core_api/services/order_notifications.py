# START_MODULE_CONTRACT
#   PURPOSE: Thin wrapper around Celery dispatch for order status change
#            notifications. Tests monkey-patch send_order_notification on this
#            module so the lifecycle code stays pure.
#   SCOPE:   single send_order_notification helper.
#   DEPENDS: M-SHARED (OrderStatus), celery_app
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §6.1, §6.4
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   send_order_notification - dispatch sms_worker.order_status_changed task
# END_MODULE_MAP
"""Тонкий модуль постановки SMS-уведомлений о смене статуса заказа.

Конкретная реализация sms-worker шлёт из Phase 5; здесь — только enqueue.
Тесты monkey-patch’ат `send_order_notification`.
"""
from __future__ import annotations

from shared.enums import OrderStatus

from core_api.celery_app import celery_app


# START_CONTRACT: send_order_notification
#   PURPOSE: Enqueue an sms_worker.order_status_changed task carrying order id,
#            new status, and optional reason.
#   INPUTS:  order: Order — only `id` is read (kept un-typed for test fakes)
#            new_status: OrderStatus
#            reason: str | None
#   OUTPUTS: None
#   SIDE_EFFECTS: Celery .send_task() to default queue; raises broker error to caller.
#   LINKS:   PDD §6.1, §6.4
# END_CONTRACT: send_order_notification
def send_order_notification(
    order, new_status: OrderStatus, reason: str | None = None
) -> None:
    """Ставит задачу в sms-worker на отправку уведомления о новом статусе."""
    celery_app.send_task(
        "sms_worker.order_status_changed",
        args=[str(order.id), new_status.value, reason],
    )
