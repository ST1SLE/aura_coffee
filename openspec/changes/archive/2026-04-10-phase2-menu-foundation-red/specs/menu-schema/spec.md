## ADDED Requirements

_References: PDD §3 (Domain Language — Menu), PDD §5.2 (Menu table group), PDD §5.4 (Indexes), INV-006 (stop list), INV-015 (secrets)._

### Requirement: Categories table exists with PDD §5.2 columns

The system SHALL provide a `categories` table with columns `id`, `type`, `name_ru`, `name_en`, `sort_order`, `is_visible`, `created_at`, `updated_at`. The `type` column SHALL be a PostgreSQL enum `category_type` with values `drink`, `food`, `merch`, `modifier` matching PDD §3.

#### Scenario: Migration creates categories table
- **WHEN** `alembic upgrade head` runs against a database at revision `0003_staff_accounts`
- **THEN** table `categories` exists with all listed columns, `type` is a `category_type` enum, and the PG enum contains exactly `drink`, `food`, `merch`, `modifier`

#### Scenario: Downgrade removes categories cleanly
- **WHEN** `alembic downgrade -1` runs against revision `0004_menu_tables`
- **THEN** table `categories` no longer exists and enum `category_type` no longer exists

### Requirement: Menu items table exists with PDD §5.2 columns and stop-list flags

The system SHALL provide a `menu_items` table with columns `id`, `category_id` (FK → `categories.id` ON DELETE RESTRICT), `name_ru`, `name_en`, `description_ru` (nullable), `description_en` (nullable), `base_price` (integer kopecks, `>= 0`), `image_url` (nullable), `available` (bool, default TRUE), `archived` (bool, default FALSE), `sort_order`, `created_at`, `updated_at`. The `available` flag SHALL represent stop-list state per INV-006; `archived` SHALL represent permanent removal per PDD §5.2 notes.

#### Scenario: Prices are stored as non-negative integers
- **WHEN** inserting a `menu_items` row with `base_price = -1`
- **THEN** the database SHALL reject the insert via a `CHECK` constraint

#### Scenario: Category FK restricts deletion
- **WHEN** attempting to delete a `categories` row referenced by at least one `menu_items` row
- **THEN** the database SHALL reject the delete (ON DELETE RESTRICT)

### Requirement: Size options table with unique label per item

The system SHALL provide a `size_options` table with columns `id`, `menu_item_id` (FK → `menu_items.id` ON DELETE CASCADE), `label` (enum `size_label` with values `S`, `M`, `L` per PDD §3), `price` (integer kopecks, `>= 0`), `available` (bool, default TRUE). A unique constraint SHALL exist on (`menu_item_id`, `label`).

#### Scenario: Duplicate label on same item is rejected
- **WHEN** inserting two `size_options` rows with the same `menu_item_id` and `label = 'M'`
- **THEN** the second insert SHALL fail with a unique-constraint violation

#### Scenario: Deleting a menu item cascades sizes
- **WHEN** a `menu_items` row is deleted
- **THEN** all `size_options` rows with that `menu_item_id` SHALL be deleted

### Requirement: Modifiers table matches PDD §5.2

The system SHALL provide a `modifiers` table with columns `id`, `name_ru`, `name_en`, `price` (integer kopecks, `>= 0`), `available` (bool, default TRUE), `sort_order`. This strictly matches PDD §5.2 — no grouping, no selection-rule fields.

#### Scenario: Negative price is rejected
- **WHEN** inserting a `modifiers` row with `price = -1`
- **THEN** the database SHALL reject the insert via a `CHECK` constraint

#### Scenario: Default availability is TRUE
- **WHEN** inserting a `modifiers` row without specifying `available`
- **THEN** the stored row SHALL have `available = TRUE`

### Requirement: Menu item ↔ modifier M:N junction

The system SHALL provide a `menu_item_modifiers` junction table with composite primary key (`menu_item_id`, `modifier_id`) and both foreign keys using `ON DELETE CASCADE`. This matches PDD §5.2.

#### Scenario: Deleting a modifier removes its junction rows
- **WHEN** a `modifiers` row is deleted
- **THEN** all matching `menu_item_modifiers` rows SHALL be deleted automatically

### Requirement: PDD §5.4 menu indexes exist

The system SHALL create the indexes listed in PDD §5.4 for menu tables: (a) `menu_items(category_id, sort_order)` for ordered category display and (b) a partial index on `menu_items(available, archived) WHERE archived = FALSE` for active menu queries. An additional index SHALL exist on `size_options(menu_item_id)`.

#### Scenario: Active-menu partial index is present
- **WHEN** inspecting the `menu_items` table after migration
- **THEN** a partial index with predicate `archived = false` SHALL be present

### Requirement: SQLAlchemy models mirror the schema

The system SHALL expose SQLAlchemy 2.0 models at `core_api.models.menu` (`Category`, `MenuItem`, `SizeOption`, `Modifier`) with relationships: `Category.menu_items`, `MenuItem.category`, `MenuItem.size_options`, `MenuItem.modifiers` (via secondary `menu_item_modifiers`), `Modifier.menu_items`. Models SHALL import enum types from `shared.enums`.

#### Scenario: Relationships resolve in a session
- **WHEN** a `MenuItem` is created with two `SizeOption`s and two `Modifier`s via the M:N relationship
- **THEN** `menu_item.size_options` SHALL yield both sizes and `menu_item.modifiers` SHALL yield both modifiers after flush

### Requirement: Pydantic v2 schemas expose Create / Update / Response

The system SHALL provide Pydantic v2 schemas at `core_api.schemas.menu` with, for each of `Category`, `MenuItem`, `SizeOption`, `Modifier`: a `Base`, `Create`, `Update` (all fields optional), and `Response` class. `Response` classes SHALL set `model_config = ConfigDict(from_attributes=True)` to convert from SQLAlchemy models. Price fields SHALL use `Field(ge=0)`. Bilingual fields SHALL be `name_ru: str` and `name_en: str` (and equivalent for descriptions). The `MenuItemResponse` SHALL include a derived `availability: MenuItemAvailability` computed from `available` and `archived`.

#### Scenario: MenuItemResponse round-trips from ORM
- **WHEN** a `MenuItem` ORM instance with populated relationships is passed to `MenuItemResponse.model_validate(instance)`
- **THEN** the schema SHALL contain all fields including nested `size_options` and `modifiers`, with `availability` derived correctly (`archived` → `archived`, else `stop_list` if `available = false`, else `available`)

#### Scenario: Negative price is rejected by Pydantic
- **WHEN** constructing `MenuItemCreate(base_price=-10, ...)`
- **THEN** Pydantic SHALL raise `ValidationError`

### Requirement: Shared enums for CategoryType, SizeLabel, MenuItemAvailability

The `packages/shared/src/shared/enums.py` module SHALL export `CategoryType(str, Enum)` with members `DRINK="drink"`, `FOOD="food"`, `MERCH="merch"`, `MODIFIER="modifier"`; `SizeLabel(str, Enum)` with members `S="S"`, `M="M"`, `L="L"`; and `MenuItemAvailability(str, Enum)` with members `AVAILABLE="available"`, `STOP_LIST="stop_list"`, `ARCHIVED="archived"`. Values SHALL match PDD §3 exactly.

#### Scenario: Enum values match the PG enums used in migration
- **WHEN** a migration creates PG enum `category_type`
- **THEN** its labels SHALL equal `[CategoryType.DRINK.value, CategoryType.FOOD.value, CategoryType.MERCH.value, CategoryType.MODIFIER.value]` in that order
