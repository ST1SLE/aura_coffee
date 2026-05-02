# START_MODULE_CONTRACT
#   PURPOSE: Read-only order feeds for both customer (own history) and staff
#            (all-orders, INV-010 RBAC enforced upstream). Sort rule: finalized
#            orders by updated_at DESC, others by created_at DESC. Staff detail
#            includes a transient customer contact projection for operations.
#   SCOPE:   list_orders, list_orders_for_staff, get_order_for_staff.
#   DEPENDS: M-SHARED (Order, OrderStatus, OrderType), M-DATABASE,
#            schemas.order_history, core_api.utils.crypto
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §5.4, §7.7, §7.10,
#            INV-010, INV-013
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   OrderNotFoundForStaffError - staff get-by-id missing target
#   list_orders                - customer-scoped paginated history
#   list_orders_for_staff      - staff-scoped feed with status/type filters
#   get_order_for_staff        - single-order detail with staff-only contact projection
# END_MODULE_MAP
"""Сервис list_orders — пагинированная история заказов пользователя (PDD §7.7).

Дополнительно: staff-scoped helpers для admin-orders-api (PDD §4.5, INV-010):
- list_orders_for_staff: пагинированный фид заказов всех клиентов.
- get_order_for_staff: одиночный заказ без ownership-check.
"""
from __future__ import annotations

import uuid

from cryptography.exceptions import InvalidTag
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from core_api.schemas.order_history import (
    OrderListResponse,
    OrderResponse,
    StaffOrderDetailResponse,
)
from core_api.settings import settings
from core_api.utils.crypto import decrypt_phone
from shared.enums import OrderStatus, OrderType
from shared.models.order import Order
from shared.models.user_profile import UserProfile


# Финальные статусы — для них фид сортируется по updated_at DESC (PDD §5.4).
_FINALIZED_STATUSES = {OrderStatus.COMPLETED, OrderStatus.CANCELLED}
_CONTACT_STATUSES = {OrderStatus.PAID, OrderStatus.PREPARING, OrderStatus.READY}


def _decrypt_contact_phone(encrypted_phone: bytes | None) -> str | None:
    """Return raw phone for staff contact without logging the PII payload."""
    if not encrypted_phone:
        return None
    try:
        key = bytes.fromhex(settings.encryption_key)
        return decrypt_phone(encrypted_phone, key)
    except (InvalidTag, ValueError):
        return None


def _staff_detail_response(
    order: Order, profile: UserProfile | None
) -> StaffOrderDetailResponse:
    """Build the staff detail DTO while keeping contact fields out of order rows."""
    base = StaffOrderDetailResponse.model_validate(order)
    contact_allowed = order.status in _CONTACT_STATUSES
    return base.model_copy(
        update={
            "customer_display_name": (
                profile.display_name if profile and contact_allowed else None
            ),
            "customer_contact_phone": (
                _decrypt_contact_phone(profile.phone)
                if profile and contact_allowed
                else None
            ),
        }
    )


# START_CONTRACT: OrderNotFoundForStaffError
#   PURPOSE: Raised by get_order_for_staff when id is unknown — kept distinct
#            from customer-scoped errors so the router can map cleanly.
#   INPUTS:  message: str
#   OUTPUTS: Exception instance.
#   SIDE_EFFECTS: none
# END_CONTRACT: OrderNotFoundForStaffError
class OrderNotFoundForStaffError(Exception):
    """Заказ с таким id отсутствует — staff-вариант (отделён от customer-scoped ошибки)."""


