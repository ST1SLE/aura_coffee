"""RED-фаза: контракт Celery-задачи `sms_worker.tasks.notification.send_order_notification_sms`.

Pins PDD §7.8 (retry 3× с backoff 2s/8s/32s), §8.2 (SMS формат), INV-013 (no plaintext phone in logs).

Все тесты ДОЛЖНЫ падать в RED: целевой модуль отсутствует, импорты внутри тел тестов.
"""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ─────────────────────────────────────────────
# Helpers (общие для нескольких тестов)
# ─────────────────────────────────────────────


def _encrypt_phone_hex(phone: str, key: bytes) -> str:
    """Возвращает nonce+ciphertext в hex-формате."""
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, phone.encode(), None)
    return (nonce + ct).hex()


@dataclass
class _FakeRequest:
    retries: int = 0
    id: str = "fake-task-id"


@dataclass
class _FakeSelf:
    """Стаб Celery `self`-объекта для прямого вызова .run()."""

    request: _FakeRequest = field(default_factory=_FakeRequest)
    max_retries: int = 3


def _make_self(retries: int = 0, max_retries: int = 3) -> _FakeSelf:
    return _FakeSelf(request=_FakeRequest(retries=retries), max_retries=max_retries)


# ─────────────────────────────────────────────
# 9.x Structural tests
# ─────────────────────────────────────────────


def test_production_worker_import_registers_notification_task() -> None:
    """9.0 — production Celery app startup registers the task core-api enqueues."""
    from sms_worker.main import celery_app

    celery_app.loader.import_default_modules()

    assert "sms_worker.send_order_notification_sms" in celery_app.tasks


def test_task_is_registered_under_expected_name() -> None:
    """9.1 — Celery-задача зарегистрирована как 'sms_worker.send_order_notification_sms'."""
    from sms_worker.tasks.notification import send_order_notification_sms

    assert send_order_notification_sms.name == "sms_worker.send_order_notification_sms"


def test_task_retry_configuration_matches_pdd_7_8() -> None:
    """9.2 — retry=3, delay=2, backoff=True, backoff_max=32 (§7.8)."""
    from sms_worker.tasks.notification import send_order_notification_sms

    assert send_order_notification_sms.max_retries == 3
    # Универсальная проверка: читаем атрибуты напрямую
    assert send_order_notification_sms.default_retry_delay == 2
    assert getattr(send_order_notification_sms, "retry_backoff", None) is True
    assert getattr(send_order_notification_sms, "retry_backoff_max", None) == 32


# ─────────────────────────────────────────────
# 10.x Behavior tests
# ─────────────────────────────────────────────


def test_success_updates_notification_to_sent() -> None:
    """10.1 — успешная отправка: status=SENT, sent_at≈utc_now."""
    from sms_worker.tasks import notification as notif_module
    from sms_worker.tasks.notification import send_order_notification_sms

    key = os.urandom(32)
    encrypted_hex = _encrypt_phone_hex("+79991234567", key)
    notification_id = uuid.uuid4()

    # Поддельная строка Notification в БД (мокируем SessionLocal)
    fake_row = MagicMock()
    fake_row.id = notification_id
    fake_row.status = "pending"
    fake_row.sent_at = None

    fake_session = MagicMock()
    fake_session.get.return_value = fake_row
    fake_session.__enter__.return_value = fake_session
    fake_session.__exit__.return_value = False

    with (
        patch.object(notif_module, "_TRANSPORT", return_value=True),
        patch.object(notif_module, "settings") as mock_settings,
        patch.object(notif_module, "SessionLocal", return_value=fake_session),
    ):
        mock_settings.encryption_key = key.hex()
        send_order_notification_sms.run(
            notification_id=notification_id,
            encrypted_phone_hex=encrypted_hex,
            message="Оплачен. Заказ №abcdef01. Aura Coffee",
        )

    # Проверяем, что статус переведён в SENT и sent_at в UTC
    assert str(fake_row.status).lower().endswith("sent")
    assert isinstance(fake_row.sent_at, datetime)
    delta = datetime.now(UTC) - fake_row.sent_at
    assert 0 <= delta.total_seconds() < 5
    fake_session.commit.assert_called()


