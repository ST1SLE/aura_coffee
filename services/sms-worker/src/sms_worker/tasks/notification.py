"""Celery-задача отправки SMS-уведомлений о статусах заказа (PDD §7.8 / §8.2).

- Retry 3× с backoff 2s/8s/32s (§7.8).
- На успехе: Notification.status = SENT, sent_at = now(UTC).
- На окончательном провале: Notification.status = FAILED, лог об ошибке.
- INV-013: открытый телефон никогда не попадает в логи.
"""

from __future__ import annotations

import functools
import logging
import uuid
from datetime import UTC, datetime

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from shared.enums import NotificationStatus
from shared.models.notification import Notification
from sms_worker.clients.log import send_via_log
from sms_worker.clients.smsru import send_via_smsru
from sms_worker.main import celery_app
from sms_worker.settings import settings

logger = logging.getLogger(__name__)

# Модульные привязки — тесты патчат эти имена через patch.object(notif_module, ...).
_TRANSPORT = send_via_log if settings.sms_backend == "log" else send_via_smsru


def SessionLocal():  # noqa: N802 — имя сохраняет контракт теста (patch.object по имени).
    """Ленивое создание сессии: engine инициализируется при первом обращении.

    Ленивость нужна, чтобы worker не падал на импорте, если psycopg2
    отсутствует в тестовом окружении или database_url невалиден.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return factory()


def _decrypt_phone(encrypted_hex: str) -> str:
    """AES-256-GCM расшифровка phone из hex-формата (nonce[:12] + ciphertext)."""
    key = bytes.fromhex(settings.encryption_key)
    encrypted = bytes.fromhex(encrypted_hex)
    aesgcm = AESGCM(key)
    nonce = encrypted[:12]
    ciphertext = encrypted[12:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode()


def _send_order_notification_sms_impl(
    self,
    notification_id: uuid.UUID | str,
    encrypted_phone_hex: str,
    message: str,
) -> None:
    """Чистая реализация задачи (без Celery-обёртки).

    Вынесено отдельной функцией, чтобы `.run.__wrapped__` указывал на неё —
    тесты вызывают её напрямую со своим `self`-stub для проверки retry-логики.
    """
    nid_prefix = str(notification_id)[:8]

    with SessionLocal() as session:
        row = session.get(Notification, notification_id)
        if row is None:
            logger.warning("notification %s missing, skipping", nid_prefix)
            return

        phone = _decrypt_phone(encrypted_phone_hex)
        ok = _TRANSPORT(phone, message)

        if ok:
            row.status = NotificationStatus.SENT
            row.sent_at = datetime.now(UTC)
            session.commit()
            logger.info("notification %s delivered", nid_prefix)
            return

        if self.request.retries < self.max_retries:
            # Промежуточный провал — поднимаем исключение, чтобы Celery перепланировал.
            raise RuntimeError(f"sms transport returned False for {nid_prefix}")

        # Исчерпаны retries — помечаем FAILED и возвращаемся без исключения.
        row.status = NotificationStatus.FAILED
        session.commit()
        logger.error("notification %s delivery exhausted retries", nid_prefix)


@celery_app.task(
    bind=True,
    name="sms_worker.send_order_notification_sms",
    max_retries=3,
    default_retry_delay=2,
    retry_backoff=True,
    retry_backoff_max=32,
)
@functools.wraps(_send_order_notification_sms_impl)
def send_order_notification_sms(
    self,
    notification_id: uuid.UUID | str,
    encrypted_phone_hex: str,
    message: str,
) -> None:
    return _send_order_notification_sms_impl(
        self, notification_id, encrypted_phone_hex, message
    )
