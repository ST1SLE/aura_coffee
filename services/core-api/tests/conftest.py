import os
import pathlib as _pathlib
import sys as _sys

# Корень репо в sys.path — чтобы тесты могли импортировать `database.seeds.*`
_REPO_ROOT = _pathlib.Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

# Подставляем минимальные env-переменные до импорта приложения
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("ENCRYPTION_KEY", "0" * 64)

# Тесты НИКОГДА не падают в DATABASE_URL (prod DB). Если TEST_DATABASE_URL
# не задан — уходим в in-memory sqlite и Postgres-фикстуры skip-аются.
_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "sqlite://")

import pathlib
import uuid
from collections.abc import Generator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
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
def _current_jwt_secret() -> str:
    """Секрет JWT, согласованный с settings.jwt_secret_key (читается из env)."""
    return os.environ.get("JWT_SECRET_KEY", "test-secret")


def _make_jwt(role: str) -> str:
    """Создание JWT-токена заданной роли без мокирования AuthService."""
    payload = {
        "sub": str(uuid.uuid4()),
        "role": role,
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(seconds=900),
    }
    return pyjwt.encode(payload, _current_jwt_secret(), algorithm="HS256")


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


# ---------------------------------------------------------------------------
# Публичное меню — фикстуры для PostgreSQL-интеграционных тестов
# ---------------------------------------------------------------------------

@dataclass
class PublicMenuSeed:
    """Идентификаторы сидированных данных для тестов публичного меню."""

    engine: Any
    # Категории
    cat_drink_id: int
    cat_food_id: int
    cat_invis_id: int       # is_visible=False
    cat_mod_type_id: int    # type=modifier
    # Позиции — категория drink (sort_order=10/20/30)
    item_d1_id: int         # available=True, archived=False, sort_order=10
    item_d2_id: int         # available=False, archived=False, sort_order=20
    item_d3_id: int         # archived=True, sort_order=30
    # Позиции — категория food (sort_order=10/20/30)
    item_f1_id: int         # available=True, archived=False, sort_order=10
    item_f2_id: int         # available=False, archived=False, sort_order=20
    item_f3_id: int         # archived=True, sort_order=30
    # Позиции прочих категорий
    item_invis_id: int      # в невидимой категории
    item_mt_id: int         # в modifier-type категории
    # Размеры для item_d1 (вставлены в порядке L, S — тест проверит S, L)
    size_d1_L_id: int       # label=L, available=True
    size_d1_S_id: int       # label=S, available=False
    # Модификаторы
    mod1_id: int            # sort_order=10, available=True
    mod2_id: int            # sort_order=20, available=False


@pytest.fixture(scope="session")
def _pg_ready(_ensure_test_database) -> bool:
    """Запускает миграции на TEST_DATABASE_URL один раз за pytest-сессию."""
    if _TEST_DB_URL.startswith("sqlite"):
        return False
    from alembic import command as alembic_cmd
    from alembic.config import Config

    alembic_ini = str(pathlib.Path(__file__).parents[3] / "database" / "alembic.ini")
    cfg = Config(alembic_ini)
    cfg.set_main_option("sqlalchemy.url", _TEST_DB_URL)
    alembic_cmd.upgrade(cfg, "head")
    return True


@pytest.fixture
def _pg_db_override(_pg_ready) -> Generator[Any, None, None]:
    """Переопределяет get_db → PostgreSQL (TEST_DATABASE_URL). Без данных."""
    if not _pg_ready:
        pytest.skip("Требует PostgreSQL (TEST_DATABASE_URL)")

    from core_api.deps.database import get_db

    engine = create_engine(_TEST_DB_URL)

    def override_get_db() -> Generator[Session, None, None]:
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    yield engine
    app.dependency_overrides.pop(get_db, None)
    engine.dispose()


