# shop-settings-ui Specification

## Purpose
TBD - created by archiving change shop-settings-ui. Update Purpose after archive.
## Requirements
### Requirement: Settings page mount — initial load

The admin SPA SHALL render a single `SettingsPage` form at `/settings` that, on mount, fetches the full shop-settings snapshot via `GET /api/v1/admin/settings` and populates every form field. While the initial fetch is pending, the page SHALL show a skeleton/placeholder; it SHALL NOT render the form with empty defaults.

Ref: PDD §5.2, §7.1 Phase 6 item 3, INV-010.

#### Scenario: Happy initial load
- **WHEN** an authenticated admin navigates to `/settings`
- **AND** `GET /api/v1/admin/settings` returns 200 with a full `ShopSettingsResponse`
- **THEN** every input is pre-filled from the response (shop_lat, shop_lon, delivery_radius_km, min_delivery_amount in rubles, free_delivery_threshold in rubles, delivery_fee in rubles, loyalty_percent, default_prep_time_minutes, estimated_delivery_time_minutes, auto_close_minutes, working_hours per day)
- **AND** no loading skeleton is visible

#### Scenario: Initial fetch in flight
- **WHEN** the `/settings` page is mounting and the `GET` has not resolved
- **THEN** a loading skeleton is rendered and the form is NOT yet interactive

#### Scenario: Initial fetch fails with 500/network
- **WHEN** `GET /api/v1/admin/settings` fails
- **THEN** an error toast (generic) is shown and the form remains in the loading/empty state (does NOT submit with partial data)

### Requirement: Save submits full snapshot via PUT

On save, the SPA SHALL send the entire current form state as the body of `PUT /api/v1/admin/settings`. Money amounts SHALL be converted from rubles (UI) to integer kopecks (wire) before sending. The SPA SHALL NOT issue PATCH requests and SHALL NOT send partial-field bodies.

#### Scenario: Save happy path
- **WHEN** the admin edits any field and clicks Save
- **AND** `PUT /api/v1/admin/settings` returns 200
- **THEN** a success snackbar with `pages.settings.toast.saved` is shown
- **AND** the form's baseline (initial state used for dirty-check) is reset to the returned snapshot
- **AND** `isDirty` becomes false (Save button disables again)

#### Scenario: Rubles-to-kopecks conversion
- **WHEN** the admin enters `100` into the delivery-fee input (rendered as "₽")
- **AND** clicks Save
- **THEN** the PUT body's `delivery_fee` field is the integer `10000`

### Requirement: Save button disabled unless form is dirty and valid

The Save button SHALL be disabled whenever the current form state equals the initial baseline (`isDirty === false`) OR client-side validation reports any error (`isValid === false`).

#### Scenario: Disabled before any edits
- **WHEN** the page just loaded successfully
- **THEN** the Save button is disabled

#### Scenario: Disabled with invalid input
- **WHEN** the admin sets `loyalty_percent` to `150`
- **THEN** the Save button is disabled regardless of other edits

#### Scenario: Enabled when dirty and valid
- **WHEN** the admin changes one field to a valid value
- **THEN** the Save button becomes enabled

### Requirement: Section — Coordinates

`SectionCoords` SHALL render numeric inputs for `shop_lat` and `shop_lon`. Client-side validation SHALL enforce `shop_lat ∈ [-90, 90]` and `shop_lon ∈ [-180, 180]`. The SPA SHALL NOT render a map picker; numeric inputs are sufficient.

Ref: PDD §5.2 ShopSettings.

#### Scenario: Out-of-range latitude
- **WHEN** the admin enters `91` into `shop_lat`
- **THEN** an inline error is shown under the field
- **AND** the form is considered invalid

### Requirement: Section — Delivery

`SectionDelivery` SHALL render four fields:
- `delivery_radius_km` (decimal, suffix "km"), validated `[0.1, 50]`.
- `min_delivery_amount` (rubles, suffix "₽"), validated `≥ 0`.
- `free_delivery_threshold` (rubles, suffix "₽"), validated `≥ 0` AND `≥ min_delivery_amount`.
- `delivery_fee` (rubles, suffix "₽"), validated `≥ 0`.

Money fields SHALL be converted from rubles to integer kopecks on the PUT body.

Ref: PDD §5.2.

#### Scenario: Inconsistent thresholds
- **WHEN** `min_delivery_amount = 500 ₽` and `free_delivery_threshold = 300 ₽`
- **THEN** an inline error is shown on `free_delivery_threshold`
- **AND** the form is invalid

#### Scenario: Conversion on save
- **WHEN** the admin saves with `min_delivery_amount = 100 ₽`
- **THEN** the PUT body's `min_delivery_amount` field equals `10000`

### Requirement: Section — Loyalty

`SectionLoyalty` SHALL render a numeric input (or slider) for `loyalty_percent`, validated as integer `[0, 100]` inclusive.

Ref: PDD §5.2.

#### Scenario: Boundary accepted
- **WHEN** `loyalty_percent = 0`
- **THEN** no error
- **WHEN** `loyalty_percent = 100`
- **THEN** no error

#### Scenario: Above upper bound
- **WHEN** `loyalty_percent = 101`
- **THEN** inline error shown; form invalid

### Requirement: Section — Timing

