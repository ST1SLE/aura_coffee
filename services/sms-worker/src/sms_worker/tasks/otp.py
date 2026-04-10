import json
import logging

import redis

from sms_worker.clients.log import send_via_log
from sms_worker.clients.smsru import send_via_smsru
from sms_worker.main import celery_app
from sms_worker.settings import settings

_TRANSPORT = send_via_log if settings.sms_backend == "log" else send_via_smsru

logger = logging.getLogger(__name__)


def _decrypt_phone(encrypted_hex: str) -> str:
    """Дешифрование phone из hex (AES-256-GCM: nonce + ciphertext)."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = bytes.fromhex(settings.encryption_key)
    encrypted = bytes.fromhex(encrypted_hex)
    aesgcm = AESGCM(key)
    nonce = encrypted[:12]
    ciphertext = encrypted[12:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode()


def _update_otp_status(r: redis.Redis, phone_hash: str, status: str) -> None:
    """Обновление статуса OTP в Redis."""
    key = f"otp:{phone_hash}"
    raw = r.get(key)
    if raw is None:
        return

    otp_data = json.loads(raw)
    otp_data["status"] = status
    ttl = r.ttl(key)

    if status == "failed":
        r.delete(key)
    elif ttl > 0:
        r.set(key, json.dumps(otp_data), ex=ttl)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=2,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=32,
)
def send_otp_sms(
    self, phone_hash: str, encrypted_phone_hex: str, code: str
) -> None:
    """Отправка OTP SMS. Retry 3x с backoff 2s/8s/32s."""
    phone = _decrypt_phone(encrypted_phone_hex)
    message = f"Код подтверждения: {code}. Aura Coffee"

    success = _TRANSPORT(phone, message)

    r = redis.Redis.from_url(settings.redis_url)
    try:
        if success:
            _update_otp_status(r, phone_hash, "sent")
            logger.info("OTP SMS sent for %s", phone_hash[:8])
        else:
            if self.request.retries >= self.max_retries:
                _update_otp_status(r, phone_hash, "failed")
                logger.error("OTP SMS failed after retries for %s", phone_hash[:8])
            else:
                raise Exception("SMS delivery failed, retrying")
    finally:
        r.close()
