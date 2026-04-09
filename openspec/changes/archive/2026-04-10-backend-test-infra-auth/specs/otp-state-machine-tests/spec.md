## ADDED Requirements

### Requirement: Lua branch — verified (correct code)
Tests SHALL verify that submitting the correct code when OTP status is "sent" returns `VerifyResult.VERIFIED` and deletes the Redis key.

#### Scenario: Correct code on first attempt
- **WHEN** OTP is created, status set to "sent", and the correct code is submitted
- **THEN** `verify_otp` returns `VerifyResult.VERIFIED` and the OTP key no longer exists in Redis

#### Scenario: Correct code on final attempt (attempt 5 of 5)
- **WHEN** 4 wrong codes have been submitted (attempts = 4) and the 5th submission is the correct code
- **THEN** `verify_otp` returns `VerifyResult.VERIFIED` (not FAILED)

### Requirement: Lua branch — wrong_code (incorrect, attempts remaining)
Tests SHALL verify that submitting a wrong code when attempts < max returns `VerifyResult.WRONG_CODE` with correct `remaining_attempts` and preserves the OTP key.

#### Scenario: First wrong attempt
- **WHEN** OTP is in "sent" status and a wrong code is submitted for the first time
- **THEN** result is `VerifyResult.WRONG_CODE` with `remaining_attempts == 4`, and the OTP key still exists

#### Scenario: Remaining attempts decrement correctly
- **WHEN** 3 wrong codes are submitted sequentially
- **THEN** `remaining_attempts` values are 4, 3, 2 respectively

### Requirement: Lua branch — failed (attempts exhausted)
Tests SHALL verify that exhausting all attempts returns `VerifyResult.FAILED` with `remaining_attempts == 0` and deletes the Redis key.

#### Scenario: Fifth wrong attempt triggers failure
- **WHEN** 5 consecutive wrong codes are submitted
- **THEN** the 5th call returns `VerifyResult.FAILED` with `remaining_attempts == 0` and the OTP key is deleted

### Requirement: Lua branch — expired (key missing)
Tests SHALL verify that verifying against a non-existent key returns `VerifyResult.EXPIRED`.

#### Scenario: OTP key does not exist
- **WHEN** `verify_otp` is called with a phone_hash that has no OTP key in Redis
- **THEN** result is `VerifyResult.EXPIRED`

### Requirement: Lua branch — invalid_status (status ≠ "sent")
Tests SHALL verify that attempting verification when OTP status is not "sent" returns `VerifyResult.INVALID_STATUS`.

#### Scenario: OTP still in "created" status
- **WHEN** OTP is created but `update_otp_status` has NOT been called (status = "created"), and a code is submitted
- **THEN** result is `VerifyResult.INVALID_STATUS`

### Requirement: Rate limit boundary tests
Tests SHALL verify rate limiting at exact boundary values and `retry_after` correctness.

#### Scenario: Request at exactly the per-minute limit
- **WHEN** exactly 1 SMS has been sent (matching the per-minute limit of 1)
- **THEN** `check_rate_limit` returns `allowed=False`

#### Scenario: retry_after is positive
- **WHEN** rate limit is exceeded
- **THEN** `retry_after` is a positive integer representing seconds until the window resets
