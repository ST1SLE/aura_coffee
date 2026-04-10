# menu-admin-crud Specification

## Purpose

Admin-facing CRUD and stop-list endpoints for menu categories, items, modifiers, and size options under `/api/v1/admin/menu/...`, with RBAC enforcement (admin mutates, barista may list and toggle availability) and all write logic isolated in a `MenuAdminService`.

_References: PDD §3 (Domain Language — Category, Menu Item, Modifier, Size Option, Stop List), PDD §5.2 (Menu table group), PDD §7.1 Phase 6 (Admin Panel), INV-002 (auth on mutations), INV-006 (stop list), INV-010 (role isolation)._

## Requirements

### Requirement: Admin categories CRUD

The system SHALL expose admin endpoints to create, list, update, and delete menu categories under `/api/v1/admin/menu/categories`. Requests SHALL use the `CategoryCreate` / `CategoryUpdate` / `CategoryResponse` Pydantic schemas already defined in `core_api.schemas.menu`. Only role `admin` SHALL be allowed to mutate categories; roles `admin` and `barista` SHALL be allowed to list them. All other roles (including `customer` and `courier`) SHALL receive HTTP 403.

#### Scenario: Admin creates a category
- **WHEN** an authenticated `admin` sends `POST /api/v1/admin/menu/categories` with a valid `CategoryCreate` body
- **THEN** the response SHALL be HTTP 201 with a `CategoryResponse` body whose `id` is assigned by the database and whose fields match the request

#### Scenario: Admin updates a category
- **WHEN** an authenticated `admin` sends `PUT /api/v1/admin/menu/categories/{id}` with a `CategoryUpdate` body against an existing category
- **THEN** the response SHALL be HTTP 200 with the updated `CategoryResponse` reflecting only the supplied fields

#### Scenario: Admin deletes an empty category
- **WHEN** an authenticated `admin` sends `DELETE /api/v1/admin/menu/categories/{id}` against a category with no referencing menu items
- **THEN** the response SHALL be HTTP 204 and the row SHALL be removed

#### Scenario: Delete of referenced category is rejected
- **WHEN** an authenticated `admin` sends `DELETE /api/v1/admin/menu/categories/{id}` against a category with at least one referencing `menu_items` row
- **THEN** the response SHALL be HTTP 409 and the row SHALL NOT be removed (ON DELETE RESTRICT from `menu-schema`)

#### Scenario: Barista cannot create or delete categories
- **WHEN** an authenticated `barista` sends `POST /api/v1/admin/menu/categories` or `DELETE /api/v1/admin/menu/categories/{id}`
- **THEN** the response SHALL be HTTP 403 and no row SHALL be created or deleted

#### Scenario: Customer is blocked entirely
- **WHEN** an authenticated `customer` sends any request under `/api/v1/admin/menu/categories`
- **THEN** the response SHALL be HTTP 403

### Requirement: Admin menu items CRUD

The system SHALL expose admin endpoints to create, list, read, update, and delete menu items under `/api/v1/admin/menu/items` using the `MenuItemCreate` / `MenuItemUpdate` / `MenuItemResponse` schemas. Only role `admin` SHALL be allowed to create, update, or delete items; roles `admin` and `barista` SHALL be allowed to list and read items. All responses SHALL include the computed `availability` field (`AVAILABLE` / `STOP_LIST` / `ARCHIVED`) from `MenuItemResponse`.

#### Scenario: Admin creates a menu item in an existing category
- **WHEN** an authenticated `admin` sends `POST /api/v1/admin/menu/items` with a `MenuItemCreate` referring to an existing `category_id`
- **THEN** the response SHALL be HTTP 201 with a `MenuItemResponse` whose `availability` field is `AVAILABLE` by default

#### Scenario: Create with non-existent category is rejected
- **WHEN** an authenticated `admin` sends `POST /api/v1/admin/menu/items` with a `category_id` that does not exist
- **THEN** the response SHALL be HTTP 404 or 409 and no row SHALL be created

#### Scenario: Admin archives a menu item via PUT
- **WHEN** an authenticated `admin` sends `PUT /api/v1/admin/menu/items/{id}` with body `{"archived": true}`
- **THEN** the response SHALL be HTTP 200 and the returned `MenuItemResponse.availability` SHALL equal `ARCHIVED`

#### Scenario: Delete an item
- **WHEN** an authenticated `admin` sends `DELETE /api/v1/admin/menu/items/{id}` against an existing item not referenced elsewhere
- **THEN** the response SHALL be HTTP 204

#### Scenario: Barista may list items but not mutate them
- **WHEN** an authenticated `barista` sends `GET /api/v1/admin/menu/items`
- **THEN** the response SHALL be HTTP 200 with a list of `MenuItemResponse`
- **AND WHEN** the same `barista` sends `DELETE /api/v1/admin/menu/items/{id}`
- **THEN** the response SHALL be HTTP 403

### Requirement: Admin modifiers CRUD

