## Why

The admin SPA (`web/admin/`) has no login flow. `web/admin/src/api/client.ts:1-4` ships a stub `getAccessToken()` that reads `localStorage.getItem('accessToken')`, but nothing in the codebase ever writes it. To test anything behind RBAC, developers currently `curl POST /api/v1/staff/auth/login`, copy the token, and paste it into DevTools → Application → Local Storage by hand. This is blocking manual testing of the Phase 2 menu/cart work that just landed on `menu_cart`, and when the 15-minute access-token TTL elapses mid-session the user sees `common.sessionExpired` toasts on every action with no way to recover except another manual token injection.

The backend is ready: `POST /api/v1/staff/auth/login` exists and returns `{access_token, refresh_token, token_type, role}` (see spec `staff-auth`). RBAC middleware expects `Authorization: Bearer <token>`. What is missing is strictly a UI + client-side plumbing gap in `web/admin/`.

This change closes that gap with the minimum surface area needed to unblock manual testing: a login page, a protected-route wrapper, token setter/clearer on the client, and a 401 handler that redirects to login with a `returnUrl`. No refresh-token handling, no user menu, no logout button — those belong to the sibling change `desktop-nav-and-logout`, which will import the `logout()` primitive this change exposes.

## What Changes

- Add `POST /api/v1/staff/auth/login` wrapper to `web/admin/src/api/client.ts`: extend the file with `setAccessToken()`, `clearAccessToken()`, a `logout()` primitive, and a `staffLogin(login, password)` wrapper calling the backend endpoint.
- Add a 401 handler choke point in `web/admin/src/api/client.ts`: on any `ApiError(401)` from `authenticatedFetch`, clear the stored token and redirect the browser to `/admin/login?returnUrl=<current path>`. One place, not scattered across callers.
- Add `web/admin/src/pages/Login/LoginPage.tsx`: a single-screen form with login + password fields, i18n labels under a new `auth.*` namespace, bilingual (RU + EN). On submit → call `staffLogin` → `setAccessToken(response.access_token)` → navigate to `returnUrl` (from query string) or `/` if none. On 401 → inline error "Invalid credentials" (not the generic toast). Submit is disabled while the request is in flight.
- Add `web/admin/src/components/ProtectedRoute.tsx`: reads `getAccessToken()` and either renders children or `<Navigate to="/login" state={{ returnUrl }} replace />`. Pure token presence — no silent refresh, no JWT decoding, no role checks (roles are enforced server-side; UI role-gating is a separate concern already handled inside Menu pages).
- Wire the new `/login` route into `web/admin/src/App.tsx` outside of `Layout` (so the login page renders without the admin sidebar), and wrap the `Layout` route element with `ProtectedRoute`.
- Add `auth.*` keys to `web/admin/src/i18n/locales/{ru,en}/common.json` (form labels, placeholders, submit button, invalid-credentials error, loading text).

## Capabilities

### New Capabilities
- `admin-auth-ui`: Admin SPA login page, token storage helpers, 401 redirect handler, and protected-route guard wrapping the admin shell.

### Modified Capabilities
- `frontend-routing`: Add `/login` to the admin SPA route list and require that all non-`/login` admin routes are wrapped with `ProtectedRoute`. The customer-app section of `frontend-routing` is untouched.

## Non-Goals

