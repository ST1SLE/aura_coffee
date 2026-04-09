## MODIFIED Requirements

### Requirement: Auth API client interface
The system SHALL provide an auth API client module at `src/api/auth.ts` exporting functions: `sendCode(phone: string)`, `verifyCode(phone: string, code: string)`, `refreshTokens(refreshToken: string)`, `logout()`. Each function SHALL call the backend at `/api/v1/auth/*` via `fetch` and return a typed Promise. The module SHALL map backend snake_case responses to camelCase frontend types. The `logout` function SHALL include the refresh token in the request body.

- **Previously:** `logout()` sends `POST /api/v1/auth/logout` with `Authorization: Bearer <accessToken>` header and empty JSON body `{}`. Network errors are silently ignored.
- **Now:** `logout()` sends `POST /api/v1/auth/logout` with `Authorization: Bearer <accessToken>` header and JSON body `{ refresh_token: <refreshToken> }` where `refreshToken` is retrieved via `getRefreshToken()` from `auth/token.ts`. Network errors are still silently ignored. This matches the backend `RefreshRequest` schema and enables server-side token invalidation in Redis (INV-002).

#### Scenario: logout sends refresh token
- **WHEN** `logout` is called and a refresh token exists in localStorage
- **THEN** it sends `POST /api/v1/auth/logout` with `Authorization: Bearer <accessToken>` header and body `{ "refresh_token": "<refreshToken>" }`

#### Scenario: logout with no refresh token
- **WHEN** `logout` is called and no refresh token exists in localStorage
- **THEN** it sends `POST /api/v1/auth/logout` with `Authorization: Bearer <accessToken>` header and body `{ "refresh_token": null }`. Network errors are silently ignored.

#### Scenario: logout network error
- **WHEN** `logout` is called and the network request fails
- **THEN** the error is silently ignored (tokens will be cleared client-side by AuthProvider)
