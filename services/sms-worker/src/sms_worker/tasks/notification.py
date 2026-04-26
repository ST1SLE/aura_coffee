"""Celery-задача отправки SMS-уведомлений о статусах заказа (PDD §7.8 / §8.2).

- Retry 3× с backoff 2s/8s/32s (§7.8).
- На успехе: Notification.status = SENT, sent_at = now(UTC).
- На окончательном провале: Notification.status = FAILED, лог об ошибке.
- INV-013: открытый телефон никогда не попадает в логи.
"""

# START_MODULE_CONTRACT
#   PURPOSE: Celery task that delivers order-status SMS notifications. Drives
#            the Notification row through PENDING → SENT/FAILED with retry
#            policy 3× exponential backoff (2s/8s/32s).
#   SCOPE:   Owns the `send_order_notification_sms` task and its DB session
#            factory. Decrypts phone numbers in-memory only — never logs
#            cleartext PII (INV-013). Uses `_TRANSPORT` selected at import
#            time from settings.sms_backend (log vs smsru).
#   DEPENDS: M-SHARED (enums, models.Notification), SQLAlchemy, cryptography,
#            sms_worker.clients.{log,smsru}, sms_worker.main (celery_app),
#            sms_worker.settings
#   LINKS:   docs/development-plan.xml M-SMS-WORKER, PDD §7.8, PDD §8.2,
#            INV-013 (PII redaction), INV-016 (state-machine boundaries)
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   SessionLocal                    - lazy SQLAlchemy session factory
#   send_order_notification_sms     - Celery task: deliver notification SMS
# END_MODULE_MAP

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


# START_CONTRACT: SessionLocal
#   PURPOSE: Lazily build a SQLAlchemy Session bound to settings.database_url.
#            Lazy import keeps the worker startable in environments where
#            psycopg2 or the database URL are not configured (tests).
#   INPUTS:  (none)
#   OUTPUTS: sqlalchemy.orm.Session — fresh session, expire_on_commit=False
#   SIDE_EFFECTS: Creates a SQLAlchemy engine and sessionmaker on each call;
#            opens a DB connection on first use (pool_pre_ping=True).
#   LINKS:   docs/development-plan.xml M-SMS-WORKER (DB write side of §7.8)
# END_CONTRACT: SessionLocal
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


# START_CONTRACT: send_order_notification_sms
#   PURPOSE: Deliver an order-status SMS for a Notification row, advancing it
#            through SENT (success) or FAILED (retries exhausted). Implements
#            the §7.8 retry policy via Celery (3× exponential backoff capped
#            at 32s).
#   INPUTS:  self — Celery task binding (provides .request.retries, .max_retries)
#            notification_id: uuid.UUID | str — primary key of Notification row
#            encrypted_phone_hex: str — AES-256-GCM hex blob (nonce[:12] + ct)
#            message: str — pre-rendered SMS body (≤ 70 chars)
#   OUTPUTS: None
#   SIDE_EFFECTS: Decrypts phone in-memory, calls SMS transport (log/smsru),
#            updates Notification.status + sent_at, may raise to trigger
#            Celery retry. INV-013: cleartext phone never logged — only the
#            first 8 chars of notification_id appear in log lines.
#   LINKS:   PDD §7.8 (SMS Delivery Chain), PDD §8.2, INV-013, INV-016
# END_CONTRACT: send_order_notification_sms
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