@pytest.fixture
def seed_public_menu(_pg_db_override) -> Generator[PublicMenuSeed, None, None]:
    """Сидирует детерминированное меню в PostgreSQL и убирает данные после теста."""
    from shared.enums import CategoryType, SizeLabel
    from shared.models.menu import Category, MenuItem, Modifier, SizeOption

    engine = _pg_db_override

    with Session(engine) as session:
        # Модификаторы (без привязки к категории)
        mod1 = Modifier(
            name_ru="Сироп ваниль",
            name_en="Vanilla syrup",
            sort_order=10,
            available=True,
            price=5000,
        )
        mod2 = Modifier(
            name_ru="Карамель",
            name_en="Caramel",
            sort_order=20,
            available=False,
            price=3000,
        )

        # Категории
        cat_drink = Category(
            type=CategoryType.DRINK,
            name_ru="Напитки",
            name_en="Drinks",
            sort_order=10,
            is_visible=True,
        )
        cat_food = Category(
            type=CategoryType.FOOD,
            name_ru="Еда",
            name_en="Food",
            sort_order=20,
            is_visible=True,
        )
        cat_invis = Category(
            type=CategoryType.DRINK,
            name_ru="Скрытые",
            name_en="Hidden",
            sort_order=30,
            is_visible=False,
        )
        cat_mod_type = Category(
            type=CategoryType.MODIFIER,
            name_ru="Топпинги",
            name_en="Toppings",
            sort_order=40,
            is_visible=True,
        )
        session.add_all([mod1, mod2, cat_drink, cat_food, cat_invis, cat_mod_type])
        session.flush()

        # Позиции категории drink
        item_d1 = MenuItem(
            category_id=cat_drink.id,
            name_ru="Латте",
            name_en="Latte",
            description_ru="Молочный кофе",
            description_en="Milk coffee",
            sort_order=10,
            available=True,
            archived=False,
            base_price=35000,
        )
        item_d2 = MenuItem(
            category_id=cat_drink.id,
            name_ru="Американо",
            name_en="Americano",
            description_ru=None,
            description_en=None,
            sort_order=20,
            available=False,
            archived=False,
            base_price=25000,
        )
        item_d3 = MenuItem(
            category_id=cat_drink.id,
            name_ru="Архив напиток",
            name_en="Archived drink",
            sort_order=30,
            available=True,
            archived=True,
            base_price=10000,
        )
        # Позиции категории food
        item_f1 = MenuItem(
            category_id=cat_food.id,
            name_ru="Круассан",
            name_en="Croissant",
            description_ru="Свежая выпечка",
            description_en="Fresh pastry",
            sort_order=10,
            available=True,
            archived=False,
            base_price=15000,
        )
        item_f2 = MenuItem(
            category_id=cat_food.id,
            name_ru="Сэндвич",
            name_en="Sandwich",
            description_ru=None,
            description_en=None,
            sort_order=20,
            available=False,
            archived=False,
            base_price=20000,
        )
        item_f3 = MenuItem(
            category_id=cat_food.id,
            name_ru="Убран",
            name_en="Removed",
            sort_order=30,
            available=True,
            archived=True,
            base_price=5000,
        )
        # Позиции прочих категорий
        item_invis = MenuItem(
            category_id=cat_invis.id,
            name_ru="Невидимый",
            name_en="Invisible",
            sort_order=10,
            available=True,
            archived=False,
            base_price=1000,
        )
        item_mt = MenuItem(
            category_id=cat_mod_type.id,
            name_ru="Топпинг 1",
            name_en="Topping 1",
            sort_order=10,
            available=True,
            archived=False,
            base_price=500,
        )
        session.add_all([item_d1, item_d2, item_d3, item_f1, item_f2, item_f3, item_invis, item_mt])
        session.flush()

        # Размеры: вставляем L до S для item_d1 (тест порядка ожидает S, L в ответе)
        size_d1_L = SizeOption(menu_item_id=item_d1.id, label=SizeLabel.L, price=38000, available=True)
        size_d1_S = SizeOption(menu_item_id=item_d1.id, label=SizeLabel.S, price=30000, available=False)
        size_d2_M = SizeOption(menu_item_id=item_d2.id, label=SizeLabel.M, price=25000, available=True)
        size_d2_S = SizeOption(menu_item_id=item_d2.id, label=SizeLabel.S, price=22000, available=False)
        size_f1_L = SizeOption(menu_item_id=item_f1.id, label=SizeLabel.L, price=18000, available=True)
        size_f1_S = SizeOption(menu_item_id=item_f1.id, label=SizeLabel.S, price=12000, available=False)
        size_f2_M = SizeOption(menu_item_id=item_f2.id, label=SizeLabel.M, price=22000, available=True)
        size_f2_S = SizeOption(menu_item_id=item_f2.id, label=SizeLabel.S, price=18000, available=False)
        session.add_all([
            size_d1_L, size_d1_S, size_d2_M, size_d2_S,
            size_f1_L, size_f1_S, size_f2_M, size_f2_S,
        ])
        session.flush()

        # M:N: модификаторы → все не-архивные позиции видимых категорий
        for item in [item_d1, item_d2, item_f1, item_f2]:
            item.modifiers.append(mod1)
            item.modifiers.append(mod2)
        session.flush()

        session.commit()

        seed = PublicMenuSeed(
            engine=engine,
            cat_drink_id=cat_drink.id,
            cat_food_id=cat_food.id,
            cat_invis_id=cat_invis.id,
            cat_mod_type_id=cat_mod_type.id,
            item_d1_id=item_d1.id,
            item_d2_id=item_d2.id,
            item_d3_id=item_d3.id,
            item_f1_id=item_f1.id,
            item_f2_id=item_f2.id,
            item_f3_id=item_f3.id,
            item_invis_id=item_invis.id,
            item_mt_id=item_mt.id,
            size_d1_L_id=size_d1_L.id,
            size_d1_S_id=size_d1_S.id,
            mod1_id=mod1.id,
            mod2_id=mod2.id,
        )

    yield seed

    # Очистка: сначала удаляем позиции (RESTRICT FK category_id), потом категории и модификаторы
    with Session(engine) as session:
        all_item_ids = [
            seed.item_d1_id, seed.item_d2_id, seed.item_d3_id,
            seed.item_f1_id, seed.item_f2_id, seed.item_f3_id,
            seed.item_invis_id, seed.item_mt_id,
        ]
        for iid in all_item_ids:
            obj = session.get(MenuItem, iid)
            if obj:
                session.delete(obj)
        session.flush()

        for cid in [seed.cat_drink_id, seed.cat_food_id, seed.cat_invis_id, seed.cat_mod_type_id]:
            obj = session.get(Category, cid)
            if obj:
                session.delete(obj)
        session.flush()

        for mid in [seed.mod1_id, seed.mod2_id]:
            obj = session.get(Modifier, mid)
            if obj:
                session.delete(obj)

        session.commit()


