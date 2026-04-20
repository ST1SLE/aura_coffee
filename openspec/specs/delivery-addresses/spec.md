# delivery-addresses Specification

## Purpose
TBD - created by archiving change delivery-addresses-red. Update Purpose after archive.
## Requirements
### Requirement: DeliveryAddress model exists in shared package

The system SHALL expose `shared.models.delivery_address.DeliveryAddress` (re-exported from `shared.models`) as a SQLAlchemy model mapped to table `delivery_addresses` with columns: `id` (UUID primary key), `user_id` (UUID, FK to `users.id`, `ON DELETE CASCADE` per INV-013), `label` (str, non-null), `address_text` (str, non-null), `lat` (float, non-null), `lon` (float, non-null), `apartment` / `entrance` / `floor` / `comment` (str, nullable), `is_default` (bool, non-null, default `false`), `created_at` and `updated_at` (`TIMESTAMPTZ`, server default `now()`). The table SHALL carry a partial unique index on `(user_id)` where `is_default = true` and a non-unique index on `(user_id)` for fast list queries.

#### Scenario: Importing the model succeeds
- **WHEN** Python evaluates `from shared.models import DeliveryAddress`
- **THEN** the import SHALL succeed and the resulting class SHALL have `__tablename__ == "delivery_addresses"`

#### Scenario: At most one default per user
- **GIVEN** two rows exist for `user_id = U` with `is_default = true`
- **WHEN** the DB attempts to commit
- **THEN** the partial unique index SHALL raise a unique-constraint violation and the transaction SHALL be aborted

#### Scenario: Deleting the user cascades to addresses (INV-013)
- **GIVEN** `delivery_addresses` rows referencing `user_id = U`
- **WHEN** the `users` row with `id = U` is deleted
- **THEN** all rows for that user SHALL be removed by the database and no orphan rows SHALL remain

### Requirement: CRUD router /api/v1/profile/addresses authorized for Customer only

The system SHALL expose `core_api.routers.delivery_addresses.router` mounted under `/api/v1/profile/addresses` on the FastAPI app. The router SHALL expose exactly four operations: `GET /`, `POST /`, `PATCH /{address_id}`, `DELETE /{address_id}`. Each operation SHALL require a valid Customer JWT (INV-002, INV-010). Staff roles (`admin`, `barista`, `courier`) SHALL receive HTTP `403`. Unauthenticated callers SHALL receive HTTP `401`. The four routes SHALL be present in `core_api.rbac_matrix.ROUTE_MATRIX` with value exactly `{CUSTOMER}` and SHALL NOT appear in `PUBLIC_ROUTES`.

#### Scenario: Four routes mounted
- **WHEN** the test client fetches `/openapi.json`
- **THEN** `paths` SHALL contain `/api/v1/profile/addresses` with `get` and `post` keys AND `/api/v1/profile/addresses/{address_id}` with `patch` and `delete` keys

#### Scenario: Unauthenticated request is rejected
- **WHEN** a caller issues `GET /api/v1/profile/addresses` without an `Authorization` header
- **THEN** the response status SHALL be `401`

#### Scenario: Non-customer role is forbidden
- **WHEN** an authenticated `barista`, `admin`, or `courier` issues any of the four operations
- **THEN** the response status SHALL be `403`

#### Scenario: RBAC matrix entries present
- **WHEN** tests import `ROUTE_MATRIX` from `core_api.rbac_matrix`
- **THEN** keys `("GET", "/api/v1/profile/addresses")`, `("POST", "/api/v1/profile/addresses")`, `("PATCH", "/api/v1/profile/addresses/{address_id}")`, `("DELETE", "/api/v1/profile/addresses/{address_id}")` SHALL all map to `{CUSTOMER}`

### Requirement: GET returns only the caller's addresses

`GET /api/v1/profile/addresses` SHALL return a JSON array of the authenticated Customer's saved addresses ordered with `is_default=true` first, then by `created_at` ascending. The response SHALL NOT leak rows belonging to other users. An empty list SHALL return HTTP `200` with `[]`.

#### Scenario: Empty list for new user
- **GIVEN** the Customer has no saved addresses
- **WHEN** `GET /api/v1/profile/addresses` is invoked
- **THEN** the response SHALL be `200` with body `[]`

