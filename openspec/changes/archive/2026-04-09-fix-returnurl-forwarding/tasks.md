## 1. Fix LoginPage — forward returnUrl

- [x] 1.1 [web-customer] In `LoginPage.tsx`, read `returnUrl` from `location.state` and include it in the `navigate('/login/verify', { state: { phone, returnUrl } })` call

## 2. Fix tests — LoginPage

- [x] 2.1 [web-customer] In `LoginPage.test.tsx`, add `useLocation` mock returning `state: { returnUrl: '/profile' }` and update "calls login and navigates on valid submit" test to assert `returnUrl` is forwarded in navigate state

## 3. Fix tests — VerifyPage

- [x] 3.1 [web-customer] In `VerifyPage.test.tsx`, change mocked `returnUrl` from `'/'` to `'/profile'` and update "redirects on success" test to assert `mockNavigate` is called with `'/profile'`
- [x] 3.2 [web-customer] In `VerifyPage.otp409.test.tsx`, update mocked `returnUrl` from `'/'` to `'/profile'` for consistency

## 4. Verify

- [x] 4.1 [web-customer] Run `vitest` in `web/customer/` and confirm all tests pass
