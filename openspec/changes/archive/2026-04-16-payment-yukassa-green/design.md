## Context

Affected modules: `[payment-worker]` (new code + rewritten `tasks.py`/`settings.py`), `[shared]` (read-only — Phase 3 models and enums).

The Payment Worker currently exposes a single `health_check` Celery task. To satisfy the RED contract it must grow three production surfaces:

1. **YuKassa HTTP client** — thin wrapper over `httpx.Client` that encapsulates auth, idempotency, amount formatting, and timeouts (PDD §8.1).
2. **Celery tasks** — `create_payment` with retry + atomic compensation; `initiate_refund` with swallow-on-failure (PDD §6.2).
3. **FastAPI webhook app** — `POST /webhooks/yukassa` with IP whitelist, Redis idempotency, event dispatcher, and per-event DB transaction (PDD §4.2, §7.9).

All behavior is pinned by the RED tests. This document captures the implementation-level decisions that were intentionally left open in the RED design (backend choice, module boundaries, helper shapes).

## Goals / Non-Goals

**Goals:**

- Make every RED test pass with no edits to test files.
- Keep modules small and independently testable (client ≠ tasks ≠ webhook).
- Respect INV-004 (atomic compensation) and INV-016 (no status downgrades).
- Expose factories (`get_engine`, `get_redis`, `YukassaClient` import) that tests already patch with `create=True` — match those names exactly.

**Non-Goals:**

- No Dockerfile / docker-compose / Nginx changes. Production wiring of the uvicorn process and Nginx routing belongs to a subsequent integration change.
- No core-api wiring (the task is invoked from core-api in a later change).
- No webhook signature verification.
- No DB table for idempotency — Redis with a key TTL is the single source of truth.

## Decisions

### D1. Module layout

Five files inside `services/payment-worker/src/payment_worker/`:

- `settings.py` — pydantic-settings `Settings` with the six env-driven fields; parses `YUKASSA_WEBHOOK_IPS` into a trimmed `list[str]`.
- `yukassa_client.py` — `YukassaClient` class and a small response type (`CreatePaymentResult` dict or dataclass).
- `db.py` — `get_engine()` lazy singleton (creates `create_engine(settings.database_url)` once) and `session_scope()` context manager. Keeps import-time side effects out of `tasks.py`.
- `redis_client.py` — `get_redis()` lazy singleton returning a `redis.Redis.from_url(settings.redis_url)` client.
- `tasks.py` — Celery task definitions + compensation helpers. Re-exports `health_check` so existing wiring is preserved.
- `webhook.py` — FastAPI `app`, route handler, event dispatcher, idempotency helpers, IP whitelist helper.

RED tests patch the following full dotted paths — we MUST match them verbatim:

- `payment_worker.tasks.get_engine`
- `payment_worker.tasks.YukassaClient`
- `payment_worker.tasks._decrement_promocode`
- `payment_worker.webhook.get_engine`
- `payment_worker.webhook.get_redis`
- `payment_worker.webhook.dispatch_event`

That means `tasks.py` imports `YukassaClient` and `get_engine` by name (not `from ... import ...` at function level), and `webhook.py` imports `get_engine`, `get_redis`, and defines `dispatch_event` as a module-level symbol.

### D2. YukassaClient shape

- Constructor: `YukassaClient(shop_id: str, secret_key: str, base_url: str = DEFAULT_BASE_URL, timeout: httpx.Timeout | None = None)`.
- Default `timeout = httpx.Timeout(connect=10.0, read=30.0, write=30.0, pool=30.0)`.
- Internal `self._client = httpx.Client(auth=(shop_id, secret_key), timeout=self.timeout)` — HTTP Basic handled by httpx.
- `create_payment(amount_kopecks, idempotency_key, return_url, description) -> dict` — POST `/payments`. Body:
  ```json
  {
    "amount": {"value": "123.45", "currency": "RUB"},
    "confirmation": {"type": "redirect", "return_url": "..."},
    "capture": true,
    "description": "..."
  }
  ```
  Returns a dict with keys `payment_id`, `confirmation_url`, `status` — flattened from the ЮKassa response (RED test reads via `obj["payment_id"]` / `getattr`). Using a plain dict avoids an extra dataclass import.
- `get_payment(payment_id) -> dict` — GET `/payments/{id}`, no idempotency header.
- `create_refund(payment_id, amount_kopecks, idempotency_key) -> dict` — POST `/refunds` with body `{"payment_id": ..., "amount": {"value": "...", "currency": "RUB"}}`.
- Amount formatting helper: `_format_amount(kopecks: int) -> str` returns `f"{kopecks // 100}.{kopecks % 100:02d}"`. Edge cases pinned by parametrized RED test: `(100→"1.00"), (1→"0.01"), (100000→"1000.00"), (12345→"123.45")`.