# ---------------------------------------------------------------------------
# Корзина — фикстуры для тестов корзины
# ---------------------------------------------------------------------------

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
def db_session(_ensure_test_database) -> Generator[Session, None, None]:
    """Функциональная сессия к реальному PostgreSQL с применёнными миграциями.

    Пропускается, если TEST_DATABASE_URL не указывает на Postgres.
    Изоляция: внешняя транзакция + SAVEPOINT (join_transaction_mode=
    "create_savepoint"), чтобы любые `session.commit()` внутри теста
    превращались в release-savepoint, а внешний rollback в teardown
    гарантированно очищал данные. Без этого staff-scoped тесты (которые
    не фильтруют по user_id) видят накапливающиеся orders из соседних
    тестов и падают.
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
    connection = engine.connect()
    outer_tx = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer_tx.rollback()
        connection.close()
        engine.dispose()


# ─────────────────────────────────────────────
# GRACE-LDD: log-capture fixture for verification tests
# ─────────────────────────────────────────────
# Exposes shared.grace.testing.GraceLogCapture as the `grace_logs` fixture so
# tests can assert on [Module][fn][BLOCK] markers and BELIEF/ACTUAL/STATUS
# pairs emitted by code paths under test. See docs/verification-plan.xml
# GlobalPolicy/log-format and packages/shared/tests/test_grace_logging.py
# for usage examples.
from shared.grace.testing import GraceLogCapture as _GraceLogCapture  # noqa: E402


@pytest.fixture
def grace_logs():
    """Capture GRACE LDD log lines emitted during a test.

    Usage:
        def test_x(grace_logs):
            ... call code under test ...
            grace_logs.assert_trajectory(
                ("orders.create", "BLOCK_TX_BEGIN"),
                ("orders.create", "BLOCK_STATE_TRANSITION"),
                ("orders.create", "BLOCK_TX_COMMIT"),
            )
            assert grace_logs.beliefs(status="MISMATCH") == []
    """
    capture = _GraceLogCapture()
    capture.install()
    try:
        yield capture
    finally:
        capture.uninstall()
