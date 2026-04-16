"""Order state machine — сервисный слой (PDD §6.1, INV-003, INV-010, INV-016).

`transition_order` — единственная точка входа для переходов статуса заказа.
Запрещённые переходы и запрещённые роли → `OrderTransitionError(reason=...)`.
При переходе в COMPLETED начисляются баллы лояльности из суммы товаров
(без delivery_fee, INV-003).
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from shared.enums import LoyaltyTransactionType, OrderStatus, OrderType
from shared.models import (
    LoyaltyAccount,
    LoyaltyTransaction,
    Order,
    ShopSettings,
)

from core_api.services.order_notifications import send_order_notification


class OrderTransitionError(Exception):
    """Доменная ошибка: переход недопустим по правилам §6.1 / §6 / INV-010."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


# Allow-list переходов из PDD §6.1, которые обслуживает ЭТОТ сервис.
# CREATED→PAID и CREATED→CANCELLED — территория payment-webhook, не наша.
_ALLOWED_TRANSITIONS: set[tuple[OrderStatus, OrderStatus]] = {
    (OrderStatus.PAID, OrderStatus.PREPARING),
    (OrderStatus.PAID, OrderStatus.CANCELLED),
    (OrderStatus.PREPARING, OrderStatus.READY),
    (OrderStatus.PREPARING, OrderStatus.CANCELLED),
    (OrderStatus.READY, OrderStatus.IN_DELIVERY),
    (OrderStatus.READY, OrderStatus.COMPLETED),
    (OrderStatus.READY, OrderStatus.CANCELLED),
    (OrderStatus.IN_DELIVERY, OrderStatus.COMPLETED),
}


# (from, to) → множество ролей, которым разрешён переход.
# CUSTOMER отсутствует везде — отмена клиентом идёт через order_cancel.
_ALLOWED_ROLES: dict[tuple[OrderStatus, OrderStatus], frozenset[str]] = {
    (OrderStatus.PAID, OrderStatus.PREPARING):        frozenset({"barista", "admin"}),
    (OrderStatus.PAID, OrderStatus.CANCELLED):        frozenset({"admin"}),
    (OrderStatus.PREPARING, OrderStatus.READY):       frozenset({"barista", "admin"}),
    (OrderStatus.PREPARING, OrderStatus.CANCELLED):   frozenset({"admin"}),
    (OrderStatus.READY, OrderStatus.IN_DELIVERY):     frozenset({"courier", "admin"}),
    (OrderStatus.READY, OrderStatus.COMPLETED):       frozenset({"barista", "admin"}),
    (OrderStatus.READY, OrderStatus.CANCELLED):       frozenset({"admin"}),
    (OrderStatus.IN_DELIVERY, OrderStatus.COMPLETED): frozenset({"courier", "admin"}),
}


def _accrue_loyalty(order: Order, db: Session) -> None:
    """Начисление баллов при COMPLETED (INV-003: только с суммы товаров)."""
    settings_row = db.get(ShopSettings, 1)
    percent = settings_row.loyalty_percent if settings_row is not None else 0
    goods_total = order.total - order.delivery_fee
    accrual = (goods_total * percent) // 100
    if accrual <= 0:
        return

    account = db.get(LoyaltyAccount, order.user_id)
    new_balance = (account.balance if account is not None else 0) + accrual
    if account is not None:
        account.balance = new_balance
    db.add(
        LoyaltyTransaction(
            user_id=order.user_id,
            order_id=order.id,
            type=LoyaltyTransactionType.ACCRUAL,
            amount=accrual,
            balance_after=new_balance,
        )
    )
    db.flush()


def transition_order(
    order_id: uuid.UUID,
    new_status: OrderStatus,
    actor_role: str,
    db_session: Session,
) -> Order:
    """Применяет один переход статуса на заказе.

    Args:
        order_id: идентификатор заказа.
        new_status: целевой статус.
        actor_role: роль вызывающего (`customer` / `barista` / `courier` / `admin`).
        db_session: открытая SQLAlchemy-сессия.

    Returns:
        Обновлённый `Order`.

    Raises:
        OrderTransitionError: с машиночитаемым `reason`:
            - `order_not_found` — заказа нет;
            - `forbidden_transition` — пара `(from, to)` не в allow-list;
            - `role_not_allowed` — роль не допущена до перехода;
            - `wrong_order_type_for_transition` — тип заказа не подходит
              (READY→IN_DELIVERY требует DELIVERY, READY→COMPLETED — PICKUP).
    """
    order = db_session.get(Order, order_id)
    if order is None:
        raise OrderTransitionError(reason="order_not_found")

    current = order.status
    key = (current, new_status)

    if key not in _ALLOWED_TRANSITIONS:
        raise OrderTransitionError(reason="forbidden_transition")

    if actor_role not in _ALLOWED_ROLES[key]:
        raise OrderTransitionError(reason="role_not_allowed")

    # Гварды по типу заказа для READY-переходов (PDD §6.1).
    if key == (OrderStatus.READY, OrderStatus.IN_DELIVERY) and order.type != OrderType.DELIVERY:
        raise OrderTransitionError(reason="wrong_order_type_for_transition")
    if key == (OrderStatus.READY, OrderStatus.COMPLETED) and order.type != OrderType.PICKUP:
        raise OrderTransitionError(reason="wrong_order_type_for_transition")

    order.status = new_status
    db_session.flush()

    if new_status == OrderStatus.COMPLETED:
        _accrue_loyalty(order, db_session)

    send_order_notification(order, new_status)
    db_session.commit()
    return order
