"""RED: тесты HTTP-эндпоинтов корзины (section 8).

Все тесты ДОЛЖНЫ падать до добавления операций в routers/cart.py.
Тесты с реальной БД пропускаются без TEST_DATABASE_URL.
"""
from __future__ import annotations

import uuid
from unittest.mock import patch

import fakeredis
import pytest
from fastapi.testclient import TestClient

from tests.conftest import _TEST_DB_URL as TEST_DB_URL

_IS_SQLITE = TEST_DB_URL.startswith("sqlite")

# JWT-секрет из conftest.py
_JWT_SECRET = "test-secret"


def _make_token(role: str = "customer", user_id: uuid.UUID | None = None) -> str:
    """Создаёт JWT-токен с нужной ролью, используя test-secret из conftest."""
    from core_api.services.auth import AuthService

    uid = user_id or uuid.uuid4()
    with patch("core_api.services.auth.settings") as mock_settings:
        mock_settings.jwt_secret_key = _JWT_SECRET
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.access_token_ttl = 900
        svc = AuthService.__new__(AuthService)
        return svc.create_access_token(uid, role)


def _auth(role: str = "customer", user_id: uuid.UUID | None = None) -> dict[str, str]:
    return {"Authorization": f"Bearer {_make_token(role, user_id)}"}


def _patch_jwt():
    """Патч JWT-настроек для RBAC middleware."""
    return patch("core_api.services.auth.settings", **{
        "jwt_secret_key": _JWT_SECRET,
        "jwt_algorithm": "HS256",
        "access_token_ttl": 900,
    })


@pytest.fixture
def client(cart_redis):
    """TestClient с fakeredis, подменённым в deps.redis."""
    from core_api.main import app

    def _override():
        yield cart_redis

    with patch("core_api.deps.redis.get_redis", side_effect=_override):
        with TestClient(app) as c:
            yield c


@pytest.fixture
def db_client(cart_redis, db_session):
    """TestClient с fakeredis + реальной DB-сессией."""
    from core_api.main import app

    def _override_redis():
        yield cart_redis

    def _override_db():
        yield db_session

    with (
        patch("core_api.deps.redis.get_redis", side_effect=_override_redis),
        patch("core_api.deps.database.get_session", side_effect=_override_db),
    ):
        with TestClient(app) as c:
            yield c


# ===========================================================================
# 8.1 OpenAPI: пять операций должны появиться в /openapi.json
# ===========================================================================

def test_cart_router_now_has_five_operations(client) -> None:
    """Роутер корзины должен иметь 5 операций в OpenAPI."""
    with _patch_jwt():
        resp = client.get("/openapi.json")

    assert resp.status_code == 200
    paths = resp.json()["paths"]

    assert "get" in paths.get("/api/v1/cart", {}), "GET /api/v1/cart отсутствует"
    assert "delete" in paths.get("/api/v1/cart", {}), "DELETE /api/v1/cart отсутствует"
    assert "post" in paths.get("/api/v1/cart/items", {}), "POST /api/v1/cart/items отсутствует"
    assert "patch" in paths.get("/api/v1/cart/items/{line_id}", {}), (
        "PATCH /api/v1/cart/items/{line_id} отсутствует"
    )
    assert "delete" in paths.get("/api/v1/cart/items/{line_id}", {}), (
        "DELETE /api/v1/cart/items/{line_id} отсутствует"
    )


# ===========================================================================
# 8.2-8.3 Аутентификация и авторизация
# ===========================================================================

def test_get_cart_requires_auth(client) -> None:
    """GET /api/v1/cart без JWT → 401."""
    with _patch_jwt():
        resp = client.get("/api/v1/cart")
    assert resp.status_code == 401


def test_get_cart_forbidden_for_staff(client) -> None:
    """GET /api/v1/cart с ролью barista → 403."""
    with _patch_jwt():
        resp = client.get("/api/v1/cart", headers=_auth("barista"))
    assert resp.status_code == 403


# ===========================================================================
# 8.4 GET пустая корзина
# ===========================================================================

def test_get_cart_returns_empty_for_fresh_customer(client) -> None:
    """GET /api/v1/cart для нового клиента → 200, items=[], subtotal=0."""
    with _patch_jwt():
        resp = client.get("/api/v1/cart", headers=_auth("customer"))

    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["subtotal"] == 0
    assert data["currency"] == "RUB"


