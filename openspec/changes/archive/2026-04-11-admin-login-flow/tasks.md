## 1. Token helpers and login wrapper in api/client.ts

- [x] 1.1 [web-admin] IMPL: Extend `web/admin/src/api/client.ts` with module-level constant `STORAGE_KEY = 'accessToken'` and refactor the existing `getAccessToken()` stub to read from `STORAGE_KEY`. Behavior unchanged; this is a rename-in-place that keeps the existing `localStorage.getItem('accessToken')` semantics but routes it through the constant so D1 stays a single source of truth.
- [x] 1.2 [web-admin] IMPL: Add `setAccessToken(token: string): void` and `clearAccessToken(): void` exports to `web/admin/src/api/client.ts`, both delegating to `localStorage` via `STORAGE_KEY`. No side effects beyond the `localStorage` write.
- [x] 1.3 [web-admin] IMPL: Add `logout(): void` export to `web/admin/src/api/client.ts` that calls `clearAccessToken()` then `window.location.assign('/admin/login')`. No return value, no context dependencies. Per D2.
- [x] 1.4 [web-admin] IMPL: Add `staffLogin(login, password)` export to `web/admin/src/api/client.ts` that POSTs to `/api/v1/staff/auth/login` via a plain `fetch` (NOT `authenticatedFetch`), parses JSON, and returns `{ access_token: string; role: string }`. On non-2xx throw `ApiError` with the same shape `authenticatedFetch` throws. Per D7 and D8.
- [x] 1.5 [web-admin] TEST: Add test cases to `web/admin/src/api/client.test.ts` covering `setAccessToken` / `clearAccessToken` / `getAccessToken` round-trip, `logout()` calling `clearAccessToken` and `window.location.assign('/admin/login')` (stubbed), `staffLogin` success path (returns parsed body), `staffLogin` 401 path (throws `ApiError(401, …)`), and that `staffLogin` does NOT trigger the 401 redirect handler (i.e. no `window.location.assign` call on its own 401 — covered by the D3 skip).

## 2. 401 handler inside authenticatedFetch

