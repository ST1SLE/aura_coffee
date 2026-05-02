"""Celery-таски Payment Worker: create_payment, initiate_refund + health_check.

Инварианты: INV-004 (атомарность компенсации), INV-016 (state-машина платежа
только вперёд). Имена модульных символов ``get_engine``, ``YukassaClient``,
``_decrement_promocode`` намеренно экспонируются на уровне модуля, чтобы
тесты могли патчить их через ``unittest.mock.patch``.
"""

# START_MODULE_CONTRACT
#   PURPOSE: Celery tasks driving the Payment lifecycle (PDD §6.2):
#            create_payment performs PENDING -> AWAITING_CONFIRMATION via
#            YuKassa; initiate_refund performs SUCCEEDED/REFUND_FAILED ->
#            REFUND_PENDING.
#            On terminal create-payment failure the private compensation
#            helper executes Payment -> PAYMENT_FAILED + Order -> CANCELLED
#            + finite inventory restore + loyalty REVERSAL + promocode
#            decrement in a single transaction (INV-004).
#   SCOPE:   Celery task definitions + a YuKassa client factory. Webhook-side
#            transitions (SUCCEEDED, REFUNDED, REFUND_FAILED) live in
#            webhook.py.
#   DEPENDS: M-SHARED (shared.enums, shared.models.{order,payment,
#            loyalty_transaction,promocode}), M-DATABASE (Postgres via
#            payment_worker.db), payment_worker.main, payment_worker.yukassa_client,
#            httpx, Celery
#   LINKS:   docs/development-plan.xml M-PAYMENT-WORKER, PDD §6.2, INV-004
#            (atomic), INV-016 (explicit transitions)
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   get_yukassa_client - factory selecting live YukassaClient vs FakeYukassaClient
#                        from YUKASSA_BACKEND env
#   health_check       - Celery task returning "ok" (liveness probe)
#   create_payment     - Celery task: PENDING -> AWAITING_CONFIRMATION; on
#                        terminal failure compensates to PAYMENT_FAILED + order
#                        CANCELLED (INV-004)
#   initiate_refund    - Celery task: SUCCEEDED/REFUND_FAILED -> REFUND_PENDING
#                        (full refund only, per INV-005)
#   logger             - module logger
# END_MODULE_MAP

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

import httpx

from payment_worker.db import get_engine, session_scope

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
from payment_worker.main import celery_app
from payment_worker.yukassa_client import YukassaClient
from shared.grace.logging import get_grace_logger

_grace_log = get_grace_logger("PaymentWorker")

logger = logging.getLogger(__name__)


# START_CONTRACT: get_yukassa_client
#   PURPOSE: Per-task factory choosing the live YukassaClient or the
#            FakeYukassaClient based on YUKASSA_BACKEND. Reads env directly
#            instead of going through Settings() so the live-mode safety-rail
#            doesn't fire inside every task (it fires once at worker boot).
#   INPUTS:  none — reads YUKASSA_BACKEND, YUKASSA_SHOP_ID, YUKASSA_SECRET_KEY,
#            YUKASSA_BASE_URL from os.environ.
#   OUTPUTS: YukassaClient | FakeYukassaClient
#   SIDE_EFFECTS: none (no I/O); the returned client opens HTTP connections lazily.
#   LINKS:   PDD §8.1, INV-015 (live mode requires real creds — enforced upstream)
# END_CONTRACT: get_yukassa_client
def get_yukassa_client():
    """Фабрика клиента ЮKassa — вызывается каждой таской отдельно.

    Читаем env напрямую (а не через Settings()), чтобы не запускать safety-rail
    валидацию внутри каждого вызова таски: валидация запускается один раз при
    старте воркера (импорт Settings в main.py). Заодно фабрика не ломает тесты,
    которые патчат `YukassaClient` и не передают валидные creds в env.
    """
    import os

    backend = os.getenv("YUKASSA_BACKEND", "live")
    if backend == "fake":
        from payment_worker.yukassa_fake import FakeYukassaClient

        return FakeYukassaClient()
    return YukassaClient(
        shop_id=os.getenv("YUKASSA_SHOP_ID", ""),
        secret_key=os.getenv("YUKASSA_SECRET_KEY", ""),
        base_url=os.getenv("YUKASSA_BASE_URL", "https://api.yookassa.ru/v3"),
    )


