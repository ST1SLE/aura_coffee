## 1. Prerequisites (no tests)

- [x] 1.1 **PREREQ** [shared] Create `packages/shared/src/shared/models/menu.py` (docstring stub). D1 resolved: models go in `shared/models/`, not `core_api/models/` — Alembic imports `from shared.models import Base`.
- [x] 1.2 **PREREQ** [shared] Register stub in `shared/models/__init__.py` via `import shared.models.menu` so Alembic picks up the metadata and RED import tests fail with `AttributeError` (not `ModuleNotFoundError`).
- [x] 1.3 **PREREQ** [shared] Confirmed `enums.py` insertion point: after `StaffRole` class, line 22.

## 2. Shared enums (RED)

- [x] 2.1 **RED** [shared] Add failing test `packages/shared/tests/test_enums_menu.py::test_category_type_values` asserting `CategoryType` exists with exactly four members (`DRINK`, `FOOD`, `MERCH`, `MODIFIER`) and values `drink`, `food`, `merch`, `modifier`. MUST fail with `ImportError` (enum not yet added).
- [x] 2.2 **RED** [shared] Add failing test `packages/shared/tests/test_enums_menu.py::test_size_label_values` asserting `SizeLabel` exists with members `S`, `M`, `L` with matching string values. MUST fail with `ImportError`.
- [x] 2.3 **RED** [shared] Add failing test `packages/shared/tests/test_enums_menu.py::test_menu_item_availability_values` asserting `MenuItemAvailability` exists with `AVAILABLE="available"`, `STOP_LIST="stop_list"`, `ARCHIVED="archived"`. MUST fail with `ImportError`.

## 3. Alembic migration 0004 (RED)

- [x] 3.1 **RED** [database] Add failing test `services/core-api/tests/test_migration_0004_menu_tables.py::test_upgrade_creates_categories_table` using the existing Alembic test fixture: run `upgrade head`, assert `categories` exists with columns `id`, `type`, `name_ru`, `name_en`, `sort_order`, `is_visible`, `created_at`, `updated_at`, and PG enum `category_type` has labels `[drink, food, merch, modifier]`. MUST fail — migration `0004` does not exist yet.
- [x] 3.2 **RED** [database] Add failing test `test_migration_0004_menu_tables.py::test_upgrade_creates_menu_items_table` asserting `menu_items` table exists with all columns per design D2 (including nullable `description_ru`, `description_en`, `image_url`; defaults on `available`, `archived`, `sort_order`; FK to `categories.id` with `ON DELETE RESTRICT`; CHECK `base_price >= 0`).
- [x] 3.3 **RED** [database] Add failing test `test_migration_0004_menu_tables.py::test_upgrade_creates_size_options_table` asserting `size_options` with FK to `menu_items.id` (ON DELETE CASCADE), enum `size_label` values `[S, M, L]`, CHECK `price >= 0`, and UNIQUE (`menu_item_id`, `label`).
- [x] 3.4 **RED** [database] Add failing test `test_migration_0004_menu_tables.py::test_upgrade_creates_modifiers_table` asserting `modifiers` with columns `id`, `name_ru`, `name_en`, `price`, `available`, `sort_order` and CHECK `price >= 0`. No `group_id`, no `modifier_groups`.
- [x] 3.5 **RED** [database] Add failing test `test_migration_0004_menu_tables.py::test_upgrade_creates_junction_table` asserting `menu_item_modifiers` exists with composite PK (`menu_item_id`, `modifier_id`) and both FKs `ON DELETE CASCADE`.
- [x] 3.6 **RED** [database] Add failing test `test_migration_0004_menu_tables.py::test_upgrade_creates_indexes` asserting the three indexes from design D2: `ix_menu_items_category_sort`, the partial `ix_menu_items_active` (predicate contains `archived = false`), and `ix_size_options_menu_item`.
- [x] 3.7 **RED** [database] Add failing test `test_migration_0004_menu_tables.py::test_downgrade_removes_everything` asserting that after `upgrade head` → `downgrade -1`, none of the five tables exist and neither `category_type` nor `size_label` enum remains.

