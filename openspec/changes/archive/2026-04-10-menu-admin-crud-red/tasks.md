> **TDD phase: RED.** All tasks here add failing tests and the minimal scaffolding required to make them collectable by pytest. No production behaviour is implemented. Green-phase tasks live in `menu-admin-crud-green/tasks.md`.

## 1. Prerequisites

- [x] 1.1 **PREREQ** [core-api] Confirm `services/core-api/tests/conftest.py` already exposes a `client: TestClient` fixture with a clean DB and factories for admin/barista/customer/courier JWTs. If any of the four role fixtures is missing, add it (one task per missing role, split out if needed). No new test file yet.
- [x] 1.2 **PREREQ** [core-api] Confirm `services/core-api/tests/conftest.py` exposes a SQLAlchemy `db_session` fixture bound to `TEST_DATABASE_URL` for direct ORM assertions inside the new test module. If missing, add it.
- [x] 1.3 **PREREQ** [core-api] Create empty test module `services/core-api/tests/test_menu_admin.py` with the module docstring `"""RED: menu-admin CRUD and stop-list contract."""` and an `import pytest` line. No test functions yet.

## 2. AvailabilityPatch schema (RED)

- [x] 2.1 **RED** [core-api] In `test_menu_admin.py` add `test_availability_patch_schema_exists` importing `AvailabilityPatch` from `core_api.schemas.menu` and asserting it is a `BaseModel` subclass with exactly one required field `available: bool`. MUST fail with `ImportError` (symbol not yet defined).
- [x] 2.2 **RED** [core-api] Add `test_availability_patch_rejects_extra_fields` constructing `AvailabilityPatch(available=False, price=0)` and expecting `ValidationError` (model_config must forbid extras). MUST fail with `ImportError` first.

## 3. Service module shape (RED)

- [x] 3.1 **RED** [core-api] Add `test_menu_admin_service_importable` asserting `from core_api.services.menu_admin import MenuAdminService` succeeds and that `MenuAdminService.__init__` takes `db: Session`. MUST fail with `ModuleNotFoundError`.
- [x] 3.2 **RED** [core-api] Add `test_menu_admin_service_has_required_methods` asserting `MenuAdminService` exposes callables: `create_category, update_category, delete_category, list_categories, create_item, update_item, delete_item, list_items, get_item, set_item_availability, create_modifier, update_modifier, delete_modifier, list_modifiers, set_modifier_availability, create_size, update_size, delete_size`. MUST fail with `AttributeError` once 3.1 is green.
- [x] 3.3 **RED** [core-api] Add `test_menu_admin_router_has_no_direct_db_calls` grepping the text of `core_api/routers/menu_admin.py` for `db.add(`, `db.delete(`, `db.commit(`, `db.flush(` — asserting zero matches. MUST pass trivially now (router is empty) and continue to pass throughout green. This is a guardrail for D4.

## 4. Categories CRUD (RED)

- [x] 4.1 **RED** [core-api] Add `test_admin_creates_category` — admin JWT `POST /api/v1/admin/menu/categories` with a valid body, assert 201 and echoed fields. MUST fail with 404 (route not registered).
- [x] 4.2 **RED** [core-api] Add `test_admin_updates_category` — admin `PUT /api/v1/admin/menu/categories/{id}` with a partial body, assert 200 and updated fields.
- [x] 4.3 **RED** [core-api] Add `test_admin_lists_categories_returns_seeded_rows` — seed 2 categories via `db_session`, admin `GET /api/v1/admin/menu/categories`, assert 200 and len == 2.
- [x] 4.4 **RED** [core-api] Add `test_barista_lists_categories_allowed` — seed 1 category, barista `GET /api/v1/admin/menu/categories`, assert 200.
- [x] 4.5 **RED** [core-api] Add `test_admin_deletes_empty_category` — admin `DELETE` on a category with no items, assert 204 and row gone in `db_session`.
- [x] 4.6 **RED** [core-api] Add `test_admin_delete_referenced_category_returns_409` — create a category + one item in it via `db_session`, admin `DELETE` on the category, assert 409 and row still present.
- [x] 4.7 **RED** [core-api] Add `test_barista_cannot_create_category` — barista `POST`, assert 403.
- [x] 4.8 **RED** [core-api] Add `test_barista_cannot_delete_category` — barista `DELETE`, assert 403.
- [x] 4.9 **RED** [core-api] Add `test_customer_blocked_from_categories_crud` — customer `GET`/`POST`/`DELETE`, assert 403 each.

