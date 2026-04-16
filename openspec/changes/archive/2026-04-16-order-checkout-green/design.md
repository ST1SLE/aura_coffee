## Context

**Affected modules:** [core-api]

This is the GREEN half of the TDD pair `order-checkout-red` / `order-checkout-green`. The RED cycle sealed a 5-requirement capability spec (`order-checkout`) and landed 60 failing tests across `tests/test_checkout_service.py` (40) and `tests/test_route_orders.py` (20). Current state: the symbols those tests reference (`core_api.services.checkout.create_order`, `core_api.routers.orders.orders_router`, plus twelve stub names for validators / pricing / Celery enqueue) do not exist. `core_api.rbac_matrix.ROUTE_MATRIX` has no entry for the two new routes. Default-deny RBAC in `core_api.middleware.rbac` currently rejects `POST /api/v1/orders` and `GET /api/v1/orders/{order_id}` with 403, which is why 5 of the 60 RED tests already pass (the 401-no-token and 403-staff-role assertions).

Stakeholders are narrow: the only caller inside MVP is the web-customer SPA (to be built in the `customer-checkout-ui` feature). The `payment-worker` Celery service will consume the task enqueued by `enqueue_payment_task` once the `payment-yukassa` feature lands. No staff or admin surface touches this capability in this change.

Constraints that shape the design:
- **INV-001 (prepayment only)** — no cash path, no pay-on-delivery branch. `total > 0` always routes through YuKassa; `total = 0` commits PAID directly.
- **INV-004 (atomic financials)** — all of `orders`, `order_items`, `payments`, `loyalty_transactions`, `promocode_usages`, and the `loyalty_accounts.balance` decrement MUST land in a single DB transaction. Any validator failure or pricing error MUST abort before the first DB write.
- **INV-010 (role isolation)** — staff roles (ADMIN / BARISTA / COURIER) MUST be rejected with 403 at these routes. `ROUTE_MATRIX` entries scope both routes to `{CUSTOMER}`.
- **INV-013 (PII isolation, 152-FZ)** — `GET /api/v1/orders/{order_id}` returns 404 (not 403) on a foreign order id, so existence is not leaked across customers.
- **INV-014 (immutable order items)** — `order_items.name_ru`, `name_en`, `unit_price`, `modifiers_snapshot`, and `size_label`/`size_price` are snapshots read fresh from the DB at checkout time. No FK on `menu_item_id` / `size_option_id` — plain `BigInteger` references — so archiving the menu never breaks an order row.
- **PDD §7.2 pricing chain** — strict order: subtotal → promocode → loyalty points → delivery fee → total → estimated accrual. The RED tests patch all six functions on the checkout module namespace and assert call order via a parent `MagicMock`; GREEN MUST call them in exactly that sequence.
- **PDD §6.1 Order Lifecycle** — only two transitions are in scope: the INSERT that creates an Order with `status=CREATED` (total > 0 path) and the INSERT that creates an Order with `status=PAID` (total = 0 path). No other transitions are implemented here.

## Goals / Non-Goals

**Goals:**
- Turn the 60 RED tests from `test_checkout_service.py` and `test_route_orders.py` green without deleting or weakening any assertion.
- Land the `create_order` service and the two HTTP routes with production-shaped code that a real YuKassa Celery task and real validator suite can be swapped into by replacing stub implementations with real ones — without touching the route or service shape.
- Make every stub symbol (`validate_stop_list`, `validate_time_slot`, `validate_delivery_address`, `validate_min_delivery_amount`, `validate_promocode`, `compute_subtotal`, `apply_promocode`, `apply_loyalty_points`, `compute_delivery_fee`, `compute_order_total`, `compute_estimated_accrual`, `enqueue_payment_task`) importable at `core_api.services.checkout.<name>` so the test patch paths hold.
- Preserve the existing 5-tests-passing RBAC assertions by adding the correct `ROUTE_MATRIX` entries.
- Deliver zero regressions: no other test file changes status as a side effect.

