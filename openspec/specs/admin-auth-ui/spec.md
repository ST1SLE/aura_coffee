## Purpose

Authentication UI flows for the admin SPA: access-token storage, login page, 401 redirect handler, and protected-route guards.
## Requirements
### Requirement: Admin access-token storage helpers
The admin SPA SHALL expose token helpers from `web/admin/src/api/client.ts`: `getAccessToken(): string | null`, `setAccessToken(token: string): void`, `clearAccessToken(): void`, and `logout(): void`. All helpers SHALL read and write a single `localStorage` key (`accessToken`). `logout()` SHALL call `clearAccessToken()` AND `clearRole()` (imported from `@/lib/auth`), and then perform a hard navigation to `/admin/login` via `window.location.assign`.

**Previously:** `logout()` called `clearAccessToken()` and then `window.location.assign('/admin/login')`. The role key did not exist.

**Now:** `logout()` additionally clears the `staffRole` localStorage key so a subsequent login starts from a clean role state.

Refs: PDD §7.1 Phase 1 step 4; INV-002; spec `staff-auth`.

#### Scenario: setAccessToken persists token for subsequent requests
- **WHEN** `setAccessToken('abc')` is called
- **THEN** `localStorage.getItem('accessToken')` returns `'abc'`, and the next `authenticatedFetch` call includes `Authorization: Bearer abc` in its request headers

#### Scenario: clearAccessToken removes token
- **WHEN** `setAccessToken('abc')` is called, then `clearAccessToken()` is called
- **THEN** `localStorage.getItem('accessToken')` returns `null`, and the next `authenticatedFetch` call is sent WITHOUT an `Authorization` header

#### Scenario: logout clears token, role, and redirects
- **WHEN** `setAccessToken('abc')` and `setRole('courier')` are called, then `logout()` is called
- **THEN** `localStorage.getItem('accessToken')` returns `null`, `localStorage.getItem('staffRole')` returns `null`, `window.location.assign` is called with `'/admin/login'`, and the function returns `undefined`

#### Scenario: logout has no React context dependency
- **WHEN** `logout()` is imported from `@/api/client` and called from a non-component module (e.g., a utility, an event handler outside a component tree, or a test)
- **THEN** it completes without throwing and does NOT require a `useNavigate` / router context to be present

### Requirement: Staff login API wrapper
The admin SPA SHALL expose `staffLogin(login: string, password: string): Promise<{ access_token: string; role: string }>` from `web/admin/src/api/client.ts`. It SHALL `POST` to `/api/v1/staff/auth/login` with JSON body `{login, password}` and `Content-Type: application/json`. On a 2xx response it SHALL return the parsed body narrowed to `{access_token, role}`. On non-2xx it SHALL throw `ApiError(status, body, message)`. It MUST NOT attach an `Authorization` header, and it MUST NOT go through `authenticatedFetch`. Refs: spec `staff-auth` §Staff login endpoint.

#### Scenario: Successful login returns access token
- **WHEN** `staffLogin('admin', 'correct-password')` is called and the backend responds 200 with `{access_token: 'jwt', refresh_token: 'rt', token_type: 'bearer', role: 'admin'}`
- **THEN** the call resolves to `{access_token: 'jwt', role: 'admin'}` and the `refresh_token` field is ignored (not returned, not stored, not logged)

#### Scenario: Invalid credentials throw ApiError(401)
- **WHEN** `staffLogin('admin', 'wrong-password')` is called and the backend responds 401 with `{detail: 'Invalid credentials'}`
- **THEN** the call rejects with an `ApiError` whose `status` is 401 and whose `body` contains `{detail: 'Invalid credentials'}`

#### Scenario: Login request carries no auth header
- **WHEN** `staffLogin(...)` is called
- **THEN** the outgoing `POST /api/v1/staff/auth/login` request has `Content-Type: application/json` and no `Authorization` header, even if `localStorage.accessToken` is set to a stale value