## 5. Menu items CRUD (RED)

- [x] 5.1 **RED** [core-api] Add `test_admin_creates_menu_item` — seed a category, admin `POST /api/v1/admin/menu/items` with a valid body, assert 201 and `availability == "available"`.
- [x] 5.2 **RED** [core-api] Add `test_admin_create_item_with_unknown_category_rejected` — admin `POST` with a `category_id` that doesn't exist, assert 404 or 409 (document the exact code in a comment once it's frozen by the green phase).
- [x] 5.3 **RED** [core-api] Add `test_admin_updates_item_archives_it` — seed an item, admin `PUT .../items/{id}` with body `{"archived": true}`, assert 200 and `availability == "archived"`.
- [x] 5.4 **RED** [core-api] Add `test_admin_lists_items` — seed 3 items, admin `GET .../items`, assert 200 and len == 3.
- [x] 5.5 **RED** [core-api] Add `test_admin_gets_single_item_with_sizes_and_modifiers` — seed an item with 2 sizes and 1 modifier attached, admin `GET .../items/{id}`, assert embedded `size_options` and `modifiers` lists match.
- [x] 5.6 **RED** [core-api] Add `test_admin_deletes_item` — admin `DELETE .../items/{id}`, assert 204.
- [x] 5.7 **RED** [core-api] Add `test_barista_lists_items_allowed` — seed items, barista `GET`, assert 200.
- [x] 5.8 **RED** [core-api] Add `test_barista_cannot_delete_item` — barista `DELETE`, assert 403.
- [x] 5.9 **RED** [core-api] Add `test_customer_blocked_from_items_crud` — customer on list and delete, assert 403.

## 6. Modifiers CRUD (RED)

- [x] 6.1 **RED** [core-api] Add `test_admin_creates_modifier` — admin `POST .../modifiers` with valid body, assert 201.
- [x] 6.2 **RED** [core-api] Add `test_admin_updates_modifier_price` — seed modifier, admin `PUT .../modifiers/{id}` body `{"price": 5000}`, assert 200 and price==5000.
- [x] 6.3 **RED** [core-api] Add `test_admin_deletes_modifier` — admin `DELETE`, assert 204.
- [x] 6.4 **RED** [core-api] Add `test_delete_missing_modifier_returns_404` — admin `DELETE` on non-existent id, assert 404.
- [x] 6.5 **RED** [core-api] Add `test_barista_lists_modifiers_allowed` — seed modifiers, barista `GET`, assert 200.
- [x] 6.6 **RED** [core-api] Add `test_barista_cannot_update_modifier` — barista `PUT`, assert 403.

## 7. Size options CRUD (RED)

- [x] 7.1 **RED** [core-api] Add `test_admin_creates_size_for_item` — seed an item, admin `POST .../sizes` with `{menu_item_id, label: "M", price: 100}`, assert 201 and echoed `menu_item_id`.
- [x] 7.2 **RED** [core-api] Add `test_duplicate_size_label_on_same_item_returns_409` — admin creates size `M` twice for the same item, assert second request returns 409.
- [x] 7.3 **RED** [core-api] Add `test_admin_updates_size_price` — seed size, admin `PUT .../sizes/{id}` with `{"price": 200}`, assert 200.
- [x] 7.4 **RED** [core-api] Add `test_admin_deletes_size` — admin `DELETE`, assert 204.
- [x] 7.5 **RED** [core-api] Add `test_barista_cannot_create_size` — barista `POST .../sizes`, assert 403.

## 8. Item stop-list toggle (RED)

