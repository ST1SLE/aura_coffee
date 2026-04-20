## Why

Admin needs CRUD over promocodes to run marketing campaigns (PDD §6.6, §7.1 Phase 5 item 1). Currently the only promocode code path is the customer-side `validate_promocode` at checkout — there is no way to create, list, edit, activate, or deactivate a code. Without it, the Phase 5 admin UI cannot be built and the marketing flow is blocked. INV-010 forbids reusing customer surfaces for staff, and INV-011 forbids a DB-level `status` column — the lifecycle is `is_active` + computed state derived from timestamps and counters. A dedicated `/api/v1/admin/promocodes/*` prefix scoped to ADMIN-only (not BARISTA, not COURIER) locks both invariants at the router boundary.

This is the RED phase of the two-change model — failing tests lock the contract before any implementation lands.

MVP phase: **Phase 5 — Loyalty & Promocodes** (PDD §7.1 item 1).

## What Changes

- Introduce failing tests for a new admin-scoped service API in `core_api.services.admin_promocodes`:
  - `compute_state(promo, now)` — pure function returning `Literal['inactive','active','expired','exhausted']` per PDD §6.6 state derivation.
  - `create_promocode`, `list_promocodes`, `get_promocode`, `update_promocode`, `activate`, `deactivate` — CRUD + lifecycle transitions, all write-ops transactional (INV-004).
- Introduce failing router tests for the six endpoints under `/api/v1/admin/promocodes`:
  - `POST /`, `GET /`, `GET /{id}`, `PATCH /{id}`, `POST /{id}/activate`, `POST /{id}/deactivate`.
  - ADMIN → 200/201/204; BARISTA + COURIER + CUSTOMER → 403 (INV-010); no token → 401.
  - POST validation: `code` pattern `^[A-Z0-9_-]+$`, auto-UPPER, unique (409 on collision), `discount_value` bounds per `discount_type`, date order, `max_uses_per_user ≤ max_uses`.
  - GET list: `state` filter over computed state, `code` prefix match (case-insensitive), pagination (default 20, max 100), sort `created_at DESC`.
  - PATCH edit-rules: `current_uses=0` → all fields editable; `current_uses>0` → only `valid_until`, `max_uses`, `max_uses_per_user`, `min_order_amount`, `is_active`; locked-field attempts → 422 `"field_locked_after_use"`.
  - Activate preconditions: `valid_until` required → 422; computed `expired` → 409; computed `exhausted` → 409; happy path sets `is_active=true`.
  - Deactivate: computed `expired` → 409; happy path sets `is_active=false`.
- Introduce failing rbac_matrix tests asserting all six rows map to `{ADMIN}` and none appear in `PUBLIC_ROUTES`.
- Introduce failing Pydantic schema tests for `PromocodeCreate`, `PromocodeUpdate`, `PromocodeResponse`, `PromocodeListResponse`, `PromocodeState` in `schemas.promocode`.
- No router, service, schema, or `main.py` wiring lands in this change. Every new test MUST fail because the implementation is absent. `services/validators/promocode.py`, `pricing.py`, `checkout.py` are NOT modified.

## Capabilities

### New Capabilities
- `admin-promocodes-api`: ADMIN-only CRUD over promocodes — create, paginated listing with computed-state filter, detail read, partial edit with post-use field lock, activate/deactivate lifecycle transitions. Archive-style (no DELETE). State is computed, not stored (INV-011).

### Modified Capabilities
<!-- None — RED phase only introduces a new capability. -->

## Non-Goals

- Implementing the routers, services, schemas, RBAC entries, or `main.py` wiring (GREEN phase).
- DELETE endpoint — archive-style per PDD §6.6 (FK `promocode_usages → promocodes` RESTRICT enforces this at the DB layer anyway).
- Adding a `status` column to the `promocodes` table — explicitly forbidden by PDD §6.6 + INV-011; state is always computed.
- Touching `services/validators/promocode.py` (checkout-side validation chain) or `pricing.py` / `checkout.py` (promocode-race-fix zone).
- Loyalty `ADMIN_ADJUSTMENT` transaction type — belongs to Phase 6 users-admin.
- Schema migrations — the `promocodes` + `promocode_usages` tables already exist (0005_phase3_schema.py).
- Admin UI — lands in a separate web-admin change.
- Promocode usage reporting / analytics — out of scope for CRUD.

## Impact

- **Code**: adds new test modules `services/core-api/tests/test_admin_promocodes_crud.py`, `test_admin_promocodes_list.py`, `test_admin_promocodes_edit_rules.py`, `test_admin_promocodes_lifecycle.py`, `test_admin_promocodes_rbac.py`. May extend `tests/_factories/` with a `make_promocode(**overrides)` helper seeding orders across the four computed states.
- **APIs**: locks the contract for six endpoints under `/api/v1/admin/promocodes` (no implementation yet).
- **Dependencies**: reuses `shared.models.promocode.Promocode`, `shared.models.promocode_usage.PromocodeUsage`, `shared.enums.PromocodeDiscountType`. No new third-party packages. No new ORM columns — `current_uses` already exists (migration 0005).
- **Inviolable rules touched**: INV-010 (role isolation — ADMIN-only, BARISTA explicitly denied), INV-011 (no status column — state computed), INV-004 (all write-ops in single transaction — asserted in service tests by pinning session.commit behavior).
- **Systems**: PostgreSQL (SELECT/INSERT/UPDATE over `promocodes`). No Redis, no migrations, no Celery.
