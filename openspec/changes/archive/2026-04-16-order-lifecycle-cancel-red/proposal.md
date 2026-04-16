## Why

Phase 3 (Order & Payment) schema is now live (migration 0005 + models), but the runtime layer that moves an `Order` through the PDD §6.1 state machine — and the compensating §7.6 cancellation chain — does not exist. Staff (barista, courier, admin) cannot advance orders, customers cannot cancel, and INV-004/INV-005/INV-010/INV-016 are enforced nowhere. TDD discipline requires that every rule in §6.1/§7.6 is pinned as a failing test BEFORE any service or router ships. This RED cycle delivers only those failing tests; GREEN will turn them green.

## What Changes

- Add `services/core-api/tests/test_order_lifecycle.py` — unit tests for `core_api.services.order_lifecycle.transition_order(order_id, new_status, actor_role, db_session)`:
  - Every allowed transition from PDD §6.1 that the router owns: PAID→PREPARING, PAID→CANCELLED, PREPARING→READY, PREPARING→CANCELLED, READY→IN_DELIVERY (requires `type=DELIVERY`), READY→COMPLETED (requires `type=PICKUP`), READY→CANCELLED, IN_DELIVERY→COMPLETED.
  - Every forbidden transition raises a clear error (COMPLETED→any, CANCELLED→any, every backward transition, PAID→READY, etc.) — INV-016.
  - CREATED→PAID and CREATED→CANCELLED are NOT owned by this service (they belong to the payment webhook) and MUST be rejected here.
  - Role gating (INV-010): BARISTA may only do PAID→PREPARING, PREPARING→READY, READY→COMPLETED (pickup). COURIER may only do READY→IN_DELIVERY, IN_DELIVERY→COMPLETED. ADMIN may do any non-forbidden transition. CUSTOMER may do none (cancellation goes through the dedicated endpoint).
  - Side effects: every successful transition calls `send_order_notification()` on the order-notifications module (mocked); transition to COMPLETED creates a `LoyaltyTransaction(type=ACCRUAL, amount=+floor((total - delivery_fee) * loyalty_percent / 100))` and increments `LoyaltyAccount.balance` (INV-003).
- Add `services/core-api/tests/test_order_cancel.py` — unit tests for `core_api.services.order_cancel.cancel_order(order_id, cancelled_by, reason, db_session)`:
  - Customer rights (INV-005): only when `order.status == PAID`; every other source status rejects with a clear reason.
  - Admin rights: PAID/PREPARING/READY allowed; IN_DELIVERY/COMPLETED/CANCELLED rejected.
  - §7.6 step 2 (promocode return): decrement `promocode.current_uses` and delete the matching `promocode_usages` row. No-op when the order had no promocode.
  - §7.6 step 3 (loyalty reversal): when `order.points_used > 0`, insert a `LoyaltyTransaction(type=REVERSAL, amount=+points_used)` and bump `LoyaltyAccount.balance`. No-op when `points_used == 0`.
  - §7.6 step 4 (refund): when `payment.amount > 0`, enqueue the Celery task `initiate_refund(payment_id, amount)` via a mocked `celery_app.send_task`. Skipped when total was 0.
  - §7.6 step 5: order fields `status`, `cancelled_by`, `cancelled_at` all updated.
  - §7.6 step 6: notification service called exactly once with the reason propagated.
  - INV-004 atomicity: if any step raises, the whole DB transaction rolls back (no partial state — points not refunded without the order being cancelled, promocode usage not deleted without the reversal, etc.). The refund task MUST NOT be enqueued on rollback paths.
- Add `services/core-api/tests/test_route_order_actions.py` — HTTP layer tests for `services/core-api/src/core_api/routers/order_actions.py`:
  - `PATCH /api/v1/orders/{order_id}/status` accepts `OrderStatusUpdate`, calls `order_lifecycle.transition_order`, returns 200 with `OrderResponse`; RBAC accepts BARISTA/COURIER/ADMIN and rejects CUSTOMER with 403 (INV-010).
  - `POST /api/v1/orders/{order_id}/cancel` accepts `CancelOrderRequest`, calls `order_cancel.cancel_order`; CUSTOMER may cancel their own order (403 on someone else's), ADMIN may cancel any order, staff roles BARISTA/COURIER are rejected with 403.
  - Unknown / invalid new_status → 422. Forbidden transition → 409 with a human-readable reason. Not-found order → 404.
  - `main.py` registers the new router (test imports `app.router.routes` and asserts both paths are present).
- Tests MUST fail against the current codebase — because `order_lifecycle`, `order_cancel`, and `order_actions` do not exist yet. Failures will surface as `ImportError` / `AttributeError` / 404 on RBAC matrix lookup, which are all valid RED states.

## Capabilities

### New Capabilities
- `order-lifecycle-tests`: RED-cycle test suite pinning the Order Lifecycle state machine service, the Cancellation Chain service, and the staff-action HTTP router. Lives under `services/core-api/tests/` and covers §6.1, §7.6, INV-003, INV-004, INV-005, INV-010, INV-016.

### Modified Capabilities
<!-- None — `order-schema` is untouched; this adds a brand-new behavioural capability. -->

## Impact

- **Code**: 3 new test files under `services/core-api/tests/`. No production code changes in this cycle.
- **APIs**: none shipped yet — the router the tests target lands in the GREEN change.
- **Dependencies**: no new runtime dependencies; tests use the existing pytest / SQLAlchemy / httpx / unittest.mock toolchain.
- **Database**: no migration changes. Tests use the session-scoped `migrated_db_session` PostgreSQL fixture (Phase 3 tables already exist on 0005) or in-memory SQLite where PG features aren't exercised.
- **Mocks**: `core_api.services.order_notifications.send_order_notification` (not yet created) and `payment-worker` Celery task `initiate_refund` (invoked via `celery_app.send_task`) are monkey-patched in tests; no real network or broker calls.

## Non-Goals

- No production code for `order_lifecycle`, `order_cancel`, or the router — all ship in `order-lifecycle-cancel-green`.
- No implementation or tests for CREATED→PAID / CREATED→CANCELLED — those belong to the payment webhook (`payment-yukassa` feature) and are explicitly out of scope here.
- No real notification service; the order-notifications module itself is a separate feature. We only declare the import path and mock it.
- No payment-worker refund task implementation; we only assert that the Celery `send_task` call is made with the right signature.
- No auto-completion timer for pickup orders (PDD §6.1 auto-complete) — that is a scheduled-job feature.
- No frontend changes (staff dashboard buttons land with the UI feature).
- No delivery assignment lifecycle coupling (§6.3) — that runs parallel to §6.1 and is a separate change.
- No loyalty balance math refactor — we use the existing `LoyaltyAccount` row and the existing `LoyaltyTransaction` ledger already shipped by `phase3-schema-green`.

## MVP Phase

Phase 3 — Order & Payment (PDD §7.1).
