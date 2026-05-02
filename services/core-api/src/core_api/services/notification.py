# START_MODULE_CONTRACT
#   PURPOSE: Order-status notification service — creates IN_APP Notification
#            rows for every PDD §6.1 transition and enqueues SMS jobs for the
#            subset that requires phone delivery.
#   SCOPE:   resolve_notification_text matrix; build_sms_body; resolve_display_text;
#            send_order_notification (write IN_APP + optional post-commit Celery dispatch).
#   DEPENDS: M-SHARED (Notification, Order, UserProfile, enums), M-DATABASE,
#            celery (sms-worker boundary)
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §6.1, §7.8, §8.2,
#            INV-013 (encrypted phone in Celery), INV-016
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   NotificationText               - dataclass holding RU/EN bodies + SMS flag
#   resolve_notification_text      - lookup §6.1 matrix
#   build_sms_body                 - format SMS body (≤70 chars)
#   resolve_display_text           - choose RU/EN per profile preference
#   send_order_notification        - write IN_APP + defer SMS enqueue (boundary)
#   send_order_notification_sms    - Celery stub (real impl in sms-worker)
# END_MODULE_MAP
"""Сервис уведомлений о статусах заказа (PDD §6.1 / §7.8 / §8.2).

Создаёт строки `notifications` для каждого перехода статуса заказа из §6.1,
а для SMS-обязательных статусов после commit публикует Celery-задачу
`sms_worker.send_order_notification_sms` в очередь sms-worker.

INV-013: телефон передаётся в очередь только в зашифрованном hex-виде.
INV-016: неизвестные переходы отклоняются `ValueError`.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Literal

from celery import Celery
from sqlalchemy import event
from sqlalchemy.orm import Session

from core_api.settings import settings
from shared.enums import (
    NotificationChannel,
    NotificationStatus,
    NotificationType,
    OrderStatus,
)
from shared.models.notification import Notification
from shared.models.order import Order
from shared.models.user_profile import UserProfile
from shared.notifications import (
    NotificationText,
    build_sms_body,
    resolve_notification_text,
)

__all__ = [
    "NotificationText",
    "build_sms_body",
    "resolve_display_text",
    "resolve_notification_text",
    "send_order_notification",
    "send_order_notification_sms",
]

logger = logging.getLogger(__name__)
_AFTER_COMMIT_KEY = "core_api_notification_after_commit"
_AFTER_COMMIT_REGISTERED_KEY = "core_api_notification_after_commit_registered"


# ─────────────────────────────────────────────
# Celery-клиент — локальный stub задачи sms-worker.
# Исполнение реальное живёт в sms-worker; здесь нужен только .delay().
# ─────────────────────────────────────────────

_celery_app = Celery("core_api_notifications", broker=settings.redis_url)


# START_CONTRACT: send_order_notification_sms
#   PURPOSE: Celery-task placeholder used as `.delay()` target so SMS worker
#            picks up the message; the real handler runs in sms-worker.
#   INPUTS:  notification_id: UUID | str
#            encrypted_phone_hex: str — INV-013, never plaintext
#            message: str — formatted SMS body
#   OUTPUTS: None
#   SIDE_EFFECTS: Raises NotImplementedError when called inside core-api;
#                 dispatch happens via Celery .delay().
#   LINKS:   PDD §6.4, §7.8, INV-013
# END_CONTRACT: send_order_notification_sms
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


# START_CONTRACT: resolve_display_text
#   PURPOSE: Pick message_ru/message_en off a Notification row based on the
#            user's preferred_language.
#   INPUTS:  notification: Notification, preferred_language: str
#   OUTPUTS: str — display message body.
#   SIDE_EFFECTS: none
# END_CONTRACT: resolve_display_text
def resolve_display_text(notification: Notification, preferred_language: str) -> str:
    """Выбирает message_ru/message_en по предпочтению пользователя."""
    if preferred_language == "en":
        return notification.message_en
    return notification.message_ru


def _defer_after_commit(db_session: Session, callback) -> None:
    callbacks = db_session.info.setdefault(_AFTER_COMMIT_KEY, [])
    callbacks.append(callback)
    if db_session.info.get(_AFTER_COMMIT_REGISTERED_KEY):
        return

    @event.listens_for(db_session, "after_commit")
    def _run_after_commit(session: Session) -> None:
        pending = session.info.pop(_AFTER_COMMIT_KEY, [])
        for fn in pending:
            fn()

    @event.listens_for(db_session, "after_rollback")
    def _clear_after_rollback(session: Session) -> None:
        session.info.pop(_AFTER_COMMIT_KEY, None)

    db_session.info[_AFTER_COMMIT_REGISTERED_KEY] = True


# ─────────────────────────────────────────────
# Основная функция-сервис
# ─────────────────────────────────────────────


# START_CONTRACT: send_order_notification
#   PURPOSE: Persist IN_APP Notification row and (when matrix requires) enqueue
#            SMS via Celery — phone payload always passes the boundary in
#            encrypted hex form (INV-013).
#   INPUTS:  order_id: UUID
#            user_id: UUID
#            new_status: OrderStatus — target §6.1 state
#            db_session: Session — caller owns transaction commit
#            cancelled_by: "customer" | "admin" | None — required for CANCELLED
#   OUTPUTS: None
#   SIDE_EFFECTS: DB INSERT(s) on notifications; post-commit Celery dispatch
#                 to queue 'sms' for status types in the matrix; ValueError on
#                 unknown transitions (INV-016) or missing UserProfile/Order.
#   LINKS:   PDD §6.1, §7.8, §8.2, INV-013, INV-016
# END_CONTRACT: send_order_notification
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

    sms_row_id = sms_row.id
    sms_task = send_order_notification_sms

    def _enqueue_sms() -> None:
        try:
            sms_task.delay(sms_row_id, encrypted_hex, message)
        except Exception:  # broker недоступен, но порядок заказа не должен падать.
            logger.exception(
                "Failed to enqueue SMS notification %s for order %s",
                str(sms_row_id)[:8],
                str(order_id)[:8],
            )

    _defer_after_commit(db_session, _enqueue_sms)
