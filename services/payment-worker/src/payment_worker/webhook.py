"""FastAPI-приложение для webhook-ов ЮKassa (PDD §4.2, §7.9).

Единственная точка — ``POST /webhooks/yukassa``. Cекьюрити:

1. IP whitelist через ``X-Forwarded-For`` против ``settings.yukassa_webhook_ips``.
2. Если настроен ``YUKASSA_WEBHOOK_SIGNATURE_SECRET`` — HMAC-SHA256 подпись
   сырого тела запроса до JSON-parsing и DB writes.
3. Идемпотентность на ``X-Event-Id`` в Redis (``yukassa:event:{event_id}``).
4. Всё мутационное тело события — одна транзакция БД; Redis-ключ
   ``yukassa:event:*`` пишется ТОЛЬКО после успешного commit.
"""

# START_MODULE_CONTRACT
#   PURPOSE: FastAPI webhook surface for YuKassa events. Security-relevant:
#            verifies caller authenticity by IP whitelist (literal IPs, CIDRs,
#            or DNS-resolved hostnames from settings.yukassa_webhook_ips),
#            optionally verifies an HMAC-SHA256 signature over the raw request
#            body when settings.yukassa_webhook_signature_secret is configured,
#            enforces event-id idempotency via Redis, and runs every state
#            transition inside one DB transaction so the Redis "processed"
#            marker is only written after a successful commit (PDD §7.9).
#            Drives PDD §6.2 transitions: payment.succeeded ->
#            Payment.SUCCEEDED + Order.PAID, payment.canceled ->
#            Payment.PAYMENT_FAILED + Order.CANCELLED + finite inventory
#            restore, refund.succeeded -> Payment.REFUNDED, refund.canceled ->
#            Payment.REFUND_FAILED.
#   SCOPE:   FastAPI app + dispatcher + Redis idempotency helpers. Per-event
#            handlers are private and live in this file.
#   DEPENDS: M-SHARED (shared.enums, shared.models.{menu,order,order_item,
#            payment,loyalty_transaction,notification,promocode}), M-DATABASE,
#            payment_worker.db, payment_worker.redis_client,
#            payment_worker.settings, FastAPI
#   LINKS:   docs/development-plan.xml M-PAYMENT-WORKER, PDD §4.2, §7.9,
#            §6.2, INV-004 (atomic), INV-016 (explicit transitions),
#            INV-013 (no PII in logs)
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   app                  - FastAPI application
#   health               - GET /health route — liveness + active YuKassa backend
#   is_event_processed   - returns True if the YuKassa event_id is already in Redis
#   mark_event_processed - records the YuKassa event_id in Redis with TTL
#   dispatch_event       - routes a parsed YuKassa event to its private handler
#   yukassa_webhook      - POST /webhooks/yukassa route — IP-gated entry point
#   logger               - module logger
# END_MODULE_MAP

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import logging
import socket
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import event
from sqlalchemy.orm import Session

from payment_worker.db import get_engine, session_scope  # noqa: F401  (patch target)
from payment_worker.main import celery_app
from payment_worker.redis_client import get_redis  # noqa: F401  (patch target)
from payment_worker.settings import Settings
from shared.enums import NotificationChannel, NotificationStatus, NotificationType
from shared.grace.logging import get_grace_logger
from shared.notifications import build_sms_body, resolve_notification_text

_grace_log = get_grace_logger("PaymentWorker")

if TYPE_CHECKING:
    from uuid import UUID

logger = logging.getLogger(__name__)

app = FastAPI()

_EVENT_TTL_SECONDS = 86_400
_ORDER_SMS_TASK = "sms_worker.send_order_notification_sms"
_AFTER_COMMIT_KEY = "payment_worker_notification_after_commit"
_AFTER_COMMIT_REGISTERED_KEY = "payment_worker_notification_after_commit_registered"


