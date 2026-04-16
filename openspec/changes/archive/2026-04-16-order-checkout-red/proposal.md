## Why

Phase 3 (Order & Payment) — item 1 in PDD §7.1 — requires converting Cart → Order: a transactional flow that reads Redis, runs validators, composes the pricing chain (§7.2), writes an atomic set of rows (orders/order_items/payments/loyalty_transactions/promocode_usages — INV-004), and hands off to payment-worker. TDD discipline for backend (AGENTS.md §Two-Change Model) requires the RED cycle to land only failing tests that pin the contract before implementation.

## What Changes

- Add `services/core-api/tests/test_checkout_service.py` — unit tests for `core_api.services.checkout.create_order`: empty-cart rejection, validator wiring (stop-list / working hours / delivery / promocode), pricing-chain call order, atomic DB writes (Order + OrderItems + Payment + optional LoyaltyTransaction + optional PromocodeUsage), `total = 0` loyalty-only shortcut (Order → PAID, cart deleted, no Celery enqueue), normal `total > 0` path (Order stays CREATED, cart retained, Celery `create_payment` task enqueued), and INV-014 item snapshot immutability.
- Add `services/core-api/tests/test_route_orders.py` — HTTP tests for `core_api.routers.orders`: `POST /api/v1/orders` (customer-only, 201 on success, 400 on empty cart, 409 on validator failure, 422 on malformed body, 401 unauthenticated, 403 for staff) and `GET /api/v1/orders/{order_id}` (customer fetches own order, 404 for foreign order, includes `confirmation_url` when available for polling).
- Add RBAC matrix entries in tests asserting the two new routes map to `{CUSTOMER}`.
- All new tests are expected to FAIL in RED until the GREEN cycle lands `services/checkout.py`, `routers/orders.py`, and the wiring in `main.py`.

## Capabilities

### New Capabilities
- `order-checkout`: Checkout pipeline (service + HTTP endpoints) that converts a Redis cart into a persisted Order/Payment with atomic financial writes, loyalty/promocode reservation, and `confirmation_url` polling support. Covers PDD §7.1 Phase 3 items 1-2, INV-004, INV-006, INV-014.

### Modified Capabilities

## Impact

- Affected code (this RED cycle): `services/core-api/tests/` only (two new test files).
- Not touched in RED: `services/core-api/src/core_api/services/checkout.py`, `services/core-api/src/core_api/routers/orders.py`, `services/core-api/src/core_api/main.py`, RBAC matrix — all delivered in the sibling GREEN cycle `order-checkout-green`.
- External dependencies (validators in `services/validators/`, pricing helpers in `services/pricing.py` beyond current, Celery task in payment-worker) are MOCKED in tests; the order-pricing-validation and payment-yukassa features ship separately.
- MVP Phase: Phase 3 — Order & Payment (PDD §7.1, items 1-2).

## Non-Goals

- No implementation of `checkout.py` service or `routers/orders.py` — production code ships in GREEN.
- No real Celery broker or YuKassa calls — `celery_app.send_task` is patched.
- No validator or pricing implementations — they live in sibling features (`order-pricing-validation`, `payment-yukassa`) and are mocked here.
- No Order Lifecycle transitions beyond CREATED / PAID-on-zero-total — PDD §6.1 transitions after CREATED (PREPARING / READY / IN_DELIVERY / COMPLETED / CANCELLED) ship in subsequent Phase 3 items (3-5).
- No SMS notifications, refunds, or webhook handling — Phase 3 items 3, 5, 6.
- No frontend (checkout UI) changes.
- No Alembic migrations — Phase 3 schema already landed in `phase3-schema-green`.
