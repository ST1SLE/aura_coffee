## Context

RED delivered the failing tests. The pre-existing `create_order` bumps `promocode.current_uses` through ORM attribute mutation after the validator returns — a classic TOCTOU window. `_return_promocode` symmetrically decrements through ORM mutation with a Python-side `> 0` guard that does not survive concurrent stale reads.

GREEN implements the conditional UPDATEs prescribed by PDD §6.6.

**Affected modules:** `[core-api]`.

## Goals / Non-Goals

**Goals:**
- Replace the two ORM mutations with conditional UPDATEs using SQLAlchemy Core `update()`.
- Preserve the external HTTP 422 contract for race loss (same `PromocodeValidationError("Global quota exhausted")` message as the validator).
- Keep `PromocodeUsage` insertion tied to the winning UPDATE: insert only after `rowcount == 1`.
- Leave validator unchanged.

**Non-Goals:**
- Locking primitives, isolation changes, schema work.

## Decisions

- **UPDATE order vs INSERT order in `create_order`.** Increment UPDATE fires BEFORE `PromocodeUsage` INSERT. If the UPDATE returns `rowcount == 0`, the INSERT is skipped and `PromocodeValidationError` is raised; the outer transaction rolls back the entire `Order` / `OrderItem` / `Payment` / `LoyaltyTransaction` graph created moments earlier. This is consistent with "the checkout transaction rolls back as a whole" (INV-004). The alternative — INSERT usage, then UPDATE — would need compensating logic.
- **`current_uses = current_uses + 1` (self-reference).** Using the column self-reference in `.values()` ensures the DB — not the stale Python snapshot — produces the new value. SQLAlchemy compiles this to `UPDATE ... SET current_uses = promocodes.current_uses + 1 WHERE ...`, which Postgres evaluates atomically per row.
- **`rowcount == 0` as the race-loss signal.** Both Postgres and SQLite populate `Result.rowcount` for UPDATE correctly. No ORM refresh / re-query is needed — we trust the driver's affected-row count.
- **Decrement uses the same pattern with `current_uses > 0`.** The floor guard moves from Python to SQL. Double-cancel becomes a zero-rowcount no-op; no exception is raised (cancel is idempotent on the counter).
- **Expiring the ORM-cached Promocode after the UPDATE.** Because the update bypasses the ORM unit-of-work, any downstream read of `promocode.current_uses` via the cached instance would be stale. The existing `create_order` does not re-read the counter after the increment, so no `db.refresh(promocode)` is needed. For safety and clarity of intent, the function can leave the cache alone — the counter is never observed post-UPDATE inside this function.

## Risks / Trade-offs

- **Risk:** A future edit re-adds `promocode.current_uses = ...` after the UPDATE and double-increments. **Mitigation:** tests 1.2, 1.3, 1.4 cover "counter ends at the expected value" — any such edit trips 1.3 (ends at 44 instead of 43) or 1.4 (ends at 4 instead of 3).
- **Trade-off:** No re-query of the Promocode row after the UPDATE. The ORM instance stays with its pre-UPDATE snapshot. This is fine for `create_order` (no downstream reads) and `_return_promocode` (same).

## Migration Plan

1. Edit `checkout.py` and `order_cancel.py` to use conditional UPDATEs.
2. Re-run `test_promocode_atomic_increment.py` and `test_order_cancel_atomic_decrement.py` — every test green.
3. Re-run `test_checkout_service.py` and `test_order_cancel.py` — no regressions.
4. Archive.
