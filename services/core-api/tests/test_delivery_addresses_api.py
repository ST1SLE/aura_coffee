"""RED: контракт CRUD-роутера /api/v1/profile/addresses (PDD §3, §5.2, §7.3 шаг 3).

Проверяет:
 - монтирование маршрутов (GET/POST/PATCH/DELETE) и записи в RBAC matrix;
 - аутентификацию (401) и ролевые гейты (403 для staff);
 - GET → список СВОИХ адресов, default первым;
 - POST → серверная валидация радиуса Haversine (INV-008), 422 out-of-radius;
 - PATCH → частичное обновление, атомарный переход is_default между строками,
   404 на чужой/несуществующий {address_id};
 - DELETE → 204 на свой, 404 на чужой, снимок в orders.delivery_address_snapshot
   НЕ мутируется (INV-014).

Импорты целевых символов (router, модель DeliveryAddress) выполняются
ВНУТРИ каждого теста, чтобы отсутствующие модули давали ImportError на
конкретном тесте, а не ломали коллекцию.
"""
from __future__ import annotations

import uuid
from typing import Any, Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core_api.main import app
from core_api.services.auth import AuthService

from tests.conftest import _TEST_DB_URL as TEST_DB_URL

_IS_SQLITE = TEST_DB_URL.startswith("sqlite")

TEST_SECRET = "test-secret-for-delivery-addresses-tests"


def _make_token(role: str = "customer", user_id: uuid.UUID | None = None) -> str:
    """JWT-токен роли role для заданного user_id (или случайного UUID)."""
    uid = user_id or uuid.uuid4()
    with patch("core_api.services.auth.settings") as mock_settings:
        mock_settings.jwt_secret_key = TEST_SECRET
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.access_token_ttl = 900
        svc = AuthService.__new__(AuthService)
        return svc.create_access_token(uid, role)


def _auth_header(role: str = "customer", user_id: uuid.UUID | None = None) -> dict[str, str]:
    return {"Authorization": f"Bearer {_make_token(role, user_id)}"}


def _patch_jwt():
    """Патч настроек JWT для middleware (совпадает с _make_token)."""
    return patch(
        "core_api.services.auth.settings",
        **{
            "jwt_secret_key": TEST_SECRET,
            "jwt_algorithm": "HS256",
            "access_token_ttl": 900,
        },
    )


client = TestClient(app)


@pytest.fixture
def db_client(db_session) -> Generator[TestClient, None, None]:
    """TestClient, привязанный к функционально-скоупной db_session (Postgres)."""
    from core_api.deps.database import get_db

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Фикстуры (см. tasks 1.3, 1.4)
# ---------------------------------------------------------------------------


def _seed_shop_settings(db_session: Any) -> None:
    """Сидирует singleton ShopSettings (id=1) если его ещё нет."""
    from shared.models import ShopSettings

    existing = db_session.get(ShopSettings, 1)
    if existing is not None:
        existing.shop_lat = 55.7558
        existing.shop_lon = 37.6173
        existing.delivery_radius_km = 5.0
        existing.min_delivery_amount = 30000
        existing.free_delivery_threshold = 100000
        existing.delivery_fee = 15000
        existing.loyalty_percent = 5
        existing.default_prep_time_minutes = 15
        existing.estimated_delivery_time_minutes = 30
        existing.working_hours = {"mon": "08:00-22:00"}
    else:
        db_session.add(
            ShopSettings(
                id=1,
                shop_lat=55.7558,
                shop_lon=37.6173,
                delivery_radius_km=5.0,
                min_delivery_amount=30000,
                free_delivery_threshold=100000,
                delivery_fee=15000,
                loyalty_percent=5,
                default_prep_time_minutes=15,
                estimated_delivery_time_minutes=30,
                working_hours={"mon": "08:00-22:00"},
            )
        )
    db_session.flush()


