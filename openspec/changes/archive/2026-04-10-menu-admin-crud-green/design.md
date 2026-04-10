## Context

Affected modules: **[core-api]**, **[shared]** (read-only — imports existing ORM models).

The menu schema (`categories`, `menu_items`, `modifiers`, `size_options`, `menu_item_modifiers`) is live from migration `0004_menu_tables` and the `menu-schema` capability. Pydantic schemas (`core_api.schemas.menu`) already cover Create/Update/Response for all four entities and even expose a computed `availability` field on `MenuItemResponse` that maps `(archived, available)` → `MenuItemAvailability` enum — we SHALL reuse these as-is, no new schema work.

`core_api.routers.menu_admin` is currently an empty router mounted at `/api/v1/admin/menu` (per `menu-router-stubs`). RBAC is enforced centrally by `core_api.middleware.rbac.RBACMiddleware`, which reads `core_api.rbac_matrix.ROUTE_MATRIX`. There is no per-endpoint `Depends(require_role(...))` fan-out for menu admin — adding entries to `ROUTE_MATRIX` is the only authorization wiring required.

The `menu_items.available` column is the INV-006 stop-list flag; `menu_items.archived` is the "permanent removal" flag. Modifiers have a single `available` flag (no archived). Size options have `available` as well, but the proposal scope calls out item- and modifier-level stop-list toggles only — size availability is only editable via the generic `PUT size` endpoint.

## Goals / Non-Goals

**Goals:**

- The `menu_admin` router SHALL expose full CRUD for categories, menu items, modifiers, and size options under `/api/v1/admin/menu/...` using the existing Pydantic schemas.
- A dedicated `PATCH .../items/{id}/availability` and `PATCH .../modifiers/{id}/availability` endpoint SHALL exist so that baristas can toggle stop-list state without the `admin` role (INV-006, INV-010).
- All write endpoints SHALL delegate to a new `core_api.services.menu_admin` module; the router SHALL contain only request/response glue (parity with `routers/auth.py` → `services/auth.py`).
- The RBAC matrix SHALL be the single source of truth for authorization on these routes; no `Depends(require_role(...))` is introduced in the router.
- Tests in `services/core-api/tests/test_menu_admin.py` SHALL cover: happy-path CRUD for each resource, 404 on missing ids, 403 for wrong roles, 401 without a token, and the stop-list toggle specifically under the `barista` role.

**Non-Goals:**

- No Alembic migration, no change to `packages/shared/src/shared/models/menu.py`.
- No endpoints under `menu_public` — read APIs for customers are handled by a later change.
- No bulk endpoints, no CSV import, no image upload, no drag-and-drop reordering (client-side can still PUT `sort_order`).
- No audit log, no soft-delete beyond the existing `menu_items.archived` flag.
- No optimistic-locking / `If-Match` headers.

## Decisions

### D1. Router URL layout

The router prefix stays `/api/v1/admin/menu` (fixed by `menu-router-stubs`). Resource sub-paths SHALL be:

```
POST   /categories              -> CategoryResponse       [admin]
GET    /categories              -> list[CategoryResponse] [admin, barista]
PUT    /categories/{id}         -> CategoryResponse       [admin]
DELETE /categories/{id}         -> 204                    [admin]

POST   /items                   -> MenuItemResponse       [admin]
GET    /items                   -> list[MenuItemResponse] [admin, barista]
GET    /items/{id}              -> MenuItemResponse       [admin, barista]
PUT    /items/{id}              -> MenuItemResponse       [admin]
DELETE /items/{id}              -> 204                    [admin]
PATCH  /items/{id}/availability -> MenuItemResponse       [admin, barista]   # stop list

POST   /modifiers               -> ModifierResponse       [admin]
GET    /modifiers               -> list[ModifierResponse] [admin, barista]
PUT    /modifiers/{id}          -> ModifierResponse       [admin]
DELETE /modifiers/{id}          -> 204                    [admin]
PATCH  /modifiers/{id}/availability -> ModifierResponse   [admin, barista]   # stop list

POST   /sizes                   -> SizeOptionResponse     [admin]
PUT    /sizes/{id}              -> SizeOptionResponse     [admin]
DELETE /sizes/{id}              -> 204                    [admin]
```

