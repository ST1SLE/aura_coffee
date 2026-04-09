## 1. Shared Models & Enums

- [x] 1.1 [shared] Create `UserStatus` enum (PENDING_VERIFICATION, ACTIVE, BLOCKED, DELETED) in `packages/shared/src/shared/enums.py`
- [x] 1.2 [shared] Create `OTPStatus` enum (CREATED, SENT, VERIFIED, EXPIRED, FAILED) in `packages/shared/src/shared/enums.py`
- [x] 1.3 [shared] Create `User` SQLAlchemy model in `packages/shared/src/shared/models/user.py` — id (UUID PK), phone_hash (VARCHAR UNIQUE), status (user_status ENUM), created_at, deleted_at
- [x] 1.4 [shared] Create `UserProfile` SQLAlchemy model in `packages/shared/src/shared/models/user_profile.py` — user_id (UUID FK→users PK), phone (BYTEA), display_name (VARCHAR nullable), preferred_language (VARCHAR default 'ru')
- [x] 1.5 [shared] Create `LoyaltyAccount` SQLAlchemy model in `packages/shared/src/shared/models/loyalty_account.py` — user_id (UUID FK→users PK), balance (INTEGER default 0), created_at
- [x] 1.6 [shared] Export new models in `packages/shared/src/shared/models/__init__.py`

## 2. Database Migration

- [x] 2.1 [database] Create Alembic migration `0002_auth_tables.py` — create user_status ENUM, users table, user_profiles table, loyalty_accounts table, index on users.phone_hash
- [x] 2.2 [database] Verify migration rollback (downgrade) drops all tables and enum cleanly

## 3. Core API — Crypto & Phone Utilities

- [x] 3.1 [core-api] Create phone normalization utility in `services/core-api/src/core_api/utils/phone.py` — normalize to E.164 (+7XXXXXXXXXX), validate format
- [x] 3.2 [core-api] Create phone hashing utility in `services/core-api/src/core_api/utils/crypto.py` — SHA-256 hex digest of normalized phone
- [x] 3.3 [core-api] Create phone encryption/decryption utility in `services/core-api/src/core_api/utils/crypto.py` — AES-256-GCM with ENCRYPTION_KEY from env, unique nonce per call

## 4. Core API — Settings & Dependencies

- [x] 4.1 [core-api] Add auth-related settings to `services/core-api/src/core_api/settings.py` — JWT_SECRET_KEY, JWT_ALGORITHM (HS256), ACCESS_TOKEN_TTL (900s), REFRESH_TOKEN_TTL (604800s), ENCRYPTION_KEY, SMSRU_API_KEY
- [x] 4.2 [core-api] Create Redis dependency in `services/core-api/src/core_api/deps/redis.py` — get_redis() yielding async/sync Redis client

## 5. Core API — OTP Service

- [x] 5.1 [redis] Create Redis Lua script for atomic OTP verify (check code + increment attempts + conditional status change) in `services/core-api/src/core_api/services/otp.py`
- [x] 5.2 [core-api] Create OTP service in `services/core-api/src/core_api/services/otp.py` — create_otp(phone_hash): generate code, store in Redis with TTL 300s, status CREATED
- [x] 5.3 [core-api] Add rate-limit checking to OTP service — check_rate_limit(phone_hash): verify 3 counters in Redis, return (allowed, retry_after)
- [x] 5.4 [core-api] Add rate-limit incrementing to OTP service — increment_rate_limits(phone_hash): INCR + EXPIRE on 3 counter keys
- [x] 5.5 [core-api] Add OTP verification to OTP service — verify_otp(phone_hash, code): atomic Lua-based verify, return result (verified/wrong_code/expired/failed)
- [x] 5.6 [core-api] Add OTP status update method — update_otp_status(phone_hash, new_status): for sms-worker callback

## 6. Core API — Auth Service

- [x] 6.1 [core-api] Create JWT utility in `services/core-api/src/core_api/services/auth.py` — create_access_token(user_id, role): HS256-signed JWT with sub/role/iat/exp
- [x] 6.2 [core-api] Add refresh token management — create_refresh_token(user_id): generate UUID, store in Redis session:{token} with TTL 7d
- [x] 6.3 [core-api] Add token refresh logic — refresh_tokens(refresh_token): validate, rotate, return new pair
- [x] 6.4 [core-api] Add logout logic — logout(refresh_token): delete from Redis

