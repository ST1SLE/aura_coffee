## ADDED Requirements

### Requirement: Admin-only route gating
The admin SPA SHALL restrict the `/promos` route to users whose role is `admin`. Authenticated users with role `barista` or `courier` MUST be denied render access (defense-in-depth alongside the Layout sidebar filter). Reference: PDD §4.5 Admin, INV-010.

#### Scenario: Barista hits /promos directly
- **WHEN** a user with role `barista` navigates to `/admin/promos`
- **THEN** the `ProtectedRoute` SHALL deny rendering the `PromosPage` and redirect per the app's existing unauthorized-route convention

#### Scenario: Admin hits /promos
- **WHEN** a user with role `admin` navigates to `/admin/promos`
- **THEN** the `PromosPage` shell SHALL render with state-filter tabs, code search, Create button, and the promocodes table

### Requirement: Promocodes API client
The admin SPA SHALL expose a zod-typed module at `web/admin/src/api/promocodes.ts` providing `listPromocodes`, `getPromocode`, `createPromocode`, `updatePromocode`, `activatePromocode`, `deactivatePromocode`. JWT MUST be sourced from the existing `client.ts` helper; the types MUST mirror `services/core-api/src/core_api/schemas/promocode.py`. Reference: phase5-plan.yaml `admin-promocodes-api`.

#### Scenario: List with state and code filters
- **WHEN** `listPromocodes({ state: 'active', code: 'WEEK', page: 1, per_page: 20 })` is called
- **THEN** the client SHALL issue `GET /api/v1/admin/promocodes?state=active&code=WEEK&page=1&per_page=20` with the admin bearer token and return a zod-parsed `PromocodeListResponse`

#### Scenario: Create with fixed-amount discount
- **WHEN** `createPromocode` is called with `{ discount_type: 'fixed_amount', discount_value_rubles: 500, min_order_rubles: 1000, ... }`
- **THEN** the client SHALL POST `discount_value: 50000` and `min_order_amount: 100000` (kopecks) to `POST /api/v1/admin/promocodes`

#### Scenario: Activate request
- **WHEN** `activatePromocode(id)` is called
- **THEN** the client SHALL issue `POST /api/v1/admin/promocodes/{id}/activate` with an empty body and return the refreshed `PromocodeResponse`

#### Scenario: 422 surfaces field errors
- **WHEN** the server responds with `422` and a Pydantic-shaped error body listing `loc: ['body', 'code']`
- **THEN** the API client SHALL parse the error payload into a structured shape consumable by the form dialog (no plain-text throw-away)

### Requirement: State filter tabs
The `PromosPage` shell SHALL render five tabs — All, Active, Inactive, Expired, Exhausted — that map to the server `?state=` parameter (`all` omits the param, the others pass the lowercase literal). Switching a tab SHALL reset pagination to page 1. Reference: PDD §6.6 computed state.

#### Scenario: Tab switch reissues list request
- **WHEN** the admin clicks the "Expired" tab while the current query is `state=active`
- **THEN** the page SHALL issue a new `GET /api/v1/admin/promocodes?state=expired&page=1&per_page=20`

#### Scenario: All tab omits state param
- **WHEN** the "All" tab is active
- **THEN** the request SHALL be `GET /api/v1/admin/promocodes?page=1&per_page=20` (no `state` query)

### Requirement: Code search with 300ms debounce
The `PromosPage` SHALL include a search input whose value is debounced by 300 ms before being issued as `?code=` on the list request. Rapid typing MUST collapse to a single final request. Reference: phase5-plan `admin-promocodes-ui` task 2.

#### Scenario: Rapid typing collapses to one request
- **WHEN** the admin types "WEEK" with < 300 ms between keystrokes
- **THEN** exactly one `GET /api/v1/admin/promocodes?code=WEEK` request SHALL be issued after typing stops

### Requirement: Promocodes table rendering
`PromosTable` SHALL render one row per promocode with columns: `code` (monospace), `state_chip` (colored badge mapped from the server-provided `state`), `discount` preview (`"10%"` when `discount_type==='percent'`, `"500 ₽"` when `discount_type==='fixed_amount'`), `valid_until` (local datetime format, dimmed when server-state is `expired`), `uses` (`"3 / 10"` or `"3 / ∞"`), and an `actions` cell. Clicking a row SHALL open `PromoFormDialog` in edit-mode. Reference: PDD §6.6.

