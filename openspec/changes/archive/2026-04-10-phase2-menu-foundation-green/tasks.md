## 1. Shared enums

- [x] 1.1 **GREEN** [shared] Add `CategoryType(str, Enum)` to `packages/shared/src/shared/enums.py` with members `DRINK="drink"`, `FOOD="food"`, `MERCH="merch"`, `MODIFIER="modifier"`. → passes RED 2.1.
- [x] 1.2 **GREEN** [shared] Add `SizeLabel(str, Enum)` with members `S="S"`, `M="M"`, `L="L"`. → passes RED 2.2.
- [x] 1.3 **GREEN** [shared] Add `MenuItemAvailability(str, Enum)` with members `AVAILABLE="available"`, `STOP_LIST="stop_list"`, `ARCHIVED="archived"`. → passes RED 2.3.
- [x] 1.4 **REFACTOR** [shared] Grouped under `# Menu` block; `shared/__init__.py` has no re-exports to update.

## 2. Alembic migration 0004

- [x] 2.1 **MIGRATE** [database] Create `database/migrations/versions/0004_menu_tables.py` with `revision = "0004_menu_tables"`, `down_revision = "0003_staff_accounts"`. Implement `upgrade()` creating in order: PG enum `category_type`, PG enum `size_label`, then tables `categories`, `menu_items`, `size_options`, `modifiers`, `menu_item_modifiers`, then indexes `ix_menu_items_category_sort`, partial `ix_menu_items_active`, `ix_size_options_menu_item`. All columns, defaults, CHECK constraints, FKs, and cascade rules per design D2. → passes RED 3.1–3.6.
- [x] 2.2 **MIGRATE** [database] Implement `downgrade()` in `0004_menu_tables.py` dropping in reverse order: indexes, `menu_item_modifiers`, `modifiers`, `size_options`, `menu_items`, `categories`, enum `size_label`, enum `category_type`. → passes RED 3.7.
- [x] 2.3 **VERIFY** [database] Run `pytest services/core-api/tests/test_migration_0004_menu_tables.py -q` and confirm all seven tests pass.
- [x] 2.4 **VERIFY** [database] Manually run `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` against a fresh test database; confirm each command exits zero and `\dt` + `\dT` in `psql` show the expected state transitions.

## 3. SQLAlchemy models

- [x] 3.1 **GREEN** [shared] `shared/models/__init__.py` now exports `Category, MenuItem, SizeOption, Modifier` from `shared.models.menu` (D1: models live in shared, not core_api).
- [x] 3.2 **GREEN** [shared] `Category` declared in `shared/models/menu.py` with all D2 columns. → passes RED 4.1.
- [x] 3.3 **GREEN** [shared] `MenuItem` declared with all columns, FK on `category_id`, `relationship("Category")`. → passes RED 4.2.
- [x] 3.4 **GREEN** [shared] `SizeOption` declared with FK (`ondelete="CASCADE"`), `SizeLabel` enum, relationship back to `MenuItem`. → passes RED 4.3.
- [x] 3.5 **GREEN** [shared] `Modifier` declared — six columns, no group_id. → passes RED 4.4.
- [x] 3.6 **GREEN** [shared] `menu_item_modifiers` Table + M:N relationships wired. `Category.menu_items` and `MenuItem.size_options` with cascade/passive_deletes. → passes RED 4.5, 4.6, 4.7.
- [x] 3.7 **REFACTOR** [shared] Classes ordered: Category → Modifier → SizeOption → MenuItem. `__repr__` on each. Consistent `Mapped[...]` annotations throughout.

## 4. Pydantic menu schemas

- [x] 4.1 **GREEN** [core-api] `schemas/menu.py` created with `CategoryBase/Create/Update/Response`. → passes RED 5.1, 5.2.
- [x] 4.2 **GREEN** [core-api] `MenuItemBase/Create/Update/Response` with `PriceKopecks`, nested `size_options` and `modifiers`. → passes RED 5.3, 5.4.
- [x] 4.3 **GREEN** [core-api] `@computed_field availability` on `MenuItemResponse`. → passes RED 5.5.
- [x] 4.4 **GREEN** [core-api] `SizeOptionBase/Create/Update/Response` with `SizeLabel` and `PriceKopecks`. → passes RED 5.6.
- [x] 4.5 **GREEN** [core-api] `ModifierBase/Create/Update/Response` with `PriceKopecks`, no group fields. → passes RED 5.7.
- [x] 4.6 **GREEN** [core-api] All `Response` classes have `ConfigDict(from_attributes=True)`. → passes RED 5.8.
- [x] 4.7 **REFACTOR** [core-api] `PriceKopecks` alias extracted; order: Category → Modifier → SizeOption → MenuItem (no forward refs needed).

## 5. Pydantic cart schemas

- [x] 5.1 **GREEN** [core-api] `CartItemCreate` with four fields, no price. → passes RED 6.1, 6.2.
- [x] 5.2 **GREEN** [core-api] `MenuItemCartSnapshot`, `SizeSnapshot`, `ModifierSnapshot` declared as pure DTOs.
- [x] 5.3 **GREEN** [core-api] `CartItemResponse` with `model_validator` enforcing `line_total == unit_price * quantity`. → passes RED 6.3, 6.4.
- [x] 5.4 **GREEN** [core-api] `CartResponse` with `model_validator` enforcing `subtotal == sum(line_total)`. → passes RED 6.5, 6.6.
- [x] 5.5 **GREEN** [core-api] Imports: only `pydantic`, `typing`, `datetime`, `shared.enums`. No sqlalchemy/redis. → passes RED 6.7.
- [x] 5.6 **REFACTOR** [core-api] Snapshots at top of file; Russian docstrings on each class.

## 6. Router stubs and main.py wiring

- [x] 6.1 **GREEN** [core-api] `routers/menu_admin.py` created. → passes RED 7.1.
- [x] 6.2 **GREEN** [core-api] `routers/menu_public.py` created. → passes RED 7.2.
- [x] 6.3 **GREEN** [core-api] `routers/cart.py` created. → passes RED 7.3, 7.4.
- [x] 6.4 **GREEN** [core-api] `main.py` updated: 3 new imports (blank-line separated from Phase 1) + 3 `include_router` calls. → passes RED 7.5, 7.6.
- [x] 6.5 **REFACTOR** [core-api] Order: auth → profile → staff_auth → menu_admin → menu_public → cart; imports grouped by phase with blank line.

## 7. Full verification

- [x] 7.1 **VERIFY** [core-api] `docker compose exec core-api pytest tests/ -q` — zero failures; all RED tests now green, no Phase 1 regression.
- [x] 7.2 **VERIFY** [shared] `docker compose exec core-api pytest tests/ -k "enums_menu" -q` — three tests green.
- [x] 7.3 **VERIFY** [core-api] Hit `GET /openapi.json` — tags `menu-admin`, `menu-public`, `cart` present; no paths under those prefixes.
- [x] 7.4 **VERIFY** [database] `docker compose exec core-api alembic -c /app/database/alembic.ini current` → head is `0004`.
- [x] 7.5 **VERIFY** [database] `alembic downgrade -1 && alembic upgrade head` round-trip — clean.