## 7. Core API — User Service

- [x] 7.1 [core-api] Create user service in `services/core-api/src/core_api/services/user.py` — get_or_create_user(phone, phone_hash): find by phone_hash or create PENDING_VERIFICATION user + profile
- [x] 7.2 [core-api] Add user activation method — activate_user(user_id): transition PENDING_VERIFICATION → ACTIVE, create loyalty_accounts in single transaction

## 8. Core API — Auth Router

- [x] 8.1 [core-api] Create Pydantic request/response schemas in `services/core-api/src/core_api/schemas/auth.py` — SendCodeRequest, VerifyCodeRequest, RefreshRequest, TokenResponse, ErrorResponse
- [x] 8.2 [core-api] Create `POST /api/v1/auth/send-code` endpoint in `services/core-api/src/core_api/routers/auth.py` — normalize phone, check rate-limit, get_or_create_user, create OTP, dispatch SMS task
- [x] 8.3 [core-api] Create `POST /api/v1/auth/verify-code` endpoint — normalize phone, verify OTP, activate user if needed, issue tokens
- [x] 8.4 [core-api] Create `POST /api/v1/auth/refresh` endpoint — validate refresh token, rotate, return new tokens
- [x] 8.5 [core-api] Create `POST /api/v1/auth/logout` endpoint (requires auth) — delete refresh token from Redis
- [x] 8.6 [core-api] Register auth router in `services/core-api/src/core_api/main.py`

## 9. Core API — Auth Middleware

- [x] 9.1 [core-api] Create `get_current_user` FastAPI dependency in `services/core-api/src/core_api/deps/auth.py` — decode JWT from Authorization header, verify signature and expiry, return user_id and role

## 10. SMS Worker — OTP Task

- [x] 10.1 [sms-worker] Add SMS.ru API client in `services/sms-worker/src/sms_worker/clients/smsru.py` — send_sms(phone, message): POST /sms/send, return success/failure
- [x] 10.2 [sms-worker] Add sms-worker settings in `services/sms-worker/src/sms_worker/settings.py` — SMSRU_API_KEY, REDIS_URL, ENCRYPTION_KEY
- [x] 10.3 [sms-worker] Create `send_otp_sms` Celery task in `services/sms-worker/src/sms_worker/tasks/otp.py` — decrypt phone, send via SMS.ru, update OTP status in Redis (CREATED→SENT or CREATED→FAILED), retry 3x with backoff 2s/8s/32s

## 11. Configuration & Environment

- [x] 11.1 [database] Add new env vars to `.env.example` — JWT_SECRET_KEY, ENCRYPTION_KEY, SMSRU_API_KEY
- [x] 11.2 [core-api] Add `PyJWT` and `cryptography` to core-api dependencies in `services/core-api/pyproject.toml`
- [x] 11.3 [sms-worker] Add `cryptography` and `httpx` to sms-worker dependencies in `services/sms-worker/pyproject.toml`

## 12. Tests

- [x] 12.1 [core-api] Test phone normalization — valid RU phones, 8-prefix, invalid formats
- [x] 12.2 [core-api] Test phone hash — deterministic SHA-256 output
- [x] 12.3 [core-api] Test phone encryption/decryption — round-trip, unique nonces
- [x] 12.4 [core-api] Test OTP service — create, verify correct, verify wrong, attempts exhaustion, expired
- [x] 12.5 [core-api] Test rate-limit — under limit, per-minute exceeded, per-hour exceeded, per-day exceeded
- [x] 12.6 [core-api] Test auth endpoints integration — send-code → verify-code → refresh → logout full flow
- [x] 12.7 [core-api] Test user creation — new user, existing pending user, existing active user, blocked user rejection
- [x] 12.8 [core-api] Test JWT — token creation, validation, expiry, invalid signature
- [x] 12.9 [sms-worker] Test send_otp_sms task — success, retry on failure, status updates in Redis
