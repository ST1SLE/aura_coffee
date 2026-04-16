## Context

Affected modules: `[payment-worker]` (new tests), `[shared]` (read-only — Phase 3 models/enums already shipped in `phase3-schema-green`).

The Payment Worker has today only a Celery skeleton (`main.py`, a single `health_check` task, minimal `settings.py`). PDD §4.2 requires it to run two processes:
1. A Celery worker for `create_payment` and `initiate_refund` tasks triggered from Core API.
2. A FastAPI HTTP server that accepts webhook callbacks from ЮKassa at `POST /webhooks/yukassa`.

ЮKassa compliance rules (PDD §8.1) dictate amounts-as-strings (`"123.45"`), mandatory `Idempotency-Key` header on create requests, HTTP Basic auth (`shopId:secretKey`), and `RUB`-only currency. Webhook security is IP-whitelist based (PDD §4.2), with idempotency on `event_id`.

This RED cycle MUST ship only failing tests. All production modules (`yukassa_client.py`, `webhook.py`, rewritten `tasks.py`) are deliberately absent; tests MUST fail with `ImportError` or `AttributeError` until the GREEN cycle lands implementation.

## Goals / Non-Goals

**Goals:**

- The test suite MUST pin the behavior contract of the YuKassa client: endpoints, auth, amount format, idempotency header, timeouts.
- The test suite MUST pin Celery task contracts: happy-path DB updates, retry behavior, compensation on exhausted retries.
- The test suite MUST pin the FastAPI webhook endpoint contract: IP whitelist, idempotency short-circuit, event dispatch, error surface.
- All tests MUST run from a container OR from a host venv without external network access (httpx → `respx` mock, webhook → FastAPI TestClient).
- Settings tests MUST confirm env-driven configuration for all five new fields.

**Non-Goals:**

- No new SQLAlchemy models or Alembic migrations. `processed_webhook_events` idempotency table is out of scope for RED — tests use Redis (fakeredis) as the idempotency store. The GREEN design MAY elect Redis or a table; this RED cycle expresses the contract at the function boundary (`is_event_processed(event_id)` / `mark_event_processed(event_id)`).
- No signature verification tests (IP whitelist only for MVP).
- No Nginx routing change.
- No core-api integration tests.

## Decisions

### D1. HTTP mocking: `respx` over manual `MockTransport`

YuKassa calls MUST be intercepted without network I/O. `respx` gives declarative matching on method + URL + headers + JSON body, and works with sync `httpx.Client`. Alternatives:

- `httpx.MockTransport`: lower-level, verbose assertions.
- `responses` / `requests_mock`: incompatible (we use `httpx`, not `requests`).

`respx` is the smallest ergonomic surface for the contract tests we need.

### D2. Webhook idempotency store: Redis via `fakeredis`

Webhooks MUST be idempotent on `event_id` (PDD §7.9 step 2). Rather than introducing a new DB table in the RED phase, we express the contract as two function calls:

- `is_event_processed(event_id: str) -> bool`
- `mark_event_processed(event_id: str) -> None`

Tests patch/stub these to assert the control flow. `fakeredis` is already used by `core-api` (see `test-infra-fakeredis`), so reusing it keeps runtime uniform. The GREEN change is free to pick the actual backend (Redis SET + TTL is the obvious choice) — this RED contract does not leak backend details.

### D3. DB for task tests: in-process SQLite

Celery task tests need to assert DB state transitions (Payment row, Order row, LoyaltyTransaction row, Promocode counter). Running a real PostgreSQL per test is overkill for RED; `phase3-schema-green` already ensures the SQLAlchemy models boot on SQLite (compat variants in place). RED tests build tables from `shared.models.Base.metadata.create_all(engine)` on a SQLite file. This is consistent with existing `services/core-api/tests/conftest.py`.

Caveat: SQLite has no PG enums, no JSONB, no partial indexes, no CHECK-constraint parity on `shop_settings`. None of the Payment Worker RED tests exercise those corners — behavior is at the ORM level (`Payment.status = SUCCEEDED`, row counts, FK integrity).

### D4. FastAPI TestClient over raw ASGI

`webhook.py` will ship a FastAPI `app`. Tests use `fastapi.testclient.TestClient` for request/response assertions. IP whitelist is tested by injecting the client IP via `X-Forwarded-For` + trusted-proxy config, OR by patching a `get_client_ip(request)` helper. RED tests assert the helper contract, not a specific middleware wiring.