### D3. Celery retry policy

```python
@celery_app.task(
    bind=True,
    name="payment_worker.tasks.create_payment",
    autoretry_for=(httpx.RequestError,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
)
def create_payment(self, order_id: str, amount_kopecks: int, idempotency_key: str) -> None:
    ...
```

Exhausted retries run compensation via Celery's `on_failure` hook OR a try/except around the final attempt. **Chosen:** try/except inside the task body — when `self.request.retries >= self.max_retries` and the call raises, invoke `_fail_payment_and_cancel_order(order_id, payment_id)` and then re-raise so Celery marks the task failed. This matches the RED test which calls `_fail_payment_and_cancel_order(...)` directly as a standalone function.

Alternative rejected: `on_failure` handler. Splits the compensation across two code paths (handler vs. unit-tested helper) and makes the atomicity story harder to reason about.

### D4. Atomic compensation

`_fail_payment_and_cancel_order(order_id, payment_id)` opens a single SQLAlchemy session/transaction:

1. `SELECT Payment, Order (with relationship Order.promocode)`.
2. `Payment.status = PAYMENT_FAILED`.
3. `Order.status = CANCELLED`.
4. If `Order.points_used > 0`: insert `LoyaltyTransaction(type=REVERSAL, amount=+Order.points_used, balance_after=<current_balance + points_used>)`. The "current balance" is computed by summing existing transactions for the user, mirroring how `phase3-schema` seeds the loyalty ledger.
5. If `Order.promocode_id is not None`: call `_decrement_promocode(session, promocode_id)` which does `UPDATE Promocode SET current_uses = current_uses - 1 WHERE id = :id AND current_uses > 0`.
6. `session.commit()`.

Any exception inside the `with` block triggers a full rollback. RED test `test_create_payment_compensation_is_atomic` verifies this by patching `_decrement_promocode` to raise — Payment/Order MUST remain at their pre-call values.

### D5. `initiate_refund` swallow-on-failure

```python
@celery_app.task(bind=True, name="payment_worker.tasks.initiate_refund", max_retries=0)
def initiate_refund(self, payment_id: str, amount_kopecks: int) -> None:
    try:
        client = YukassaClient(...)
        client.create_refund(...)
    except Exception as exc:
        logger.exception("initiate_refund failed", ...)
        return
    # mark Payment REFUND_PENDING in its own transaction
```

No retry decorator: PDD §6.2 says admin handles failures manually. RED `test_initiate_refund_failure_does_not_mutate` asserts the task doesn't raise AND the Payment row is unchanged, which rules out "retry loop" behavior.

### D6. Webhook idempotency via Redis

- Key format: `yukassa:event:{event_id}` (matches RED helper assertion).
- TTL: 24 hours (configurable, but 24h is the common ЮKassa retry window).
- Algorithm:
  1. Read `X-Event-Id` header (if missing → generate one from the payload hash — RED test always sends the header).
  2. `EXISTS yukassa:event:{event_id}` → if truthy, return 200 immediately.
  3. Dispatch the event inside a DB transaction.
  4. On success, `SET yukassa:event:{event_id} 1 EX 86400`.
  5. On exception, **do not mark processed** — FastAPI surfaces the exception as 500 (RED test asserts `fake_redis.get(...) is None`).

### D7. IP whitelist helper

Read client IP from `X-Forwarded-For` (first hop) with fallback to `request.client.host`. Compare to `settings.yukassa_webhook_ips` (a list of plain IPs in the test fixture; production will feed CIDRs — handled by `ipaddress.ip_network` check). For the RED suite the fixture is `127.0.0.1,185.71.76.1,185.71.76.2` and tests use `X-Forwarded-For: 127.0.0.1` for success, `203.0.113.9` for 403. Implementation: if entry contains `/` treat as network, else exact string match. Both branches covered.

### D8. Webhook event dispatcher

`dispatch_event(session: Session, redis: Redis, event: str, obj: dict) -> None` handles the five branches:

- `payment.succeeded`: find Payment by `yukassa_payment_id = obj["id"]`; advance Payment/Order; convert RESERVATION loyalty row → insert REDEMPTION (amount equal to the RESERVATION magnitude); drop Redis cart key `cart:{user_id}`; enqueue `Notification(channel=SMS, message_ru="Заказ оплачен...")` and `Notification(channel=IN_APP, message_ru="Заказ оплачен...")`.
- `payment.canceled`: same Payment lookup; run the same compensation body as `_fail_payment_and_cancel_order`; enqueue `Notification(channel=IN_APP, message_ru="Платёж не прошёл...")`.
- `refund.succeeded`: lookup Payment by `yukassa_payment_id = obj["payment_id"]`; `Payment.status = REFUNDED`.
- `refund.canceled`: `Payment.status = REFUND_FAILED`; enqueue an admin notification (`Notification(order_id=payment.order_id, channel=IN_APP, message_ru="Возврат не прошёл — требуется ручное вмешательство")` with `user_id=None` or a reserved admin UUID; RED test only asserts `len(notifs) >= 1`).
- unknown: log and return (endpoint still returns 200).

