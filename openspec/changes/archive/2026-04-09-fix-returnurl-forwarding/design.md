## Context

**Affected modules:** [web-customer]

The auth flow uses a two-step login: phone input (`/login`) → OTP verification (`/login/verify`). When `ProtectedRoute` redirects unauthenticated users to `/login`, it saves the original path as `returnUrl` in React Router's location state. After successful OTP verification, `VerifyPage` reads `returnUrl` from state and navigates there.

The bug: `LoginPage` navigates to `/login/verify` with `state: { phone }` — discarding `returnUrl`. `VerifyPage` gets `returnUrl: undefined` and falls back to `'/'`.

```
ProtectedRoute ──state:{returnUrl:'/profile'}──▶ /login ──state:{phone}──▶ /login/verify
                                                           ↑ returnUrl DROPPED here
```

## Goals / Non-Goals

**Goals:**
- `LoginPage` SHALL forward `returnUrl` from its own location state to `VerifyPage`
- Tests SHALL verify the full `returnUrl` propagation chain
- Post-auth redirect SHALL work for all protected routes

**Non-Goals:**
- No changes to `ProtectedRoute` (already correct)
- No changes to `VerifyPage` component logic (already reads `returnUrl` correctly)
- No changes to `AuthProvider` or token handling
- No backend changes

## Decisions

### 1. Read and forward `returnUrl` in LoginPage

**Choice:** `LoginPage` reads `returnUrl` from `location.state` (set by `ProtectedRoute`) and includes it in the navigate call to `/login/verify`.

**Change in `LoginPage.tsx`:**
- Read: `const returnUrl = (location.state as { returnUrl?: string })?.returnUrl;`
- Forward: `navigate('/login/verify', { state: { phone, returnUrl } })`

**Why not a different approach (e.g., query params, context):**
React Router location state is already the established pattern — `ProtectedRoute` writes it, `VerifyPage` reads it. Using the same mechanism keeps the solution consistent with zero new dependencies.

### 2. Fix test mocks to use realistic `returnUrl`

**Choice:** Update `VerifyPage.test.tsx` mock to use `returnUrl: '/profile'` (a real protected route) and assert redirect to `/profile`. Update `LoginPage.test.tsx` to verify `returnUrl` is forwarded in navigate state.

**Why:** Tests currently hardcode `returnUrl: '/'` which masks the bug. Using a realistic value makes the test a regression guard.

## Risks / Trade-offs

- **[Risk: Direct navigation to /login]** → If a user navigates directly to `/login` (not via ProtectedRoute redirect), `returnUrl` will be `undefined`. `VerifyPage` already handles this with the `|| '/'` fallback. No change needed.
- **[Risk: Stale returnUrl]** → If a user sits on `/login` for a long time, the `returnUrl` still points to the original page. This is acceptable behavior — the alternative (clearing it) is worse UX.
