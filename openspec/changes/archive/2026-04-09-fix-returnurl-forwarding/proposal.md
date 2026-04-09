## Why

After OTP verification, authenticated customers always land on `/` (HomePage placeholder) instead of the page they originally tried to access (e.g., `/profile`). `ProtectedRoute` correctly saves `returnUrl` in location state when redirecting to `/login`, but `LoginPage` drops it when navigating to `/login/verify` — only forwarding `phone`. This breaks the post-auth redirect for every protected route. MVP Phase 1 (Auth) bug — blocks normal profile and future checkout flows.

## What Changes

- **LoginPage** reads `returnUrl` from `location.state` and forwards it alongside `phone` when navigating to `/login/verify`
- **VerifyPage tests** updated to assert redirect to the actual `returnUrl` (e.g., `/profile`) instead of hardcoded `'/'`
- **LoginPage tests** updated to verify `returnUrl` forwarding in the navigate call

## Non-Goals

- Changing `ProtectedRoute` logic — it already correctly saves `returnUrl`
- Changing `VerifyPage` component logic — it already reads `returnUrl` from state and falls back to `'/'`
- Adding new routes or pages
- Backend changes — this is purely a frontend state-forwarding bug

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `auth-screens`: Add explicit requirement that `returnUrl` MUST be propagated through the full login → verify flow, not just saved at redirect time

## Impact

- **Code**: `web/customer/src/pages/LoginPage.tsx`, `web/customer/src/pages/LoginPage.test.tsx`, `web/customer/src/pages/VerifyPage.test.tsx`
- **User-facing**: Post-auth redirect will work correctly for all protected routes (`/profile`, `/cart`, `/checkout`, `/orders`)
- **Risk**: Minimal — single line change in LoginPage + test corrections
