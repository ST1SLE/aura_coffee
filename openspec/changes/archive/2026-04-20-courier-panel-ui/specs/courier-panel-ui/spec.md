## ADDED Requirements

### Requirement: Courier page at /courier
The admin SPA SHALL provide a page at `/courier` (under `basename="/admin"`, so `/admin/courier` in the browser) at `web/admin/src/pages/Courier/CourierPage.tsx`. The page SHALL render a mobile-first layout with exactly two tabs — "Доступные" / "Available" (available assignments) and "Мои" / "Mine" (assignments taken by the current courier) — and no sidebar, no admin navigation. Refs: PDD §4.5 (Courier view), PDD §6.3 (Delivery Assignment lifecycle), INV-010 (role isolation).

#### Scenario: Courier page renders two tabs
- **WHEN** an authenticated courier navigates to `/admin/courier`
- **THEN** the page renders two tab controls labeled via `courier.tabs.available` and `courier.tabs.mine` i18n keys, with one tab selected by default (`available`)

#### Scenario: No admin sidebar on courier page
- **WHEN** the courier page renders (for any role)
- **THEN** the admin `Layout` sidebar (dashboard/orders/menu/users/promos/settings nav links) is NOT rendered on the page, and the only chrome present is the language switcher and the notification list

#### Scenario: Mobile-first layout
- **WHEN** the viewport width is 375px (iPhone SE class)
- **THEN** every assignment card occupies the full width, the primary action button on each card has a minimum tap height ≥ 48 CSS pixels, and no horizontal scrolling is introduced

### Requirement: Available assignments tab polling
The "Available" tab SHALL call `GET /api/v1/courier/assignments/available` via `@tanstack/react-query`'s `useQuery` with `queryKey: ['courier', 'available']`, `refetchInterval: 5000`, and `refetchIntervalInBackground: false`. Each item SHALL be rendered as a card showing the delivery address, the order total (kopecks converted to roubles for display), the `requested_time` (formatted `HH:mm` in the browser locale, or "ASAP" / "ASAP" i18n if the field is `null`), and a single primary action button labeled via `courier.actions.take`. Refs: PDD §4.5 (≤ 5 s feed latency), PDD §6.3 transition `AWAITING_COURIER → COURIER_ASSIGNED`.

#### Scenario: Feed refreshes every 5 seconds
- **WHEN** the Available tab has been open for 12 seconds without user action
- **THEN** `GET /api/v1/courier/assignments/available` has been called at least 3 times (initial fetch plus at least two 5-second refetches)

#### Scenario: Polling pauses when tab is hidden
- **WHEN** the browser tab hosting the courier page transitions from visible to hidden
- **THEN** no further `GET /api/v1/courier/assignments/available` requests are issued until the tab becomes visible again

#### Scenario: Empty list shows explicit empty state
- **WHEN** the API returns an empty array
- **THEN** the tab body renders a localized `courier.empty.available` message instead of an empty scroll region

#### Scenario: Kopeck-to-rouble display conversion
- **GIVEN** an assignment with `total = 45000` (i.e. 450 ₽ in kopecks)
- **WHEN** the card renders
- **THEN** the visible total text contains `450` followed by the rouble currency suffix (`₽` or localized), and NOT the raw integer `45000`

### Requirement: Take assignment action
Clicking the "Взять" / "Take" button on an Available-tab card SHALL issue `POST /api/v1/courier/assignments/{id}/take` via a `useMutation`. On HTTP 2xx success the mutation's `onSettled` (or `onSuccess`) handler SHALL call `queryClient.invalidateQueries({ queryKey: ['courier', 'available'] })` AND `queryClient.invalidateQueries({ queryKey: ['courier', 'mine'] })`. On HTTP 409 it SHALL emit a toast via the `useNotifier` hook using `courier.errors.alreadyTaken` AND refetch the available list so the stale card disappears. Refs: PDD §6.3 (optimistic lock note).

#### Scenario: Successful take moves card from Available to Mine
- **WHEN** the user clicks "Взять" on a card with id `aid-1` and the backend responds 200
- **THEN** both `['courier', 'available']` and `['courier', 'mine']` queries are invalidated, the card with id `aid-1` disappears from the Available tab on the next refetch, and appears on the Mine tab

#### Scenario: 409 shows the already-taken toast
- **WHEN** the user clicks "Взять" and the backend responds 409
- **THEN** the notifier is called with the `courier.errors.alreadyTaken` string and variant `'error'`, and `['courier', 'available']` is refetched

#### Scenario: Take button disabled while in flight
- **WHEN** the user clicks "Взять" and the request is pending
- **THEN** the button is disabled until the request settles (resolves or rejects), and a second click during that interval does NOT issue a second request

### Requirement: My assignments tab and status actions
The "Mine" tab SHALL call `GET /api/v1/courier/assignments/mine` via `useQuery` with `queryKey: ['courier', 'mine']`, `refetchInterval: 5000`, and `refetchIntervalInBackground: false`. Each item SHALL render a card with the same core fields as Available (address, total, requested_time) plus the assignment's `status` label. The card's single primary action button SHALL be chosen by status:

- `status === 'COURIER_ASSIGNED'` → button labeled `courier.actions.pickup`, issues `POST /api/v1/courier/assignments/{id}/pickup`.
- `status === 'PICKED_UP'` → button labeled `courier.actions.deliver`, issues `POST /api/v1/courier/assignments/{id}/deliver`.
- Any other status → no action button is rendered.