def test_decrypted_phone_is_passed_to_transport() -> None:
    """10.2 — транспорт получает расшифрованный телефон."""
    from sms_worker.tasks import notification as notif_module
    from sms_worker.tasks.notification import send_order_notification_sms

    key = os.urandom(32)
    phone = "+79991234567"
    encrypted_hex = _encrypt_phone_hex(phone, key)
    notification_id = uuid.uuid4()

    fake_row = MagicMock()
    fake_row.id = notification_id
    fake_row.status = "pending"
    fake_row.sent_at = None

    fake_session = MagicMock()
    fake_session.get.return_value = fake_row
    fake_session.__enter__.return_value = fake_session
    fake_session.__exit__.return_value = False

    mock_transport = MagicMock(return_value=True)

    with (
        patch.object(notif_module, "_TRANSPORT", mock_transport),
        patch.object(notif_module, "settings") as mock_settings,
        patch.object(notif_module, "SessionLocal", return_value=fake_session),
    ):
        mock_settings.encryption_key = key.hex()
        send_order_notification_sms.run(
            notification_id=notification_id,
            encrypted_phone_hex=encrypted_hex,
            message="Оплачен. Заказ №abcdef01. Aura Coffee",
        )

    mock_transport.assert_called_once()
    args = mock_transport.call_args.args
    assert phone in args
    assert any("Aura Coffee" in a for a in args if isinstance(a, str))


def test_intermediate_failure_raises_for_retry() -> None:
    """10.3 — промежуточный провал: задача поднимает исключение, status остаётся PENDING."""
    from sms_worker.tasks import notification as notif_module
    from sms_worker.tasks.notification import send_order_notification_sms

    key = os.urandom(32)
    encrypted_hex = _encrypt_phone_hex("+79991234567", key)
    notification_id = uuid.uuid4()

    fake_row = MagicMock()
    fake_row.id = notification_id
    fake_row.status = "pending"
    fake_row.sent_at = None

    fake_session = MagicMock()
    fake_session.get.return_value = fake_row
    fake_session.__enter__.return_value = fake_session
    fake_session.__exit__.return_value = False

    self_stub = _make_self(retries=1, max_retries=3)

    with (
        patch.object(notif_module, "_TRANSPORT", return_value=False),
        patch.object(notif_module, "settings") as mock_settings,
        patch.object(notif_module, "SessionLocal", return_value=fake_session),
    ):
        mock_settings.encryption_key = key.hex()
        with pytest.raises(RuntimeError):
            send_order_notification_sms.run.__wrapped__(
                self_stub,
                notification_id=notification_id,
                encrypted_phone_hex=encrypted_hex,
                message="Оплачен. Заказ №abcdef01. Aura Coffee",
            )

    assert str(fake_row.status).lower().endswith("pending")


def test_exhausted_retries_marks_failed_and_does_not_raise() -> None:
    """10.4 — после исчерпания retries: status=FAILED, без исключения наружу."""
    from sms_worker.tasks import notification as notif_module
    from sms_worker.tasks.notification import send_order_notification_sms

    key = os.urandom(32)
    encrypted_hex = _encrypt_phone_hex("+79991234567", key)
    notification_id = uuid.uuid4()

    fake_row = MagicMock()
    fake_row.id = notification_id
    fake_row.status = "pending"
    fake_row.sent_at = None

    fake_session = MagicMock()
    fake_session.get.return_value = fake_row
    fake_session.__enter__.return_value = fake_session
    fake_session.__exit__.return_value = False

    self_stub = _make_self(retries=3, max_retries=3)

    with (
        patch.object(notif_module, "_TRANSPORT", return_value=False),
        patch.object(notif_module, "settings") as mock_settings,
        patch.object(notif_module, "SessionLocal", return_value=fake_session),
    ):
        mock_settings.encryption_key = key.hex()
        # Не должно пробрасывать исключение наверх
        send_order_notification_sms.run.__wrapped__(
            self_stub,
            notification_id=notification_id,
            encrypted_phone_hex=encrypted_hex,
            message="Оплачен. Заказ №abcdef01. Aura Coffee",
        )

    assert str(fake_row.status).lower().endswith("failed")