#### Scenario: State chip renders for all four states
- **WHEN** rows are rendered with `state` values `active`, `inactive`, `expired`, `exhausted`
- **THEN** each row SHALL render a distinctly-colored chip with the localized label from `pages.promos.state_chip.*`

#### Scenario: Uses column renders unbounded quota
- **WHEN** `current_uses=3` and `max_uses=null`
- **THEN** the `uses` cell SHALL display `"3 / ∞"`

#### Scenario: Expired row dims valid_until
- **WHEN** `state==='expired'`
- **THEN** the `valid_until` cell SHALL render with the dim-color styling

#### Scenario: UI does not recompute state
- **WHEN** a row's backing payload has `state: 'active'` but an already-past `valid_until`
- **THEN** the chip SHALL still render "active" — the UI MUST trust the server-provided `state`

### Requirement: Row action visibility matrix
Action buttons rendered per row SHALL follow this matrix (PDD §6.6): `active` → Edit + Deactivate; `inactive` → Edit + Activate; `expired` → Edit only (no Activate); `exhausted` → Edit only (no Activate). Activate / Deactivate buttons MUST be disabled while their mutation is in flight.

#### Scenario: Active row
- **WHEN** a row has `state='active'`
- **THEN** Edit and Deactivate buttons SHALL be visible; Activate SHALL NOT be visible

#### Scenario: Inactive row
- **WHEN** a row has `state='inactive'`
- **THEN** Edit and Activate buttons SHALL be visible; Deactivate SHALL NOT be visible

#### Scenario: Expired row
- **WHEN** a row has `state='expired'`
- **THEN** only Edit SHALL be visible (no Activate, no Deactivate)

#### Scenario: Exhausted row
- **WHEN** a row has `state='exhausted'`
- **THEN** only Edit SHALL be visible (no Activate)

#### Scenario: In-flight mutation disables button
- **WHEN** the Deactivate mutation is pending
- **THEN** the corresponding button SHALL render disabled until the response resolves

### Requirement: Promo form dialog — create mode
`PromoFormDialog` in create-mode SHALL expose editable inputs for `code`, `discount_type` (radio: percent / fixed), `discount_value` (number; suffix `%` or `₽` based on `discount_type`), `min_order_amount` (number, optional, rubles), `valid_from`, `valid_until` (datetime-local), `max_uses`, `max_uses_per_user` (numbers, optional). Footer SHALL render Cancel / Create. Reference: PDD §6.6, phase5-plan.

#### Scenario: Fixed-amount conversion on submit
- **WHEN** the admin enters `discount_value=500` with `discount_type=fixed`
- **THEN** the POST body SHALL carry `discount_value=50000` (kopecks)

#### Scenario: Percent submit without conversion
- **WHEN** the admin enters `discount_value=10` with `discount_type=percent`
- **THEN** the POST body SHALL carry `discount_value=10` (no kopecks conversion)

#### Scenario: Successful create closes dialog and refreshes list
- **WHEN** the server responds 200 to create
- **THEN** the dialog SHALL close and the list query SHALL be invalidated (re-fetched)

### Requirement: Promo form dialog — edit mode lock-after-use
In edit-mode, when `current_uses > 0`, the `code`, `discount_type`, and `discount_value` inputs SHALL render as disabled and SHALL surface a tooltip sourced from `pages.promos.locked_hint`. The remaining fields (`min_order_amount`, `valid_from`, `valid_until`, `max_uses`, `max_uses_per_user`) MUST remain editable. The client MUST NOT attempt to bypass this lock; the server 422 (`field_locked_after_use`) remains authoritative. Reference: PDD §6.6 "Редактирование".

#### Scenario: uses=0 — all fields editable
- **WHEN** editing a promocode with `current_uses=0`
- **THEN** every field SHALL render enabled

#### Scenario: uses>0 — code, discount_type, discount_value disabled
- **WHEN** editing a promocode with `current_uses=3`
- **THEN** `code`, `discount_type`, and `discount_value` inputs SHALL be disabled AND a tooltip sourced from `pages.promos.locked_hint` SHALL be reachable

