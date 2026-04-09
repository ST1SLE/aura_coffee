## MODIFIED Requirements

### Requirement: Phone input screen

Previously: The phone input screen navigated to the OTP verification screen with only the phone number in state.
Now: The phone input screen SHALL forward any `returnUrl` received in its own location state (from `ProtectedRoute` redirect) when navigating to the OTP verification screen. The navigation state SHALL include both `phone` and `returnUrl`.

#### Scenario: Valid phone number submission
- **WHEN** user enters a valid 10-digit phone number and clicks submit
- **THEN** the system sends a `send-code` request with the phone normalized to E.164 format (`+7XXXXXXXXXX`) and navigates to the OTP verification screen with `{ phone, returnUrl }` in location state

#### Scenario: returnUrl forwarded from ProtectedRoute redirect
- **WHEN** an unauthenticated user is redirected to `/login` with `returnUrl: '/profile'` in location state, then enters a valid phone and submits
- **THEN** the navigation to `/login/verify` SHALL include `{ phone: '+7XXXXXXXXXX', returnUrl: '/profile' }` in location state

#### Scenario: Direct navigation to /login without returnUrl
- **WHEN** a user navigates directly to `/login` (no `returnUrl` in state) and submits a valid phone
- **THEN** the navigation to `/login/verify` SHALL include `{ phone: '+7XXXXXXXXXX', returnUrl: undefined }` in location state, and `VerifyPage` SHALL fall back to `'/'` after verification

#### Scenario: Invalid phone number
- **WHEN** user enters fewer than 10 digits
- **THEN** the submit button remains disabled

#### Scenario: API error on send-code
- **WHEN** user submits a valid phone and the API returns an error (rate-limit exceeded, server error)
- **THEN** an error message is displayed on the same screen without navigation
