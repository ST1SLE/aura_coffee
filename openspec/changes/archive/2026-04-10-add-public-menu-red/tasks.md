## 1. Prerequisites

- [x] 1.1 PREREQ [core-api] Create empty module file `services/core-api/src/core_api/services/menu_public.py` with only a module docstring (RU, 1 line) so future RED imports can target it without `ModuleNotFoundError` masking the intended `ImportError` on symbols.
- [x] 1.2 PREREQ [core-api] Create empty test module `services/core-api/tests/test_menu_public.py` with a module docstring (RU, 1 line) and an import of `fastapi.testclient.TestClient` + `core_api.main.app`. No tests yet.
- [x] 1.3 PREREQ [core-api] Add a pytest fixture `seed_public_menu` to `services/core-api/tests/conftest.py` that inserts a deterministic menu fixture into the test DB within a transaction rolled back after each test. Contents MUST include: (a) two visible `drink` / `food` categories with distinct `sort_order`, (b) one `is_visible = FALSE` category with one item, (c) one `type = 'modifier'` category with one row, (d) per-visible-category: one item with `archived = FALSE, available = TRUE`, one with `archived = FALSE, available = FALSE`, one with `archived = TRUE`, (e) each non-archived item has two `size_options` with mixed `available` and labels in non-sorted insertion order (`L`, `S` or `M`), (f) each non-archived item is linked to two `modifiers` with distinct `sort_order` and mixed `available`. Fixture yields a typed dataclass exposing the seeded IDs so tests can reference rows directly.

## 2. RED — service layer contract

- [x] 2.1 RED [core-api] In `tests/test_menu_public.py`, add `test_get_public_menu_service_is_importable`: asserts `from core_api.services.menu_public import get_public_menu` and that `get_public_menu` is a callable. Fails today with `ImportError`.
- [x] 2.2 RED [core-api] Add `test_get_public_menu_signature_uses_keyword_only_flags`: imports `get_public_menu`, uses `inspect.signature` to assert parameters are exactly `db` (positional-or-keyword), `only_available` (keyword-only, `bool`), `language` (keyword-only). Fails today.
- [x] 2.3 RED [core-api] Add `test_language_enum_exists`: asserts `from core_api.services.menu_public import Language` is an `enum.Enum` subclass with members `RU`, `EN`. Fails today.

## 3. RED — schemas (PublicMenu*)

- [x] 3.1 RED [core-api] Add `test_public_menu_schemas_importable`: asserts `PublicMenuResponse`, `PublicCategory`, `PublicMenuItem`, `PublicMenuSizeOption`, `PublicMenuModifier` are importable from `core_api.schemas.menu`. Fails today.
- [x] 3.2 RED [core-api] Add `test_public_menu_item_has_no_archived_field`: asserts `"archived"` is not in `PublicMenuItem.model_fields` and `"availability"` is not in `PublicMenuItem.model_fields`. Fails today (class does not exist).
- [x] 3.3 RED [core-api] Add `test_public_menu_item_exposes_flat_and_raw_bilingual_fields`: asserts `PublicMenuItem.model_fields` includes `name`, `name_ru`, `name_en`, `description`, `description_ru`, `description_en`, `base_price`, `image_url`, `available`, `sort_order`, `category_id`, `size_options`, `modifiers`, `id`.
- [x] 3.4 RED [core-api] Add `test_public_category_exposes_flat_and_raw_bilingual_fields`: asserts `PublicCategory.model_fields` contains `id`, `type`, `name`, `name_ru`, `name_en`, `sort_order`, `items`.
- [x] 3.5 RED [core-api] Add `test_admin_menu_item_response_still_has_archived`: asserts `"archived" in MenuItemResponse.model_fields` — guards against accidental edits to the admin schema. Passes today; MUST keep passing after green.
- [x] 3.6 RED [core-api] Add `test_public_menu_modifier_has_bilingual_and_name`: asserts `PublicMenuModifier.model_fields` contains `id`, `name`, `name_ru`, `name_en`, `price`, `available`.
- [x] 3.7 RED [core-api] Add `test_public_menu_size_option_has_expected_fields`: asserts `PublicMenuSizeOption.model_fields` contains exactly `id`, `label`, `price`, `available` (no bilingual fields).

## 4. RED — HTTP happy path

- [x] 4.1 RED [core-api] Add `test_get_menu_returns_200_for_anonymous_client`: uses `TestClient(app).get("/api/v1/menu")`, asserts status 200 and body has key `categories` as a list. Fails today (404 because router is empty).
- [x] 4.2 RED [core-api] Add `test_get_menu_empty_database_returns_empty_list`: with all fixture rows absent, asserts body equals `{"categories": []}`.
- [x] 4.3 RED [core-api] Add `test_get_menu_groups_and_orders_categories_and_items` using `seed_public_menu`: asserts (a) only visible non-modifier categories appear, (b) categories are ordered by `sort_order`, (c) within each category, items are ordered by `sort_order`, (d) the `drink` and `food` category ids are present and the invisible and `modifier` ids are absent.

## 5. RED — visibility rules

- [x] 5.1 RED [core-api] Add `test_archived_items_are_never_returned`: asserts the archived item ID from the fixture is not present in any category's `items` array, even when the `available` filter is absent.
- [x] 5.2 RED [core-api] Add `test_invisible_category_is_excluded_with_its_items`: asserts the invisible category ID is absent from the response and its items' IDs are absent from all categories.
- [x] 5.3 RED [core-api] Add `test_modifier_type_category_is_excluded`: asserts no response category has `type == "modifier"` and the fixture's `modifier` category id is absent.

