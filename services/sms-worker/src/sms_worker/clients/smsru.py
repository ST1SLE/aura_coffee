# START_MODULE_CONTRACT
#   PURPOSE: Production SMS transport — POSTs to the SMS.ru `/sms/send`
#            endpoint using the configured api_id (INV-015). Returns boolean
#            success so callers (otp/notification tasks) can drive retry logic.
#   SCOPE:   Thin synchronous httpx wrapper. No retry policy here — Celery
#            task layer owns retries (3× exponential backoff per PDD §7.8).
#   DEPENDS: httpx, sms_worker.settings
#   LINKS:   docs/development-plan.xml M-SMS-WORKER, PDD §7.8, PDD §8.2,
#            INV-015 (secrets in env, never code)
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   SMSRU_SEND_URL - SMS.ru send endpoint URL constant
#   send_via_smsru - synchronous transport function, returns True on success
# END_MODULE_MAP

import hashlib
import logging
import re

import httpx

from sms_worker.settings import settings

logger = logging.getLogger(__name__)

SMSRU_SEND_URL = "https://sms.ru/sms/send"
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")


def _recipient_ref(phone: str) -> str:
    return hashlib.sha256(phone.encode()).hexdigest()[:12]


def _smsru_error_fields(data: object) -> tuple[object, object]:
    if not isinstance(data, dict):
        return None, None

    status = data.get("status")
    status_text = data.get("status_text")
    sms_items = data.get("sms")

    if status_text is None and isinstance(sms_items, dict):
        for sms_item in sms_items.values():
            if isinstance(sms_item, dict):
                status = sms_item.get("status", status)
                status_text = sms_item.get("status_text")
                break

    return status, status_text


def _smsru_recipient_fields(data: object) -> tuple[object, object, object, object]:
    if not isinstance(data, dict):
        return None, None, None, None

    sms_items = data.get("sms")
    if not isinstance(sms_items, dict):
        return None, None, None, None

    for sms_item in sms_items.values():
        if isinstance(sms_item, dict):
            return (
                sms_item.get("status"),
                sms_item.get("status_code"),
                sms_item.get("status_text"),
                sms_item.get("sms_id"),
            )

    return None, None, None, None


def _redact_provider_text(value: object, phone: str, message: str) -> object:
    if not isinstance(value, str):
        return value

    redacted = value
    for sensitive in (phone, message, settings.smsru_api_key):
        if sensitive:
            redacted = redacted.replace(sensitive, "[redacted]")
    for code in set(re.findall(r"\b\d{4,8}\b", message)):
        redacted = redacted.replace(code, "[redacted]")
    return _JWT_RE.sub("[redacted]", redacted)


# START_CONTRACT: send_via_smsru
#   PURPOSE: Send a single SMS through the SMS.ru HTTP API and return whether
#            the provider accepted it. Failures (network, non-OK response,
#            exceptions) are logged and surfaced as False — Celery task layer
#            decides whether to retry.
#   INPUTS:  phone: str — recipient phone number (cleartext, E.164-ish)
#            message: str — SMS body (≤ 70 chars per AGENTS.md)
#   OUTPUTS: bool — True if SMS.ru returned status="OK", False otherwise.
#   SIDE_EFFECTS: HTTPS POST to https://sms.ru/sms/send with api_id from
#            settings.smsru_api_key (INV-015). Logs only redacted provider
#            status metadata and exception tracebacks via stdlib logging.
#   LINKS:   PDD §7.8 (SMS Delivery Chain), PDD §8.2 (SMS.ru compliance),
#            INV-013 (phone/message/api_id never logged),
#            INV-015 (api_id sourced from env via Settings)
# END_CONTRACT: send_via_smsru
def send_via_smsru(phone: str, message: str) -> bool:
    """Отправка SMS через SMS.ru API. Возвращает True при успехе."""
    try:
        payload: dict[str, object] = {
            "api_id": settings.smsru_api_key,
            "to": phone,
            "msg": message,
            "json": 1,
        }
        if settings.smsru_sender_name:
            payload["from"] = settings.smsru_sender_name

        response = httpx.post(
            SMSRU_SEND_URL,
            data=payload,
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "OK":
            status, status_text = _smsru_error_fields(data)
            logger.error(
                "SMS.ru error: recipient_ref=%s status=%r status_text=%r",
                _recipient_ref(phone),
                _redact_provider_text(status, phone, message),
                _redact_provider_text(status_text, phone, message),
            )
            return False

        (
            recipient_status,
            recipient_status_code,
            recipient_status_text,
            sms_id,
        ) = _smsru_recipient_fields(data)
        if recipient_status == "OK":
            logger.info(
                "SMS.ru accepted message: recipient_ref=%s status_code=%r sms_id=%r",
                _recipient_ref(phone),
                recipient_status_code,
                sms_id,
            )
            return True

        logger.error(
            "SMS.ru recipient error: recipient_ref=%s status=%r "
            "status_code=%r status_text=%r",
            _recipient_ref(phone),
            _redact_provider_text(recipient_status, phone, message),
            recipient_status_code,
            _redact_provider_text(recipient_status_text, phone, message),
        )
        return False
    except Exception:
        logger.exception("SMS.ru request failed")
        return False
