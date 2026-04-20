## ADDED Requirements

<!-- References: PDD §3 Promocode, §5.2 Promocodes, §6.6 Promocode Lifecycle, §7.1 Phase 5 item 1, §7.2 step 2, INV-010, INV-011, INV-004. -->

### Requirement: Computed state function

The system SHALL expose a pure function `compute_state(promo, now)` in `core_api.services.admin_promocodes` returning one of `'inactive'`, `'active'`, `'expired'`, `'exhausted'`. Priority SHALL be: expired > exhausted > active > inactive. No `status` column SHALL be added to the `promocodes` table (INV-011).

#### Scenario: Promocode past valid_until is expired
- **WHEN** `valid_until IS NOT NULL AND now > valid_until`
- **THEN** `compute_state` returns `'expired'` regardless of any other field

#### Scenario: Promocode at or above max_uses is exhausted
- **WHEN** `current_uses >= max_uses` AND `valid_until` is either NULL or `now <= valid_until`
- **THEN** `compute_state` returns `'exhausted'`

#### Scenario: Active promocode
- **WHEN** `is_active = true`, not expired, not exhausted, and (`valid_from IS NULL` OR `now >= valid_from`)
- **THEN** `compute_state` returns `'active'`

#### Scenario: Inactive fallback
- **WHEN** no expired/exhausted/active branch applies
- **THEN** `compute_state` returns `'inactive'`

### Requirement: Admin-only RBAC surface

The system SHALL register exactly six endpoints under `/api/v1/admin/promocodes`: `POST /`, `GET /`, `GET /{promocode_id}`, `PATCH /{promocode_id}`, `POST /{promocode_id}/activate`, `POST /{promocode_id}/deactivate`. Each SHALL be permitted for ADMIN only (INV-010). BARISTA, COURIER, and CUSTOMER SHALL receive 403. Requests without a valid token SHALL receive 401. None of these routes SHALL appear in `PUBLIC_ROUTES`.

#### Scenario: Admin can list promocodes
- **WHEN** an ADMIN calls `GET /api/v1/admin/promocodes`
- **THEN** the response status is 200

#### Scenario: Barista cannot access promocode surface
- **WHEN** a BARISTA calls any of the six endpoints
- **THEN** the response status is 403

#### Scenario: Courier cannot access promocode surface
- **WHEN** a COURIER calls any of the six endpoints
- **THEN** the response status is 403

#### Scenario: Customer cannot access promocode surface
- **WHEN** a CUSTOMER calls any of the six endpoints
- **THEN** the response status is 403

#### Scenario: Missing token
- **WHEN** a request with no Authorization header hits any of the six endpoints
- **THEN** the response status is 401

### Requirement: Create promocode

The system SHALL accept `POST /api/v1/admin/promocodes` with a `PromocodeCreate` body and persist a new promocode with `is_active = false` and `current_uses = 0`. The `code` field SHALL be canonicalized server-side by uppercasing before validation and persistence; it SHALL match `^[A-Z0-9_-]+$` after uppercasing and have length 1..64. `discount_value` SHALL be a positive integer; for `discount_type='percent'` it SHALL be ≤ 100; for `discount_type='fixed_amount'` it SHALL be expressed in kopecks. `min_order_amount` SHALL default to 0. If both `valid_from` and `valid_until` are set, `valid_from < valid_until`. If both `max_uses` and `max_uses_per_user` are set, `max_uses_per_user ≤ max_uses`. A duplicate `code` SHALL yield HTTP 409.

#### Scenario: Happy path create
- **WHEN** an ADMIN POSTs a valid body with `code="welcome10"`
- **THEN** the server persists a row with `code="WELCOME10"`, `is_active=false`, `current_uses=0`, and returns HTTP 201 with a `PromocodeResponse`

#### Scenario: Duplicate code
- **WHEN** two POSTs with the same `code` (after uppercasing) are sent
- **THEN** the second returns HTTP 409

#### Scenario: Invalid pattern
- **WHEN** an ADMIN POSTs `code="bad code!"`
- **THEN** the response status is 422

#### Scenario: Percent value out of range
- **WHEN** `discount_type='percent'` and `discount_value=150`
- **THEN** the response status is 422

#### Scenario: Fixed amount not positive
- **WHEN** `discount_type='fixed_amount'` and `discount_value=0`
- **THEN** the response status is 422

#### Scenario: Dates inverted
- **WHEN** `valid_from` is after `valid_until`
- **THEN** the response status is 422

#### Scenario: Per-user quota exceeds global quota
- **WHEN** `max_uses=10` and `max_uses_per_user=20`
- **THEN** the response status is 422

### Requirement: List promocodes

The system SHALL accept `GET /api/v1/admin/promocodes` with optional query params: `state` (one of `inactive|active|expired|exhausted|all`, default `all`), `code` (case-insensitive prefix match), `page` (default 1), `per_page` (default 20, max 100; 101 → 422). The response SHALL be a `PromocodeListResponse` with `items` (each item carrying a computed `state`), `total_count` (count after filters, before pagination), `page`, `per_page`. Items SHALL be sorted `created_at DESC`.

#### Scenario: Default state is all
- **WHEN** an ADMIN calls `GET /api/v1/admin/promocodes` with fixtures covering all four computed states
- **THEN** items from all four states appear in the response

#### Scenario: State filter narrows to one bucket
- **WHEN** an ADMIN calls `GET /api/v1/admin/promocodes?state=expired`
- **THEN** every returned item has `state == "expired"`

#### Scenario: Code prefix match is case-insensitive
- **WHEN** an ADMIN calls `GET /api/v1/admin/promocodes?code=welc` and a row exists with `code=WELCOME10`
- **THEN** the row is included in the response

