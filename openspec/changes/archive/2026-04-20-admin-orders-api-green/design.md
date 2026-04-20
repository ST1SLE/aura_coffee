## Context

Complementary GREEN half of the TDD cycle started by archived change
`admin-orders-api-red`. The RED change already:

- Defined the REST contract and RBAC rows via `specs/admin-orders-api/spec.md`.
- Locked 33 failing tests (`test_admin_orders_list.py`, `test_admin_orders_detail.py`,
  `test_admin_orders_rbac.py`) using body-local imports so each assertion surfaces a
  clean `ImportError` today.
- Confirmed key building blocks exist: migration 0005 partial index
  `orders (status) WHERE status NOT IN ('completed', 'cancelled')` (PDD §5.4),
  `Order.updated_at` column, `schemas.order_history.OrderListResponse` /
  `OrderResponse` with `user_id`.

**Affected modules:** [core-api].

This is strictly an implementation delivery — no schema changes, no new endpoints
beyond what the RED spec locked, no new dependencies.

**State machine note (§6, INV-016):** both endpoints are READ-only. They do not emit
status transitions, so no entry in the state machine table §6.1 changes. Existing
write endpoints in `order-actions-api` remain the sole mutators.

**152-FZ compliance (INV-013):** no new PII is collected, stored, or exposed. Staff
access to order detail (including `user_id`) is covered by the existing legitimate-
purpose rationale for barista/admin operations on the order queue; phone/full name
remain in `users` table and are not returned by these endpoints (schema unchanged).

## Goals / Non-Goals

**Goals:**

- Make all 33 tests authored in RED pass without skipping or modifying any of them.
- Keep the implementation colocated with related customer-scoped helpers
  (`services/order_history.py`) to minimise surface area and match the seed pattern
  already documented in the RED design (D2).
- Leave the customer-scoped contract byte-for-byte unchanged.

**Non-Goals:**

- No new schemas, no new DTO variants — reuse `OrderListResponse` / `OrderResponse`
  from `schemas.order_history`.
- No new filters (no date range, no user filter, no text search).
- No pagination metadata changes (total_count, page, per_page stay as-is).
- No new error types beyond `OrderNotFoundForStaffError` required by RED test 3.3.

## Decisions

### D1 — Placement of staff helpers: colocate in `services/order_history.py`

Add `list_orders_for_staff`, `get_order_for_staff`, and `OrderNotFoundForStaffError`
into the SAME module as `list_orders`. RED tests import from
`core_api.services.order_history` (see `test_admin_orders_list.py:47` et al.);
moving the helpers to a new module would make those imports fail at module-load time
instead of per-test.

*Alternatives considered:*
- New `services/admin_orders.py` — cleaner separation but forces RED test file edits
  (contract violation for a GREEN-only change).
- Composition via `list_orders(user_id=None, ...)` overload — violates RED design
  decision D3 (separate functions for isolation & clarity) and muddies INV-010 audit.

### D2 — Query strategy: two SQL queries gated by `status_filter` semantics

`list_orders_for_staff` MUST branch on the shape of `status_filter`:

- Case `status_filter == "active"` (default): WHERE clause uses
  `Order.status.notin_([COMPLETED, CANCELLED])`, ORDER BY `Order.created_at DESC`.
  This hits migration 0005's partial index on `status` and matches PDD §5.4 active-
  feed guidance.
- Case `status_filter ∈ OrderStatus` (e.g., `OrderStatus.COMPLETED`): WHERE clause is
  `Order.status == status_filter`. ORDER BY depends on the status:
  - Finalized (`COMPLETED`, `CANCELLED`): `Order.updated_at DESC` (freshly moved to
    the finalized state floats to the top — RED tests 2.6).
  - Non-finalized (`CREATED`, `PAID`, `PREPARING`, `READY`, `IN_DELIVERY`):
    `Order.created_at DESC` (consistent with "active" feed).

The `type_filter` is AND-combined when present (RED test 2.4): simple
`Order.type == type_filter` added to the WHERE clause in both branches.

*Alternatives considered:*
- Always sort by `created_at DESC` — fails RED test 2.6 (updated_at inversion for
  finalized) and muddies the PDD §5.4 finalized-feed semantics.
- Single giant query with `CASE` — harder to read, doesn't leverage the partial index
  as cleanly.

