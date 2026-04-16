## Context

Phase 3 schema (migration 0005) ships 9 tables — `orders`, `order_items`, `payments`, `refunds`, `loyalty_transactions`, `promocodes`, `promocode_usages`, `notifications`, `shop_settings` — plus enums for every state machine. No behavioural code consumes them yet.

This RED change adds the failing tests that pin down the **service-layer state machine** (`order_lifecycle.transition_order`) and the **cancellation chain** (`order_cancel.cancel_order`), plus the thin HTTP router that exposes both operations to staff and customers. All production code is intentionally absent — the GREEN cycle `order-lifecycle-cancel-green` ships it.

Affected modules: **[core-api]**. The [payment-worker] Celery task `initiate_refund` and the as-yet-unlanded [core-api] `order_notifications` module are **referenced by import path and mocked** in tests, not built here.

Authoritative references: PDD §6.1 (Order Lifecycle), §7.2 (loyalty accrual formula), §7.6 (Cancellation Chain), INV-003, INV-004, INV-005, INV-010, INV-016.

## Goals / Non-Goals

**Goals:**
- Produce a pytest suite that MUST fail against HEAD because `core_api.services.order_lifecycle`, `core_api.services.order_cancel`, and `core_api.routers.order_actions` do not exist.
- Pin every PDD §6.1 transition owned by staff: allowed transitions land with a green test shape, forbidden transitions land with a dedicated parametrised test asserting a raised error (INV-016).
- Pin role gating per INV-010: BARISTA/COURIER/ADMIN have narrow, non-overlapping allowed sets; CUSTOMER cannot drive state machine transitions (uses the cancel endpoint instead).
- Pin loyalty accrual exactly at the READY→COMPLETED transition using the INV-003 formula `floor((order.total - order.delivery_fee) * loyalty_percent / 100)`.
- Pin the full §7.6 cancellation chain in one transactional unit: rights check → promocode return → points reversal → refund-task enqueue → order update → notification. INV-004 atomicity is asserted by forcing a mid-chain failure and observing zero partial state.
- Pin the HTTP surface: path, method, body schema, status codes, RBAC (server-side only — INV-002).

**Non-Goals:**
- Production implementations for the two services or the router.
- CREATED→PAID / CREATED→CANCELLED transitions (payment webhook territory — `payment-yukassa` feature).
- Real notification delivery or real refund submission — mocked.
- Frontend staff panel screens (ship with the UI feature).
- Auto-complete timer for pickup orders (separate scheduled-job feature).
- Delivery Assignment lifecycle (§6.3) coupling — tracked in its own change.

## Decisions

### D1 — Service signature: plain functions, not classes

Both services are module-level functions:

```
order_lifecycle.transition_order(
    order_id: uuid.UUID,
    new_status: OrderStatus,
    actor_role: str,               # "admin" | "barista" | "courier"
    db_session: Session,
) -> Order

order_cancel.cancel_order(
    order_id: uuid.UUID,
    cancelled_by: Literal["customer", "admin"],
    reason: str | None,
    db_session: Session,
) -> Order
```

Rationale: they are stateless domain operations; a class wrapper would add nothing beyond the session parameter, which is already explicit. Matches the project's preference (see `core_api.services.pricing`: module-level functions).

**Alternative rejected**: a `OrderLifecycleService` class — would have forced every test to instantiate and would make the mock surface larger without benefit.

### D2 — Error type: one domain exception per service

Each service raises a dedicated subclass of `Exception` carrying a machine-readable `reason` string. Mirrors the existing `CartValidationError` pattern in `core_api.services.cart`. The router translates `reason` into the corresponding HTTP status (409 for business-rule violations, 404 for not-found, 403 for role gating on cancel).

- `order_lifecycle.OrderTransitionError(reason: str)` — raised for forbidden transitions, bad roles, order not found, precondition failures (`READY→IN_DELIVERY` on a pickup order, `READY→COMPLETED` on a delivery order).
- `order_cancel.OrderCancelError(reason: str)` — raised for not-cancellable statuses, wrong role, order not found.

**Alternative rejected**: HTTPException raised inside services — couples service layer to FastAPI and blocks reuse from Celery tasks.

### D3 — Transition table lives in the service, not the DB

