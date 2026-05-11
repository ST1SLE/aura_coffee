"""RED: контракт HTTP-маршрутов заказов (Phase 3, §7.1 item 2).

POST /api/v1/orders — создаёт заказ из корзины (201 / 400 / 409 / 422 / 401 / 403).
GET  /api/v1/orders/{order_id} — детали заказа для polling confirmation_url
                                 (200 / 404 foreign-or-unknown / 401 / 403).

Все тесты ДОЛЖНЫ падать в RED с 404/AssertionError / ImportError до
регистрации core_api.routers.orders в main.py и добавления записей в
ROUTE_MATRIX.
"""
from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import patch

import fakeredis
import pytest
from fastapi.testclient import TestClient

from tests.conftest import _TEST_DB_URL as TEST_DB_URL

_IS_SQLITE = TEST_DB_URL.startswith("sqlite")

# JWT-секрет из conftest.py (совпадает с env JWT_SECRET_KEY), длина >=32 байт.
_JWT_SECRET = "aura-coffee-tests-jwt-secret-0001"


def _make_token(role: str = "customer", user_id: uuid.UUID | None = None) -> str:
    """Создаёт JWT-токен нужной роли через AuthService (как в test_route_cart)."""
    from core_api.services.auth import AuthService

    uid = user_id or uuid.uuid4()
    with patch("core_api.services.auth.settings") as mock_settings:
        mock_settings.jwt_secret_key = _JWT_SECRET
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.access_token_ttl = 900
        svc = AuthService.__new__(AuthService)
        return svc.create_access_token(uid, role)


def _auth(role: str = "customer") -> dict[str, str]:
    return {"Authorization": f"Bearer {_make_token(role)}"}


@contextmanager
def _patch_jwt():
    """Патч JWT-настроек и synthetic-subject checks для route-contract тестов."""
    with (
        patch(
            "core_api.services.auth.settings",
            **{
                "jwt_secret_key": _JWT_SECRET,
                "jwt_algorithm": "HS256",
                "access_token_ttl": 900,
            },
        ),
        patch("core_api.middleware.rbac.is_subject_active", return_value=True),
        patch("core_api.deps.auth.is_subject_active", return_value=True),
    ):
        yield


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
    """TestClient с fakeredis + реальной DB-сессией (skip на SQLite через db_session)."""
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


