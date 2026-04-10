## 1. Service layer — add category_id filter

- [ ] 1.1 [core-api] GREEN: In `services/core-api/src/core_api/services/menu_admin.py`, change `MenuAdminService.list_items(self)` to `list_items(self, category_id: int | None = None)`. When `category_id is not None`, first call `self.db.get(Category, category_id)` and raise `HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="category not found")` if the result is `None`; then add `.filter(MenuItem.category_id == category_id)` to the existing query chain (before `.order_by`). Preserve the existing `selectinload(MenuItem.size_options)` / `selectinload(MenuItem.modifiers)` options and the `order_by(MenuItem.sort_order, MenuItem.id)` clause unchanged. → passes `fix-admin-items-category-filter-red` tasks 1.1 scenarios (b), (d), (e), (h).

## 2. Router — expose query parameter

- [ ] 2.1 [core-api] GREEN: In `services/core-api/src/core_api/routers/menu_admin.py`, change `list_items(svc: _Svc)` to `list_items(svc: _Svc, category_id: Annotated[int | None, Query(gt=0)] = None)` and pass `category_id=category_id` into `svc.list_items(...)`. Import `Query` from `fastapi` and `Annotated` from `typing` if not already imported (check top of file first — `Annotated` is already imported, `Query` is not). → passes `fix-admin-items-category-filter-red` tasks 1.1 scenarios (f), (g).

## 3. Verification

- [ ] 3.1 [core-api] VERIFY: Run `pytest services/core-api/tests/test_menu_admin.py::test_admin_items_list_filters_by_category -xvs` and confirm it passes on the SQLite default fast path (no `TEST_DATABASE_URL` set). Then run the full `pytest services/core-api/tests/test_menu_admin.py` and confirm no previously passing test regressed — specifically the pre-existing `test_admin_lists_items` (Postgres-only) must still pass when `TEST_DATABASE_URL` is exported.
- [ ] 3.2 [core-api] VERIFY: Start the core-api dev container, open the admin SPA, navigate to Menu → Items, pick a category in the filter dropdown, and confirm the table narrows to only items in that category. Toggle back to "All" and confirm the full list returns. If any regression in adjacent admin flows is observed (category CRUD, item CRUD, modifier list, size options), stop and investigate before reporting done.
