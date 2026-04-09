## Why

Existing frontend tests in `web/customer/src/` have coverage gaps for critical auth flows: AuthProvider doesn't test expired refresh token recovery, ProtectedRoute doesn't verify `returnUrl` preservation, VerifyPage lacks resend timer tests, and App.test.tsx is fragile (smoke-only, breaks on route changes). These gaps let regressions in the auth pipeline slip through unnoticed.

MVP Phase 1 (Auth) — hardening existing implementation, no new features.

## What Changes

- **AuthProvider.test.tsx**: add test for expired refresh token clearing auth state and removing stored token
- **ProtectedRoute.test.tsx**: add test verifying `returnUrl` is passed via `state` on redirect to `/login`
- **VerifyPage.test.tsx**: add tests for ResendTimer interaction (resend callback triggers `login()`, timer reset)
- **App.test.tsx**: fix broken smoke test; add route-level integration tests (public vs protected routes, redirect behavior)

All changes are test-only — no production code modifications.

## Non-Goals

- Adding tests for page components (HomePage, CartPage, etc.) — placeholder pages, not worth testing yet
- Testing API layer success paths (`sendCode`, `refreshTokens`) — separate change
- Testing untested components (Layout, ResendTimer, LanguageSwitcher) in isolation — out of scope
- Refactoring production code to improve testability

## Capabilities

### New Capabilities
- `auth-test-coverage`: Tests for AuthProvider expired-refresh, ProtectedRoute returnUrl, VerifyPage resend timer, and App route integration

### Modified Capabilities
<!-- None — test-only change, no spec-level behavior changes -->

## Impact

- Files affected: `web/customer/src/App.test.tsx`, `web/customer/src/auth/AuthProvider.test.tsx`, `web/customer/src/auth/ProtectedRoute.test.tsx`, `web/customer/src/pages/VerifyPage.test.tsx`
- No API, dependency, or infrastructure changes
- CI test suite will have additional test cases