**Why `GET` exists at all on the admin router**: the admin SPA needs to list resources to render edit tables. Adding read endpoints here keeps `menu_public` uncontaminated until the customer-facing read API is designed (it will likely have a different shape — nested, flattened, cached).

**Why `sizes` has no `GET`**: sizes are always read via the parent `MenuItemResponse.size_options` field, which the existing schema already embeds.

**Alternative considered**: nest sizes under items (`POST /items/{item_id}/sizes`). Rejected — `SizeOptionCreate` already carries `menu_item_id` in the body, so a flat route matches the schema and keeps the service layer simple.

### D2. RBAC wiring via matrix only

All protection SHALL be declared in `core_api.rbac_matrix.ROUTE_MATRIX` using the exact path templates FastAPI emits (e.g. `/api/v1/admin/menu/items/{item_id}/availability`). No `Depends(require_role(...))` on the endpoint functions.

**Why**: `rbac-middleware` spec already declares the matrix as "single source of truth for route-level authorization". Splitting authorization between the matrix and per-endpoint deps creates two places to audit and two places to get wrong. This is consistent with `routers/profile.py` (no `require_role`, matrix-only).

**Alternative considered**: add `Depends(require_role("admin", "barista"))` as defence-in-depth. Rejected for now — the middleware runs on every request and the rbac-middleware test suite already covers 401/403. If the defence-in-depth argument becomes compelling, it can be added later without breaking the API contract.

Matrix additions (roles per route):

- `("POST"|"PUT"|"DELETE", /categories[/{id}])` → `{admin}`
- `("GET", /categories)` → `{admin, barista}`
- same pattern for `/items`, `/modifiers`
- `("POST"|"PUT"|"DELETE", /sizes[/{id}])` → `{admin}`
- `("PATCH", /items/{item_id}/availability)` → `{admin, barista}`
- `("PATCH", /modifiers/{modifier_id}/availability)` → `{admin, barista}`

Customers (`customer`) and couriers (`courier`) MUST get 403 on every route above. This is enforced by the matrix — any role not in the set is rejected by `RBACMiddleware`.

### D3. Availability PATCH payload

The two stop-list endpoints SHALL accept a minimal body:

```json
{ "available": false }
```

and return the full updated entity. The body SHALL be a dedicated Pydantic model `AvailabilityPatch(BaseModel): available: bool` defined in `core_api.schemas.menu` (added in this change, since it is not yet present).

**Why a dedicated payload instead of reusing `MenuItemUpdate`**: `MenuItemUpdate` allows editing price, category, description, etc. — a barista sending `{"available": false}` through it would technically be allowed by the schema but semantically wrong. A dedicated 1-field schema makes the barista capability explicit and keeps the RBAC story clean ("baristas can only hit `.../availability`").

**Note**: menu items have both `available` (stop list) and `archived` (permanent removal). The availability PATCH SHALL only touch `available`. Archiving is an admin-only action via `PUT /items/{id}` setting `archived=true`.

### D4. Service layer shape

`core_api.services.menu_admin` SHALL expose a `MenuAdminService` class (parity with `AuthService`, `ProfileService`) taking `db: Session` in `__init__`. Methods:

```
create_category / update_category / delete_category / list_categories
create_item / update_item / delete_item / list_items / get_item / set_item_availability
create_modifier / update_modifier / delete_modifier / list_modifiers / set_modifier_availability
create_size / update_size / delete_size
```

Each method SHALL:

