## Context

Affected modules: [core-api], [shared] (read-only).

Phase 3 schema (orders, payments, loyalty_accounts, loyalty_transactions, promocodes, promocode_usages) already exists and is committed to `main`. The RED cycle for this change (archived as `2026-04-16-order-lifecycle-cancel-red`) shipped 84 failing tests across three files — `test_order_lifecycle.py`, `test_order_cancel.py`, `test_route_order_actions.py` — that pin down the exact state machine, role matrix, side effects, and HTTP contract. This design spells out how the implementation MUST be structured to turn those tests green without regressing the rest of the suite.

The state machine is authoritative from PDD §6.1 (order states) and the cancellation chain from PDD §7.6. INV-003, INV-004, INV-005, INV-010, INV-016 are the five binding rules.

## Goals / Non-Goals

**Goals:**
- Implement the order state machine as a pure allow-list — every transition not in the list MUST raise `OrderTransitionError(reason="forbidden_transition")`.
- Implement the cancellation chain as a single atomic unit — a failure in ANY step MUST roll back ALL five artefacts (order, promocode, promocode_usages, loyalty_transactions, loyalty_account.balance).
- Expose both operations as HTTP endpoints with correct RBAC and error mapping.
- Keep the notification and refund-enqueue seams patchable from tests (tests monkey-patch names inside the service module and router module).

**Non-Goals:**
- No retry logic for failed refund enqueues — if `send_task` raises, we roll back everything and let the caller see 409 / 500. A future Phase 3.x change MAY add an outbox pattern.
- No audit log beyond the existing `cancelled_by` / `cancelled_at` columns plus the new `LoyaltyTransaction(type=REVERSAL)` row. No separate event table.
- No WebSocket / SSE for status updates.

## Decisions

### D1: Allow-list tables — transitions keyed by `(from, to)`, role gate keyed by `(from, to)`

**What:** Two nested constants inside `order_lifecycle.py`:

```python
_ALLOWED_TRANSITIONS: set[tuple[OrderStatus, OrderStatus]] = {
    (OrderStatus.PAID, OrderStatus.PREPARING),
    (OrderStatus.PAID, OrderStatus.CANCELLED),
    (OrderStatus.PREPARING, OrderStatus.READY),
    (OrderStatus.PREPARING, OrderStatus.CANCELLED),
    (OrderStatus.READY, OrderStatus.IN_DELIVERY),
    (OrderStatus.READY, OrderStatus.COMPLETED),
    (OrderStatus.READY, OrderStatus.CANCELLED),
    (OrderStatus.IN_DELIVERY, OrderStatus.COMPLETED),
}

_ALLOWED_ROLES: dict[tuple[OrderStatus, OrderStatus], frozenset[str]] = {
    (OrderStatus.PAID, OrderStatus.PREPARING):        frozenset({"barista", "admin"}),
    (OrderStatus.PAID, OrderStatus.CANCELLED):        frozenset({"admin"}),
    (OrderStatus.PREPARING, OrderStatus.READY):       frozenset({"barista", "admin"}),
    (OrderStatus.PREPARING, OrderStatus.CANCELLED):   frozenset({"admin"}),
    (OrderStatus.READY, OrderStatus.IN_DELIVERY):     frozenset({"courier", "admin"}),
    (OrderStatus.READY, OrderStatus.COMPLETED):       frozenset({"barista", "admin"}),
    (OrderStatus.READY, OrderStatus.CANCELLED):       frozenset({"admin"}),
    (OrderStatus.IN_DELIVERY, OrderStatus.COMPLETED): frozenset({"courier", "admin"}),
}
```

**Why:** INV-016 demands exhaustive enumeration. A data table is strictly more auditable than `if/elif` chains and lines up 1:1 with the PDD §6.1 table. `customer` is absent from every role set on purpose — cancellation for customers flows through `order_cancel.cancel_order`, not through `transition_order`.

**Rejected alternative:** encoding the matrix as a pydantic model / class-per-state. Unnecessary indirection — the data shape here is literally two tables.

### D2: Order-type gating for READY transitions

**What:** After the role check, `transition_order` MUST apply a type guard:
- `(READY, IN_DELIVERY)` requires `order.type == OrderType.DELIVERY` — pickup orders raise `OrderTransitionError(reason="wrong_order_type_for_transition")`.
- `(READY, COMPLETED)` requires `order.type == OrderType.PICKUP` — delivery orders raise the same reason (delivery orders reach COMPLETED through IN_DELIVERY).

**Why:** PDD §6.1 splits the READY row by order type. Without this guard a barista could skip IN_DELIVERY on a delivery order, which violates the courier workflow.

### D3: Loyalty accrual at COMPLETED, via the ledger

**What:** When the target status is COMPLETED, after the UPDATE of `order.status`:

