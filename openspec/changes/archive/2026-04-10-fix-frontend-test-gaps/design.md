## Context

**Affected modules:** [web-customer]

The `web/customer/src/` test suite covers the auth flow but has specific gaps:
1. AuthProvider: no test for expired refresh token clearing state
2. ProtectedRoute: no test verifying `returnUrl` state on redirect
3. VerifyPage: ResendTimer interaction untested
4. App.test.tsx: fragile smoke test that breaks on route changes

All four test files exist. This is a test-only change — no production code modifications.

## Goals / Non-Goals

**Goals:**
- Close coverage gaps in AuthProvider, ProtectedRoute, VerifyPage, App test files
- Tests SHALL follow existing patterns (Vitest, React Testing Library, vi.mock)
- App.test.tsx SHALL be robust against route additions

**Non-Goals:**
- Testing page components (HomePage, CartPage, etc.)
- Testing API layer success paths
- Testing isolated components (ResendTimer, Layout, LanguageSwitcher)
- Refactoring production code

## Decisions

### 1. Test mocking strategy: reuse existing mock patterns
**Decision:** Follow the mocking patterns already established in each test file (vi.mock for modules, mock implementations for context providers).
**Alternatives considered:** Introducing MSW (Mock Service Worker) for API mocking — rejected because existing tests use vi.mock consistently, and introducing MSW for 4 files adds unnecessary complexity.

### 2. App.test.tsx: MemoryRouter with route assertions
**Decision:** Replace BrowserRouter smoke test with MemoryRouter-based tests that verify route rendering and redirect behavior. Mock all page components to isolate routing logic.
**Alternatives considered:** Snapshot testing — rejected because snapshots are brittle and don't validate behavior.

### 3. VerifyPage resend timer: test via callback, not timer internals
**Decision:** Test that clicking resend triggers `login()` from AuthProvider context, without testing ResendTimer's countdown logic (that belongs in a ResendTimer unit test, out of scope).
**Alternatives considered:** Using `vi.advanceTimersByTime` to test full countdown — rejected as it tests ResendTimer internals, not VerifyPage integration.

## Risks / Trade-offs

- [App route tests may need updating when new routes are added] → Acceptable; route tests are inherently coupled to route config. Mocked page components keep them lightweight.
- [VerifyPage resend test depends on ResendTimer exposing a clickable element] → Low risk; ResendTimer renders a button with known text. If it changes, the test will fail visibly.
