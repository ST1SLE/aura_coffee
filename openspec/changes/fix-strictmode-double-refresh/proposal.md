## Why

React 18 StrictMode fires `useEffect` twice on mount in dev mode. `AuthProvider` sends two parallel `POST /refresh` with the same refresh token. Because backend uses token rotation (GET + DELETE in Redis), this creates a race condition: if the first request deletes the session before the second reads it, the second gets 401 → `clearAllTokens()` → user kicked to `/login` after page refresh. The bug is non-deterministic — depends on Redis timing.

## What Changes

- **[web-customer]** Guard `AuthProvider` mount refresh with a `useRef` flag so only the first `useEffect` invocation performs the refresh call. The second StrictMode invocation is a no-op.
- **[web-customer]** Add cleanup function to the `useEffect` that sets an `aborted` flag, preventing state updates from the first (unmounted) effect in StrictMode's mount-unmount-remount cycle.

## Non-Goals

- No changes to backend refresh endpoint or Redis operations — the frontend should not send duplicate requests in the first place
- No removal of StrictMode — it catches real bugs and should stay enabled in dev
- No changes to `authenticatedFetch` deduplication — that handles concurrent 401s correctly, this is a different code path

## MVP Phase

Phase 1 (Auth) — fixes session persistence across page reloads in dev mode.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `auth-state`: AuthProvider mount refresh becomes idempotent under StrictMode double-fire

## Impact

- **Code:** `web/customer/src/auth/AuthProvider.tsx` (single file)
- **Risk:** Minimal — adds a standard React 18 pattern, no behavior change in production (StrictMode double-fire only happens in dev)
