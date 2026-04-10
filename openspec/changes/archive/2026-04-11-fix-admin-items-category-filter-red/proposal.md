## Why

The admin SPA's menu items table has a "filter by category" dropdown. The frontend sends `GET /api/v1/admin/menu/items?category_id=<id>` (see `web/admin/src/api/menu.ts:202-207`), but the backend route at `services/core-api/src/core_api/routers/menu_admin.py:89-95` declares no query parameters and `MenuAdminService.list_items()` at `services/core-api/src/core_api/services/menu_admin.py:108-114` queries all items unconditionally. FastAPI silently drops the unknown query string, so the filter is a no-op and staff see products that don't belong to the selected category.

This is the **RED phase** of the fix: establish failing tests that pin down the expected behavior before touching production code. The GREEN phase (`fix-admin-items-category-filter-green`) will make them pass.

MVP phase: **Phase 6 — Admin Panel** (PDD §7.1). Belongs to the already-delivered `menu-admin-crud` capability.

## What Changes

- Add failing tests to `services/core-api/tests/test_menu_admin.py` that lock in the new server-side filter behavior:
  - `GET /admin/menu/items` with no param → still returns all items (regression guard).
  - `GET /admin/menu/items?category_id=<A>` → returns only items from category A, excludes items from category B.
  - `GET /admin/menu/items?category_id=999999` (nonexistent) → HTTP 404 with detail `"category not found"`.
  - `GET /admin/menu/items?category_id=0` → HTTP 422.
  - `GET /admin/menu/items?category_id=abc` → HTTP 422.
  - Barista role can filter too (RBAC regression guard).
- Tests MUST be SQLite-safe (no `_IS_SQLITE` skip) so they run in the fast suite.
- Production code in router and service layer is NOT touched in this change — the tests will fail against `main`, which is the RED state.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `menu-admin-crud`: pins new scenarios for the `GET /admin/menu/items` filter behavior. The spec delta is identical to the GREEN change's delta — the contract is defined once here and consumed by both phases.

## Non-Goals

- **No production code changes.** Router and service layer stay broken; the point of this phase is to have a failing regression suite.
- **No frontend changes.** The call site is already correct (`web/admin/src/api/menu.ts:202-207`).
- **No filter on `/modifiers`, `/categories`, or `/sizes`.** No gap exists there.
- **No schema or RBAC matrix changes.**
- **Not merged to `main` alone.** This change ships together with `fix-admin-items-category-filter-green` — merging RED alone would land failing tests on `main`.

## Impact

- **Code**: `services/core-api/tests/test_menu_admin.py` gets one new test function (or small test class) exercising all six scenarios.
- **CI**: test run turns red until GREEN lands. The two changes MUST be applied back-to-back on the same branch.
- **Dependencies**: none.
- **Inviolable rules**: INV-002 / INV-010 (admin authorization) unchanged.
