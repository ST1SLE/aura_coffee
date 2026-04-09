## 1. Dependencies

- [x] 1.1 [core-api] Add `fakeredis[lua]>=2.21,<3.0` to `[project.optional-dependencies] dev` in `services/core-api/pyproject.toml`

## 2. Test Fixtures

- [x] 2.1 [core-api] Rewrite `tests/conftest.py`: replace real-Redis `r` fixture with `fakeredis.FakeRedis(connected=False)` per-test instance, keep `otp_svc` fixture, add `auth_svc` fixture with patched settings

## 3. OTP State Machine Tests

- [x] 3.1 [core-api] Rewrite `tests/test_otp_service.py` `TestVerifyOTP`: add test for correct code on final attempt (attempt 5 of 5 → VERIFIED)
- [x] 3.2 [core-api] Add test in `tests/test_otp_service.py` for `invalid_status` branch: verify when OTP status is still "created"
- [x] 3.3 [core-api] Add test in `tests/test_otp_service.py` for remaining_attempts decrement sequence (3 wrong → 4, 3, 2)
- [x] 3.4 [core-api] Add test in `tests/test_otp_service.py` verifying Redis key is deleted after VERIFIED
- [x] 3.5 [core-api] Add test in `tests/test_otp_service.py` verifying Redis key is deleted after FAILED (attempts exhausted)

## 4. Rate Limit Boundary Tests

- [x] 4.1 [core-api] Add test in `tests/test_otp_service.py` for exact boundary: 1 SMS sent → per-minute blocked
- [x] 4.2 [core-api] Add test in `tests/test_otp_service.py` verifying `retry_after` is a positive integer when rate-limited

## 5. Token Lifecycle Tests

- [x] 5.1 [core-api] Create `tests/test_token_lifecycle.py` with test: `issue_tokens` returns decodable access token with correct `sub` and `role`
- [x] 5.2 [core-api] Add test in `tests/test_token_lifecycle.py`: refresh token stored in Redis as `session:{token}` with `user_id`
- [x] 5.3 [core-api] Add test in `tests/test_token_lifecycle.py`: `refresh_tokens` deletes old token, returns new pair, new refresh token exists in Redis
- [x] 5.4 [core-api] Add test in `tests/test_token_lifecycle.py`: new access token after rotation contains same `user_id`
- [x] 5.5 [core-api] Add test in `tests/test_token_lifecycle.py`: double-use of rotated refresh token returns `None`
- [x] 5.6 [core-api] Add test in `tests/test_token_lifecycle.py`: `logout` deletes session key and returns `True`
- [x] 5.7 [core-api] Add test in `tests/test_token_lifecycle.py`: `logout` with nonexistent token returns `False`

## 6. Verify

- [x] 6.1 [core-api] Run `pytest tests/test_otp_service.py tests/test_token_lifecycle.py -v` — all tests pass with no `redis-server` running
