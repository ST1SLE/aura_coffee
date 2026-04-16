"""Сервис уведомлений о статусах заказа (PDD §6.1 / §7.8 / §8.2).

Создаёт строки `notifications` для каждого перехода статуса заказа из §6.1,
а для SMS-обязательных статусов дополнительно публикует Celery-задачу
`sms_worker.send_order_notification_sms` в очередь sms-worker.

INV-013: телефон передаётся в очередь только в зашифрованном hex-виде.
INV-016: неизвестные переходы отклоняются `ValueError`.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from celery import Celery
from sqlalchemy.orm import Session

from core_api.settings import settings
from shared.enums import (
    NotificationChannel,
    NotificationStatus,
    NotificationType,
    OrderStatus,
    OrderType,
)
from shared.models.notification import Notification
from shared.models.order import Order
from shared.models.user_profile import UserProfile

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Celery-клиент — локальный stub задачи sms-worker.
# Исполнение реальное живёт в sms-worker; здесь нужен только .delay().
# ─────────────────────────────────────────────

_celery_app = Celery("core_api_notifications", broker=settings.redis_url)


@_celery_app.task(name="sms_worker.send_order_notification_sms", queue="sms")
def send_order_notification_sms(
    notification_id: uuid.UUID | str,
    encrypted_phone_hex: str,
    message: str,
) -> None:
    """Stub для постановки в очередь sms-worker. Реальное исполнение — в worker-процессе."""
    raise NotImplementedError(
        "send_order_notification_sms executes in sms-worker, not core-api"
    )


# ─────────────────────────────────────────────
# Матрица текстов §6.1 (IN_APP + SMS status phrase + requires_sms)
# ─────────────────────────────────────────────


@dataclass(frozen=True)
class NotificationText:
    """Результат `resolve_notification_text` — тексты + флаг SMS."""

    message_ru: str
    message_en: str
    sms_status_ru: str | None
    sms_status_en: str | None
    requires_sms: bool


# Ключ: (new_status, order_type, cancelled_by).
# Значение: (template_ru, template_en, sms_status_ru, sms_status_en, requires_sms).
# `{short_id}` — плейсхолдер, подставляется в resolve_notification_text.
_MATRIX: dict[
    tuple[OrderStatus, OrderType | None, str | None],
    tuple[str, str, str | None, str | None, bool],
] = {
    (OrderStatus.PAID, None, None): (
        "Заказ №{short_id} оплачен",
        "Order #{short_id} paid",
        "Оплачен",
        "Paid",
        True,
    ),
    (OrderStatus.PREPARING, None, None): (
        "Заказ №{short_id} готовится",
        "Order #{short_id} is being prepared",
        "Готовится",
        "Being prepared",
        True,
    ),
    (OrderStatus.READY, OrderType.PICKUP, None): (
        "Заказ №{short_id} готов, заберите",
        "Order #{short_id} is ready, please pick it up",
        "Готов, заберите",
        "Ready, pick up",
        True,
    ),
    (OrderStatus.READY, OrderType.DELIVERY, None): (
        "Заказ №{short_id} готов",
        "Order #{short_id} is ready",
        "Готов",
        "Ready",
        True,
    ),
    (OrderStatus.IN_DELIVERY, None, None): (
        "Курьер забрал заказ №{short_id}",
        "Courier picked up order #{short_id}",
        None,
        None,
        False,
    ),
    (OrderStatus.COMPLETED, OrderType.PICKUP, None): (
        "Заказ №{short_id} завершён",
        "Order #{short_id} completed",
        None,
        None,
        False,
    ),
    (OrderStatus.COMPLETED, OrderType.DELIVERY, None): (
        "Заказ №{short_id} доставлен",
        "Order #{short_id} delivered",
        "Доставлен",
        "Delivered",
        True,
    ),
    (OrderStatus.CANCELLED, None, "customer"): (
        "Заказ №{short_id} отменён, средства возвращены",
        "Order #{short_id} cancelled, funds refunded",
        "Отменён, средства возвращены",
        "Cancelled, funds refunded",
        True,
    ),
    (OrderStatus.CANCELLED, None, "admin"): (
        "Заказ №{short_id} отменён кофейней",
        "Order #{short_id} cancelled by the coffee shop",
        "Отменён кофейней",
        "Cancelled by the coffee shop",
        True,
    ),
}

# Статусы, где order_type влияет на текст.
_TYPE_DEPENDENT_STATUSES = {OrderStatus.READY, OrderStatus.COMPLETED}


def resolve_notification_text(
    new_status: OrderStatus,
    order_type: OrderType,
    cancelled_by: Literal["customer", "admin"] | None,
    short_id: str,
) -> NotificationText:
    """Ищет §6.1-кейс и возвращает тексты + флаг SMS.

    Raises:
        ValueError: если переход не описан в §6.1 (INV-016) или
            CANCELLED без cancelled_by.
    """
    if new_status == OrderStatus.CANCELLED:
        if cancelled_by not in ("customer", "admin"):
            raise ValueError(
                "CANCELLED requires cancelled_by in ('customer', 'admin')"
            )
        key = (new_status, None, cancelled_by)
    elif new_status in _TYPE_DEPENDENT_STATUSES:
        key = (new_status, order_type, None)
    else:
        key = (new_status, None, None)

    entry = _MATRIX.get(key)
    if entry is None:
        raise ValueError(
            f"No notification defined for transition: "
            f"status={new_status}, order_type={order_type}, cancelled_by={cancelled_by}"
        )

    tpl_ru, tpl_en, sms_ru, sms_en, requires_sms = entry
    return NotificationText(
        message_ru=tpl_ru.format(short_id=short_id),
        message_en=tpl_en.format(short_id=short_id),
        sms_status_ru=sms_ru,
        sms_status_en=sms_en,
        requires_sms=requires_sms,
    )


def build_sms_body(status_text: str, short_id: str) -> str:
    """PDD §8.2 — формат SMS: `{status_text}. Заказ №{short_id}. Aura Coffee`.

    Гарантирует ≤ 70 символов для всех sms_status_ru из `_MATRIX`.
    """
    return f"{status_text}. Заказ №{short_id}. Aura Coffee"


def resolve_display_text(notification: Notification, preferred_language: str) -> str:
    """Выбирает message_ru/message_en по предпочтению пользователя."""
    if preferred_language == "en":
        return notification.message_en
    return notification.message_ru


# ─────────────────────────────────────────────
# Основная функция-сервис
# ─────────────────────────────────────────────


def send_order_notification(
    order_id: uuid.UUID,
    user_id: uuid.UUID,
    new_status: OrderStatus,
    db_session: Session,
    cancelled_by: Literal["customer", "admin"] | None = None,
) -> None:
    """Создаёт IN_APP-уведомление и (если требуется §6.1) ставит SMS в очередь.

    Args:
        order_id: UUID заказа. `short_id` = первые 8 hex-символов.
        user_id: UUID пользователя (получатель уведомления).
        new_status: Целевой статус заказа из §6.1.
        db_session: Активная SQLAlchemy-сессия. Сервис делает flush(), но не commit() —
            границу транзакции владеет вызывающий код (см. проектное решение D6 GREEN).
        cancelled_by: "customer"/"admin" для CANCELLED; обязательно.

    Raises:
        ValueError: если order/profile не найдены, либо переход не описан (§6.1).
    """
    order = db_session.get(Order, order_id)
    if order is None:
        raise ValueError(f"Order {order_id} not found")

    short_id = order.id.hex[:8]

    # resolve_notification_text валидирует переход и бросит ValueError для INV-016.
    text = resolve_notification_text(
        new_status=new_status,
        order_type=order.type,
        cancelled_by=cancelled_by,
        short_id=short_id,
    )

    now = datetime.now(UTC)

    in_app = Notification(
        user_id=user_id,
        order_id=order_id,
        channel=NotificationChannel.IN_APP,
        type=NotificationType.ORDER_STATUS_CHANGE,
        status=NotificationStatus.SENT,
        message_ru=text.message_ru,
        message_en=text.message_en,
        sent_at=now,
    )
    db_session.add(in_app)
    db_session.flush()

    if not text.requires_sms:
        return

    profile = db_session.get(UserProfile, user_id)
    if profile is None:
        raise ValueError(f"UserProfile for user {user_id} not found")

    sms_row = Notification(
        user_id=user_id,
        order_id=order_id,
        channel=NotificationChannel.SMS,
        type=NotificationType.ORDER_STATUS_CHANGE,
        status=NotificationStatus.PENDING,
        message_ru=text.message_ru,
        message_en=text.message_en,
    )
    db_session.add(sms_row)
    db_session.flush()

    # INV-013: телефон пересекает Celery-границу только в hex-зашифрованном виде.
    phone_bytes = profile.phone
    encrypted_hex = (
        phone_bytes.hex() if isinstance(phone_bytes, (bytes, bytearray)) else phone_bytes
    )

    assert text.sms_status_ru is not None  # гарантировано requires_sms=True
    message = build_sms_body(text.sms_status_ru, short_id)

    try:
        send_order_notification_sms.delay(sms_row.id, encrypted_hex, message)
    except Exception:  # broker недоступен, но порядок заказа не должен падать.
        logger.exception(
            "Failed to enqueue SMS notification %s for order %s",
            str(sms_row.id)[:8],
            str(order_id)[:8],
        )