#### Scenario: per_page over 100
- **WHEN** an ADMIN calls `GET /api/v1/admin/promocodes?per_page=101`
- **THEN** the response status is 422

#### Scenario: Sort order is created_at DESC
- **WHEN** two promos exist with `created_at` T1 < T2
- **THEN** the T2 row appears before the T1 row in the response

### Requirement: Get promocode detail

The system SHALL accept `GET /api/v1/admin/promocodes/{promocode_id}` and return a `PromocodeResponse` with the computed `state`. Unknown id SHALL return 404.

#### Scenario: Detail happy path
- **WHEN** an ADMIN calls `GET /api/v1/admin/promocodes/{id}` for an existing promo
- **THEN** the response is 200 and contains a `state` field matching `compute_state`

#### Scenario: Unknown id
- **WHEN** an ADMIN calls the endpoint with a random UUID not in the DB
- **THEN** the response status is 404

### Requirement: Edit promocode

The system SHALL accept `PATCH /api/v1/admin/promocodes/{promocode_id}` with a `PromocodeUpdate` body (all fields optional). When the target's `current_uses = 0`, the admin SHALL be permitted to edit every field. When `current_uses > 0`, the admin SHALL be permitted to edit ONLY `valid_until`, `max_uses`, `max_uses_per_user`, `min_order_amount`, `is_active`. Any attempt to edit `code`, `discount_type`, or `discount_value` when `current_uses > 0` SHALL return HTTP 422 carrying an error payload that names the offending field with type `"field_locked_after_use"`. After applying the patch, `valid_from < valid_until` (if both set) and `max_uses_per_user ≤ max_uses` (if both set) invariants SHALL hold.

#### Scenario: Unused promocode fully editable
- **WHEN** an ADMIN PATCHes `{code, discount_value, valid_until}` on a promo with `current_uses=0`
- **THEN** the response is 200 and all three fields are updated

#### Scenario: Used promocode rejects locked field
- **WHEN** an ADMIN PATCHes `{"code": "NEWCODE"}` on a promo with `current_uses>0`
- **THEN** the response is 422 with an error carrying `type="field_locked_after_use"` and `field="code"`

#### Scenario: Used promocode accepts allowed field
- **WHEN** an ADMIN PATCHes `{"valid_until": "..."}` on a promo with `current_uses>0`
- **THEN** the response is 200 and `valid_until` is updated

#### Scenario: Post-patch date invariant
- **WHEN** the merged state has `valid_from >= valid_until`
- **THEN** the response is 422

### Requirement: Activate promocode

The system SHALL accept `POST /api/v1/admin/promocodes/{promocode_id}/activate`. Preconditions: the row exists (else 404), `valid_until IS NOT NULL` (else 422 with `"valid_until required"`), computed state is not `expired` (else 409 with `"promocode expired"`), computed state is not `exhausted` (else 409 with `"promocode exhausted"`). On success the server SHALL set `is_active = true` in a single transaction and return 200 with a `PromocodeResponse`.

#### Scenario: Activate without valid_until
- **WHEN** an ADMIN activates a promo with `valid_until IS NULL`
- **THEN** the response is 422

#### Scenario: Activate expired
- **WHEN** an ADMIN activates a promo whose `valid_until` is in the past
- **THEN** the response is 409

#### Scenario: Activate exhausted
- **WHEN** an ADMIN activates a promo with `current_uses >= max_uses` and `valid_until` in the future
- **THEN** the response is 409

#### Scenario: Activate happy path
- **WHEN** an ADMIN activates an inactive, non-expired, non-exhausted promo with `valid_until` in the future
- **THEN** the response is 200, `is_active=true`, and `state="active"`

### Requirement: Deactivate promocode

The system SHALL accept `POST /api/v1/admin/promocodes/{promocode_id}/deactivate`. Preconditions: the row exists (else 404), computed state is not `expired` (else 409 with `"promocode expired"`). On success the server SHALL set `is_active = false` in a single transaction and return 200 with a `PromocodeResponse`. There SHALL be no DELETE endpoint.

#### Scenario: Deactivate expired
- **WHEN** an ADMIN deactivates an expired promo
- **THEN** the response is 409

#### Scenario: Deactivate happy path
- **WHEN** an ADMIN deactivates an active promo
- **THEN** the response is 200 and `is_active=false`

#### Scenario: No DELETE endpoint exposed
- **WHEN** an ADMIN issues `DELETE /api/v1/admin/promocodes/{id}`
- **THEN** the route is not registered (405 or 404 from FastAPI)

### Requirement: Transactional write-ops

All write operations (`create_promocode`, `update_promocode`, `activate`, `deactivate`) SHALL perform a single transaction per call (INV-004). A failed guard SHALL leave the row unchanged.

#### Scenario: Failed field-lock leaves row unchanged
- **WHEN** a PATCH with a locked field is rejected with 422
- **THEN** a subsequent GET of the same id returns the pre-PATCH state

### Requirement: Pydantic schema contract

The system SHALL expose the following schemas in `core_api.schemas.promocode`: `PromocodeState` (Literal of the four state strings), `PromocodeCreate`, `PromocodeUpdate` (all fields optional), `PromocodeResponse` (with a `state: PromocodeState` field), `PromocodeListResponse` (`items`, `total_count`, `page`, `per_page`). Monetary fields SHALL be integers in kopecks. `discount_type` SHALL reuse `shared.enums.PromocodeDiscountType`.

#### Scenario: PromocodeResponse carries computed state
- **WHEN** a `PromocodeResponse` is constructed for a promo past `valid_until`
- **THEN** the `state` field equals `"expired"`

#### Scenario: PromocodeUpdate all fields optional
- **WHEN** `PromocodeUpdate()` is instantiated with no arguments
- **THEN** instantiation succeeds
