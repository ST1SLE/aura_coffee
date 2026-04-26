"""Маршруты истории заказов и repeat (PDD §7.7).

GET  /api/v1/orders                       → OrderListResponse
POST /api/v1/orders/{order_id}/repeat     → RepeatOrderResult

Оба маршрута авторизованы под ролью CUSTOMER через ROUTE_MATRIX.
"""
from __future__ import annotations

# START_MODULE_CONTRACT
#   PURPOSE: HTTP routes for customer order history under /api/v1/orders
#            — list own orders + repeat-order from a historical entry.
#   SCOPE:   Read-only history listing and the repeat-order side effect
#            (rebuilds cart at current prices). CUSTOMER-only via
#            rbac_matrix.ROUTE_MATRIX.
#   DEPENDS: M-DATABASE (Session), Redis,
#            core_api.services.{order_history,order_repeat},
#            core_api.deps.{auth,database,redis}.
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §7.7,
#            INV-002, INV-013 (own-orders only).
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   router             - APIRouter("/api/v1/orders", tags=["orders-history"])
#   get_own_orders     - GET  /api/v1/orders
#   post_repeat_order  - POST /api/v1/orders/{order_id}/repeat
# END_MODULE_MAP

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from core_api.deps import database as _db_dep
from core_api.deps import redis as _redis_dep
from core_api.deps.auth import get_current_user
from core_api.schemas.order_history import OrderListResponse, RepeatOrderResult
from core_api.services.order_history import list_orders
from core_api.services.order_repeat import (
    NoItemsAvailableError,
    OrderNotFoundError,
    repeat_order,
)

router = APIRouter(prefix="/api/v1/orders", tags=["orders-history"])


# Обёртки для patch-friendly dep resolution (см. routers/cart.py)
def _get_redis():
    yield from _redis_dep.get_redis()


def _get_session():
    yield from _db_dep.get_session()


# START_CONTRACT: get_own_orders
#   PURPOSE: Paginated history of orders for the current customer.
#   INPUTS:  page (1+), per_page (1..50), current_user, Session.
#   OUTPUTS: 200 OrderListResponse.
#   SIDE_EFFECTS: none (read-only DB query).
#   LINKS:   PDD §7.7, INV-002, INV-013, services.order_history.
# END_CONTRACT: get_own_orders
@router.get("", response_model=OrderListResponse)
def get_own_orders(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(_get_session),
) -> OrderListResponse:
    """Пагинированная история заказов текущего пользователя."""
    return list_orders(
        user_id=current_user["user_id"],
        page=page,
        per_page=per_page,
        db_session=db,
    )


# START_CONTRACT: post_repeat_order
#   PURPOSE: Repeat a historical order — rebuilds the Redis cart at
#            current prices and stop-list state.
#   INPUTS:  order_id: UUID, current_user, Session, Redis client.
#   OUTPUTS: 200 RepeatOrderResult; 404 order_not_found;
#            422 NoItemsAvailableError (all items archived/stopped).
#   SIDE_EFFECTS: Redis write — rewrites cart with current snapshot.
#                 No DB writes (history rows are immutable, INV-014).
#   LINKS:   PDD §7.7, INV-002, INV-006, INV-013, INV-014,
#            services.order_repeat.
# END_CONTRACT: post_repeat_order
@router.post("/{order_id}/repeat", response_model=RepeatOrderResult)
def post_repeat_order(
    order_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(_get_session),
    redis_client=Depends(_get_redis),
) -> RepeatOrderResult:
    """Повтор исторического заказа: заполняет корзину текущими ценами."""
    try:
        return repeat_order(
            order_id=order_id,
            user_id=current_user["user_id"],
            redis=redis_client,
            db_session=db,
        )
    except OrderNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="order_not_found",
        )
    except NoItemsAvailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