1. Read `shop_settings.loyalty_percent` (single-row table, enforced by Phase 3 schema). If no row exists, percent = 0.
2. Compute `accrual_amount = (order.total - order.delivery_fee) * loyalty_percent // 100` with integer division.
3. If `accrual_amount > 0`:
   - Append `LoyaltyTransaction(user_id=order.user_id, order_id=order.id, type=ACCRUAL, amount=accrual_amount, balance_after=account.balance + accrual_amount)`.
   - Increment `loyalty_account.balance` by `accrual_amount`.
4. If `accrual_amount == 0`: skip both writes (tests assert delta-only, not row count).

**Why:** INV-003 — loyalty is accrued on money paid, not on points redeemed or delivery-fee value. Using integer division matches existing Phase 3 payment-split logic and avoids float rounding drift.

**Rejected alternative:** Decimal arithmetic. Kopecks are already integers end-to-end; introducing Decimal just here creates a boundary conversion.

### D4: `order_cancel` is a single-transaction, fail-fast chain

**What:** `cancel_order` executes this sequence inside the caller-provided `db_session`:

1. **Rights check** (pure, no DB writes):
   - Load order (404 if absent: `OrderCancelError(reason="order_not_found")`).
   - `cancelled_by == "customer"` AND `order.status != PAID` → `OrderCancelError(reason="customer_cannot_cancel_in_this_status")`.
   - `cancelled_by == "admin"` AND `order.status in {IN_DELIVERY, COMPLETED, CANCELLED}` → `OrderCancelError(reason="not_cancellable_in_this_status")`.
2. **Promocode return**: if `order.promocode_id` is set, `UPDATE promocode SET current_uses = current_uses - 1 WHERE id = order.promocode_id`, then `DELETE FROM promocode_usages WHERE order_id = order.id`.
3. **Points reversal**: if `order.points_used > 0`, insert `LoyaltyTransaction(type=REVERSAL, amount=order.points_used, balance_after=account.balance + order.points_used)` and increment `loyalty_account.balance`.
4. **Refund enqueue**: if `payment.amount > 0`, `celery_app.send_task("payment_worker.initiate_refund", args=[str(payment.id), payment.amount])`. If `send_task` raises, propagate — the caller MUST rollback (see D5).
5. **Order update**: set `order.status=CANCELLED`, `cancelled_by=cancelled_by`, `cancelled_at=datetime.now(UTC)`.
6. **Notification**: `send_order_notification(order, OrderStatus.CANCELLED, reason=reason)`. If this raises, propagate — same rollback path.
7. **Commit** the session. Return the updated order.

Steps 5 and 6 are re-ordered from the PDD's literal listing so that notification happens AFTER every other side effect but BEFORE commit. This matters for test 2.12 (`test_notification_failure_rolls_back_and_no_task_enqueued`) — see D6.

**Why:** INV-004 demands atomicity; this sequence places all DB writes and the only external-effect-we-cannot-undo (refund enqueue) inside a single `try` with a bare `raise` on any exception. The caller (router) wraps this in a session context manager; if the service raises, the `with` block rolls back automatically.

### D5: Atomicity MUST rely on SQLAlchemy's session-commit boundary

**What:**
- The service accepts a live `Session` but does NOT call `.commit()` until step 7.
- On any exception, we re-raise and let the caller's context manager roll back. Internally we also do not catch/swallow — every `except` in `cancel_order` re-raises.
- The router obtains the session via `Depends(get_session)` (which yields a session and closes it on exit); it calls the service inside a `try` and re-raises. FastAPI's dependency-injection finaliser rolls back the open transaction on unhandled exception.

**Rejected alternative:** explicit `SAVEPOINT` / nested `.begin_nested()`. Unnecessary here — the whole operation is a single logical transaction, and there is no intermediate "partial" state that should survive a later failure.

### D6: Refund enqueue happens BEFORE notification

**What:** The call ordering above is: ... promocode → points → `send_task` → order update → `send_order_notification` → commit.

**Why:** Test 2.12 (`test_notification_failure_rolls_back_and_no_task_enqueued`) asserts that if notification raises, `send_task` must NOT have been called. The ONLY way to satisfy this is to put `send_task` AFTER notification. But test 2.11 (`test_celery_send_task_failure_rolls_back_everything`) asserts DB rollback when `send_task` fails, so `send_task` cannot be the first step either.

Resolution: **swap** — notification BEFORE refund enqueue. Order becomes: rights → promo → points → order-update → **notification** → **send_task** → commit. This satisfies both: notification failure = no send_task call + rollback (DB writes not committed yet); send_task failure = full rollback including DB writes that preceded it.