### D3 — Pagination: slice over `total_count`, clamp `per_page`

Mirror the existing `list_orders` pattern:

1. `total_count = session.scalar(select(func.count()).select_from(subquery))` over
   the filtered set.
2. `rows = session.scalars(query.offset((page - 1) * per_page).limit(per_page)).all()`.
3. Build `OrderListResponse(orders=..., total_count=..., page=page, per_page=per_page)`.

Validation: `per_page` MUST be constrained to `1 ≤ per_page ≤ 100` and `page ≥ 1`.
RED test 4.5 expects `422` for `per_page=150`. Implement via Pydantic `Query`
constraints on the router signature (FastAPI standard) — not via manual raise.

### D4 — Router module & registration

Create `core_api/routers/admin_orders.py` with a single `APIRouter(prefix="/api/v1/admin",
tags=["admin-orders"])`. Register in `core_api/main.py` alongside other routers, after
RBAC middleware wiring. Two route functions:

- `list_admin_orders(status: str | OrderStatus = "active", type: OrderType | None = None,
  page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100), db = Depends(get_db))`
- `get_admin_order_detail(order_id: UUID, db = Depends(get_db))`

The `status` parameter accepts the literal string `"active"` OR any `OrderStatus`
value. Use a union `OrderStatus | Literal["active"]` or a manual coerce-in-router step
to convert `"active"` → internal sentinel. Rationale: FastAPI can serialise `"active"`
directly, and accepting `OrderStatus` members gives automatic `422` on bad values.

*Alternatives considered:*
- Two separate routes `/admin/orders/active` + `/admin/orders?status=...` — breaks the
  RED contract (which locked one route with `status=active` as the default).
- Enum extension `OrderStatusOrActive` — pollutes shared `OrderStatus`.

### D5 — RBAC wiring: two ROUTE_MATRIX rows, keep existing rows untouched

Add exactly two entries to `core_api/rbac_matrix.py::ROUTE_MATRIX`:

```python
("GET", "/api/v1/admin/orders"): {ADMIN, BARISTA},
("GET", "/api/v1/admin/orders/{order_id}"): {ADMIN, BARISTA},
```

RED test 6.5 guards that `("GET", "/api/v1/orders/{order_id}")` still allows
`CUSTOMER`. Do NOT modify `PUBLIC_ROUTES` (RED test 6.3).

### D6 — Error translation: `OrderNotFoundForStaffError → HTTPException(404)`

In the detail router, wrap the service call:

```python
try:
    return get_order_for_staff(order_id=order_id, db_session=db)
except OrderNotFoundForStaffError:
    raise HTTPException(status_code=404, detail="Order not found")
```

RED test 5.6 asserts `404` on unknown id. The distinct exception type (vs. generic
`OrderNotFoundError` from customer-scoped code) lets downstream observers
differentiate staff-lookup misses from customer-scope misses.

## Risks / Trade-offs

- **[Risk]** `OrderStatus | Literal["active"]` in the router signature could trip up
  the OpenAPI generator (discriminated unions vs. the web-admin client codegen).
  **→ Mitigation:** manually coerce — accept `status: str = "active"` and parse inside
  the route function (validate membership against `OrderStatus` + `"active"`,
  raise `422` on mismatch). This preserves a clean OpenAPI schema (`string` with enum)
  and keeps FastAPI validation idiomatic.
- **[Risk]** Sort-order switching between `created_at` and `updated_at` doubles query
  paths, so index coverage matters. **→ Mitigation:** migration 0005 already indexes
  `status`; `created_at` and `updated_at` are defaults with btree indexes via
  `server_default=now()` semantics. If any status-filtered query degrades in
  production, add a targeted index in a follow-up migration (post-MVP).
- **[Trade-off]** Staff ignore the existing `list_orders(user_id=...)` ownership
  check by design — any implementation bug that reintroduces the filter would break
  INV-010 silently (admin sees only their own orders). **→ Mitigation:** RED test 4.9
  ("admin sees multiple users") already guards this.

## Migration Plan

- Forward-only: additive code + two new ROUTE_MATRIX rows.
- No DB migration, no data backfill, no feature flag.
- **Rollback:** revert the commit. RED tests will then re-fail, but no runtime data
  or contract is corrupted.