- [x] 8.1 **RED** [core-api] Add `test_barista_stop_lists_item` — seed available item, barista `PATCH .../items/{id}/availability` body `{"available": false}`, assert 200 and `availability == "stop_list"`.
- [x] 8.2 **RED** [core-api] Add `test_barista_unstops_item` — seed stop-listed item, barista same endpoint `{"available": true}`, assert 200 and `availability == "available"`.
- [x] 8.3 **RED** [core-api] Add `test_archived_item_availability_unchanged_by_toggle` — seed archived item, barista sends `{"available": true}`, assert 200 and returned `availability == "archived"` and DB `archived` still `true`.
- [x] 8.4 **RED** [core-api] Add `test_admin_stop_lists_item` — admin same endpoint, assert 200.
- [x] 8.5 **RED** [core-api] Add `test_customer_blocked_from_item_availability` — customer `PATCH .../items/{id}/availability`, assert 403.
- [x] 8.6 **RED** [core-api] Add `test_courier_blocked_from_item_availability` — courier same endpoint, assert 403.
- [x] 8.7 **RED** [core-api] Add `test_item_availability_patch_404_on_missing_id` — admin `PATCH` on non-existent id, assert 404.
- [x] 8.8 **RED** [core-api] Add `test_item_availability_patch_rejects_extra_fields` — admin body `{"available": false, "price": 0}`, assert 422.
- [x] 8.9 **RED** [core-api] Add `test_item_availability_patch_only_touches_available_column` — seed item with known `base_price`, barista toggles availability, assert DB `base_price` unchanged.

## 9. Modifier stop-list toggle (RED)

- [x] 9.1 **RED** [core-api] Add `test_barista_stop_lists_modifier` — seed modifier, barista `PATCH .../modifiers/{id}/availability` body `{"available": false}`, assert 200 and `available == False` in response.
- [x] 9.2 **RED** [core-api] Add `test_admin_stop_lists_modifier` — admin same endpoint, assert 200.
- [x] 9.3 **RED** [core-api] Add `test_customer_blocked_from_modifier_availability` — customer `PATCH`, assert 403.
- [x] 9.4 **RED** [core-api] Add `test_courier_blocked_from_modifier_availability` — courier `PATCH`, assert 403.
- [x] 9.5 **RED** [core-api] Add `test_modifier_availability_patch_404_on_missing_id` — admin `PATCH` on non-existent id, assert 404.

## 10. RBAC matrix coverage (RED)

- [x] 10.1 **RED** [core-api] Add `test_rbac_matrix_contains_admin_menu_routes` importing `ROUTE_MATRIX` from `core_api.rbac_matrix` and asserting entries exist for every `(method, path)` pair in §D1 of `design.md`. MUST fail until the green phase wires them up.
- [x] 10.2 **RED** [core-api] Add `test_rbac_matrix_availability_routes_allow_barista` asserting that the two `PATCH .../availability` entries have role set `{"admin", "barista"}` and no other non-GET entry under `/api/v1/admin/menu` contains `"barista"`.
- [x] 10.3 **RED** [core-api] Add `test_rbac_matrix_mutations_admin_only` asserting that every non-GET, non-`/availability` entry under `/api/v1/admin/menu` has role set `{"admin"}`.
- [x] 10.4 **RED** [core-api] Add `test_admin_menu_routes_not_public` asserting no `/api/v1/admin/menu/...` entry exists in `PUBLIC_ROUTES`.
- [x] 10.5 **RED** [core-api] Add `test_unauthenticated_admin_menu_request_401` — plain `client.get("/api/v1/admin/menu/categories")` with no Authorization header, assert 401.

## 11. OpenAPI surface (RED)

- [x] 11.1 **RED** [core-api] Add `test_openapi_exposes_menu_admin_paths` — fetch `/openapi.json` and assert at least the ten admin menu paths from §D1 appear under `paths` with their expected methods. MUST fail until green.
- [x] 11.2 **RED** [core-api] Add `test_openapi_menu_admin_tag_is_consistent` asserting every admin menu operation in `/openapi.json` carries the `menu-admin` tag.

## 12. Red-phase verification

- [x] 12.1 **VERIFY** [core-api] Run `pytest services/core-api/tests/test_menu_admin.py` and confirm that all tests added in sections 2–11 fail with `ImportError`, `AttributeError`, `404`, `403`, or assertion errors — NEVER with unexpected `500`s. Fix any 500s by adding the minimal import stub (still keeping the behaviour failing) before moving on.
- [x] 12.2 **VERIFY** [core-api] Run the full `pytest` suite and confirm the new RED tests are the only failures — no previously passing test has regressed. The output of this command is the handoff signal to `menu-admin-crud-green`.
