## Context

`validate_promocode` in `core_api.services.validators.promocode` runs a plain `SELECT` and compares `current_uses < max_uses` in Python. `create_order` in `core_api.services.checkout` later bumps the counter through ORM attribute mutation:

```python
promocode.current_uses = (promocode.current_uses or 0) + 1
```

Two concurrent checkouts on a `max_uses=1` promocode each see `current_uses=0` during validation, each increment to `1` in their own session, and the winning commit yields `current_uses=2`. Symmetrically, `_return_promocode` in `order_cancel` decrements via `promo.current_uses -= 1` with no floor, so two concurrent cancellations on the same order can drive the value below zero.

PDD §6.6 specifies the fix: one conditional UPDATE per state transition, with the quota predicate (`max_uses IS NULL OR current_uses < max_uses`) inside the `WHERE` clause for increment, and a `current_uses > 0` floor guard for decrement. The DB becomes the serialization point; the row the loser targets simply does not match, and `rowcount == 0` becomes the race-loss signal.

**Affected modules:** `[core-api]`.

## Goals / Non-Goals

**Goals:**
- Author failing tests that pin the atomic-increment contract of `checkout.create_order` against PDD §6.6 and §7.2 step 2.
- Author failing tests that pin the atomic-decrement contract of `order_cancel._return_promocode` against PDD §7.6 step 2.
- Keep the RED signal clean: tests MUST fail on the current racy implementation and MUST NOT fail for unrelated reasons. The validator at `core_api.services.validators.promocode` MUST NOT be touched — race-loss is tested at the checkout level, not the validator level.
- Preserve the external HTTP error contract: race loss surfaces as `PromocodeValidationError("Global quota exhausted")` — the same exception and message already raised by the validator.

**Non-Goals:**
- Writing the conditional UPDATE (GREEN phase).
- Introducing `SELECT ... FOR UPDATE`, advisory locks, or serializable isolation.
- Touching `core_api.services.validators.promocode` — it remains the UX pre-check.
- Schema or index changes.
- Per-user-quota race hardening.

## Decisions

- **Race simulation via explicit state advancement, not threading.** Tests pre-advance `promocodes.current_uses` with a raw `UPDATE` between the validator read and the checkout write. This is deterministic, runs on SQLite, and models exactly what would happen under a lost commit race — the validator's snapshot becomes stale before the increment lands. `threading.Thread` + real Postgres would be flakier, slower, and would pin us to a specific isolation level. The conditional UPDATE's correctness does not depend on concurrency primitives; it depends on the predicate being inside `WHERE`. Proving that predicate is enough.
- **Race loss surfaces as `PromocodeValidationError`.** The client must not distinguish "invalid code" from "you lost the race" — both are HTTP 422 with the existing "Global quota exhausted" message. This keeps the API contract stable and avoids leaking internal concurrency to the UI.
- **Decrement is floored at zero, not `max_uses - max_uses_per_user`.** The decrement UPDATE condition is `current_uses > 0`. Double-cancel is expected to succeed idempotently (the second call is a no-op on the counter); the rest of the cancel chain (status flip, notification, refund) is protected by the `not_cancellable_in_this_status` rights check.
- **Tests import target symbols at module level.** Unlike greenfield RED (where we pattern `importorskip` for non-existent symbols), here `create_order` and `cancel_order` already exist — so normal imports are fine. The RED signal is behavioural: tests exercise the existing code paths and assert quota invariants the current code does not uphold.
- **SQLite-compatible test fixtures.** All new tests run under the existing in-memory SQLite conftest. The conditional UPDATE that GREEN lands works identically on SQLite and Postgres (both honour `UPDATE ... WHERE ... = a + 1` atomics and populate `Result.rowcount`).

## Risks / Trade-offs

- **Risk:** SQLite and Postgres handle "predicate in WHERE" identically, but the real race (two concurrent Postgres transactions) is not exercised by any test. **Mitigation:** the race-simulation test asserts the *predicate semantics* the GREEN code depends on. If the GREEN UPDATE's `WHERE` is correct under serial execution, it is correct under concurrent MVCC — Postgres serializes row writers on the UPDATE lock. We accept that the test proves the predicate, not the concurrency primitive.
- **Risk:** A developer might accidentally "fix" the test by catching the race in the validator. **Mitigation:** the race-simulation test pre-advances state *after* the validator stub has been replaced to return a stale Promocode instance. The validator has no chance to re-observe the advanced state; only the conditional UPDATE inside the checkout transaction can stop the over-commit.
- **Risk:** The cancel test's "double-cancel" scenario is blocked today by the rights check (`not_cancellable_in_this_status` for CANCELLED). **Mitigation:** the atomic-decrement test drives `_return_promocode` directly (white-box), bypassing the rights check. This isolates the counter-floor invariant from the rest of the cancel chain.
- **Trade-off:** Choosing conditional UPDATE over `SELECT ... FOR UPDATE` trades one round-trip for a retry-free path, at the cost of losing the ability to *return* the validated row in the same statement. Since validation already provides the row and the row ID is stable, this is fine.

## Migration Plan

1. RED (this change): add the two test modules; verify every new test fails on the current code; every pre-existing test still passes.
2. GREEN (next change): replace the ORM-mutation increment in `checkout.create_order` with the conditional UPDATE (raising `PromocodeValidationError("Global quota exhausted")` on zero rowcount). Replace the ORM-mutation decrement in `order_cancel._return_promocode` with a `current_uses > 0`-guarded UPDATE. Re-run the full suite; the new tests flip to green and all existing tests continue to pass.