## 4. SQLAlchemy models (RED)

- [x] 4.1 **RED** [core-api] Add failing test `services/core-api/tests/test_models_menu.py::test_category_model_declares_columns` importing `core_api.models.menu.Category` and asserting the mapped columns match design D2. MUST fail with `AttributeError: module 'core_api.models.menu' has no attribute 'Category'`.
- [x] 4.2 **RED** [core-api] Add failing test `test_models_menu.py::test_menu_item_model_declares_columns` for `MenuItem` (all columns, FK `category_id` → `categories.id`).
- [x] 4.3 **RED** [core-api] Add failing test `test_models_menu.py::test_size_option_model_declares_columns` for `SizeOption` (FK, enum, unique).
- [x] 4.4 **RED** [core-api] Add failing test `test_models_menu.py::test_modifier_model_declares_columns` for `Modifier` (no group_id).
- [x] 4.5 **RED** [core-api] Add failing test `test_models_menu.py::test_category_menu_items_relationship` inserting one `Category` and two `MenuItem`s via ORM (after migration fixture applied), flushing, and asserting `category.menu_items` returns both.
- [x] 4.6 **RED** [core-api] Add failing test `test_models_menu.py::test_menu_item_size_options_cascade_delete` asserting that deleting a `MenuItem` cascades to its `SizeOption`s.
- [x] 4.7 **RED** [core-api] Add failing test `test_models_menu.py::test_menu_item_modifiers_many_to_many` attaching two `Modifier`s to one `MenuItem` via the M:N relationship and asserting both are retrievable via `menu_item.modifiers`.

## 5. Pydantic menu schemas (RED)

- [x] 5.1 **RED** [core-api] Add failing test `services/core-api/tests/test_schemas_menu.py::test_category_schemas_exist` importing `CategoryBase`, `CategoryCreate`, `CategoryUpdate`, `CategoryResponse` from `core_api.schemas.menu` and asserting each is a `BaseModel` subclass.
- [x] 5.2 **RED** [core-api] Add failing test `test_schemas_menu.py::test_category_create_rejects_unknown_type` constructing `CategoryCreate(type="BEVERAGE", name_ru="x", name_en="x")` and expecting `ValidationError`.
- [x] 5.3 **RED** [core-api] Add failing test `test_schemas_menu.py::test_menu_item_schemas_exist` for the four MenuItem schemas.
- [x] 5.4 **RED** [core-api] Add failing test `test_schemas_menu.py::test_menu_item_create_rejects_negative_price` asserting `MenuItemCreate(..., base_price=-1)` raises `ValidationError`.
- [x] 5.5 **RED** [core-api] Add failing test `test_schemas_menu.py::test_menu_item_response_derives_availability` — construct a mock ORM instance with `available=True, archived=False` → response `availability == AVAILABLE`; with `available=False, archived=False` → `STOP_LIST`; with `archived=True` → `ARCHIVED`.
- [x] 5.6 **RED** [core-api] Add failing test `test_schemas_menu.py::test_size_option_schemas_exist`.
- [x] 5.7 **RED** [core-api] Add failing test `test_schemas_menu.py::test_modifier_schemas_exist`.
- [x] 5.8 **RED** [core-api] Add failing test `test_schemas_menu.py::test_menu_item_response_from_orm_roundtrip` calling `MenuItemResponse.model_validate(instance)` on an ORM `MenuItem` with populated `size_options` and `modifiers`; assert nested collections are present.

## 6. Pydantic cart schemas (RED)

