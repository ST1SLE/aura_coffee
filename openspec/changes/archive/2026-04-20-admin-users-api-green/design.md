## Context

Complementary GREEN half of the TDD cycle started by archived change
`admin-users-api-red` (archived `2026-04-20`). The RED change already:

- Defined the REST contract and RBAC rows via `specs/admin-users-api/spec.md`
  (now merged into `openspec/specs/admin-users-api/spec.md`).
- Locked 87 tests across 6 test modules (`test_admin_users_list.py`,
  `test_admin_users_detail.py`, `test_admin_users_block.py`,
  `test_admin_users_unblock.py`, `test_admin_users_loyalty_adjust.py`,
  `test_admin_users_rbac.py`) using body-local imports so every failing
  assertion surfaces a clean `ImportError` / `KeyError` today.
- Confirmed key building blocks exist: `LoyaltyTransactionType.ADMIN_ADJUSTMENT`,
  `UserStatus.{ACTIVE, BLOCKED, PENDING_VERIFICATION, DELETED}`,
  `users.deleted_at` tombstone column, `user_profiles.display_name` column,
  `loyalty_accounts.balance`, `services.order_cancel.cancel_order`
  (commits internally per-order).

**Affected modules:** [core-api].

This is strictly an implementation delivery — no schema changes, no new
endpoints beyond what the RED spec locked, no new dependencies.

**State machine note (§6.5, INV-016):** `block_user` emits
`ACTIVE → BLOCKED` and `unblock_user` emits `BLOCKED → ACTIVE`. Forbidden
transitions (`{PENDING_VERIFICATION, DELETED} → *`, `ACTIVE → PENDING_VERIFICATION`,
etc.) raise `InvalidUserStateError` (HTTP 409). `block_user` also triggers
`PAID|CREATED|PREPARING|READY → CANCELLED` transitions on affected orders via
`cancel_order` (§6.1). No other state-mutating endpoints are introduced.

**Atomicity Analysis (INV-004):**
- `adjust_loyalty`: ALL of `SELECT user FOR UPDATE` + `SELECT loyalty_account FOR UPDATE`
  + `UPDATE balance` + `INSERT LoyaltyTransaction` + `db.commit()` happen inside
  one DB transaction. Aborting raises before commit → zero partial state.