**Why this is safe:** The notification is sms-only (Phase 5 hasn't wired real SMS yet; sms-worker is a stub). It is an in-process call that either succeeds or raises synchronously. The refund enqueue is a network call to Redis — if it fails we roll back every DB write we just made, which matches the invariant "either the whole cancel happened or none of it did".

**Trade-off:** if `send_task` succeeds but the subsequent commit fails (extremely unlikely with a healthy PG connection), we have enqueued a refund for an order whose cancellation did not persist. Accepted risk — the refund task itself idempotency-checks the payment status before issuing the YuKassa refund, so in practice a duplicate/orphan task is a no-op.

### D7: Domain errors at service layer, HTTP mapping at router layer

**What:** Services raise two domain exceptions with a single `reason: str` attribute:

```python
class OrderTransitionError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
```

Router maps them:
- `reason == "order_not_found"` → `HTTPException(status_code=404, detail={"reason": "order_not_found"})`
- Any other reason → `HTTPException(status_code=409, detail={"reason": reason})`

**Why:** Matches the `CartValidationError` pattern already established in `core_api.services.cart`. Keeps services framework-agnostic and lets tests assert on `.reason` without touching HTTP.

### D8: Router owns the CUSTOMER-owner check for cancel

**What:** The cancel endpoint's dependency stack is:
1. RBAC middleware allows CUSTOMER + ADMIN.
2. Handler logic: if the JWT role == CUSTOMER, load order, check `order.user_id == jwt.sub`; mismatch → 403 (FastAPI `HTTPException(403)`).
3. Then call `cancel_order(..., cancelled_by=role, ...)`.

**Why:** RBAC matrix is path-based and cannot inspect request body / URL parameters against the DB. The per-request owner check MUST live in the handler. Test 3.10 exercises this — it expects the service to never be invoked for a foreign-order cancel.

**Alternative rejected:** adding a "resource-owner" lookup field to the RBAC matrix. Would create a new architectural pattern for a single use case.

### D9: `order_actions` router uses `Depends(get_session)`, not a global session

**What:** Every handler function signature: `def handler(order_id: UUID, body: Schema, db: Session = Depends(get_session), claims: JWTClaims = Depends(get_current_claims))`. The handler does ONE service call inside a `try`, catches the two domain exceptions, maps to HTTP, and returns a Pydantic `OrderResponse`.

**Why:** Matches `order.py` router in the same service. Session lifecycle stays under FastAPI's control.

### D10: Minimal stubs for celery_app and send_order_notification

**What:**
- `core_api/celery_app.py`: `from celery import Celery; celery_app = Celery("core_api", broker=settings.redis_url)`. No tasks defined — we only call `.send_task`.
- `core_api/services/order_notifications.py`: `def send_order_notification(order, new_status, reason=None): celery_app.send_task("sms_worker.order_status_changed", args=[str(order.id), new_status.value, reason])`. Thin; tests patch it.

**Why:** Tests import these names and monkey-patch them. They have to exist to be patchable. Keeping them thin means we don't write production code that Phase 5 will have to rewrite.

## Risks / Trade-offs

- **Risk:** Integer division in loyalty accrual truncates — a customer spending 12345 at 5% gets 617 not 617.25. → **Mitigation:** matches PDD §6.1 test `617 = floor(12345 * 5 / 100)` and matches how prices-in-kopecks work throughout the system.
- **Risk:** Test 2.11 (`send_task` failure rolls back) assumes SQLite in-memory supports rollback; SQLAlchemy sessions do, so this works. In production PostgreSQL it works identically. Mitigation: none needed.
- **Risk:** The READY type-check (D2) doesn't cover a hypothetical "pickup order where courier attempts IN_DELIVERY" — but the role gate already blocks it (courier is not in `{barista, admin}` for (READY, COMPLETED), and the type check blocks pickup from going IN_DELIVERY). Both guards are layered.
- **Risk:** If Phase 5 later wires `send_order_notification` to make a synchronous HTTP call instead of an in-process `celery_app.send_task`, the ordering in D6 becomes a latency issue. → **Mitigation:** keep notification async (task enqueue) — documented as a design invariant.

## Migration Plan

No database schema changes. No data backfill. No rollback plan beyond "revert the commit" — all three new service files + router are additive, and the only mutation to `rbac_matrix.py` is adding two new route entries.

## Atomicity Analysis (INV-004)

`cancel_order` MUST produce exactly one of these two end states:

**State A (success):** order.status=CANCELLED, promocode.current_uses decremented, promocode_usages row removed, one new LoyaltyTransaction(REVERSAL) row, loyalty_account.balance updated, refund task enqueued, notification sent.

**State B (failure):** every DB row identical to pre-call state, NO refund task enqueued, NO notification call visible (mock call_count == 0) OR visible-and-failed (test 2.12 patches notification to raise — in that case its mock was called once, which is fine, the test only asserts `send_task` was not invoked).

The ordering in D6 — DB writes → notification → send_task → commit — delivers both:
- DB is inside the session and rolls back if ANY step raises before commit.
- Notification happens inside the session; if it raises, rollback happens and `send_task` was never reached.
- `send_task` is the last step before commit; if it raises, rollback happens on session close.
- If commit itself raises (rare): rollback happens; the only orphan effect is the enqueued refund task, which the payment-worker idempotency-checks against YuKassa payment status before acting (documented trade-off).

No partial state is observable to another transaction because commit is the only DB-visible event.

## Open Questions

None at authoring time. All 84 RED tests have a deterministic happy path under this design.
