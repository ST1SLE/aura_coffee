## Why

The RED phase (archived as `2026-04-20-admin-promocodes-api-red`) locked the contract for admin-scoped promocode CRUD with 52 failing tests across service, schema, router, and RBAC layers. Nothing is wired up yet. This GREEN change turns the failing suite green by implementing the minimum code needed: service module, schema module, router module, RBAC matrix rows, and `main.py` wiring. No new contract is introduced; no new tests are added.

MVP phase: **Phase 5 — Loyalty & Promocodes** (PDD §7.1 item 1).

## What Changes

- Create `services/core-api/src/core_api/services/admin_promocodes.py` with:
  - `compute_state(promo, now)` — pure state-derivation function per PDD §6.6.
  - `create_promocode`, `list_promocodes`, `get_promocode`, `update_promocode`, `activate`, `deactivate` — CRUD + lifecycle functions. Single `session.commit()` per write op (INV-004). `IntegrityError` on duplicate code is translated into a domain error.
  - Internal `FieldLockedAfterUseError(field)` domain exception raised by `update_promocode`.
  - Internal `PromocodeStateConflictError(reason)` raised by activate/deactivate guards.
- Create `services/core-api/src/core_api/schemas/promocode.py` with Pydantic v2 models:
  - `PromocodeState = Literal['inactive','active','expired','exhausted']`
  - `PromocodeCreate` with field validators: UPPER + regex on `code`, percent ≤ 100, positive `discount_value`, `valid_from < valid_until`, `max_uses_per_user ≤ max_uses`.
  - `PromocodeUpdate` (all optional) with the same cross-field invariants (applied only to fields set).
  - `PromocodeResponse` (includes computed `state`).
  - `PromocodeListResponse { items, total_count, page, per_page }`.
- Create `services/core-api/src/core_api/routers/admin_promocodes.py` with six endpoints under `APIRouter(prefix="/api/v1/admin", tags=["admin-promocodes"])`:
  - `POST /promocodes` → 201 / 422 / 409 / 403 / 401.
  - `GET /promocodes` → 200 / 422 / 403 / 401.
  - `GET /promocodes/{promocode_id}` → 200 / 404 / 403 / 401.
  - `PATCH /promocodes/{promocode_id}` → 200 / 422 (field_locked_after_use) / 404 / 403 / 401.
  - `POST /promocodes/{promocode_id}/activate` → 200 / 422 / 409 / 404 / 403 / 401.
  - `POST /promocodes/{promocode_id}/deactivate` → 200 / 409 / 404 / 403 / 401.
- Register the router in `services/core-api/src/core_api/main.py` (include alongside other admin routers).
- Add six rows to `services/core-api/src/core_api/rbac_matrix.py::ROUTE_MATRIX`, each `{ADMIN}`.
- No migrations, no changes to `services/validators/promocode.py`, no changes to checkout / pricing.

## Capabilities

### New Capabilities
<!-- None — the capability was introduced in the RED change's delta spec. GREEN does not change the contract, only implements it. -->

### Modified Capabilities
<!-- None — GREEN does not change the spec. The RED spec already describes the full contract. -->

## Non-Goals

- Adding new tests — RED locked the suite; GREEN turns it green. No new assertions, no widened coverage.
- DELETE endpoint — archive-style only (PDD §6.6).
- Admin UI — separate web-admin change.
- Loyalty `ADMIN_ADJUSTMENT` — Phase 6 users-admin.
- Analytics / reporting over promocodes — out of scope.
- Touching `services/validators/promocode.py`, `pricing.py`, `checkout.py`.
- Schema migrations.

## Impact

- **Code**: three new modules under `services/core-api/src/core_api/` (service, schema, router), plus `main.py` + `rbac_matrix.py` edits. Zero test changes — the RED suite is the acceptance criterion.
- **APIs**: six new endpoints under `/api/v1/admin/promocodes`, returning existing `PromocodeResponse`-shaped DTOs.
- **Dependencies**: reuses `shared.models.promocode.Promocode`, `shared.models.promocode_usage.PromocodeUsage` (indirectly, through the checkout-side validator — not touched here), `shared.enums.PromocodeDiscountType`. No new third-party packages.
- **Inviolable rules touched**: INV-010 (RBAC matrix rows `{ADMIN}`), INV-011 (no status column — state is computed), INV-004 (one commit per write op).
- **Systems**: PostgreSQL only. No Redis, no migrations, no Celery, no external APIs.