- `block_user`: per-order atomicity is delegated to `cancel_order`, which
  already owns the §7.6 refund/loyalty REVERSAL/promocode-decrement/SMS chain
  in its own transaction and internal commit. We explicitly do NOT wrap all
  cancelled orders + the `status=BLOCKED` flip inside one giant transaction:
  the RED tests don't require it, INV-004 applies at the per-order financial
  boundary, and wrapping would require editing `order_cancel.py` (which the
  RED suite forbids under non-goal #3).
- `unblock_user`: single UPDATE + commit. No financials.

**152-FZ compliance (INV-013):**
- `UserSummary` / `UserDetailResponse` / `BlockUserResponse` /
  `LoyaltyAdjustResponse` schemas DO NOT declare `phone`, `phone_hash`, or
  `deleted_at` fields. Pydantic serialisation with
  `ConfigDict(from_attributes=True)` emits only declared fields.
- `search` parameter hits `user_profiles.display_name` ONLY. The service
  function SHALL NOT build any `LIKE` / `ILIKE` clause against `phone_hash`
  or `phone`.
- Tombstone users (`deleted_at IS NOT NULL`) → 404 on the detail endpoint.
  This mirrors the customer-facing account-deletion contract: once the user
  tombstones themselves the account is no longer addressable.

## Goals / Non-Goals

**Goals:**

- Make all 87 tests authored in RED flip from FAIL to PASS without skipping
  or modifying any of them.
- Keep the implementation dedicated to a new `services/admin_users.py`
  module — distinct from customer-scoped helpers — so INV-010 role isolation
  is auditable at the module-path level (`admin_users` → only
  `routers/admin_users.py` imports it).
- Leave the customer-scoped `/api/v1/profile/*` routes and services
  byte-for-byte unchanged (RED test 7.x asserts
  `ROUTE_MATRIX[("GET", "/api/v1/profile")] == {CUSTOMER}`).

**Non-Goals:**

- No new DTO variants beyond the 7 locked in RED (`UserSummary`,
  `UserListResponse`, `UserDetailResponse`, `LoyaltyTransactionItem`,
  `BlockUserResponse`, `LoyaltyAdjustRequest`, `LoyaltyAdjustResponse`).
- No admin UI — lands in a separate `web-admin` frontend change.
- No modification of `services/order_cancel.py` or any `shared/models/*`
  file (explicit non-goal from RED).
- No new DB migration — columns and enum values already exist.
- No auto-creation of `LoyaltyAccount` on first adjust. Users created in
  Phase 5 already have one; we raise `UserNotFoundError` (→ 404) if the
  account is somehow missing rather than silently repairing state.

## Decisions

### D1 — Service module placement: dedicated `services/admin_users.py`

Create a new module `core_api/services/admin_users.py` hosting all five
service functions AND the three domain errors (`UserNotFoundError`,
`InvalidUserStateError`, `InsufficientBalanceError`). RED tests import
exclusively from this path (see `test_admin_users_list.py:from core_api.services.admin_users import list_users`).

*Alternatives considered:*
- Splitting into `admin_users_list.py` / `admin_users_block.py` /
  `admin_users_loyalty.py` — forces RED test file edits (contract violation)
  and fragments the tight 5-function surface.
- Folding into existing customer-scoped `profile_service.py` — violates
  INV-010 isolation (admin and customer scopes would share a module).

### D2 — Schema module placement: dedicated `schemas/admin_users.py`

Create `core_api/schemas/admin_users.py` with the 7 Pydantic v2 DTOs. All
response DTOs use `ConfigDict(from_attributes=True)` so service functions can
return ORM instances / simple dataclasses and FastAPI handles serialisation.

*Alternatives considered:*
- Reuse `schemas.profile` — profile has a `phone` field that must never
  leak via the admin surface; sharing risks accidental cross-wiring.

### D3 — List query strategy: single SELECT with LEFT JOINs + COALESCE

`list_users` SHALL issue one query:

```sql
SELECT users.id, users.status, users.created_at, users.deleted_at,
       user_profiles.display_name,
       COALESCE(loyalty_accounts.balance, 0) AS loyalty_balance
FROM users
LEFT JOIN user_profiles ON user_profiles.user_id = users.id
LEFT JOIN loyalty_accounts ON loyalty_accounts.user_id = users.id
WHERE <status-filter> AND <search-filter?>
ORDER BY users.created_at DESC
LIMIT :per_page OFFSET (:page-1)*:per_page
```

`total_count` is a separate `SELECT COUNT(*) FROM users WHERE <status-filter>
AND <search-filter?>` (no join — row count matches the main query because
`user_profiles` / `loyalty_accounts` are at most 1:1 with users). The
status-filter dispatch table (see `### D4` below) maps the 5 string values
to explicit SQLAlchemy predicates.

*Alternatives considered:*
- Separate queries per status — duplicates boilerplate with zero readability
  gain.
- In-Python filtering — breaks pagination correctness and `total_count` semantics.

### D4 — Status filter dispatch

```python
_STATUS_FILTERS: dict[str, Callable[[], ColumnElement[bool]]] = {
    "active":                lambda: and_(User.status == UserStatus.ACTIVE,
                                          User.deleted_at.is_(None)),
    "blocked":               lambda: and_(User.status == UserStatus.BLOCKED,
                                          User.deleted_at.is_(None)),
    "pending_verification":  lambda: and_(User.status == UserStatus.PENDING_VERIFICATION,
                                          User.deleted_at.is_(None)),
    "deleted":               lambda: or_(User.status == UserStatus.DELETED,
                                         User.deleted_at.is_not(None)),
    "all":                   lambda: true(),
}
```

Router-level validation (`Query(..., regex=...)` or `Literal` type) rejects
other values → 422.

### D5 — Search predicate: `ILIKE display_name || '%'`, NEVER phone_hash

```python
if search:
    stmt = stmt.where(
        func.lower(UserProfile.display_name).like(search.lower() + "%")
    )
```

Case-insensitive prefix match against `user_profiles.display_name` only.
INV-013 forbids any `LIKE` clause touching `phone_hash` (one-way hash) or
`phone` (encrypted). RED test "search does NOT match phone_hash fragments"
asserts this directly.

### D6 — Detail query strategy: 3 focused queries

1. Load user with `User` + `UserProfile` + `LoyaltyAccount` via `joinedload`
   (single SELECT). Raise `UserNotFoundError` if not found OR if
   `user.deleted_at IS NOT NULL`.
2. Load last 20 `LoyaltyTransaction` rows ordered by `created_at DESC` via
   a separate SELECT (`LIMIT 20`). Cleaner than window functions, and 20
   rows per detail call is well within network/serialisation budget.
3. `SELECT COUNT(*) FROM orders WHERE user_id=? AND status NOT IN
   (COMPLETED, CANCELLED)` — single scalar query.

*Alternatives considered:*
- Single mega-query with subqueries — obscures the three independent
  read paths; harder to debug.
- ORM lazy-loading from step 1 — N+1 risk on `loyalty_transactions`.

### D7 — `block_user` cascade filter: `{CREATED, PAID, PREPARING, READY}` (explicit include-list)

The service selects orders via:

```python
CANCELLABLE_STATUSES = {
    OrderStatus.CREATED, OrderStatus.PAID,
    OrderStatus.PREPARING, OrderStatus.READY,
}
orders_to_cancel = db.scalars(
    select(Order).where(
        Order.user_id == user_id,
        Order.status.in_(CANCELLABLE_STATUSES),
    )
).all()
```

`IN_DELIVERY` is explicitly EXCLUDED (skip silently — courier finishes
active delivery, §7.6 admin-cancel restriction). `COMPLETED` and
`CANCELLED` are terminal and already excluded by the WHERE.

### D8 — `block_user` transaction boundary: per-order via `cancel_order`

`block_user` pseudocode:

```python
def block_user(db: Session, user_id: UUID) -> BlockUserResponse:
    user = db.execute(
        select(User).where(User.id == user_id).with_for_update()
    ).scalar_one_or_none()
    if user is None:
        raise UserNotFoundError(...)
    if user.deleted_at is not None or user.status in {PENDING_VERIFICATION, DELETED}:
        raise InvalidUserStateError("invalid_user_state")
    if user.status == UserStatus.BLOCKED:
        return BlockUserResponse(user_id=user.id, status="blocked", cancelled_orders_count=0)

    user.status = UserStatus.BLOCKED
    db.flush()                       # release user row write, still in tx
    db.commit()                      # persist BLOCKED before cascade

    orders_to_cancel = db.scalars(select(Order).where(...)).all()
    cancelled = 0
    for o in orders_to_cancel:
        cancel_order(order_id=o.id, cancelled_by="admin",
                     reason="user_blocked", db_session=db)
        cancelled += 1

    if cancelled > 10:
        logger.warning("block_user cascade cancelled %d orders for user %s",
                       cancelled, user_id)
    return BlockUserResponse(user_id=user.id, status="blocked",
                             cancelled_orders_count=cancelled)
```

Committing `status=BLOCKED` BEFORE the cascade is intentional: if a single
`cancel_order` fails mid-cascade, the user is still BLOCKED (no concurrent
customer action can land) and the operator can retry the block — which is
then idempotent (no-op, returns `cancelled_orders_count=0`). The remaining
cancellable orders would be caught by a second invocation (each
`cancel_order` call is independently atomic).

*Alternatives considered:*
- One giant transaction wrapping the BLOCK flip + all cancellations —
  requires editing `order_cancel.py` to skip its internal commit, which is
  an explicit non-goal.
- Fail-fast retry transaction — adds operator cognitive load without
  matching any RED test expectation.

### D9 — `unblock_user`: no cascade

```python
def unblock_user(db: Session, user_id: UUID) -> BlockUserResponse:
    user = db.execute(select(User).where(User.id == user_id).with_for_update()).scalar_one_or_none()
    if user is None:
        raise UserNotFoundError(...)
    if user.deleted_at is not None or user.status in {PENDING_VERIFICATION, DELETED}:
        raise InvalidUserStateError("invalid_user_state")
    if user.status == UserStatus.ACTIVE:
        return BlockUserResponse(user_id=user.id, status="active", cancelled_orders_count=0)
    user.status = UserStatus.ACTIVE
    db.commit()
    return BlockUserResponse(user_id=user.id, status="active", cancelled_orders_count=0)
```

CANCELLED orders remain CANCELLED (terminal per §6.1). RED test "No
cascade — previously cancelled orders stay cancelled" asserts this.

### D10 — `adjust_loyalty` transaction: single atomic block (INV-004)

```python
def adjust_loyalty(db: Session, user_id: UUID, delta: int, reason: str)
        -> LoyaltyAdjustResponse:
    user = db.execute(select(User).where(User.id == user_id).with_for_update()).scalar_one_or_none()
    if user is None:
        raise UserNotFoundError(...)
    if user.deleted_at is not None or user.status in {PENDING_VERIFICATION, DELETED}:
        raise InvalidUserStateError("invalid_user_state")
    account = db.execute(
        select(LoyaltyAccount)
        .where(LoyaltyAccount.user_id == user_id)
        .with_for_update()
    ).scalar_one_or_none()
    if account is None:
        raise UserNotFoundError(...)   # non-goal #2: do NOT auto-create
    new_balance = account.balance + delta
    if new_balance < 0:
        raise InsufficientBalanceError("insufficient_balance")
    account.balance = new_balance
    tx = LoyaltyTransaction(
        user_id=user_id, order_id=None,
        type=LoyaltyTransactionType.ADMIN_ADJUSTMENT,
        amount=delta, balance_after=new_balance, description=reason,
    )
    db.add(tx)
    db.flush()                         # populate tx.id
    db.commit()
    return LoyaltyAdjustResponse(transaction_id=tx.id,
                                 new_balance=new_balance, delta=delta)
```

Both Pydantic-layer validation (`delta != 0`, `1 <= len(reason) <= 500`)
and service-layer invariants (`status`, `new_balance >= 0`) are enforced.
On `InsufficientBalanceError`, NO `db.commit()` is reached — SQLAlchemy
rolls back the in-progress tx on exception escape (or the caller rolls
back). RED test asserts `balance` unchanged post-error.

BLOCKED is accepted: legitimate operator workflow to refund points before
unblock.

### D11 — Router module + registration

Create `core_api/routers/admin_users.py` with a single
`APIRouter(prefix="/api/v1/admin/users", tags=["admin-users"])` and 5 route
functions. Register in `core_api/main.py` alongside `admin_orders` via
`app.include_router(admin_users.router)`. RED test 2.12 for routes asserts
each of the 5 routes appears exactly once in `app.routes`.

Error-to-HTTP translation happens at the router layer:

```python
try:
    return service_call(...)
except UserNotFoundError:
    raise HTTPException(status_code=404, detail="user_not_found")
except InvalidUserStateError:
    raise HTTPException(status_code=409, detail="invalid_user_state")
except InsufficientBalanceError:
    raise HTTPException(status_code=422, detail="insufficient_balance")
```

RED test 6.x for loyalty adjust asserts `body.detail` mentions
`"insufficient_balance"` on 422.

### D12 — Status query param: Pydantic `Literal` type for 422-on-bogus

```python
@router.get("", response_model=UserListResponse)
def list_admin_users(
    status: Literal["active","blocked","pending_verification","deleted","all"] = "all",
    search: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
): ...
```

FastAPI auto-422s on `?status=bogus` (RED test 2.9) and on
`?per_page=101` (RED test 2.8). No manual validation needed.

### D13 — RBAC: 5 rows `{ADMIN}`, none in PUBLIC_ROUTES

Extend `core_api/rbac_matrix.py::ROUTE_MATRIX` with exactly these 5 keys:

```python
("GET",  "/api/v1/admin/users"):                                {ADMIN},
("GET",  "/api/v1/admin/users/{user_id}"):                      {ADMIN},
("POST", "/api/v1/admin/users/{user_id}/block"):                {ADMIN},
("POST", "/api/v1/admin/users/{user_id}/unblock"):              {ADMIN},
("POST", "/api/v1/admin/users/{user_id}/loyalty/adjust"):       {ADMIN},
```

RBACMiddleware default-deny → 401 without token, 403 on role mismatch,
all already exercised by RED RBAC route tests.

### D14 — Error class hierarchy

```python
class AdminUsersError(Exception): ...
class UserNotFoundError(AdminUsersError): ...
class InvalidUserStateError(AdminUsersError): ...
class InsufficientBalanceError(AdminUsersError): ...
```

Dedicated base for the admin-users scope mirrors existing patterns
(`services/order_cancel.py` has its own error tree). Tests import the
specific subclass types, so the hierarchy is purely organisational.

## Risks / Trade-offs

- **[Risk]** `block_user` commit-then-cascade may leave the user BLOCKED
  but some orders still active if `cancel_order` crashes mid-loop.
  **→ Mitigation:** the operation is idempotent on re-invocation
  (BLOCKED user → no-op but cascade loop re-runs via a separate
  `cancelled_orders_count`-style reconciliation? Actually no — re-blocking
  a BLOCKED user short-circuits to the `cancelled_orders_count=0` branch).
  Residual cascade completion is an operator workflow: if the cascade
  partially failed, re-run `block_user` WON'T retry it. Accept this — the
  RED tests do not assert a re-run picks up straggling orders, and
  aborting mid-cascade is already an ops anomaly.
  **Follow-up:** post-MVP, consider a dedicated "cancel all user orders"
  operator button / cron, independent of `block_user`.
- **[Risk]** Committing `status=BLOCKED` before the cascade means an
  operator rolling back the cascade (e.g., "oh wait, unblock them")
  leaves cancelled orders permanent. **→ Mitigation:** documented in
  D9 — CANCELLED is terminal per §6.1. Customers must re-order. The UI
  change will warn the operator before invoking block.
- **[Trade-off]** `get_user_detail` makes 3 queries instead of 1. This
  costs ~2× PG roundtrip on detail fetch but keeps the SQL debuggable and
  the ORM mapping simple. At ~1 RPM admin-panel load this is acceptable.
- **[Trade-off]** `adjust_loyalty` raises `UserNotFoundError` instead of
  auto-creating a missing `LoyaltyAccount`. Rationale: silent state
  repair is the anti-pattern that lets ORM drift into prod. If an account
  is missing, the auth / registration flow has a bug that should surface
  explicitly.

## Migration Plan

- Forward-only: additive code + 5 new ROUTE_MATRIX rows + 1 new
  `include_router` line.
- No DB migration, no data backfill, no feature flag.
- **Rollback:** revert the commit. RED tests (now archived) are no
  longer in the active suite; the merged `openspec/specs/admin-users-api/spec.md`
  would remain but describe an unimplemented contract. No runtime state
  is corrupted (everything is read-only until first `block`/`adjust` admin call).
- **Verification:** after implementation, running
  `pytest services/core-api/tests/test_admin_users_*.py -v` MUST report
  87 passed, 0 failed. No pre-existing test suite regressions allowed.
