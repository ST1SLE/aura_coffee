## Context

**Affected modules:** [web-admin].

The admin SPA (`web/admin/`) is live on branch `menu_cart` with a working Menu CRUD page (`pages/Menu/*`, shipped by the archived `menu-admin-ui` change) and placeholder stubs for every other route. Its API client `web/admin/src/api/client.ts` exports `authenticatedFetch(path, init?)` and an `ApiError` class. The file already has a `getAccessToken()` stub (`localStorage.getItem('accessToken')`) and a call-side pattern where every Menu page branches on `err.status === 401` to show the `common.sessionExpired` toast.

The backend side of staff auth is done and documented in spec `staff-auth`: `POST /api/v1/staff/auth/login` accepts `{login, password}`, returns `{access_token (15-min JWT), refresh_token, token_type: "bearer", role}`, 401 on bad creds. RBAC middleware (`spec rbac`) enforces server-side role checks on every admin endpoint.

The customer SPA already ships a full auth system at `web/customer/src/auth/` (`AuthProvider`, `ProtectedRoute`, `token` module, `registerAuthFailureHandler` hook in `web/customer/src/api/client.ts`), built around the phone/OTP flow in specs `auth-screens` and `auth-state`. That pattern is *structurally* useful as a reference but is **not** a direct port target for this change — the customer app needs a React context because it surfaces `user.role`, `isLoading`, and a refresh lifecycle in the UI. The admin app, for Phase 2, needs none of those.

Stakeholders: shop admin + barista (the users), and any developer trying to manually test `menu_cart` without hand-injecting tokens.

Constraints:
- Bilingual UI (RU + EN) via `react-i18next`, `auth.*` namespace, no hard-coded strings in JSX.
- Must not touch `web/admin/src/pages/Menu/*` (Thread 2 boundary).
- Must not touch backend, nginx, docker-compose, or `web/customer/*`.
- Must expose a `logout()` primitive importable by the sibling `desktop-nav-and-logout` change.
- 15-minute access-token TTL is accepted (no refresh).
- Existing `getAccessToken()` callers (four test files + menu page branches) must keep working without edits — the `localStorage` key stays as `accessToken`.
- INV-002 / INV-010 role enforcement is server-side; the client is a courier of the bearer token, not a trust boundary.

## Goals / Non-Goals

**Goals:**
- Let a developer open `http://localhost:<NGINX_PORT>/admin/` in a fresh browser, be redirected to `/admin/login`, enter credentials, and land on the dashboard with `localStorage.accessToken` set — no DevTools gymnastics.
- Give `authenticatedFetch` a single choke point that converts 401 into a clear-token-and-redirect so that a mid-session token expiry takes the user back to login (with `returnUrl` preserved) instead of leaving them stuck on a page that only says "Сессия истекла".
- Expose `logout()` as a standalone function callers can import — no context, no hook — so `desktop-nav-and-logout` can bind it to a button without this change needing to know about the sidebar.
- Keep the edit set small enough that the whole diff can be reviewed in one sitting.

**Non-Goals:**
- React context for auth state. Phase 2 does not need it (see proposal Non-Goals).
- Silent refresh / refresh-token storage. Deliberate.
- Any edits to `pages/Menu/*`. The `sessionExpired` audit finding is "no blanket catches, all five call sites are correctly gated on `status === 401`" — see proposal Non-Goals. Fixing the redirect in `client.ts` makes those toasts effectively invisible without touching the call sites.
- Porting `AuthProvider` / `AuthContext` from `web/customer/`. See Context.
- Rate limiting, CAPTCHA, lockout, remember-me. Out of scope (proposal Non-Goals).
- Role-gated routes. Server-side is the source of truth.

## Decisions

### D1. Token storage: keep `localStorage.accessToken` as-is

Rename considered: `aura_admin_access_token`, to mirror customer's `aura_refresh_token`. **Rejected.** Four files already read/write `accessToken`: `web/admin/src/api/client.ts:3`, `web/admin/src/api/client.test.ts` (token header tests), `web/admin/src/api/menu.test.ts` (test-bed auth state setup), and the documented manual-injection workflow in `menu-admin-ui`'s PR description. Renaming now is 4+ file touches plus test-bed churn for zero testing benefit; it bundles a cosmetic concern into a feature change. If the team wants a standard prefix convention later, it's a one-commit grep-and-replace.

The asymmetry with customer's `aura_refresh_token` is acceptable: they store different things (customer stores the *refresh* token, admin stores the *access* token). If admin ever stores a refresh token, *that* key can follow the convention.

### D2. No React context. A module-level getter/setter pair is the seam.

```ts
// web/admin/src/api/client.ts (additions)

const STORAGE_KEY = 'accessToken';

export function getAccessToken(): string | null {
  return localStorage.getItem(STORAGE_KEY);
}

export function setAccessToken(token: string): void {
  localStorage.setItem(STORAGE_KEY, token);
}

export function clearAccessToken(): void {
  localStorage.removeItem(STORAGE_KEY);
}

export function logout(): void {
  clearAccessToken();
  // Hard navigation so React Router re-evaluates ProtectedRoute
  // against an empty localStorage on reload. Deliberate: the admin SPA is
  // small, a hard reload is cheap, and it guarantees no stale component
  // state survives with a cleared token.
  window.location.assign('/admin/login');
}
```

