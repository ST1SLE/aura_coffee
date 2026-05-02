"""RED: контракт расширения CreateOrderRequest и services.checkout для
saved-address flow (PDD §3, §5.2, §7.3 шаг 3; INV-008, INV-013, INV-014).

1. CreateOrderRequest получает optional delivery_address_id: UUID | None.
2. Для type=DELIVERY — XOR между delivery_address и delivery_address_id
   (ровно одно из двух → иначе 422).
3. Сервис checkout.create_order:
   - при delivery_address_id грузит строку из БД с ownership-проверкой
     (чужой → 404, НЕ 403);
   - снимок в orders.delivery_address_snapshot (JSONB, INV-014 immutable);
   - Haversine re-check ВСЕГДА — shop_settings могут измениться;
   - geocoder НЕ вызывается для сохранённых (у них уже есть lat/lon).

Импорты целевых символов выполняются ВНУТРИ каждого теста. В RED модели
DeliveryAddress ещё нет, поля delivery_address_id в CreateOrderRequest ещё нет,
helper-функции load_saved_address / geocode_address в checkout ещё нет —
каждый тест падает на своём import/AttributeError.
"""
from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import fakeredis
import pytest
from fastapi.testclient import TestClient

from tests.conftest import _TEST_DB_URL as TEST_DB_URL

_IS_SQLITE = TEST_DB_URL.startswith("sqlite")

_JWT_SECRET = "test-secret"


def _make_token(role: str = "customer", user_id: uuid.UUID | None = None) -> str:
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
    return patch(
        "core_api.services.auth.settings",
        **{
            "jwt_secret_key": _JWT_SECRET,
            "jwt_algorithm": "HS256",
            "access_token_ttl": 900,
        },
    )