def test_exhausted_retries_logs_error_with_notification_id(caplog) -> None:
    """10.5 — при окончательном провале в логах присутствует id уведомления (префикс)."""
    from sms_worker.tasks import notification as notif_module
    from sms_worker.tasks.notification import send_order_notification_sms

    key = os.urandom(32)
    encrypted_hex = _encrypt_phone_hex("+79991234567", key)
    notification_id = uuid.UUID("c0ffee11-1234-4567-89ab-cdefdeadbeef")

    fake_row = MagicMock()
    fake_row.id = notification_id
    fake_row.status = "pending"
    fake_row.sent_at = None

    fake_session = MagicMock()
    fake_session.get.return_value = fake_row
    fake_session.__enter__.return_value = fake_session
    fake_session.__exit__.return_value = False

    self_stub = _make_self(retries=3, max_retries=3)

    with (
        caplog.at_level(logging.ERROR),
        patch.object(notif_module, "_TRANSPORT", return_value=False),
        patch.object(notif_module, "settings") as mock_settings,
        patch.object(notif_module, "SessionLocal", return_value=fake_session),
    ):
        mock_settings.encryption_key = key.hex()
        send_order_notification_sms.run.__wrapped__(
            self_stub,
            notification_id=notification_id,
            encrypted_phone_hex=encrypted_hex,
            message="Оплачен. Заказ №c0ffee11. Aura Coffee",
        )

    # В логах ожидаем хотя бы префикс id (8 первых hex-символов)
    assert any("c0ffee11" in rec.getMessage() for rec in caplog.records)


def test_plaintext_phone_not_in_logs(caplog) -> None:
    """10.6 (INV-013) — sensitive SMS data never appears in task logs."""
    from sms_worker.tasks import notification as notif_module
    from sms_worker.tasks.notification import send_order_notification_sms

    key = os.urandom(32)
    phone = "+79991234567"
    message = "Оплачен. Заказ №abcdef01. Aura Coffee"
    jwt = "eyJhbGciOiJIUzI1NiJ9.secret.payload"
    api_key = "smsru_live_api_key_secret"
    encrypted_hex = _encrypt_phone_hex(phone, key)
    notification_id = uuid.uuid4()

    # --- success path
    fake_row = MagicMock()
    fake_row.id = notification_id
    fake_row.status = "pending"
    fake_row.sent_at = None

    fake_session = MagicMock()
    fake_session.get.return_value = fake_row
    fake_session.__enter__.return_value = fake_session
    fake_session.__exit__.return_value = False

    with (
        caplog.at_level(logging.DEBUG),
        patch.object(notif_module, "_TRANSPORT", return_value=True),
        patch.object(notif_module, "settings") as mock_settings,
        patch.object(notif_module, "SessionLocal", return_value=fake_session),
    ):
        mock_settings.encryption_key = key.hex()
        mock_settings.smsru_api_key = api_key
        send_order_notification_sms.run(
            notification_id=notification_id,
            encrypted_phone_hex=encrypted_hex,
            message=message,
        )

    # --- failure path
    self_stub = _make_self(retries=3, max_retries=3)
    fake_row2 = MagicMock()
    fake_row2.id = notification_id
    fake_row2.status = "pending"
    fake_session2 = MagicMock()
    fake_session2.get.return_value = fake_row2
    fake_session2.__enter__.return_value = fake_session2
    fake_session2.__exit__.return_value = False

    with (
        caplog.at_level(logging.DEBUG),
        patch.object(notif_module, "_TRANSPORT", return_value=False),
        patch.object(notif_module, "settings") as mock_settings,
        patch.object(notif_module, "SessionLocal", return_value=fake_session2),
    ):
        mock_settings.encryption_key = key.hex()
        mock_settings.smsru_api_key = api_key
        send_order_notification_sms.run.__wrapped__(
            self_stub,
            notification_id=notification_id,
            encrypted_phone_hex=encrypted_hex,
            message=message,
        )

    forbidden = (phone, message, jwt, api_key)
    for rec in caplog.records:
        line = rec.getMessage()
        for sensitive in forbidden:
            assert sensitive not in line


def test_missing_notification_row_logs_and_returns(caplog) -> None:
    """10.7 — если Notification по id не найден, задача логирует warning и возвращается."""
    from sms_worker.tasks import notification as notif_module
    from sms_worker.tasks.notification import send_order_notification_sms

    key = os.urandom(32)
    encrypted_hex = _encrypt_phone_hex("+79991234567", key)

    fake_session = MagicMock()
    fake_session.get.return_value = None  # строка не найдена
    fake_session.__enter__.return_value = fake_session
    fake_session.__exit__.return_value = False

    with (
        caplog.at_level(logging.WARNING),
        patch.object(notif_module, "settings") as mock_settings,
        patch.object(notif_module, "SessionLocal", return_value=fake_session),
    ):
        mock_settings.encryption_key = key.hex()
        # Не должно raise
        send_order_notification_sms.run(
            notification_id=uuid.uuid4(),
            encrypted_phone_hex=encrypted_hex,
            message="Оплачен. Заказ №abcdef01. Aura Coffee",
        )

    assert any(rec.levelno == logging.WARNING for rec in caplog.records)
