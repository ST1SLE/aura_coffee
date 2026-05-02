# START_MODULE_CONTRACT
#   PURPOSE: Admin refund-retry command for PDD §6.2 Payment lifecycle
#            recovery. Validates that an order's payment is in REFUND_FAILED
#            and enqueues payment_worker.tasks.initiate_refund with a fresh
#            idempotency key; payment-worker owns the actual DB transition.
#   SCOPE:   retry_refund_for_order plus reason-tagged domain error.
#   DEPENDS: M-SHARED (Order, Payment, PaymentStatus), M-DATABASE,
#            core_api.celery_app.
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §6.2, INV-002,
#            INV-004, INV-016
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   RefundRetryError       - reason-tagged retry validation error
#   retry_refund_for_order - enqueue a retry for Payment.REFUND_FAILED
# END_MODULE_MAP
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from core_api import celery_app as _celery_mod
from shared.enums import PaymentStatus
from shared.models import Order, Payment

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

celery_app = _celery_mod.celery_app


# START_CONTRACT: RefundRetryError
#   PURPOSE: Domain error for admin refund retry validation with a stable
#            .reason for router-to-HTTP mapping.
#   INPUTS:  reason: str — order_not_found | payment_not_found |
#                    refund_not_retryable
#   OUTPUTS: Exception with .reason.
#   SIDE_EFFECTS: none
#   LINKS:   PDD §6.2, INV-016
# END_CONTRACT: RefundRetryError
class RefundRetryError(Exception):
    """Reason-tagged refund retry domain error."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


# START_CONTRACT: retry_refund_for_order
#   PURPOSE: Enqueue an admin-initiated retry for a failed YuKassa refund.
#            The payment-worker task creates the new refunds row and performs
#            REFUND_FAILED -> REFUND_PENDING after YuKassa accepts the call.
#   INPUTS:  order_id: UUID — order whose payment needs retry
#            db_session: Session — current Core API DB session
#   OUTPUTS: Payment — the local payment row that was validated/enqueued
#   SIDE_EFFECTS: Celery send_task to payment_worker.tasks.initiate_refund with
#                 args [payment_id, amount, fresh idempotency key]. No DB write;
#                 invalid states raise RefundRetryError.
#   LINKS:   PDD §6.2, INV-002, INV-004, INV-016
# END_CONTRACT: retry_refund_for_order
def retry_refund_for_order(
    *,
    order_id: uuid.UUID,
    db_session: Session,
) -> Payment:
    order = db_session.get(Order, order_id)
    if order is None:
        raise RefundRetryError("order_not_found")

    payment = db_session.query(Payment).filter_by(order_id=order.id).one_or_none()
    if payment is None:
        raise RefundRetryError("payment_not_found")

    if payment.status != PaymentStatus.REFUND_FAILED or payment.amount <= 0:
        raise RefundRetryError("refund_not_retryable")

    idempotency_key = f"refund-retry-{payment.id}-{uuid.uuid4()}"
    celery_app.send_task(
        "payment_worker.tasks.initiate_refund",
        args=[str(payment.id), payment.amount, idempotency_key],
    )
    return payment
