## 1. Frontend Error Code & API Client

- [x] 1.1 [web-customer] Add `CODE_NOT_DELIVERED` to `AuthErrorCode` union type in `web/customer/src/api/types.ts`
- [x] 1.2 [web-customer] Add HTTP 409 → `CODE_NOT_DELIVERED` mapping in `handleErrorResponse()` in `web/customer/src/api/auth.ts`

## 2. Frontend i18n

- [x] 2.1 [web-customer] Add `auth.otp.error.notDelivered` key to EN locale in `web/customer/src/i18n/locales/en/common.json`
- [x] 2.2 [web-customer] Add `auth.otp.error.notDelivered` key to RU locale in `web/customer/src/i18n/locales/ru/common.json`

## 3. Frontend VerifyPage

- [x] 3.1 [web-customer] Add `case 'CODE_NOT_DELIVERED'` branch in error handler switch in `web/customer/src/pages/VerifyPage.tsx`

## 4. Backend OpenAPI Documentation

- [x] 4.1 [core-api] Add `409: {"model": ErrorResponse}` to `responses` dict on `verify-code` endpoint in `services/core-api/src/core_api/routers/auth.py`

## 5. Verification

- [x] 5.1 [web-customer] Verify TypeScript compilation passes with no type errors (`npm run typecheck` or `npx tsc --noEmit`)
- [x] 5.2 [core-api] Verify core-api starts without import errors and OpenAPI schema includes 409 response