**Non-Goals:**
- Real validator bodies — stay as stubs that raise `NotImplementedError`. Real logic belongs to `order-pricing-validation`.
- Real Celery wiring — `enqueue_payment_task` is a stub. Real `.delay()` call belongs to `payment-yukassa`.
- Order Lifecycle transitions beyond the initial INSERT — PREPARING / READY / IN_DELIVERY / COMPLETED / CANCELLED remain out of scope.
- YuKassa webhook handler, refunds, partial refunds — out of scope.
- Frontend consumption — out of scope; owned by `customer-checkout-ui`.
- Schema changes — none. All required tables were created in `phase3-schema`.

## Decisions

### Decision 1: Stubs live inside `core_api.services.checkout`, not in sibling modules

**Context:** The RED tests patch twelve external-looking functions at `core_api.services.checkout.<name>`. Those functions belong semantically to two other capabilities (`order-pricing-validation` and `payment-yukassa`) that do not exist yet.

**Decision:** The GREEN change defines twelve Python-level stubs in `core_api/services/checkout.py`. Each stub has the correct call signature, a docstring pointing to the owning capability, and a body that raises `NotImplementedError("<symbol> not wired — owned by <capability>")`. When `order-pricing-validation` lands, it will import those symbols from their real modules (`core_api.services.validation`, `core_api.services.pricing`) and re-bind them inside `checkout.py` via explicit `from ... import <name>` statements at the top of `checkout.py`. Until then, production code paths that are not mocked will fail loudly at runtime — and that is the desired behavior for an incomplete feature behind feature-incomplete siblings.

**Alternative considered (rejected):** Put the stubs in `core_api.services.validation` / `core_api.services.pricing` and have `checkout.py` import them. This would force GREEN to modify three modules and would fight the RED patch paths (`@patch("core_api.services.checkout.validate_stop_list")` would patch a local alias that the real code path does not use if the checkout function reaches through to the origin module). The stub-in-checkout approach keeps the mock seam aligned with the production seam.

**Alternative considered (rejected):** Inline the stubs as `lambda` or closure-level helpers. This breaks `patch()` — mock.patch needs module-level names. Rejected.

### Decision 2: Idempotency key is a stable UUID4, generated inside `create_order`

**Context:** The RED spec requires `payments.idempotency_key` to be non-null and for the Celery enqueue to receive it. YuKassa deduplicates by this key on their side.

**Decision:** `create_order` MUST call `uuid.uuid4()` once, cast to `str`, and use the same value for (a) the `Payment.idempotency_key` column, (b) the argument passed to `enqueue_payment_task`. The key is generated on the first line of the atomic section (after validation, before INSERTs) so a validator abort does not leak unused keys.

**Alternative considered (rejected):** Derive the key from `(user_id, cart_hash, timestamp)` — more complex, no actual benefit since YuKassa tolerates any unique string and the DB column has no uniqueness constraint beyond the per-payment uniqueness.

### Decision 3: Redis cart deletion is a post-commit side effect (total=0 path only)

**Context:** PDD §6.1 says the cart is cleared on `PAID`, not `CREATED`. For the total>0 path, the PAID transition happens later (webhook), so the cart MUST NOT be touched at checkout. For the total=0 path, the Order is PAID in the same transaction.

**Decision:** `create_order` SHALL delete `cart:{user_id}` from Redis only on the total=0 branch, only AFTER the SQL transaction commits successfully. If the DB commit succeeds but the Redis DELETE fails, the function MUST still return a successful `OrderResponse` — the cart is ephemeral and a stale cart is less harmful than a duplicate-paid order. The DELETE MUST NOT live inside the DB transaction (SQL and Redis have different consistency domains).

**Alternative considered (rejected):** Use a Redis MULTI/EXEC or Lua script to coordinate — overkill for a best-effort cleanup. Rejected.

### Decision 4: Celery enqueue is post-commit for the total>0 path

**Context:** Enqueueing before commit creates a race: the worker might dequeue and query the DB before the Order row is visible. The RED spec explicitly requires post-commit enqueue.

**Decision:** The control flow inside `create_order` SHALL be (for total > 0):
1. Read cart from Redis; reject if empty
2. Run validators (all raise on failure — no DB writes yet)
3. Run pricing chain
4. Open `db_session.begin()` transaction
5. INSERT `orders`, `order_items[*]`, `payments`, conditional `loyalty_transactions`, conditional `promocode_usages`, conditional `loyalty_accounts` balance UPDATE
6. Flush + commit
7. After commit returns: call `enqueue_payment_task(order_id, total, idempotency_key)` ONCE
8. Build and return `OrderResponse`