### Requirement: Client-wide 401 redirect handler
`authenticatedFetch` in `web/admin/src/api/client.ts` SHALL, on receiving an HTTP 401 response for any path EXCEPT one ending with `/staff/auth/login`, call `clearAccessToken()`, then call `window.location.assign('/admin/login?returnUrl=<router-relative current path>')` where `<router-relative current path>` is `window.location.pathname + window.location.search` with a leading `/admin` segment stripped. After the redirect side effect, `authenticatedFetch` SHALL still throw `ApiError(401, body, message)` so in-flight callers' `catch` and `finally` blocks execute cleanly. Refs: PDD §7.1 Phase 1 step 4.

#### Scenario: 401 on a protected endpoint redirects to login with returnUrl
- **GIVEN** the browser is at `http://localhost:8240/admin/menu`
- **WHEN** `authenticatedFetch('/api/v1/admin/menu/categories')` receives HTTP 401
- **THEN** `localStorage.accessToken` is cleared, AND `window.location.assign` is called with `'/admin/login?returnUrl=%2Fmenu'`, AND the promise rejects with `ApiError(401, ...)`

#### Scenario: 401 on login endpoint does NOT redirect
- **GIVEN** the browser is at `http://localhost:8240/admin/login`
- **WHEN** the login request to `/api/v1/staff/auth/login` receives HTTP 401 (wrong credentials)
- **THEN** `window.location.assign` is NOT called, `localStorage.accessToken` is NOT modified, and the caller receives the `ApiError(401)` to display an inline form error

#### Scenario: Non-401 errors do not trigger redirect
- **WHEN** `authenticatedFetch(...)` receives HTTP 500, 422, 409, or any non-401 error
- **THEN** `window.location.assign` is NOT called, `localStorage.accessToken` is NOT modified, and the `ApiError` is thrown as before

#### Scenario: Successful response does not trigger redirect
- **WHEN** `authenticatedFetch(...)` receives HTTP 200
- **THEN** `window.location.assign` is NOT called and the response is returned unchanged

#### Scenario: Current sessionExpired call sites keep working
- **GIVEN** Menu pages (`CategoryList.tsx`, `MenuItemsTable.tsx`, `ModifiersPanel.tsx`, `MenuItemFormDialog.tsx`) currently branch on `err instanceof ApiError && err.status === 401` to show `common.sessionExpired`
- **WHEN** an authenticated request from those pages receives 401
- **THEN** the 401 handler redirects the browser before React re-renders, so the `sessionExpired` toast is never actually displayed — AND the existing `catch` / `finally` blocks still run because `authenticatedFetch` still throws after the redirect

### Requirement: Admin login page
The admin SPA SHALL provide a login page at `/login` (under `basename="/admin"`, so `/admin/login` in the browser). The page SHALL render outside the admin `Layout` (no sidebar, no header chrome) and SHALL include: a `login` text input, a `password` input, a submit button, an inline error region (`role="alert"`), and bilingual labels via `react-i18next` under the `auth.login.*` namespace.

The submit button SHALL be disabled when either field is empty OR when a request is in flight. On submit, the page SHALL call `staffLogin(login, password)`, then `setAccessToken(result.access_token)`, then `setRole(result.role)`, then navigate by role:

- If `result.role === 'courier'` → navigate to `/courier` with `{ replace: true }`, **ignoring** any `returnUrl` query parameter.
- Otherwise (admin or barista) → navigate to `returnUrl` (from the `returnUrl` query parameter) or `/` if not present, using `navigate(..., { replace: true })`.

**Previously:** On submit the page called `staffLogin`, then `setAccessToken(result.access_token)`, then navigated to `returnUrl ?? '/'`. The `role` field of the `staffLogin` response was discarded; all roles landed on `/` by default.

**Now:** `role` is persisted via `setRole(result.role)` before navigation, and couriers are routed to `/courier` regardless of `returnUrl`. Admin and barista behavior for non-courier roles is unchanged.

Refs: spec `staff-auth` §Staff login endpoint; PDD §7.1 Phase 1 step 4; PDD §4.5 (courier dedicated view); INV-010.

#### Scenario: Successful admin login navigates to dashboard
- **WHEN** a user opens `/admin/login` (no `returnUrl`), enters valid admin credentials, and the backend returns `{access_token, role: 'admin'}`
- **THEN** `setAccessToken` is called with `access_token`, `setRole('admin')` is called, and the router navigates to `/` with `{ replace: true }`

