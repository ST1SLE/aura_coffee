# START_MODULE_CONTRACT
#   PURPOSE: Atomic order cancellation chain (PDD §7.6) — restores promo quota
#            and loyalty points, restores finite inventory for pre-kitchen
#            cancellations where order_items still reference menu_item_id,
#            transitions Order to CANCELLED, cascade-cancels DeliveryAssignment,
#            fires notification, dispatches refund task.
#   SCOPE:   single entry-point cancel_order with inner private helpers.
#   DEPENDS: M-SHARED (Order, OrderItem, Payment, Promocode, PromocodeUsage,
#            LoyaltyAccount/Transaction), M-DATABASE, services.delivery_assignment,
#            services.order_notifications, celery_app
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §6.1, §6.3, §7.6,
#            INV-004, INV-005, INV-016
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   OrderCancelError - reason-tagged cancellation error
#   cancel_order     - orchestrate the §7.6 chain in a single transaction
# END_MODULE_MAP
"""Цепочка отмены заказа (PDD §7.6, INV-004, INV-005).

`cancel_order` выполняет все шаги в одной DB-транзакции. На любом исключении
сессия остаётся с нефиксированными изменениями — rollback делает вызывающий
(FastAPI-зависимость `get_session` при исключении откатит; в тестах вручную).

Порядок шагов внутри одной транзакции:
    1. Rights check (order_not_found / customer_cannot_cancel_in_this_status /
       not_cancellable_in_this_status).
    2. Возврат промокода (если был).
    3. Возврат потраченных баллов (если были).
    4. Установка status=CANCELLED, cancelled_by, cancelled_at.
    5. send_order_notification — ВАЖНО: до send_task, чтобы падение уведомления
       не оставило enqueued refund-таска (контракт теста 2.12).
    6. celery_app.send_task("payment_worker.initiate_refund", ...) — если был
       ненулевой платёж.
    7. db.commit().
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from shared.enums import LoyaltyTransactionType, OrderStatus
from shared.models import (
    LoyaltyAccount,
    LoyaltyTransaction,
    Order,
    OrderItem,
    Payment,
    Promocode,
    PromocodeUsage,
)
from shared.models.menu import MenuItem

from core_api import celery_app as _celery_mod
from core_api.services.delivery_assignment import cancel_assignment_for_order
from core_api.services.order_notifications import send_order_notification

# Модуль-уровневая ссылка — тесты патчат `sut.celery_app.send_task`.
celery_app = _celery_mod.celery_app


# START_CONTRACT: OrderCancelError
#   PURPOSE: Domain error for the cancellation chain, with a machine-readable
#            .reason: order_not_found / customer_cannot_cancel_in_this_status
#            / not_cancellable_in_this_status.
#   INPUTS:  reason: str
#   OUTPUTS: Exception with .reason
#   SIDE_EFFECTS: none
#   LINKS:   PDD §7.6, INV-005
# END_CONTRACT: OrderCancelError
class OrderCancelError(Exception):
    """Доменная ошибка цепочки отмены (PDD §7.6)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


# Статусы, при которых админ НЕ может отменить: INV-005 + §7.6.
_ADMIN_FORBIDDEN = {OrderStatus.IN_DELIVERY, OrderStatus.COMPLETED, OrderStatus.CANCELLED}
_INVENTORY_RESTORE_STATUSES = {OrderStatus.CREATED, OrderStatus.PAID}


def _return_promocode(order: Order, db: Session) -> None:
    if order.promocode_id is None:
        return
    # Атомарный conditional UPDATE c zero-floor (PDD §6.6, §7.6 шаг 2).
    # Двойная отмена (race в admin-path) не уведёт current_uses в минус —
    # второй UPDATE матчит ноль строк и становится no-op на счётчике.
    db.execute(
        update(Promocode)
        .where(
            Promocode.id == order.promocode_id,
            Promocode.current_uses > 0,
        )
        .values(current_uses=Promocode.current_uses - 1)
    )
    db.query(PromocodeUsage).filter_by(order_id=order.id).delete(
        synchronize_session=False
    )
    db.flush()


def _reverse_points(order: Order, db: Session) -> None:
    if order.points_used <= 0:
        return
    account = db.get(LoyaltyAccount, order.user_id)
    new_balance = (account.balance if account is not None else 0) + order.points_used
    if account is not None:
        account.balance = new_balance
    db.add(
        LoyaltyTransaction(
            user_id=order.user_id,
            order_id=order.id,
            type=LoyaltyTransactionType.REVERSAL,
            amount=order.points_used,
            balance_after=new_balance,
        )
    )
    db.flush()


