import os

# Подставляем минимальные env-переменные до импорта приложения
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("ENCRYPTION_KEY", "0" * 64)

_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL", "")

from collections.abc import Generator
from unittest.mock import patch

import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

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


@pytest.fixture(scope="module")
def migrated_db_session():
    """Сессия к реальному PostgreSQL с применёнными миграциями.

    Пропускается, если TEST_DATABASE_URL не указывает на Postgres.
    Используется в тестах моделей и ORM-relationship.
    """
    if _TEST_DB_URL.startswith("sqlite"):
        pytest.skip("Требует PostgreSQL (TEST_DATABASE_URL)")
    from alembic import command
    from alembic.config import Config
    import pathlib

    alembic_ini = str(
        pathlib.Path(__file__).parents[3] / "database" / "alembic.ini"
    )
    cfg = Config(alembic_ini)
    cfg.set_main_option("sqlalchemy.url", _TEST_DB_URL)
    command.upgrade(cfg, "head")

    engine = create_engine(_TEST_DB_URL)
    with Session(engine) as session:
        yield session
        session.rollback()

    engine.dispose()


@pytest.fixture
def auth_svc(r: fakeredis.FakeRedis) -> Generator[AuthService, None, None]:
    with patch("core_api.services.auth.settings") as mock_settings:
        mock_settings.jwt_secret_key = "test-secret"
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.access_token_ttl = 900
        mock_settings.refresh_token_ttl = 604800
        yield AuthService(r)