`logout()` does a full `window.location.assign` rather than `navigate('/login')`. Reason: `navigate` would require logout to be called from within a React component tree that has access to `useNavigate`, which tightly couples `logout()` to a router context. A hard redirect is one line, has no context dependency, and survives being called from anywhere (including a future `desktop-nav-and-logout` button handler that may want to call `logout()` from a click event without threading a hook through). The cost is ~50ms of reload — acceptable for a once-per-shift action.

**Alternative considered:** a React context + `useAuth()` hook + a `logout` closure bound to `useNavigate`. Rejected for Phase 2 — it's the right shape for the customer app because the customer app's UI *reacts* to auth state (showing/hiding the profile page, displaying the user name). The admin SPA doesn't display any of that yet, and `desktop-nav-and-logout`'s scope is "add a sidebar with a logout button," which can just call the imported `logout()` without needing hook-shaped reactivity.

### D3. 401 handler lives inside `authenticatedFetch`, not per-caller.

`authenticatedFetch` already throws `ApiError` on non-2xx. Add a branch: *before* throwing, if `response.status === 401`, call `clearAccessToken()` and `window.location.assign('/admin/login?returnUrl=' + encodeURIComponent(currentPath))`, then still throw so in-flight callers' `catch` blocks resolve cleanly and don't leave dangling state.

```ts
export async function authenticatedFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  // ... existing code ...

  const response = await fetch(`${BASE_URL}${path}`, merged);

  if (!response.ok) {
    let body: unknown = null;
    try { body = await response.clone().json(); } catch {}

    if (response.status === 401 && !path.endsWith('/staff/auth/login')) {
      clearAccessToken();
      const currentPath = window.location.pathname + window.location.search;
      const returnUrl = encodeURIComponent(
        currentPath.replace(/^\/admin/, '') || '/',
      );
      window.location.assign(`/admin/login?returnUrl=${returnUrl}`);
    }

    throw new ApiError(
      response.status,
      body,
      `HTTP ${response.status}: ${path}`,
    );
  }

  return response;
}
```

Three subtle points:

1. **Skip the 401 handler for the login endpoint itself.** Otherwise a wrong password triggers the redirect, clobbering the `LoginPage` inline error. The check `path.endsWith('/staff/auth/login')` is one line and obvious.
2. **Strip the `/admin` prefix from `returnUrl`.** React Router uses `basename="/admin"` so its paths are `/menu`, not `/admin/menu`. The `LoginPage` navigates with router-relative paths, so we store router-relative paths.
3. **Still throw the `ApiError`.** Callers in `pages/Menu/*` already have `catch` blocks that expect an error. Swallowing the throw would leave their `setLoading(false)` / `finally` blocks in undefined states. The user never sees the `sessionExpired` toast because the page navigates away before React renders it — but the promise chain still unwinds cleanly.

**Alternative considered:** a `registerAuthFailureHandler` hook like the customer app uses. Rejected for Phase 2 — the registration hook is only worth its weight when the handler needs to touch React state (e.g., clearing a context). Here the handler is one `window.location.assign`, which has no dependencies to inject.

**Trade-off:** the 401 handler uses `window.location`, which makes `authenticatedFetch` non-trivially pure. Tests must mock `window.location.assign`. This is already done for other `window` APIs in the admin test bed.

### D4. `ProtectedRoute` reads `localStorage` directly — no subscription.

```ts
// web/admin/src/components/ProtectedRoute.tsx
import { Navigate, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';
import { getAccessToken } from '@/api/client';

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const token = getAccessToken();
  const location = useLocation();

  if (!token) {
    const returnUrl = location.pathname + location.search;
    return (
      <Navigate
        to={`/login?returnUrl=${encodeURIComponent(returnUrl)}`}
        replace
      />
    );
  }

  return <>{children}</>;
}
```

