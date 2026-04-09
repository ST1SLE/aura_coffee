## Why

The customer frontend has two token lifecycle bugs. First, `logout()` sends an empty body instead of `{ refresh_token }`, so the backend cannot invalidate the refresh token in Redis — stale tokens remain valid until TTL expiry (PDD section 5, INV-002). Second, the `auth-state` spec already requires "auto-refresh on 401" (scenarios at lines 25–31), but no implementation exists — any expired access token causes a hard failure in `profile.ts` and future protected endpoints instead of a silent refresh + retry. Both bugs are in Phase 1 (Auth) scope.

## What Changes

- **Fix logout request**: `api/auth.ts#logout()` sends `{ refresh_token: getRefreshToken() }` in the body so the backend can delete the token from Redis. No backend changes needed — the endpoint already expects `RefreshRequest`.
- **New authenticated fetch client**: `api/client.ts` exports `authenticatedFetch(input, init?)` — a thin wrapper around `fetch` that attaches `Authorization: Bearer` header and intercepts 401 → refresh → retry (one attempt). On refresh failure, clears tokens and signals logout.
- **Migrate profile API**: `api/profile.ts` switches from raw `fetch` + manual `authHeaders()` to `authenticatedFetch`, removing duplicated auth logic.

## Non-Goals

- No changes to the backend auth endpoints — the contract is already correct.
- No changes to `AuthProvider` mount-time refresh logic — that works correctly.
- No retry logic for non-auth errors (5xx, network). Only 401 is intercepted.
- No admin panel (`web-admin`) changes — this change targets `web-customer` only.

## Capabilities

### New Capabilities
- `authenticated-fetch`: Centralized fetch wrapper that attaches access token, intercepts 401 → silent refresh → retry, and signals auth failure on refresh error.

### Modified Capabilities
- `auth-api-client`: Logout function must send `refresh_token` in request body (currently sends `{}`).

## Impact

- **Code**: `web/customer/src/api/auth.ts` (logout fix), new `web/customer/src/api/client.ts`, `web/customer/src/api/profile.ts` (migrate to new client).
- **Auth token storage**: `auth/token.ts` read functions used by new client — no changes to storage itself.
- **Security**: Fixes token invalidation gap where refresh tokens survive logout (INV-002).
- **MVP Phase**: Phase 1 (Auth).
