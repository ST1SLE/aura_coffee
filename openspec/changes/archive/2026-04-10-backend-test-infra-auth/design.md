## Context

**Affected modules:** [core-api], [redis]

`services/core-api/tests/` currently contains ~1 100 lines of tests. Redis-backed tests (`test_otp_service.py`) connect to a live Redis on DB 15 via `TEST_REDIS_URL`. This requires a running `redis-server` both locally and in CI, and `flushdb` between runs creates a shared-state dependency that can cause flaky failures under parallel execution.

The OTP Lua verification script (`_VERIFY_LUA` in `services/otp.py`) has 5 distinct exit branches; only 3 are exercised. `AuthService.refresh_tokens` (token rotation) and `AuthService.logout` have zero direct unit tests — they are only exercised indirectly through endpoint integration tests, which mock heavily.

## Goals / Non-Goals

**Goals:**
- Replace the real-Redis test dependency with `fakeredis[lua]` so unit tests run without external services.
- Achieve full branch coverage of the OTP Lua script state machine (all 5 exit paths).
- Add direct unit tests for the `AuthService` token lifecycle: issue → refresh (rotation) → double-use rejection → logout.
- Strengthen rate-limit boundary tests (at-limit vs. over-limit, `retry_after` value).

**Non-Goals:**
- No changes to production code in `src/core_api/`.
- No async migration (`pytest-asyncio`, `aioredis`).
- No coverage tooling or thresholds.
- No endpoint-level integration tests (already covered).

## Decisions

### D1: Use `fakeredis[lua]` instead of `testcontainers` or mocks

`fakeredis[lua]` embeds a Lua interpreter that executes Redis Lua scripts identically to real Redis. This is critical because the OTP verification logic lives in a Lua script — plain `unittest.mock` cannot exercise it, and `testcontainers` adds Docker overhead.

**Alternatives considered:**
- **`testcontainers-redis`**: Spins up a real Redis in Docker per session. Accurate but slow (~2s startup), requires Docker socket, and is overkill for unit tests.
- **Manual mocking**: Cannot execute Lua scripts. Would require reimplementing the Lua logic in Python, defeating the purpose.

### D2: Single `FakeRedis` instance per test via `conftest.py` fixture

Each test gets a fresh `FakeRedis()` instance (no persistence between tests). The existing `r` fixture in `conftest.py` SHALL be replaced; the `otp_svc` fixture SHALL be updated to use it. A new `auth_svc` fixture SHALL be added.

**Rationale:** Per-test isolation without `flushdb`. No shared state, no ordering dependencies.

### D3: Test file organisation

| File | Scope |
|------|-------|
| `tests/conftest.py` | `fake_redis`, `otp_svc`, `auth_svc` fixtures |
| `tests/test_otp_service.py` | OTP Lua state machine + rate limits (rewritten) |
| `tests/test_token_lifecycle.py` | AuthService issue/refresh/logout (new) |

Existing test files (`test_jwt.py`, `test_auth_endpoints.py`, etc.) SHALL NOT be modified.

### D4: OTP Lua branches to cover

Per `_VERIFY_LUA` in `otp.py:20-51` and `VerifyResult` enum:

| # | Branch | Trigger | Expected |
|---|--------|---------|----------|
| 1 | `expired` | Key missing (TTL elapsed) | `VerifyResult.EXPIRED` |
| 2 | `invalid_status` | OTP status ≠ "sent" (e.g. still "created") | `VerifyResult.INVALID_STATUS` |
| 3 | `verified` | Correct code submitted | `VerifyResult.VERIFIED`, key deleted |
| 4 | `wrong_code` | Wrong code, attempts < max | `VerifyResult.WRONG_CODE`, remaining > 0 |
| 5 | `failed` | Wrong code, attempts = max | `VerifyResult.FAILED`, key deleted |

Additional edge case: correct code on the final attempt (attempt 5 of 5) SHALL return `VERIFIED`.

## Risks / Trade-offs

- **[Risk] FakeRedis Lua fidelity** — `fakeredis` Lua support covers standard commands but MAY diverge on edge cases (e.g. `KEEPTTL` was added in fakeredis 2.21+).
  → **Mitigation:** Pin `fakeredis[lua]>=2.21`. Run the full suite against real Redis in CI nightly as a smoke test (not blocking).

- **[Risk] Fixture rename breaks imports** — Renaming `r` → `fake_redis` in `conftest.py` breaks `test_otp_service.py` parameter names.
  → **Mitigation:** Keep the fixture name `r` as an alias or update all call sites in the same commit.

- **[Trade-off] No concurrent-access tests** — FakeRedis is single-threaded; we cannot test true Redis race conditions (e.g. two concurrent `verify_otp` calls).
  → **Accepted:** The Lua script's atomicity guarantee comes from Redis itself, not from our code. Unit tests verify branch logic; concurrency correctness is a Redis property.

## Open Questions

None — scope is narrow and fully determined by existing code.
