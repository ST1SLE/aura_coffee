## ADDED Requirements

_References: PDD §5.2 `orders.delivery_address_snapshot`, §7.3 step 3 (Haversine re-check), INV-008, INV-013, INV-014._

### Requirement: CreateOrderRequest accepts optional delivery_address_id

The Pydantic schema `core_api.schemas.order.CreateOrderRequest` SHALL expose an additional optional field `delivery_address_id: UUID | None = None`. The existing inline `delivery_address: DeliveryAddress | None` field SHALL remain unchanged for backward compatibility. Both fields SHALL default to `None`.

#### Scenario: Schema accepts only delivery_address (legacy path)
- **WHEN** the body is `{"type": "delivery", "delivery_address": {...inline...}}`
- **THEN** `CreateOrderRequest.model_validate` SHALL return a valid instance with `delivery_address_id is None`

#### Scenario: Schema accepts only delivery_address_id (new path)
- **WHEN** the body is `{"type": "delivery", "delivery_address_id": "<uuid>"}`
- **THEN** `CreateOrderRequest.model_validate` SHALL return a valid instance with `delivery_address is None`

### Requirement: XOR between delivery_address and delivery_address_id for type=DELIVERY

For `type = DELIVERY`, `CreateOrderRequest` SHALL require exactly one of `{delivery_address, delivery_address_id}` to be set. Setting both or neither SHALL raise a Pydantic `ValidationError`, which FastAPI SHALL surface as HTTP `422`. For `type = PICKUP`, both fields SHOULD be `None`; if either is set the server MAY ignore it (no assertion).

#### Scenario: Both fields set is rejected
- **WHEN** the body has both `delivery_address` and `delivery_address_id` with `type=delivery`
- **THEN** validation SHALL fail and `POST /api/v1/orders` SHALL return `422`

#### Scenario: Neither field set is rejected for delivery
- **WHEN** the body has `type=delivery` and neither `delivery_address` nor `delivery_address_id`
- **THEN** validation SHALL fail and `POST /api/v1/orders` SHALL return `422`

#### Scenario: Pickup without either field is accepted
- **WHEN** the body is `{"type": "pickup"}` with neither delivery field set
- **THEN** validation SHALL succeed

### Requirement: Checkout loads saved address and enforces ownership

When `create_order` is invoked with `delivery_address_id` set, the service SHALL load the referenced row from `delivery_addresses` within the same DB session. If the row does not exist OR belongs to a different `user_id` than the caller, the service SHALL raise an error mapped to HTTP `404 Not Found` (never `403`, to prevent existence leaks). The service SHALL NOT call the geocoder stub when `delivery_address_id` is used — the saved row already carries validated `lat`/`lon`.

#### Scenario: Foreign address_id is rejected as 404
- **GIVEN** address `Z` belongs to user B
- **WHEN** user A calls checkout with `delivery_address_id = Z`
- **THEN** `POST /api/v1/orders` SHALL return `404` and no `orders` row SHALL be inserted

#### Scenario: Unknown address_id is rejected as 404
- **WHEN** checkout is called with a random UUID not present in `delivery_addresses`
- **THEN** `POST /api/v1/orders` SHALL return `404`

#### Scenario: Geocoder is not called for saved addresses
- **GIVEN** a valid saved address owned by the caller
- **WHEN** checkout succeeds via `delivery_address_id`
- **THEN** the geocoder stub `core_api.services.checkout.geocode_address` SHALL NOT be invoked

### Requirement: Checkout snapshots saved address immutably (INV-014)

When checkout succeeds via `delivery_address_id`, the service SHALL write `orders.delivery_address_snapshot` as a JSONB copy of the saved row's fields (`text` = `address_text`, `lat`, `lon`, `apartment`, `entrance`, `floor`, `comment`). The snapshot SHALL NOT be a foreign key — subsequent DELETE/UPDATE on the `delivery_addresses` row SHALL NOT alter the stored snapshot (INV-014).

#### Scenario: Snapshot shape matches the inline-address shape
- **WHEN** checkout succeeds via `delivery_address_id`
- **THEN** the resulting `orders.delivery_address_snapshot` SHALL contain keys `text`, `lat`, `lon`, and any of `apartment`, `entrance`, `floor`, `comment` that were non-null on the saved row

#### Scenario: Deleting the source address does not mutate the snapshot
- **GIVEN** an `orders` row created from saved address `W`
- **WHEN** the Customer deletes `W` from `delivery_addresses`
- **THEN** the `orders.delivery_address_snapshot` JSONB SHALL remain byte-identical to its value at checkout-time

### Requirement: Haversine radius re-check on every delivery checkout (INV-008)

The checkout service SHALL call `core_api.services.checkout.validate_delivery_address(lat, lon, shop_settings)` EVERY time `type = DELIVERY`, regardless of whether the address came from the inline body or a saved row. Shop settings (`delivery_radius_km`, `shop_lat`, `shop_lon`) can change between save-time and checkout-time; the re-check SHALL use the CURRENT `ShopSettings`. If the saved address is now out-of-radius, checkout SHALL reject with the existing `DeliveryRadiusError → HTTP 409` mapping.

#### Scenario: Re-check fires on the inline path
- **WHEN** `create_order` is called with inline `delivery_address`
- **THEN** `validate_delivery_address` SHALL be called at least once with the inline lat/lon

#### Scenario: Re-check fires on the saved-address path
- **WHEN** `create_order` is called with `delivery_address_id`
- **THEN** `validate_delivery_address` SHALL be called at least once with the SAVED row's lat/lon (not a cached value from save-time)

#### Scenario: Saved address now outside radius is rejected
- **GIVEN** a saved address inside the radius at save-time, but `ShopSettings.delivery_radius_km` has since been tightened
- **WHEN** checkout is invoked via `delivery_address_id`
- **THEN** `POST /api/v1/orders` SHALL return `409` and no `orders` row SHALL be inserted