@pytest.fixture
def _addresses_user(db_session) -> Generator[tuple[uuid.UUID, dict[str, str]], None, None]:
    """Создаёт User + UserProfile + сидирует ShopSettings. Возвращает (user_id, auth_header)."""
    from shared.models import User, UserProfile

    user = User(phone_hash=uuid.uuid4().hex[:32])
    db_session.add(user)
    db_session.flush()

    profile = UserProfile(
        user_id=user.id,
        phone=b"test-phone-bytes",
        display_name="Test Customer",
        preferred_language="ru",
    )
    db_session.add(profile)
    _seed_shop_settings(db_session)
    db_session.flush()

    headers = _auth_header("customer", user.id)
    yield (user.id, headers)


def _saved_address(db_session: Any, user_id: uuid.UUID, **overrides: Any) -> Any:
    """Инсёртит delivery_addresses-строку и возвращает ORM-объект.

    Импорт DeliveryAddress внутри функции: до GREEN модель не существует,
    и ImportError падает на тесте, использующем хелпер, а не на коллекции.
    """
    from shared.models import DeliveryAddress

    defaults: dict[str, Any] = {
        "user_id": user_id,
        "label": "Дом",
        "address_text": "Москва, Тверская 1",
        "lat": 55.7600,
        "lon": 37.6200,
        "apartment": None,
        "entrance": None,
        "floor": None,
        "comment": None,
        "is_default": False,
    }
    defaults.update(overrides)
    row = DeliveryAddress(**defaults)
    db_session.add(row)
    db_session.flush()
    return row


def _committed_addresses_user(engine: Any) -> tuple[uuid.UUID, dict[str, str]]:
    """Creates and commits a customer in a standalone DB session."""
    from shared.models import User, UserProfile

    with Session(engine) as session:
        user = User(phone_hash=uuid.uuid4().hex[:32])
        session.add(user)
        session.flush()
        session.add(
            UserProfile(
                user_id=user.id,
                phone=b"test-phone-bytes",
                display_name="Test Customer",
                preferred_language="ru",
            )
        )
        _seed_shop_settings(session)
        user_id = user.id
        session.commit()

    return user_id, _auth_header("customer", user_id)


def _cleanup_committed_user(engine: Any, user_id: uuid.UUID) -> None:
    from sqlalchemy import delete
    from shared.models import DeliveryAddress, User, UserProfile

    with Session(engine) as session:
        session.execute(delete(DeliveryAddress).where(DeliveryAddress.user_id == user_id))
        session.execute(delete(UserProfile).where(UserProfile.user_id == user_id))
        session.execute(delete(User).where(User.id == user_id))
        session.commit()


# ===========================================================================
# 2. RED: модель DeliveryAddress в shared
# ===========================================================================


def test_delivery_address_model_importable() -> None:
    """shared.models.DeliveryAddress — SQLAlchemy-модель с нужными колонками."""
    from shared.models import DeliveryAddress

    assert DeliveryAddress.__tablename__ == "delivery_addresses"
    cols = set(DeliveryAddress.__table__.columns.keys())
    expected = {
        "id",
        "user_id",
        "label",
        "address_text",
        "lat",
        "lon",
        "apartment",
        "entrance",
        "floor",
        "comment",
        "is_default",
        "created_at",
        "updated_at",
    }
    assert expected <= cols, f"Missing columns: {expected - cols}"


def test_delivery_address_model_has_user_cascade_delete() -> None:
    """INV-013: FK user_id → users.id с ON DELETE CASCADE."""
    from shared.models import DeliveryAddress

    user_col = DeliveryAddress.__table__.c.user_id
    fks = list(user_col.foreign_keys)
    assert len(fks) == 1, f"user_id должен иметь ровно один FK, найдено {len(fks)}"
    assert fks[0].ondelete == "CASCADE", (
        f"FK user_id должен быть ON DELETE CASCADE, сейчас {fks[0].ondelete!r}"
    )


def test_delivery_address_has_partial_unique_default_index() -> None:
    """Partial unique index (user_id) WHERE is_default=true."""
    from shared.models import DeliveryAddress

    indexes = list(DeliveryAddress.__table__.indexes)
    partial_unique = [
        ix
        for ix in indexes
        if ix.unique and (ix.dialect_options.get("postgresql", {}).get("where") is not None)
    ]
    assert partial_unique, (
        "Ожидается хотя бы один unique-индекс с postgresql_where (partial)"
    )