The system SHALL expose admin endpoints to create, list, update, and delete modifiers under `/api/v1/admin/menu/modifiers` using the `ModifierCreate` / `ModifierUpdate` / `ModifierResponse` schemas. Role permissions match the categories requirement: mutation is `admin`-only, listing is allowed for `admin` and `barista`.

#### Scenario: Admin creates a modifier
- **WHEN** an authenticated `admin` sends `POST /api/v1/admin/menu/modifiers` with a valid `ModifierCreate` body
- **THEN** the response SHALL be HTTP 201 with the created `ModifierResponse`

#### Scenario: Admin updates a modifier price
- **WHEN** an authenticated `admin` sends `PUT /api/v1/admin/menu/modifiers/{id}` with body `{"price": 5000}`
- **THEN** the response SHALL be HTTP 200 with `ModifierResponse.price == 5000`

#### Scenario: Delete non-existent modifier
- **WHEN** an authenticated `admin` sends `DELETE /api/v1/admin/menu/modifiers/{id}` against an id that does not exist
- **THEN** the response SHALL be HTTP 404

### Requirement: Admin size options CRUD

The system SHALL expose admin endpoints to create, update, and delete size options under `/api/v1/admin/menu/sizes` using the `SizeOptionCreate` / `SizeOptionUpdate` / `SizeOptionResponse` schemas. Mutation SHALL be `admin`-only. There SHALL NOT be a standalone `GET` list endpoint for sizes; sizes are read through their parent `MenuItemResponse.size_options` field.

#### Scenario: Admin creates a size option for an item
- **WHEN** an authenticated `admin` sends `POST /api/v1/admin/menu/sizes` with a `SizeOptionCreate` referring to an existing `menu_item_id`
- **THEN** the response SHALL be HTTP 201 with the created `SizeOptionResponse` echoing the same `menu_item_id`

#### Scenario: Duplicate size label on the same item is rejected
- **WHEN** an authenticated `admin` creates two size options with the same `label` (e.g. `"M"`) for the same `menu_item_id`
- **THEN** the second request SHALL receive HTTP 409 (unique label per item, from `menu-schema`)

#### Scenario: Delete a size option
- **WHEN** an authenticated `admin` sends `DELETE /api/v1/admin/menu/sizes/{id}` against an existing size
- **THEN** the response SHALL be HTTP 204

### Requirement: Menu item stop-list toggle

The system SHALL expose `PATCH /api/v1/admin/menu/items/{item_id}/availability` accepting a body of shape `{ "available": bool }` and returning the full updated `MenuItemResponse`. This endpoint SHALL set `menu_items.available` and SHALL NOT modify any other column. Roles `admin` and `barista` SHALL be allowed to call it; all other roles SHALL receive HTTP 403. This endpoint exists specifically to implement INV-006 (stop list) during a shift.

#### Scenario: Barista stop-lists an item
- **WHEN** an authenticated `barista` sends `PATCH /api/v1/admin/menu/items/{id}/availability` with body `{"available": false}`
- **THEN** the response SHALL be HTTP 200 and the returned `MenuItemResponse.availability` SHALL equal `STOP_LIST`

#### Scenario: Barista un-stop-lists an item
- **WHEN** an authenticated `barista` sends the same endpoint with body `{"available": true}` against an item previously stop-listed
- **THEN** the response SHALL be HTTP 200 and the returned `availability` SHALL equal `AVAILABLE`

#### Scenario: Archived item stays archived when toggling availability
- **WHEN** an authenticated `barista` sends `{"available": true}` against an item with `archived == true`
- **THEN** the underlying `archived` flag SHALL remain `true` and the returned `availability` SHALL equal `ARCHIVED` (per `MenuItemResponse.availability` precedence)

#### Scenario: Customer is blocked from the stop-list endpoint
- **WHEN** an authenticated `customer` sends `PATCH /api/v1/admin/menu/items/{id}/availability`
- **THEN** the response SHALL be HTTP 403

#### Scenario: Missing item returns 404
- **WHEN** any authorized caller sends the endpoint with a non-existent `item_id`
- **THEN** the response SHALL be HTTP 404

### Requirement: Modifier stop-list toggle

The system SHALL expose `PATCH /api/v1/admin/menu/modifiers/{modifier_id}/availability` accepting a body of shape `{ "available": bool }` and returning the full updated `ModifierResponse`. Roles `admin` and `barista` SHALL be allowed to call it; all other roles SHALL receive HTTP 403.

#### Scenario: Barista stop-lists a modifier
- **WHEN** an authenticated `barista` sends `PATCH /api/v1/admin/menu/modifiers/{id}/availability` with body `{"available": false}`
- **THEN** the response SHALL be HTTP 200 and the returned `ModifierResponse.available` SHALL be `false`

#### Scenario: Courier cannot toggle modifier availability
- **WHEN** an authenticated `courier` sends `PATCH /api/v1/admin/menu/modifiers/{id}/availability`
- **THEN** the response SHALL be HTTP 403

