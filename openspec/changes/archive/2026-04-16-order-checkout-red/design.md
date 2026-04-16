## Affected Modules

`[core-api]`

## Context

Phase 3 §7.1 item 1-2 converts a Redis cart into a persisted order atomically. The checkout feature is the largest financial boundary in the app after payment: it consumes validators (stop-list, working hours, delivery radius, promocode), runs the full PDD §7.2 pricing chain, writes 3-5 DB rows in one transaction (INV-004), optionally short-circuits to `PAID` when loyalty covers the whole total, and hands off the remainder to the payment-worker via a Celery task. Two sibling features provide the dependencies: `order-pricing-validation` (validators + extended pricing helpers) and `payment-yukassa` (`create_payment` Celery task). They are mocked in RED tests so this cycle is self-contained.

The RED cycle of this change ships ONLY failing tests. GREEN lands implementation.

## Goals / Non-Goals

**Goals:**
- Pin the checkout service contract as executable tests covering empty-cart rejection, validator invocation order, DB transaction atomicity (INV-004), immutable item snapshots (INV-014), `total = 0` loyalty-only shortcut (Order → PAID immediately), and `total > 0` Celery hand-off.
- Pin the orders router contract (POST creation, GET detail for polling `confirmation_url`) with RBAC checks and status codes.
- All tests fail in RED with `ImportError` or `ModuleNotFoundError` (the target modules don't exist yet).

**Non-Goals:**
- No production code (no `services/checkout.py`, no `routers/orders.py`, no `main.py` wiring, no `ROUTE_MATRIX` edits) — lands in GREEN.
- No real validator / pricing / Celery code — mocked.
- No Order Lifecycle transitions after CREATED/PAID (PDD §6.1 PREPARING/READY/etc. ship in Phase 3 items 3-5).
- No SMS/refund/webhook plumbing.

## Decisions

### D1. Mock path for validators (stop-list, working hours, delivery, promocode)

The task brief says validators live in `services/validators/` (owned by the `order-pricing-validation` feature). Since that module does not exist, tests MUST patch by stringly-typed symbol names at the call site — i.e. patch `core_api.services.checkout.validate_stop_list`, `validate_time_slot`, `validate_delivery_address`, `validate_min_delivery_amount`, `validate_promocode`. This forces the GREEN implementation to import those names at module top-level (either re-export from `validators` or import them directly), which is the contract we want to pin.

**Alternative considered:** mock `core_api.services.validators.validate_stop_list` directly. **Rejected:** the module does not exist yet — `unittest.mock.patch` requires the path to resolve; a missing attribute raises `AttributeError`. Patching at `core_api.services.checkout.X` still requires `X` to be importable there, but our RED tests fail on `import core_api.services.checkout` itself (the file is absent), so the patch path is reached only in GREEN when the symbols exist. **Alternative considered:** let GREEN decide the import style. **Rejected:** that leaks design ambiguity into implementation. Pinning "validators are imported by name into checkout.py" is a worthwhile contract.

### D2. Mock path for pricing-chain functions

Same rationale as D1. Tests patch `core_api.services.checkout.compute_subtotal`, `apply_promocode`, `apply_loyalty_points`, `compute_delivery_fee`, `compute_order_total`, `compute_estimated_accrual`. GREEN MUST import those names into `checkout.py` (either via `from core_api.services.pricing import ...` or via re-exports). `compute_subtotal` already exists in `services/pricing.py`; the rest land with `order-pricing-validation`.

### D3. Mock path for Celery hand-off

`celery_app.send_task("payment_worker.tasks.create_payment", ...)` — the `celery_app` instance will be imported by checkout as `from core_api.celery_app import celery_app` (mirrors expected convention) OR a thin wrapper function `enqueue_payment_task(order_id, amount, idempotency_key)`. Tests patch `core_api.services.checkout.enqueue_payment_task` (or equivalent — GREEN picks one) and assert call args. Since both names are patched-by-string, GREEN is free to pick.

**Decision:** pin `enqueue_payment_task` as the patch target — a single symbol is simpler than patching the whole Celery app. GREEN adds a one-line wrapper if needed.

### D4. Fixtures: Redis is fakeredis; DB is real PG via `db_session`

Follows the cart pattern (`test_cart_service.py` + `conftest.py` `cart_redis` + `db_session` fixtures). Checkout reads cart from Redis (fakeredis suffices) and writes Order/OrderItem/Payment rows to Postgres. SQLite path is skipped for the real-DB tests (the Phase 3 migration uses JSONB, PG enums, partial indexes — SQLite cannot reflect them). Pure unit tests that only exercise the service with heavy mocks can run on in-memory SQLite.

### D5. User + loyalty account fixture

Tests that write orders need a real `users` row + `loyalty_accounts` row (FK RESTRICT on `orders.user_id`, loyalty reservation writes to `loyalty_accounts`). Add a `_checkout_user` fixture to the test file (or conftest if we want to share) that inserts a `User`, `UserProfile`, and `LoyaltyAccount(balance=…)` row and yields the UUID.

### D6. Route registration — RBAC assertion in route-coverage test

`test_route_coverage.py::test_all_routes_covered` enumerates all mounted routes. When orders router lands in GREEN it MUST be mirrored in `ROUTE_MATRIX` — otherwise route-coverage fails. In RED we add a dedicated assertion that the two expected entries (`POST /api/v1/orders` and `GET /api/v1/orders/{order_id}`) exist in `ROUTE_MATRIX` with exactly `{CUSTOMER}`. This will fail with `KeyError`/`AssertionError` in RED.

### D7. OpenAPI operation count

Test that `/openapi.json` contains `post` on `/api/v1/orders` and `get` on `/api/v1/orders/{order_id}`. Mirrors `test_cart_router_now_has_five_operations` pattern.

### D8. Error-code mapping

Per task brief:
- `400 Bad Request` — empty cart ("Корзина пуста")
- `409 Conflict` — validator rejection (stop-list, working hours, promocode invalid, delivery address out of radius, min delivery amount unmet)
- `422 Unprocessable Entity` — Pydantic validation failure (auto, FastAPI default)
- `401` — no/invalid JWT
- `403` — non-customer role

GET detail:
- `404 Not Found` — order_id does not exist OR belongs to a different user (do not leak existence — merge both into 404)

## Atomicity Analysis (INV-004)

The checkout DB transaction covers:

1. INSERT `orders` row (status=CREATED).
2. INSERT 1+ `order_items` rows (immutable snapshots per INV-014).
3. INSERT `payments` row (status=PENDING, amount=total, idempotency_key=UUID).
4. IF `points_used > 0`: INSERT `loyalty_transactions(type=RESERVATION, amount=-points)` AND UPDATE `loyalty_accounts.balance -= points`.
5. IF `promocode_id`: UPDATE `promocodes.current_uses += 1` AND INSERT `promocode_usages` row.
6. IF `total == 0`: UPDATE `orders.status = PAID` AND UPDATE `loyalty_transactions.type = REDEMPTION` for the RESERVATION written in step 4. Cart is deleted from Redis OUTSIDE the DB transaction but AFTER commit (Redis is not transactional — acceptable per PDD §7.1 note "Корзина (Redis) удаляется после подтверждения оплаты (PAID)").

RED tests assert: all writes happen in one session.begin() / commit, no flushed-but-not-committed partial state on validator failure, and Redis cart is NOT touched when DB commit fails. (Hard to test rollback in fakeredis without real-PG, so the RED tests assert callers' observable behaviour; robust atomicity testing with intentional rollback is GREEN-cycle work.)

## Risks / Trade-offs

- **[Risk]** Tests over-specify mock paths → GREEN implementation forced into awkward imports.
  → **Mitigation:** patch at `core_api.services.checkout.<symbol>` — GREEN is free to `from ... import` or re-export; we only assert the symbol exists in checkout's namespace.
- **[Risk]** `total = 0` flow edge cases (e.g. loyalty covers promo-discounted subtotal to exactly zero) might desync between RESERVATION and REDEMPTION if we split writes.
  → **Mitigation:** test the state inspection directly — after `create_order` returns for `total=0`, `LoyaltyTransaction.type = REDEMPTION` and `Order.status = PAID`.
- **[Risk]** Celery `send_task` failure → Order row already created but payment not enqueued. INV-004 is violated.
  → **Mitigation:** enqueue happens AFTER DB commit per PDD §7.9 pattern; if enqueue fails, Order stays CREATED and the cleanup cron eventually transitions to CANCELLED (Phase 3 item 3 work). RED tests assert enqueue is called AFTER commit (via call-order assertion if possible, or implicit from mock invocation).

## Migration Plan

No schema migration — Phase 3 tables already landed in `phase3-schema-green` (migration `0005`). No data backfill.

## Open Questions

- Should the GREEN implementation host `enqueue_payment_task` in `core_api.services.checkout` or in a new `core_api.celery_client` module? **Resolution:** left to GREEN; RED patches the attribute on `checkout` module directly, so the GREEN implementation can define it locally OR import it — either works.
- What fields does the Celery task expect (`amount` in kopecks? rubles? payload shape)? **Resolution:** deferred to `payment-yukassa` design; RED asserts only `order_id` (UUID) and `total` (int, kopecks) and `idempotency_key` (UUID string) appear as kwargs to `enqueue_payment_task`. GREEN may add more fields without breaking these tests.
