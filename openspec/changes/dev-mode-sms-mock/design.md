## Affected Modules

- [sms-worker] — `services/sms-worker/src/sms_worker/clients/smsru.py`

## Design Decisions

### DD-1: Empty API key as dev-mode signal

The `send_sms()` function MUST check `settings.smsru_api_key` at the start. If the key is empty (falsy), the function MUST:
1. Log the phone number and full message text at `WARNING` level
2. Return `True` without making any HTTP request

No new env vars or flags are introduced. The existing `SMSRU_API_KEY` being empty is sufficient to signal dev mode. This follows the principle of least surprise — no key means no real SMS.

### DD-2: Log level WARNING

Dev-mode SMS logs MUST use `WARNING` level so they stand out in `docker compose logs sms-worker` output. The log line MUST include the word "DEV" for easy filtering. The OTP code itself is in the message body, making it retrievable from logs.

## Migration Strategy

No migrations. Single function change, backward compatible.