Both mutations SHALL invalidate `['courier', 'mine']` on success. Refs: PDD §6.3 transitions `COURIER_ASSIGNED → PICKED_UP`, `PICKED_UP → DELIVERED`.

#### Scenario: Pickup button shown for COURIER_ASSIGNED
- **GIVEN** a mine-card with `status: 'COURIER_ASSIGNED'`
- **WHEN** the Mine tab renders
- **THEN** exactly one primary button is shown on the card, labeled via `courier.actions.pickup`, and clicking it calls `POST /api/v1/courier/assignments/{id}/pickup`

#### Scenario: Deliver button shown for PICKED_UP
- **GIVEN** a mine-card with `status: 'PICKED_UP'`
- **WHEN** the Mine tab renders
- **THEN** exactly one primary button is shown on the card, labeled via `courier.actions.deliver`, and clicking it calls `POST /api/v1/courier/assignments/{id}/deliver`

#### Scenario: No forbidden-transition buttons are exposed
- **GIVEN** a mine-card with `status: 'DELIVERED'` or `status: 'CANCELLED'`
- **WHEN** the Mine tab renders
- **THEN** NO action button is rendered on that card (the UI MUST NOT expose `PICKED_UP → COURIER_ASSIGNED`, `COURIER_ASSIGNED → AWAITING_COURIER`, or any other transition forbidden by PDD §6.3)

#### Scenario: Successful pickup updates the card in place
- **WHEN** the user clicks "Забрал" on a `COURIER_ASSIGNED` card and the backend responds 200 with `status: 'PICKED_UP'`
- **THEN** `['courier', 'mine']` is invalidated, the card's action button re-renders as "Доставлен", and the status label updates

#### Scenario: Successful deliver removes the card
- **WHEN** the user clicks "Доставлен" on a `PICKED_UP` card and the backend responds 200
- **THEN** `['courier', 'mine']` is invalidated, and because the backend no longer returns DELIVERED assignments in `GET /mine`, the card disappears on the next refetch

### Requirement: Courier API client module
The admin SPA SHALL provide `web/admin/src/api/courier.ts` exporting typed functions that mirror `services/core-api/src/core_api/schemas/courier.py`: `listAvailable()`, `takeAssignment(id: string)`, `listMine()`, `pickupAssignment(id: string)`, `deliverAssignment(id: string)`. All five SHALL go through `authenticatedFetch` and SHALL throw `ApiError(status, body, message)` on non-2xx responses, matching the pattern in `web/admin/src/api/menu.ts`. Refs: spec `delivery-assignment` (endpoint contract — owned by backend, not this change).

#### Scenario: Requests carry the bearer token
- **WHEN** any of the five client functions is called while `localStorage.accessToken` is set
- **THEN** the outgoing HTTP request includes `Authorization: Bearer <token>`

#### Scenario: 409 on take throws ApiError(409)
- **WHEN** `takeAssignment('aid-1')` is called and the backend responds 409 with body `{detail: 'already_taken'}`
- **THEN** the promise rejects with `ApiError` whose `.status === 409` and `.body.detail === 'already_taken'`

#### Scenario: 401 triggers client-wide logout
- **WHEN** any of the five client functions receives HTTP 401
- **THEN** `authenticatedFetch`'s existing 401 handler clears `accessToken` and redirects to `/admin/login?returnUrl=...` (unchanged behavior from spec `admin-auth-ui`)

### Requirement: React Query provider in admin SPA
The admin SPA's `web/admin/src/main.tsx` (or equivalent app bootstrap) SHALL construct exactly one `QueryClient` instance and wrap `<App />` with `<QueryClientProvider client={queryClient}>`. The `QueryClient` default options SHALL NOT set a global `refetchInterval` — polling cadence MUST be per-query. `@tanstack/react-query` SHALL be declared in `web/admin/package.json` `dependencies`. Refs: PDD §4.5 (≤ 5 s latency via polling).

#### Scenario: Single QueryClient across the app
- **WHEN** two different components in the admin SPA both read `['courier', 'available']` via `useQuery`
- **THEN** they share a single cache entry and a single in-flight request (de-duplication works), proving they live under the same `QueryClient`

#### Scenario: No global refetch interval
- **WHEN** any `useQuery` is called without explicitly passing `refetchInterval`
- **THEN** the query does NOT poll — it fetches once and remains idle until a manual invalidation

### Requirement: Courier i18n namespace
The admin SPA's `web/admin/src/i18n/locales/{ru,en}/common.json` SHALL each include a `courier` namespace with these keys: `courier.tabs.available`, `courier.tabs.mine`, `courier.actions.take`, `courier.actions.pickup`, `courier.actions.deliver`, `courier.empty.available`, `courier.empty.mine`, `courier.errors.alreadyTaken`, `courier.fields.requestedAsap`, `courier.fields.total`, `courier.fields.address`. RU strings SHALL be used for Russian and EN strings for English. Refs: PDD §4.5 bilingual UI.

#### Scenario: Keys exist in both locales
- **WHEN** every key listed above is looked up via `t('courier.<key>')` under `lng: 'ru'` and then under `lng: 'en'`
- **THEN** every lookup returns a non-empty string that is NOT equal to the key itself (i.e. i18next did not fall through the missing-key path)

#### Scenario: Language switcher updates courier labels live
- **WHEN** the courier page is open and the user toggles RU ↔ EN via the `LanguageSwitcher`
- **THEN** every visible courier-namespaced label re-renders into the selected language without a page reload
