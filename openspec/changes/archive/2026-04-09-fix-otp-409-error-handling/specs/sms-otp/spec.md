## MODIFIED Requirements

### Requirement: OTP verification
The system SHALL verify OTP by comparing the submitted code against the stored code in Redis. Verification SHALL use a Redis Lua script to ensure atomicity of check + attempt increment. Maximum 5 attempts allowed (§6.4).

- **Previously:** The `verify-code` endpoint's OpenAPI `responses` dict documents only 401 and 410 status codes.
- **Now:** The `verify-code` endpoint's OpenAPI `responses` dict SHALL also document 409 with `ErrorResponse` model, reflecting the existing behavior where HTTP 409 is returned when OTP status is `CREATED` (§6.4: CREATED → VERIFIED forbidden).

#### Scenario: Correct code submitted
- **WHEN** client sends `POST /api/v1/auth/verify-code` with correct code
- **AND** OTP status is `SENT` and attempts < 5 and TTL has not expired
- **THEN** system transitions OTP to `VERIFIED`, deletes OTP from Redis, and returns JWT tokens

#### Scenario: Incorrect code submitted with remaining attempts
- **WHEN** client submits incorrect code and attempts < 4
- **THEN** system increments attempts counter and returns HTTP 401 with `remaining_attempts`

#### Scenario: Fifth incorrect attempt exhausts OTP
- **WHEN** client submits incorrect code and attempts reaches 5
- **THEN** system transitions OTP to `FAILED`, deletes OTP from Redis, and returns HTTP 401 with message indicating code is invalidated (§6.4: SENT → FAILED)

#### Scenario: Code submitted for expired OTP
- **WHEN** client submits code but OTP key does not exist in Redis (TTL expired)
- **THEN** system returns HTTP 410 indicating code has expired

#### Scenario: Code submitted before SMS sent (status CREATED)
- **WHEN** client submits code while OTP status is still `CREATED`
- **THEN** system returns HTTP 409 indicating code is not yet delivered (§6.4: CREATED → VERIFIED forbidden)
- **AND** HTTP 409 is documented in the endpoint's OpenAPI `responses` dict with `ErrorResponse` model
