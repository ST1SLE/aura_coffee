## Why

Companion GREEN phase to `fix-admin-items-category-filter-red`. The RED change lands a failing regression suite that pins down the contract for `GET /api/v1/admin/menu/items?category_id=<id>`. This change makes it pass.

The underlying bug: the admin SPA sends the `category_id` query string (`web/admin/src/api/menu.ts:202-207`), but the backend route at `services/core-api/src/core_api/routers/menu_admin.py:89-95` declares no parameters and `MenuAdminService.list_items()` at `services/core-api/src/core_api/services/menu_admin.py:108-114` queries all items unconditionally. Staff see products that don't belong to the selected category.

MVP phase: **Phase 6 — Admin Panel** (PDD §7.1). Belongs to the already-delivered `menu-admin-crud` capability.

## What Changes

- **Router** (`routers/menu_admin.py`): `list_items` gains `category_id: Annotated[int | None, Query(gt=0)] = None`, passed through to `svc.list_items(category_id=category_id)`.
- **Service** (`services/menu_admin.py`): `list_items` accepts `category_id: int | None = None`. When supplied, verifies the category exists via `self.db.get(Category, category_id)` and raises `HTTPException(404, "category not found")` if missing, then adds `.filter(MenuItem.category_id == category_id)` to the existing query chain. Ordering and eager-loading options stay identical.
- Test suite from the RED change turns green. No new tests added in this change.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `menu-admin-crud`: implements the `GET /admin/menu/items` category filter contract. Spec delta is identical to the RED change — both phases reference the same requirement so the delta stays consistent through archival.

## Non-Goals

- **No new tests.** The RED change owns the test suite; this change only flips it green.
- **No frontend changes.** The call site is already correct.
- **No filter on `/modifiers`, `/categories`, or `/sizes`.** Scope stays on items list only.
- **No schema, RBAC matrix, or Pydantic response model changes.**
- **No refactor of the surrounding CRUD code** (e.g., no pagination, no extraction of a common "category-scoped query" helper) — keep the diff minimal.

## Impact

- **Code**:
  - `services/core-api/src/core_api/routers/menu_admin.py` — add `category_id` query param to `list_items`.
  - `services/core-api/src/core_api/services/menu_admin.py` — `list_items` signature and body.
- **APIs**: Backwards-compatible additive query parameter. OpenAPI spec regenerates automatically; admin SPA's hand-rolled call is already correct.
- **Dependencies**: None.
- **Inviolable rules**: INV-002 / INV-010 (admin authorization) unchanged — same path, same RBAC entry.
- **Deploy**: Ships together with the RED change. Rollback = revert both.