def _restore_inventory(order: Order, db: Session) -> None:
    rows = db.execute(
        select(OrderItem.menu_item_id, func.sum(OrderItem.quantity))
        .where(
            OrderItem.order_id == order.id,
            OrderItem.menu_item_id.is_not(None),
        )
        .group_by(OrderItem.menu_item_id)
    ).all()
    quantities = {int(item_id): int(quantity or 0) for item_id, quantity in rows}
    if not quantities:
        return

    stmt = (
        select(MenuItem)
        .where(
            MenuItem.id.in_(list(quantities)),
            MenuItem.inventory_quantity.is_not(None),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    for item in db.execute(stmt).scalars().all():
        item.inventory_quantity = int(item.inventory_quantity or 0) + quantities[item.id]
    db.flush()


def _enqueue_refund(order: Order, db: Session) -> None:
    payment = db.query(Payment).filter_by(order_id=order.id).one_or_none()
    if payment is None or payment.amount <= 0:
        return
    celery_app.send_task(
        "payment_worker.tasks.initiate_refund",
        args=[str(payment.id), payment.amount],
    )


# START_CONTRACT: cancel_order
#   PURPOSE: Atomically transition an order to CANCELLED with full financial
#            unwind: restore finite inventory for CREATED/PAID orders,
#            promocode quota/loyalty points, set cancelled_by/cancelled_at,
#            cascade-cancel DeliveryAssignment, send notification, dispatch
#            refund Celery task, commit.
#   INPUTS:  order_id: UUID
#            cancelled_by: str — "customer" or "admin"
#            reason: str | None — passed through to notification
#            db_session: Session
#   OUTPUTS: Order (status=CANCELLED, refreshed)
#   SIDE_EFFECTS: DB UPDATE/INSERT/DELETE across promocodes, promocode_usages,
#                 menu_items.inventory_quantity, loyalty_accounts,
#                 loyalty_transactions, orders, delivery_assignments,
#                 notifications — all in a single txn (INV-004); commit at end;
#                 post-validation Celery dispatch of payment_worker.initiate_refund
#                 when payment exists. Source: PAID/PREPARING/READY (admin) or
#                 PAID (customer). Target: CANCELLED. Forbidden src/role pairs
#                 raise OrderCancelError (INV-005, INV-016).
#   LINKS:   PDD §6.1, §6.3, §6.6, §7.6, INV-004, INV-005, INV-011, INV-013, INV-016
# END_CONTRACT: cancel_order
def cancel_order(
    order_id: uuid.UUID,
    cancelled_by: str,
    reason: str | None,
    db_session: Session,
) -> Order:
    """Атомарная отмена заказа с возвратом всех финансовых артефактов.

    Args:
        order_id: идентификатор заказа.
        cancelled_by: роль вызывающего (`customer` / `admin`).
        reason: свободный текст причины; пробрасывается в уведомление.
        db_session: открытая сессия.

    Returns:
        Обновлённый `Order` со статусом CANCELLED.

    Raises:
        OrderCancelError: c полем `reason`:
            - `order_not_found`,
            - `customer_cannot_cancel_in_this_status` (INV-005),
            - `not_cancellable_in_this_status` (для админа на
              IN_DELIVERY / COMPLETED / CANCELLED).
    """
    order = db_session.get(Order, order_id)
    if order is None:
        raise OrderCancelError(reason="order_not_found")

    # Rights check (§7.6, INV-005)
    if cancelled_by == "customer" and order.status != OrderStatus.PAID:
        raise OrderCancelError(reason="customer_cannot_cancel_in_this_status")
    if cancelled_by == "admin" and order.status in _ADMIN_FORBIDDEN:
        raise OrderCancelError(reason="not_cancellable_in_this_status")

    # 2–3. Остатки (до кухни), промокод и баллы
    if order.status in _INVENTORY_RESTORE_STATUSES:
        _restore_inventory(order, db_session)
    _return_promocode(order, db_session)
    _reverse_points(order, db_session)

    # 4. Обновление заказа
    order.status = OrderStatus.CANCELLED
    order.cancelled_by = cancelled_by
    order.cancelled_at = datetime.now(UTC)
    db_session.flush()

    # 4a. Каскадная отмена DeliveryAssignment в той же транзакции (PDD §6.3, INV-004).
    #     No-op для PICKUP-заказов / PICKED_UP / DELIVERED.
    cancel_assignment_for_order(order.id, db_session)

    # 5. Уведомление — ДО постановки refund-таска, чтобы падение уведомления
    #    не оставило enqueued задачу (контракт теста 2.12).
    send_order_notification(order, OrderStatus.CANCELLED, reason=reason)

    # 6. Refund-таск
    _enqueue_refund(order, db_session)

    # 7. Фиксация
    db_session.commit()
    return order