def _seed_cart(cart_redis: fakeredis.FakeRedis, user_id: uuid.UUID, items: list[dict]) -> None:
    payload = {
        "items": items,
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    cart_redis.set(f"cart:{user_id}", json.dumps(payload), ex=300)


def _seed_shop_settings(db_session: Any) -> None:
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
def _checkout_user(db_session) -> Generator[tuple[uuid.UUID, Any, str], None, None]:
    """User + UserProfile + LoyaltyAccount + ShopSettings. Возвращает (user_id, user, token)."""
    from shared.models import LoyaltyAccount, User, UserProfile

    user = User(phone_hash=uuid.uuid4().hex[:32])
    db_session.add(user)
    db_session.flush()
    db_session.add(
        UserProfile(
            user_id=user.id,
            phone=b"test-phone-bytes",
            display_name="Test Customer",
            preferred_language="ru",
        )
    )
    db_session.add(LoyaltyAccount(user_id=user.id, balance=0))
    _seed_shop_settings(db_session)
    db_session.flush()

    token = _make_token("customer", user.id)
    yield (user.id, user, token)


def _saved_address(db_session: Any, user_id: uuid.UUID, **overrides: Any) -> Any:
    """Инсёртит delivery_addresses. Импорт модели внутри — RED-фэйл только здесь."""
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


@pytest.fixture
def db_client(cart_redis, db_session) -> Generator[TestClient, None, None]:
    """TestClient с fakeredis + реальной БД (функциональный db_session)."""
    from core_api.deps.database import get_db
    from core_api.main import app

    def _override_redis():
        yield cart_redis

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    try:
        with patch("core_api.deps.redis.get_redis", side_effect=_override_redis):
            with TestClient(app) as c:
                yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


# ===========================================================================
# 9. RED: CreateOrderRequest — поле delivery_address_id и XOR-валидация
# ===========================================================================


def test_create_order_request_accepts_delivery_address_id() -> None:
    """delivery_address_id: UUID | None — новое поле CreateOrderRequest."""
    from core_api.schemas.order import CreateOrderRequest

    addr_id = uuid.uuid4()
    req = CreateOrderRequest.model_validate(
        {"type": "delivery", "delivery_address_id": str(addr_id)}
    )
    assert req.delivery_address_id == addr_id
    assert req.delivery_address is None


def test_create_order_request_accepts_inline_delivery_address_legacy_path() -> None:
    """Legacy-путь (inline delivery_address) должен оставаться валидным; добавлено поле id=None."""
    from core_api.schemas.order import CreateOrderRequest

    req = CreateOrderRequest.model_validate(
        {
            "type": "delivery",
            "delivery_address": {"text": "A", "lat": 55.76, "lon": 37.61},
        }
    )
    assert req.delivery_address is not None
    assert req.delivery_address_id is None


def test_create_order_request_both_set_raises_validation_error() -> None:
    """Для type=DELIVERY нельзя передавать ОБА поля сразу."""
    from pydantic import ValidationError

    from core_api.schemas.order import CreateOrderRequest

    with pytest.raises(ValidationError):
        CreateOrderRequest.model_validate(
            {
                "type": "delivery",
                "delivery_address": {"text": "A", "lat": 55.76, "lon": 37.61},
                "delivery_address_id": str(uuid.uuid4()),
            }
        )


def test_create_order_request_neither_set_for_delivery_raises() -> None:
    """Для type=DELIVERY нужно хоть одно из двух полей."""
    from pydantic import ValidationError

    from core_api.schemas.order import CreateOrderRequest

    with pytest.raises(ValidationError):
        CreateOrderRequest.model_validate({"type": "delivery"})


def test_create_order_request_pickup_without_address_is_valid() -> None:
    """Регресс: pickup без адреса — валидный запрос."""
    from core_api.schemas.order import CreateOrderRequest

    req = CreateOrderRequest.model_validate({"type": "pickup"})
    assert req.delivery_address is None
    assert req.delivery_address_id is None


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_post_orders_rejects_both_delivery_fields_with_422(db_client, _checkout_user) -> None:
    user_id, _, _ = _checkout_user
    with _patch_jwt():
        resp = db_client.post(
            "/api/v1/orders",
            json={
                "type": "delivery",
                "delivery_address": {"text": "A", "lat": 55.76, "lon": 37.61},
                "delivery_address_id": str(uuid.uuid4()),
            },
            headers=_auth("customer", user_id),
        )
    assert resp.status_code == 422, resp.text


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_post_orders_rejects_neither_delivery_field_with_422(db_client, _checkout_user) -> None:
    user_id, _, _ = _checkout_user
    with _patch_jwt():
        resp = db_client.post(
            "/api/v1/orders",
            json={"type": "delivery"},
            headers=_auth("customer", user_id),
        )
    assert resp.status_code == 422, resp.text


# ===========================================================================
# 10. RED: checkout service — загрузка saved address + ownership check
# ===========================================================================


def test_checkout_loads_saved_address_when_id_provided() -> None:
    """core_api.services.checkout.load_saved_address должен быть вызван с (id, user_id, db)."""
    from tests._factories.menu import make_menu_item  # noqa: F401 — ensure package importable

    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order, load_saved_address  # noqa: F401
    from shared.enums import OrderType

    fake_redis = fakeredis.FakeRedis()
    fake_session = MagicMock()

    saved = MagicMock()
    saved.lat = 55.7600
    saved.lon = 37.6200
    saved.address_text = "Тверская 1"
    saved.apartment = None
    saved.entrance = None
    saved.floor = None
    saved.comment = None
    saved.user_id = uuid.uuid4()

    user_id = saved.user_id
    addr_id = uuid.uuid4()
    saved.id = addr_id

    payload = {
        "items": [
            {"menu_item_id": 1, "size_option_id": None, "modifier_ids": [], "quantity": 1}
        ],
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    fake_redis.set(f"cart:{user_id}", json.dumps(payload), ex=300)

    with (
        patch("core_api.services.checkout.load_saved_address", return_value=saved) as load_mock,
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.validate_promocode", return_value=None),
        patch("core_api.services.checkout.compute_subtotal", return_value=50000),
        patch("core_api.services.checkout.apply_promocode", return_value=(0, 50000)),
        patch("core_api.services.checkout.apply_loyalty_points", return_value=(0, 50000)),
        patch("core_api.services.checkout.compute_delivery_fee", return_value=0),
        patch("core_api.services.checkout.compute_order_total", return_value=50000),
        patch("core_api.services.checkout.compute_estimated_accrual", return_value=2500),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        try:
            create_order(
                user_id,
                CreateOrderRequest(type=OrderType.DELIVERY, delivery_address_id=addr_id),
                fake_redis,
                fake_session,
            )
        except Exception:
            # Для RED достаточно ImportError/AttributeError. Если GREEN ещё не положил
            # всю wiring'у — load_mock может не успеть вызваться из-за ранних ошибок.
            pass

        assert load_mock.called, "load_saved_address должен быть вызван при delivery_address_id"
        call_args = load_mock.call_args
        assert addr_id in (call_args.args + tuple(call_args.kwargs.values())), (
            "В аргументах load_saved_address должен быть переданный UUID адреса"
        )
        assert user_id in (call_args.args + tuple(call_args.kwargs.values())), (
            "В аргументах load_saved_address должен быть user_id"
        )


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_checkout_foreign_address_id_returns_404(db_client, db_session, cart_redis, _checkout_user) -> None:
    """Чужой delivery_address_id → HTTP 404 (не 403)."""
    from tests._factories.menu import make_menu_item

    from shared.models import User, UserProfile

    user_a, _, token = _checkout_user

    user_b = User(phone_hash=uuid.uuid4().hex[:32])
    db_session.add(user_b)
    db_session.flush()
    db_session.add(UserProfile(user_id=user_b.id, phone=b"b", preferred_language="ru"))
    row_z = _saved_address(db_session, user_b.id, label="чужой")
    db_session.flush()

    item = make_menu_item(db_session, base_price=50000)
    db_session.flush()
    _seed_cart(
        cart_redis,
        user_a,
        [{"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 1}],
    )

    with (
        _patch_jwt(),
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        resp = db_client.post(
            "/api/v1/orders",
            json={"type": "delivery", "delivery_address_id": str(row_z.id)},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 404, resp.text


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_checkout_unknown_address_id_returns_404(db_client, db_session, cart_redis, _checkout_user) -> None:
    """Неизвестный UUID delivery_address_id → 404."""
    from tests._factories.menu import make_menu_item

    user_a, _, token = _checkout_user

    item = make_menu_item(db_session, base_price=50000)
    db_session.flush()
    _seed_cart(
        cart_redis,
        user_a,
        [{"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 1}],
    )

    with (
        _patch_jwt(),
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        resp = db_client.post(
            "/api/v1/orders",
            json={"type": "delivery", "delivery_address_id": str(uuid.uuid4())},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 404, resp.text


def test_checkout_does_not_call_geocoder_when_address_id_provided() -> None:
    """Для сохранённых адресов geocoder не вызывается (у них уже есть lat/lon)."""
    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order, geocode_address  # noqa: F401
    from shared.enums import OrderType

    fake_redis = fakeredis.FakeRedis()
    fake_session = MagicMock()

    saved = MagicMock()
    saved.lat = 55.7600
    saved.lon = 37.6200
    saved.address_text = "Тверская 1"
    saved.apartment = None
    saved.entrance = None
    saved.floor = None
    saved.comment = None

    user_id = uuid.uuid4()
    saved.user_id = user_id
    addr_id = uuid.uuid4()
    saved.id = addr_id

    payload = {
        "items": [
            {"menu_item_id": 1, "size_option_id": None, "modifier_ids": [], "quantity": 1}
        ],
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    fake_redis.set(f"cart:{user_id}", json.dumps(payload), ex=300)

    with (
        patch("core_api.services.checkout.geocode_address") as geo_mock,
        patch("core_api.services.checkout.load_saved_address", return_value=saved),
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.validate_promocode", return_value=None),
        patch("core_api.services.checkout.compute_subtotal", return_value=50000),
        patch("core_api.services.checkout.apply_promocode", return_value=(0, 50000)),
        patch("core_api.services.checkout.apply_loyalty_points", return_value=(0, 50000)),
        patch("core_api.services.checkout.compute_delivery_fee", return_value=0),
        patch("core_api.services.checkout.compute_order_total", return_value=50000),
        patch("core_api.services.checkout.compute_estimated_accrual", return_value=2500),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        try:
            create_order(
                user_id,
                CreateOrderRequest(type=OrderType.DELIVERY, delivery_address_id=addr_id),
                fake_redis,
                fake_session,
            )
        except Exception:
            pass
        assert geo_mock.called is False, (
            "geocode_address не должен вызываться для saved-address flow"
        )


# ===========================================================================
# 11. RED: checkout — snapshot in orders.delivery_address_snapshot (INV-014)
# ===========================================================================


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (JSONB, enum, FK)")
def test_checkout_snapshots_saved_address_into_order_jsonb(
    db_client, db_session, cart_redis, _checkout_user
) -> None:
    """delivery_address_snapshot = JSONB-копия сохранённой строки (не FK)."""
    from tests._factories.menu import make_menu_item

    from shared.models import Order

    user_a, _, token = _checkout_user

    row = _saved_address(
        db_session,
        user_a,
        label="Дом",
        address_text="Москва, Тверская 1",
        lat=55.7600,
        lon=37.6200,
        apartment="12",
        entrance="2",
        floor="3",
        comment="код 1234",
    )
    db_session.flush()

    item = make_menu_item(db_session, base_price=50000)
    db_session.flush()
    _seed_cart(
        cart_redis,
        user_a,
        [{"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 1}],
    )

    with (
        _patch_jwt(),
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        resp = db_client.post(
            "/api/v1/orders",
            json={"type": "delivery", "delivery_address_id": str(row.id)},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 201, resp.text
    order_id = uuid.UUID(resp.json()["id"])
    db_session.expire_all()
    order = db_session.get(Order, order_id)
    assert order is not None
    snap = order.delivery_address_snapshot
    assert snap is not None, "delivery_address_snapshot должен быть установлен"
    assert snap.get("text") == "Москва, Тверская 1"
    assert float(snap.get("lat")) == pytest.approx(55.7600)
    assert float(snap.get("lon")) == pytest.approx(37.6200)
    # Остальные поля — либо присутствуют, либо пропущены, но если присутствуют, то с ожидаемым значением
    if "apartment" in snap:
        assert snap["apartment"] == "12"
    if "entrance" in snap:
        assert snap["entrance"] == "2"
    if "floor" in snap:
        assert snap["floor"] == "3"
    if "comment" in snap:
        assert snap["comment"] == "код 1234"


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_checkout_snapshot_byte_identical_after_saved_address_deleted(
    db_client, db_session, cart_redis, _checkout_user
) -> None:
    """Удаление сохранённого адреса НЕ меняет order.delivery_address_snapshot (INV-014)."""
    from tests._factories.menu import make_menu_item

    from shared.models import DeliveryAddress, Order

    user_a, _, token = _checkout_user
    row = _saved_address(db_session, user_a, label="W")
    row_id = row.id
    db_session.flush()

    item = make_menu_item(db_session, base_price=50000)
    db_session.flush()
    _seed_cart(
        cart_redis,
        user_a,
        [{"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 1}],
    )

    with (
        _patch_jwt(),
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        resp = db_client.post(
            "/api/v1/orders",
            json={"type": "delivery", "delivery_address_id": str(row_id)},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 201, resp.text
    order_id = uuid.UUID(resp.json()["id"])

    db_session.expire_all()
    order_before = db_session.get(Order, order_id)
    snap_before = copy.deepcopy(order_before.delivery_address_snapshot)

    # Удаляем источник
    db_session.delete(db_session.get(DeliveryAddress, row_id))
    db_session.flush()

    db_session.expire_all()
    order_after = db_session.get(Order, order_id)
    assert order_after.delivery_address_snapshot == snap_before, (
        "INV-014: snapshot не должен меняться при удалении исходного адреса"
    )


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_checkout_snapshot_shape_matches_inline_path(
    db_client, db_session, cart_redis, _checkout_user
) -> None:
    """Форма snapshot одинакова для inline и saved-address путей."""
    from tests._factories.menu import make_menu_item

    from shared.models import Order

    user_a, _, token = _checkout_user

    row = _saved_address(
        db_session,
        user_a,
        label="Дом",
        address_text="A",
        lat=55.76,
        lon=37.61,
    )
    db_session.flush()

    item = make_menu_item(db_session, base_price=50000)
    db_session.flush()

    # 1) inline-путь
    _seed_cart(
        cart_redis,
        user_a,
        [{"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 1}],
    )
    with (
        _patch_jwt(),
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        resp_inline = db_client.post(
            "/api/v1/orders",
            json={
                "type": "delivery",
                "delivery_address": {"text": "A", "lat": 55.76, "lon": 37.61},
            },
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp_inline.status_code == 201, resp_inline.text
    order_inline_id = uuid.UUID(resp_inline.json()["id"])

    # 2) saved-путь
    _seed_cart(
        cart_redis,
        user_a,
        [{"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 1}],
    )
    with (
        _patch_jwt(),
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        resp_saved = db_client.post(
            "/api/v1/orders",
            json={"type": "delivery", "delivery_address_id": str(row.id)},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp_saved.status_code == 201, resp_saved.text
    order_saved_id = uuid.UUID(resp_saved.json()["id"])

    db_session.expire_all()
    snap_inline = db_session.get(Order, order_inline_id).delivery_address_snapshot
    snap_saved = db_session.get(Order, order_saved_id).delivery_address_snapshot

    # Нормализуем: и там, и там должны быть совпадающие text/lat/lon
    assert snap_inline is not None and snap_saved is not None
    assert snap_inline.get("text") == snap_saved.get("text")
    assert float(snap_inline.get("lat")) == pytest.approx(float(snap_saved.get("lat")))
    assert float(snap_inline.get("lon")) == pytest.approx(float(snap_saved.get("lon")))


# ===========================================================================
# 12. RED: Haversine re-check ВСЕГДА
# ===========================================================================


def test_checkout_calls_validate_delivery_address_on_saved_path() -> None:
    """validate_delivery_address должен быть вызван хотя бы раз с координатами СОХРАНЁННОЙ строки."""
    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order, load_saved_address  # noqa: F401
    from shared.enums import OrderType

    fake_redis = fakeredis.FakeRedis()
    fake_session = MagicMock()

    saved = MagicMock()
    saved.lat = 55.7600
    saved.lon = 37.6200
    saved.address_text = "Тверская 1"
    saved.apartment = None
    saved.entrance = None
    saved.floor = None
    saved.comment = None

    user_id = uuid.uuid4()
    saved.user_id = user_id
    addr_id = uuid.uuid4()
    saved.id = addr_id

    payload = {
        "items": [
            {"menu_item_id": 1, "size_option_id": None, "modifier_ids": [], "quantity": 1}
        ],
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    fake_redis.set(f"cart:{user_id}", json.dumps(payload), ex=300)

    with (
        patch("core_api.services.checkout.load_saved_address", return_value=saved),
        patch("core_api.services.checkout.validate_delivery_address") as v_mock,
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.validate_promocode", return_value=None),
        patch("core_api.services.checkout.compute_subtotal", return_value=50000),
        patch("core_api.services.checkout.apply_promocode", return_value=(0, 50000)),
        patch("core_api.services.checkout.apply_loyalty_points", return_value=(0, 50000)),
        patch("core_api.services.checkout.compute_delivery_fee", return_value=0),
        patch("core_api.services.checkout.compute_order_total", return_value=50000),
        patch("core_api.services.checkout.compute_estimated_accrual", return_value=2500),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        try:
            create_order(
                user_id,
                CreateOrderRequest(type=OrderType.DELIVERY, delivery_address_id=addr_id),
                fake_redis,
                fake_session,
            )
        except Exception:
            pass
        assert v_mock.call_count >= 1, (
            "validate_delivery_address должен быть вызван хотя бы раз для saved-пути"
        )
        flat_args = []
        for c in v_mock.call_args_list:
            flat_args.extend(list(c.args))
            flat_args.extend(list(c.kwargs.values()))
        assert 55.7600 in flat_args or any(
            isinstance(x, float) and abs(x - 55.7600) < 1e-6 for x in flat_args
        ), f"Координаты сохранённой строки (lat=55.76) должны быть в аргументах validate_delivery_address; получено {v_mock.call_args_list}"


def test_checkout_calls_validate_delivery_address_on_inline_path() -> None:
    """Regression: inline-путь тоже вызывает validate_delivery_address."""
    from core_api.schemas.order import CreateOrderRequest, DeliveryAddress
    from core_api.services.checkout import create_order
    from shared.enums import OrderType

    fake_redis = fakeredis.FakeRedis()
    fake_session = MagicMock()
    user_id = uuid.uuid4()

    payload = {
        "items": [
            {"menu_item_id": 1, "size_option_id": None, "modifier_ids": [], "quantity": 1}
        ],
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    fake_redis.set(f"cart:{user_id}", json.dumps(payload), ex=300)

    with (
        patch("core_api.services.checkout.validate_delivery_address") as v_mock,
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.validate_promocode", return_value=None),
        patch("core_api.services.checkout.compute_subtotal", return_value=50000),
        patch("core_api.services.checkout.apply_promocode", return_value=(0, 50000)),
        patch("core_api.services.checkout.apply_loyalty_points", return_value=(0, 50000)),
        patch("core_api.services.checkout.compute_delivery_fee", return_value=0),
        patch("core_api.services.checkout.compute_order_total", return_value=50000),
        patch("core_api.services.checkout.compute_estimated_accrual", return_value=2500),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        try:
            create_order(
                user_id,
                CreateOrderRequest(
                    type=OrderType.DELIVERY,
                    delivery_address=DeliveryAddress(text="A", lat=55.76, lon=37.61),
                ),
                fake_redis,
                fake_session,
            )
        except Exception:
            pass
        assert v_mock.call_count >= 1, "inline-путь должен также вызывать validate_delivery_address"


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_checkout_rejects_saved_address_now_outside_radius(
    db_client, db_session, cart_redis, _checkout_user
) -> None:
    """Сохранённый адрес теперь вне радиуса → 409, ни одной Order-записи."""
    from tests._factories.menu import make_menu_item

    from core_api.services.validators.exceptions import DeliveryRadiusError
    from shared.models import Order

    user_a, _, token = _checkout_user
    row = _saved_address(db_session, user_a, label="W")
    db_session.flush()

    item = make_menu_item(db_session, base_price=15000)
    db_session.flush()
    _seed_cart(
        cart_redis,
        user_a,
        [{"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 1}],
    )

    count_before = db_session.query(Order).count()

    with (
        _patch_jwt(),
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch(
            "core_api.services.checkout.validate_delivery_address",
            side_effect=DeliveryRadiusError("distance > radius"),
        ),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        resp = db_client.post(
            "/api/v1/orders",
            json={"type": "delivery", "delivery_address_id": str(row.id)},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 409, resp.text
    db_session.expire_all()
    count_after = db_session.query(Order).count()
    assert count_after == count_before, "Order не должен быть создан при out-of-radius"


def test_checkout_haversine_uses_saved_row_coords_not_request_body() -> None:
    """validate_delivery_address должен получить координаты СОХРАНЁННОЙ строки."""
    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order, load_saved_address  # noqa: F401
    from shared.enums import OrderType

    fake_redis = fakeredis.FakeRedis()
    fake_session = MagicMock()

    saved = MagicMock()
    A_LAT, A_LON = 55.9999, 37.8888
    saved.lat = A_LAT
    saved.lon = A_LON
    saved.address_text = "Особый адрес"
    saved.apartment = None
    saved.entrance = None
    saved.floor = None
    saved.comment = None

    user_id = uuid.uuid4()
    saved.user_id = user_id
    addr_id = uuid.uuid4()
    saved.id = addr_id

    payload = {
        "items": [
            {"menu_item_id": 1, "size_option_id": None, "modifier_ids": [], "quantity": 1}
        ],
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    fake_redis.set(f"cart:{user_id}", json.dumps(payload), ex=300)

    with (
        patch("core_api.services.checkout.load_saved_address", return_value=saved),
        patch("core_api.services.checkout.validate_delivery_address") as v_mock,
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.validate_promocode", return_value=None),
        patch("core_api.services.checkout.compute_subtotal", return_value=50000),
        patch("core_api.services.checkout.apply_promocode", return_value=(0, 50000)),
        patch("core_api.services.checkout.apply_loyalty_points", return_value=(0, 50000)),
        patch("core_api.services.checkout.compute_delivery_fee", return_value=0),
        patch("core_api.services.checkout.compute_order_total", return_value=50000),
        patch("core_api.services.checkout.compute_estimated_accrual", return_value=2500),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        try:
            create_order(
                user_id,
                CreateOrderRequest(type=OrderType.DELIVERY, delivery_address_id=addr_id),
                fake_redis,
                fake_session,
            )
        except Exception:
            pass

        flat_args: list[Any] = []
        for c in v_mock.call_args_list:
            flat_args.extend(list(c.args))
            flat_args.extend(list(c.kwargs.values()))
        has_lat = any(isinstance(x, float) and abs(x - A_LAT) < 1e-6 for x in flat_args)
        has_lon = any(isinstance(x, float) and abs(x - A_LON) < 1e-6 for x in flat_args)
        assert has_lat and has_lon, (
            f"validate_delivery_address должен получить SAVED lat={A_LAT}, lon={A_LON}; "
            f"фактические аргументы: {v_mock.call_args_list}"
        )
