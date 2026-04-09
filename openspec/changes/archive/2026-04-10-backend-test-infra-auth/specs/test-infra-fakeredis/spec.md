## ADDED Requirements

### Requirement: FakeRedis dev dependency
The project SHALL declare `fakeredis[lua]>=2.21,<3.0` in `pyproject.toml` under `[project.optional-dependencies] dev`.

#### Scenario: Dependency is installable
- **WHEN** a developer runs `pip install -e ".[dev]"` in `services/core-api/`
- **THEN** `fakeredis` with Lua support is installed alongside pytest and httpx

### Requirement: FakeRedis fixture replaces real Redis
`tests/conftest.py` SHALL provide a `r` fixture that returns a `fakeredis.FakeRedis` instance (with Lua support enabled). The fixture SHALL create a new instance per test (no shared state). The `otp_svc` fixture SHALL construct `OTPService(r)` using this fake client.

#### Scenario: OTP tests run without redis-server
- **WHEN** `pytest tests/test_otp_service.py` is executed with no `redis-server` running
- **THEN** all tests pass using the in-process FakeRedis

#### Scenario: Each test gets isolated state
- **WHEN** two tests run sequentially, and the first writes key `otp:abc`
- **THEN** the second test does NOT see `otp:abc` because it receives a fresh FakeRedis instance

### Requirement: AuthService fixture
`tests/conftest.py` SHALL provide an `auth_svc` fixture that returns an `AuthService` instance backed by FakeRedis, with `settings.jwt_secret_key`, `settings.jwt_algorithm`, and `settings.access_token_ttl` patched to deterministic test values.

#### Scenario: Token lifecycle tests use auth_svc fixture
- **WHEN** a test requests the `auth_svc` fixture
- **THEN** it receives an `AuthService` connected to a FakeRedis instance with known JWT settings
