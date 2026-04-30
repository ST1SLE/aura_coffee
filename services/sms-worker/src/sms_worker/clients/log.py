# START_MODULE_CONTRACT
#   PURPOSE: Dev/CI SMS transport that records redacted delivery metadata
#            instead of calling SMS.ru. Selected by SMS_BACKEND=log.
#   SCOPE:   Single function — no HTTP, no retries, no Redis. Logs only
#            non-secret metadata; never logs phone numbers, OTP codes, or SMS
#            bodies (INV-013).
#   DEPENDS: stdlib logging
#   LINKS:   docs/development-plan.xml M-SMS-WORKER, PDD §7.8 (SMS Delivery
#            Chain), INV-013 (PII isolation and log redaction)
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   send_via_log - dev/CI transport that logs redacted metadata and returns True
# END_MODULE_MAP

import hashlib
import logging

logger = logging.getLogger(__name__)


def _phone_ref(phone: str) -> str:
    return hashlib.sha256(phone.encode()).hexdigest()[:12]


def _message_kind(message: str) -> str:
    lowered = message.lower()
    if "код" in lowered or "code" in lowered:
        return "otp"
    return "notification"


# START_CONTRACT: send_via_log
#   PURPOSE: Pretend to send an SMS by logging redacted metadata. Always
#            succeeds. Used as the `_TRANSPORT` callable in dev/CI so flows
#            work without touching the SMS.ru network.
#   INPUTS:  phone: str — recipient phone number (cleartext)
#            message: str — SMS body
#   OUTPUTS: bool — always True (dev transport never fails)
#   SIDE_EFFECTS: Writes `[SMS:log]` metadata at INFO with a non-reversible
#            phone hash prefix, message kind, and body length; never writes
#            raw phone numbers, OTP codes, or SMS bodies.
#   LINKS:   PDD §7.8, INV-013
# END_CONTRACT: send_via_log
def send_via_log(phone: str, message: str) -> bool:
    """Dev-транспорт: логирует факт отправки без PII/секретов."""
    logger.info(
        "[SMS:log] recipient_ref=%s kind=%s message_len=%s",
        _phone_ref(phone),
        _message_kind(message),
        len(message),
    )
    return True