**Rationale:** `ProtectedRoute` runs on every navigation, `localStorage.getItem` is synchronous and cheap, and we don't need reactivity — once the token is gone, the 401 handler's `window.location.assign` already forces a hard navigation that re-mounts the whole SPA. No `useState`, no `useEffect`, no subscription to storage events. Simpler to reason about and eliminates a class of race conditions (token cleared in one tab, other tab still thinks it's authed) because the hard redirect happens on the next API call anyway.

**Alternative considered:** wrap every individual route in `<ProtectedRoute>`. Rejected — we have six routes and want the same policy on all of them. Wrapping the shared `<Layout>` element once is idiomatic React Router and matches the customer SPA pattern.

### D5. Login page shape: server-validated, inline error, no client-side credential rules.

- Two inputs: `login` (text), `password` (password).
- Submit disabled when either field is empty or a request is in flight.
- On submit: `setError(null); setLoading(true); try { const r = await staffLogin(login, password); setAccessToken(r.access_token); navigate(returnUrl ?? '/', { replace: true }); } catch (e) { if (e instanceof ApiError && e.status === 401) setError(t('auth.login.invalidCredentials')); else setError(t('common.error')); } finally { setLoading(false); }`
- Inline error lives in a `<p role="alert">` below the password field.
- `returnUrl` comes from `useSearchParams()` (`searchParams.get('returnUrl')`), not from `location.state`. Why: the 401 handler in `authenticatedFetch` uses `window.location.assign(...)` which loses React Router `location.state`. Using a query param means both entry paths into the login page (router `<Navigate>` from `ProtectedRoute` and hard redirect from the 401 handler) work the same way.
- Form styling is the same Tailwind + shadcn primitives (`input`, `button`, `label`) already vendored by `menu-admin-ui`. No new primitives.
- No "forgot password" link — the backend `staff-auth` spec has no reset endpoint. If added later, it's an i18n-key change.

### D6. Route wiring in `App.tsx`

```tsx
// web/admin/src/App.tsx (sketch, NOT the actual edit)
<BrowserRouter basename="/admin">
  <Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route
      element={
        <ProtectedRoute>
          <Layout />
        </ProtectedRoute>
      }
    >
      <Route index element={<DashboardPage />} />
      <Route path="orders" element={<OrdersPage />} />
      <Route path="menu" element={<MenuPage />} />
      <Route path="users" element={<UsersPage />} />
      <Route path="promos" element={<PromosPage />} />
      <Route path="settings" element={<SettingsPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Route>
  </Routes>
</BrowserRouter>
```

`LoginPage` lives outside `Layout` so it renders full-viewport without the admin sidebar. `NotFoundPage` stays inside the protected subtree — a 404 from an authenticated user still shows the layout. An unauthenticated user hitting a bogus path gets redirected to `/login` first, which is correct.

### D7. `staffLogin` wrapper does NOT use `authenticatedFetch`.

The login request has no token yet and must not go through the 401-redirect handler (which would create a loop on wrong password). It's a plain `fetch` call, with explicit `Content-Type: application/json`, and parses the response body directly. On non-2xx it throws `ApiError` the same way `authenticatedFetch` does so callers see one error shape.

```ts
export async function staffLogin(
  login: string,
  password: string,
): Promise<{ access_token: string; role: string }> {
  const response = await fetch(`${BASE_URL}/api/v1/staff/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ login, password }),
  });
  if (!response.ok) {
    let body: unknown = null;
    try { body = await response.clone().json(); } catch {}
    throw new ApiError(response.status, body, `HTTP ${response.status}: /api/v1/staff/auth/login`);
  }
  return await response.json();
}
```

The response type only picks out the two fields we use — `refresh_token` and `token_type` are ignored (see D8).

### D8. `refresh_token` is explicitly dropped.

`staffLogin` returns `access_token` + `role`. The backend still sends `refresh_token` in the JSON body; the client parses it out of the `{access_token, role}` return type. We do not store it, do not log it, do not forward it. If `desktop-nav-and-logout` or a future change wants it, that change adds the storage.

## Risks / Trade-offs

| Risk | Mitigation |
| --- | --- |
| 15-minute TTL feels short during a long admin session, user has to log in every 15 min | Accepted for Phase 2. If it becomes painful, add refresh in a follow-up change. |
| `window.location.assign` in `authenticatedFetch` is a hard redirect — any unsaved form state is lost | Accepted. The admin SPA has one form (`MenuItemFormDialog`), and losing unsaved state on session expiry is standard admin-panel behavior. If the product later wants "save draft on 401", that's its own change. |
| Hard redirect in `logout()` bypasses router — if `desktop-nav-and-logout` wants an animated sidebar-close first, it can't | `desktop-nav-and-logout` can do its own `navigate('/login')` + `clearAccessToken()` if it prefers. `logout()` is a primitive, not a policy. Worth mentioning in that change's design doc. |
| 401 handler clobbers `location.state` | Mitigated by D5: `returnUrl` is carried in the query string, not state, so both `ProtectedRoute` and the 401 handler serialize it the same way. |
| Test bed for `authenticatedFetch` now has to stub `window.location.assign` | Add a `beforeEach` that stubs it with `vi.fn()`; tests assert it was called with the expected URL. |
| Concurrent 401s (e.g., Menu page firing three parallel requests, all 401) all trigger `window.location.assign` | `window.location.assign` is idempotent for the same URL and the browser coalesces rapid identical navigations. Acceptable. |
| A deep-linked URL like `/admin/menu?categoryId=42` needs to survive login | `returnUrl` in D3 concatenates `pathname + search`, and the login page uses `navigate(returnUrl, { replace: true })` with the full string. Covered. |

## Migration Plan

No schema. No backend. No shared package. One SPA bundle. The rollout is just merge + `docker compose restart web-admin`. Existing tokens in developer `localStorage` continue to work — they're still read from the same key.

## Open Questions

- Does the barista role need a narrower landing page than `/` (the dashboard)? Current default: everyone lands on `/`. If PDD §7.1 or the eventual sidebar work needs role-based redirect on login, we add it as a follow-up change.
- Should `LoginPage` display the logo? No logo asset lives in `web/admin/` today. Skipping for now; a product pass can add it later with a one-line asset import.
