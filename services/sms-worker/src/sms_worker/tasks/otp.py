# START_MODULE_CONTRACT
#   PURPOSE: Celery task that delivers OTP authentication codes via SMS and
#            advances the OTP lifecycle in Redis through CREATED → SENT or
#            CREATED → FAILED (PDD §6.4). Worker MUST NOT generate or store
#            the code itself — core-api owns Redis OTP state.
#   SCOPE:   Owns `send_otp_sms` task. Selects transport at import time from
#            settings.sms_backend (log/smsru). Retry policy: 3× exponential
#            backoff (2s/8s/32s) per AGENTS.md and §7.8.
#   DEPENDS: redis-py, cryptography, sms_worker.clients.{log,smsru},
#            sms_worker.main (celery_app), sms_worker.settings
#   LINKS:   docs/development-plan.xml M-SMS-WORKER, PDD §6.4 (OTP Lifecycle),
#            PDD §7.8, INV-013 (PII isolation), INV-015 (secret handling)
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   send_otp_sms - Celery task: deliver OTP SMS and update Redis status
# END_MODULE_MAP

import json
import logging

import redis

from shared.grace.logging import get_grace_logger
from sms_worker.clients.log import send_via_log
from sms_worker.clients.smsru import send_via_smsru
from sms_worker.main import celery_app
from sms_worker.settings import settings

_grace_log = get_grace_logger("SmsWorker")

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


# START_CONTRACT: send_otp_sms
#   PURPOSE: Deliver a 6-digit OTP code via SMS and drive the Redis OTP
#            record from CREATED → SENT (success) or CREATED → FAILED
#            (retries exhausted). Implements PDD §6.4 OTP Lifecycle from the
#            worker side; core-api owns CREATED/VERIFIED/EXPIRED transitions.
#   INPUTS:  self — Celery task binding (provides .request.retries, .max_retries)
#            phone_hash: str — SHA-256 hex digest used as Redis key suffix
#            encrypted_phone_hex: str — AES-256-GCM hex blob (nonce[:12] + ct)
#            code: str — 6-digit OTP code (cleartext, NEVER log it)
#   OUTPUTS: None
#   SIDE_EFFECTS: Decrypts phone in-memory, calls SMS transport (log/smsru),
#            opens a Redis connection to update otp:{phone_hash} status;
#            may raise to trigger Celery retry. INV-013: only the first 8
#            chars of phone_hash appear in logs — never phone or code.
#   LINKS:   PDD §6.4 (OTP Lifecycle: CREATED → SENT/FAILED/EXPIRED/VERIFIED),
#            PDD §7.8 (retry policy), INV-013, INV-015, INV-016
# END_CONTRACT: send_otp_sms
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
    message = f"Ваш код: {code}"

    _grace_log.block("send_otp", "BLOCK_SMSRU_CALL")
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
