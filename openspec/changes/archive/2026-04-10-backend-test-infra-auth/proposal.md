## Why

Existing auth tests in `services/core-api/` require a live Redis on DB 15 — this makes CI fragile and local runs fail without `redis-server`. Coverage gaps exist: the OTP Lua state machine only tests the happy path and basic failures, refresh-token rotation is untested, and rate-limit boundary conditions are missing. Fixing both the infra dependency and coverage gaps now prevents regressions as we build order and payment flows (Phase 3).

## What Changes

- Add `fakeredis[lua]` to `[project.optional-dependencies] dev` in `pyproject.toml` so all Redis-backed tests run without a real server.
- Replace the real-Redis fixture in `tests/conftest.py` with a `fakeredis.FakeRedis` instance shared across OTP, auth, and rate-limit tests.
- Expand `test_otp_service.py` to cover every Lua script branch: CREATED→SENT→VERIFIED, CREATED→SENT→WRONG_CODE→…→FAILED, verify-when-status-is-still-CREATED (`invalid_status`), verify-after-TTL-expired, and correct-code-on-final-attempt.
- Add `test_token_lifecycle.py` covering: issue tokens → decode access → validate refresh in Redis, refresh rotation (old token deleted, new pair issued), double-use of a rotated refresh token returns `None`, and logout deletes session key.
- Strengthen rate-limit tests with boundary values (exactly at limit vs. limit+1) and verify `retry_after` decreases over time.

## Non-Goals

- No changes to production code (`src/core_api/`). This is test-only.
- No integration/E2E tests hitting FastAPI `TestClient` — endpoint-level tests already exist in `test_auth_endpoints.py` and `test_staff_auth.py`.
- No migration to async Redis or `pytest-asyncio`. Sync Redis client stays.
- No test coverage tooling (`pytest-cov`, coverage thresholds) — separate concern.

## Capabilities

### New Capabilities
- `test-infra-fakeredis`: Shared fakeredis-based test fixtures replacing real Redis dependency, centralised in `conftest.py`.
- `otp-state-machine-tests`: Exhaustive unit tests for every branch of the OTP Lua verification script and status transitions.
- `token-lifecycle-tests`: Unit tests for JWT+refresh token issue/rotate/logout cycle in `AuthService`.

### Modified Capabilities
<!-- No spec-level requirement changes — these are test-only additions. -->

## Impact

- **Dependencies:** `fakeredis[lua]` added to dev extras in `services/core-api/pyproject.toml`.
- **Test infra:** `tests/conftest.py` gains new fixtures; existing `r` fixture changes from real Redis to FakeRedis. Existing tests that use `r` continue to pass because FakeRedis is API-compatible.
- **CI:** Redis service container is no longer required for `core-api` unit tests (integration tests may still need it).
- **MVP phase:** Phase 1 (Auth), hardening.