- [x] 2.1 [web-admin] IMPL: Extend `authenticatedFetch` in `web/admin/src/api/client.ts` so that when the response status is 401 AND the path does not end with `/staff/auth/login`, it calls `clearAccessToken()` and `window.location.assign('/admin/login?returnUrl=' + encodeURIComponent(returnUrl))` *before* throwing `ApiError`. `returnUrl` is derived from `window.location.pathname + window.location.search`, with the leading `/admin` stripped (so router-relative paths are stored). Per D3.
- [x] 2.2 [web-admin] TEST: Add test cases to `web/admin/src/api/client.test.ts`: (a) 401 on `/api/v1/admin/menu/categories` calls `window.location.assign` with `/admin/login?returnUrl=%2Fmenu` when current path is `/admin/menu`, AND clears `localStorage.accessToken`, AND throws `ApiError(401)`; (b) 401 on `/api/v1/staff/auth/login` does NOT call `window.location.assign` and does NOT clear the token; (c) 500 on any path does NOT call `window.location.assign`; (d) 200 on any path does NOT call `window.location.assign`.
- [x] 2.3 [web-admin] REFACTOR: Sanity-read the final `api/client.ts` file, confirm the 401 branch lives inside the existing `if (!response.ok)` block and that the `throw` still runs after the redirect side-effect (so callers' `catch` blocks still fire).

## 3. ProtectedRoute component

- [x] 3.1 [web-admin] IMPL: Create `web/admin/src/components/ProtectedRoute.tsx` per D4: imports `getAccessToken` from `@/api/client`, reads the token synchronously, renders children if present, otherwise returns `<Navigate to={'/login?returnUrl=' + encodeURIComponent(location.pathname + location.search)} replace />`.
- [x] 3.2 [web-admin] TEST: Create `web/admin/src/components/ProtectedRoute.test.tsx`: (a) with a token in `localStorage`, children render; (b) with no token, `<Navigate>` is emitted with the expected `to` value (use a test that renders `ProtectedRoute` inside a `MemoryRouter` at `/menu` and asserts the final rendered location is `/login?returnUrl=%2Fmenu`); (c) `replace` is set so the back button doesn't return to the protected page.

## 4. LoginPage

- [x] 4.1 [web-admin] IMPL: Create `web/admin/src/pages/Login/LoginPage.tsx` per D5. Component state: `login` (string), `password` (string), `error` (string | null), `loading` (boolean). Submit handler wires to `staffLogin` → `setAccessToken` → `navigate(returnUrl ?? '/', { replace: true })`. On `ApiError(401)` sets `error` to `t('auth.login.invalidCredentials')`; on other errors sets it to `t('common.error')`. `returnUrl` is read from `useSearchParams().get('returnUrl')`. Submit button disabled when `!login || !password || loading`. Inline error renders in a `<p role="alert">` below the password field.
- [x] 4.2 [web-admin] IMPL: Create `web/admin/src/pages/Login/index.ts` barrel that re-exports `LoginPage`, matching the pattern used by `pages/Menu/index.tsx`.
- [x] 4.3 [web-admin] TEST: Create `web/admin/src/pages/Login/LoginPage.test.tsx`: (a) renders login + password fields and a disabled submit when fields are empty; (b) enables submit when both fields have values; (c) submitting with valid creds calls `staffLogin` (mocked), calls `setAccessToken` with the returned `access_token`, and navigates to `/` when no `returnUrl` is present; (d) submitting with a `returnUrl=%2Fmenu` query param navigates to `/menu` on success; (e) on `ApiError(401)` from `staffLogin`, the inline error `auth.login.invalidCredentials` is displayed and `setAccessToken` is NOT called; (f) the submit button is disabled during an in-flight request.

## 5. Route wiring in App.tsx

- [x] 5.1 [web-admin] IMPL: Edit `web/admin/src/App.tsx` per D6: import `LoginPage` from `@/pages/Login` and `ProtectedRoute` from `@/components/ProtectedRoute`. Add `<Route path="/login" element={<LoginPage />} />` as a sibling of the existing `Layout` route. Wrap the `Layout` route's element in `<ProtectedRoute>`.
- [x] 5.2 [web-admin] TEST: Extend `web/admin/src/App.test.tsx` (or add a new smoke-test file if the existing one is too narrow): (a) visiting `/` with no token renders the login page (asserted by matching a known `auth.login.*` i18n string); (b) visiting `/` with a token in `localStorage` renders the dashboard; (c) visiting `/login` directly always renders the login page regardless of token presence.

## 6. i18n keys

- [x] 6.1 [web-admin] IMPL: Add `auth.login.*` keys to `web/admin/src/i18n/locales/ru/common.json`: `title` ("Вход"), `loginLabel` ("Логин"), `loginPlaceholder` ("Введите логин"), `passwordLabel` ("Пароль"), `passwordPlaceholder` ("Введите пароль"), `submit` ("Войти"), `submitLoading` ("Вход..."), `invalidCredentials` ("Неверный логин или пароль"). Do NOT touch the existing `common.sessionExpired` entry.
- [x] 6.2 [web-admin] IMPL: Add the mirrored `auth.login.*` keys to `web/admin/src/i18n/locales/en/common.json` with English values ("Sign in", "Login", "Enter login", "Password", "Enter password", "Sign in", "Signing in…", "Invalid login or password").
- [x] 6.3 [web-admin] VERIFY: Grep `web/admin/src/pages/Login/` for hard-coded Russian or English string literals; fail the task if any are found outside of i18n call arguments.

## 7. Manual acceptance

- [ ] 7.1 [web-admin] VERIFY: With a fresh browser profile (no `localStorage.accessToken`), open `http://localhost:<NGINX_PORT>/admin/` and confirm: (a) redirected to `/admin/login?returnUrl=%2F`; (b) entering a known-good staff login + password lands on the dashboard; (c) `localStorage.accessToken` is now set; (d) navigating to `/admin/menu` works and loads data.
- [ ] 7.2 [web-admin] VERIFY: With the dashboard open, run `localStorage.removeItem('accessToken')` in DevTools, then click any Menu action that triggers a request (e.g., expand a category). Confirm the page redirects to `/admin/login?returnUrl=%2Fmenu` within one request cycle, and that logging in again lands on `/admin/menu` (not `/`).
- [ ] 7.3 [web-admin] VERIFY: With a token in `localStorage`, open `http://localhost:<NGINX_PORT>/admin/login` directly. Confirm the login page renders (the route is NOT protected) and that submitting valid creds still works.
- [ ] 7.4 [web-admin] VERIFY: With a fresh browser profile, attempt to log in with bad credentials. Confirm: (a) the page stays on `/admin/login`; (b) the inline error `auth.login.invalidCredentials` is displayed; (c) `localStorage.accessToken` is NOT set; (d) no `window.location.assign` redirect loop occurred.
- [ ] 7.5 [web-admin] VERIFY: Toggle the language switcher on `/admin/login` and confirm every visible string updates to RU or EN.

## 8. Validation

- [x] 8.1 [web-admin] VERIFY: Run `openspec validate admin-login-flow` and fix any reported issues.
- [x] 8.2 [web-admin] VERIFY: Run `cd web/admin && npm run lint && npm run test && npm run build` — all green.
- [x] 8.3 [web-admin] VERIFY: Run `git diff --stat` against `main` and confirm the file list matches proposal.md §Impact exactly — no stray edits under `web/admin/src/pages/Menu/`, `web/customer/`, `services/`, `deploy/`, or `docker-compose*`.
