## Why

When a customer submits an OTP code before the SMS worker has delivered the message (OTP status is still `CREATED`), core-api correctly returns HTTP 409 (`"OTP not yet delivered"`). However, the frontend API client has no handler for 409 — the error falls through to `UNKNOWN_ERROR`, and `VerifyPage` displays a misleading "Network error, try again later" instead of telling the user their code hasn't arrived yet. This is confusing UX that makes a normal race condition look like a system failure.

**MVP Phase:** Phase 1 (Auth)

## What Changes

- Add `CODE_NOT_DELIVERED` variant to the `AuthErrorCode` type in the frontend
- Map HTTP 409 to `CODE_NOT_DELIVERED` in the API client error handler (`auth.ts`)
- Add a `case 'CODE_NOT_DELIVERED'` branch in `VerifyPage` to show a user-friendly message ("Code not yet delivered, please wait")
- Add `auth.otp.error.notDelivered` i18n keys for RU and EN locales
- Document 409 in the `verify-code` endpoint's `responses` dict (backend OpenAPI schema)

## Non-Goals

- Changing the backend OTP state machine or 409 semantics — the backend behavior is correct per spec (§6.4)
- Auto-retry or polling logic on the frontend — user can simply wait and resubmit
- Handling SMS delivery failure (`OTPStatus.FAILED`) on the frontend — that is a separate error path

## Capabilities

### New Capabilities

- `otp-error-display`: Frontend handling of HTTP 409 (CODE_NOT_DELIVERED) during OTP verification — error code, API client mapping, UI message, i18n keys

### Modified Capabilities

- `sms-otp`: Adding 409 to the `verify-code` endpoint's OpenAPI response schema (requirement completeness, not behavior change)

## Impact

- **Frontend** (`web/customer`): `types.ts`, `auth.ts`, `VerifyPage.tsx`, i18n JSON files (EN + RU)
- **Backend** (`services/core-api`): `routers/auth.py` — OpenAPI `responses` dict only (no logic change)
- **No database, Redis, or infrastructure changes**
- **No breaking changes**
