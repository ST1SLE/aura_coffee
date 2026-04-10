import os

# Подставляем минимальные env-переменные до импорта приложения
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("ENCRYPTION_KEY", "0" * 64)

# Тесты НИКОГДА не падают в DATABASE_URL (prod DB). Если TEST_DATABASE_URL
# не задан — уходим в in-memory sqlite и Postgres-фикстуры skip-аются.
_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "sqlite://")

from collections.abc import Generator
from unittest.mock import patch
from urllib.parse import urlparse, urlunparse

import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
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
def auth_svc(r: fakeredis.FakeRedis) -> Generator[AuthService, None, None]:
    with patch("core_api.services.auth.settings") as mock_settings:
        mock_settings.jwt_secret_key = "test-secret"
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.access_token_ttl = 900
        mock_settings.refresh_token_ttl = 604800
        yield AuthService(r)


@pytest.fixture
def cart_redis() -> Generator[fakeredis.FakeRedis, None, None]:
    """FakeRedis для тестов корзины.

    Патчит core_api.deps.redis.get_redis, чтобы FastAPI-зависимость и прямые
    вызовы CartService получали один и тот же изолированный экземпляр.
    Данные очищаются после каждого теста.
    """
    fake = fakeredis.FakeRedis()

    def _override():
        yield fake

    with patch("core_api.deps.redis.get_redis", side_effect=_override):
        yield fake
    fake.flushall()


@pytest.fixture
def db_session() -> Generator[None, None, None]:
    """Функциональная сессия к реальному PostgreSQL с применёнными миграциями.

    Пропускается, если TEST_DATABASE_URL не указывает на Postgres.
    Откатывает транзакцию после теста (данные не сохраняются).
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
