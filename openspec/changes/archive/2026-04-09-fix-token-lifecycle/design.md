## Context

**Affected modules:** [web-customer]

The customer SPA (`web/customer/`) has two token lifecycle defects:

1. `api/auth.ts#logout()` sends `body: JSON.stringify({})` — the backend endpoint `POST /api/v1/auth/logout` expects a `RefreshRequest` with `refresh_token` field to delete the token from Redis. Without it, stale refresh tokens survive in Redis until TTL expiry.

2. The `auth-state` spec (requirement "Token management", scenario "Auto-refresh on 401") mandates silent refresh on 401, but no implementation exists. Each API module (`profile.ts`) uses raw `fetch` with manual `authHeaders()` and throws generic errors on 401 without attempting refresh.

Currently `profile.ts` is the only non-auth protected endpoint, but menu, cart, orders, and payment endpoints will follow in subsequent MVP phases — all will need the same 401 → refresh → retry pattern.

## Goals / Non-Goals

**Goals:**
- Fix logout to send `refresh_token` in the request body, ensuring proper server-side token invalidation (INV-002).
- Provide a centralized `authenticatedFetch` that handles auth headers and 401 auto-refresh for all protected endpoints.
- Migrate `profile.ts` to use `authenticatedFetch`, removing duplicated auth logic.

**Non-Goals:**
- No backend changes — the existing endpoints work correctly.
- No retry logic for non-401 errors (5xx, network timeouts).
- No changes to `AuthProvider` mount-time refresh or `ProtectedRoute`.
- No admin panel changes.

## Decisions

### D1: Thin wrapper function vs. class-based API client

**Decision:** Export a plain `authenticatedFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response>` function from `api/client.ts`.

**Rationale:** The function mirrors the `fetch` signature, so callers just swap `fetch` → `authenticatedFetch`. No need for a class — there's no per-instance state (tokens live in the `auth/token.ts` module). This also avoids coupling to a specific HTTP library; it wraps the global `fetch` directly.

**Alternative considered:** Axios interceptors or a class with `.get()`, `.post()` methods. Rejected — adds a dependency and deviates from the existing raw-fetch pattern across the codebase.

### D2: Refresh-race serialization via promise deduplication

**Decision:** If a refresh is already in-flight when a second 401 arrives, reuse the same refresh promise instead of firing a duplicate refresh request.

**Rationale:** Without this, concurrent requests hitting 401 simultaneously would each call `/api/v1/auth/refresh`, but token rotation means only the first succeeds — the rest would fail and force logout. A module-level `let refreshPromise: Promise | null` gate solves this.

**Alternative considered:** Queue all 401 requests and replay after refresh. Unnecessary complexity for the current scale; promise deduplication achieves the same result.

### D3: Signaling auth failure to AuthProvider

**Decision:** `authenticatedFetch` SHALL call a registered `onAuthFailure` callback when refresh fails. `AuthProvider` registers this callback on mount via `registerAuthFailureHandler(() => { clearAllTokens(); setUser(null); })`. This keeps `client.ts` decoupled from React.

**Rationale:** `client.ts` cannot import React context. A callback registration pattern keeps the dependency inverted — `AuthProvider` tells `client.ts` what to do on failure, not the other way around.

**Alternative considered:** Dispatching a custom DOM event (`auth:failure`). Works but is less type-safe and harder to test.

### D4: Logout fix — minimal change

**Decision:** Change `body: JSON.stringify({})` → `body: JSON.stringify({ refresh_token: getRefreshToken() })` in `api/auth.ts#logout()`. One-line fix.

**Rationale:** Backend already expects `RefreshRequest`. Frontend already imports `getRefreshToken`. No structural changes needed.

## Risks / Trade-offs

- **[Refresh token might be null at logout time]** → If `localStorage` was cleared by another tab, `getRefreshToken()` returns `null`. The backend handles `null` gracefully (returns 200 regardless). Tokens still get cleared client-side. Acceptable.

- **[Race between logout and in-flight refresh]** → If `authenticatedFetch` triggers a refresh while the user simultaneously clicks logout, the refresh might complete and store new tokens, which logout then clears. Net effect: user is logged out correctly. No data corruption risk. Acceptable.

- **[Future endpoints must use authenticatedFetch]** → If a developer uses raw `fetch` instead, they bypass 401 handling. Mitigated by removing the `authHeaders()` helper from `profile.ts` — the pattern becomes the obvious default. Linting or code review can enforce this going forward.
