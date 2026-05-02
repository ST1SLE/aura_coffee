# START_MODULE_CONTRACT
#   PURPOSE: Single entry point for Order state-machine transitions (PDD §6.1).
#            Owns the allow-list, role gating (INV-010), DELIVERY-vs-PICKUP
#            type guards, loyalty accrual on COMPLETED (INV-003), and creation
#            of DeliveryAssignment on PAID→PREPARING for delivery orders.
#   SCOPE:   transition_order (commits + notifies); transition_order_bridge
#            (no-commit/no-notify variant for atomic cascades from delivery_assignment).
#   DEPENDS: M-SHARED (Order, DeliveryAssignment, LoyaltyAccount/Transaction,
#            ShopSettings, enums), M-DATABASE, services.order_notifications
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §6.1, §6.3,
#            INV-003, INV-010, INV-016
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   OrderTransitionError       - reason-tagged transition error
#   transition_order           - commits + dispatches notification
#   transition_order_bridge    - no-commit variant for cascades
# END_MODULE_MAP
"""Order state machine — сервисный слой (PDD §6.1, INV-003, INV-010, INV-016).

`transition_order` — единственная точка входа для переходов статуса заказа.
`transition_order_bridge` — тот же переход, но БЕЗ commit и notify: используется
сервисом `delivery_assignment` для атомарного каскада assignment + order в одной
транзакции (PDD §6.3).
Запрещённые переходы и запрещённые роли → `OrderTransitionError(reason=...)`.
При переходе в COMPLETED начисляются баллы лояльности из суммы товаров
(без delivery_fee, INV-003).
Для DELIVERY-заказов при PAID→PREPARING создаётся `DeliveryAssignment`
в статусе AWAITING_COURIER (PDD §6.3).
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from shared.enums import (
    DeliveryAssignmentStatus,
    LoyaltyTransactionType,
    OrderStatus,
    OrderType,
)
from shared.models import (
    DeliveryAssignment,
    LoyaltyAccount,
    LoyaltyTransaction,
    Order,
    ShopSettings,
)

from core_api.services.order_notifications import send_order_notification

from shared.grace.logging import get_grace_logger

_grace_log = get_grace_logger("CoreApi")


# START_CONTRACT: OrderTransitionError
#   PURPOSE: Raised on disallowed Order state transition or RBAC gate failure.
#            .reason is one of: order_not_found, forbidden_transition,
#            role_not_allowed, wrong_order_type_for_transition.
#   INPUTS:  reason: str
#   OUTPUTS: Exception with .reason
#   SIDE_EFFECTS: none
#   LINKS:   PDD §6.1, INV-010, INV-016
# END_CONTRACT: OrderTransitionError
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
    (OrderStatus.READY, OrderStatus.COMPLETED):       frozenset({"barista", "admin", "system"}),
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


def _apply_transition(
    order_id: uuid.UUID,
    new_status: OrderStatus,
    actor_role: str,
    db_session: Session,
) -> Order:
    """Ядро перехода: валидация + мутация + side-effects БЕЗ commit и notify."""
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

    # PDD §6.3: на PAID→PREPARING для DELIVERY-заказа сразу создаём
    # DeliveryAssignment в статусе AWAITING_COURIER.
    if key == (OrderStatus.PAID, OrderStatus.PREPARING) and order.type == OrderType.DELIVERY:
        db_session.add(
            DeliveryAssignment(
                order_id=order.id,
                status=DeliveryAssignmentStatus.AWAITING_COURIER,
            )
        )
        db_session.flush()

    if new_status == OrderStatus.COMPLETED:
        _accrue_loyalty(order, db_session)

    return order


# START_CONTRACT: transition_order
#   PURPOSE: Apply a single Order status transition: validates allow-list,
#            role gate, type guard; mutates row; creates DeliveryAssignment on
#            PAID→PREPARING (delivery); accrues loyalty on COMPLETED; commits;
#            dispatches notification (skipped for system actor).
#   INPUTS:  order_id: UUID
#            new_status: OrderStatus — target state
#            actor_role: str — customer/barista/courier/admin/system
#            db_session: Session
#   OUTPUTS: Order (refreshed)
#   SIDE_EFFECTS: DB UPDATE on orders.status; conditional INSERT(s) on
#                 delivery_assignments and loyalty_transactions; commit; Celery
#                 dispatch via order_notifications.send_order_notification.
#                 Source: any (validated against allow-list). Target: any in
#                 PDD §6.1 except CREATED→{PAID,CANCELLED} which payment-webhook
#                 owns. Forbidden src/target/role pairs raise OrderTransitionError.
#   LINKS:   PDD §6.1, §6.3, INV-003, INV-004, INV-010, INV-016
# END_CONTRACT: transition_order
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
    order = _apply_transition(order_id, new_status, actor_role, db_session)
    # actor_role="system" — служебный вызов (например, scheduler
    # pickup-autoclose): §6.1 row "Автозакрытие по таймеру" явно требует
    # отсутствия уведомлений для этого перехода.
    if actor_role != "system":
        send_order_notification(order, new_status, actor_role=actor_role)
    db_session.commit()
    _grace_log.belief(
        "order_lifecycle.transition_order",
        "BLOCK_STATE_TRANSITION",
        belief=str(new_status),
        actual=str(order.status),
        order_id=str(order.id),
    )
    return order


# START_CONTRACT: transition_order_bridge
#   PURPOSE: Same allow-list / validation / side effects as transition_order
#            but WITHOUT db.commit() and WITHOUT notification dispatch — used
#            from delivery_assignment so assignment + order updates land in a
#            single transaction (INV-004).
#   INPUTS:  order_id: UUID, new_status: OrderStatus, actor_role: str,
#            db_session: Session
#   OUTPUTS: Order (in-session, not yet committed)
#   SIDE_EFFECTS: DB UPDATE on orders.status; conditional inserts as above; NO
#                 commit; NO notification dispatch — caller owns both.
#   LINKS:   PDD §6.1, §6.3, INV-004, INV-016
# END_CONTRACT: transition_order_bridge
def transition_order_bridge(
    order_id: uuid.UUID,
    new_status: OrderStatus,
    actor_role: str,
    db_session: Session,
) -> Order:
    """Bridge-вариант перехода для вызова изнутри delivery_assignment (PDD §6.3).

    Тот же allow-list / validation / side-effects, что и `transition_order`,
    но БЕЗ `db.commit()` и БЕЗ `send_order_notification` — эти шаги делает
    вызывающий сервис, чтобы весь каскад (assignment + order) поместился
    в одну транзакцию (INV-004).
    """
    return _apply_transition(order_id, new_status, actor_role, db_session)
