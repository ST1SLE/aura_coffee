## ADDED Requirements

### Requirement: Admin menu item modifier set replacement

The system SHALL expose `PUT /api/v1/admin/menu/items/{item_id}/modifiers` accepting a body of shape `{ "modifier_ids": list[int] }` and returning the full updated `MenuItemResponse`. This endpoint SHALL replace the complete set of modifiers linked to the addressed menu item with the supplied list via the existing `menu_item_modifiers` junction table. Only role `admin` SHALL be allowed to call it; all other roles (including `barista`, `customer`, `courier`) SHALL receive HTTP 403.

The request body SHALL be validated by a new Pydantic model `MenuItemModifierSet` defined in `core_api.schemas.menu` with a single required field `modifier_ids: list[int]`. Duplicate ids in the input list SHALL be deduplicated server-side and SHALL NOT cause an error. An empty list SHALL be accepted and SHALL detach every modifier from the item.

If any id in `modifier_ids` does not correspond to an existing `Modifier` row, the response SHALL be HTTP 422 and the item's modifier set SHALL NOT be modified. If the addressed `item_id` does not exist, the response SHALL be HTTP 404.

The response `MenuItemResponse` SHALL reflect the new modifier set, freshly loaded via the existing `get_item` path so that `size_options` and `modifiers` are both eager-loaded.

#### Scenario: Admin attaches modifiers to an item
- **WHEN** an authenticated `admin` sends `PUT /api/v1/admin/menu/items/{id}/modifiers` with body `{"modifier_ids": [1, 2, 3]}` against an existing item
- **THEN** the response SHALL be HTTP 200 with a `MenuItemResponse` whose `modifiers` array contains exactly the three modifiers with ids `1`, `2`, `3`

#### Scenario: Admin detaches all modifiers from an item
- **WHEN** an authenticated `admin` sends the endpoint with body `{"modifier_ids": []}` against an item that previously had modifiers
- **THEN** the response SHALL be HTTP 200 with `MenuItemResponse.modifiers == []` and the underlying `menu_item_modifiers` rows for that item SHALL be removed

#### Scenario: Replacing the set swaps modifiers
- **WHEN** an authenticated `admin` sends body `{"modifier_ids": [5]}` against an item currently linked to modifiers `[1, 2]`
- **THEN** the response SHALL be HTTP 200, the returned `modifiers` array SHALL contain only the modifier with id `5`, and the rows for modifiers `1` and `2` in `menu_item_modifiers` for this item SHALL be removed

#### Scenario: Unknown modifier id returns 422
- **WHEN** an authenticated `admin` sends body `{"modifier_ids": [1, 99999]}` where `99999` does not exist
- **THEN** the response SHALL be HTTP 422, the item's modifier set SHALL remain unchanged from before the call, and the response detail SHALL identify `99999` as the offending id

#### Scenario: Unknown item id returns 404
- **WHEN** an authenticated `admin` sends the endpoint against a non-existent `item_id`
- **THEN** the response SHALL be HTTP 404 and no `menu_item_modifiers` rows SHALL be created or removed

#### Scenario: Duplicate modifier ids are deduplicated
- **WHEN** an authenticated `admin` sends body `{"modifier_ids": [1, 1, 2]}`
- **THEN** the response SHALL be HTTP 200, the returned `modifiers` array SHALL contain exactly the modifiers with ids `1` and `2` (each once), and the underlying `menu_item_modifiers` SHALL contain exactly one row per distinct id for this item

#### Scenario: Barista cannot attach modifiers
- **WHEN** an authenticated `barista` sends `PUT /api/v1/admin/menu/items/{id}/modifiers` with any body
- **THEN** the response SHALL be HTTP 403 and no rows SHALL be created or removed

#### Scenario: Customer is blocked
- **WHEN** an authenticated `customer` sends the endpoint
- **THEN** the response SHALL be HTTP 403

#### Scenario: Unauthenticated request is rejected
- **WHEN** a request without an `Authorization` header hits `PUT /api/v1/admin/menu/items/{id}/modifiers`
- **THEN** the response SHALL be HTTP 401

## MODIFIED Requirements

### Requirement: Admin menu routes are protected via RBAC matrix

**Previously:** The RBAC matrix entries for `/api/v1/admin/menu/...` did not include a route for modifier attachment (no such route existed), and the modified-routes invariant ("the only entries whose role set contains `"barista"` AND whose HTTP method is not `GET` SHALL be the two `PATCH .../availability` entries") was stated over the closed set of existing mutating routes.

**Now:** The system SHALL register the new `PUT /api/v1/admin/menu/items/{item_id}/modifiers` route in `core_api.rbac_matrix.ROUTE_MATRIX` with role set `{"admin"}`. The invariant still holds: after this change the ONLY mutating routes under `/api/v1/admin/menu/...` whose role set contains `"barista"` SHALL be the two `PATCH .../availability` entries. No admin menu route SHALL appear in `PUBLIC_ROUTES`.

#### Scenario: Unauthenticated request to any admin menu route is rejected
- **WHEN** a request without an `Authorization` header hits any `/api/v1/admin/menu/...` path (including the new modifier set-replacement route)
- **THEN** the response SHALL be HTTP 401

#### Scenario: Availability endpoints are the only menu routes barista can mutate
- **WHEN** inspecting `ROUTE_MATRIX` for every entry under `/api/v1/admin/menu`
- **THEN** the only entries whose role set contains `"barista"` AND whose HTTP method is not `GET` SHALL be the two `PATCH .../availability` entries; the new `PUT .../items/{item_id}/modifiers` entry SHALL map to `{"admin"}` only

#### Scenario: Admin can call the new modifier route
- **WHEN** an authenticated `admin` sends `PUT /api/v1/admin/menu/items/{id}/modifiers` with a valid body
- **THEN** the RBAC layer SHALL permit the request and pass it through to the router handler
