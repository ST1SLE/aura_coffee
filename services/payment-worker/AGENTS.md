# Payment Worker

Celery worker for YuKassa payment processing — payment creation, webhook handling, and refunds.

**PDD sections:** §4.2 (boundaries), §6.2 (Payment Lifecycle), §7.9 (Webhook Processing Chain), §8.1 (YuKassa compliance)

## Tech Stack

- Python 3.12+, Celery
- SQLAlchemy 2.0 (sync) for DB access
- `requests` or `httpx` for YuKassa API calls
- pytest for testing

## Scope

This module is responsible for:
- Creating payments in YuKassa API (`POST /v3/payments`)
- Processing incoming webhooks from YuKassa (payment.succeeded, payment.canceled, refund.succeeded, refund.canceled)
- Initiating full refunds via YuKassa API (`POST /v3/refunds`)
- Checking payment status on timeout (`GET /v3/payments/{id}`) — 15 min timeout per §6.1
- Updating Payment status in DB and triggering Order status transitions

## Constraints

- **Idempotency:** Every payment creation request MUST include a unique `Idempotency-Key` (UUID). Repeated webhooks with the same `event_id` MUST NOT duplicate operations.
- **Webhook verification:** Incoming webhooks MUST be verified by IP whitelist (`YUKASSA_WEBHOOK_IPS` env var). Signature verification MUST be enabled if configured in YuKassa dashboard. Invalid webhooks → HTTP 403 + log as potential attack.
- **Amounts:** YuKassa expects amounts as string `"100.50"` (rubles with kopecks). Convert from internal kopecks integer: `f"{amount_kopecks / 100:.2f}"`.
- **Currency:** Only `RUB`. No other currencies.
- **Retry on failure:** 3 attempts for payment creation. On exhaustion → Payment status = `PAYMENT_FAILED`, Order → `CANCELLED`.
- **Webhook response:** Always HTTP 200 after successful processing. Non-200 triggers YuKassa retry (up to 10 times in 24h). If processing fails internally → do NOT return 200, let YuKassa retry.
- **Test/production mode:** Logic MUST NOT depend on mode. Switching is via env vars (`YUKASSA_SHOP_ID`, `YUKASSA_SECRET_KEY`).

## Key Files

_(to be updated as code is added)_

## This Module MUST NOT

- Handle HTTP requests from clients (that's core-api)
- Send SMS or notifications (that's sms-worker)
- Manage cart, menu, or user data
- Perform partial refunds (only full refunds, per INV-005)