- raise `HTTPException(404)` if the target id does not exist.
- raise `HTTPException(409)` on FK violations surfaced by SQLAlchemy (`IntegrityError`) — e.g. deleting a category that still has items (the DB uses `ON DELETE RESTRICT`, per `menu-schema`).
- commit the transaction inside the method and return a refreshed ORM instance suitable for Pydantic `from_attributes=True` conversion.

**Alternative considered**: separate service module per entity (`categories.py`, `items.py`, …). Rejected — the total surface is ~15 small methods and splitting would create four near-empty files. Keep them in one module until the file exceeds ~300 lines.

### D5. Ordering / sort_order

`sort_order` is a plain integer column already present on all four entities. This change does NOT introduce a reorder endpoint; clients SHALL set `sort_order` via the generic PUT. Admin SPA is responsible for computing new values when rearranging rows.

### D6. Validation ownership

Pydantic handles: non-negative prices (`PriceKopecks = Annotated[int, Field(ge=0)]`), required fields, enum values. The DB handles: FK restrict (`ON DELETE RESTRICT` on `categories`, `menu_items`), `CHECK (base_price >= 0)`. The service layer handles: 404s and translating `IntegrityError` → 409.

### D7. State-machine reference

This change mutates menu entities, not order/payment state. PDD §6 state machines are not touched. The only "state-ish" behaviour is the stop-list toggle, which is a single boolean flag with two transitions (`true ↔ false`) and no preconditions. INV-016 does not apply.

## Risks / Trade-offs

- **[Risk]** A barista with the `availability` endpoint could mass-stop-list every item and break service → **Mitigation**: out-of-scope for code; handled operationally (logging). A future audit-log change can add traceability; we intentionally defer (Non-Goal).
- **[Risk]** The admin SPA is not yet built, so the contract will only be exercised by tests and curl until Phase 6 UI lands → **Mitigation**: tests in `test_menu_admin.py` are the acceptance harness; the OpenAPI schema is stable enough for API-client codegen.
- **[Risk]** `IntegrityError → 409` mapping can leak DB error messages → **Mitigation**: service raises `HTTPException(409, detail="category has items")` with a fixed string; the underlying `IntegrityError` is caught and discarded from the response body.
- **[Trade-off]** Using the matrix-only authorization means a developer can add a new endpoint and forget to register it. The rbac-middleware default is deny-by-default for authenticated routes (missing entry → 403), so the failure mode is "nobody can call it" rather than "everybody can call it" — safe.
- **[Trade-off]** We keep admin read endpoints on the same router instead of creating `menu_public`. Adds a few more routes to migrate later if the public contract ends up identical — acceptable, the contracts will diverge (public needs cache headers, grouping, no stop-listed items).

## Migration Plan

- Forward-only code change. No Alembic migration.
- Deployment: rolling restart of `core-api`. Old admin SPA (none yet) is unaffected.
- Rollback: revert the PR. The matrix entries are additive; removing them disables the endpoints. No data migration.

## 152-FZ Compliance

Not applicable. This change touches menu data only; no PII (`users`, `profiles`, `addresses`) is read or written. INV-013 is not engaged.

## Atomicity Analysis

Not applicable. No financial operations (payments, loyalty, promocodes). INV-004 is not engaged. Each CRUD call is a single-statement transaction plus `commit`.

## Open Questions

- Q1: Should `DELETE /items/{id}` hard-delete or set `archived=true`? **Proposed default**: hard-delete, because `archived` already exists for the soft-removal path and the admin SPA will use `PUT` with `archived=true` for that UX. Hard delete is reserved for never-launched items. If `order_items` or `cart` ever FK `menu_items` they SHOULD use `ON DELETE RESTRICT`, so hard delete on a referenced item will naturally 409. Accepting unless reviewer objects.
- Q2: Do we need a `GET /sizes/{id}` for the admin SPA edit-in-place UI? **Proposed default**: no — the SPA already has the size embedded in `MenuItemResponse.size_options`, so an edit form can populate itself from the cached parent fetch. Accepting unless reviewer objects.