def _seed_cart(cart_redis: fakeredis.FakeRedis, user_id: uuid.UUID, items: list[dict]) -> None:
    payload = {
        "items": items,
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    cart_redis.set(f"cart:{user_id}", json.dumps(payload), ex=300)


def _ensure_shop_settings(db_session) -> None:
    from shared.models.shop_settings import ShopSettings

    if db_session.get(ShopSettings, 1) is not None:
        return
    db_session.add(
        ShopSettings(
            id=1,
            shop_lat=55.751244,
            shop_lon=37.618423,
            delivery_radius_km=10,
            min_delivery_amount=0,
            free_delivery_threshold=100000,
            delivery_fee=0,
            loyalty_percent=5,
            default_prep_time_minutes=10,
            estimated_delivery_time_minutes=30,
            auto_close_minutes=60,
            ordering_paused=False,
            working_hours={},
        )
    )
    db_session.flush()


# ===========================================================================
# 11. RED: POST /api/v1/orders
# ===========================================================================


def test_orders_router_exposes_post(client) -> None:
    """POST /api/v1/orders должен присутствовать в /openapi.json."""
    with _patch_jwt():
        resp = client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    assert "post" in paths.get("/api/v1/orders", {}), "POST /api/v1/orders отсутствует"


def test_orders_router_exposes_estimate(client) -> None:
    """POST /api/v1/orders/estimate должен присутствовать в /openapi.json."""
    with _patch_jwt():
        resp = client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    assert "post" in paths.get("/api/v1/orders/estimate", {}), (
        "POST /api/v1/orders/estimate отсутствует"
    )


def test_post_orders_requires_auth(client) -> None:
    """POST /api/v1/orders без Authorization → 401."""
    with _patch_jwt():
        resp = client.post("/api/v1/orders", json={"type": "pickup"})
    assert resp.status_code == 401


def test_post_order_estimate_requires_auth(client) -> None:
    """POST /api/v1/orders/estimate без Authorization → 401."""
    with _patch_jwt():
        resp = client.post("/api/v1/orders/estimate", json={"type": "pickup"})
    assert resp.status_code == 401


def test_post_orders_forbidden_for_staff(client) -> None:
    """POST /api/v1/orders с ролью barista → 403."""
    with _patch_jwt():
        resp = client.post("/api/v1/orders", json={"type": "pickup"}, headers=_auth("barista"))
    assert resp.status_code == 403


def test_post_order_estimate_forbidden_for_staff(client) -> None:
    """POST /api/v1/orders/estimate с ролью barista → 403."""
    with _patch_jwt():
        resp = client.post(
            "/api/v1/orders/estimate",
            json={"type": "pickup"},
            headers=_auth("barista"),
        )
    assert resp.status_code == 403


def test_post_orders_forbidden_for_admin_and_courier(client) -> None:
    """POST /api/v1/orders для admin и courier → 403."""
    with _patch_jwt():
        r_admin = client.post("/api/v1/orders", json={"type": "pickup"}, headers=_auth("admin"))
        r_courier = client.post(
            "/api/v1/orders", json={"type": "pickup"}, headers=_auth("courier")
        )
    assert r_admin.status_code == 403
    assert r_courier.status_code == 403


def test_post_order_estimate_returns_server_totals(client) -> None:
    """Estimate route delegates to checkout service and returns its totals."""
    from core_api.schemas.order import OrderEstimateResponse

    with (
        _patch_jwt(),
        patch(
            "core_api.routers.orders.estimate_order",
            return_value=OrderEstimateResponse(
                subtotal=10000,
                discount_amount=1000,
                points_used=2000,
                delivery_fee=5000,
                total=12000,
                estimated_accrual=700,
                estimated_ready_at=None,
                loyalty_balance=3000,
                min_delivery_amount=0,
                free_delivery_threshold=50000,
                free_delivery_remaining=40000,
            ),
        ) as estimate_mock,
    ):
        resp = client.post(
            "/api/v1/orders/estimate",
            json={"type": "pickup", "points_to_use": 2000},
            headers=_auth("customer"),
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["subtotal"] == 10000
    assert body["total"] == 12000
    assert body["free_delivery_remaining"] == 40000
    estimate_mock.assert_called_once()


def test_post_order_estimate_minimum_delivery_error_is_structured(client) -> None:
    """Delivery minimum failure returns kopecks as data, not raw developer text."""
    from core_api.services.validators.exceptions import MinimumDeliveryAmountError

    with (
        _patch_jwt(),
        patch(
            "core_api.routers.orders.estimate_order",
            side_effect=MinimumDeliveryAmountError(
                subtotal=21000,
                min_amount=50000,
            ),
        ),
    ):
        resp = client.post(
            "/api/v1/orders/estimate",
            json={
                "type": "delivery",
                "delivery_address": {
                    "text": "Hidden user address",
                    "lat": 55.7558,
                    "lon": 37.6173,
                },
            },
            headers=_auth("customer"),
        )

    assert resp.status_code == 409
    assert resp.json()["detail"] == {
        "code": "minimum_delivery_amount",
        "subtotal": 21000,
        "min_delivery_amount": 50000,
    }
    assert "Hidden user address" not in resp.text


def test_post_order_estimate_ordering_paused_error_is_structured(client) -> None:
    """Estimate route reports operator pause without exposing checkout payload."""
    from core_api.services.checkout import OrderingPausedError

    with (
        _patch_jwt(),
        patch(
            "core_api.routers.orders.estimate_order",
            side_effect=OrderingPausedError("ordering_paused"),
        ),
    ):
        resp = client.post(
            "/api/v1/orders/estimate",
            json={
                "type": "delivery",
                "delivery_address": {
                    "text": "Hidden user address",
                    "lat": 55.7558,
                    "lon": 37.6173,
                },
            },
            headers=_auth("customer"),
        )

    assert resp.status_code == 409
    assert resp.json()["detail"] == {"code": "ordering_paused"}
    assert "Hidden user address" not in resp.text


def test_post_order_minimum_delivery_error_is_structured(client) -> None:
    """Order create route uses the same user-safe delivery minimum envelope."""
    from core_api.services.validators.exceptions import MinimumDeliveryAmountError

    with (
        _patch_jwt(),
        patch(
            "core_api.routers.orders.create_order",
            side_effect=MinimumDeliveryAmountError(
                subtotal=21000,
                min_amount=50000,
            ),
        ),
    ):
        resp = client.post(
            "/api/v1/orders",
            json={
                "type": "delivery",
                "delivery_address": {
                    "text": "Hidden user address",
                    "lat": 55.7558,
                    "lon": 37.6173,
                },
            },
            headers=_auth("customer"),
        )

    assert resp.status_code == 409
    assert resp.json()["detail"] == {
        "code": "minimum_delivery_amount",
        "subtotal": 21000,
        "min_delivery_amount": 50000,
    }
    assert "Hidden user address" not in resp.text


def test_post_order_ordering_paused_error_is_structured(client) -> None:
    """Order create route reports operator pause as a stable structured 409."""
    from core_api.services.checkout import OrderingPausedError

    with (
        _patch_jwt(),
        patch(
            "core_api.routers.orders.create_order",
            side_effect=OrderingPausedError("ordering_paused"),
        ),
    ):
        resp = client.post(
            "/api/v1/orders",
            json={
                "type": "delivery",
                "delivery_address": {
                    "text": "Hidden user address",
                    "lat": 55.7558,
                    "lon": 37.6173,
                },
            },
            headers=_auth("customer"),
        )

    assert resp.status_code == 409
    assert resp.json()["detail"] == {"code": "ordering_paused"}
    assert "Hidden user address" not in resp.text


def test_post_orders_empty_cart_returns_400(client, cart_redis) -> None:
    """Customer без корзины в Redis → 400."""
    uid = uuid.uuid4()
    token = _make_token("customer", uid)
    with _patch_jwt():
        resp = client.post(
            "/api/v1/orders",
            json={"type": "pickup"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 400


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_post_orders_happy_path_returns_201(db_client, db_session, cart_redis) -> None:
    """Корзина → 201 с OrderResponse(status=created, id=UUID)."""
    from tests._factories.menu import make_menu_item

    from shared.models import LoyaltyAccount, User, UserProfile

    _ensure_shop_settings(db_session)
    user = User(phone_hash=uuid.uuid4().hex[:32])
    db_session.add(user)
    db_session.flush()
    db_session.add(
        UserProfile(
            user_id=user.id, phone=b"test-phone-bytes", display_name="Test", preferred_language="ru"
        )
    )
    db_session.add(LoyaltyAccount(user_id=user.id, balance=0))
    db_session.flush()

    item = make_menu_item(db_session, base_price=15000)
    db_session.flush()

    _seed_cart(
        cart_redis,
        user.id,
        [{"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 1}],
    )

    token = _make_token("customer", user.id)

    with (
        _patch_jwt(),
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.validate_promocode", return_value=None),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        resp = db_client.post(
            "/api/v1/orders",
            json={"type": "pickup"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "created"
    # id должен парситься как UUID
    uuid.UUID(body["id"])


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_post_orders_validator_failure_returns_409(db_client, db_session, cart_redis) -> None:
    """validate_stop_list бросает → 409."""
    from tests._factories.menu import make_menu_item

    from shared.models import LoyaltyAccount, User, UserProfile

    _ensure_shop_settings(db_session)
    user = User(phone_hash=uuid.uuid4().hex[:32])
    db_session.add(user)
    db_session.flush()
    db_session.add(
        UserProfile(
            user_id=user.id, phone=b"test-phone-bytes", display_name="Test", preferred_language="ru"
        )
    )
    db_session.add(LoyaltyAccount(user_id=user.id, balance=0))
    db_session.flush()

    item = make_menu_item(db_session, base_price=15000)
    db_session.flush()

    _seed_cart(
        cart_redis,
        user.id,
        [{"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 1}],
    )

    token = _make_token("customer", user.id)

    class _ValidatorError(Exception):
        pass

    with (
        _patch_jwt(),
        patch(
            "core_api.services.checkout.validate_stop_list",
            side_effect=_ValidatorError("stop_listed"),
        ),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.validate_promocode", return_value=None),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        resp = db_client.post(
            "/api/v1/orders",
            json={"type": "pickup"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 409


def test_post_orders_rejects_unknown_type_with_422(client) -> None:
    """Неизвестный type=takeaway → 422."""
    with _patch_jwt():
        resp = client.post(
            "/api/v1/orders",
            json={"type": "takeaway"},
            headers=_auth("customer"),
        )
    assert resp.status_code == 422


def test_post_orders_rejects_negative_points_with_422(client) -> None:
    """points_to_use=-1 → 422."""
    with _patch_jwt():
        resp = client.post(
            "/api/v1/orders",
            json={"type": "pickup", "points_to_use": -1},
            headers=_auth("customer"),
        )
    assert resp.status_code == 422


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_post_orders_total_zero_returns_paid_status(db_client, db_session, cart_redis) -> None:
    """pricing → total=0 → 201 и JSON status == 'paid'."""
    from tests._factories.menu import make_menu_item

    from shared.models import LoyaltyAccount, User, UserProfile

    _ensure_shop_settings(db_session)
    user = User(phone_hash=uuid.uuid4().hex[:32])
    db_session.add(user)
    db_session.flush()
    db_session.add(
        UserProfile(
            user_id=user.id, phone=b"test-phone-bytes", display_name="Test", preferred_language="ru"
        )
    )
    db_session.add(LoyaltyAccount(user_id=user.id, balance=100000))
    db_session.flush()

    item = make_menu_item(db_session, base_price=20000)
    db_session.flush()

    _seed_cart(
        cart_redis,
        user.id,
        [{"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 1}],
    )

    token = _make_token("customer", user.id)

    with (
        _patch_jwt(),
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.validate_promocode", return_value=None),
        patch("core_api.services.checkout.compute_subtotal", return_value=20000),
        patch("core_api.services.checkout.apply_promocode", return_value=(0, 20000)),
        patch("core_api.services.checkout.apply_loyalty_points", return_value=(20000, 0)),
        patch("core_api.services.checkout.compute_delivery_fee", return_value=0),
        patch("core_api.services.checkout.compute_order_total", return_value=0),
        patch("core_api.services.checkout.compute_estimated_accrual", return_value=0),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        resp = db_client.post(
            "/api/v1/orders",
            json={"type": "pickup", "points_to_use": 20000},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 201
    assert resp.json()["status"] == "paid"


# ===========================================================================
# 12. RED: GET /api/v1/orders/{order_id}
# ===========================================================================


def test_orders_router_exposes_get_detail(client) -> None:
    """GET /api/v1/orders/{order_id} должен присутствовать в /openapi.json."""
    with _patch_jwt():
        resp = client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    assert "get" in paths.get("/api/v1/orders/{order_id}", {}), (
        "GET /api/v1/orders/{order_id} отсутствует"
    )


def test_get_order_detail_requires_auth(client) -> None:
    """GET /api/v1/orders/{id} без токена → 401."""
    with _patch_jwt():
        resp = client.get(f"/api/v1/orders/{uuid.uuid4()}")
    assert resp.status_code == 401


def test_get_order_detail_forbidden_for_staff(client) -> None:
    """GET /api/v1/orders/{id} с ролью barista → 403."""
    with _patch_jwt():
        resp = client.get(f"/api/v1/orders/{uuid.uuid4()}", headers=_auth("barista"))
    assert resp.status_code == 403


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_get_order_detail_returns_own_order(db_client, db_session) -> None:
    """Customer видит свой заказ: 200 с id / status / items / total."""
    from shared.enums import OrderStatus, OrderType
    from shared.models import LoyaltyAccount, Order, OrderItem, Payment, User, UserProfile

    user = User(phone_hash=uuid.uuid4().hex[:32])
    db_session.add(user)
    db_session.flush()
    db_session.add(
        UserProfile(
            user_id=user.id, phone=b"test-phone-bytes", display_name="Test", preferred_language="ru"
        )
    )
    db_session.add(LoyaltyAccount(user_id=user.id, balance=0))

    order = Order(
        user_id=user.id,
        status=OrderStatus.CREATED,
        type=OrderType.PICKUP,
        subtotal=15000,
        total=15000,
    )
    db_session.add(order)
    db_session.flush()

    db_session.add(
        OrderItem(
            order_id=order.id,
            menu_item_id=1,
            menu_item_name_ru="Латте",
            menu_item_name_en="Latte",
            unit_price=15000,
            modifiers_snapshot=[],
            quantity=1,
            line_total=15000,
        )
    )
    db_session.add(Payment(order_id=order.id, amount=15000))
    db_session.flush()

    token = _make_token("customer", user.id)
    with _patch_jwt():
        resp = db_client.get(
            f"/api/v1/orders/{order.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(order.id)
    assert body["status"] == "created"
    assert isinstance(body["items"], list) and len(body["items"]) >= 1
    assert body["total"] == 15000


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_get_order_detail_foreign_order_returns_404(db_client, db_session) -> None:
    """Customer A запрашивает заказ Customer B → 404 (не утекаем существование)."""
    from shared.enums import OrderStatus, OrderType
    from shared.models import LoyaltyAccount, Order, Payment, User, UserProfile

    user_a = User(phone_hash=uuid.uuid4().hex[:32])
    user_b = User(phone_hash=uuid.uuid4().hex[:32])
    db_session.add_all([user_a, user_b])
    db_session.flush()
    for u in (user_a, user_b):
        db_session.add(
            UserProfile(
                user_id=u.id,
                phone=b"test-phone-bytes",
                display_name="T",
                preferred_language="ru",
            )
        )
        db_session.add(LoyaltyAccount(user_id=u.id, balance=0))

    order_b = Order(
        user_id=user_b.id,
        status=OrderStatus.CREATED,
        type=OrderType.PICKUP,
        subtotal=10000,
        total=10000,
    )
    db_session.add(order_b)
    db_session.flush()
    db_session.add(Payment(order_id=order_b.id, amount=10000))
    db_session.flush()

    token_a = _make_token("customer", user_a.id)
    with _patch_jwt():
        resp = db_client.get(
            f"/api/v1/orders/{order_b.id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )

    assert resp.status_code == 404


def test_get_order_detail_unknown_id_returns_404(client) -> None:
    """Неизвестный order_id → 404."""
    with _patch_jwt():
        resp = client.get(f"/api/v1/orders/{uuid.uuid4()}", headers=_auth("customer"))
    assert resp.status_code == 404


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_get_order_detail_includes_confirmation_url_when_set(db_client, db_session) -> None:
    """Payment.confirmation_url='https://...' → попадает в тело ответа."""
    from shared.enums import OrderStatus, OrderType
    from shared.models import LoyaltyAccount, Order, Payment, User, UserProfile

    user = User(phone_hash=uuid.uuid4().hex[:32])
    db_session.add(user)
    db_session.flush()
    db_session.add(
        UserProfile(
            user_id=user.id, phone=b"test-phone-bytes", display_name="T", preferred_language="ru"
        )
    )
    db_session.add(LoyaltyAccount(user_id=user.id, balance=0))

    order = Order(
        user_id=user.id,
        status=OrderStatus.CREATED,
        type=OrderType.PICKUP,
        subtotal=15000,
        total=15000,
    )
    db_session.add(order)
    db_session.flush()

    db_session.add(
        Payment(
            order_id=order.id,
            amount=15000,
            confirmation_url="https://yookassa.ru/confirmation/abc123",
        )
    )
    db_session.flush()

    token = _make_token("customer", user.id)
    with _patch_jwt():
        resp = db_client.get(
            f"/api/v1/orders/{order.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    assert resp.json()["confirmation_url"] == "https://yookassa.ru/confirmation/abc123"


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_get_order_detail_confirmation_url_null_while_worker_pending(
    db_client, db_session
) -> None:
    """Payment.confirmation_url=None → в ответе тоже null."""
    from shared.enums import OrderStatus, OrderType
    from shared.models import LoyaltyAccount, Order, Payment, User, UserProfile

    user = User(phone_hash=uuid.uuid4().hex[:32])
    db_session.add(user)
    db_session.flush()
    db_session.add(
        UserProfile(
            user_id=user.id, phone=b"test-phone-bytes", display_name="T", preferred_language="ru"
        )
    )
    db_session.add(LoyaltyAccount(user_id=user.id, balance=0))

    order = Order(
        user_id=user.id,
        status=OrderStatus.CREATED,
        type=OrderType.PICKUP,
        subtotal=15000,
        total=15000,
    )
    db_session.add(order)
    db_session.flush()
    db_session.add(Payment(order_id=order.id, amount=15000, confirmation_url=None))
    db_session.flush()

    token = _make_token("customer", user.id)
    with _patch_jwt():
        resp = db_client.get(
            f"/api/v1/orders/{order.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    assert resp.json()["confirmation_url"] is None


# ===========================================================================
# 13. RED: RBAC matrix coverage
# ===========================================================================


def test_orders_routes_in_rbac_matrix() -> None:
    """ROUTE_MATRIX должен содержать POST и GET orders с ролью customer."""
    from core_api.rbac_matrix import CUSTOMER, ROUTE_MATRIX

    assert ("POST", "/api/v1/orders") in ROUTE_MATRIX
    assert ROUTE_MATRIX[("POST", "/api/v1/orders")] == {CUSTOMER}
    assert ("GET", "/api/v1/orders/{order_id}") in ROUTE_MATRIX
    assert ROUTE_MATRIX[("GET", "/api/v1/orders/{order_id}")] == {CUSTOMER}


def test_route_coverage_passes_for_orders() -> None:
    """Оба маршрута orders должны быть покрыты матрицей (не в PUBLIC_ROUTES)."""
    from tests.test_route_coverage import _all_registered_routes, _is_covered

    from core_api.rbac_matrix import PUBLIC_ROUTES

    registered = _all_registered_routes()
    assert ("POST", "/api/v1/orders") in registered, "POST /api/v1/orders не зарегистрирован"
    assert ("GET", "/api/v1/orders/{order_id}") in registered, (
        "GET /api/v1/orders/{order_id} не зарегистрирован"
    )
    assert _is_covered("POST", "/api/v1/orders")
    assert _is_covered("GET", "/api/v1/orders/{order_id}")
    assert ("POST", "/api/v1/orders") not in PUBLIC_ROUTES
    assert ("GET", "/api/v1/orders/{order_id}") not in PUBLIC_ROUTES
