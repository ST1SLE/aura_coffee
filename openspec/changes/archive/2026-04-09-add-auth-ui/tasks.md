## 1. Auth API Client & Types

- [x] 1.1 [web-customer] Create auth types in `src/api/types.ts` — `AuthTokens`, `AuthUser`, `SendCodeResponse`, `VerifyCodeResponse`, `AuthError` class with error codes (`INVALID_CODE`, `CODE_EXPIRED`, `RATE_LIMITED`, `NETWORK_ERROR`, `UNKNOWN_ERROR`)
- [x] 1.2 [web-customer] Create mock auth implementation in `src/api/mocks/auth.ts` — `sendCode`, `verifyCode`, `refreshTokens`, `logout` with 500ms delays; code `000000` succeeds, others fail
- [x] 1.3 [web-customer] Create auth API client in `src/api/auth.ts` — re-export mock functions as the active implementation; typed interface matching `sendCode(phone)`, `verifyCode(phone, code)`, `refreshTokens(refreshToken)`, `logout(accessToken)`

## 2. Token Management

- [x] 2.1 [web-customer] Create token storage module in `src/auth/token.ts` — `getAccessToken()`, `setAccessToken(token)`, `clearAccessToken()` (in-memory), `getRefreshToken()`, `setRefreshToken(token)`, `clearRefreshToken()` (localStorage key `aura_refresh_token`), `clearAllTokens()`

## 3. Auth Context & Hook

- [x] 3.1 [web-customer] Create `AuthContext` and `AuthProvider` in `src/auth/AuthProvider.tsx` — context with `user`, `isAuthenticated`, `isLoading`, `login(phone)`, `verifyCode(phone, code)`, `logout()`; silent refresh on mount if refresh token exists
- [x] 3.2 [web-customer] Create `useAuth` hook in `src/auth/useAuth.ts` — returns AuthContext value, throws error if used outside AuthProvider
- [x] 3.3 [web-customer] Create `ProtectedRoute` component in `src/auth/ProtectedRoute.tsx` — checks `isAuthenticated`, redirects to `/login` with `returnUrl` state if not authenticated, shows loading indicator while `isLoading`

## 4. Auth UI Components

- [x] 4.1 [web-customer] Create `PhoneInput` component in `src/components/auth/PhoneInput.tsx` — controlled input with fixed `+7` prefix, mask `(XXX) XXX-XX-XX`, returns normalized E.164 string via onChange
- [x] 4.2 [web-customer] Create `OTPInput` component in `src/components/auth/OTPInput.tsx` — 6 separate digit inputs, auto-advance on input, backspace navigation, paste support, `onComplete(code)` callback
- [x] 4.3 [web-customer] Create `ResendTimer` component in `src/components/auth/ResendTimer.tsx` — 60s countdown, disabled "Resend" button during countdown, `onResend` callback when clicked after timer expires

## 5. Auth Pages

- [x] 5.1 [web-customer] Create `LoginPage` in `src/pages/LoginPage.tsx` — phone input form using `PhoneInput`, submit calls `login()` from `useAuth`, loading/error states, navigates to `/login/verify` on success passing phone in state
- [x] 5.2 [web-customer] Create `VerifyPage` in `src/pages/VerifyPage.tsx` — OTP input using `OTPInput`, `ResendTimer`, displays masked phone, auto-submits on 6 digits via `verifyCode()`, redirects to returnUrl or `/` on success, error display

## 6. i18n

- [x] 6.1 [web-customer] Add Russian auth translations in `src/i18n/locales/ru/common.json` — keys under `auth.*`: `phone.title`, `phone.placeholder`, `phone.submit`, `otp.title`, `otp.resend`, `otp.resendIn`, `otp.error.invalid`, `otp.error.expired`, `otp.error.rateLimit`, `otp.error.network`
- [x] 6.2 [web-customer] Add English auth translations in `src/i18n/locales/en/common.json` — same keys as 6.1

## 7. Routing Integration

- [x] 7.1 [web-customer] Wrap app with `AuthProvider` in `src/App.tsx` — add `AuthProvider` inside `BrowserRouter`
- [x] 7.2 [web-customer] Add auth routes in `src/App.tsx` — `/login` → `LoginPage`, `/login/verify` → `VerifyPage` (public routes outside Layout)
- [x] 7.3 [web-customer] Wrap protected routes with `ProtectedRoute` in `src/App.tsx` — cart, checkout, orders, profile routes wrapped with `ProtectedRoute`

## 8. Tests

- [x] 8.1 [web-customer] Test `PhoneInput` — renders with +7 prefix, formats input, returns normalized E.164
- [x] 8.2 [web-customer] Test `OTPInput` — digit entry advances focus, backspace navigates back, paste fills all fields, calls onComplete
- [x] 8.3 [web-customer] Test `AuthProvider` — silent refresh on mount, login flow, logout clears state
- [x] 8.4 [web-customer] Test `ProtectedRoute` — redirects unauthenticated, renders content for authenticated, shows loading
- [x] 8.5 [web-customer] Test `LoginPage` — submits phone, shows errors, navigates to verify
- [x] 8.6 [web-customer] Test `VerifyPage` — submits code, handles errors, redirects on success