### D5. Celery tasks: synchronous execution in tests

Celery tasks are tested by invoking the task function directly (`create_payment.run(...)`) with a patched `yukassa_client` module, not through a broker. Retry logic is asserted by raising `httpx.RequestError` from the mock and checking that the task re-raises (or the compensation path triggers after 3 attempts). We do NOT assert Celery retry decorator config via runtime behavior; we assert it via `create_payment.max_retries == 3` and `create_payment.autoretry_for`.

## Risks / Trade-offs

- **[Risk]** RED tests that stub out `yukassa_client` module-level symbols can drift from the real module signature. **Mitigation:** tests import and call the task with an injected client instance (`create_payment(..., _client=fake_client)` is the RED contract), OR patch `payment_worker.yukassa_client.YukassaClient` via `monkeypatch`. Tests MUST document which pattern they use.
- **[Risk]** Tests run against SQLite while production runs PostgreSQL; JSONB payload assertions would differ. **Mitigation:** RED tests avoid JSONB assertions — they touch `Payment.status`, `Order.status`, `LoyaltyTransaction` inserts, and `Promocode.current_uses` only.
- **[Risk]** `respx` version pinning drift. **Mitigation:** add `respx>=0.21,<1.0` to dev deps and document the version in `pyproject.toml`.
- **[Risk]** GREEN implementation might pick a different boundary (e.g. move idempotency into middleware). **Mitigation:** the RED contract is expressed at the function level (`is_event_processed` helper), which any implementation (middleware, decorator, inline) can satisfy.

## Atomicity Analysis (INV-004)

This change ships tests only — no financial mutations run. However, the tests PIN the atomicity contract that GREEN MUST honor:

- `create_payment` failure path MUST, in a single DB transaction, set `Payment.status = PAYMENT_FAILED`, `Order.status = CANCELLED`, insert `LoyaltyTransaction(type=REVERSAL, amount=+points_used, balance_after=...)`, and `Promocode.current_uses -= 1` (if a promocode was applied). Partial state (e.g. Payment failed but points still held) is FORBIDDEN.
- `payment.succeeded` webhook MUST, in a single DB transaction, set `Payment.status = SUCCEEDED`, `Order.status = PAID`, convert the RESERVATION loyalty row type to REDEMPTION (or append a REDEMPTION + matching reversal — design detail for GREEN), increment promo usage record, and return 200. Cart delete (Redis) MAY happen outside the DB txn since Redis is eventual-state-safe.
- `payment.canceled` webhook: mirrors the create_payment failure compensation path.

Tests assert these end-states row-by-row; they do not introspect transaction boundaries. Wrapping is the implementer's responsibility — the RED contract is "after this call, the following rows are in these states".

## State-Machine Impact (INV-016)

- **Payment Lifecycle (PDD §6.2).** Transitions covered by tests: `PENDING → AWAITING_CONFIRMATION` (create_payment success), `PENDING → PAYMENT_FAILED` (create_payment exhausted retries), `AWAITING_CONFIRMATION → SUCCEEDED` (webhook payment.succeeded), `AWAITING_CONFIRMATION → PAYMENT_FAILED` (webhook payment.canceled), `SUCCEEDED → REFUND_PENDING` (initiate_refund), `REFUND_PENDING → REFUNDED` (webhook refund.succeeded), `REFUND_PENDING → REFUND_FAILED` (webhook refund.canceled). No transitions outside this set.
- **Order Lifecycle (PDD §6.1).** Transitions touched by webhooks: `CREATED → PAID` (on payment.succeeded), `CREATED → CANCELLED` (on payment.canceled or exhausted retries in create_payment).

## Migration Plan

Not applicable — no schema changes in this cycle. `payment-yukassa-green` inherits this design and implements the contract; any new tables (e.g. `processed_webhook_events`) are proposed there.

## Open Questions

- **Webhook idempotency backend: Redis SET or new SQL table?** Default to Redis (matches §7.9 step 2 "check event_id"). Final decision belongs to `payment-yukassa-green`. RED contract is backend-agnostic.
- **`GET /v3/payments/{id}` timeout-polling caller.** PDD §6.1 says "если webhook не пришёл за 15 мин — проверить статус через ЮKassa API". The scheduler for this poll is out of scope for this RED cycle; the YukassaClient MUST expose `get_payment(payment_id)` and tests assert the endpoint wiring, but no scheduled-task test is shipped.
