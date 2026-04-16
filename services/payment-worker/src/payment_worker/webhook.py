"""FastAPI-приложение для webhook-ов ЮKassa (PDD §4.2, §7.9).

Единственная точка — ``POST /webhooks/yukassa``. Cекьюрити:

1. IP whitelist через ``X-Forwarded-For`` против ``settings.yukassa_webhook_ips``.
2. Идемпотентность на ``X-Event-Id`` в Redis (``yukassa:event:{event_id}``).
3. Всё мутационное тело события — одна транзакция БД; Redis-ключ
   ``yukassa:event:*`` пишется ТОЛЬКО после успешного commit.
"""

from __future__ import annotations

import hashlib
import ipaddress
import logging
import socket
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from payment_worker.db import get_engine, session_scope  # noqa: F401  (patch target)
from payment_worker.redis_client import get_redis  # noqa: F401  (patch target)
from payment_worker.settings import Settings

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

app = FastAPI()

_EVENT_TTL_SECONDS = 86_400


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


def _event_key(event_id: str) -> str:
    return f"yukassa:event:{event_id}"


def is_event_processed(redis_client: Any, event_id: str) -> bool:
    return bool(redis_client.exists(_event_key(event_id)))


def mark_event_processed(redis_client: Any, event_id: str) -> None:
    redis_client.set(_event_key(event_id), b"1", ex=_EVENT_TTL_SECONDS)


# --- event handlers ---------------------------------------------------


def _handle_payment_succeeded(
    session: Session, redis_client: Any, obj: dict[str, Any]
) -> UUID | None:
    """Возвращает user_id, чтобы вызывающий мог почистить Redis-корзину вне транзакции."""
    from shared.enums import (
        LoyaltyTransactionType,
        NotificationChannel,
        NotificationType,
        OrderStatus,
        PaymentStatus,
    )
    from shared.models.loyalty_transaction import LoyaltyTransaction
    from shared.models.notification import Notification
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

    # Идемпотентность на уровне state-машины: если уже SUCCEEDED — выходим.
    if payment.status == PaymentStatus.SUCCEEDED:
        return None

    order = session.get(Order, payment.order_id)
    if order is None:
        return None

    payment.status = PaymentStatus.SUCCEEDED
    order.status = OrderStatus.PAID

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

    # Уведомления: SMS + IN_APP, RU/EN.
    body_ru = f"Заказ оплачен. Номер заказа: {order.id}"
    body_en = f"Order paid. Order ID: {order.id}"
    for channel in (NotificationChannel.SMS, NotificationChannel.IN_APP):
        session.add(
            Notification(
                user_id=order.user_id,
                order_id=order.id,
                channel=channel,
                type=NotificationType.ORDER_STATUS_CHANGE,
                message_ru=body_ru,
                message_en=body_en,
            )
        )

    return order.user_id


def _handle_payment_canceled(
    session: Session, obj: dict[str, Any]
) -> None:
    from shared.enums import (
        LoyaltyTransactionType,
        NotificationChannel,
        NotificationType,
        OrderStatus,
        PaymentStatus,
    )
    from shared.models.loyalty_transaction import LoyaltyTransaction
    from shared.models.notification import Notification
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

    payment.status = PaymentStatus.PAYMENT_FAILED
    order.status = OrderStatus.CANCELLED

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

    session.add(
        Notification(
            user_id=order.user_id,
            order_id=order.id,
            channel=NotificationChannel.IN_APP,
            type=NotificationType.ORDER_STATUS_CHANGE,
            message_ru="Платёж не прошёл. Заказ отменён.",
            message_en="Payment failed. Order canceled.",
        )
    )


def _handle_refund_succeeded(session: Session, obj: dict[str, Any]) -> None:
    from shared.enums import PaymentStatus
    from shared.models.payment import Payment

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
    payment.status = PaymentStatus.REFUNDED


def _handle_refund_canceled(session: Session, obj: dict[str, Any]) -> None:
    from shared.enums import (
        NotificationChannel,
        NotificationType,
        PaymentStatus,
    )
    from shared.models.notification import Notification
    from shared.models.order import Order
    from shared.models.payment import Payment

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
    payment.status = PaymentStatus.REFUND_FAILED

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


@app.post("/webhooks/yukassa")
async def yukassa_webhook(request: Request) -> JSONResponse:
    ip = _client_ip(request)
    # Settings читаем на каждый запрос: env может быть обновлён в тестах или
    # в рантайме (низкий QPS вебхука, накладных расходов нет).
    current_settings = Settings()  # type: ignore[call-arg]
    if not _is_whitelisted(ip, current_settings.yukassa_webhook_ips):
        logger.warning("yukassa webhook: rejected untrusted IP", extra={"ip": ip})
        return JSONResponse(status_code=403, content={"error": "forbidden"})

    body = await request.json()
    event = body.get("event", "")
    obj = body.get("object", {}) or {}

    raw_body = await request.body()
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
