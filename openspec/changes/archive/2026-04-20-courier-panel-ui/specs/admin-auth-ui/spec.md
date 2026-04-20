## ADDED Requirements

### Requirement: Admin role storage helpers
The admin SPA SHALL expose role helpers from `web/admin/src/lib/auth.ts`: `getRole(): StaffRole | null`, `setRole(role: StaffRole): void`, and `clearRole(): void`. `StaffRole` SHALL be the union type `'admin' | 'barista' | 'courier'`. All three helpers SHALL read and write a single `localStorage` key (`staffRole`). `setRole` SHALL reject any value outside the `StaffRole` union (narrowed at the TypeScript type level; at runtime, `setRole` MAY skip the check since the caller is always `staffLogin` output). Refs: PDD §4.5 (role-filtered admin panel), INV-010 (client role is a UX hint — server remains the source of truth).

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

## MODIFIED Requirements

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