# ===========================================================================
# 3. RED: монтирование роутера и RBAC matrix
# ===========================================================================


def test_delivery_addresses_router_is_mounted() -> None:
    """GET/POST на /api/v1/profile/addresses и PATCH/DELETE на /{address_id}."""
    with _patch_jwt():
        resp = client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]

    list_path = paths.get("/api/v1/profile/addresses", {})
    assert "get" in list_path, "GET /api/v1/profile/addresses не смонтирован"
    assert "post" in list_path, "POST /api/v1/profile/addresses не смонтирован"

    detail_path = paths.get("/api/v1/profile/addresses/{address_id}", {})
    assert "patch" in detail_path, "PATCH /api/v1/profile/addresses/{address_id} не смонтирован"
    assert "delete" in detail_path, "DELETE /api/v1/profile/addresses/{address_id} не смонтирован"


def test_delivery_addresses_rbac_matrix_entries() -> None:
    """Четыре записи в ROUTE_MATRIX со значением {CUSTOMER}."""
    from core_api.rbac_matrix import CUSTOMER, ROUTE_MATRIX

    expected = {
        ("GET", "/api/v1/profile/addresses"),
        ("POST", "/api/v1/profile/addresses"),
        ("PATCH", "/api/v1/profile/addresses/{address_id}"),
        ("DELETE", "/api/v1/profile/addresses/{address_id}"),
    }
    for key in expected:
        assert key in ROUTE_MATRIX, f"Запись {key} отсутствует в ROUTE_MATRIX"
        assert ROUTE_MATRIX[key] == {CUSTOMER}, (
            f"Роли для {key} должны быть {{CUSTOMER}}, сейчас {ROUTE_MATRIX[key]}"
        )


def test_delivery_addresses_not_in_public_routes() -> None:
    """Маршруты адресов НЕ должны попасть в PUBLIC_ROUTES (регрессия)."""
    from core_api.rbac_matrix import PUBLIC_ROUTES

    forbidden = {
        ("GET", "/api/v1/profile/addresses"),
        ("POST", "/api/v1/profile/addresses"),
        ("PATCH", "/api/v1/profile/addresses/{address_id}"),
        ("DELETE", "/api/v1/profile/addresses/{address_id}"),
    }
    leaked = forbidden & PUBLIC_ROUTES
    assert not leaked, f"Маршруты адресов не должны быть публичными: {leaked}"


# ===========================================================================
# 4. RED: аутентификация и ролевые гейты
# ===========================================================================


def test_list_addresses_requires_auth() -> None:
    resp = client.get("/api/v1/profile/addresses")
    assert resp.status_code == 401


def test_list_addresses_forbidden_for_staff() -> None:
    with _patch_jwt():
        for role in ("barista", "admin", "courier"):
            resp = client.get("/api/v1/profile/addresses", headers=_auth_header(role))
            assert resp.status_code == 403, f"Роль {role}: ожидался 403, получено {resp.status_code}"


def test_create_address_requires_auth() -> None:
    resp = client.post(
        "/api/v1/profile/addresses",
        json={"label": "Дом", "address_text": "X", "lat": 55.76, "lon": 37.62},
    )
    assert resp.status_code == 401


def test_create_address_forbidden_for_staff() -> None:
    with _patch_jwt():
        resp = client.post(
            "/api/v1/profile/addresses",
            json={"label": "Дом", "address_text": "X", "lat": 55.76, "lon": 37.62},
            headers=_auth_header("barista"),
        )
    assert resp.status_code == 403


def test_patch_address_requires_auth() -> None:
    resp = client.patch(
        f"/api/v1/profile/addresses/{uuid.uuid4()}",
        json={"label": "Work"},
    )
    assert resp.status_code == 401


def test_patch_address_forbidden_for_staff() -> None:
    with _patch_jwt():
        resp = client.patch(
            f"/api/v1/profile/addresses/{uuid.uuid4()}",
            json={"label": "Work"},
            headers=_auth_header("admin"),
        )
    assert resp.status_code == 403


