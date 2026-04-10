## Context

Affected modules: **[core-api]**.

`GET /api/v1/admin/menu/items` in `services/core-api/src/core_api/routers/menu_admin.py:89-95` currently has no query parameters. The admin SPA sends `?category_id=<id>` (`web/admin/src/api/menu.ts:202-207`), but FastAPI silently discards unknown query strings and `svc.list_items()` in `services/menu_admin.py:108-114` returns every row unconditionally. The RED change `fix-admin-items-category-filter-red` locks in a failing regression suite; this change implements the route and service changes that turn it green.

No test in `tests/test_menu_admin.py` pre-RED asserted that a filtered list excluded items from other categories. The existing list test (line 258-276, `_IS_SQLITE` skip) seeds three items in one category and asserts `len >= 3` — too loose to catch the bug.

References: PDD §5.2 (Menu tables), §7.1 Phase 6 (Admin Panel), INV-002 / INV-010 (admin auth unchanged).

## Goals / Non-Goals

**Goals:**
- `GET /admin/menu/items` MUST honor an optional `category_id` query parameter server-side.
- Invalid (`<=0`, non-integer) IDs MUST yield HTTP 422 via Pydantic.
- Nonexistent IDs MUST yield HTTP 404 with detail `"category not found"`.
- Existing behavior (no param → all items, RBAC, ordering, eager loading) MUST be preserved unchanged.
- All tests from `fix-admin-items-category-filter-red` MUST pass after this change.

**Non-Goals:**
- No new tests — the RED change owns them.
- No pagination, search, sort, or filtering on `/modifiers`, `/categories`, or `/sizes`.
- No schema changes, no RBAC matrix changes, no Pydantic response-model changes.
- No refactor of `MenuAdminService.list_items` beyond adding the one parameter and the filter — the diff should be the smallest thing that passes the RED suite.

## Decisions

### Decision 1: Query parameter validation — `Query(None, gt=0)` (strict)

The route SHALL declare `category_id: Annotated[int | None, Query(gt=0)] = None`.

- **Why `int`**: FastAPI/Pydantic coerce and reject non-integer values with HTTP 422 for free.
- **Why `gt=0`**: Category PK is a positive auto-increment. `0` and negatives are structurally impossible and almost certainly a caller bug. Rejecting them with 422 surfaces the bug instead of hiding it behind an empty list.
- **Why not `ge=1`**: Equivalent; `gt=0` reads more naturally against "positive integer."

**Alternative considered — permissive (return `[]` for `0`/negative/nonexistent)**: Rejected in the explore phase. A silent empty response is exactly how the current bug manifests; we should not trade one silent failure for another. Admin tool users are staff, not customers, and can surface a 404/422 toast gracefully.

### Decision 2: Nonexistent category → HTTP 404

When `category_id` is provided and `db.get(Category, category_id) is None`, the service SHALL raise `HTTPException(404, "category not found")`. This matches the existing pattern in `create_item` (`services/menu_admin.py:75-76`) and in `update_category` / `delete_category` / `update_item` / `delete_item`. Consistency > novelty.

**Alternative considered — return `[]`**: Rejected (see Decision 1).

### Decision 3: Filter lives in the service layer, not the router

The service method becomes `list_items(self, category_id: int | None = None)`. The router passes the query param through. The `.filter(MenuItem.category_id == category_id)` clause is added inside the existing query chain before `.order_by`. Eager-loading `.options(selectinload(...))` stays untouched.

**Why**: All DB access in `menu-admin-crud` lives in `MenuAdminService`. The router is a thin adapter. Keeping the filter in the service preserves that boundary.

### Decision 4: Implement in the exact order that makes the RED suite go green

Service change lands before router change. If only the router is patched first, the test framework sees a TypeError (`list_items() got an unexpected keyword argument 'category_id'`) which obscures signal. Patching the service first means the route keeps compiling even mid-edit.

## Risks / Trade-offs

- **Risk**: Stale frontend dropdown (category deleted by another admin) now returns 404 instead of an empty list, which shows up as a toast error. → **Mitigation**: Acceptable and intentional (Decision 2). If it becomes a UX problem, the fix is frontend: handle 404 on the items fetch by reloading the category list. Tracked as a follow-up idea, not a scope expansion here.
- **Risk**: Adding a new query parameter changes the OpenAPI schema. → **Mitigation**: The affected call is hand-rolled in `web/admin/src/api/menu.ts:202-207` and already sends `category_id`. Auto-generated clients don't consume admin endpoints.
- **Trade-off**: Strict validation is slightly less forgiving than "filter that matches nothing." Deliberate — loud failures for an internal tool.

## Migration Plan

Forward-only code change. No data migration, no schema change, no feature flag, no staged rollout. Deploy core-api together with the RED change, verify the admin items table in staging (dropdown filter actually narrows the list; toggling "All categories" restores full list), ship to prod. Rollback = revert both commits; the frontend continues to send the query param which the old server continues to ignore (pre-fix behavior).