The allowed-transition table is a Python constant (frozenset of `(from_status, to_status, required_actor_roles, optional_order_type_requirement)` tuples) declared at module top of `order_lifecycle.py`. Everything not in the table is forbidden by construction — this is how INV-016 gets enforced and tested: a parametrised RED test enumerates every `(from, to)` pair NOT in the table and asserts `OrderTransitionError` is raised.

**Alternative rejected**: generate the table from the PDD markdown at runtime — unnecessary build-time indirection.

### D4 — Side effects sequenced inside the service

`transition_order` performs, in order:
1. Lookup order (→ `OrderTransitionError("order_not_found")` if missing).
2. Validate transition via the table (→ `OrderTransitionError("forbidden_transition")` or `"role_not_allowed"` or `"wrong_order_type_for_transition"`).
3. Update `order.status`. For READY→COMPLETED also compute accrual and insert a `LoyaltyTransaction(type=ACCRUAL)` + bump `LoyaltyAccount.balance` in the same session.
4. Call `send_order_notification(order, new_status, reason=None)`. The function is imported at module top from `core_api.services.order_notifications` — RED tests monkey-patch that module attribute to observe the call.
5. Flush/commit is the caller's responsibility (the router commits via dependency-injected session).

Tests assert: side-effect ordering, exact accrual amount, exact balance delta, exact notification-call payload. The accrual uses `after_points = order.total - order.delivery_fee` per PDD §7.2 step 6 + INV-003.

### D5 — Cancellation chain as a single transactional function

`cancel_order` performs the full PDD §7.6 body in one function body. All database work uses `db_session` (no nested sessions). A mid-chain failure is tested by monkey-patching `celery_app.send_task` to raise — the RED test asserts:
- `order.status` remains the pre-call value;
- `promocode.current_uses` unchanged;
- `promocode_usages` row still present;
- `loyalty_account.balance` unchanged;
- no new `loyalty_transaction` row of type `REVERSAL`;
- notification mock was not called.

The service itself does NOT call `db_session.commit()` — that is the router's contract, which ensures rollback on exceptions works naturally via FastAPI dependency teardown.

### D6 — Celery enqueue via `celery_app.send_task`, not direct import

`initiate_refund` lives in the `payment-worker` service, which `core-api` must not import directly (separate container, separate virtualenv in CI). Following the existing Celery pattern, `order_cancel` does:

```python
from core_api.celery_app import celery_app
celery_app.send_task("payment_worker.initiate_refund", args=[str(payment_id), amount])
```

RED tests monkey-patch `core_api.services.order_cancel.celery_app.send_task` and assert: task name, positional args, and that it is **not** called when `payment.amount == 0` or on rollback paths.

### D7 — Router path & RBAC

```
PATCH /api/v1/orders/{order_id}/status      body: OrderStatusUpdate
POST  /api/v1/orders/{order_id}/cancel      body: CancelOrderRequest
```

RBAC matrix additions (enforced server-side by `RBACMiddleware`):
- `PATCH /api/v1/orders/{order_id}/status` → `{BARISTA, COURIER, ADMIN}` (staff-only; INV-010).
- `POST /api/v1/orders/{order_id}/cancel` → `{CUSTOMER, ADMIN}` — CUSTOMER access additionally requires that the JWT `sub` matches `order.user_id` (enforced in the router body, tested with a 403-on-foreign-order scenario).

RED tests assert: every forbidden role/path pair returns 403, the authorized paths reach the service layer (verified by patching the service to a sentinel), and `main.py` registers the router (a test inspects `app.router.routes` for both paths).

### D8 — Test layout mirrors existing Phase 3 tests

- `test_order_lifecycle.py` — pure unit tests against sqlite-backed session (no HTTP). Uses a small factory (inline, not shared) to build `Order`, `OrderItem`, `LoyaltyAccount`, `Promocode`, `Payment` rows.
- `test_order_cancel.py` — unit tests against sqlite-backed session, with `celery_app.send_task` and `send_order_notification` monkey-patched.
- `test_route_order_actions.py` — HTTP tests using the `client` + `customer_headers` / `barista_headers` / `courier_headers` / `admin_headers` fixtures already in `conftest.py`. Service layer is monkey-patched at the router import path (`core_api.routers.order_actions.transition_order` / `cancel_order`) so HTTP tests stay decoupled from service tests.

## Risks / Trade-offs