#### Scenario: Successful courier login navigates to /courier
- **WHEN** a user opens `/admin/login` (no `returnUrl`), enters valid courier credentials, and the backend returns `{access_token, role: 'courier'}`
- **THEN** `setAccessToken` is called, `setRole('courier')` is called, and the router navigates to `/courier` with `{ replace: true }`

#### Scenario: Courier login ignores returnUrl
- **WHEN** a user opens `/admin/login?returnUrl=%2Fmenu`, enters valid courier credentials, and the backend returns `role: 'courier'`
- **THEN** the router navigates to `/courier` (NOT `/menu`) with `{ replace: true }`

#### Scenario: returnUrl forwarded from protected-route redirect for admin
- **WHEN** an unauthenticated user navigates to `/admin/menu`, is redirected to `/admin/login?returnUrl=%2Fmenu`, and submits valid admin credentials
- **THEN** after a successful login the router navigates to `/menu` with `{ replace: true }` (NOT to `/`)

#### Scenario: Invalid credentials show inline error
- **WHEN** a user submits credentials that the backend rejects with 401
- **THEN** `setAccessToken` is NOT called, `setRole` is NOT called, the page stays on `/admin/login`, and the inline `role="alert"` region displays the `auth.login.invalidCredentials` i18n string

#### Scenario: Submit button disabled while request is in flight
- **WHEN** the user submits the form
- **THEN** the submit button is disabled until the `staffLogin` promise resolves or rejects, and both input fields remain enabled (to preserve typed values) but a second submission is not possible

#### Scenario: Login page is not protected
- **WHEN** a user with a valid token in `localStorage` navigates directly to `/admin/login`
- **THEN** the login page renders (the route is NOT wrapped in `ProtectedRoute`), and the user can still choose to re-log in; on successful re-login, the previous token AND role are overwritten

#### Scenario: Bilingual labels
- **WHEN** the language switcher toggles between RU and EN on the login page
- **THEN** every visible label, placeholder, button text, and error message updates to the selected language via the `auth.login.*` i18n keys

### Requirement: Admin ProtectedRoute guard
The admin SPA SHALL provide a `ProtectedRoute` component at `web/admin/src/components/ProtectedRoute.tsx`. It SHALL accept an optional prop `allowedRoles?: StaffRole[]`. It SHALL synchronously read `getAccessToken()` and (when `allowedRoles` is set) `getRole()` on every render and:

- When no token is present → emit `<Navigate to='/login?returnUrl=<encoded current path>' replace />`.
- When a token is present AND `allowedRoles` is omitted → render `children` unchanged (legacy behavior, preserved so existing callers do not need to opt into role checking).
- When a token is present AND `allowedRoles` is set AND `getRole()` is one of the allowed roles → render `children`.
- When a token is present AND `allowedRoles` is set AND `getRole()` is NOT one of the allowed roles → emit `<Navigate to='/courier' replace />` if `getRole() === 'courier'`, else `<Navigate to='/' replace />`.

It MUST NOT use React state, effects, or subscriptions. It MUST NOT decode the JWT — `role` is read from `localStorage` via `getRole()`, not from the token. Refs: INV-002; INV-010; spec `rbac`.

**Previously:** `ProtectedRoute` only checked token presence and rendered `children` on any token. No role-based redirect existed; a courier could reach every admin route.

**Now:** `ProtectedRoute` accepts `allowedRoles` and redirects mismatched roles — couriers to `/courier`, others to `/`. When `allowedRoles` is omitted, behavior is identical to before, so the `/courier` route can reuse the same component with a different `allowedRoles` set.

#### Scenario: Authenticated request renders children when allowedRoles omitted
- **WHEN** `localStorage.accessToken` is set and `ProtectedRoute` renders without `allowedRoles`
- **THEN** its `children` are rendered unchanged regardless of `staffRole`