# START_CONTRACT: health_check
#   PURPOSE: Celery task returning a constant "ok" string — liveness probe
#            consumed by orchestration / smoke tests.
#   INPUTS:  none
#   OUTPUTS: str — literal "ok"
#   SIDE_EFFECTS: none
#   LINKS:   docs/verification-plan.xml V-M-PAYMENT-WORKER (probe surface)
# END_CONTRACT: health_check
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


def _restore_inventory(session: Session, order) -> None:
    """Restore finite menu inventory from immutable order item snapshots."""
    from sqlalchemy import func, select

    from shared.models.menu import MenuItem
    from shared.models.order_item import OrderItem

    rows = session.execute(
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
    for item in session.execute(stmt).scalars().all():
        item.inventory_quantity = int(item.inventory_quantity or 0) + quantities[item.id]
    session.flush()


def _fail_payment_and_cancel_order(order_id: str, payment_id: str) -> None:
    """Атомарная компенсация провалившегося платежа (INV-004).

    Всё в одной транзакции: Payment→PAYMENT_FAILED, Order→CANCELLED,
    restore finite inventory, REVERSAL лояльности, decrement промокода.
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
        if payment.status == PaymentStatus.PAYMENT_FAILED:
            return

        payment.status = PaymentStatus.PAYMENT_FAILED
        _grace_log.block(
            "create_intent", "BLOCK_TX_PAYMENT", payment_id=str(payment.id)
        )
        if order.status == OrderStatus.CANCELLED:
            return

        order.status = OrderStatus.CANCELLED
        _restore_inventory(session, order)
        _grace_log.belief(
            "create_intent",
            "BLOCK_STATE_TRANSITION",
            belief="CANCELLED",
            actual=order.status.name,
        )

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


# START_CONTRACT: create_payment
#   PURPOSE: Drive the PDD §6.2 transition Payment.PENDING ->
#            AWAITING_CONFIRMATION by calling YuKassa POST /v3/payments with
#            an idempotency key, then persisting `yukassa_payment_id` and
#            `confirmation_url` on the Payment row. On terminal RequestError
#            (after 3 retries) runs the atomic compensation
#            (Payment -> PAYMENT_FAILED, Order -> CANCELLED, finite inventory
#            restore, loyalty REVERSAL, promocode decrement) in a single DB
#            transaction.
#   INPUTS:  self: Celery task binding (bind=True)
#            order_id: str — UUID string of the Order
#            amount_kopecks: int — gross amount in kopecks
#            idempotency_key: str — caller-supplied idempotency key for YuKassa
#   OUTPUTS: None
#   SIDE_EFFECTS: DB write to `payments` (status, yukassa_payment_id,
#                 confirmation_url); on terminal failure also writes
#                 `payments`, `orders`, `menu_items`, `loyalty_transactions`,
#                 `promocodes` atomically. External HTTP POST to YuKassa /v3/payments.
#                 Triggers Payment lifecycle transition PENDING ->
#                 AWAITING_CONFIRMATION (or PENDING -> PAYMENT_FAILED on
#                 terminal failure).
#   LINKS:   PDD §6.2, INV-004 (atomic compensation), INV-016 (explicit
#            transitions), INV-015 (idempotency-key required on create)
# END_CONTRACT: create_payment
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

    client = get_yukassa_client()
    return_url = f"https://aura.coffee/orders/{order_id}"
    description = f"Order #{order_id}"

    _grace_log.block("create_intent", "BLOCK_YUKASSA_CALL", order_id=str(order_id))
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


# START_CONTRACT: initiate_refund
#   PURPOSE: Drive the PDD §6.2 transitions Payment.SUCCEEDED ->
#            REFUND_PENDING and Payment.REFUND_FAILED -> REFUND_PENDING by
#            creating a new refunds row and calling YuKassa POST /v3/refunds.
#            Full refund only (per INV-005). Refund finalization (REFUNDED /
#            REFUND_FAILED) lands later via webhook.
#   INPUTS:  self: Celery task binding (bind=True)
#            payment_id: str — UUID string of the local Payment row
#            amount_kopecks: int — refund amount in kopecks (must equal the
#                                  original gross amount, INV-005)
#            idempotency_key: str | None — optional caller-provided key; admin
#                                  retries pass a fresh key, cancellation uses
#                                  the deterministic payment-level key
#   OUTPUTS: None
#   SIDE_EFFECTS: DB INSERT to `refunds`; DB write to `payments`
#                 (status -> REFUND_PENDING after YuKassa accepts). External
#                 HTTP POST to YuKassa /v3/refunds. YuKassa errors are
#                 swallowed (admin follow-up) — Payment status stays at the
#                 source state in that case so the state machine never silently
#                 regresses (INV-016), and the refund attempt is marked failed.
#   LINKS:   PDD §6.2, INV-004 (atomic), INV-005 (full refund only),
#            INV-016 (explicit transitions)
# END_CONTRACT: initiate_refund
@celery_app.task(
    bind=True,
    name="payment_worker.tasks.initiate_refund",
    max_retries=0,
)
def initiate_refund(
    self,
    payment_id: str,
    amount_kopecks: int,
    idempotency_key: str | None = None,
) -> None:
    """Инициирует возврат в ЮKassa. Ошибки ЮKassa глушатся (админ ручками)."""
    from shared.enums import PaymentStatus, RefundStatus
    from shared.models.payment import Payment
    from shared.models.refund import Refund

    refund_id: UUID | None = None
    key = idempotency_key or f"refund-{payment_id}"
    allowed_sources = {PaymentStatus.SUCCEEDED, PaymentStatus.REFUND_FAILED}

    # Достаём yukassa_payment_id и создаём новую попытку возврата.
    with session_scope(get_engine()) as session:
        payment = session.get(Payment, UUID(payment_id))
        if payment is None or not payment.yukassa_payment_id:
            logger.error(
                "initiate_refund: payment not found or no yukassa_payment_id",
                extra={"payment_id": payment_id},
            )
            return
        if payment.status not in allowed_sources:
            logger.warning(
                "initiate_refund: payment status is not retryable",
                extra={"payment_id": payment_id, "status": payment.status.value},
            )
            return
        if amount_kopecks <= 0 or amount_kopecks != payment.amount:
            logger.error(
                "initiate_refund: invalid refund amount",
                extra={"payment_id": payment_id, "amount_kopecks": amount_kopecks},
            )
            return
        pending_refund = (
            session.query(Refund)
            .filter(
                Refund.payment_id == payment.id,
                Refund.status == RefundStatus.PENDING,
            )
            .first()
        )
        if pending_refund is not None:
            logger.info(
                "initiate_refund: pending refund already exists",
                extra={
                    "payment_id": payment_id,
                    "refund_id": str(pending_refund.id),
                },
            )
            return
        refund = Refund(
            payment_id=payment.id,
            amount=amount_kopecks,
            status=RefundStatus.PENDING,
            reason=(
                "admin_retry"
                if payment.status == PaymentStatus.REFUND_FAILED
                else "order_cancel"
            ),
        )
        session.add(refund)
        session.flush()
        refund_id = refund.id
        yukassa_id = payment.yukassa_payment_id

    client = get_yukassa_client()
    try:
        result = client.create_refund(
            payment_id=yukassa_id,
            amount_kopecks=amount_kopecks,
            idempotency_key=key,
        )
    except Exception:
        if refund_id is not None:
            with session_scope(get_engine()) as session:
                refund = session.get(Refund, refund_id)
                if refund is not None:
                    refund.status = RefundStatus.FAILED
        logger.exception(
            "initiate_refund: refund call failed — admin follow-up required",
            extra={"payment_id": payment_id},
        )
        return

    with session_scope(get_engine()) as session:
        payment = session.get(Payment, UUID(payment_id))
        if payment is None:
            return
        refund = session.get(Refund, refund_id) if refund_id is not None else None
        if refund is not None:
            refund.yukassa_refund_id = (
                result.get("id") or result.get("refund_id") or refund.yukassa_refund_id
            )
        if payment.status not in allowed_sources | {PaymentStatus.REFUND_PENDING}:
            logger.warning(
                "initiate_refund: payment status changed before refund persist",
                extra={"payment_id": payment_id, "status": payment.status.value},
            )
            return
        payment.status = PaymentStatus.REFUND_PENDING
        _grace_log.block(
            "initiate_refund", "BLOCK_TX_PAYMENT", payment_id=str(payment.id)
        )
        _grace_log.belief(
            "initiate_refund",
            "BLOCK_STATE_TRANSITION",
            belief="REFUND_PENDING",
            actual=payment.status.name,
        )