# START_CONTRACT: health
#   PURPOSE: Liveness probe + reports the active YuKassa backend (live | fake)
#            so smoke tests can assert the deploy mode.
#   INPUTS:  none
#   OUTPUTS: dict[str, str] — {"status": "ok", "yukassa_backend": <mode>}
#   SIDE_EFFECTS: instantiates Settings() each call (cheap, low QPS).
#   LINKS:   docs/verification-plan.xml V-M-PAYMENT-WORKER (probe surface)
# END_CONTRACT: health
@app.get("/health")
async def health() -> dict[str, str]:
    # Читаем Settings каждый раз — env может меняться между тестами/релоадами.
    return {
        "status": "ok",
        "yukassa_backend": Settings().yukassa_backend,  # type: ignore[call-arg]
    }


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Первый хоп из X-Forwarded-For
        return forwarded.split(",")[0].strip()
    if request.client is not None:
        return request.client.host
    return ""


_HOSTNAME_CACHE: dict[str, str | None] = {}


def _resolve_hostname(entry: str) -> str | None:
    if entry in _HOSTNAME_CACHE:
        return _HOSTNAME_CACHE[entry]
    try:
        resolved = socket.gethostbyname(entry)
    except OSError:
        resolved = None
    _HOSTNAME_CACHE[entry] = resolved
    return resolved


def _is_whitelisted(ip: str, whitelist: list[str]) -> bool:
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for entry in whitelist:
        entry = entry.strip()
        if not entry or entry == "*":
            # Wildcard намеренно не поддерживается: explicit > permissive.
            continue
        if "/" in entry:
            try:
                if addr in ipaddress.ip_network(entry, strict=False):
                    return True
            except ValueError:
                continue
            continue
        # Literal IP match
        if entry == ip:
            return True
        # Hostname — резолвим (с кэшем) и сравниваем.
        try:
            ipaddress.ip_address(entry)
            # Это был IP, но не совпавший — дальше.
            continue
        except ValueError:
            pass
        resolved = _resolve_hostname(entry)
        if resolved is not None and resolved == ip:
            return True
    return False


def _signature_values(header_value: str) -> list[str]:
    values: list[str] = []
    for part in header_value.split(","):
        candidate = part.strip()
        if not candidate:
            continue
        if "=" in candidate:
            scheme, value = candidate.split("=", 1)
            if scheme.strip().lower() in {"sha256", "v1"} and value.strip():
                values.append(value.strip())
            continue
        values.append(candidate)
    return values


