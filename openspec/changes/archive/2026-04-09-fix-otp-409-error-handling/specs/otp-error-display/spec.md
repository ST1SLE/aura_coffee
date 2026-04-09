## ADDED Requirements

### Requirement: Frontend CODE_NOT_DELIVERED error code
The frontend API client SHALL define a `CODE_NOT_DELIVERED` variant in the `AuthErrorCode` type. The `handleErrorResponse` function in `auth.ts` SHALL map HTTP 409 responses to `AuthError` with code `CODE_NOT_DELIVERED` (§6.4: CREATED → VERIFIED is a forbidden transition, surfaced as 409).

#### Scenario: API client receives HTTP 409 from verify-code
- **WHEN** `POST /api/v1/auth/verify-code` returns HTTP 409
- **THEN** the API client throws `AuthError` with `code = 'CODE_NOT_DELIVERED'` and `message` from the response body `detail` field

#### Scenario: API client receives other unhandled status codes
- **WHEN** `POST /api/v1/auth/verify-code` returns a status code not in {401, 409, 410, 429}
- **THEN** the API client throws `AuthError` with `code = 'UNKNOWN_ERROR'` (existing behavior unchanged)

### Requirement: VerifyPage displays distinct message for CODE_NOT_DELIVERED
The `VerifyPage` component SHALL handle `AuthError` with code `CODE_NOT_DELIVERED` by displaying a localized message via i18n key `auth.otp.error.notDelivered`. The message SHALL NOT be confused with network errors or invalid code errors.

#### Scenario: User submits code before SMS is delivered
- **WHEN** user enters OTP code on VerifyPage
- **AND** the verification request returns `CODE_NOT_DELIVERED` error
- **THEN** VerifyPage displays the `auth.otp.error.notDelivered` message
- **AND** the OTP input remains editable (user can retry)

#### Scenario: User submits code after SMS is delivered
- **WHEN** user enters OTP code on VerifyPage
- **AND** the verification request returns success, `INVALID_CODE`, `CODE_EXPIRED`, or `RATE_LIMITED`
- **THEN** existing behavior is unchanged

### Requirement: Bilingual i18n keys for CODE_NOT_DELIVERED
The system SHALL provide `auth.otp.error.notDelivered` translations in both EN and RU locale files. The message SHALL communicate that the code is being delivered (not that an error occurred) and suggest the user wait before retrying.

#### Scenario: English locale displays notDelivered message
- **WHEN** VerifyPage renders `auth.otp.error.notDelivered` with EN locale
- **THEN** user sees a message indicating the code is on its way and to wait

#### Scenario: Russian locale displays notDelivered message
- **WHEN** VerifyPage renders `auth.otp.error.notDelivered` with RU locale
- **THEN** user sees a message in Russian indicating the code is on its way and to wait