#### Scenario: Rubles ↔ kopecks conversion on load + save
- **WHEN** loading a promocode with `discount_type='fixed_amount'`, `discount_value=50000`, `min_order_amount=100000`
- **THEN** the dialog SHALL display `discount_value=500` and `min_order_amount=1000`; on save with unchanged values, the PATCH body SHALL carry `discount_value=50000` and `min_order_amount=100000`

#### Scenario: Server 422 on locked field surfaces inline
- **WHEN** the server returns 422 with an error on `code` carrying detail-code `field_locked_after_use`
- **THEN** the dialog SHALL render the localized message from `pages.promos.errors.field_locked_after_use` under the `code` input

### Requirement: Promo form dialog — footer actions by state
Edit-mode footer SHALL render: Cancel + Save, plus Activate when `is_active === false && state !== 'expired' && state !== 'exhausted'`, plus Deactivate when `is_active === true`. Activate / Deactivate MUST be dispatched as dedicated POST requests — not embedded in the PATCH body. Reference: PDD §6.6 state transitions.

#### Scenario: Inactive eligible promocode
- **WHEN** editing a promocode with `is_active=false`, `state='inactive'`
- **THEN** the footer SHALL render Cancel + Save + Activate

#### Scenario: Active promocode
- **WHEN** editing a promocode with `is_active=true`, `state='active'`
- **THEN** the footer SHALL render Cancel + Save + Deactivate

#### Scenario: Expired inactive promocode
- **WHEN** editing a promocode with `is_active=false`, `state='expired'`
- **THEN** the footer SHALL render Cancel + Save only (no Activate button)

#### Scenario: Activate is a separate request
- **WHEN** the admin clicks Activate
- **THEN** the client SHALL issue `POST /api/v1/admin/promocodes/{id}/activate` and MUST NOT include `is_active` in any PATCH payload

### Requirement: No Delete / archive-style UI
The admin SPA SHALL NOT expose any destructive delete affordance for promocodes (no button, no menu item, no keyboard shortcut). Archival is achieved via Deactivate. Reference: PDD §6.6, INV-010.

#### Scenario: Table row has no Delete button
- **WHEN** any promocode row is rendered
- **THEN** no Delete / Remove / Archive action SHALL be present

#### Scenario: Form dialog has no Delete button
- **WHEN** `PromoFormDialog` renders in edit-mode
- **THEN** no Delete / Remove / Archive footer action SHALL be present

### Requirement: i18n keys for RU and EN
All user-visible strings introduced by this capability SHALL be localized in both `web/admin/src/i18n/locales/ru.json` and `en.json` under `pages.promos.*` covering: `title`, `create`, `search_placeholder`, `empty`, `locked_hint`, `state.*`, `state_chip.*`, `columns.*`, `form.*`, `actions.*`, `errors.*`. Reference: PDD bilingual interface constraint.

#### Scenario: Every key is defined in both locales
- **WHEN** the translation catalog is loaded
- **THEN** every `pages.promos.*` key referenced by the UI SHALL resolve to a non-empty string in both `ru` and `en`

### Requirement: Vitest coverage
The following vitest suites SHALL exist and pass: `PromosTable.test.tsx`, `PromoFormDialog.test.tsx`, `PromosPage.test.tsx`, `api/promocodes.test.ts`. Collectively they MUST cover the state-chip matrix, action-button visibility matrix, lock-after-use disable matrix, rubles↔kopecks conversion on save + load, search debounce collapsing to a single request, and state-tab → reload wiring.

#### Scenario: State-chip render matrix
- **WHEN** `PromosTable.test.tsx` runs
- **THEN** it SHALL assert chip rendering for each of `active`, `inactive`, `expired`, `exhausted`

#### Scenario: Lock-after-use matrix
- **WHEN** `PromoFormDialog.test.tsx` runs
- **THEN** it SHALL assert enabled inputs for `current_uses=0` and disabled `code` / `discount_type` / `discount_value` for `current_uses=3`

#### Scenario: Rubles↔kopecks round-trip
- **WHEN** `PromoFormDialog.test.tsx` runs
- **THEN** it SHALL assert that loading `discount_value=50000` shows `500` and saving `500` posts `50000`

#### Scenario: Search debounce
- **WHEN** `PromosPage.test.tsx` runs
- **THEN** it SHALL assert that rapid typing in the search input issues exactly one list request after 300 ms of idle
