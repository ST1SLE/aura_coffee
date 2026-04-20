## Why

The current promocode quota enforcement is a textbook TOCTOU race. `core_api.services.validators.promocode.validate_promocode` runs a plain `SELECT` to check `current_uses < max_uses`, then `core_api.services.checkout.create_order` later mutates `promocode.current_uses` via an ORM attribute assignment (`promocode.current_uses = ... + 1`). Two concurrent checkouts against a `max_uses=1` promocode both pass validation, both increment the counter, and the database ends with `current_uses=2`. INV-011 ("один промокод на заказ — квота реально не ограничена") is silently violated, and the symmetric `_return_promocode` in `core_api.services.order_cancel` can drive `current_uses` below zero if two cancellations race.

PDD §6.6 ("Атомарный инкремент `current_uses`"), §7.2 step 2, and §7.6 step 2 require a conditional UPDATE that enforces the quota predicate inside the UPDATE's `WHERE` clause, so that the DB — not application code — is the single source of truth for the remaining-uses invariant. The pre-transaction validator stays (fast 422 for obviously invalid codes), but it is advisory; the atomic UPDATE is the load-bearing gate.

This is the RED phase of the two-change model: the failing tests lock the race semantics before the implementation lands.

MVP phase: **Phase 3 — Order Pricing & Cancel** (PDD §7.1).

## What Changes

- Introduce failing tests that lock the atomic-increment contract in `core_api.services.checkout.create_order`:
  - A race-simulation test that pre-advances `promocodes.current_uses` to `max_uses` via a raw SQL UPDATE after validator has already read the pre-race state, then invokes checkout. The checkout SHALL raise `PromocodeValidationError("Global quota exhausted")` — the exact same exception/message the pre-transaction validator raises — and SHALL NOT cause `current_uses` to exceed `max_uses`.
  - A positive test: when `max_uses=None` (unlimited), the conditional UPDATE SHALL still succeed and increment `current_uses`.
  - A positive test: when `max_uses > current_uses`, the conditional UPDATE SHALL match exactly one row and bump `current_uses` by 1.
- Introduce failing tests that lock the atomic-decrement contract in `core_api.services.order_cancel._return_promocode`:
  - A "double cancel" race test: two cancellations on the same order SHALL NOT decrement `current_uses` below zero; after the race, `current_uses` SHALL be `max(pre_state - 1, 0)`.
- No service implementation lands in this change. Every new test MUST fail because the implementation still uses the racy ORM-mutation path. The validator at `core_api.services.validators.promocode` is NOT modified — it remains the UX pre-check.

## Capabilities

### Modified Capabilities
- `order-checkout`: Add atomic conditional UPDATE for `promocodes.current_uses` with quota predicate inside the `WHERE`, raising the same `PromocodeValidationError("Global quota exhausted")` on zero rowcount.
- `order-cancel`: Replace ORM attribute decrement with a conditional UPDATE guarded by `current_uses > 0`, preventing double-cancel underflow.

## Non-Goals

- Changing `core_api.services.validators.promocode` — it stays as the UX pre-check.
- Introducing `SELECT ... FOR UPDATE` or advisory locks — conditional UPDATE is sufficient and cheaper.
- Schema changes or new indexes.
- Changing the external HTTP error contract — the client still sees HTTP 422 with message "Global quota exhausted" on race loss.
- Per-user quota race hardening (`PromocodeUsage` uniqueness) — separate capability.
- Frontend work.

## Impact

- **Code**: adds new test modules `services/core-api/tests/test_promocode_atomic_increment.py` and `services/core-api/tests/test_order_cancel_atomic_decrement.py`. No production code is touched in RED.
- **APIs**: locks the race-loss behaviour of `checkout.create_order` and `order_cancel.cancel_order`. No new public symbols.
- **Dependencies**: reuses `shared.models.Promocode`, `shared.models.PromocodeUsage`, `core_api.services.validators.exceptions.PromocodeValidationError`. No new third-party packages.
- **Inviolable rules touched**: INV-004 (atomicity), INV-011 (quota honoured).
- **Systems**: PostgreSQL (single conditional UPDATE per checkout/cancel). No Redis, no migrations.
