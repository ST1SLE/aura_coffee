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

import logging

import httpx

from sms_worker.settings import settings

logger = logging.getLogger(__name__)

SMSRU_SEND_URL = "https://sms.ru/sms/send"


# START_CONTRACT: send_via_smsru
#   PURPOSE: Send a single SMS through the SMS.ru HTTP API and return whether
#            the provider accepted it. Failures (network, non-OK response,
#            exceptions) are logged and surfaced as False — Celery task layer
#            decides whether to retry.
#   INPUTS:  phone: str — recipient phone number (cleartext, E.164-ish)
#            message: str — SMS body (≤ 70 chars per AGENTS.md)
#   OUTPUTS: bool — True if SMS.ru returned status="OK", False otherwise.
#   SIDE_EFFECTS: HTTPS POST to https://sms.ru/sms/send with api_id from
#            settings.smsru_api_key (INV-015). Logs provider error payloads
#            and exception tracebacks via stdlib logging.
#   LINKS:   PDD §7.8 (SMS Delivery Chain), PDD §8.2 (SMS.ru compliance),
#            INV-013 (caller is responsible for not logging `phone`),
#            INV-015 (api_id sourced from env via Settings)
# END_CONTRACT: send_via_smsru
def send_via_smsru(phone: str, message: str) -> bool:
    """Отправка SMS через SMS.ru API. Возвращает True при успехе."""
    try:
        response = httpx.post(
            SMSRU_SEND_URL,
            data={
                "api_id": settings.smsru_api_key,
                "to": phone,
                "msg": message,
                "json": 1,
            },
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "OK":
            return True

        logger.error("SMS.ru error: %s", data)
        return False
    except Exception:
        logger.exception("SMS.ru request failed")
        return False
