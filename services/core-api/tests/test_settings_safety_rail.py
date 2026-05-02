"""Core API settings safety rails for auth and PII secrets (INV-015)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from core_api.settings import Settings


VALID_JWT_SECRET = "0123456789abcdef0123456789abcdef"
VALID_ENCRYPTION_KEY = "0123456789abcdef" * 4


def _set_required_env(monkeypatch, **overrides: str) -> None:
    values = {
        "AURA_ENV": "production",
        "DATABASE_URL": "sqlite://",
        "REDIS_URL": "redis://localhost:6379/0",
        "JWT_SECRET_KEY": VALID_JWT_SECRET,
        "ENCRYPTION_KEY": VALID_ENCRYPTION_KEY,
    }
    values.update(overrides)
    for key, value in values.items():
        monkeypatch.setenv(key, value)


def test_dev_env_accepts_local_placeholder_secrets(monkeypatch) -> None:
    _set_required_env(
        monkeypatch,
        AURA_ENV="dev",
        JWT_SECRET_KEY="test-secret",
        ENCRYPTION_KEY="0" * 64,
    )

    settings = Settings()  # type: ignore[call-arg]

    assert settings.aura_env == "dev"
    assert settings.jwt_secret_key == "test-secret"
    assert settings.encryption_key == "0" * 64


@pytest.mark.parametrize(
    "jwt_secret",
    ["", "test-secret", "change-me-to-random-secret", "short"],
)
def test_non_dev_rejects_weak_jwt_secret(monkeypatch, jwt_secret: str) -> None:
    _set_required_env(monkeypatch, JWT_SECRET_KEY=jwt_secret)

    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        Settings()  # type: ignore[call-arg]


@pytest.mark.parametrize(
    "encryption_key",
    [
        "",
        "0" * 64,
        "abc",
        "not-a-hex-value".ljust(64, "x"),
        "a" * 64,
    ],
)
def test_non_dev_rejects_weak_encryption_key(
    monkeypatch, encryption_key: str
) -> None:
    _set_required_env(monkeypatch, ENCRYPTION_KEY=encryption_key)

    with pytest.raises(ValidationError, match="ENCRYPTION_KEY"):
        Settings()  # type: ignore[call-arg]


def test_non_dev_accepts_strong_jwt_and_encryption_key(monkeypatch) -> None:
    _set_required_env(monkeypatch)

    settings = Settings()  # type: ignore[call-arg]

    assert settings.aura_env == "production"
    assert settings.jwt_secret_key == VALID_JWT_SECRET
    assert settings.encryption_key == VALID_ENCRYPTION_KEY


def test_jwt_validation_errors_do_not_echo_raw_secret_values(monkeypatch) -> None:
    raw_jwt = "short-secret-value"
    _set_required_env(monkeypatch, JWT_SECRET_KEY=raw_jwt)

    with pytest.raises(ValidationError) as exc_info:
        Settings()  # type: ignore[call-arg]

    message = str(exc_info.value)
    assert raw_jwt not in message
    assert "input_value" not in message


def test_encryption_validation_errors_do_not_echo_raw_secret_values(
    monkeypatch,
) -> None:
    raw_key = "not-a-hex-value".ljust(64, "x")
    _set_required_env(monkeypatch, ENCRYPTION_KEY=raw_key)

    with pytest.raises(ValidationError) as exc_info:
        Settings()  # type: ignore[call-arg]

    message = str(exc_info.value)
    assert raw_key not in message
    assert "input_value" not in message
