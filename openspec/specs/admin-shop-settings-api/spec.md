# admin-shop-settings-api Specification

## Purpose
TBD - created by archiving change shop-settings-admin-api-red. Update Purpose after archive.

## Requirements

### Requirement: Shop settings are readable via admin GET endpoint

The system SHALL expose `GET /api/v1/admin/settings` that returns the current
singleton row from `shop_settings` serialized as JSON. The response SHALL include
`auto_close_minutes` (new field added by migration 0008, default 60). Only
callers with role `admin` SHALL receive 200; other roles SHALL receive 403;
unauthenticated calls SHALL receive 401. References: PDD §5.2, §7.1 Phase 6
item 3, INV-010.

#### Scenario: Admin reads default settings
- **WHEN** an admin sends `GET /api/v1/admin/settings` right after seed
- **THEN** the response is 200 with JSON including `auto_close_minutes = 60`,
  all existing shop_settings fields (shop_lat/lon, delivery_radius_km,
  min_delivery_amount, free_delivery_threshold, delivery_fee, loyalty_percent,
  default_prep_time_minutes, estimated_delivery_time_minutes, working_hours,
  updated_at), and an `updated_at` timestamp

#### Scenario: Non-admin staff cannot read
- **WHEN** a barista or courier sends `GET /api/v1/admin/settings`
- **THEN** the response is 403

#### Scenario: Customer cannot read admin settings
- **WHEN** a customer sends `GET /api/v1/admin/settings`
- **THEN** the response is 403

#### Scenario: No token
- **WHEN** an unauthenticated caller sends `GET /api/v1/admin/settings`
- **THEN** the response is 401

### Requirement: Shop settings are updatable as full snapshot via admin PUT

The system SHALL expose `PUT /api/v1/admin/settings` that accepts a full
`ShopSettingsUpdate` JSON body and updates all columns of the singleton row
atomically. PATCH SHALL NOT be supported (avoids JSONB merge semantics on
`working_hours`). Only role `admin` SHALL be authorized. References: PDD §5.2,
§6.1, §7.1 Phase 6 item 3, INV-010.

#### Scenario: Admin updates all fields
- **WHEN** an admin sends `PUT /api/v1/admin/settings` with a valid complete
  body (including `auto_close_minutes`)
- **THEN** the response is 200 with the new snapshot and `updated_at` advanced

#### Scenario: Singleton constraint is preserved
- **WHEN** the service layer (or a direct ORM insert) attempts to create a
  second row with `id=2`
- **THEN** the database raises `IntegrityError` from
  `ck_shop_settings_singleton` and no second row exists

#### Scenario: Non-admin rejected
- **WHEN** a barista, courier, or customer sends `PUT /api/v1/admin/settings`
  with a valid body
- **THEN** the response is 403

#### Scenario: No token on PUT
- **WHEN** an unauthenticated caller sends `PUT /api/v1/admin/settings`
- **THEN** the response is 401

### Requirement: Shop settings payload is strictly validated

`ShopSettingsUpdate` SHALL enforce numeric bounds (lat/lon/loyalty/radius),
business invariants (free_delivery_threshold ≥ min_delivery_amount,
`auto_close_minutes ∈ [1, 1440]`), and a strict `working_hours` shape (exactly
the 7 keys mon..sun; value is either null or `{open, close}` with HH:MM and
`open < close`). Violations SHALL return 422.

#### Scenario: Out-of-range latitude
- **WHEN** the body has `shop_lat = 91`
- **THEN** the response is 422

#### Scenario: Out-of-range longitude
- **WHEN** the body has `shop_lon = 181`
- **THEN** the response is 422

#### Scenario: Loyalty percent > 100
- **WHEN** the body has `loyalty_percent = 101`
- **THEN** the response is 422

#### Scenario: Free threshold below minimum
- **WHEN** the body has `free_delivery_threshold < min_delivery_amount`
- **THEN** the response is 422

#### Scenario: auto_close_minutes = 0
- **WHEN** the body has `auto_close_minutes = 0`
- **THEN** the response is 422

#### Scenario: auto_close_minutes > 1440
- **WHEN** the body has `auto_close_minutes = 1441`
- **THEN** the response is 422

#### Scenario: working_hours missing a day
- **WHEN** the `working_hours` object has no `sun` key
- **THEN** the response is 422

#### Scenario: working_hours invalid time
- **WHEN** `working_hours.mon.open = '25:00'`
- **THEN** the response is 422

#### Scenario: working_hours open == close
- **WHEN** `working_hours.mon = {open: '10:00', close: '10:00'}`
- **THEN** the response is 422

#### Scenario: working_hours day off is allowed
- **WHEN** `working_hours.tue = null` (and every other field is valid)
- **THEN** the response is 200

### Requirement: Migration 0008 adds auto_close_minutes column

Migration `0008_shop_settings_auto_close.py` SHALL add
`auto_close_minutes INTEGER NOT NULL DEFAULT 60` on upgrade and drop it on
downgrade. The migration SHALL be purely additive (no existing column renamed
or removed). The seed SHALL populate `auto_close_minutes = 60` on the
singleton row. References: PDD §6.1, §7.1 Phase 6 item 3.

#### Scenario: Upgrade head creates the column
- **WHEN** Alembic applies revision 0008 on top of 0007
- **THEN** the `shop_settings` table has a column `auto_close_minutes` with
  type INTEGER, NOT NULL, default 60

#### Scenario: Downgrade removes the column
- **WHEN** Alembic downgrades revision 0008 to 0007
- **THEN** the `shop_settings` table no longer has `auto_close_minutes`

#### Scenario: Seed row carries the default
- **WHEN** the shop_settings seed runs on a freshly migrated database
- **THEN** the singleton row (id=1) has `auto_close_minutes = 60`

### Requirement: Admin settings routes are declared in the RBAC matrix

`ROUTE_MATRIX` SHALL declare `("GET", "/api/v1/admin/settings")` and
`("PUT", "/api/v1/admin/settings")` with allowed roles `{ADMIN}`. The RBAC
middleware test suite (`test_rbac_matrix.py`, `test_route_coverage.py`) SHALL
still pass — every registered route MUST be present in the matrix.

#### Scenario: Matrix lookup grants admin
- **WHEN** middleware looks up `(GET, /api/v1/admin/settings)` for an admin
- **THEN** access is allowed

#### Scenario: Matrix lookup denies barista
- **WHEN** middleware looks up `(PUT, /api/v1/admin/settings)` for a barista
- **THEN** access is denied (403)
