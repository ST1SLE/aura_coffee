import os

# Подставляем минимальные env-переменные до импорта приложения
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("ENCRYPTION_KEY", "0" * 64)

from collections.abc import Generator
from unittest.mock import patch

import fakeredis
import pytest
from fastapi.testclient import TestClient

from core_api.main import app
from core_api.services.auth import AuthService
from core_api.services.otp import OTPService


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def r() -> fakeredis.FakeRedis:
    return fakeredis.FakeRedis()


@pytest.fixture
def otp_svc(r: fakeredis.FakeRedis) -> OTPService:
    return OTPService(r)


@pytest.fixture
def auth_svc(r: fakeredis.FakeRedis) -> Generator[AuthService, None, None]:
    with patch("core_api.services.auth.settings") as mock_settings:
        mock_settings.jwt_secret_key = "test-secret"
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.access_token_ttl = 900
        mock_settings.refresh_token_ttl = 604800
        yield AuthService(r)
