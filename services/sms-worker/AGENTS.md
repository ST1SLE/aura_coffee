# SMS Worker

Celery worker for SMS delivery via SMS.ru/SMSC — OTP codes for authentication and order status notifications.

**PDD sections:** §4.3 (boundaries), §6.4 (OTP Lifecycle), §7.8 (SMS Delivery Chain), §8.2 (SMS.ru compliance)

## Tech Stack

- Python 3.12+, Celery
- `requests` or `httpx` for SMS.ru API calls
- pytest for testing

## Scope

This module is responsible for:
- Sending OTP codes via SMS.ru API (`POST /sms/send`)
- Sending order status notification SMS
- Retry with exponential backoff on failure
- Logging delivery status

## Constraints

- **Rate-limiting is NOT this module's responsibility.** Core API enforces rate limits (INV-012: 1/min, 5/hour, 10/day per phone). This worker sends everything it receives from the queue.
- **Retry policy:** 3 attempts with exponential backoff (2s, 8s, 32s). After 3 failures:
  - OTP: mark as `FAILED`, client sees "Не удалось отправить код"
  - Notifications: mark as `failed`, log error, do NOT block order processing
- **SMS content:** Minimal, ≤ 70 characters (1 SMS segment for Cyrillic).
  - OTP: `"Код подтверждения: {code}. Aura Coffee"`
  - Notifications: `"{status_text}. Заказ #{short_id}. Aura Coffee"`
- **OTP codes:** This worker does NOT store or generate OTP codes. It only delivers them via SMS. Codes are stored in Redis by core-api.
- **Sender name:** Configurable via `SMSRU_SENDER_NAME` env var (requires SMS.ru verification).

## Key Files

_(to be updated as code is added)_

## Testing

- **Framework:** pytest
- **Runner:** `pytest services/sms-worker/tests/ -v`
- **Test files:** `tests/test_<module>.py` mirrors `src/sms_worker/<module>.py`
- **Mocks:** mock SMS.ru API responses, mock Redis for OTP status updates
- **TDD:** full RED → GREEN → REFACTOR. Backend changes split into `-red` / `-green` changes.

## This Module MUST NOT

- Generate or store OTP codes (core-api + Redis handle this)
- Enforce rate limits (core-api handles this)
- Process payments or manage orders
- Block the main order processing flow on SMS failure
