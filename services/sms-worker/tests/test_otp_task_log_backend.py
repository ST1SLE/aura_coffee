"""Интеграционные тесты send_otp_sms с log-транспортом и fakeredis."""

import json
import os
from unittest.mock import patch

import fakeredis
import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from shared.grace.testing import GraceLogCapture


def _encrypt_phone(phone: str, key: bytes) -> str:
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, phone.encode(), None)
    return (nonce + ct).hex()


@pytest.fixture()
def fake_redis():
    return fakeredis.FakeRedis()


def test_send_otp_sms_transitions_created_to_sent_via_log(fake_redis) -> None:
    from sms_worker.clients.log import send_via_log
    from sms_worker.tasks.otp import send_otp_sms

    key = os.urandom(32)
    phone_hash = "testhash_log"
    encrypted = _encrypt_phone("+79161234567", key)
    code = "123456"

    # Предзаполняем OTP в Redis со статусом CREATED
    otp_key = f"otp:{phone_hash}"
    fake_redis.set(otp_key, json.dumps({"code": code, "attempts": 0, "status": "created"}), ex=300)

    with (
        patch("sms_worker.tasks.otp._TRANSPORT", side_effect=send_via_log),
        patch("sms_worker.tasks.otp.settings") as mock_settings,
        patch("sms_worker.tasks.otp.redis") as mock_redis_mod,
    ):
        mock_settings.encryption_key = key.hex()
        mock_settings.redis_url = "redis://localhost:6379/15"
        mock_settings.sms_backend = "log"
        mock_redis_mod.Redis.from_url.return_value = fake_redis

        send_otp_sms.apply(args=[phone_hash, encrypted, code])

    raw = fake_redis.get(otp_key)
    assert raw is not None
    data = json.loads(raw)
    assert data["status"] == "sent"


# START_CONTRACT: test_send_otp_sms_emits_ldd_marker_and_redacts_logs
#   PURPOSE: Verify the OTP SMS log-backend path emits the required GRACE LDD
#            marker while keeping sensitive SMS/auth values out of logs.
#   INPUTS:  fake_redis: fakeredis.FakeRedis — isolated Redis replacement.
#   OUTPUTS: None — pytest assertions pin marker trajectory and redaction.
#   SIDE_EFFECTS: Patches SMS transport/settings/Redis for the task call.
#   LINKS:   docs/verification-plan.xml V-M-SMS-WORKER marker-1,
#            INV-013, PDD §6.4, PDD §7.8.
# END_CONTRACT: test_send_otp_sms_emits_ldd_marker_and_redacts_logs
def test_send_otp_sms_emits_ldd_marker_and_redacts_logs(fake_redis) -> None:
    from sms_worker.clients.log import send_via_log
    from sms_worker.tasks.otp import send_otp_sms

    key = os.urandom(32)
    phone = "+79161234569"
    phone_hash = "testhash_ldd"
    encrypted = _encrypt_phone(phone, key)
    code = "987654"
    sms_body = f"Код подтверждения: {code}. Aura Coffee"
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.sensitive.signature"
    api_key = "smsru_api_key_secret"

    otp_key = f"otp:{phone_hash}"
    fake_redis.set(otp_key, json.dumps({"code": code, "attempts": 0, "status": "created"}), ex=300)

    with (
        GraceLogCapture() as grace_logs,
        patch("sms_worker.tasks.otp._TRANSPORT", side_effect=send_via_log),
        patch("sms_worker.tasks.otp.settings") as mock_settings,
        patch("sms_worker.tasks.otp.redis") as mock_redis_mod,
    ):
        mock_settings.encryption_key = key.hex()
        mock_settings.redis_url = "redis://localhost:6379/15"
        mock_settings.sms_backend = "log"
        mock_settings.smsru_api_key = api_key
        mock_redis_mod.Redis.from_url.return_value = fake_redis

        send_otp_sms.apply(args=[phone_hash, encrypted, code])

    grace_logs.assert_trajectory(("send_otp", "BLOCK_SMSRU_CALL"))
    assert grace_logs.blocks(
        module="SmsWorker", fn="send_otp", blk="BLOCK_SMSRU_CALL"
    )
    assert grace_logs.beliefs(status="MISMATCH") == []

    captured = "\n".join(grace_logs.lines)
    for sensitive in (phone, code, sms_body, jwt, api_key):
        assert sensitive not in captured


def test_send_otp_sms_log_backend_does_not_retry(fake_redis) -> None:
    from sms_worker.clients.log import send_via_log
    from sms_worker.tasks.otp import send_otp_sms

    key = os.urandom(32)
    phone_hash = "testhash_log2"
    encrypted = _encrypt_phone("+79161234568", key)
    code = "654321"

    otp_key = f"otp:{phone_hash}"
    fake_redis.set(otp_key, json.dumps({"code": code, "attempts": 0, "status": "created"}), ex=300)

    call_count = 0

    def counting_transport(phone, message):
        nonlocal call_count
        call_count += 1
        return send_via_log(phone, message)

    with (
        patch("sms_worker.tasks.otp._TRANSPORT", side_effect=counting_transport),
        patch("sms_worker.tasks.otp.settings") as mock_settings,
        patch("sms_worker.tasks.otp.redis") as mock_redis_mod,
        patch("httpx.post") as mock_httpx,
    ):
        mock_settings.encryption_key = key.hex()
        mock_settings.redis_url = "redis://localhost:6379/15"
        mock_settings.sms_backend = "log"
        mock_redis_mod.Redis.from_url.return_value = fake_redis

        send_otp_sms.apply(args=[phone_hash, encrypted, code])

    assert call_count == 1, "log транспорт должен вызываться ровно один раз"
    mock_httpx.assert_not_called()
