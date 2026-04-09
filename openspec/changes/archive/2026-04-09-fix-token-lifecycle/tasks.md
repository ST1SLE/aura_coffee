## 1. Fix logout request body

- [x] 1.1 [web-customer] Update `src/api/auth.ts#logout()` to send `{ refresh_token: getRefreshToken() }` in request body instead of `{}`

## 2. Authenticated fetch client

- [x] 2.1 [web-customer] Create `src/api/client.ts` with `authenticatedFetch` function: inject `Authorization: Bearer` header from `getAccessToken()`, intercept 401 → call `refreshTokens` → store new tokens → retry original request once
- [x] 2.2 [web-customer] Add refresh promise deduplication in `src/api/client.ts`: module-level `refreshPromise` variable to prevent concurrent refresh calls on simultaneous 401s
- [x] 2.3 [web-customer] Add `registerAuthFailureHandler` export in `src/api/client.ts`: callback registration for auth failure signaling, with `clearAllTokens` fallback when no handler is registered

## 3. Integrate with AuthProvider

- [x] 3.1 [web-customer] Update `src/auth/AuthProvider.tsx` to call `registerAuthFailureHandler` on mount with a handler that clears tokens and sets user to null

## 4. Migrate profile API

- [x] 4.1 [web-customer] Update `src/api/profile.ts` to use `authenticatedFetch` instead of raw `fetch` + `authHeaders()`, remove the local `authHeaders` helper
