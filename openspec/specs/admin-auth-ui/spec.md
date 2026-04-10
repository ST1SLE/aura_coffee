## ADDED Requirements

### Requirement: Admin access-token storage helpers
The admin SPA SHALL expose token helpers from `web/admin/src/api/client.ts`: `getAccessToken(): string | null`, `setAccessToken(token: string): void`, `clearAccessToken(): void`, and `logout(): void`. All helpers SHALL read and write a single `localStorage` key (`accessToken`). `logout()` SHALL call `clearAccessToken()` and then perform a hard navigation to `/admin/login` via `window.location.assign`. Refs: PDD §7.1 Phase 1 step 4; INV-002; spec `staff-auth`.

#### Scenario: setAccessToken persists token for subsequent requests
- **WHEN** `setAccessToken('abc')` is called
- **THEN** `localStorage.getItem('accessToken')` returns `'abc'`, and the next `authenticatedFetch` call includes `Authorization: Bearer abc` in its request headers

#### Scenario: clearAccessToken removes token
- **WHEN** `setAccessToken('abc')` is called, then `clearAccessToken()` is called
- **THEN** `localStorage.getItem('accessToken')` returns `null`, and the next `authenticatedFetch` call is sent WITHOUT an `Authorization` header

#### Scenario: logout clears token and redirects
- **WHEN** `logout()` is called from any module (with or without a React component context)
- **THEN** `localStorage.getItem('accessToken')` returns `null`, AND `window.location.assign` is called with the argument `'/admin/login'`, AND the function returns `undefined`

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

The submit button SHALL be disabled when either field is empty OR when a request is in flight. On submit, the page SHALL call `staffLogin(login, password)`, then `setAccessToken(result.access_token)`, then navigate to `returnUrl` (from the `returnUrl` query parameter) or `/` if not present, using `navigate(..., { replace: true })`.

Refs: spec `staff-auth` §Staff login endpoint; PDD §7.1 Phase 1 step 4.

#### Scenario: Successful login navigates to dashboard
- **WHEN** a user opens `/admin/login` (no `returnUrl`), enters valid credentials, and submits
- **THEN** `staffLogin` is called, `setAccessToken` is called with the returned `access_token`, and the router navigates to `/` (dashboard) with `{ replace: true }`

#### Scenario: returnUrl forwarded from protected-route redirect
- **WHEN** an unauthenticated user navigates to `/admin/menu`, is redirected to `/admin/login?returnUrl=%2Fmenu`, and submits valid credentials
- **THEN** after a successful login the router navigates to `/menu` with `{ replace: true }` (NOT to `/`)

#### Scenario: Invalid credentials show inline error
- **WHEN** a user submits credentials that the backend rejects with 401
- **THEN** `setAccessToken` is NOT called, the page stays on `/admin/login`, and the inline `role="alert"` region displays the `auth.login.invalidCredentials` i18n string

#### Scenario: Submit button disabled while request is in flight
- **WHEN** the user submits the form
- **THEN** the submit button is disabled until the `staffLogin` promise resolves or rejects, and both input fields remain enabled (to preserve typed values) but a second submission is not possible

#### Scenario: Login page is not protected
- **WHEN** a user with a valid token in `localStorage` navigates directly to `/admin/login`
- **THEN** the login page renders (the route is NOT wrapped in `ProtectedRoute`), and the user can still choose to re-log in; on successful re-login, the previous token is overwritten

#### Scenario: Bilingual labels
- **WHEN** the language switcher toggles between RU and EN on the login page
- **THEN** every visible label, placeholder, button text, and error message updates to the selected language via the `auth.login.*` i18n keys

### Requirement: Admin ProtectedRoute guard
The admin SPA SHALL provide a `ProtectedRoute` component at `web/admin/src/components/ProtectedRoute.tsx`. It SHALL synchronously read `getAccessToken()` on every render and either render its `children` (when a token is present) or emit `<Navigate to='/login?returnUrl=<encoded current path>' replace />` (when no token is present). It MUST NOT use React state, effects, or subscriptions. It MUST NOT decode the token, check expiry, or inspect its claims — server-side RBAC is the source of truth. Refs: INV-002; INV-010; spec `rbac`.

#### Scenario: Authenticated request renders children
- **WHEN** `localStorage.accessToken` is set and `ProtectedRoute` renders
- **THEN** its `children` are rendered unchanged

#### Scenario: Unauthenticated request redirects to login with returnUrl
- **WHEN** `localStorage.accessToken` is absent and `ProtectedRoute` renders at location `/menu?category=42`
- **THEN** React Router navigates to `/login?returnUrl=%2Fmenu%3Fcategory%3D42` with `replace: true`

#### Scenario: No silent refresh
- **WHEN** `ProtectedRoute` renders with no token
- **THEN** it does NOT call any API (no silent refresh, no token probe), and the redirect happens on the first render

#### Scenario: No token decoding
- **WHEN** `ProtectedRoute` renders with a token present
- **THEN** it does NOT parse the JWT, does NOT check `exp`, and does NOT read `role` — an expired or malformed token still renders children, and the next API call's 401 handler takes care of clearing + redirecting