If the enqueue fails, the Order still exists with `status=CREATED` and `Payment.status=PENDING`. A future reconcile job (out of scope) can re-enqueue. The DB is the source of truth; Celery is the effect queue.

### Decision 5: Pricing chain accepts the checkout context; validators accept individual facts

**Context:** The RED tests mock each function with simple return values (e.g., `compute_subtotal` returns `10000`, `apply_promocode` returns `(9000, 1000)`). The call signatures need to be consistent across RED and GREEN.

**Decision:** `create_order` SHALL call the stubs with these signatures:
- `compute_subtotal(cart_items: list[CartLine], db_session) -> int` — returns subtotal in kopecks
- `apply_promocode(subtotal: int, promocode: Promocode | None) -> tuple[int, int]` — returns `(amount_after, discount)`
- `apply_loyalty_points(amount: int, points: int, loyalty_account: LoyaltyAccount) -> tuple[int, int]` — returns `(amount_after, points_applied)`
- `compute_delivery_fee(amount_after_discount: int, request: CreateOrderRequest) -> int`
- `compute_order_total(subtotal: int, discount: int, points_applied: int, delivery_fee: int) -> int`
- `compute_estimated_accrual(total: int, loyalty_account: LoyaltyAccount) -> int`

Validator signatures:
- `validate_stop_list(cart_items, db_session) -> None` — raises on stop-list hit
- `validate_time_slot(slot: datetime | None, shop_settings) -> None`
- `validate_delivery_address(address: DeliveryAddress, db_session) -> None` — only called when `request.type == DELIVERY`
- `validate_min_delivery_amount(subtotal: int, address: DeliveryAddress) -> None` — only called when delivery
- `validate_promocode(code: str | None, user_id: UUID, subtotal: int, db_session) -> Promocode | None`

These signatures mirror the mock expectations in the RED tests verbatim.

### Decision 6: Order fetch in GET route uses `user_id` filter at the query level

**Context:** INV-013 forbids leaking existence of foreign orders. The RED spec requires 404 (not 403) for both non-existent ids and foreign ids.

**Decision:** `GET /api/v1/orders/{order_id}` SHALL query `Order` with `WHERE id = :order_id AND user_id = :current_user_id` in a single SELECT. If the row is missing, return 404 with a generic Russian message. No separate "exists but not yours" branch — same response shape, same message, same status.

**Alternative considered (rejected):** Two queries (existence → ownership) with distinct error messages. Rejected because it leaks existence through timing and messages.

## Atomicity Analysis (INV-004)

The `create_order` SQL transaction MUST cover every row whose existence is financially material:

| Row | Table | Condition |
|-----|-------|-----------|
| Order | `orders` | always (1 row) |
| OrderItem[] | `order_items` | always (N rows, one per cart line) |
| Payment | `payments` | always (1 row) |
| LoyaltyTransaction (RESERVATION or REDEMPTION) | `loyalty_transactions` | when `points_to_use > 0` (1 row) |
| LoyaltyAccount balance UPDATE | `loyalty_accounts` | when `points_to_use > 0` (1 row UPDATE) |
| PromocodeUsage | `promocode_usages` | when `promocode_code` provided and valid (1 row) |
| Promocode `current_uses` UPDATE | `promocodes` | when promocode applied (1 row UPDATE) |

All are persisted within `with db_session.begin():` (or equivalent session-level transaction). On any exception raised inside the block — whether from a validator, from `IntegrityError` on a unique constraint, or from the pricing chain — SQLAlchemy rolls back and no row is committed. The Celery enqueue is outside the `with` block and therefore cannot rollback the DB; if the enqueue fails after commit, the DB remains consistent and a reconcile mechanism (out of scope) would re-emit.

**Race conditions considered:**
- Concurrent checkout with the same cart (double-submit): the second call will either see the Redis cart already gone (total=0 path deleted it) → `EmptyCartError`, or will create a second Order for the same items. YuKassa idempotency at the payment level and the frontend single-submit button are the current guardrails. Idempotent order creation by `(user_id, cart_hash)` is out of scope.
- Concurrent loyalty redemption: the `loyalty_accounts` row UPDATE uses `SELECT ... FOR UPDATE` semantics via SQLAlchemy's default isolation level inside the transaction — the second transaction waits, reads a stale balance after commit, and the RED test `points_to_use > balance` check (handled by `apply_loyalty_points` on GREEN path / by validator) will reject the second redemption.
- Concurrent promocode use: the `promocodes.current_uses` INCREMENT under the transaction serializes by row lock. `validate_promocode` checks `current_uses < max_uses` inside the transaction window.

