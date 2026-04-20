"""Маршруты staff-feed заказов (admin-orders-api, PDD §4.5, INV-010).

GET /api/v1/admin/orders               → OrderListResponse
GET /api/v1/admin/orders/{order_id}    → OrderResponse

RBAC: только {ADMIN, BARISTA}, прописано в rbac_matrix.ROUTE_MATRIX.
401/403 обрабатывает RBACMiddleware — здесь явных auth-deps нет.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from core_api.deps import database as _db_dep
from core_api.schemas.order_history import OrderListResponse, OrderResponse
from core_api.services.order_history import (
    OrderNotFoundForStaffError,
    get_order_for_staff,
    list_orders_for_staff,
)
from shared.enums import OrderStatus, OrderType

router = APIRouter(prefix="/api/v1/admin", tags=["admin-orders"])


# Обёртка для patch-friendly dep resolution (см. routers/order_history.py)
def _get_session():
    yield from _db_dep.get_session()


def _coerce_status(raw: str) -> OrderStatus | str:
    """Принимает 'active' или любое значение OrderStatus, иначе → 422."""
    if raw == "active":
        return "active"
    try:
        return OrderStatus(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status filter: {raw!r}",
        ) from exc


@router.get("/orders", response_model=OrderListResponse)
def list_admin_orders(
    status: str = Query("active"),
    type: OrderType | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(_get_session),
) -> OrderListResponse:
    """Пагинированный staff-фид заказов (см. PDD §4.5, S-ADMIN-003)."""
    status_filter = _coerce_status(status)
    return list_orders_for_staff(
        status_filter=status_filter,
        type_filter=type,
        page=page,
        per_page=per_page,
        db_session=db,
    )


@router.get("/orders/{order_id}", response_model=OrderResponse)
def get_admin_order_detail(
    order_id: uuid.UUID,
    db: Session = Depends(_get_session),
) -> OrderResponse:
    """Одиночный заказ для staff — без ownership-check."""
    try:
        return get_order_for_staff(order_id=order_id, db_session=db)
    except OrderNotFoundForStaffError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="order_not_found",
        ) from exc