#### Scenario: Authenticated request renders children when role is allowed
- **WHEN** `localStorage.accessToken` is set, `localStorage.staffRole` is `'admin'`, and `ProtectedRoute` renders with `allowedRoles={['admin', 'barista']}`
- **THEN** its `children` are rendered unchanged

#### Scenario: Courier redirected away from admin-only route
- **WHEN** `localStorage.accessToken` is set, `localStorage.staffRole` is `'courier'`, and `ProtectedRoute` renders with `allowedRoles={['admin', 'barista']}`
- **THEN** React Router navigates to `/courier` with `replace: true`

#### Scenario: Admin on a courier-only gated route is allowed
- **WHEN** `localStorage.accessToken` is set, `localStorage.staffRole` is `'admin'`, and `ProtectedRoute` renders with `allowedRoles={['admin', 'courier']}`
- **THEN** its `children` are rendered unchanged (admins retain access to the courier view for debugging)

#### Scenario: Barista redirected away from courier-only route
- **WHEN** `localStorage.accessToken` is set, `localStorage.staffRole` is `'barista'`, and `ProtectedRoute` renders with `allowedRoles={['admin', 'courier']}`
- **THEN** React Router navigates to `/` with `replace: true`

#### Scenario: Unauthenticated request still redirects to login
- **WHEN** `localStorage.accessToken` is absent and `ProtectedRoute` renders at location `/courier` with any `allowedRoles`
- **THEN** React Router navigates to `/login?returnUrl=%2Fcourier` with `replace: true` (the role check is skipped — no-token takes precedence)

#### Scenario: Missing role with allowedRoles set is treated as unauthorized
- **WHEN** `localStorage.accessToken` is set but `localStorage.staffRole` is absent (`getRole()` returns `null`), and `ProtectedRoute` renders with `allowedRoles={['admin']}`
- **THEN** React Router navigates to `/` with `replace: true` (null is not in any allow-list; fall through to the default redirect)

#### Scenario: No token decoding
- **WHEN** `ProtectedRoute` renders with a token present
- **THEN** it does NOT parse the JWT, does NOT check `exp`, and does NOT read `role` from the token — role is read exclusively via `getRole()` from `localStorage`

### Requirement: Admin role storage helpers

The admin SPA SHALL expose role helpers from `web/admin/src/lib/auth.ts`: `getRole(): StaffRole | null`, `setRole(role: StaffRole): void`, `clearRole(): void`, and `useCurrentRole(): StaffRole | null`. `StaffRole` SHALL be the union type `'admin' | 'barista' | 'courier'`. The three non-hook helpers SHALL read and write a single `localStorage` key (`staffRole`). `setRole` SHALL reject any value outside the `StaffRole` union (narrowed at the TypeScript type level; at runtime, `setRole` MAY skip the check since the caller is always `staffLogin` output). `useCurrentRole` SHALL wrap `getRole()` in `useMemo(..., [])` so the value is captured once per component mount and NOT subscribed to `localStorage` changes.

Refs: PDD §4.5 (role-filtered admin panel), INV-010 (client role is a UX hint — server remains the source of truth); design.md D1.

#### Scenario: setRole persists role across a page reload
- **WHEN** `setRole('courier')` is called and the page is reloaded
- **THEN** `getRole()` returns `'courier'`

#### Scenario: clearRole removes the persisted role
- **WHEN** `setRole('courier')` is called, then `clearRole()` is called
- **THEN** `getRole()` returns `null`

#### Scenario: getRole with no persisted value returns null
- **WHEN** `localStorage` contains no `staffRole` key
- **THEN** `getRole()` returns `null` (NOT `undefined`, NOT the string `"null"`)

#### Scenario: getRole narrows to StaffRole at compile time
- **WHEN** TypeScript consumers write `const r = getRole(); if (r === 'courier') { ... }`
- **THEN** the compiler does NOT error on the comparison (i.e. `StaffRole | null` is the inferred return type, not `string | null`)

#### Scenario: useCurrentRole exposed from the module
- **WHEN** a consumer writes `import { useCurrentRole } from '@/lib/auth'`
- **THEN** TypeScript resolves the import and the hook returns `StaffRole | null`

### Requirement: Admin useCurrentRole hook

