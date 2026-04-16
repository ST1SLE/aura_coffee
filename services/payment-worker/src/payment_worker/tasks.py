"""Celery-таски Payment Worker: create_payment, initiate_refund + health_check.

Инварианты: INV-004 (атомарность компенсации), INV-016 (state-машина платежа
только вперёд). Имена модульных символов ``get_engine``, ``YukassaClient``,
``_decrement_promocode`` намеренно экспонируются на уровне модуля, чтобы
тесты могли патчить их через ``unittest.mock.patch``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

import httpx

from payment_worker.db import get_engine, session_scope

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
from payment_worker.main import celery_app
from payment_worker.settings import settings
from payment_worker.yukassa_client import YukassaClient

logger = logging.getLogger(__name__)


@celery_app.task
def health_check() -> str:
    return "ok"


def _latest_balance(session: Session, user_id: UUID) -> int:
    """Последний balance_after по леджеру пользователя (0 если записей нет)."""
    from shared.models.loyalty_transaction import LoyaltyTransaction

    tx = (
        session.query(LoyaltyTransaction)
        .filter(LoyaltyTransaction.user_id == user_id)
        .order_by(LoyaltyTransaction.created_at.desc())
        .first()
    )
    return tx.balance_after if tx is not None else 0


def _decrement_promocode(session: Session, promocode_id: UUID) -> None:
    """Атомарно уменьшить current_uses промокода на 1 (если > 0)."""
    from shared.models.promocode import Promocode

    promo = session.get(Promocode, promocode_id)
    if promo is not None and promo.current_uses > 0:
        promo.current_uses -= 1


def _fail_payment_and_cancel_order(order_id: str, payment_id: str) -> None:
    """Атомарная компенсация провалившегося платежа (INV-004).

    Всё в одной транзакции: Payment→PAYMENT_FAILED, Order→CANCELLED,
    REVERSAL лояльности, decrement промокода.
    """
    from shared.enums import LoyaltyTransactionType, OrderStatus, PaymentStatus
    from shared.models.loyalty_transaction import LoyaltyTransaction
    from shared.models.order import Order
    from shared.models.payment import Payment

    with session_scope(get_engine()) as session:
        order = session.get(Order, UUID(order_id))
        payment = session.get(Payment, UUID(payment_id))
        if order is None or payment is None:
            logger.warning(
                "compensation: order or payment not found",
                extra={"order_id": order_id, "payment_id": payment_id},
            )
            return

        payment.status = PaymentStatus.PAYMENT_FAILED
        order.status = OrderStatus.CANCELLED

        if order.points_used and order.points_used > 0:
            base = _latest_balance(session, order.user_id)
            reversal = LoyaltyTransaction(
                user_id=order.user_id,
                order_id=order.id,
                type=LoyaltyTransactionType.REVERSAL,
                amount=order.points_used,
                balance_after=base + order.points_used,
                description="reversed: payment failed",
            )
            session.add(reversal)
            session.flush()

        if order.promocode_id is not None:
            _decrement_promocode(session, order.promocode_id)


@celery_app.task(
    bind=True,
    name="payment_worker.tasks.create_payment",
    autoretry_for=(httpx.RequestError,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
)
def create_payment(
    self,
    order_id: str,
    amount_kopecks: int,
    idempotency_key: str,
) -> None:
    """Создаёт платёж в ЮKassa и помечает Payment как AWAITING_CONFIRMATION."""
    from shared.enums import PaymentStatus
    from shared.models.order import Order
    from shared.models.payment import Payment

    with session_scope(get_engine()) as session:
        order = session.get(Order, UUID(order_id))
        if order is None:
            logger.error("create_payment: order not found", extra={"order_id": order_id})
            return
        payment = (
            session.query(Payment).filter(Payment.order_id == order.id).first()
        )
        if payment is None:
            logger.error("create_payment: payment not found", extra={"order_id": order_id})
            return
        payment_id = str(payment.id)

    client = YukassaClient(
        shop_id=settings.yukassa_shop_id,
        secret_key=settings.yukassa_secret_key,
        base_url=settings.yukassa_base_url,
    )
    return_url = f"https://aura.coffee/orders/{order_id}"
    description = f"Order #{order_id}"

    try:
        result = client.create_payment(
            amount_kopecks=amount_kopecks,
            idempotency_key=idempotency_key,
            return_url=return_url,
            description=description,
        )
    except httpx.RequestError:
        # Последняя попытка — запускаем компенсацию и отдаём ошибку выше,
        # чтобы Celery пометил задачу FAILED.
        if self.request.retries >= self.max_retries:
            _fail_payment_and_cancel_order(order_id, payment_id)
        raise

    with session_scope(get_engine()) as session:
        payment = session.get(Payment, UUID(payment_id))
        if payment is None:
            return
        payment.yukassa_payment_id = result["payment_id"]
        payment.confirmation_url = result.get("confirmation_url")
        payment.status = PaymentStatus.AWAITING_CONFIRMATION


@celery_app.task(
    bind=True,
    name="payment_worker.tasks.initiate_refund",
    max_retries=0,
)
def initiate_refund(
    self,
    payment_id: str,
    amount_kopecks: int,
) -> None:
    """Инициирует возврат в ЮKassa. Ошибки ЮKassa глушатся (админ ручками)."""
    from shared.enums import PaymentStatus
    from shared.models.payment import Payment

    # Достаём yukassa_payment_id для вызова ЮKassa
    with session_scope(get_engine()) as session:
        payment = session.get(Payment, UUID(payment_id))
        if payment is None or not payment.yukassa_payment_id:
            logger.error(
                "initiate_refund: payment not found or no yukassa_payment_id",
                extra={"payment_id": payment_id},
            )
            return
        yukassa_id = payment.yukassa_payment_id

    client = YukassaClient(
        shop_id=settings.yukassa_shop_id,
        secret_key=settings.yukassa_secret_key,
        base_url=settings.yukassa_base_url,
    )
    try:
        client.create_refund(
            payment_id=yukassa_id,
            amount_kopecks=amount_kopecks,
            idempotency_key=f"refund-{payment_id}",
        )
    except Exception:
        logger.exception(
            "initiate_refund: refund call failed — admin follow-up required",
            extra={"payment_id": payment_id},
        )
        return

    with session_scope(get_engine()) as session:
        payment = session.get(Payment, UUID(payment_id))
        if payment is None:
            return
        payment.status = PaymentStatus.REFUND_PENDING
