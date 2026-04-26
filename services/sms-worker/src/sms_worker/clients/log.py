# START_MODULE_CONTRACT
#   PURPOSE: Dev-only SMS transport that writes the SMS body to stdout instead
#            of calling SMS.ru. Selected by SMS_BACKEND=log (default in dev/CI).
#   SCOPE:   Single function — no HTTP, no retries, no Redis. Logs the OTP
#            payload at INFO so engineers can read codes from worker logs
#            during local development.
#   DEPENDS: stdlib logging
#   LINKS:   docs/development-plan.xml M-SMS-WORKER, PDD §7.8 (SMS Delivery
#            Chain), INV-013 (PII isolation — dev-only, MUST NOT run in prod)
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   send_via_log - dev-only transport that logs the SMS body and returns True
# END_MODULE_MAP

import logging

logger = logging.getLogger(__name__)


# START_CONTRACT: send_via_log
#   PURPOSE: Pretend to send an SMS by logging it. Always succeeds. Used as
#            the `_TRANSPORT` callable in dev/CI so the OTP login flow works
#            without touching the SMS.ru network.
#   INPUTS:  phone: str — recipient phone number (cleartext)
#            message: str — SMS body
#   OUTPUTS: bool — always True (dev transport never fails)
#   SIDE_EFFECTS: Writes phone + message to stdout via stdlib logging at INFO.
#            WARNING: violates INV-013 (PII in logs) by design — never enable
#            in production. Guarded by SMS_BACKEND=log in settings.
#   LINKS:   PDD §7.8, INV-013 (dev-only exemption documented in AGENTS.md)
# END_CONTRACT: send_via_log
def send_via_log(phone: str, message: str) -> bool:
    """Dev-транспорт: выводит SMS в лог вместо реальной отправки."""
    logger.info("[SMS:log] to=%s msg=%s", phone, message)
    return True