The admin SPA SHALL expose `useCurrentRole(): StaffRole | null` from `web/admin/src/lib/auth.ts`. The hook SHALL return the value of `getRole()` captured once at component mount via `useMemo(() => getRole(), [])`. It MUST NOT subscribe to the `storage` event, MUST NOT use `useState`, and MUST NOT trigger re-renders when `localStorage.staffRole` changes mid-session.

Consumers that are rendered inside `ProtectedRoute` with a non-empty `allowedRoles` MAY treat a `null` return as unreachable, but MUST still narrow the type (e.g., via an early return) so that TypeScript inference holds without `!` assertions.

Refs: PDD §4.5 (role-filtered admin panel); INV-010 (server-side authoritative); design.md D1 / D3.

#### Scenario: Returns null when no role persisted
- **WHEN** `localStorage` contains no `staffRole` key and a test component calls `useCurrentRole()`
- **THEN** the hook returns `null`

#### Scenario: Returns persisted role after setRole
- **WHEN** `setRole('barista')` is called, then a test component calls `useCurrentRole()` via `renderHook`
- **THEN** the hook returns `'barista'`

#### Scenario: Value is stable across re-renders within a session
- **WHEN** `setRole('admin')` is called, `useCurrentRole()` is read once (returns `'admin'`), then `setRole('barista')` is called in-place, and the consuming component re-renders without un-mounting
- **THEN** the hook STILL returns `'admin'` (the cached value), reflecting the `useMemo(..., [])` contract — no reactive subscription on `localStorage`

### Requirement: Role-filtered admin sidebar

The admin `Layout` component at `web/admin/src/components/Layout.tsx` SHALL filter its `navItems` through a static `NAV_BY_ROLE: Record<StaffRole, readonly string[]>` map, keyed by `StaffRole` and exhaustive at the TypeScript type level. The mapping SHALL be:

- `admin` → `['dashboard', 'orders', 'menu', 'users', 'promos', 'settings']` (all 6 nav items).
- `barista` → `['orders', 'menu']` (orders for queue; menu for stop-list management, PDD §4.5).
- `courier` → `[]` (courier uses `CourierShell`; empty array is a defensive default for edge-case routing).

When `useCurrentRole()` returns `null`, Layout SHALL render zero nav links. Each rendered `<Link>` SHALL carry a `data-testid` attribute of the form `nav-<key>` (e.g., `nav-orders`) to support role-matrix tests independent of i18n labels.

This requirement affects UX only — INV-010 RBAC enforcement remains server-side via `rbac_matrix`, and client-side routing remains gated by `ProtectedRoute.allowedRoles` in `App.tsx`.

Refs: PDD §4.5; INV-010; design.md D2 / D4.

#### Scenario: Admin sees all six nav items
- **WHEN** `setRole('admin')` is called and `<Layout>` renders inside `<MemoryRouter>`
- **THEN** the DOM contains links with `data-testid` values `nav-dashboard`, `nav-orders`, `nav-menu`, `nav-users`, `nav-promos`, `nav-settings`

#### Scenario: Barista sees only orders and menu
- **WHEN** `setRole('barista')` is called and `<Layout>` renders
- **THEN** the DOM contains `nav-orders` and `nav-menu` links, AND does NOT contain `nav-dashboard`, `nav-users`, `nav-promos`, `nav-settings`

#### Scenario: Courier sees zero nav links
- **WHEN** `setRole('courier')` is called and `<Layout>` renders
- **THEN** the DOM contains no element with a `data-testid` prefix of `nav-`

#### Scenario: No persisted role renders zero nav links
- **WHEN** `clearRole()` is called (no `staffRole` in `localStorage`) and `<Layout>` renders
- **THEN** the DOM contains no element with a `data-testid` prefix of `nav-`

#### Scenario: Role map is exhaustive at compile time
- **WHEN** a developer adds a new variant to the `StaffRole` union (e.g., `'manager'`) without updating `NAV_BY_ROLE`
- **THEN** the TypeScript compiler emits an error on the `Record<StaffRole, readonly string[]>` literal (missing property), preventing the build