def test_delete_address_requires_auth() -> None:
    resp = client.delete(f"/api/v1/profile/addresses/{uuid.uuid4()}")
    assert resp.status_code == 401


def test_delete_address_forbidden_for_staff() -> None:
    with _patch_jwt():
        resp = client.delete(
            f"/api/v1/profile/addresses/{uuid.uuid4()}",
            headers=_auth_header("courier"),
        )
    assert resp.status_code == 403


# ===========================================================================
# 5. RED: GET list
# ===========================================================================


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (JSONB, partial index, FK)")
def test_list_addresses_empty_returns_200_with_empty_list(db_client, _addresses_user) -> None:
    _, headers = _addresses_user
    with _patch_jwt():
        resp = db_client.get("/api/v1/profile/addresses", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_list_addresses_returns_own_rows_only(db_client, db_session, _addresses_user) -> None:
    user_a, headers = _addresses_user

    from shared.models import User, UserProfile

    user_b = User(phone_hash=uuid.uuid4().hex[:32])
    db_session.add(user_b)
    db_session.flush()
    db_session.add(UserProfile(user_id=user_b.id, phone=b"b", preferred_language="ru"))
    db_session.flush()

    a1 = _saved_address(db_session, user_a, label="A1")
    a2 = _saved_address(db_session, user_a, label="A2")
    _saved_address(db_session, user_b.id, label="B1")
    db_session.flush()

    with _patch_jwt():
        resp = db_client.get("/api/v1/profile/addresses", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    returned_ids = {item["id"] for item in body}
    assert returned_ids == {str(a1.id), str(a2.id)}


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_list_addresses_default_first_then_created_asc(db_client, db_session, _addresses_user) -> None:
    user_a, headers = _addresses_user

    _saved_address(db_session, user_a, label="Первый")
    _saved_address(db_session, user_a, label="Второй")
    default_row = _saved_address(db_session, user_a, label="Дефолт", is_default=True)
    db_session.flush()

    with _patch_jwt():
        resp = db_client.get("/api/v1/profile/addresses", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 3
    assert body[0]["id"] == str(default_row.id), (
        f"Default-адрес должен идти первым, получено {body[0]}"
    )


# ===========================================================================
# 6. RED: POST create
# ===========================================================================


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_address_happy_path_returns_201(db_client, db_session, _addresses_user) -> None:
    _, headers = _addresses_user
    body = {
        "label": "Дом",
        "address_text": "Москва, Тверская 1",
        "lat": 55.7600,
        "lon": 37.6200,
    }
    with _patch_jwt():
        resp = db_client.post("/api/v1/profile/addresses", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    for field in ("id", "label", "address_text", "lat", "lon", "is_default"):
        assert field in data
    uuid.UUID(data["id"])
    assert data["label"] == "Дом"

    from shared.models import DeliveryAddress

    row = db_session.get(DeliveryAddress, uuid.UUID(data["id"]))
    assert row is not None


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_address_rejects_out_of_radius_with_422(db_client, db_session, _addresses_user) -> None:
    _, headers = _addresses_user
    body = {
        "label": "Далеко",
        "address_text": "Экватор",
        "lat": 0.0,
        "lon": 0.0,
    }
    with _patch_jwt():
        resp = db_client.post("/api/v1/profile/addresses", json=body, headers=headers)
    assert resp.status_code == 422, resp.text

    from shared.models import DeliveryAddress

    count = db_session.query(DeliveryAddress).count()
    assert count == 0, "Строка не должна создаваться при out-of-radius"


def test_create_address_rejects_missing_fields_with_422() -> None:
    with _patch_jwt():
        resp = client.post(
            "/api/v1/profile/addresses",
            json={"label": "Дом", "address_text": "X", "lon": 37.62},
            headers=_auth_header("customer"),
        )
    assert resp.status_code == 422


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_address_persists_optional_fields(db_client, db_session, _addresses_user) -> None:
    _, headers = _addresses_user
    body = {
        "label": "Дом",
        "address_text": "Москва, Тверская 1",
        "lat": 55.7600,
        "lon": 37.6200,
        "apartment": "12",
        "entrance": "2",
        "floor": "3",
        "comment": "код 1234",
    }
    with _patch_jwt():
        resp = db_client.post("/api/v1/profile/addresses", json=body, headers=headers)
    assert resp.status_code == 201
    data = resp.json()

    from shared.models import DeliveryAddress

    row = db_session.get(DeliveryAddress, uuid.UUID(data["id"]))
    assert row is not None
    assert row.apartment == "12"
    assert row.entrance == "2"
    assert row.floor == "3"
    assert row.comment == "код 1234"


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_address_first_for_user_not_automatically_default(db_client, _addresses_user) -> None:
    _, headers = _addresses_user
    body = {
        "label": "Дом",
        "address_text": "Тверская 1",
        "lat": 55.7600,
        "lon": 37.6200,
    }
    with _patch_jwt():
        resp = db_client.post("/api/v1/profile/addresses", json=body, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["is_default"] is False


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_address_with_is_default_true_persists_flag(db_client, db_session, _addresses_user) -> None:
    _, headers = _addresses_user
    body = {
        "label": "Дом",
        "address_text": "Тверская 1",
        "lat": 55.7600,
        "lon": 37.6200,
        "is_default": True,
    }
    with _patch_jwt():
        resp = db_client.post("/api/v1/profile/addresses", json=body, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["is_default"] is True

    from shared.models import DeliveryAddress

    row = db_session.get(DeliveryAddress, uuid.UUID(data["id"]))
    assert row is not None
    assert row.is_default is True


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_address_commits_visible_to_new_session(_pg_db_override) -> None:
    engine = _pg_db_override
    user_id, headers = _committed_addresses_user(engine)
    try:
        body = {
            "label": "Работа",
            "address_text": "Москва, ул. Льва Толстого, 16",
            "lat": 55.733,
            "lon": 37.588,
        }
        with _patch_jwt(), TestClient(app) as c:
            resp = c.post("/api/v1/profile/addresses", json=body, headers=headers)
        assert resp.status_code == 201, resp.text
        row_id = uuid.UUID(resp.json()["id"])

        from shared.models import DeliveryAddress

        with Session(engine) as session:
            row = session.get(DeliveryAddress, row_id)
            assert row is not None
            assert row.user_id == user_id
            assert row.label == "Работа"
    finally:
        _cleanup_committed_user(engine, user_id)


# ===========================================================================
# 7. RED: PATCH update
# ===========================================================================


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_patch_address_updates_label(db_client, db_session, _addresses_user) -> None:
    user_a, headers = _addresses_user
    row = _saved_address(db_session, user_a, label="Старое")
    db_session.flush()

    with _patch_jwt():
        resp = db_client.patch(
            f"/api/v1/profile/addresses/{row.id}",
            json={"label": "Дача"},
            headers=headers,
        )
    assert resp.status_code == 200
    db_session.refresh(row)
    assert row.label == "Дача"


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_patch_address_updates_optional_fields(db_client, db_session, _addresses_user) -> None:
    user_a, headers = _addresses_user
    row = _saved_address(db_session, user_a, apartment="1", entrance="A", floor="5")
    db_session.flush()

    with _patch_jwt():
        resp = db_client.patch(
            f"/api/v1/profile/addresses/{row.id}",
            json={"apartment": "42", "entrance": None},
            headers=headers,
        )
    assert resp.status_code == 200
    db_session.refresh(row)
    assert row.apartment == "42"
    assert row.entrance is None


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_patch_is_default_true_demotes_previous_default(db_client, db_session, _addresses_user) -> None:
    user_a, headers = _addresses_user
    row_x = _saved_address(db_session, user_a, label="X", is_default=True)
    row_y = _saved_address(db_session, user_a, label="Y", is_default=False)
    db_session.flush()

    with _patch_jwt():
        resp = db_client.patch(
            f"/api/v1/profile/addresses/{row_y.id}",
            json={"is_default": True},
            headers=headers,
        )
    assert resp.status_code == 200

    db_session.expire_all()
    from shared.models import DeliveryAddress

    x_fresh = db_session.get(DeliveryAddress, row_x.id)
    y_fresh = db_session.get(DeliveryAddress, row_y.id)
    assert x_fresh.is_default is False
    assert y_fresh.is_default is True

    count = (
        db_session.query(DeliveryAddress)
        .filter(DeliveryAddress.user_id == user_a, DeliveryAddress.is_default.is_(True))
        .count()
    )
    assert count == 1, f"Ровно один default должен остаться, найдено {count}"


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_patch_is_default_false_does_not_touch_other_rows(db_client, db_session, _addresses_user) -> None:
    user_a, headers = _addresses_user
    row_x = _saved_address(db_session, user_a, label="X", is_default=True)
    row_y = _saved_address(db_session, user_a, label="Y", is_default=False)
    db_session.flush()

    with _patch_jwt():
        resp = db_client.patch(
            f"/api/v1/profile/addresses/{row_x.id}",
            json={"is_default": False},
            headers=headers,
        )
    assert resp.status_code == 200
    db_session.refresh(row_x)
    db_session.refresh(row_y)
    assert row_x.is_default is False
    assert row_y.is_default is False


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_patch_foreign_address_returns_404(db_client, db_session, _addresses_user) -> None:
    user_a, headers = _addresses_user

    from shared.models import User, UserProfile

    user_b = User(phone_hash=uuid.uuid4().hex[:32])
    db_session.add(user_b)
    db_session.flush()
    db_session.add(UserProfile(user_id=user_b.id, phone=b"b", preferred_language="ru"))
    row_z = _saved_address(db_session, user_b.id, label="Чужой")
    db_session.flush()

    with _patch_jwt():
        resp = db_client.patch(
            f"/api/v1/profile/addresses/{row_z.id}",
            json={"label": "hack"},
            headers=headers,
        )
    assert resp.status_code == 404

    db_session.refresh(row_z)
    assert row_z.label == "Чужой", "Чужая строка не должна мутироваться"


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_patch_unknown_address_returns_404(db_client, _addresses_user) -> None:
    _, headers = _addresses_user
    with _patch_jwt():
        resp = db_client.patch(
            f"/api/v1/profile/addresses/{uuid.uuid4()}",
            json={"label": "nope"},
            headers=headers,
        )
    assert resp.status_code == 404


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_patch_returns_updated_body(db_client, db_session, _addresses_user) -> None:
    user_a, headers = _addresses_user
    row = _saved_address(db_session, user_a, label="Старое")
    db_session.flush()

    with _patch_jwt():
        resp = db_client.patch(
            f"/api/v1/profile/addresses/{row.id}",
            json={"label": "Новое"},
            headers=headers,
        )
    assert resp.status_code == 200
    assert resp.json()["label"] == "Новое"


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_patch_address_commits_visible_to_new_session(_pg_db_override) -> None:
    engine = _pg_db_override
    user_id, headers = _committed_addresses_user(engine)
    try:
        from shared.models import DeliveryAddress

        with Session(engine) as session:
            row = DeliveryAddress(
                user_id=user_id,
                label="Старое",
                address_text="Москва, Тверская 1",
                lat=55.7600,
                lon=37.6200,
            )
            session.add(row)
            session.commit()
            row_id = row.id

        with _patch_jwt(), TestClient(app) as c:
            resp = c.patch(
                f"/api/v1/profile/addresses/{row_id}",
                json={"label": "Новое", "apartment": "42"},
                headers=headers,
            )
        assert resp.status_code == 200, resp.text

        with Session(engine) as session:
            fresh = session.get(DeliveryAddress, row_id)
            assert fresh is not None
            assert fresh.label == "Новое"
            assert fresh.apartment == "42"
    finally:
        _cleanup_committed_user(engine, user_id)


# ===========================================================================
# 8. RED: DELETE remove
# ===========================================================================


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_delete_own_address_returns_204(db_client, db_session, _addresses_user) -> None:
    user_a, headers = _addresses_user
    row = _saved_address(db_session, user_a)
    row_id = row.id
    db_session.flush()

    with _patch_jwt():
        resp = db_client.delete(f"/api/v1/profile/addresses/{row_id}", headers=headers)
    assert resp.status_code == 204
    assert resp.content in (b"", b"null")

    from shared.models import DeliveryAddress

    assert db_session.get(DeliveryAddress, row_id) is None


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_delete_address_commits_visible_to_new_session(_pg_db_override) -> None:
    engine = _pg_db_override
    user_id, headers = _committed_addresses_user(engine)
    try:
        from shared.models import DeliveryAddress

        with Session(engine) as session:
            row = DeliveryAddress(
                user_id=user_id,
                label="Удалить",
                address_text="Москва, Тверская 1",
                lat=55.7600,
                lon=37.6200,
            )
            session.add(row)
            session.commit()
            row_id = row.id

        with _patch_jwt(), TestClient(app) as c:
            resp = c.delete(f"/api/v1/profile/addresses/{row_id}", headers=headers)
        assert resp.status_code == 204, resp.text

        with Session(engine) as session:
            assert session.get(DeliveryAddress, row_id) is None
    finally:
        _cleanup_committed_user(engine, user_id)


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_delete_foreign_address_returns_404_and_row_persists(db_client, db_session, _addresses_user) -> None:
    _, headers = _addresses_user

    from shared.models import DeliveryAddress, User, UserProfile

    user_b = User(phone_hash=uuid.uuid4().hex[:32])
    db_session.add(user_b)
    db_session.flush()
    db_session.add(UserProfile(user_id=user_b.id, phone=b"b", preferred_language="ru"))
    row_z = _saved_address(db_session, user_b.id)
    row_z_id = row_z.id
    db_session.flush()

    with _patch_jwt():
        resp = db_client.delete(f"/api/v1/profile/addresses/{row_z_id}", headers=headers)
    assert resp.status_code == 404

    assert db_session.get(DeliveryAddress, row_z_id) is not None


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_delete_unknown_address_returns_404(db_client, _addresses_user) -> None:
    _, headers = _addresses_user
    with _patch_jwt():
        resp = db_client.delete(
            f"/api/v1/profile/addresses/{uuid.uuid4()}",
            headers=headers,
        )
    assert resp.status_code == 404


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_delete_does_not_mutate_past_order_snapshot(db_client, db_session, _addresses_user) -> None:
    """INV-014: удаление сохранённого адреса НЕ меняет orders.delivery_address_snapshot."""
    import copy

    from shared.enums import OrderStatus, OrderType
    from shared.models import DeliveryAddress, Order

    user_a, headers = _addresses_user
    row_w = _saved_address(
        db_session,
        user_a,
        label="W",
        apartment="12",
        entrance="2",
    )
    db_session.flush()

    snapshot = {
        "text": row_w.address_text,
        "lat": float(row_w.lat),
        "lon": float(row_w.lon),
        "apartment": row_w.apartment,
        "entrance": row_w.entrance,
    }
    order = Order(
        user_id=user_a,
        status=OrderStatus.CREATED,
        type=OrderType.DELIVERY,
        delivery_address_snapshot=copy.deepcopy(snapshot),
        subtotal=50000,
        discount_amount=0,
        points_used=0,
        delivery_fee=15000,
        total=65000,
        estimated_accrual=3000,
    )
    db_session.add(order)
    db_session.flush()
    order_id = order.id

    with _patch_jwt():
        resp = db_client.delete(f"/api/v1/profile/addresses/{row_w.id}", headers=headers)
    assert resp.status_code == 204
    assert db_session.get(DeliveryAddress, row_w.id) is None

    db_session.expire_all()
    order_after = db_session.get(Order, order_id)
    assert order_after is not None
    assert order_after.delivery_address_snapshot == snapshot, (
        "orders.delivery_address_snapshot не должен меняться при удалении адреса (INV-014)"
    )