- **[Risk] Tests over-specify internal structure** → **Mitigation**: assertions target public observable state (order columns, ledger rows, mock call args) — not private helpers. If a helper is renamed during GREEN, tests still pass.
- **[Risk] Monkey-patching `celery_app.send_task` hides import-time failures** → **Mitigation**: one integration-style test imports the real `core_api.celery_app` module and asserts `send_task` exists as a callable attribute.
- **[Risk] Race between `send_task` and DB commit** (task enqueued, transaction rolled back → double refund) → **Accepted**: GREEN cycle MUST enqueue the task AFTER the DB commit (design pattern to land with implementation). RED tests declare the contract: enqueue happens only on the happy path, not on rollback.
- **[Risk] SQLite vs. PostgreSQL enum handling** → **Mitigation**: service tests use sqlite with `Base.metadata.create_all` already configured in `conftest.py`; enum-backed columns are compared by `.value` string, which works on both engines.

## Atomicity Analysis (INV-004)

The cancellation chain mutates five persistence surfaces:
1. `promocodes.current_uses` (decrement) + `promocode_usages` row delete.
2. `loyalty_transactions` insert + `loyalty_accounts.balance` update.
3. `orders.status` / `cancelled_by` / `cancelled_at` update.
4. Celery task enqueue (external side effect).
5. Notification service call (external side effect).

Per PDD §7.6 and INV-004, (1)+(2)+(3) MUST commit atomically. The RED suite enforces this:
- A test patches `celery_app.send_task` to raise and asserts nothing from (1)+(2)+(3) persisted (session rolled back).
- A test patches the notification mock to raise and asserts the DB state is rolled back AND the Celery task was NOT enqueued.
- A test patches the DB `UPDATE orders` step to raise (via a side_effect on the session `add`) and asserts nothing persisted.

The order-lifecycle service has a narrower atomic surface: `orders.status` + (for COMPLETED) `loyalty_transactions` + `loyalty_accounts.balance` MUST commit atomically. The RED suite asserts this by patching the notification call to raise AFTER the status update and observing a rolled-back session. Per the D5 decision the router owns the commit, so the test framework's per-test transaction rollback naturally cleans state.

## State Machine Reference (INV-016)

PDD §6.1 transitions owned by this router (explicit allow-list):

| From | To | Roles | Extra precondition |
|------|----|-------|--------------------|
| PAID | PREPARING | BARISTA, ADMIN | — |
| PAID | CANCELLED | ADMIN (and CUSTOMER via cancel endpoint) | routed via cancel_order when cancelled_by=customer |
| PREPARING | READY | BARISTA, ADMIN | — |
| PREPARING | CANCELLED | ADMIN | — |
| READY | IN_DELIVERY | COURIER, ADMIN | order.type == DELIVERY |
| READY | COMPLETED | BARISTA, ADMIN | order.type == PICKUP; accrue loyalty |
| READY | CANCELLED | ADMIN | — |
| IN_DELIVERY | COMPLETED | COURIER, ADMIN | accrue loyalty |

Transitions NOT owned here (MUST be rejected with `forbidden_transition`):
- CREATED→PAID, CREATED→CANCELLED (payment webhook).
- Any COMPLETED→*, any CANCELLED→* (terminal).
- Any backward transition (PREPARING→PAID, READY→PREPARING, IN_DELIVERY→READY, etc.).
- IN_DELIVERY→CANCELLED (PDD §6.1 explicitly forbids).

## Migration Plan

No schema migration. The change is tests-only; rollback is `git revert` of the three new test files.

## Open Questions

1. **Should READY→COMPLETED for delivery orders run through `transition_order` or only via `IN_DELIVERY→COMPLETED`?**
   → Decision: per PDD §6.1, `READY→COMPLETED` is PICKUP-only. Delivery orders MUST go READY → IN_DELIVERY → COMPLETED. The RED test encodes this as a precondition failure (`wrong_order_type_for_transition`) when a delivery order attempts READY→COMPLETED.

2. **Does the customer cancel endpoint need to verify JWT `sub` matches `order.user_id`?**
   → Decision: yes — at the router level, BEFORE calling `cancel_order`. A CUSTOMER attacking someone else's order receives 403. Covered by a dedicated RED test.

3. **Do we create the `order_notifications` module stub as part of RED?**
   → Decision: no. RED tests monkey-patch `core_api.services.order_notifications.send_order_notification` using a `sys.modules` shim when the real module is absent. The GREEN cycle creates the real stub module (or a real call into the notification feature) as needed.
