## Why

`payment-yukassa-red` shipped 26 failing tests that pin the Payment Worker's behavior against PDD §4.2, §6.2, §7.9, §8.1. All of them fail today with `ImportError` / `AttributeError` because the production modules (`yukassa_client.py`, `webhook.py`, rewritten `tasks.py`, upgraded `settings.py`) do not yet exist. This GREEN cycle implements exactly those modules — no new behavior beyond what RED already describes.

## What Changes

- **Upgrade `payment_worker.settings`** to load `yukassa_shop_id`, `yukassa_secret_key`, `yukassa_webhook_ips` (comma-separated list, whitespace-trimmed), `yukassa_base_url` (default `https://api.yookassa.ru/v3`), and `database_url` — on top of the existing `redis_url`.
- **Add `payment_worker.yukassa_client.YukassaClient`** wrapping `httpx.Client` with HTTP Basic auth (`shop_id:secret_key`), `Idempotency-Key` header on creates, amounts formatted as string (`"123.45"`), timeout 10s connect / 30s read, and methods `create_payment`, `get_payment`, `create_refund`.
- **Rewrite `payment_worker.tasks`** with Celery tasks `create_payment` and `initiate_refund` plus compensation helpers (`_fail_payment_and_cancel_order`, `_decrement_promocode`) and a `get_engine()` accessor. Retry policy: `max_retries=3`, `autoretry_for=(httpx.RequestError,)`, `retry_backoff=True`. Exhausted retries run atomic compensation. `initiate_refund` swallows and logs client errors (no mutation, no raise). `health_check` task is preserved.
- **Add `payment_worker.webhook`** — FastAPI `app` exposing `POST /webhooks/yukassa`. Checks `X-Forwarded-For` against `YUKASSA_WEBHOOK_IPS`, short-circuits on duplicate `X-Event-Id` via Redis key `yukassa:event:{event_id}`, dispatches `payment.succeeded`, `payment.canceled`, `refund.succeeded`, `refund.canceled`; acknowledges unknown types with 200; surfaces handler exceptions as 500 without marking the event processed. Each event handler runs its DB mutations atomically inside a single transaction.
- **Extend `payment_worker.main`** so `celery_app` imports `payment_worker.tasks` (keeps task discovery) without starting the FastAPI app (dual process).
- **No new runtime dependencies** — `httpx`, `fastapi`, `sqlalchemy` are added to `[project.dependencies]` (they were dev-only in RED). `respx`, `fakeredis`, `pytest-asyncio` remain dev-only.
- **No schema migrations** — idempotency uses Redis (`fakeredis` in tests, real Redis in prod).

## Capabilities

### New Capabilities
- `payment-worker-yukassa`: production YuKassa integration. Owns the ЮKassa HTTP client, the `create_payment` / `initiate_refund` Celery tasks, and the FastAPI webhook endpoint. Compensates atomically on payment/refund failures (INV-004), honors the payment state machine (INV-016, PDD §6.2), and preserves the order state machine (PDD §6.1).

### Modified Capabilities
- `payment-worker-yukassa-tests`: the RED test suite is unchanged in source but now PASSES against the GREEN implementation (no edits to existing tests — only new production files).

## Impact

- Affected code: `services/payment-worker/src/payment_worker/{settings.py,tasks.py,yukassa_client.py (new),webhook.py (new),main.py}`, `services/payment-worker/pyproject.toml` (promote runtime deps).
- Affected tests: all 26 existing tests in `services/payment-worker/tests/` — previously RED, now GREEN.
- Affected runtime: `payment-worker` container now has a second process (FastAPI via uvicorn). Dockerfile / docker-compose entrypoint wiring is **deferred** — the webhook is reachable in tests via `TestClient`, and the production entrypoint is part of the next integration change (see `Non-Goals`).
- Affected deps (runtime): `httpx`, `fastapi`, `sqlalchemy` promoted from `[dev]` to `[project.dependencies]`. `uvicorn` is added (required to run the FastAPI app in prod).
- Not affected: `shared` schema, core-api, Phase 1/2 behavior, Nginx config.

## MVP Phase

- Phase 3: Order & Payment (PDD §7.1).

## Non-Goals

- No Dockerfile / docker-compose edits in this change. The dual-process entrypoint (Celery + uvicorn) and the Nginx route to `/webhooks/yukassa` belong to a follow-up integration change.
- No core-api integration (core-api triggering `create_payment.delay(...)` on order creation).
- No partial refunds (forbidden by INV-005 — `initiate_refund` always refunds `Payment.amount`).
- No HMAC/signature verification of webhooks (IP whitelist only, per PDD §4.2).
- No `processed_webhook_events` SQL table — Redis suffices for idempotency and matches the RED contract.
- No admin UI to retry `REFUND_FAILED → REFUND_PENDING`.
- No scheduler for the §6.1 "15-minute timeout poll" against `GET /v3/payments/{id}` (client method exists, but no periodic task).
