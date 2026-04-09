## Context

**Affected modules:** [core-api], [web-customer]

The OTP verification flow currently has a gap in frontend error handling. When `POST /api/v1/auth/verify-code` returns HTTP 409 (OTP status is `CREATED`, meaning SMS has not yet been delivered by sms-worker), the frontend API client (`web/customer/src/api/auth.ts`) has no case for this status code. The error falls through to `UNKNOWN_ERROR`, and `VerifyPage` displays a generic "Network error" message. The backend behavior is correct per the OTP state machine (§6.4: `CREATED → VERIFIED` is a forbidden transition).

## Goals / Non-Goals

**Goals:**
- Map HTTP 409 to a distinct `CODE_NOT_DELIVERED` error code in the frontend API client
- Display a clear, localized message on `VerifyPage` when the code hasn't arrived yet
- Document 409 in the `verify-code` endpoint's OpenAPI `responses` dict

**Non-Goals:**
- Changing OTP state machine logic or backend behavior
- Implementing auto-retry, polling, or countdown timer on the frontend
- Handling `OTPStatus.FAILED` (SMS delivery permanently failed) — separate concern

## Decisions

### 1. New error code variant: `CODE_NOT_DELIVERED`

Add `'CODE_NOT_DELIVERED'` to the `AuthErrorCode` union type in `web/customer/src/api/types.ts`.

**Rationale:** Follows the existing pattern — each HTTP error status maps to a named error code (`429 → RATE_LIMITED`, `410 → CODE_EXPIRED`). A dedicated code allows the UI to show a specific message and keeps the error handling exhaustive.

**Alternative considered:** Reusing `UNKNOWN_ERROR` with a special message — rejected because it conflates "code not delivered" (a normal timing condition) with actual unexpected errors.

### 2. HTTP 409 mapping in API client

Add a handler in `handleErrorResponse()` in `auth.ts` before the final fallthrough:

```
if (res.status === 409) → throw new AuthError('CODE_NOT_DELIVERED', body.detail)
```

**Rationale:** Consistent with how 429, 410, and 401 are already mapped in the same function. The 409 case SHALL be placed between the existing 410 and 401 handlers for logical ordering (HTTP status code order).

**Alternative considered:** Handling 409 generically in a shared HTTP interceptor — rejected because `CODE_NOT_DELIVERED` is auth-specific, not a general API concern.

### 3. VerifyPage switch case

Add `case 'CODE_NOT_DELIVERED'` in the `handleComplete` error handler, displaying `t('auth.otp.error.notDelivered')`.

**Rationale:** Direct extension of the existing switch statement. No structural change needed.

### 4. i18n keys

Add `auth.otp.error.notDelivered` to both locale files:
- EN: `"Code is on its way — please wait a moment and try again"`
- RU: `"Код ещё в пути — подождите немного и попробуйте снова"`

**Rationale:** The message SHALL be user-friendly and non-technical. It communicates that the system is working (not broken), and the user should wait — not that there is an error.

### 5. Backend OpenAPI schema update

Add `409: {"model": ErrorResponse}` to the `responses` dict on the `verify-code` endpoint in `routers/auth.py`.

**Rationale:** The endpoint already returns 409, but it is not documented in the OpenAPI spec. This is a documentation-only fix — no logic change.

## Risks / Trade-offs

**[Race window UX]** → The user may repeatedly see "code on its way" if SMS delivery is slow. **Mitigation:** This is acceptable for MVP. A future enhancement MAY add a countdown or disable the submit button temporarily. The current fix eliminates confusion ("network error") without adding complexity.

**[No auto-generated client update]** → The API client is hand-written (`auth.ts`), not auto-generated from OpenAPI for auth endpoints. **Mitigation:** The 409 mapping is added manually, which is consistent with how 429/410/401 are already handled.