## 6. RED — `available` query parameter

- [x] 6.1 RED [core-api] Add `test_default_request_includes_stop_listed_items`: hits `GET /api/v1/menu` with no query param, asserts the item with `available = FALSE` (non-archived) is present in the response and carries `"available": false`.
- [x] 6.2 RED [core-api] Add `test_available_true_hides_stop_listed_items`: hits `GET /api/v1/menu?available=true`, asserts the stop-listed item id is absent while the `available = TRUE` items are present.
- [x] 6.3 RED [core-api] Add `test_available_true_prunes_stop_listed_size_options`: hits `GET /api/v1/menu?available=true`, asserts the response item's `size_options` list for a known item contains only rows with `available is true`.
- [x] 6.4 RED [core-api] Add `test_available_false_is_treated_as_default`: hits `GET /api/v1/menu?available=false`, asserts the stop-listed item is still present (i.e. only `available=true` prunes; `available=false` == absent).
- [x] 6.5 RED [core-api] Add `test_archived_filter_is_independent_of_available_param`: hits both `GET /api/v1/menu` and `GET /api/v1/menu?available=true`, asserts the archived item id is absent from both.

## 7. RED — Accept-Language projection

- [x] 7.1 RED [core-api] Add `test_default_language_is_russian`: hits `GET /api/v1/menu` with no `Accept-Language` header, asserts every category and item has `name == name_ru` and item `description == description_ru` (or `None`).
- [x] 7.2 RED [core-api] Add `test_accept_language_en_selects_english`: hits `GET /api/v1/menu` with `Accept-Language: en`, asserts `name == name_en` and `description == description_en` for every item/category, AND that raw `name_ru`/`name_en` pairs are still present in the payload.
- [x] 7.3 RED [core-api] Add `test_accept_language_en_us_is_treated_as_english`: hits with `Accept-Language: en-US,en;q=0.9`, asserts `name == name_en`.
- [x] 7.4 RED [core-api] Add `test_unknown_accept_language_falls_back_to_russian`: hits with `Accept-Language: fr-FR`, asserts `name == name_ru`.
- [x] 7.5 RED [core-api] Add `test_null_description_projects_as_null`: with a seeded item whose `description_ru` and `description_en` are both `NULL`, asserts the response item has `description is None` and both raw description fields are `None`.
- [x] 7.6 RED [core-api] Add `test_modifier_name_is_projected_bilingually`: hits with `Accept-Language: en`, asserts at least one item's modifier has `name == name_en` and the raw pair is present.

## 8. RED — sizes, modifiers, ordering

- [x] 8.1 RED [core-api] Add `test_size_options_are_ordered_S_M_L`: with a seeded item whose size options were inserted in order `L, S`, asserts the response item's `size_options` come out in `S, L` order (enum order).
- [x] 8.2 RED [core-api] Add `test_modifiers_ordered_by_sort_order_then_id`: with seeded modifiers in mixed `sort_order`, asserts the response order matches `ORDER BY sort_order, id`.
- [x] 8.3 RED [core-api] Add `test_stop_listed_modifiers_still_visible_under_available_true`: hits `GET /api/v1/menu?available=true`, asserts at least one modifier with `available: false` is still in the response (filter only applies to items + size options, not modifiers).

## 9. RED — auth, query shape, router/service split

- [x] 9.1 RED [core-api] Add `test_anonymous_request_has_no_rbac_entry`: asserts the pair `("GET", "/api/v1/menu")` is NOT present in `core_api.rbac_matrix.RBAC_MATRIX` (or equivalent data structure). Fails only if someone later adds an entry; MUST be a lock-in assertion.
- [x] 9.2 RED [core-api] Add `test_public_menu_query_is_bounded` using `sqlalchemy.event` listeners on `before_cursor_execute` to count statements issued during a single `GET /api/v1/menu`: asserts the count is `<= 4` regardless of seeded-item count. (3 expected: categories+items joined, size_options selectin, modifiers selectin. Budget of 4 gives +1 for env overhead.)
- [x] 9.3 RED [core-api] Add `test_router_delegates_to_service` using `unittest.mock.patch` on `core_api.services.menu_public.get_public_menu`: asserts it is called exactly once per `GET /api/v1/menu` request.

## 10. RED — stub spec retirement lock-in

- [x] 10.1 RED [core-api] Edit `services/core-api/tests/test_router_stubs.py` to split the `menu_public` stub assertions: keep the prefix/tag assertions, REMOVE the "routes is empty" and "no paths under /api/v1/menu" assertions (those were valid only before this change). Add a new assertion that `GET /api/v1/menu` is registered. This test file change ships in the RED phase so the GREEN phase's implementation flips red→green on exactly the expected set.

## 11. RED — verify red state

- [x] 11.1 VERIFY [core-api] Run `pytest services/core-api/tests/test_menu_public.py services/core-api/tests/test_router_stubs.py -x` against the container's dev target. Expected: every RED test in groups 2–9 fails with either `ImportError` (groups 2–3) or `AssertionError` / HTTP 404 (groups 4–9). The admin-schema guard (3.5) and the untouched parts of `test_router_stubs.py` MUST still pass. Record the failure signatures in the task output so the green phase has a concrete target.