## State Machine Analysis (PDD §6.1)

The Order Lifecycle state machine has states: `CREATED → PAID → PREPARING → READY → IN_DELIVERY → COMPLETED` plus `CANCELLED` as a terminal from any pre-COMPLETED state. This change touches exactly **two** entry transitions:

| Transition | Entry condition | Owned by |
|------------|-----------------|----------|
| (initial) → CREATED | total > 0, atomic INSERT | this change |
| (initial) → PAID | total = 0, atomic INSERT | this change |

All downstream transitions (CREATED → PAID via webhook, PAID → PREPARING via barista action, etc.) are out of scope. The `OrderStatus` enum already includes all states (`packages/shared/src/shared/enums.py`), so no enum change is needed. INV-016 (exhaustive state machines) is respected: the two INSERT paths only produce the two entry states the state machine defines.

## 152-FZ Compliance (INV-013)

`GET /api/v1/orders/{order_id}` MUST NOT distinguish in its response between "order does not exist" and "order exists but belongs to a different Customer". Both cases return HTTP `404` with an identical Russian body `{"detail": "Заказ не найден"}`. This prevents probing (`for id in range(...)`) from revealing the existence of other customers' orders. Per-Customer order listing (`GET /api/v1/orders`) is out of scope for this change.

No new PII fields are persisted by this change. `orders` stores `user_id` (FK) and the delivery address; the `users` / `user_profiles` split already isolates raw phone and name. No PII flows to logs — `create_order` logs only `user_id`, `order_id`, `total`.

## Risks / Trade-offs

- **[Risk]** Unmocked production call to any validator / pricing / Celery stub raises `NotImplementedError` at runtime, breaking the feature end-to-end before `order-pricing-validation` lands. **→ Mitigation:** `customer-checkout-ui` and `order-pricing-validation` are scheduled before any UI rollout; the backend feature is shipped dark behind missing frontend. Monitoring is not required because no real user traffic can reach the stubs.
- **[Risk]** Post-commit Celery enqueue can fail silently, leaving the Order in `CREATED` with no payment task ever emitted. **→ Mitigation:** Log at ERROR if enqueue raises; a future reconcile job scans `orders WHERE status=CREATED AND created_at < now() - interval '5 min'` and re-enqueues. This is out of scope for this change but is enabled by the architectural choice to put enqueue post-commit.
- **[Risk]** Post-commit Redis DELETE can fail, leaving a stale cart after a total=0 order. **→ Mitigation:** Best-effort DELETE with exception-swallow; user-visible impact is a stale cart list, which the client refreshes on the next cart GET. Acceptable per Decision 3.
- **[Trade-off]** Stubs raising `NotImplementedError` vs. returning plausible defaults. Plausible defaults would let the feature appear to work during local dev without `order-pricing-validation`, but would mask integration gaps. Loud failure is preferred; local dev of downstream features (e.g. `customer-checkout-ui`) can mock these at the test layer just like RED does.
- **[Trade-off]** No idempotency at the order level (only at the payment level). A double-submit with network retry can create two orders. The frontend is responsible for disabling the submit button while the request is in flight. Server-side cart-hash idempotency is a Phase 4+ concern.

## Migration Plan

- **Forward:** purely additive — no DB migration, no config change, no dependency bump. The two new `ROUTE_MATRIX` entries take effect on process restart. The route handler reads symbols that exist at import time, so a normal `docker compose restart core-api` is sufficient.
- **Rollback:** revert the GREEN commit. The RED tests return to red, the routes return to 403 default-deny, and no DB state is left behind (no schema changes). No data migration rollback needed.
- **Data backfill:** none.

## Open Questions

None. All technical choices referenced by the RED test contract are fixed by that contract. Any ambiguity the implementation finds inside the `create_order` body is resolved by "make the patched mocks' assertions pass without changing them".