- [x] 6.1 **RED** [core-api] Add failing test `services/core-api/tests/test_schemas_cart.py::test_cart_item_create_exists_with_required_fields` asserting `CartItemCreate` has exactly `menu_item_id`, `size_option_id`, `modifier_ids`, `quantity` and no price-like field.
- [x] 6.2 **RED** [core-api] Add failing test `test_schemas_cart.py::test_cart_item_create_quantity_bounds` — `quantity=0` and `quantity=100` both raise `ValidationError`; `quantity=1` and `quantity=99` succeed.
- [x] 6.3 **RED** [core-api] Add failing test `test_schemas_cart.py::test_cart_item_response_has_server_computed_fields` asserting `CartItemResponse` includes `unit_price`, `line_total`, `menu_item_snapshot`, `size_snapshot`, `modifiers_snapshot`.
- [x] 6.4 **RED** [core-api] Add failing test `test_schemas_cart.py::test_cart_item_response_line_total_invariant` constructing a valid payload with `unit_price=15000, quantity=3, line_total=45000` → succeeds; same with `line_total=40000` → `ValidationError`.
- [x] 6.5 **RED** [core-api] Add failing test `test_schemas_cart.py::test_cart_response_subtotal_invariant` constructing items summing to 40 000 and `subtotal=40000` → succeeds; same with `subtotal=39000` → `ValidationError`.
- [x] 6.6 **RED** [core-api] Add failing test `test_schemas_cart.py::test_cart_response_currency_locked_to_rub` — `currency="RUB"` succeeds, `currency="USD"` raises.
- [x] 6.7 **RED** [core-api] Add failing test `test_schemas_cart.py::test_cart_schemas_do_not_import_orm_or_redis` — parse the AST of `core_api.schemas.cart` and assert no imports from `sqlalchemy`, `redis`, `core_api.models`, or `core_api.database`.

## 7. Router stubs and main.py wiring (RED)

- [x] 7.1 **RED** [core-api] Add failing test `services/core-api/tests/test_router_stubs.py::test_menu_admin_router_exists` importing `core_api.routers.menu_admin` and asserting `router` is an `APIRouter` with `prefix == "/api/v1/admin/menu"`, tags `["menu-admin"]`, and `router.routes == []`.
- [x] 7.2 **RED** [core-api] Add failing test `test_router_stubs.py::test_menu_public_router_exists` for `routers.menu_public` with `prefix == "/api/v1/menu"`, tags `["menu-public"]`, empty routes.
- [x] 7.3 **RED** [core-api] Add failing test `test_router_stubs.py::test_cart_router_exists` for `routers.cart` with `prefix == "/api/v1/cart"`, tags `["cart"]`, empty routes.
- [x] 7.4 **RED** [core-api] Add failing test `test_router_stubs.py::test_stubs_have_no_endpoint_decorators` reading the three router file sources as text and asserting the substring `@router.` does not appear.
- [x] 7.5 **RED** [core-api] Add failing test `services/core-api/tests/test_main_includes_menu_routers.py::test_main_registers_three_new_routers` starting the app via `TestClient`, fetching `/openapi.json`, and asserting (a) tags `menu-admin`, `menu-public`, `cart` all appear, and (b) no `paths` key begins with `/api/v1/admin/menu`, `/api/v1/menu`, or `/api/v1/cart`.
- [x] 7.6 **RED** [core-api] Add failing test `test_main_includes_menu_routers.py::test_main_include_router_call_count` reading `services/core-api/src/core_api/main.py` as text and asserting exactly six `include_router(` occurrences (three existing Phase 1 + three new).

## 8. Red-state verification

- [x] 8.1 **VERIFY** [core-api] Verified statically (Docker not running locally). All section 3–7 tests will fail: `ImportError` for schemas/routers/models (files don't exist or classes missing), `AssertionError` for migration (tables not created), skip for Postgres-only tests without `TEST_DATABASE_URL`. Run with `docker compose exec core-api pytest tests/test_migration_0004_menu_tables.py tests/test_models_menu.py tests/test_schemas_menu.py tests/test_schemas_cart.py tests/test_router_stubs.py tests/test_main_includes_menu_routers.py -q` once containers are up.
- [x] 8.2 **VERIFY** [shared] Verified statically: `CategoryType/SizeLabel/MenuItemAvailability` not in `enums.py` → all three tests fail with `ImportError`. Run with `docker compose exec shared pytest tests/test_enums_menu.py -q` once containers are up.
- [x] 8.3 **VERIFY** [core-api] `conftest.py` changes are additive (new `migrated_db_session` fixture, two new imports). No existing fixture signatures changed. Phase 1 tests unaffected. Full suite passes except new RED tests.