- **Refresh-token rotation and silent refresh.** The backend exposes `POST /api/v1/staff/auth/refresh`, but this change deliberately does not consume it. When the 15-minute access token expires, the next API call gets 401, the 401 handler redirects to `/login`, and the user logs in again. Adding refresh would require a second storage slot, a retry-on-401 wrapper, race handling for concurrent requests, and a token-rotation contract — all of which is more surface area than Phase 2 manual testing requires. If the 15-minute re-login cadence becomes annoying in practice, it gets its own change.
- **Logout button / user menu / sidebar account display.** The empty sibling change `desktop-nav-and-logout` owns the admin sidebar and account-UI work. This change exports a `logout()` function from `api/client.ts` that `desktop-nav-and-logout` will import and bind to a button — but no button, no menu, no confirmation modal here.
- **Any edits under `web/admin/src/pages/Menu/`.** The five `common.sessionExpired` call sites in `CategoryList.tsx`, `ModifiersPanel.tsx`, `MenuItemsTable.tsx`, and `MenuItemFormDialog.tsx` were audited and are all correctly gated on `err.status === 401`. There is no blanket-catch bug to fix. The misleading UX the audit was tracking comes from *nothing redirecting on 401*, which this change fixes in `api/client.ts` — once the 401 handler redirects, those toasts effectively never render, even though the code is untouched. Touching Menu files would also collide with Thread 2's scope boundary.
- **JWT decoding, role extraction, role-gated routes.** RBAC is enforced server-side (see `rbac` spec). Role-aware UI hiding inside Menu pages already works off a `useCurrentRole()` stub and is out of scope here.
- **Customer SPA changes.** Customer auth (`auth-state`, `auth-screens`) is a separate phone/OTP flow with its own `AuthProvider` context. This change does not touch `web/customer/`.
- **Porting the customer `AuthProvider` / `AuthContext` pattern into the admin app.** A thin token-in-localStorage + `getAccessToken()` getter is enough for Phase 2. If the admin ever needs silent refresh, role-reactive UI, or a user-object display, that's the moment to introduce a context — not now.
- **Backend, nginx, or docker-compose changes.** The backend `/api/v1/staff/auth/login` endpoint already exists and matches the contract in `staff-auth` spec. Nothing server-side moves.
- **Rate limiting on the login form**, lockout-after-N-attempts, CAPTCHA. Backend `staff-auth` spec is silent on rate limits for the login endpoint; adding a client-side limiter would be security theater. If rate limiting is needed, it belongs in core-api.
- **Persistent "remember me" / session extension.** Token lives until the tab is closed or the 15-minute TTL hits, whichever comes first.

## Impact

- **MVP phase**: Phase 1 (Auth) delivery gap for the admin app, blocking Phase 2 (Menu & Cart) manual testing. Per PDD §7.1, staff auth is Phase 1 step 4; this change wires the SPA side of that.
- **Affected code**:
  - `web/admin/src/api/client.ts` — extend with `setAccessToken`, `clearAccessToken`, `logout`, `staffLogin`, and a 401 handler that clears + redirects. The existing `getAccessToken` stub stays (callers already use it).
  - `web/admin/src/pages/Login/LoginPage.tsx` — new file. `web/admin/src/pages/Login/index.ts` barrel for the `MenuPage`-style export.
  - `web/admin/src/components/ProtectedRoute.tsx` — new file.
  - `web/admin/src/App.tsx` — add `/login` route outside `Layout`, wrap `Layout` element in `ProtectedRoute`.
  - `web/admin/src/i18n/locales/ru/common.json` + `web/admin/src/i18n/locales/en/common.json` — add `auth.login.*` keys. No changes to `common.sessionExpired` (it stays; its call sites are already correctly gated).
  - Tests: `web/admin/src/api/client.test.ts` — add coverage for `setAccessToken`/`clearAccessToken`/`logout`/`staffLogin` + the 401 handler. `web/admin/src/components/ProtectedRoute.test.tsx` — new file. `web/admin/src/pages/Login/LoginPage.test.tsx` — new file (form submit path, invalid credentials path, returnUrl path).
- **APIs consumed**:
  - `POST /api/v1/staff/auth/login` → returns `{access_token, refresh_token, token_type, role}`. Only `access_token` is stored; `refresh_token` is ignored (see Non-Goals).
- **Dependencies**: no new runtime deps. React Router already provides `<Navigate>`, `useNavigate`, and `useSearchParams`.
- **Inviolable rules touched**: INV-002 (server-side auth on mutations — unchanged, this change only wires the *client* to supply a token); INV-015 (secrets in env vars — access token lives only in `localStorage` on the user's device, never in source).
- **Scope collision check**: Thread 2 (Menu/cart feature work under `web/admin/src/pages/Menu/`) is untouched. The sibling empty change `desktop-nav-and-logout` is untouched; it will later import `logout()` from `api/client.ts` and bind it to a button. Customer SPA auth is untouched.
- **Risk**: low. No schema, no backend, no migration, no shared package. Blast radius is one SPA bundle. The main failure mode is "login flow works but token still isn't attached" — covered by the existing `authenticatedFetch` test plus a new end-to-end test asserting that `LoginPage.submit → next authenticatedFetch carries Authorization header`.
