# START_MODULE_CONTRACT
#   PURPOSE: Backwards-compatible wrapper around the canonical order-status
#            notification service. Lifecycle modules import this stable patch
#            point; production calls delegate to services.notification, which
#            writes IN_APP/SMS rows and enqueues the registered sms-worker task.
#   SCOPE:   single send_order_notification helper.
#   DEPENDS: M-SHARED (OrderStatus), SQLAlchemy object_session,
#            services.notification
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §6.1, §7.8, INV-013
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   send_order_notification - delegate to services.notification boundary
# END_MODULE_MAP
"""Compatibility wrapper for order-status notifications.

Historically lifecycle services imported this module and it sent an obsolete
`sms_worker.order_status_changed` task. Keep the import/patch point, but route
real runtime behavior through `core_api.services.notification`.
"""
from __future__ import annotations

from sqlalchemy.orm import object_session

from shared.enums import OrderStatus

from core_api.services import notification as notification_service


# START_CONTRACT: send_order_notification
#   PURPOSE: Delegate a lifecycle/cancellation/delivery status notification to
#            the canonical notification service while preserving the legacy
#            call signature used by lifecycle modules and tests.
#   INPUTS:  order: Order — only `id` is read (kept un-typed for test fakes)
#            new_status: OrderStatus
#            reason: str | None
#            actor_role: str | None — used to classify admin CANCELLED
#   OUTPUTS: None
#   SIDE_EFFECTS: DB INSERT on notifications via services.notification; SMS
#                 enqueue to registered `sms_worker.send_order_notification_sms`.
#   LINKS:   PDD §6.1, §7.8, INV-013
# END_CONTRACT: send_order_notification
def send_order_notification(
    order,
    new_status: OrderStatus,
    reason: str | None = None,
    actor_role: str | None = None,
) -> None:
    """Persist in-app/SMS notification rows and enqueue SMS when required."""
    session = object_session(order)
    if session is None:
        raise ValueError("Order notification requires an attached SQLAlchemy session")

    cancelled_by = None
    if new_status == OrderStatus.CANCELLED:
        cancelled_by = getattr(order, "cancelled_by", None) or actor_role

    notification_service.send_order_notification(
        order_id=order.id,
        user_id=order.user_id,
        new_status=new_status,
        db_session=session,
        cancelled_by=cancelled_by,
    )
