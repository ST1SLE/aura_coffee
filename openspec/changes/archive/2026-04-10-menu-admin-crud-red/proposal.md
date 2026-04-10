> **TDD phase: RED.** This is the first of a two-change pair (`menu-admin-crud-red` → `menu-admin-crud-green`). This change lands the failing tests that define the new admin menu contract. Both changes share identical proposal, design, and specs — only `tasks.md` differs.

## Why

The menu-schema (PDD §5.2) and empty `menu_admin` router stub (menu-router-stubs) are in place, but the admin panel (PDD §7.1 Phase 6, Phase 2 prerequisite for managing menu content) has no way to create, edit, or remove menu data, and baristas have no way to toggle the stop list during a shift. Until this capability lands, all menu data must be edited via SQL, and the INV-006 stop-list workflow is not usable end-to-end.

## What Changes

- Fill `core_api.routers.menu_admin` with CRUD endpoints (`POST`/`PUT`/`DELETE`) for `categories`, `menu_items`, `modifiers`, and `size_options` under `/api/v1/admin/menu/...`.
- Add `PATCH /api/v1/admin/menu/items/{id}/availability` and `PATCH /api/v1/admin/menu/modifiers/{id}/availability` as the dedicated stop-list toggle endpoints (per INV-006).
- Introduce a new `core_api.services.menu_admin` module that owns all SQLAlchemy writes, validates FKs (category → item, item → size option), and enforces non-negative kopeck prices via Pydantic/DB constraints (menu-schema already guarantees the DB side).
- Extend `rbac_matrix.ROUTE_MATRIX` so that:
  - full CRUD on categories/items/modifiers/sizes is restricted to role `admin`;
  - the two `availability` PATCH endpoints are allowed for roles `admin` **and** `barista` (baristas must be able to stop-list items mid-shift, INV-010 role isolation — baristas still cannot edit prices or create items).
- Add backend tests in `services/core-api/tests/test_menu_admin.py` covering happy paths, 404 on missing IDs, 403 on wrong roles, and the stop-list toggle specifically for barista.

## Non-Goals

- **Not** adding public read endpoints on `menu_public` — covered by a future change; this proposal is admin-write-only. `GET` endpoints under `/api/v1/admin/menu` are included only where required to read back created/updated resources (returned inline from POST/PUT).
- **Not** touching the web-admin React UI. This change stops at the HTTP contract; the admin SPA consumes it in a later worktree.
- **Not** introducing bulk / import endpoints, image upload, or category reordering via drag-and-drop. Simple per-resource CRUD only.
- **Not** changing `packages/shared/src/shared/models/menu.py` SQLAlchemy models or adding a new Alembic migration — the schema from `0004_menu_tables` is sufficient.
- **Not** adding audit logging / soft-delete semantics beyond the existing `archived` flag on `menu_items`.
- **Not** adding an idempotency layer or optimistic-locking `version` column.

## Capabilities

### New Capabilities
- `menu-admin-crud`: Admin-panel CRUD for categories, menu items, modifiers, and size options, plus the INV-006 stop-list toggle endpoints for items and modifiers, enforced via the RBAC matrix.

### Modified Capabilities
- `menu-router-stubs`: the `menu_admin` router is no longer empty — the stub's "zero endpoints" invariant for `menu_admin` is replaced by the real contract in `menu-admin-crud`. (`menu_public` and `cart` stubs are untouched.)

## Impact

- **Code:**
  - `services/core-api/src/core_api/routers/menu_admin.py` — populated.
  - `services/core-api/src/core_api/services/menu_admin.py` — new module.
  - `services/core-api/src/core_api/rbac_matrix.py` — new matrix entries.
  - `services/core-api/tests/test_menu_admin.py` — new test module.
- **API surface:** new admin endpoints under `/api/v1/admin/menu/...`. OpenAPI spec and the auto-generated web-admin API client will regenerate.
- **RBAC:** new routes protected by existing `RBACMiddleware`; stop-list endpoints are the only routes where `barista` can mutate menu state.
- **Dependencies / migrations:** none — uses existing menu-schema tables and existing Pydantic schemas in `core_api.schemas.menu`.
- **MVP phase:** PDD §7.1 Phase 6 (Admin Panel), unblocks Phase 2 (Menu & Cart) from needing manual SQL seeds.
- **Inviolable rules:** INV-002 (auth on mutations), INV-006 (stop list), INV-010 (role isolation — barista limited to stop-list toggles).
