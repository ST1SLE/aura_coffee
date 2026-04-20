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

from sqlalchemy.orm import Session

from shared.enums import LoyaltyTransactionType, OrderStatus
from shared.models import (
    LoyaltyAccount,
    LoyaltyTransaction,
    Order,
    Payment,
    Promocode,
    PromocodeUsage,
)

from core_api import celery_app as _celery_mod
from core_api.services.delivery_assignment import cancel_assignment_for_order
from core_api.services.order_notifications import send_order_notification

# Модуль-уровневая ссылка — тесты патчат `sut.celery_app.send_task`.
celery_app = _celery_mod.celery_app


class OrderCancelError(Exception):
    """Доменная ошибка цепочки отмены (PDD §7.6)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


# Статусы, при которых админ НЕ может отменить: INV-005 + §7.6.
_ADMIN_FORBIDDEN = {OrderStatus.IN_DELIVERY, OrderStatus.COMPLETED, OrderStatus.CANCELLED}


def _return_promocode(order: Order, db: Session) -> None:
    if order.promocode_id is None:
        return
    promo = db.get(Promocode, order.promocode_id)
    if promo is not None and promo.current_uses > 0:
        promo.current_uses -= 1
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


def _enqueue_refund(order: Order, db: Session) -> None:
    payment = db.query(Payment).filter_by(order_id=order.id).one_or_none()
    if payment is None or payment.amount <= 0:
        return
    celery_app.send_task(
        "payment_worker.initiate_refund",
        args=[str(payment.id), payment.amount],
    )


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

    # 2–3. Промокод и баллы
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
