## Why

The `order-checkout-red` change archived a capability spec with 5 requirements and 21 scenarios, plus 60 failing contract tests in `tests/test_checkout_service.py` and `tests/test_route_orders.py`. None of the production code those tests reference exists yet: there is no `core_api.services.checkout` module, no `core_api.routers.orders`, and `rbac_matrix.ROUTE_MATRIX` has no entry for the two new routes. This change is the GREEN half of the TDD pair — it lands the minimum implementation that turns those tests from red to green, unblocking Phase 3 items 3+ (status polling UI, YuKassa payment-worker, SMS notifications) and giving the Customer a working Cart → Order → pending-payment flow end-to-end on the backend.

## What Changes

- **ADD** `services/core-api/src/core_api/services/checkout.py` exposing `create_order(user_id, request, redis_client, db_session) -> OrderResponse`:
  - Reads Redis cart via `CartService.get(user_id)`; raises `EmptyCartError` (→ HTTP 400) when the cart is missing or has zero items
  - Runs the validator chain (`validate_stop_list`, `validate_time_slot`, `validate_delivery_address` when `type=DELIVERY`, `validate_min_delivery_amount`, `validate_promocode` when provided) BEFORE any DB write
  - Executes the PDD §7.2 pricing chain in order: `compute_subtotal` → `apply_promocode` → `apply_loyalty_points` → `compute_delivery_fee` → `compute_order_total` → `compute_estimated_accrual`
  - Persists `orders` + `order_items` (immutable snapshots from DB, not Redis) + `payments` + conditional `loyalty_transactions` + `promocode_usages` rows in a single `db_session.begin()` transaction (INV-004)
  - For `total = 0`: commits `Order.status=PAID`, `LoyaltyTransaction.type=REDEMPTION`, `Payment.amount=0`, deletes the Redis cart after commit
  - For `total > 0`: commits `Order.status=CREATED`, `LoyaltyTransaction.type=RESERVATION` (if points used), `Payment.status=PENDING` with a generated `idempotency_key`, calls `enqueue_payment_task(order_id, total, idempotency_key)` AFTER commit, leaves Redis cart in place
- **ADD** `services/core-api/src/core_api/routers/orders.py` with:
  - `POST /api/v1/orders` → `201 Created` with `OrderResponse`; maps `EmptyCartError → 400`, validator errors → `409`, Pydantic → `422`
  - `GET /api/v1/orders/{order_id}` → `200 OK` with `OrderResponse`; returns `404` when the order does not exist OR belongs to another Customer (no existence leak, INV-013)
  - Uses `get_current_user` dep for `user_id` + `role` extraction; JSON error bodies carry `detail` in Russian
- **ADD** `orders_router` registration in `core_api.main` and two entries in `core_api.rbac_matrix.ROUTE_MATRIX`: `("POST", "/api/v1/orders") -> {CUSTOMER}` and `("GET", "/api/v1/orders/{order_id}") -> {CUSTOMER}` (INV-010). No `PUBLIC_ROUTES` additions.
- **ADD** local symbol re-exports inside `core_api.services.checkout` for validators / pricing functions / Celery enqueue — these are stubs owned by sibling features (`order-pricing-validation`, `payment-yukassa`) and the RED tests patch them at `core_api.services.checkout.<name>`. The stubs live in `core_api.services.checkout` as thin no-op placeholders that raise `NotImplementedError` when called without a mock, so production code paths are explicit about the missing wiring.
- **MODIFY** `openspec/specs/order-checkout/spec.md` Purpose line (currently the "TBD — created by archiving change order-checkout-red" placeholder) to a proper one-paragraph description of the capability.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `order-checkout`: update the Purpose section from the archive-time TBD placeholder to a concrete description of the Cart → Order conversion capability. No Requirements or Scenarios change — the RED change already sealed the contract; GREEN only replaces the Purpose placeholder.

## Impact

- **Affected code (new)**:
  - `services/core-api/src/core_api/services/checkout.py`
  - `services/core-api/src/core_api/routers/orders.py`
- **Affected code (modified)**:
  - `services/core-api/src/core_api/main.py` — register `orders_router`
  - `services/core-api/src/core_api/rbac_matrix.py` — add two `ROUTE_MATRIX` entries
- **Affected tests (previously red → now green)**:
  - `services/core-api/tests/test_checkout_service.py` (40 tests)
  - `services/core-api/tests/test_route_orders.py` (20 tests)
- **APIs**: two new HTTP routes exposed in the OpenAPI schema (`POST /api/v1/orders`, `GET /api/v1/orders/{order_id}`)
- **Dependencies**: none new — uses existing SQLAlchemy session, existing `redis_client` dep, existing `get_current_user` dep, existing Pydantic schemas from `core_api.schemas.order`
- **External systems**: no real YuKassa or Celery calls happen in this change — the stubs raise `NotImplementedError` off the mocked path; real wiring is scheduled for `payment-yukassa`
- **Data**: no schema migrations — all tables (`orders`, `order_items`, `payments`, `loyalty_transactions`, `promocode_usages`) were created in `phase3-schema`
- **Specs**: Purpose-only edit to `openspec/specs/order-checkout/spec.md`

## Non-Goals

- **Real validator logic** (stop-list DB query, working-hours clock check, Yandex Maps geocoding, promocode eligibility SQL) — owned by the `order-pricing-validation` capability. The GREEN checkout service imports validator names and lets the `order-pricing-validation` change land their bodies; until then the stubs raise `NotImplementedError` on the un-mocked path, which is acceptable because the RED test suite patches every one of them.
- **Real YuKassa payment creation, confirmation-URL population, and webhook handling** — owned by the `payment-yukassa` capability. `enqueue_payment_task` ships as a stub that will be replaced by a Celery `.delay()` call once the payment-worker feature lands.
- **Order lifecycle transitions beyond CREATED and PAID** — PREPARING / READY / IN_DELIVERY / COMPLETED / CANCELLED (PDD §6.1) are owned by the `order-lifecycle` and `courier-delivery` features.
- **SMS notifications on order status change** — owned by `sms-notifications`.
- **Refunds, partial refunds, cancellations post-PAID** — owned by `payment-refunds`.
- **Admin / Barista / Courier views of the order** — this change is Customer-only. Staff routes (`GET /api/v1/admin/orders`, `PATCH /api/v1/admin/orders/{id}`) are part of the admin-panel phase.
- **Frontend checkout UI** — owned by `customer-checkout-ui`. This change is backend-only; the web-customer SPA will consume these routes in a later feature.
- **Polling cadence, WebSocket, or SSE for status updates** — only the HTTP contract is landed; polling frequency is a frontend concern.
- **MVP Phase**: PDD §7.1 Phase 3 — Order & Payment, items 1 & 2 (Cart → Order checkout service and HTTP routes). Does not touch Phase 1 (Auth), Phase 2 (Menu & Cart), or Phase 4+ (Delivery, Loyalty, Admin).