`SectionTiming` SHALL render three numeric inputs in minutes:
- `default_prep_time_minutes` — integer `≥ 1`.
- `estimated_delivery_time_minutes` — integer `≥ 1`.
- `auto_close_minutes` — integer `[1, 1440]` inclusive.

Ref: PDD §5.2, §6.1 (auto-close), §7.1 Phase 6 item 3.

#### Scenario: auto_close_minutes = 0
- **WHEN** `auto_close_minutes = 0`
- **THEN** inline error; form invalid

#### Scenario: auto_close_minutes = 1441
- **WHEN** `auto_close_minutes = 1441`
- **THEN** inline error; form invalid

#### Scenario: auto_close_minutes = 60
- **WHEN** `auto_close_minutes = 60`
- **THEN** no error; field valid

### Requirement: Section — Working Hours

`SectionWorkingHours` SHALL render exactly 7 rows in the fixed order `mon, tue, wed, thu, fri, sat, sun`. Each row SHALL contain:
- A "Выходной / Closed" checkbox. When checked, the day's value SHALL be serialized as `null` in the PUT payload, and the time inputs SHALL be hidden/disabled.
- When unchecked: two `<input type="time">` controls for `open` and `close`. On save, the day's value SHALL be serialized as `{"open": "HH:MM", "close": "HH:MM"}`.

Validation per row (when not closed):
- Both `open` and `close` SHALL be non-empty.
- `open < close` strictly; overnight (close < open) is NOT supported.

Ref: PDD §5.2 (working_hours JSONB).

#### Scenario: Toggle "Выходной" reveals time pickers
- **WHEN** the admin unchecks "Выходной" on Tuesday
- **THEN** two `<input type="time">` inputs appear for that row

#### Scenario: open >= close inline error
- **WHEN** for Monday the admin enters `open=12:00, close=10:00`
- **THEN** an inline error is shown under the Monday row
- **AND** the form is invalid

#### Scenario: Empty open/close when not closed
- **WHEN** "Выходной" is unchecked for Wednesday and `open` is empty
- **THEN** an inline error is shown; form invalid

#### Scenario: Closed day serializes to null
- **WHEN** "Выходной" is checked for Sunday and the form is saved
- **THEN** the PUT body's `working_hours.sun` equals `null`

### Requirement: 422 field-level error mapping

On a 422 response from `PUT /api/v1/admin/settings`, the SPA SHALL parse `detail[].loc` paths and surface each error next to the corresponding form field. The `loc` prefix `["body"]` SHALL be stripped; the remainder SHALL be joined with `.` to produce a field-path (e.g., `["body","working_hours","mon","open"]` → `working_hours.mon.open`).

Ref: `shop-settings-admin-api` validation contract (phase6 plan §360–506).

#### Scenario: Top-level field error
- **WHEN** backend returns 422 with `detail=[{loc: ["body","loyalty_percent"], msg: "out_of_range"}]`
- **THEN** an inline error is rendered under the `loyalty_percent` input

#### Scenario: Nested working-hours error
- **WHEN** backend returns 422 with `loc=["body","working_hours","mon","open"]`
- **THEN** the Monday `open` input shows an inline error

#### Scenario: No global toast on 422
- **WHEN** backend returns 422
- **THEN** only field-level errors are shown; no generic error toast fires

### Requirement: Generic error toast on 500 / network failure

On a non-422 failure of `PUT /api/v1/admin/settings` (500, network, timeout), the SPA SHALL show a generic error toast (`pages.settings.toast.error`) and NOT clear any field values.

#### Scenario: 500 response
- **WHEN** PUT returns 500
- **THEN** a generic error toast appears and the form state is preserved

#### Scenario: Network failure
- **WHEN** `fetch` rejects (network offline)
- **THEN** a generic error toast appears; form state preserved

### Requirement: Post-save snapshot refresh

After `PUT /api/v1/admin/settings` returns 200, the SPA SHALL replace its baseline (`initialForm`) and current form state with the response payload so that `updated_at` reflects the server's fresh value and `isDirty` becomes false.

#### Scenario: updated_at reflects server response
- **WHEN** PUT returns 200 with `updated_at = "2026-04-20T10:00:00Z"`
- **THEN** the page's baseline uses `2026-04-20T10:00:00Z`
- **AND** a subsequent no-op keeps Save disabled

### Requirement: i18n keys for settings page

The admin i18n bundle SHALL provide keys under `pages.settings` for: title, description, section headings (`coords`, `delivery`, `loyalty`, `timing`, `working_hours`), 10 field labels, units (km, rub, percent, minutes), 7 day labels (`mon..sun`), `closed`, `save_button`, toast messages (`saved`, `error`), and validation error codes. Both `ru/common.json` and `en/common.json` SHALL contain the same keys.

#### Scenario: Both locales have all keys
- **WHEN** the test asserts parity between `ru/common.json` and `en/common.json` under `pages.settings.*`
- **THEN** every key in one locale exists in the other (no missing translations)

### Requirement: No client-side caching of settings

The SPA SHALL NOT memoize or persist the settings response beyond the page-component lifetime. Navigating away and back SHALL trigger a fresh `GET /api/v1/admin/settings`.

#### Scenario: Re-mount refetches
- **WHEN** the admin navigates away from `/settings` and returns
- **THEN** a new `GET /api/v1/admin/settings` fires on re-mount

