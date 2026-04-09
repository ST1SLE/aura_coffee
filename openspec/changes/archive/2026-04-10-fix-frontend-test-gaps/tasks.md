## 1. AuthProvider Test Gap

- [x] 1.1 [web-customer] Add test "clears auth state when refresh token is expired" to `web/customer/src/auth/AuthProvider.test.tsx` — mock refresh API to return 401, assert `isAuthenticated=false`, `user=null`, stored token removed

## 2. ProtectedRoute Test Gap

- [x] 2.1 [web-customer] Add test "passes returnUrl in state when redirecting to /login" to `web/customer/src/auth/ProtectedRoute.test.tsx` — render ProtectedRoute at `/orders` with unauthenticated context, assert redirect to `/login` with `state.returnUrl === "/orders"`

## 3. VerifyPage Resend Timer Tests

- [x] 3.1 [web-customer] Add test "calls login() with phone when resend button is clicked" to `web/customer/src/pages/VerifyPage.test.tsx` — mock ResendTimer callback, assert `login()` called with phone from location state
- [x] 3.2 [web-customer] Add test "shows error when resend login() call fails" to `web/customer/src/pages/VerifyPage.test.tsx` — mock `login()` to reject, assert error message displayed

## 4. App.test.tsx Fix and Route Tests

- [x] 4.1 [web-customer] Fix existing smoke test in `web/customer/src/App.test.tsx` — use MemoryRouter, mock page components to isolate routing
- [x] 4.2 [web-customer] Add test "renders LoginPage on /login without auth" to `web/customer/src/App.test.tsx`
- [x] 4.3 [web-customer] Add test "redirects unauthenticated user from / to /login" to `web/customer/src/App.test.tsx`
- [x] 4.4 [web-customer] Add test "renders NotFoundPage on unknown route" to `web/customer/src/App.test.tsx`

## 5. Verify All Tests Pass

- [x] 5.1 [web-customer] Run full test suite (`npm test` in `web/customer/`) and confirm all new + existing tests pass