#### Scenario: Default address first, then insertion order
- **GIVEN** the Customer has three saved addresses with exactly one marked `is_default=true`
- **WHEN** `GET /api/v1/profile/addresses` is invoked
- **THEN** the response body SHALL be a list of three items with the default address at index `0`

#### Scenario: Other users' addresses are not leaked
- **GIVEN** user A has saved addresses and user B has saved addresses
- **WHEN** user A calls `GET /api/v1/profile/addresses`
- **THEN** every element's identifiers SHALL belong to user A

### Requirement: POST validates radius via Haversine (PDD §7.3 step 3, INV-008)

`POST /api/v1/profile/addresses` SHALL require a JSON body containing `label`, `address_text`, `lat`, `lon` (optional `apartment`, `entrance`, `floor`, `comment`, `is_default`). The server SHALL compute the Haversine distance between `(lat, lon)` and `(ShopSettings.shop_lat, ShopSettings.shop_lon)` and SHALL reject the request with HTTP `422` when `distance_km > ShopSettings.delivery_radius_km`. On success the response SHALL be HTTP `201` with the created row (including `id`, `created_at`).

#### Scenario: Happy path creates the row
- **GIVEN** `(lat, lon)` within the delivery radius
- **WHEN** the Customer POSTs a valid body
- **THEN** the response SHALL be `201`, a new row SHALL exist in `delivery_addresses`, and the body SHALL echo `id`, `label`, `lat`, `lon`, `is_default`

#### Scenario: Out-of-radius address is rejected
- **GIVEN** `(lat, lon)` outside the delivery radius
- **WHEN** the Customer POSTs the body
- **THEN** the response SHALL be `422` and no row SHALL be inserted

#### Scenario: Malformed body is rejected
- **WHEN** the POST body is missing `label`, `address_text`, `lat`, or `lon`
- **THEN** the response SHALL be `422`

### Requirement: PATCH updates own address and atomically re-assigns default

`PATCH /api/v1/profile/addresses/{address_id}` SHALL accept a partial JSON body with any subset of mutable fields (`label`, `address_text`, `apartment`, `entrance`, `floor`, `comment`, `is_default`). When the request sets `is_default=true`, the server SHALL, in a single DB transaction, demote the previously-default row (if any) for the same user and promote the patched row. An `address_id` owned by a different user SHALL return HTTP `404` (never `403`). Changing `lat`/`lon` via PATCH is out of scope for this requirement (a re-geocoding flow belongs to a separate feature).

#### Scenario: Update label
- **WHEN** the owner PATCHes `{"label": "Дача"}`
- **THEN** the response SHALL be `200` and the row's `label` SHALL be `"Дача"`

#### Scenario: Promoting a new default demotes the previous one
- **GIVEN** user A has two saved addresses `X` (default=true) and `Y` (default=false)
- **WHEN** user A PATCHes `Y` with `{"is_default": true}`
- **THEN** after commit `Y.is_default` SHALL be `true`, `X.is_default` SHALL be `false`, and exactly one row for user A SHALL satisfy `is_default=true`

#### Scenario: Foreign address returns 404
- **GIVEN** address `Z` belongs to user B
- **WHEN** user A PATCHes `Z`
- **THEN** the response SHALL be `404` (not `403`) and row `Z` SHALL be unchanged

### Requirement: DELETE removes own address, 404 on foreign

`DELETE /api/v1/profile/addresses/{address_id}` SHALL delete the addressed row when it belongs to the caller and return HTTP `204` with no body. A non-existent or foreign `address_id` SHALL return HTTP `404`. Deleting an address SHALL NOT alter any `orders.delivery_address_snapshot` — past orders remain immutable per INV-014.

#### Scenario: Delete own address
- **WHEN** the owner DELETEs `address_id`
- **THEN** the response SHALL be `204` and the row SHALL no longer exist in `delivery_addresses`

#### Scenario: Delete foreign address returns 404
- **GIVEN** address `Z` belongs to user B
- **WHEN** user A DELETEs `Z`
- **THEN** the response SHALL be `404` and row `Z` SHALL still exist

#### Scenario: Delete does not alter past order snapshots (INV-014)
- **GIVEN** an `orders` row exists with `delivery_address_snapshot` previously copied from address `W`
- **WHEN** user A DELETEs `W`
- **THEN** the `orders.delivery_address_snapshot` value SHALL be byte-identical to its pre-delete value

