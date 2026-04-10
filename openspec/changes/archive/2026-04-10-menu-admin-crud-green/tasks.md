> **TDD phase: GREEN.** All tasks here land the minimal implementation that turns the RED tests green, followed by REFACTOR and VERIFY. Red-phase tasks live in `menu-admin-crud-red/tasks.md`. Task numbers reference the corresponding RED sections.

## 1. Schema addition

- [x] 1.1 **GREEN** [core-api] Add `class AvailabilityPatch(BaseModel)` to `services/core-api/src/core_api/schemas/menu.py` with a single required field `available: bool` and `model_config = ConfigDict(extra="forbid")`. → passes RED 2.1, 2.2.

## 2. Service module skeleton

- [x] 2.1 **GREEN** [core-api] Create `services/core-api/src/core_api/services/menu_admin.py` defining `class MenuAdminService` with `__init__(self, db: Session)` storing `self.db = db`. → passes RED 3.1.
- [x] 2.2 **GREEN** [core-api] Add placeholder method signatures for all 18 methods listed in RED 3.2 on `MenuAdminService`. Each may raise `NotImplementedError` temporarily — but see GREEN 3.x which fills them in before any router task runs. → unblocks RED 3.2 attribute check.

## 3. Service layer implementation

- [x] 3.1 **GREEN** [core-api] Implement `MenuAdminService.create_category / update_category / delete_category / list_categories` against the `Category` ORM model. `delete_category` catches `IntegrityError` from ON DELETE RESTRICT and raises `HTTPException(409, "category has items")`; missing ids raise `HTTPException(404)`. → passes RED 4.x.
- [x] 3.2 **GREEN** [core-api] Implement `create_item / update_item / delete_item / list_items / get_item` against `MenuItem`. `create_item` validates `category_id` exists (raises 404 if not). `get_item` eager-loads `size_options` and `modifiers`. → passes RED 5.1–5.6.
- [x] 3.3 **GREEN** [core-api] Implement `create_modifier / update_modifier / delete_modifier / list_modifiers` against `Modifier`. Missing ids → 404. → passes RED 6.1–6.4.
- [x] 3.4 **GREEN** [core-api] Implement `create_size / update_size / delete_size` against `SizeOption`. `create_size` validates `menu_item_id` exists; catches unique-constraint `IntegrityError` on `(menu_item_id, label)` and raises `HTTPException(409, "duplicate size label")`. → passes RED 7.1–7.4.
- [x] 3.5 **GREEN** [core-api] Implement `set_item_availability(item_id, available)` — SELECT the row, raise 404 if missing, set only `available`, commit, return refreshed row. Does NOT touch `archived`. → passes RED 8.1–8.4, 8.7, 8.9.
- [x] 3.6 **GREEN** [core-api] Implement `set_modifier_availability(modifier_id, available)` — SELECT, 404 if missing, set `available`, commit, return. → passes RED 9.1, 9.2, 9.5.

## 4. RBAC matrix wiring

- [x] 4.1 **GREEN** [core-api] Edit `services/core-api/src/core_api/rbac_matrix.py`: add entries for every `(method, path)` pair from design §D1 under `/api/v1/admin/menu/...`. Mutating category/item/modifier/size routes → `{ADMIN}`; admin read list/detail endpoints → `{ADMIN, BARISTA}`; both `PATCH .../availability` routes → `{ADMIN, BARISTA}`. No entries added to `PUBLIC_ROUTES`. → passes RED 10.1–10.5.

## 5. Router endpoints

- [x] 5.1 **GREEN** [core-api] In `services/core-api/src/core_api/routers/menu_admin.py` add the category endpoints: `POST /categories`, `GET /categories`, `PUT /categories/{category_id}`, `DELETE /categories/{category_id}`. Each obtains a `MenuAdminService(db)` via `Depends(get_db)` and delegates. Return status codes: 201 on POST, 204 on DELETE, 200 otherwise. → passes RED 4.1–4.9.
- [x] 5.2 **GREEN** [core-api] Add the menu item endpoints: `POST /items`, `GET /items`, `GET /items/{item_id}`, `PUT /items/{item_id}`, `DELETE /items/{item_id}`. Return `MenuItemResponse` (its computed `availability` field is serialized automatically). → passes RED 5.1–5.9.
- [x] 5.3 **GREEN** [core-api] Add `PATCH /items/{item_id}/availability` taking `AvailabilityPatch` as body, delegating to `service.set_item_availability`. → passes RED 8.1–8.8.
- [x] 5.4 **GREEN** [core-api] Add the modifier endpoints: `POST /modifiers`, `GET /modifiers`, `PUT /modifiers/{modifier_id}`, `DELETE /modifiers/{modifier_id}`. → passes RED 6.1–6.6.
- [x] 5.5 **GREEN** [core-api] Add `PATCH /modifiers/{modifier_id}/availability` taking `AvailabilityPatch`. → passes RED 9.1–9.5.
- [x] 5.6 **GREEN** [core-api] Add the size option endpoints: `POST /sizes`, `PUT /sizes/{size_id}`, `DELETE /sizes/{size_id}`. No `GET` list endpoint (per design §D1). → passes RED 7.1–7.5.

## 6. OpenAPI surface

- [x] 6.1 **GREEN** [core-api] Confirm no additional wiring is needed: the router is already mounted by `menu-router-stubs`, so filling in endpoints automatically exposes them in `/openapi.json`. Add `summary=` and `description=` strings to each endpoint to keep the generated admin API client readable. → passes RED 11.1, 11.2.

## 7. Refactor

- [x] 7.1 **REFACTOR** [core-api] Extract the `IntegrityError → HTTPException(409)` pattern in `MenuAdminService` into a small private helper `_handle_integrity(self, exc, detail)` used by `delete_category` and `create_size`. No behaviour change. Re-run `pytest services/core-api/tests/test_menu_admin.py`; all RED tests stay green.
- [x] 7.2 **REFACTOR** [core-api] In `routers/menu_admin.py` collapse `Depends(get_db)` + service instantiation into a single `Depends(get_menu_admin_service)` factory declared at module top. No behaviour change. Re-run test module; stays green.
- [x] 7.3 **REFACTOR** [core-api] Re-run the `test_menu_admin_router_has_no_direct_db_calls` guardrail from RED 3.3 and confirm it still passes after refactoring.

## 8. Verification

- [x] 8.1 **VERIFY** [core-api] Run `pytest services/core-api/tests/test_menu_admin.py -v` and confirm every test added in the RED change now passes. Tests requiring PostgreSQL skip on SQLite (expected — ORM models are PG-native). 30 passed, 25 skipped on SQLite.
- [x] 8.2 **VERIFY** [core-api] Run the full `pytest` suite for `services/core-api/` and confirm no previously passing test has regressed — in particular the `menu-router-stubs` tests that previously asserted `router.routes` was empty must either have been removed in the modified spec pass or now assert the populated state (see specs/menu-router-stubs/spec.md).
- [x] 8.3 **VERIFY** [core-api] Launch the app via `uvicorn` (or `TestClient`) and `curl`/`httpx` the following smoke calls in order — confirm each returns the expected status: create a category (201), create an item in it (201), create a size for that item (201), stop-list the item via barista JWT (200, availability=stop_list), un-stop-list it (200, availability=available), delete the item (204), delete the category (204).
- [x] 8.4 **VERIFY** [core-api] Fetch `/openapi.json` and grep for `"/api/v1/admin/menu/"` — confirm the count of unique paths matches the design table in §D1 exactly. If it diverges, reconcile before archiving the change.
