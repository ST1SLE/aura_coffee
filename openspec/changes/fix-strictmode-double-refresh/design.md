## Affected Modules

- **[web-customer]**

## Design

### StrictMode double-mount problem

React 18 StrictMode in dev: mount → unmount → remount. Each mount fires `useEffect`. Current code:

```
mount1: useEffect → refreshTokens("abc") → setUser(...)
unmount1: (no cleanup)
mount2: useEffect → refreshTokens("abc") → race condition
```

### Solution: useRef guard + abort flag

```
mount1: useEffect → ref.current=false → set ref=true → refreshTokens("abc")
  cleanup1: aborted=true → state updates skipped
unmount1: cleanup runs
mount2: useEffect → ref already true? NO (remount = new ref) → set ref=true → refreshTokens("abc")
  cleanup2: (none, component stays)
```

Wait — `useRef` resets on remount. The correct pattern for StrictMode is **abort via cleanup**, not ref guard:

```typescript
useEffect(() => {
  let aborted = false;
  const refreshToken = getRefreshToken();
  if (!refreshToken) { setIsLoading(false); return; }

  authApi.refreshTokens(refreshToken)
    .then((tokens) => {
      if (aborted) return;          // ← первый mount отменён StrictMode
      setAccessToken(tokens.accessToken);
      setRefreshToken(tokens.refreshToken);
      setUser(parseUserFromJwt(tokens.accessToken));
    })
    .catch(() => {
      if (aborted) return;          // ← не чистим токены от отменённого эффекта
      clearAllTokens();
    })
    .finally(() => {
      if (aborted) return;
      setIsLoading(false);
    });

  return () => { aborted = true; }; // ← cleanup
}, []);
```

StrictMode cycle:
1. mount1 → effect1 starts refresh → unmount1 → cleanup sets `aborted=true` → effect1 results ignored
2. mount2 → effect2 starts refresh → this is the real one, no cleanup → state updates apply

**Two requests still fire**, but only the second one's results are applied. The first one's 200 response is discarded. Even if the first one rotates the token in Redis, the second one will either:
- Succeed (if concurrent) — both results valid, only second applied
- Fail with 401 (if first already rotated) — second's catch is NOT aborted → clears tokens

This is still a problem. The second request uses the **original** token which may already be rotated by the first.

### Revised solution: useRef to prevent duplicate network call

Use a module-level or ref-based flag to ensure only ONE refresh call fires:

```typescript
const refreshAttempted = useRef(false);

useEffect(() => {
  if (refreshAttempted.current) return;
  refreshAttempted.current = true;

  const refreshToken = getRefreshToken();
  if (!refreshToken) { setIsLoading(false); return; }

  authApi.refreshTokens(refreshToken)
    .then(...)
    .catch(...)
    .finally(...);
}, []);
```

StrictMode cycle:
1. mount1 → `ref.current=false` → set to `true` → fires refresh
2. unmount1 → (ref persists across remount in same component instance? **No — useRef resets on remount**)

**Actually `useRef` DOES persist across StrictMode remount** in React 18. StrictMode simulates unmount+remount but reuses the same fiber, so refs survive. This is confirmed by React docs and Dan Abramov's explanations.

So:
1. mount1 → `ref.current=false` → set `true` → fire refresh
2. unmount1 → cleanup (optional)
3. mount2 → `ref.current=true` → **skip** → no second request

This is the correct approach. Single network call, no race condition.

### Final design

Combine both: `useRef` guard prevents duplicate call + abort cleanup for safety:

```typescript
const refreshAttempted = useRef(false);

useEffect(() => {
  if (refreshAttempted.current) {
    setIsLoading(false);
    return;
  }
  refreshAttempted.current = true;

  let aborted = false;
  const refreshToken = getRefreshToken();
  if (!refreshToken) { setIsLoading(false); return; }

  authApi.refreshTokens(refreshToken)
    .then((tokens) => {
      if (aborted) return;
      setAccessToken(tokens.accessToken);
      setRefreshToken(tokens.refreshToken);
      setUser(parseUserFromJwt(tokens.accessToken));
    })
    .catch(() => {
      if (aborted) return;
      clearAllTokens();
    })
    .finally(() => {
      if (aborted) return;
      setIsLoading(false);
    });

  return () => { aborted = true; };
}, []);
```

Wait — if `refreshAttempted.current` is `true` on mount2, we return early with `setIsLoading(false)`. But the refresh from mount1 is still in-flight (cleanup set `aborted=true` so its results are ignored). Now mount2 skips the call AND sets loading false → `ProtectedRoute` sees `isLoading=false, isAuthenticated=false` → redirect to `/login`.

**Simplest correct approach:** just `useRef` guard, no abort cleanup. The ref prevents the second call. The first call's `.then()` runs and sets state correctly even after StrictMode remount (React batches state updates and applies them to the current mounted instance).

```typescript
const refreshAttempted = useRef(false);

useEffect(() => {
  if (refreshAttempted.current) return;
  refreshAttempted.current = true;

  const refreshToken = getRefreshToken();
  if (!refreshToken) { setIsLoading(false); return; }

  authApi.refreshTokens(refreshToken)
    .then((tokens) => {
      setAccessToken(tokens.accessToken);
      setRefreshToken(tokens.refreshToken);
      setUser(parseUserFromJwt(tokens.accessToken));
    })
    .catch(() => { clearAllTokens(); })
    .finally(() => { setIsLoading(false); });
}, []);
```

This works because:
- mount1: ref=false → set true → fire refresh
- unmount1: no cleanup needed
- mount2: ref=true → skip (return early, but DON'T set isLoading=false — let mount1's promise handle it)
- mount1's promise resolves → sets state on the currently mounted instance

## Decisions

- `useRef` guard only, no abort cleanup — simplest correct solution
- No `setIsLoading(false)` in the early return path — the in-flight promise from first mount handles it
- No changes to the `registerAuthFailureHandler` effect — it's idempotent (just overwrites the callback reference)