def _is_valid_signature(
    *,
    raw_body: bytes,
    provided_signature: str | None,
    signature_secret: str,
) -> bool:
    if not signature_secret:
        return True
    if not provided_signature:
        return False
    expected = hmac.new(
        signature_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    for candidate in _signature_values(provided_signature):
        candidate = candidate.lower()
        if hmac.compare_digest(candidate, expected):
            return True
        if hmac.compare_digest(candidate, f"sha256={expected}"):
            return True
    return False


def _event_key(event_id: str) -> str:
    return f"yukassa:event:{event_id}"


# START_CONTRACT: is_event_processed
#   PURPOSE: Idempotency guard — has this YuKassa event_id already been
#            processed (Redis key present)?
#   INPUTS:  redis_client: Any — redis-py-compatible client
#            event_id: str — YuKassa X-Event-Id (or sha256(body) fallback)
#   OUTPUTS: bool — True if the event has been recorded already
#   SIDE_EFFECTS: one Redis EXISTS read against `yukassa:event:{event_id}`.
#   LINKS:   PDD §7.9 (webhook idempotency)
# END_CONTRACT: is_event_processed
def is_event_processed(redis_client: Any, event_id: str) -> bool:
    return bool(redis_client.exists(_event_key(event_id)))


# START_CONTRACT: mark_event_processed
#   PURPOSE: Persist the YuKassa event_id with a 24h TTL so retries from
#            YuKassa (up to 10 in 24h) are deduplicated.
#   INPUTS:  redis_client: Any — redis-py-compatible client
#            event_id: str
#   OUTPUTS: None
#   SIDE_EFFECTS: Redis SET with EX=86400 on `yukassa:event:{event_id}`.
#   LINKS:   PDD §7.9 (webhook idempotency)
# END_CONTRACT: mark_event_processed
def mark_event_processed(redis_client: Any, event_id: str) -> None:
    redis_client.set(_event_key(event_id), b"1", ex=_EVENT_TTL_SECONDS)


# --- event handlers ---------------------------------------------------


def _encrypted_phone_hex(profile_phone: bytes | bytearray | str) -> str:
    if isinstance(profile_phone, (bytes, bytearray)):
        return profile_phone.hex()
    return profile_phone


def _defer_after_commit(session: Session, callback) -> None:
    callbacks = session.info.setdefault(_AFTER_COMMIT_KEY, [])
    callbacks.append(callback)
    if session.info.get(_AFTER_COMMIT_REGISTERED_KEY):
        return

    @event.listens_for(session, "after_commit")
    def _run_after_commit(committed_session: Session) -> None:
        pending = committed_session.info.pop(_AFTER_COMMIT_KEY, [])
        for fn in pending:
            fn()

    @event.listens_for(session, "after_rollback")
    def _clear_after_rollback(rolled_back_session: Session) -> None:
        rolled_back_session.info.pop(_AFTER_COMMIT_KEY, None)

    session.info[_AFTER_COMMIT_REGISTERED_KEY] = True


def _send_order_notification(
    session: Session,
    order: Any,
    new_status: Any,
    *,
    cancelled_by: str | None = None,
) -> None:
    """Write canonical order notification rows and enqueue SMS after commit."""
    from shared.models.notification import Notification
    from shared.models.user_profile import UserProfile

    short_id = order.id.hex[:8]
    text = resolve_notification_text(
        new_status=new_status,
        order_type=order.type,
        cancelled_by=cancelled_by,
        short_id=short_id,
    )

    session.add(
        Notification(
            user_id=order.user_id,
            order_id=order.id,
            channel=NotificationChannel.IN_APP,
            type=NotificationType.ORDER_STATUS_CHANGE,
            status=NotificationStatus.SENT,
            message_ru=text.message_ru,
            message_en=text.message_en,
        )
    )
    session.flush()

    if not text.requires_sms:
        return

    profile = session.get(UserProfile, order.user_id)
    if profile is None:
        raise ValueError(f"UserProfile for user {order.user_id} not found")

    sms_row = Notification(
        user_id=order.user_id,
        order_id=order.id,
        channel=NotificationChannel.SMS,
        type=NotificationType.ORDER_STATUS_CHANGE,
        status=NotificationStatus.PENDING,
        message_ru=text.message_ru,
        message_en=text.message_en,
    )
    session.add(sms_row)
    session.flush()

    assert text.sms_status_ru is not None
    sms_row_id = str(sms_row.id)
    encrypted_phone = _encrypted_phone_hex(profile.phone)
    message = build_sms_body(text.sms_status_ru, short_id)
    send_task = celery_app.send_task

    def _enqueue_sms() -> None:
        try:
            send_task(
                _ORDER_SMS_TASK,
                args=[sms_row_id, encrypted_phone, message],
                queue="sms",
            )
        except Exception:
            logger.exception(
                "failed to enqueue order SMS notification",
                extra={"notification_id": sms_row_id[:8], "order_id": short_id},
            )

    _defer_after_commit(session, _enqueue_sms)


def _restore_inventory(session: Session, order: Any) -> None:
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


def _status_value(status: Any) -> str:
    return getattr(status, "value", str(status))


def _log_guarded_payment_transition(
    event_type: str,
    payment: Any,
    *,
    outcome: str,
    order: Any | None = None,
    refund: Any | None = None,
) -> None:
    fields: dict[str, str] = {
        "payment_id": str(payment.id),
        "event_type": event_type,
        "outcome": outcome,
        "payment_status": _status_value(payment.status),
    }
    if order is not None:
        fields["order_id"] = str(order.id)
        fields["order_status"] = _status_value(order.status)
    if refund is not None:
        fields["refund_id"] = str(refund.id)
        fields["refund_status"] = _status_value(refund.status)

    _grace_log.block("process_webhook", "BLOCK_TX_PAYMENT", **fields)
    logger.warning("yukassa webhook: ignored guarded transition", extra=fields)


def _handle_payment_succeeded(
    session: Session, redis_client: Any, obj: dict[str, Any]
) -> UUID | None:
    """Возвращает user_id, чтобы вызывающий мог почистить Redis-корзину вне транзакции."""
    from shared.enums import (
        LoyaltyTransactionType,
        OrderStatus,
        PaymentStatus,
    )
    from shared.models.loyalty_transaction import LoyaltyTransaction
    from shared.models.order import Order
    from shared.models.payment import Payment

    yukassa_id = obj.get("id")
    if not yukassa_id:
        return None

    payment = (
        session.query(Payment)
        .filter(Payment.yukassa_payment_id == yukassa_id)
        .first()
    )
    if payment is None:
        logger.warning(
            "payment.succeeded: unknown yukassa_payment_id",
            extra={"yukassa_payment_id": yukassa_id},
        )
        return None

    order = session.get(Order, payment.order_id)
    if order is None:
        return None

    if payment.status == PaymentStatus.SUCCEEDED and order.status == OrderStatus.PAID:
        _log_guarded_payment_transition(
            "payment.succeeded",
            payment,
            outcome="idempotent_terminal",
            order=order,
        )
        return None
    if (
        payment.status != PaymentStatus.AWAITING_CONFIRMATION
        or order.status != OrderStatus.CREATED
    ):
        _log_guarded_payment_transition(
            "payment.succeeded",
            payment,
            outcome="forbidden_source_state",
            order=order,
        )
        return None

    payment.status = PaymentStatus.SUCCEEDED
    order.status = OrderStatus.PAID
    _grace_log.block(
        "process_webhook", "BLOCK_TX_PAYMENT", payment_id=str(payment.id)
    )
    _grace_log.belief(
        "process_webhook",
        "BLOCK_STATE_TRANSITION",
        belief="PAID",
        actual=order.status.name,
    )

    # RESERVATION -> REDEMPTION: конвертируем тип существующей записи.
    reservation = (
        session.query(LoyaltyTransaction)
        .filter(
            LoyaltyTransaction.order_id == order.id,
            LoyaltyTransaction.type == LoyaltyTransactionType.RESERVATION,
        )
        .first()
    )
    if reservation is not None:
        reservation.type = LoyaltyTransactionType.REDEMPTION

    _send_order_notification(session, order, OrderStatus.PAID)

    return order.user_id


def _handle_payment_canceled(
    session: Session, obj: dict[str, Any]
) -> None:
    from shared.enums import (
        LoyaltyTransactionType,
        OrderStatus,
        PaymentStatus,
    )
    from shared.models.loyalty_transaction import LoyaltyTransaction
    from shared.models.order import Order
    from shared.models.payment import Payment

    yukassa_id = obj.get("id")
    if not yukassa_id:
        return

    payment = (
        session.query(Payment)
        .filter(Payment.yukassa_payment_id == yukassa_id)
        .first()
    )
    if payment is None:
        return
    order = session.get(Order, payment.order_id)
    if order is None:
        return
    if (
        payment.status == PaymentStatus.PAYMENT_FAILED
        and order.status == OrderStatus.CANCELLED
    ):
        _log_guarded_payment_transition(
            "payment.canceled",
            payment,
            outcome="idempotent_terminal",
            order=order,
        )
        return
    if payment.status != PaymentStatus.AWAITING_CONFIRMATION:
        _log_guarded_payment_transition(
            "payment.canceled",
            payment,
            outcome="forbidden_source_state",
            order=order,
        )
        return
    if order.status == OrderStatus.CANCELLED:
        payment.status = PaymentStatus.PAYMENT_FAILED
        _grace_log.block(
            "process_webhook",
            "BLOCK_TX_PAYMENT",
            payment_id=str(payment.id),
            outcome="payment_failed_order_already_cancelled",
        )
        return
    if order.status != OrderStatus.CREATED:
        _log_guarded_payment_transition(
            "payment.canceled",
            payment,
            outcome="forbidden_source_state",
            order=order,
        )
        return

    payment.status = PaymentStatus.PAYMENT_FAILED
    order.status = OrderStatus.CANCELLED
    _restore_inventory(session, order)
    _grace_log.block(
        "process_webhook", "BLOCK_TX_PAYMENT", payment_id=str(payment.id)
    )
    _grace_log.belief(
        "process_webhook",
        "BLOCK_STATE_TRANSITION",
        belief="CANCELLED",
        actual=order.status.name,
    )

    if order.points_used and order.points_used > 0:
        last_tx = (
            session.query(LoyaltyTransaction)
            .filter(LoyaltyTransaction.user_id == order.user_id)
            .order_by(LoyaltyTransaction.created_at.desc())
            .first()
        )
        base = last_tx.balance_after if last_tx is not None else 0
        session.add(
            LoyaltyTransaction(
                user_id=order.user_id,
                order_id=order.id,
                type=LoyaltyTransactionType.REVERSAL,
                amount=order.points_used,
                balance_after=base + order.points_used,
                description="reversed: payment canceled",
            )
        )
        session.flush()

    if order.promocode_id is not None:
        from shared.models.promocode import Promocode

        promo = session.get(Promocode, order.promocode_id)
        if promo is not None and promo.current_uses > 0:
            promo.current_uses -= 1

    _send_order_notification(
        session,
        order,
        OrderStatus.CANCELLED,
        cancelled_by="payment",
    )


def _handle_refund_succeeded(session: Session, obj: dict[str, Any]) -> None:
    from shared.enums import PaymentStatus, RefundStatus
    from shared.models.payment import Payment
    from shared.models.refund import Refund

    yukassa_id = obj.get("payment_id") or obj.get("id")
    if not yukassa_id:
        return
    payment = (
        session.query(Payment)
        .filter(Payment.yukassa_payment_id == yukassa_id)
        .first()
    )
    if payment is None:
        return
    refund_id = obj.get("id")
    refund = None
    if refund_id:
        refund = (
            session.query(Refund)
            .filter(Refund.yukassa_refund_id == refund_id)
            .first()
        )
    if refund is None:
        refund = (
            session.query(Refund)
            .filter(Refund.payment_id == payment.id)
            .order_by(Refund.created_at.desc())
            .first()
        )
    if (
        payment.status == PaymentStatus.REFUNDED
        and refund is not None
        and refund.status == RefundStatus.SUCCEEDED
    ):
        _log_guarded_payment_transition(
            "refund.succeeded",
            payment,
            outcome="idempotent_terminal",
            refund=refund,
        )
        return
    if (
        payment.status != PaymentStatus.REFUND_PENDING
        or refund is None
        or refund.status != RefundStatus.PENDING
    ):
        _log_guarded_payment_transition(
            "refund.succeeded",
            payment,
            outcome="forbidden_source_state",
            refund=refund,
        )
        return
    if refund is not None:
        if refund_id:
            refund.yukassa_refund_id = refund_id
        refund.status = RefundStatus.SUCCEEDED
    payment.status = PaymentStatus.REFUNDED
    _grace_log.block(
        "process_webhook", "BLOCK_TX_PAYMENT", payment_id=str(payment.id)
    )
    _grace_log.belief(
        "process_webhook",
        "BLOCK_STATE_TRANSITION",
        belief="REFUNDED",
        actual=payment.status.name,
    )


def _handle_refund_canceled(session: Session, obj: dict[str, Any]) -> None:
    from shared.enums import (
        NotificationChannel,
        NotificationType,
        PaymentStatus,
        RefundStatus,
    )
    from shared.models.notification import Notification
    from shared.models.order import Order
    from shared.models.payment import Payment
    from shared.models.refund import Refund

    yukassa_id = obj.get("payment_id") or obj.get("id")
    if not yukassa_id:
        return
    payment = (
        session.query(Payment)
        .filter(Payment.yukassa_payment_id == yukassa_id)
        .first()
    )
    if payment is None:
        return
    refund_id = obj.get("id")
    refund = None
    if refund_id:
        refund = (
            session.query(Refund)
            .filter(Refund.yukassa_refund_id == refund_id)
            .first()
        )
    if refund is None:
        refund = (
            session.query(Refund)
            .filter(Refund.payment_id == payment.id)
            .order_by(Refund.created_at.desc())
            .first()
        )
    if (
        payment.status == PaymentStatus.REFUND_FAILED
        and refund is not None
        and refund.status == RefundStatus.FAILED
    ):
        _log_guarded_payment_transition(
            "refund.canceled",
            payment,
            outcome="idempotent_terminal",
            refund=refund,
        )
        return
    if (
        payment.status != PaymentStatus.REFUND_PENDING
        or refund is None
        or refund.status != RefundStatus.PENDING
    ):
        _log_guarded_payment_transition(
            "refund.canceled",
            payment,
            outcome="forbidden_source_state",
            refund=refund,
        )
        return
    if refund is not None:
        if refund_id:
            refund.yukassa_refund_id = refund_id
        refund.status = RefundStatus.FAILED
    payment.status = PaymentStatus.REFUND_FAILED
    _grace_log.block(
        "process_webhook", "BLOCK_TX_PAYMENT", payment_id=str(payment.id)
    )
    _grace_log.belief(
        "process_webhook",
        "BLOCK_STATE_TRANSITION",
        belief="REFUND_FAILED",
        actual=payment.status.name,
    )

    # Админское уведомление: user_id обязан быть not-null, берём владельца заказа.
    order = session.get(Order, payment.order_id)
    if order is not None:
        session.add(
            Notification(
                user_id=order.user_id,
                order_id=order.id,
                channel=NotificationChannel.IN_APP,
                type=NotificationType.ORDER_STATUS_CHANGE,
                message_ru="Возврат не прошёл — требуется ручное вмешательство администратора.",
                message_en="Refund failed — manual admin intervention required.",
            )
        )


# START_CONTRACT: dispatch_event
#   PURPOSE: Route a parsed YuKassa event to the right private handler. All
#            mutating handlers run inside the caller's DB transaction so a
#            handler failure rolls back the entire event (prerequisite for
#            INV-004 atomicity + INV-016 explicit-transition guarantee).
#   INPUTS:  session: Session — open SQLAlchemy session (caller-provided)
#            redis_client: Any — redis client for ancillary writes
#            event: str — YuKassa event name (payment.succeeded |
#                         payment.canceled | refund.succeeded | refund.canceled)
#            obj: dict[str, Any] — event payload object
#   OUTPUTS: UUID | None — user_id whose Redis cart should be cleared
#                          (only for payment.succeeded), else None
#   SIDE_EFFECTS: DB writes via the called handler — `payments` (status),
#                 `orders` (status), `menu_items` (finite inventory restore),
#                 `loyalty_transactions`, `promocodes`, `notifications`.
#                 Drives PDD §6.2 transitions:
#                 payment.succeeded -> Payment.SUCCEEDED + Order.PAID;
#                 payment.canceled -> Payment.PAYMENT_FAILED +
#                 Order.CANCELLED + finite inventory restore + loyalty
#                 REVERSAL + promocode decrement; refund.succeeded ->
#                 Payment.REFUNDED;
#                 refund.canceled -> Payment.REFUND_FAILED. Exceptions
#                 propagate so the webhook returns 500 and YuKassa retries.
#   LINKS:   PDD §6.2, §7.9, INV-004 (atomic), INV-016 (explicit transitions)
# END_CONTRACT: dispatch_event
def dispatch_event(
    session: Session,
    redis_client: Any,
    event: str,
    obj: dict[str, Any],
) -> UUID | None:
    """Единая точка обработки событий. Возвращает user_id, если корзину нужно
    почистить (только для payment.succeeded). Исключения пробрасываются наверх —
    webhook-ручка отдаст 500 и НЕ пометит event_id как обработанный."""
    if event == "payment.succeeded":
        return _handle_payment_succeeded(session, redis_client, obj)
    if event == "payment.canceled":
        _handle_payment_canceled(session, obj)
        return None
    if event == "refund.succeeded":
        _handle_refund_succeeded(session, obj)
        return None
    if event == "refund.canceled":
        _handle_refund_canceled(session, obj)
        return None
    logger.info("yukassa webhook: unknown event type", extra={"event": event})
    return None


# --- HTTP endpoint ----------------------------------------------------


# START_CONTRACT: yukassa_webhook
#   PURPOSE: HTTP entry point for YuKassa callbacks. Security-relevant:
#            first-hop X-Forwarded-For IP is checked against the configured
#            whitelist (literal IPs / CIDRs / DNS-resolved hostnames); on
#            miss returns 403. If YUKASSA_WEBHOOK_SIGNATURE_SECRET is set,
#            the configured signature header must match HMAC-SHA256 over the
#            raw request body before JSON parsing or DB writes. Idempotent:
#            dedupes by X-Event-Id (falling back to sha256(body)) via Redis.
#            Mutating work runs inside one DB transaction; the Redis
#            "processed" marker is written ONLY after the transaction commits
#            — exceptions return 500 and YuKassa retries.
#   INPUTS:  request: fastapi.Request — incoming POST with JSON body and
#                                       optional X-Event-Id header
#   OUTPUTS: JSONResponse — 200 {"ok": True} on success or dedup,
#                           403 on untrusted IP
#   SIDE_EFFECTS: DB writes (orders, payments, loyalty_transactions,
#                 menu_items, promocodes, notifications) via dispatch_event; Redis
#                 SET on `yukassa:event:*`; Redis DELETE on `cart:{user_id}`
#                 for payment.succeeded; post-commit dispatch of downstream
#                 notifications consumed by sms-worker. Drives the PDD §6.2
#                 Payment lifecycle transitions handled by dispatch_event.
#   LINKS:   PDD §4.2, §7.9, §6.2, INV-004 (atomic), INV-016 (explicit
#            transitions), INV-013 (no PII in logs)
# END_CONTRACT: yukassa_webhook
@app.post("/webhooks/yukassa")
async def yukassa_webhook(request: Request) -> JSONResponse:
    ip = _client_ip(request)
    # Settings читаем на каждый запрос: env может быть обновлён в тестах или
    # в рантайме (низкий QPS вебхука, накладных расходов нет).
    current_settings = Settings()  # type: ignore[call-arg]
    if not _is_whitelisted(ip, current_settings.yukassa_webhook_ips):
        logger.warning("yukassa webhook: rejected untrusted IP", extra={"ip": ip})
        return JSONResponse(status_code=403, content={"error": "forbidden"})

    raw_body = await request.body()
    signature_secret = current_settings.yukassa_webhook_signature_secret.strip()
    signature_header = (
        current_settings.yukassa_webhook_signature_header.strip()
        or "X-YooKassa-Signature"
    )
    provided_signature = request.headers.get(signature_header)
    if not _is_valid_signature(
        raw_body=raw_body,
        provided_signature=provided_signature,
        signature_secret=signature_secret,
    ):
        _grace_log.block(
            "process_webhook", "BLOCK_WEBHOOK_VERIFY", outcome="signature_rejected"
        )
        logger.warning("yukassa webhook: rejected invalid signature")
        return JSONResponse(status_code=403, content={"error": "forbidden"})

    try:
        body = json.loads(raw_body or b"{}")
    except json.JSONDecodeError:
        logger.warning("yukassa webhook: malformed JSON body")
        return JSONResponse(status_code=400, content={"error": "bad_request"})

    event = body.get("event", "")
    obj = body.get("object", {}) or {}
    _grace_log.block(
        "process_webhook",
        "BLOCK_WEBHOOK_VERIFY",
        event_type=str(event),
        outcome="verified",
    )

    event_id = request.headers.get("X-Event-Id") or hashlib.sha256(
        raw_body
    ).hexdigest()

    redis_client = get_redis()
    if is_event_processed(redis_client, event_id):
        return JSONResponse(status_code=200, content={"ok": True, "dedup": True})

    user_to_clear: UUID | None = None
    with session_scope(get_engine()) as session:
        user_to_clear = dispatch_event(session, redis_client, event, obj)

    # После коммита: чистим корзину и помечаем событие обработанным.
    if user_to_clear is not None:
        try:
            redis_client.delete(f"cart:{user_to_clear}")
        except Exception:
            logger.exception("yukassa webhook: failed to clear cart")

    mark_event_processed(redis_client, event_id)
    return JSONResponse(status_code=200, content={"ok": True})
