"""Тесты send_otp_sms Celery task.

Unit-тесты с мокнутыми зависимостями.
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _encrypt_phone(phone: str, key: bytes) -> str:
    """Шифрование для тестов."""
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, phone.encode(), None)
    return (nonce + ct).hex()


class TestSendOtpSms:
    @patch("sms_worker.tasks.otp.settings")
    @patch("sms_worker.tasks.otp._TRANSPORT")
    @patch("sms_worker.tasks.otp.redis")
    def test_success(self, mock_redis_mod, mock_transport, mock_settings) -> None:
        key = os.urandom(32)
        mock_settings.encryption_key = key.hex()
        mock_settings.redis_url = "redis://localhost:6379/15"

        mock_transport.return_value = True

        mock_redis_client = MagicMock()
        mock_redis_client.get.return_value = json.dumps({
            "code": "123456", "attempts": 0, "status": "created"
        }).encode()
        mock_redis_client.ttl.return_value = 280
        mock_redis_mod.Redis.from_url.return_value = mock_redis_client

        encrypted = _encrypt_phone("+79161234567", key)

        from sms_worker.tasks.otp import send_otp_sms

        # apply() запускает задачу синхронно (eager mode)
        send_otp_sms.apply(args=["testhash", encrypted, "123456"])

        mock_transport.assert_called_once()
        call_args = mock_transport.call_args
        assert "+79161234567" in call_args[0]
        assert "123456" in call_args[0][1]

    @patch("sms_worker.tasks.otp.settings")
    @patch("sms_worker.tasks.otp._TRANSPORT")
    @patch("sms_worker.tasks.otp.redis")
    def test_failure_after_retries(
        self, mock_redis_mod, mock_transport, mock_settings
    ) -> None:
        key = os.urandom(32)
        mock_settings.encryption_key = key.hex()
        mock_settings.redis_url = "redis://localhost:6379/15"

        mock_transport.return_value = False

        mock_redis_client = MagicMock()
        mock_redis_client.get.return_value = json.dumps({
            "code": "123456", "attempts": 0, "status": "created"
        }).encode()
        mock_redis_mod.Redis.from_url.return_value = mock_redis_client

        encrypted = _encrypt_phone("+79161234567", key)

        from sms_worker.tasks.otp import send_otp_sms

        # Заставляем Celery думать, что retries исчерпаны
        send_otp_sms.max_retries = 0
        result = send_otp_sms.apply(args=["testhash", encrypted, "123456"])

        # При failure после всех retries — статус FAILED, ключ удалён
        mock_redis_client.delete.assert_called()