# START_CONTRACT: list_orders
#   PURPOSE: Customer-scoped paginated order history sorted by created_at DESC,
#            with eager-loaded items.
#   INPUTS:  user_id: UUID, page: int, per_page: int, db_session: Session
#   OUTPUTS: OrderListResponse
#   SIDE_EFFECTS: DB SELECTs only.
#   LINKS:   PDD §7.7, INV-010 (router enforces ownership)
# END_CONTRACT: list_orders
def list_orders(
    *,
    user_id: uuid.UUID,
    page: int = 1,
    per_page: int = 20,
    db_session: Session,
) -> OrderListResponse:
    """Возвращает заказы пользователя, DESC по created_at, с eager-load items.

    Два SQL-запроса: count(*) для total_count + SELECT с selectinload для items.
    """
    total = db_session.execute(
        select(func.count()).select_from(Order).where(Order.user_id == user_id)
    ).scalar_one()

    rows = (
        db_session.execute(
            select(Order)
            .where(Order.user_id == user_id)
            .options(selectinload(Order.items))
            .order_by(Order.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        .scalars()
        .all()
    )

    orders = [OrderResponse.model_validate(row) for row in rows]
    return OrderListResponse(
        orders=orders,
        total_count=int(total),
        page=page,
        per_page=per_page,
    )


# START_CONTRACT: list_orders_for_staff
#   PURPOSE: Staff-scoped paginated feed across all users with status filter
#            ("active" or specific OrderStatus) and optional type filter.
#   INPUTS:  status_filter: OrderStatus | str
#            type_filter: OrderType | None
#            page, per_page: int
#            db_session: Session
#   OUTPUTS: OrderListResponse
#   SIDE_EFFECTS: DB SELECTs only.
#   LINKS:   PDD §5.4, INV-010 (admin/barista/courier RBAC at router)
# END_CONTRACT: list_orders_for_staff
def list_orders_for_staff(
    *,
    status_filter: OrderStatus | str,
    type_filter: OrderType | None,
    page: int,
    per_page: int,
    db_session: Session,
) -> OrderListResponse:
    """Staff-scoped фид: видны заказы всех пользователей (INV-010).

    Семантика status_filter:
    - "active" → status NOT IN (COMPLETED, CANCELLED), хитит partial index из PDD §5.4.
    - конкретный OrderStatus → status = <value>.

    Сортировка:
    - финальные (COMPLETED, CANCELLED) → updated_at DESC;
    - остальные (включая "active") → created_at DESC.
    """
    where_clauses = []
    if status_filter == "active":
        where_clauses.append(Order.status.notin_(_FINALIZED_STATUSES))
        order_by = Order.created_at.desc()
    else:
        # На этом пути status_filter уже OrderStatus (валидируется в роутере).
        where_clauses.append(Order.status == status_filter)
        if status_filter in _FINALIZED_STATUSES:
            order_by = Order.updated_at.desc()
        else:
            order_by = Order.created_at.desc()

    if type_filter is not None:
        where_clauses.append(Order.type == type_filter)

    total = db_session.execute(
        select(func.count()).select_from(Order).where(*where_clauses)
    ).scalar_one()

    rows = (
        db_session.execute(
            select(Order)
            .where(*where_clauses)
            .options(selectinload(Order.items))
            .order_by(order_by)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        .scalars()
        .all()
    )

    orders = [OrderResponse.model_validate(row) for row in rows]
    return OrderListResponse(
        orders=orders,
        total_count=int(total),
        page=page,
        per_page=per_page,
    )


# START_CONTRACT: get_order_for_staff
#   PURPOSE: Load a single order by id without ownership check (RBAC enforced
#            at router). Eager-loads items and adds transient staff contact
#            fields from UserProfile without storing them on Order.
#   INPUTS:  order_id: UUID, db_session: Session
#   OUTPUTS: StaffOrderDetailResponse
#   SIDE_EFFECTS: DB SELECT only; raises OrderNotFoundForStaffError on miss.
#   LINKS:   PDD §7.10, INV-010, INV-013
# END_CONTRACT: get_order_for_staff
def get_order_for_staff(
    *,
    order_id: uuid.UUID,
    db_session: Session,
) -> StaffOrderDetailResponse:
    """Одиночный заказ без ownership-check (INV-010, S-ADMIN-003)."""
    row = db_session.execute(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.items))
    ).scalar_one_or_none()

    if row is None:
        raise OrderNotFoundForStaffError(f"order {order_id} not found")

    profile = db_session.execute(
        select(UserProfile).where(UserProfile.user_id == row.user_id)
    ).scalar_one_or_none()

    return _staff_detail_response(row, profile)
