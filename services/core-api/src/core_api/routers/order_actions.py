"""HTTP-эндпоинты staff-действий над заказом (PDD §6.1, §7.6).

- PATCH /api/v1/orders/{order_id}/status — смена статуса (staff).
- POST  /api/v1/orders/{order_id}/cancel — отмена (customer-own-order / admin).

Модуль-уровневые ссылки `transition_order` и `cancel_order` — публичный
патч-пойнт для тестов.
"""
from __future__ import annotations

# START_MODULE_CONTRACT
#   PURPOSE: HTTP routes for staff/customer order actions —
#            PATCH /api/v1/orders/{order_id}/status (BARISTA/COURIER/ADMIN)
#            and POST /api/v1/orders/{order_id}/cancel (CUSTOMER own /
#            ADMIN).
#   SCOPE:   Order state-machine transitions (PDD §6.1) and cancellation
#            flow (PDD §7.6). Ownership check for customer cancels (INV-013).
#   DEPENDS: M-SHARED (models.Order), M-DATABASE,
#            core_api.services.order_lifecycle, services.order_cancel,
#            core_api.deps.{auth,database}.
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §6.1, §7.6,
#            INV-002, INV-005 (cancellation idempotency), INV-010,
#            INV-014 (order_items immutable), INV-016 (state transitions).
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   router               - APIRouter("/api/v1/orders", tags=["order-actions"])
#   patch_order_status   - PATCH /api/v1/orders/{order_id}/status
#   post_order_cancel    - POST  /api/v1/orders/{order_id}/cancel
# END_MODULE_MAP

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core_api.deps import database as _db_dep
from core_api.deps.auth import get_current_user
from core_api.schemas.order import CancelOrderRequest, OrderResponse, OrderStatusUpdate
from core_api.services.order_cancel import OrderCancelError, cancel_order
from core_api.services.order_lifecycle import (
    OrderTransitionError,
    transition_order,
)
from shared.models import Order

router = APIRouter(prefix="/api/v1/orders", tags=["order-actions"])


def _get_session():
    yield from _db_dep.get_session()


def _transition_error_to_http(exc: OrderTransitionError) -> HTTPException:
    if exc.reason == "order_not_found":
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"reason": exc.reason})
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"reason": exc.reason})


def _cancel_error_to_http(exc: OrderCancelError) -> HTTPException:
    if exc.reason == "order_not_found":
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"reason": exc.reason})
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"reason": exc.reason})


# START_CONTRACT: patch_order_status
#   PURPOSE: Drive an Order through its state machine (BARISTA/COURIER/
#            ADMIN) per PDD §6.1.
#   INPUTS:  order_id: UUID, body: OrderStatusUpdate, current_user, Session.
#   OUTPUTS: 200 OrderResponse; 404 order_not_found;
#            409 forbidden_transition / state conflict.
#   SIDE_EFFECTS: DB update on orders.status (atomic, INV-016).
#   LINKS:   PDD §6.1, INV-002, INV-010, INV-014, INV-016,
#            services.order_lifecycle.
# END_CONTRACT: patch_order_status
@router.patch("/{order_id}/status", response_model=OrderResponse)
def patch_order_status(
    order_id: uuid.UUID,
    body: OrderStatusUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(_get_session),
) -> OrderResponse:
    """Переход статуса заказа (BARISTA / COURIER / ADMIN)."""
    try:
        updated = transition_order(order_id, body.new_status, current_user["role"], db)
    except OrderTransitionError as exc:
        raise _transition_error_to_http(exc)
    return updated


# START_CONTRACT: post_order_cancel
#   PURPOSE: Cancel an order (customer own / admin). Triggers refund +
#            loyalty rollback + stop-list restore in service layer.
#   INPUTS:  order_id: UUID, body: CancelOrderRequest, current_user, Session.
#   OUTPUTS: 200 OrderResponse; 404 order_not_found;
#            403 customer cancelling someone else's order; 409 state conflict.
#   SIDE_EFFECTS: Atomic DB writes (orders, payment, loyalty), enqueue
#                 of refund and SMS Celery tasks (INV-004, INV-016).
#   LINKS:   PDD §6.1, §6.2, §7.6, INV-002, INV-004, INV-005, INV-010,
#            INV-013, INV-016, services.order_cancel.
# END_CONTRACT: post_order_cancel
@router.post("/{order_id}/cancel", response_model=OrderResponse)
def post_order_cancel(
    order_id: uuid.UUID,
    body: CancelOrderRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(_get_session),
) -> OrderResponse:
    """Отмена заказа (CUSTOMER-own-order / ADMIN). INV-010, INV-005."""
    role = current_user["role"]

    # Для клиента — проверяем, что заказ принадлежит ему (INV-010).
    if role == "customer":
        order = db.get(Order, order_id)
        if order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail={"reason": "order_not_found"}
            )
        if order.user_id != current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
            )

    try:
        updated = cancel_order(order_id, role, body.reason, db)
    except OrderCancelError as exc:
        raise _cancel_error_to_http(exc)
    return updated