### Requirement: Availability PATCH uses dedicated schema

The system SHALL define a Pydantic model `AvailabilityPatch` in `core_api.schemas.menu` with a single required field `available: bool` and no other fields. Both the item and modifier stop-list endpoints SHALL accept this exact model as their request body. Sending extra fields SHALL be rejected with HTTP 422.

#### Scenario: Extra field in availability body is rejected
- **WHEN** an authenticated `admin` sends `PATCH .../items/{id}/availability` with body `{"available": false, "price": 0}`
- **THEN** the response SHALL be HTTP 422 and the item SHALL NOT be modified

### Requirement: Admin menu write logic lives in a service module

The system SHALL place all write logic (category / item / modifier / size creation, update, delete, and availability toggling) in a new module `core_api.services.menu_admin` exposing a `MenuAdminService` class that takes an SQLAlchemy `Session` in its constructor. `core_api.routers.menu_admin` SHALL contain only request/response wiring and SHALL call into `MenuAdminService`. The router module SHALL NOT execute raw SQLAlchemy statements directly.

#### Scenario: Router delegates to service
- **WHEN** inspecting `core_api.routers.menu_admin`
- **THEN** every endpoint function SHALL obtain a `MenuAdminService(db)` instance via DI and delegate mutations to its methods; the router file SHALL contain no `db.add(...)`, `db.delete(...)`, or `db.commit()` calls

### Requirement: Admin menu routes are protected via RBAC matrix

The system SHALL register the new `/api/v1/admin/menu/...` routes in `core_api.rbac_matrix.ROUTE_MATRIX`. Mutating routes on categories, items, modifiers, and sizes SHALL map to `{admin}`. The two `PATCH .../availability` routes SHALL map to `{admin, barista}`. The admin read endpoints (`GET /categories`, `GET /items`, `GET /items/{id}`, `GET /modifiers`) SHALL map to `{admin, barista}`. No admin menu route SHALL appear in `PUBLIC_ROUTES`.

#### Scenario: Unauthenticated request to any admin menu route is rejected
- **WHEN** a request without an `Authorization` header hits any `/api/v1/admin/menu/...` path
- **THEN** the response SHALL be HTTP 401

#### Scenario: Availability endpoints are the only menu routes barista can mutate
- **WHEN** inspecting `ROUTE_MATRIX` for every entry under `/api/v1/admin/menu`
- **THEN** the only entries whose role set contains `"barista"` AND whose HTTP method is not `GET` SHALL be the two `PATCH .../availability` entries

### Requirement: Admin items list supports server-side category filtering

The `GET /api/v1/admin/menu/items` endpoint SHALL accept an optional `category_id` query parameter of type positive integer (`gt=0`). When the parameter is omitted, the endpoint SHALL return all menu items ordered by `(sort_order, id)` as before. When the parameter is supplied, the endpoint SHALL return only menu items whose `category_id` column equals the supplied value, preserving the same ordering. Supplying a `category_id` that does not exist SHALL yield HTTP 404 with detail `"category not found"`. Supplying a non-integer or non-positive value SHALL yield HTTP 422 via Pydantic validation. The parameter SHALL NOT alter RBAC: roles `admin` and `barista` may call the endpoint with or without the filter; all other roles SHALL continue to receive HTTP 403.

_References: PDD §5.2 (Menu tables), PDD §7.1 Phase 6 (Admin Panel). Extends the existing "Admin menu items CRUD" requirement without altering its existing scenarios._

#### Scenario: No filter returns all items
- **WHEN** an authenticated `admin` sends `GET /api/v1/admin/menu/items` with no query string
- **AND** the database contains items across multiple categories
- **THEN** the response SHALL be HTTP 200 and the list SHALL contain every seeded item

#### Scenario: Filter by existing category returns only matching items
- **GIVEN** two categories A and B each with two items
- **WHEN** an authenticated `admin` sends `GET /api/v1/admin/menu/items?category_id=<A.id>`
- **THEN** the response SHALL be HTTP 200 and the list SHALL contain exactly the two items belonging to category A and none from category B

#### Scenario: Filter by nonexistent category returns 404
- **WHEN** an authenticated `admin` sends `GET /api/v1/admin/menu/items?category_id=999999` and no category with that id exists
- **THEN** the response SHALL be HTTP 404 with detail `"category not found"`

#### Scenario: Filter by non-positive id is rejected by validation
- **WHEN** an authenticated `admin` sends `GET /api/v1/admin/menu/items?category_id=0`
- **THEN** the response SHALL be HTTP 422

#### Scenario: Filter by non-integer id is rejected by validation
- **WHEN** an authenticated `admin` sends `GET /api/v1/admin/menu/items?category_id=abc`
- **THEN** the response SHALL be HTTP 422

#### Scenario: Barista may also filter
- **WHEN** an authenticated `barista` sends `GET /api/v1/admin/menu/items?category_id=<A.id>` against an existing category
- **THEN** the response SHALL be HTTP 200 with the filtered list
