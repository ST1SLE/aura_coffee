"""Admin refund recovery routes (PDD §6.2, INV-002)."""
from __future__ import annotations

# START_MODULE_CONTRACT
#   PURPOSE: Admin-only HTTP surface for retrying failed YuKassa refunds.
#            RBACMiddleware enforces ADMIN before handler dispatch; the handler
#            delegates retry eligibility and Celery enqueue to services.refund_retry.
#   SCOPE:   POST /api/v1/admin/orders/{order_id}/refund/retry.
#   DEPENDS: core_api.services.refund_retry, core_api.schemas.refund_retry,
#            core_api.deps.database, RBACMiddleware via rbac_matrix.ROUTE_MATRIX.
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §6.2, INV-002,
#            INV-004, INV-016
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   router                   - APIRouter("/api/v1/admin", tags=["admin-refunds"])
#   retry_admin_order_refund - POST /orders/{order_id}/refund/retry
# END_MODULE_MAP
import uuid  # noqa: TC003

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session  # noqa: TC002

from core_api.deps import database as _db_dep
from core_api.schemas.refund_retry import RefundRetryResponse
from core_api.services.refund_retry import RefundRetryError, retry_refund_for_order

router = APIRouter(prefix="/api/v1/admin", tags=["admin-refunds"])


def _get_session():
    yield from _db_dep.get_session()


DB_SESSION = Depends(_get_session)


# START_CONTRACT: retry_admin_order_refund
#   PURPOSE: Admin command to retry a failed refund for one order. Returns 202
#            once the payment-worker task is queued; the worker/webhook own the
#            payment/refund state changes.
#   INPUTS:  order_id: UUID path parameter, Session.
#   OUTPUTS: 202 RefundRetryResponse; 404 order/payment missing; 409 when the
#            payment is not in REFUND_FAILED or has zero amount.
#   SIDE_EFFECTS: Celery task enqueue only. No raw customer PII in request,
#                 response, or logs.
#   LINKS:   PDD §6.2, INV-002, INV-004, INV-013, INV-016
# END_CONTRACT: retry_admin_order_refund
@router.post(
    "/orders/{order_id}/refund/retry",
    response_model=RefundRetryResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_admin_order_refund(
    order_id: uuid.UUID,
    db: Session = DB_SESSION,
) -> RefundRetryResponse:
    try:
        payment = retry_refund_for_order(order_id=order_id, db_session=db)
    except RefundRetryError as exc:
        if exc.reason in {"order_not_found", "payment_not_found"}:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=exc.reason,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.reason,
        ) from exc

    return RefundRetryResponse(
        order_id=order_id,
        payment_id=payment.id,
        payment_status=payment.status.value,
    )