Dispatcher exceptions propagate → FastAPI returns 500 → event_id NOT marked processed.

### D9. Enqueue notification = insert a `Notification` row

Per Phase 3 schema, `Notification` has a `status` enum that defaults to `PENDING`. "Enqueue" in this cycle means a DB insert only; the SMS worker consumes those rows in a later phase. RED tests only check row existence and channel/body — not delivery.

## Risks / Trade-offs

- **[Risk]** `respx` will not match requests if the client uses `http2=True` — we default to HTTP/1.1.
- **[Risk]** `LoyaltyTransaction.balance_after` requires computing the current balance. Mitigation: sum `LoyaltyTransaction.amount` for the user in the same transaction before insert — matches RED assertion `balance_after == 100` (because RESERVATION was `-100`, so balance goes from `-100` back to `0`... wait: RED asserts `balance_after == 100`. Re-reading the fixture: `LoyaltyAccount.balance=0`, reservation `amount=-100, balance_after=0`. After reversal `amount=+100`, `balance_after = 0 + 100 = 100`. So the computation is `latest_balance_after + this_amount`. Implementation: fetch `LoyaltyTransaction` ordered by `created_at DESC LIMIT 1`; use its `balance_after` as the baseline.
- **[Risk]** `create=True` in tests patches module-level attributes whether or not they exist — that's fine for RED but means GREEN MUST actually expose those attributes as top-level imports, otherwise the happy-path tests will call through to a real `httpx` request. Mitigated by explicit `from payment_worker.yukassa_client import YukassaClient` at module top of `tasks.py` (not lazy).
- **[Risk]** FastAPI TestClient propagates exceptions by default (Starlette `raise_server_exceptions=True`). RED test `test_processing_exception_surfaces_as_500` uses `pytest.raises(RuntimeError)` which means the server re-raises — we do NOT need to install a custom exception handler to return 500. We just let FastAPI's default do its job, and ensure the mark-processed step is AFTER dispatch.
- **[Trade-off]** Chose dict returns from `YukassaClient` over dataclasses for brevity. RED's `_attr_or_key` helper accepts both.
- **[Trade-off]** Did not add `on_failure` Celery handler. Simpler to call the compensation helper inline — and tests support that shape directly.

## Atomicity Analysis (INV-004)

- `_fail_payment_and_cancel_order` — single transaction, all four mutations (Payment, Order, LoyaltyTransaction insert, Promocode.current_uses--). Rollback on any failure is automatic (session exits without commit).
- `payment.succeeded` handler — single transaction: Payment, Order, LoyaltyTransaction insert (REDEMPTION), Promocode finalization (no-op in this change: promo usage was already counted at order creation; here we keep `current_uses` as-is). Cart-delete (Redis) happens AFTER commit — Redis eventual consistency is acceptable.
- `payment.canceled` handler — reuses `_fail_payment_and_cancel_order`, adds notification row in same transaction.
- `refund.*` handlers — single `Payment.status` update (+ optional Notification insert) per transaction.

## State-Machine Impact (INV-016)

Implementation enforces that transitions only happen when the current status is the expected "from" state:

- `PENDING → AWAITING_CONFIRMATION` in `create_payment` (guard: `if payment.status != PENDING: log and return` to be idempotent against duplicate task invocations).
- `AWAITING_CONFIRMATION → SUCCEEDED` in `payment.succeeded` (guard: skip if already SUCCEEDED — webhook idempotency is the primary defense; this is belt-and-suspenders).
- `AWAITING_CONFIRMATION → PAYMENT_FAILED` in `payment.canceled`.
- `SUCCEEDED → REFUND_PENDING` in `initiate_refund`.
- `REFUND_PENDING → REFUNDED` in `refund.succeeded`.
- `REFUND_PENDING → REFUND_FAILED` in `refund.canceled`.

No downgrades possible.

## Migration Plan

None. No schema changes; existing `services/payment-worker/src/payment_worker/__init__.py`, `main.py`, `tasks.py` (health_check), and `settings.py` are modified non-destructively. Celery task names are new, so no task-queue draining is required.

## Open Questions

- **Who creates the admin notification user_id for `refund.canceled`?** The Phase 3 schema has `Notification.user_id` nullable — we leave it NULL for admin notifications. If a real admin UUID exists later, it is a trivial one-line swap.
- **Is `shared.logging` the right logger?** Payment Worker currently uses bare `logging` stdlib. We keep stdlib here to avoid introducing a dependency; a future observability cycle can swap in structured logging.