# ===========================================================================
# 8.5-8.9 POST /api/v1/cart/items
# ===========================================================================

def test_post_cart_item_creates_line_and_returns_full_cart(db_client, db_session) -> None:
    """POST добавляет строку и возвращает CartResponse с line_id и ценой."""
    from tests._factories.menu import make_menu_item

    item = make_menu_item(db_session, base_price=15000)
    db_session.flush()

    with _patch_jwt():
        resp = db_client.post(
            "/api/v1/cart/items",
            json={"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 2},
            headers=_auth("customer"),
        )

    assert resp.status_code in (200, 201)
    data = resp.json()
    assert len(data["items"]) == 1
    line = data["items"][0]
    assert "line_id" in line
    assert len(line["line_id"]) == 16
    assert line["unit_price"] == 15000
    assert line["line_total"] == 30000


def test_post_cart_item_rejects_stop_listed_with_409(db_client, db_session) -> None:
    """POST с недоступным товаром → 409."""
    from tests._factories.menu import make_menu_item

    item = make_menu_item(db_session, available=False)
    db_session.flush()

    with _patch_jwt():
        resp = db_client.post(
            "/api/v1/cart/items",
            json={"menu_item_id": item.id, "quantity": 1},
            headers=_auth("customer"),
        )

    assert resp.status_code == 409
    assert "detail" in resp.json()


def test_post_cart_item_merges_same_line(db_client, db_session) -> None:
    """POST одной и той же позиции дважды → одна строка с суммарным quantity."""
    from tests._factories.menu import make_menu_item

    item = make_menu_item(db_session, base_price=15000)
    db_session.flush()

    payload = {"menu_item_id": item.id, "quantity": 2}
    headers = _auth("customer", uuid.uuid4())
    with _patch_jwt():
        db_client.post("/api/v1/cart/items", json=payload, headers=headers)
        resp = db_client.post("/api/v1/cart/items", json=payload, headers=headers)

    assert resp.status_code in (200, 201)
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["quantity"] == 4


def test_post_cart_item_merge_cap_409(db_client, db_session, cart_redis) -> None:
    """POST с quantity, превышающим лимит 99 → 409."""
    import json as _json
    from datetime import datetime, timezone
    from tests._factories.menu import make_menu_item

    item = make_menu_item(db_session, base_price=15000)
    db_session.flush()

    # Вставляем строку с quantity=95 прямо в Redis
    # Нужен тот же user_id, который используется в запросе — определяем из токена
    payload = _json.dumps({
        "items": [{"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 95}],
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    })

    with _patch_jwt():
        # Делаем первый запрос чтобы определить user_id из токена
        uid = uuid.uuid4()
        token = _make_token("customer", uid)
        cart_redis.set(f"cart:{uid}", payload, ex=300)

        resp = db_client.post(
            "/api/v1/cart/items",
            json={"menu_item_id": item.id, "quantity": 10},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 409


def test_post_cart_item_unknown_menu_item_404(db_client) -> None:
    """POST с несуществующим menu_item_id → 404."""
    with _patch_jwt():
        resp = db_client.post(
            "/api/v1/cart/items",
            json={"menu_item_id": 999999, "quantity": 1},
            headers=_auth("customer"),
        )

    assert resp.status_code == 404


# ===========================================================================
# 8.10-8.11 PATCH /api/v1/cart/items/{line_id}
# ===========================================================================

def test_patch_cart_item_updates_quantity(db_client, db_session) -> None:
    """PATCH обновляет quantity строки."""
    from tests._factories.menu import make_menu_item

    item = make_menu_item(db_session, base_price=15000)
    db_session.flush()

    headers = _auth("customer", uuid.uuid4())
    with _patch_jwt():
        r = db_client.post(
            "/api/v1/cart/items",
            json={"menu_item_id": item.id, "quantity": 2},
            headers=headers,
        )
        line_id = r.json()["items"][0]["line_id"]

        resp = db_client.patch(
            f"/api/v1/cart/items/{line_id}",
            json={"menu_item_id": item.id, "quantity": 4},
            headers=headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["items"][0]["quantity"] == 4


def test_patch_cart_item_unknown_line_id_404(db_client, db_session) -> None:
    """PATCH несуществующего line_id → 404."""
    from tests._factories.menu import make_menu_item

    item = make_menu_item(db_session, base_price=15000)
    db_session.flush()

    with _patch_jwt():
        resp = db_client.patch(
            "/api/v1/cart/items/deadbeefdeadbeef",
            json={"menu_item_id": item.id, "quantity": 1},
            headers=_auth("customer"),
        )

    assert resp.status_code == 404


# ===========================================================================
# 8.12-8.13 DELETE /api/v1/cart/items/{line_id}
# ===========================================================================

def test_delete_cart_item_removes_line(db_client, db_session) -> None:
    """DELETE /cart/items/{line_id} удаляет одну строку."""
    from tests._factories.menu import make_menu_item

    item1 = make_menu_item(db_session, name_ru="А", name_en="A", base_price=15000)
    item2 = make_menu_item(db_session, name_ru="Б", name_en="B", base_price=17000)
    db_session.flush()

    headers = _auth("customer", uuid.uuid4())
    with _patch_jwt():
        r1 = db_client.post("/api/v1/cart/items", json={"menu_item_id": item1.id, "quantity": 1}, headers=headers)
        db_client.post("/api/v1/cart/items", json={"menu_item_id": item2.id, "quantity": 1}, headers=headers)
        line_id = r1.json()["items"][0]["line_id"]

        resp = db_client.delete(f"/api/v1/cart/items/{line_id}", headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["menu_item_id"] == item2.id


def test_delete_cart_item_unknown_line_id_404(db_client, db_session) -> None:
    """DELETE несуществующего line_id → 404."""
    from tests._factories.menu import make_menu_item

    item = make_menu_item(db_session, base_price=15000)
    db_session.flush()
    headers = _auth("customer", uuid.uuid4())
    db_client.post("/api/v1/cart/items", json={"menu_item_id": item.id, "quantity": 1}, headers=headers)

    with _patch_jwt():
        resp = db_client.delete("/api/v1/cart/items/deadbeefdeadbeef", headers=headers)

    assert resp.status_code == 404


# ===========================================================================
# 8.14-8.15 DELETE /api/v1/cart
# ===========================================================================

def test_delete_cart_clears_all(db_client, db_session) -> None:
    """DELETE /api/v1/cart очищает корзину; следующий GET возвращает пустоту."""
    from tests._factories.menu import make_menu_item

    item1 = make_menu_item(db_session, name_ru="А", name_en="A", base_price=15000)
    item2 = make_menu_item(db_session, name_ru="Б", name_en="B", base_price=17000)
    db_session.flush()

    headers = _auth("customer", uuid.uuid4())
    with _patch_jwt():
        db_client.post("/api/v1/cart/items", json={"menu_item_id": item1.id, "quantity": 1}, headers=headers)
        db_client.post("/api/v1/cart/items", json={"menu_item_id": item2.id, "quantity": 1}, headers=headers)

        resp = db_client.delete("/api/v1/cart", headers=headers)
        assert resp.status_code == 200

        get_resp = db_client.get("/api/v1/cart", headers=headers)

    assert get_resp.json()["items"] == []


def test_delete_cart_idempotent_on_empty(client) -> None:
    """DELETE /api/v1/cart на пустой корзине → 200, пустая CartResponse."""
    with _patch_jwt():
        resp = client.delete("/api/v1/cart", headers=_auth("customer"))

    assert resp.status_code == 200
    assert resp.json()["items"] == []
    assert resp.json()["subtotal"] == 0


# ===========================================================================
# 8.16 TTL из settings
# ===========================================================================

def test_cart_ttl_env_override_respected(db_client, db_session, cart_redis) -> None:
    """CART_TTL_SECONDS monkeypatch применяется при записи в Redis."""
    from tests._factories.menu import make_menu_item

    item = make_menu_item(db_session, base_price=15000)
    db_session.flush()

    uid = uuid.uuid4()
    token = _make_token("customer", uid)

    with (
        _patch_jwt(),
        patch("core_api.routers.cart.settings") as mock_s,
    ):
        mock_s.cart_ttl_seconds = 60

        resp = db_client.post(
            "/api/v1/cart/items",
            json={"menu_item_id": item.id, "quantity": 1},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code in (200, 201)
    ttl = cart_redis.ttl(f"cart:{uid}")
    assert 0 < ttl <= 60, f"TTL должен быть ≤60, получено {ttl}"
