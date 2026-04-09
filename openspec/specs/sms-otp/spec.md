## ADDED Requirements

### Requirement: OTP generation and storage
The system SHALL generate a 6-digit cryptographically random OTP code upon receiving a send-code request for a valid phone number. The OTP SHALL be stored in Redis at key `otp:{phone_hash}` as JSON `{"code", "attempts", "status"}` with TTL 300 seconds (§6.4).

#### Scenario: Successful OTP creation for new phone
- **WHEN** client sends `POST /api/v1/auth/send-code` with a valid E.164 phone number
- **AND** rate-limit is not exceeded (INV-012)
- **THEN** system creates OTP with status `CREATED`, stores in Redis with TTL 300s, and enqueues SMS task to sms-worker

#### Scenario: OTP creation replaces existing active OTP
- **WHEN** client requests a new OTP for a phone that already has an active OTP in Redis
- **AND** rate-limit is not exceeded
- **THEN** system invalidates the previous OTP and creates a new one

### Requirement: OTP rate-limiting
The system SHALL enforce rate limits per phone number before creating OTP (INV-012): max 1 per 60s, max 5 per 3600s, max 10 per 86400s. Rate-limit counters SHALL be stored in Redis keys `sms_rate:{phone_hash}:min`, `sms_rate:{phone_hash}:hour`, `sms_rate:{phone_hash}:day` (§5.3). Rate-limit check SHALL occur BEFORE OTP creation (§6.4, §7.8).

#### Scenario: Rate limit not exceeded
- **WHEN** client requests OTP and all three rate-limit counters are below their thresholds
- **THEN** system increments all three counters (setting TTL on new keys) and proceeds with OTP creation

#### Scenario: Per-minute rate limit exceeded
- **WHEN** client requests OTP and `sms_rate:{phone_hash}:min` >= 1
- **THEN** system returns HTTP 429 with `retry_after` indicating seconds until the counter expires
- **AND** no OTP is created and no SMS task is enqueued

#### Scenario: Per-hour rate limit exceeded
- **WHEN** client requests OTP and `sms_rate:{phone_hash}:hour` >= 5
- **THEN** system returns HTTP 429 with `retry_after` indicating seconds until the counter expires

#### Scenario: Per-day rate limit exceeded
- **WHEN** client requests OTP and `sms_rate:{phone_hash}:day` >= 10
- **THEN** system returns HTTP 429 with `retry_after` indicating seconds until the counter expires

### Requirement: OTP verification
The system SHALL verify OTP by comparing the submitted code against the stored code in Redis. Verification SHALL use a Redis Lua script to ensure atomicity of check + attempt increment. Maximum 5 attempts allowed (§6.4).

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

### Requirement: SMS delivery via sms-worker
The system SHALL dispatch OTP SMS delivery to sms-worker as a Celery task. SMS Worker SHALL call SMS.ru `POST /sms/send` with message "Код подтверждения: {code}. Aura Coffee" (§8.2, max 70 chars). On success, OTP status SHALL transition CREATED → SENT. On failure after 3 retries (backoff 2s/8s/32s), OTP status SHALL transition CREATED → FAILED (§7.8).

#### Scenario: SMS sent successfully
- **WHEN** sms-worker receives send_otp_sms task and SMS.ru returns HTTP 200 with status OK
- **THEN** worker updates OTP status in Redis to `SENT`

#### Scenario: SMS fails after all retries
- **WHEN** sms-worker exhausts 3 retry attempts (2s, 8s, 32s backoff)
- **THEN** worker updates OTP status in Redis to `FAILED` and logs the error (§7.8)

#### Scenario: SMS fails but retry succeeds
- **WHEN** first SMS.ru call fails but a subsequent retry succeeds
- **THEN** worker updates OTP status to `SENT` on the successful attempt

### Requirement: OTP state machine enforcement
The system SHALL enforce the OTP state machine (§6.4) exhaustively. Only transitions listed in §6.4 are permitted (INV-016). Forbidden transitions (VERIFIED → any, EXPIRED → any, FAILED → any, CREATED → VERIFIED, CREATED → EXPIRED) SHALL be rejected.

#### Scenario: Attempt forbidden transition
- **WHEN** any operation attempts a transition not in the §6.4 transition table
- **THEN** system rejects the operation and logs the violation
