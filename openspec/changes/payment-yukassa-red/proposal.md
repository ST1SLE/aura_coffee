## Why

Phase 3 (Order & Payment) shipped the DB schema (`phase3-schema-green`). The next brick is the Payment Worker itself — the only component allowed to talk to ЮKassa (PDD §4.2). TDD discipline requires that behavior contracts ship as failing tests BEFORE any production code exists. This RED cycle locks the payment creation, webhook processing, and refund flows from PDD §6.2, §7.9, §8.1 into executable test fixtures that drive the GREEN cycle.

## What Changes

- Add `services/payment-worker/src/payment_worker/settings.py` test expectations: new env-driven fields (`database_url`, `yukassa_shop_id`, `yukassa_secret_key`, `yukassa_webhook_ips`, `yukassa_base_url`) — asserted via `test_settings.py`.
- Add `services/payment-worker/tests/test_yukassa_client.py` — `YukassaClient` contract: auth header, idempotency key propagation, amount formatting ("123.45"), endpoint paths for `create_payment`, `get_payment`, `create_refund`, timeouts.
- Add `services/payment-worker/tests/test_tasks.py` — Celery task contracts: `create_payment` happy path, retry on httpx error, exhausted retries → `PAYMENT_FAILED` + Order `CANCELLED` + loyalty REVERSAL + promocode decrement; `initiate_refund` happy path and failure-is-swallowed.
- Add `services/payment-worker/tests/test_webhook.py` — FastAPI webhook endpoint contracts: IP whitelist 403, idempotency short-circuit (returns 200 without re-processing), `payment.succeeded`, `payment.canceled`, `refund.succeeded`, `refund.canceled`, unknown-type path, 500 on internal crash.
- Add `services/payment-worker/tests/conftest.py` — pytest fixtures for isolated SQLite DB, seeded Order/Payment rows, httpx transport mocks, and a FastAPI `TestClient`.
- Extend `services/payment-worker/pyproject.toml` dev extras (`httpx`, `fastapi`, `pytest-asyncio`, `sqlalchemy`, `respx` for httpx mocking). `pytest.ini_options` gains `asyncio_mode = "auto"` if needed.
- All new tests are expected to FAIL with `ImportError` / `AttributeError` until the GREEN cycle lands `yukassa_client.py`, `webhook.py`, new `tasks.py`, and upgraded `settings.py`.

## Capabilities

### New Capabilities
- `payment-worker-yukassa-tests`: RED-cycle test suite that pins the Payment Worker contract (ЮKassa client + Celery tasks + FastAPI webhook + settings) against PDD §4.2, §6.2, §7.9, §8.1. Lives under `services/payment-worker/tests/` and covers happy paths, retries, idempotency, IP whitelisting, loyalty/promo compensation, and webhook event fan-out.

### Modified Capabilities
<!-- none — shared.models and database schema were frozen in phase3-schema-green -->

## Impact

- Affected code: `services/payment-worker/tests/` (new), `services/payment-worker/pyproject.toml` (dev deps).
- Affected tooling: the `payment-worker` pytest suite will include new failing tests.
- Affected dependencies (dev only for this cycle): `httpx`, `respx`, `fastapi`, `pytest-asyncio`, `sqlalchemy`.
- NOT affected in this cycle: production modules `payment_worker.yukassa_client`, `payment_worker.webhook`, `payment_worker.tasks`, `payment_worker.settings` — those ship in `payment-yukassa-green`. No migrations, no schema changes, no core-api edits.

## MVP Phase

- Phase 3: Order & Payment (PDD §7.1).

## Non-Goals

- No production code: no `yukassa_client.py`, no `webhook.py`, no rewritten `tasks.py`, no updates to `settings.py` in this cycle.
- No docker-compose changes (dual-process entrypoint lands in integration, not here).
- No core-api changes (order creation, payment enqueue, and cart-delete logic belong to a later change).
- No partial refunds (forbidden by INV-005).
- No signature verification of webhooks (IP whitelist only for MVP, per PDD §4.2).
- No admin UI for refund retry (state machine allows `REFUND_FAILED → REFUND_PENDING`, UI is post-MVP).
- No performance/load tests.
