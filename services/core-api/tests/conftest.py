import os

# Подставляем минимальные env-переменные до импорта приложения
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("ENCRYPTION_KEY", "0" * 64)

# Тесты НИКОГДА не падают в DATABASE_URL (prod DB). Если TEST_DATABASE_URL
# не задан — уходим в in-memory sqlite и Postgres-фикстуры skip-аются.
_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "sqlite://")

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from urllib.parse import urlparse, urlunparse

import fakeredis
import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from core_api.main import app
from core_api.services.auth import AuthService
from core_api.services.otp import OTPService

# ─────────────────────────────────────────────
# In-memory SQLite: единый движок со StaticPool
# ─────────────────────────────────────────────
# sqlite:// создаёт новую БД на каждое соединение. StaticPool гарантирует,
# что все запросы идут через одно и то же соединение и видят одни таблицы.
if _TEST_DB_URL.startswith("sqlite"):
    from sqlalchemy.pool import StaticPool
    import shared.models.menu  # noqa: F401 — регистрирует модели в Base.metadata
    import core_api.deps.database as _db_module
    from shared.models import Base

    _sqlite_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(_sqlite_engine)
    # Перезаписываем движок и фабрику сессий в модуле deps.database
    from sqlalchemy.orm import sessionmaker as _sessionmaker
    _db_module.engine = _sqlite_engine
    _db_module.SessionLocal = _sessionmaker(bind=_sqlite_engine)

# ─────────────────────────────────────────────
# JWT-хелперы для тестов
# ─────────────────────────────────────────────
_JWT_SECRET = "test-secret"  # совпадает с JWT_SECRET_KEY в окружении тестов


def _make_jwt(role: str) -> str:
    """Создание JWT-токена заданной роли без мокирования AuthService."""
    payload = {
        "sub": str(uuid.uuid4()),
        "role": role,
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(seconds=900),
    }
    return pyjwt.encode(payload, _JWT_SECRET, algorithm="HS256")


@pytest.fixture
def admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_make_jwt('admin')}"}


@pytest.fixture
def barista_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_make_jwt('barista')}"}


@pytest.fixture
def customer_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_make_jwt('customer')}"}


@pytest.fixture
def courier_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_make_jwt('courier')}"}


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


@pytest.fixture(scope="session")
def _ensure_test_database() -> None:
    """Создаёт базу TEST_DATABASE_URL, если её ещё нет.

    Подключается к maintenance-базе ``postgres`` на том же хосте с теми же
    кредами, проверяет ``pg_database`` и выполняет ``CREATE DATABASE`` при
    необходимости. Для sqlite ничего не делает.
    """
    if _TEST_DB_URL.startswith("sqlite"):
        return

    parsed = urlparse(_TEST_DB_URL)
    db_name = parsed.path.lstrip("/")
    if not db_name:
        pytest.fail("TEST_DATABASE_URL must include a database name")

    admin_url = urlunparse(parsed._replace(path="/postgres"))
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": db_name},
            ).scalar()
            if not exists:
                # Имя БД нельзя параметризовать — валидируем вручную.
                if not db_name.replace("_", "").isalnum():
                    pytest.fail(f"Unsafe test database name: {db_name!r}")
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    finally:
        admin_engine.dispose()


@pytest.fixture(scope="module")
def migrated_db_session(_ensure_test_database):
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
def db_client(migrated_db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient с get_db, перенаправленным в тестовую БД.

    Позволяет тестам засевать данные через migrated_db_session, а запросам
    через TestClient использовать тот же сеанс и те же данные.
    """
    from core_api.deps.database import get_db

    def _override() -> Generator[Session, None, None]:
        yield migrated_db_session

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def auth_svc(r: fakeredis.FakeRedis) -> Generator[AuthService, None, None]:
    with patch("core_api.services.auth.settings") as mock_settings:
        mock_settings.jwt_secret_key = "test-secret"
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.access_token_ttl = 900
        mock_settings.refresh_token_ttl = 604800
        yield AuthService(r)
