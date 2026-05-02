"""RED: контракт core_api.services.checkout.create_order (Phase 3, §7.1 item 1).

Пин сервиса Cart → Order: чтение Redis-корзины, валидаторы (stop-list /
working hours / delivery / promocode), pricing chain §7.2, атомарные
записи в БД (INV-004), неизменяемые снимки OrderItem (INV-014),
shortcut total=0 → PAID (без Celery) и total>0 → CREATED + enqueue.

Все тесты ДОЛЖНЫ падать в RED с ImportError / ModuleNotFoundError, пока
GREEN-цикл не положит `services/checkout.py`. Импорты целевых символов
выполняются ВНУТРИ тел тестов — collection не ломается.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import fakeredis
import pytest

from tests.conftest import _TEST_DB_URL as TEST_DB_URL

_IS_SQLITE = TEST_DB_URL.startswith("sqlite")


# ---------------------------------------------------------------------------
# Фикстуры и хелперы
# ---------------------------------------------------------------------------


@pytest.fixture
def _checkout_user(db_session):
    """Создаёт User + UserProfile + LoyaltyAccount и возвращает (user_id, user)."""
    from shared.models import LoyaltyAccount, User, UserProfile

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

    account = LoyaltyAccount(user_id=user.id, balance=0)
    db_session.add(account)
    _upsert_shop_settings(db_session)
    db_session.flush()

    yield (user.id, user)


def _seed_cart(cart_redis: fakeredis.FakeRedis, user_id: Any, items: list[dict]) -> None:
    """Пишет {"items": items, "updated_at": ...} в cart:{user_id} с TTL=300."""
    payload = {
        "items": items,
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    cart_redis.set(f"cart:{user_id}", json.dumps(payload), ex=300)


def _working_hours_always_open() -> dict[str, dict[str, str]]:
    return {
        day: {"open": "00:00", "close": "23:59"}
        for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
    }


def _upsert_shop_settings(
    db_session: Any,
    *,
    min_delivery_amount: int = 30000,
    free_delivery_threshold: int = 100000,
    delivery_fee: int = 15000,
    loyalty_percent: int = 5,
    working_hours: dict[str, dict[str, str]] | None = None,
) -> Any:
    from shared.models import ShopSettings

    settings = db_session.get(ShopSettings, 1)
    if settings is None:
        settings = ShopSettings(
            id=1,
            shop_lat=55.7558,
            shop_lon=37.6173,
            delivery_radius_km=5.0,
            min_delivery_amount=min_delivery_amount,
            free_delivery_threshold=free_delivery_threshold,
            delivery_fee=delivery_fee,
            loyalty_percent=loyalty_percent,
            default_prep_time_minutes=15,
            estimated_delivery_time_minutes=30,
            working_hours=working_hours or _working_hours_always_open(),
        )
        db_session.add(settings)
    else:
        settings.shop_lat = 55.7558
        settings.shop_lon = 37.6173
        settings.delivery_radius_km = 5.0
        settings.min_delivery_amount = min_delivery_amount
        settings.free_delivery_threshold = free_delivery_threshold
        settings.delivery_fee = delivery_fee
        settings.loyalty_percent = loyalty_percent
        settings.default_prep_time_minutes = 15
        settings.estimated_delivery_time_minutes = 30
        settings.working_hours = working_hours or _working_hours_always_open()
    db_session.flush()
    return settings


# ---------------------------------------------------------------------------
# 2. RED: сервис checkout — импорт и пустая корзина
# ---------------------------------------------------------------------------


def test_checkout_service_module_importable() -> None:
    """create_order должен быть импортируемым callable."""
    from core_api.services.checkout import create_order  # noqa: F401

    assert callable(create_order)


def test_create_order_rejects_empty_cart() -> None:
    """Пустой Redis-ключ корзины → ошибка 'Корзина пуста'."""
    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order
    from shared.enums import OrderType

    user_id = uuid.uuid4()
    fake_redis = fakeredis.FakeRedis()
    fake_session = MagicMock()

    with pytest.raises(Exception) as excinfo:
        create_order(
            user_id,
            CreateOrderRequest(type=OrderType.PICKUP),
            fake_redis,
            fake_session,
        )
    assert "Корзина пуста" in str(excinfo.value)


def test_create_order_rejects_cart_with_zero_items() -> None:
    """Корзина с пустым items[] → та же ошибка 'Корзина пуста'."""
    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order
    from shared.enums import OrderType

    user_id = uuid.uuid4()
    fake_redis = fakeredis.FakeRedis()
    _seed_cart(fake_redis, user_id, [])
    fake_session = MagicMock()

    with pytest.raises(Exception) as excinfo:
        create_order(
            user_id,
            CreateOrderRequest(type=OrderType.PICKUP),
            fake_redis,
            fake_session,
        )
    assert "Корзина пуста" in str(excinfo.value)


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_order_success_asserts_ldd_and_uses_shop_settings_pricing(
    cart_redis, db_session, _checkout_user, grace_logs
) -> None:
    """GRACE-LDD: successful delivery checkout uses settings for fee/accrual."""
    from tests._factories.menu import make_menu_item

    from core_api.schemas.order import CreateOrderRequest, DeliveryAddress
    from core_api.services.checkout import create_order
    from shared.enums import OrderStatus, OrderType
    from shared.models import Order

    user_id, _ = _checkout_user
    _upsert_shop_settings(
        db_session,
        min_delivery_amount=30000,
        free_delivery_threshold=100000,
        delivery_fee=7000,
        loyalty_percent=12,
    )
    item = make_menu_item(db_session, base_price=50000)
    db_session.flush()
    _seed_cart(
        cart_redis,
        user_id,
        [
            {
                "menu_item_id": item.id,
                "size_option_id": None,
                "modifier_ids": [],
                "quantity": 1,
            }
        ],
    )

    with patch("core_api.services.checkout.enqueue_payment_task"):
        resp = create_order(
            user_id,
            CreateOrderRequest(
                type=OrderType.DELIVERY,
                delivery_address=DeliveryAddress(
                    text="Secret Apt 42",
                    lat=55.7558,
                    lon=37.6173,
                ),
            ),
            cart_redis,
            db_session,
        )

    assert resp.status == OrderStatus.CREATED
    assert resp.subtotal == 50000
    assert resp.delivery_fee == 7000
    assert resp.total == 57000
    assert resp.estimated_accrual == 6000
    order = db_session.query(Order).filter(Order.user_id == user_id).one()
    assert order.estimated_ready_at is not None

    grace_logs.assert_trajectory(
        ("orders.create", "BLOCK_TX_BEGIN"),
        ("orders.create", "BLOCK_STATE_TRANSITION"),
        ("orders.create", "BLOCK_TX_COMMIT"),
    )
    assert grace_logs.beliefs(status="MISMATCH") == []
    assert "Secret Apt 42" not in "\n".join(grace_logs.lines)


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_order_decrements_finite_inventory_and_asserts_ldd(
    cart_redis, db_session, _checkout_user, grace_logs
) -> None:
    """GRACE-LDD: checkout decrements finite inventory in the order transaction."""
    from tests._factories.menu import make_menu_item

    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order
    from shared.enums import OrderType
    from shared.models import OrderItem

    user_id, _ = _checkout_user
    item = make_menu_item(db_session, base_price=20000, inventory_quantity=3)
    db_session.flush()
    _seed_cart(
        cart_redis,
        user_id,
        [
            {
                "menu_item_id": item.id,
                "size_option_id": None,
                "modifier_ids": [],
                "quantity": 2,
            }
        ],
    )

    with patch("core_api.services.checkout.enqueue_payment_task"):
        resp = create_order(
            user_id,
            CreateOrderRequest(type=OrderType.PICKUP),
            cart_redis,
            db_session,
        )

    db_session.refresh(item)
    assert item.inventory_quantity == 1
    order_item = db_session.query(OrderItem).filter_by(order_id=resp.id).one()
    assert order_item.menu_item_id == item.id
    assert order_item.quantity == 2

    grace_logs.assert_trajectory(
        ("orders.create", "BLOCK_TX_BEGIN"),
        ("orders.create", "BLOCK_STATE_TRANSITION"),
        ("orders.create", "BLOCK_TX_COMMIT"),
    )
    assert grace_logs.beliefs(status="MISMATCH") == []
    lines = "\n".join(grace_logs.lines)
    assert "test-phone-bytes" not in lines
    assert "Test Customer" not in lines


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_order_rejects_insufficient_inventory_before_persistence(
    cart_redis, db_session, _checkout_user, grace_logs
) -> None:
    """GRACE-LDD: insufficient finite stock leaves no order/payment rows."""
    from tests._factories.menu import make_menu_item

    from core_api.schemas.order import CreateOrderRequest, DeliveryAddress
    from core_api.services.checkout import InventoryInsufficientError, create_order
    from shared.enums import OrderType
    from shared.models import Order, Payment

    user_id, _ = _checkout_user
    _upsert_shop_settings(db_session, min_delivery_amount=10000)
    item = make_menu_item(db_session, base_price=20000, inventory_quantity=1)
    db_session.flush()
    _seed_cart(
        cart_redis,
        user_id,
        [
            {
                "menu_item_id": item.id,
                "size_option_id": None,
                "modifier_ids": [],
                "quantity": 2,
            }
        ],
    )

    with pytest.raises(InventoryInsufficientError):
        create_order(
            user_id,
            CreateOrderRequest(
                type=OrderType.DELIVERY,
                delivery_address=DeliveryAddress(
                    text="Secret Inventory Address",
                    lat=55.7558,
                    lon=37.6173,
                ),
            ),
            cart_redis,
            db_session,
        )

    db_session.refresh(item)
    assert item.inventory_quantity == 1
    assert db_session.query(Order).filter(Order.user_id == user_id).count() == 0
    assert (
        db_session.query(Payment).join(Order).filter(Order.user_id == user_id).count()
        == 0
    )
    assert grace_logs.blocks(fn="orders.create", blk="BLOCK_TX_BEGIN")
    assert grace_logs.blocks(fn="orders.create", blk="BLOCK_TX_COMMIT") == []
    assert grace_logs.beliefs(status="MISMATCH") == []
    assert "Secret Inventory Address" not in "\n".join(grace_logs.lines)


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_order_aggregates_inventory_by_menu_item_id(
    cart_redis, db_session, _checkout_user
) -> None:
    """Different cart line shapes for one item share the same finite stock."""
    from tests._factories.menu import make_menu_item, make_modifier

    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import InventoryInsufficientError, create_order
    from shared.enums import OrderType

    user_id, _ = _checkout_user
    mod = make_modifier(db_session, name_ru="Сироп", name_en="Syrup")
    item = make_menu_item(
        db_session,
        base_price=20000,
        inventory_quantity=2,
        modifiers=[mod],
    )
    db_session.flush()
    _seed_cart(
        cart_redis,
        user_id,
        [
            {
                "menu_item_id": item.id,
                "size_option_id": None,
                "modifier_ids": [],
                "quantity": 1,
            },
            {
                "menu_item_id": item.id,
                "size_option_id": None,
                "modifier_ids": [mod.id],
                "quantity": 2,
            },
        ],
    )

    with pytest.raises(InventoryInsufficientError):
        create_order(
            user_id,
            CreateOrderRequest(type=OrderType.PICKUP),
            cart_redis,
            db_session,
        )

    db_session.refresh(item)
    assert item.inventory_quantity == 2


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_order_stale_stop_list_fails_before_persistence(
    cart_redis, db_session, _checkout_user, grace_logs
) -> None:
    """GRACE-LDD: stale cart item stop-listed before checkout leaves no rows."""
    from tests._factories.menu import make_menu_item

    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order
    from core_api.services.validators.exceptions import StopListError
    from shared.enums import OrderType
    from shared.models import Order, Payment

    user_id, _ = _checkout_user
    _upsert_shop_settings(db_session)
    item = make_menu_item(db_session, base_price=50000, available=True)
    db_session.flush()
    _seed_cart(
        cart_redis,
        user_id,
        [
            {
                "menu_item_id": item.id,
                "size_option_id": None,
                "modifier_ids": [],
                "quantity": 1,
            }
        ],
    )
    item.available = False
    db_session.flush()

    with pytest.raises(StopListError):
        create_order(
            user_id,
            CreateOrderRequest(type=OrderType.PICKUP),
            cart_redis,
            db_session,
        )

    assert db_session.query(Order).filter(Order.user_id == user_id).count() == 0
    assert (
        db_session.query(Payment).join(Order).filter(Order.user_id == user_id).count()
        == 0
    )
    assert grace_logs.blocks(fn="orders.create", blk="BLOCK_TX_BEGIN")
    assert grace_logs.blocks(fn="orders.create", blk="BLOCK_TX_COMMIT") == []


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_order_delivery_minimum_fails_before_persistence(
    cart_redis, db_session, _checkout_user, grace_logs
) -> None:
    """Delivery minimum is enforced with ShopSettings before order/payment writes."""
    from tests._factories.menu import make_menu_item

    from core_api.schemas.order import CreateOrderRequest, DeliveryAddress
    from core_api.services.checkout import create_order
    from core_api.services.validators.exceptions import MinimumDeliveryAmountError
    from shared.enums import OrderType
    from shared.models import Order, Payment

    user_id, _ = _checkout_user
    _upsert_shop_settings(db_session, min_delivery_amount=30000)
    item = make_menu_item(db_session, base_price=20000)
    db_session.flush()
    _seed_cart(
        cart_redis,
        user_id,
        [
            {
                "menu_item_id": item.id,
                "size_option_id": None,
                "modifier_ids": [],
                "quantity": 1,
            }
        ],
    )

    with pytest.raises(MinimumDeliveryAmountError):
        create_order(
            user_id,
            CreateOrderRequest(
                type=OrderType.DELIVERY,
                delivery_address=DeliveryAddress(
                    text="Below minimum address",
                    lat=55.7558,
                    lon=37.6173,
                ),
            ),
            cart_redis,
            db_session,
        )

    assert db_session.query(Order).filter(Order.user_id == user_id).count() == 0
    assert (
        db_session.query(Payment).join(Order).filter(Order.user_id == user_id).count()
        == 0
    )
    assert grace_logs.blocks(fn="orders.create", blk="BLOCK_TX_COMMIT") == []
    assert "Below minimum address" not in "\n".join(grace_logs.lines)


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_order_promocode_validator_uses_subtotal_before_persistence(
    cart_redis, db_session, _checkout_user, grace_logs
) -> None:
    """Real promocode validator rejects subtotal below min before writes."""
    from tests._factories.menu import make_menu_item
    from tests._factories.promocodes import make_promocode

    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order
    from core_api.services.validators.exceptions import PromocodeValidationError
    from shared.enums import OrderType
    from shared.models import Order, Payment, PromocodeUsage

    user_id, _ = _checkout_user
    _upsert_shop_settings(db_session)
    promo = make_promocode(
        db_session,
        code="MIN1000",
        is_active=True,
        min_order_amount=100000,
    )
    item = make_menu_item(db_session, base_price=50000)
    db_session.flush()
    _seed_cart(
        cart_redis,
        user_id,
        [
            {
                "menu_item_id": item.id,
                "size_option_id": None,
                "modifier_ids": [],
                "quantity": 1,
            }
        ],
    )

    with pytest.raises(PromocodeValidationError):
        create_order(
            user_id,
            CreateOrderRequest(type=OrderType.PICKUP, promocode_code=promo.code),
            cart_redis,
            db_session,
        )

    assert db_session.query(Order).filter(Order.user_id == user_id).count() == 0
    assert (
        db_session.query(Payment).join(Order).filter(Order.user_id == user_id).count()
        == 0
    )
    assert db_session.query(PromocodeUsage).count() == 0
    db_session.refresh(promo)
    assert promo.current_uses == 0
    assert grace_logs.blocks(fn="orders.create", blk="BLOCK_TX_COMMIT") == []


# ---------------------------------------------------------------------------
# 3. RED: сервис checkout — validator wiring (pickup)
# ---------------------------------------------------------------------------


def _cart_item() -> dict:
    """Минимальная строка корзины для тестов с моками."""
    return {
        "menu_item_id": 1,
        "size_option_id": None,
        "modifier_ids": [],
        "quantity": 1,
    }


def _patched_pipeline():
    """Список (cm) для патча всех валидаторов и pricing-функций."""
    return [
        patch("core_api.services.checkout.validate_stop_list", MagicMock()),
        patch("core_api.services.checkout.validate_time_slot", MagicMock()),
        patch("core_api.services.checkout.validate_delivery_address", MagicMock()),
        patch("core_api.services.checkout.validate_min_delivery_amount", MagicMock()),
        patch("core_api.services.checkout.validate_promocode", MagicMock(return_value=None)),
        patch("core_api.services.checkout.compute_subtotal", MagicMock(return_value=50000)),
        patch("core_api.services.checkout.apply_promocode", MagicMock(return_value=(0, 50000))),
        patch(
            "core_api.services.checkout.apply_loyalty_points",
            MagicMock(return_value=(0, 50000)),
        ),
        patch("core_api.services.checkout.compute_delivery_fee", MagicMock(return_value=0)),
        patch("core_api.services.checkout.compute_order_total", MagicMock(return_value=50000)),
        patch(
            "core_api.services.checkout.compute_estimated_accrual",
            MagicMock(return_value=2500),
        ),
        patch("core_api.services.checkout.enqueue_payment_task", MagicMock()),
    ]


def test_create_order_calls_stop_list_validator() -> None:
    """validate_stop_list должен быть вызван хотя бы раз для элементов корзины."""
    from core_api.schemas.order import CreateOrderRequest
    from shared.enums import OrderType

    user_id = uuid.uuid4()
    fake_redis = fakeredis.FakeRedis()
    _seed_cart(fake_redis, user_id, [_cart_item()])
    fake_session = MagicMock()

    with (
        patch("core_api.services.checkout.validate_stop_list") as mv_stop,
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
        from core_api.services.checkout import create_order

        try:
            create_order(
                user_id,
                CreateOrderRequest(type=OrderType.PICKUP),
                fake_redis,
                fake_session,
            )
        except Exception:
            # Падение на более позднем этапе допустимо — проверяем только вызов валидатора
            pass

        assert mv_stop.call_count >= 1


def test_create_order_calls_time_slot_validator_before_pricing() -> None:
    """validate_time_slot вызывается раньше compute_subtotal (порядок §7.2)."""
    from core_api.schemas.order import CreateOrderRequest
    from shared.enums import OrderType

    user_id = uuid.uuid4()
    fake_redis = fakeredis.FakeRedis()
    _seed_cart(fake_redis, user_id, [_cart_item()])
    fake_session = MagicMock()

    parent = MagicMock()

    with (
        patch("core_api.services.checkout.validate_stop_list", parent.validate_stop_list),
        patch("core_api.services.checkout.validate_time_slot", parent.validate_time_slot),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.validate_promocode", return_value=None),
        patch("core_api.services.checkout.compute_subtotal", parent.compute_subtotal) as mv_sub,
        patch("core_api.services.checkout.apply_promocode", return_value=(0, 50000)),
        patch("core_api.services.checkout.apply_loyalty_points", return_value=(0, 50000)),
        patch("core_api.services.checkout.compute_delivery_fee", return_value=0),
        patch("core_api.services.checkout.compute_order_total", return_value=50000),
        patch("core_api.services.checkout.compute_estimated_accrual", return_value=2500),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        mv_sub.return_value = 50000
        from core_api.services.checkout import create_order

        try:
            create_order(
                user_id,
                CreateOrderRequest(type=OrderType.PICKUP),
                fake_redis,
                fake_session,
            )
        except Exception:
            pass

        names = [c[0] for c in parent.mock_calls]
        assert "validate_time_slot" in names, f"validate_time_slot не вызван: {names}"
        assert "compute_subtotal" in names, f"compute_subtotal не вызван: {names}"
        assert names.index("validate_time_slot") < names.index("compute_subtotal")


def test_create_order_does_not_call_delivery_validators_for_pickup() -> None:
    """type=PICKUP → validate_delivery_address / validate_min_delivery_amount НЕ вызываются."""
    from core_api.schemas.order import CreateOrderRequest
    from shared.enums import OrderType

    user_id = uuid.uuid4()
    fake_redis = fakeredis.FakeRedis()
    _seed_cart(fake_redis, user_id, [_cart_item()])
    fake_session = MagicMock()

    with (
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address") as mv_addr,
        patch("core_api.services.checkout.validate_min_delivery_amount") as mv_min,
        patch("core_api.services.checkout.validate_promocode", return_value=None),
        patch("core_api.services.checkout.compute_subtotal", return_value=50000),
        patch("core_api.services.checkout.apply_promocode", return_value=(0, 50000)),
        patch("core_api.services.checkout.apply_loyalty_points", return_value=(0, 50000)),
        patch("core_api.services.checkout.compute_delivery_fee", return_value=0),
        patch("core_api.services.checkout.compute_order_total", return_value=50000),
        patch("core_api.services.checkout.compute_estimated_accrual", return_value=2500),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        from core_api.services.checkout import create_order

        try:
            create_order(
                user_id,
                CreateOrderRequest(type=OrderType.PICKUP),
                fake_redis,
                fake_session,
            )
        except Exception:
            pass

        assert mv_addr.called is False
        assert mv_min.called is False


def test_create_order_does_not_call_promocode_validator_when_code_absent() -> None:
    """promocode_code=None → validate_promocode НЕ вызывается."""
    from core_api.schemas.order import CreateOrderRequest
    from shared.enums import OrderType

    user_id = uuid.uuid4()
    fake_redis = fakeredis.FakeRedis()
    _seed_cart(fake_redis, user_id, [_cart_item()])
    fake_session = MagicMock()

    with (
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.validate_promocode") as mv_promo,
        patch("core_api.services.checkout.compute_subtotal", return_value=50000),
        patch("core_api.services.checkout.apply_promocode", return_value=(0, 50000)),
        patch("core_api.services.checkout.apply_loyalty_points", return_value=(0, 50000)),
        patch("core_api.services.checkout.compute_delivery_fee", return_value=0),
        patch("core_api.services.checkout.compute_order_total", return_value=50000),
        patch("core_api.services.checkout.compute_estimated_accrual", return_value=2500),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        from core_api.services.checkout import create_order

        try:
            create_order(
                user_id,
                CreateOrderRequest(type=OrderType.PICKUP, promocode_code=None),
                fake_redis,
                fake_session,
            )
        except Exception:
            pass

        assert mv_promo.called is False


def test_create_order_validator_failure_raises_before_db_writes() -> None:
    """Если validate_stop_list бросает, исключение проходит и db_session.add не вызван."""
    from core_api.schemas.order import CreateOrderRequest
    from shared.enums import OrderType

    user_id = uuid.uuid4()
    fake_redis = fakeredis.FakeRedis()
    _seed_cart(fake_redis, user_id, [_cart_item()])
    fake_session = MagicMock()

    class _ValidatorError(Exception):
        pass

    with (
        patch(
            "core_api.services.checkout.validate_stop_list",
            side_effect=_ValidatorError("stop_listed"),
        ),
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
        from core_api.services.checkout import create_order

        with pytest.raises(Exception):
            create_order(
                user_id,
                CreateOrderRequest(type=OrderType.PICKUP),
                fake_redis,
                fake_session,
            )

        assert fake_session.add.called is False


# ---------------------------------------------------------------------------
# 4. RED: сервис checkout — validator wiring (delivery)
# ---------------------------------------------------------------------------


def _delivery_address() -> dict:
    return {"text": "Тверская 1", "lat": 55.76, "lon": 37.61}


def test_create_order_delivery_calls_delivery_validators() -> None:
    """type=DELIVERY → validate_delivery_address и validate_min_delivery_amount вызываются."""
    from core_api.schemas.order import CreateOrderRequest, DeliveryAddress
    from shared.enums import OrderType

    user_id = uuid.uuid4()
    fake_redis = fakeredis.FakeRedis()
    _seed_cart(fake_redis, user_id, [_cart_item()])
    fake_session = MagicMock()

    with (
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address") as mv_addr,
        patch("core_api.services.checkout.validate_min_delivery_amount") as mv_min,
        patch("core_api.services.checkout.validate_promocode", return_value=None),
        patch("core_api.services.checkout.compute_subtotal", return_value=50000),
        patch("core_api.services.checkout.apply_promocode", return_value=(0, 50000)),
        patch("core_api.services.checkout.apply_loyalty_points", return_value=(0, 50000)),
        patch("core_api.services.checkout.compute_delivery_fee", return_value=15000),
        patch("core_api.services.checkout.compute_order_total", return_value=65000),
        patch("core_api.services.checkout.compute_estimated_accrual", return_value=3000),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        from core_api.services.checkout import create_order

        try:
            create_order(
                user_id,
                CreateOrderRequest(
                    type=OrderType.DELIVERY,
                    delivery_address=DeliveryAddress(**_delivery_address()),
                ),
                fake_redis,
                fake_session,
            )
        except Exception:
            pass

        assert mv_addr.called is True
        assert mv_min.called is True


def test_create_order_delivery_calls_delivery_validators_around_subtotal() -> None:
    """Address radius runs before subtotal; delivery minimum runs after subtotal."""
    from core_api.schemas.order import CreateOrderRequest, DeliveryAddress
    from shared.enums import OrderType

    user_id = uuid.uuid4()
    fake_redis = fakeredis.FakeRedis()
    _seed_cart(fake_redis, user_id, [_cart_item()])
    fake_session = MagicMock()

    parent = MagicMock()

    with (
        patch("core_api.services.checkout.validate_stop_list", parent.validate_stop_list),
        patch("core_api.services.checkout.validate_time_slot", parent.validate_time_slot),
        patch(
            "core_api.services.checkout.validate_delivery_address", parent.validate_delivery_address
        ),
        patch(
            "core_api.services.checkout.validate_min_delivery_amount",
            parent.validate_min_delivery_amount,
        ),
        patch("core_api.services.checkout.validate_promocode", return_value=None),
        patch("core_api.services.checkout.compute_subtotal", parent.compute_subtotal) as mv_sub,
        patch("core_api.services.checkout.apply_promocode", return_value=(0, 50000)),
        patch("core_api.services.checkout.apply_loyalty_points", return_value=(0, 50000)),
        patch("core_api.services.checkout.compute_delivery_fee", return_value=15000),
        patch("core_api.services.checkout.compute_order_total", return_value=65000),
        patch("core_api.services.checkout.compute_estimated_accrual", return_value=3000),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        mv_sub.return_value = 50000
        from core_api.services.checkout import create_order

        try:
            create_order(
                user_id,
                CreateOrderRequest(
                    type=OrderType.DELIVERY,
                    delivery_address=DeliveryAddress(**_delivery_address()),
                ),
                fake_redis,
                fake_session,
            )
        except Exception:
            pass

        names = [c[0] for c in parent.mock_calls]
        assert "validate_delivery_address" in names
        assert "validate_min_delivery_amount" in names
        assert "compute_subtotal" in names
        assert names.index("validate_delivery_address") < names.index("compute_subtotal")
        assert names.index("compute_subtotal") < names.index("validate_min_delivery_amount")


def test_create_order_promocode_validator_called_when_code_provided() -> None:
    """promocode_code='SUMMER20' → validate_promocode вызван с кодом."""
    from core_api.schemas.order import CreateOrderRequest
    from shared.enums import OrderType

    user_id = uuid.uuid4()
    fake_redis = fakeredis.FakeRedis()
    _seed_cart(fake_redis, user_id, [_cart_item()])
    fake_session = MagicMock()

    fake_promocode = MagicMock()

    with (
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch(
            "core_api.services.checkout.validate_promocode", return_value=fake_promocode
        ) as mv_promo,
        patch("core_api.services.checkout.compute_subtotal", return_value=50000),
        patch("core_api.services.checkout.apply_promocode", return_value=(5000, 45000)),
        patch("core_api.services.checkout.apply_loyalty_points", return_value=(0, 45000)),
        patch("core_api.services.checkout.compute_delivery_fee", return_value=0),
        patch("core_api.services.checkout.compute_order_total", return_value=45000),
        patch("core_api.services.checkout.compute_estimated_accrual", return_value=2250),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        from core_api.services.checkout import create_order

        try:
            create_order(
                user_id,
                CreateOrderRequest(type=OrderType.PICKUP, promocode_code="SUMMER20"),
                fake_redis,
                fake_session,
            )
        except Exception:
            pass

        assert mv_promo.called is True
        # Код должен фигурировать среди аргументов (позиционно или по имени)
        first_call = mv_promo.call_args
        flat_args = list(first_call.args) + list(first_call.kwargs.values())
        assert "SUMMER20" in flat_args


# ---------------------------------------------------------------------------
# 5. RED: сервис checkout — pricing chain order
# ---------------------------------------------------------------------------


def test_create_order_pricing_chain_order() -> None:
    """§7.2: compute_subtotal → apply_promocode → apply_loyalty_points → compute_order_total → compute_estimated_accrual."""
    from core_api.schemas.order import CreateOrderRequest
    from shared.enums import OrderType

    user_id = uuid.uuid4()
    fake_redis = fakeredis.FakeRedis()
    _seed_cart(fake_redis, user_id, [_cart_item()])
    fake_session = MagicMock()

    parent = MagicMock()

    with (
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.validate_promocode", return_value=None),
        patch(
            "core_api.services.checkout.compute_subtotal", parent.compute_subtotal
        ) as mv_sub,
        patch(
            "core_api.services.checkout.apply_promocode", parent.apply_promocode
        ) as mv_promo,
        patch(
            "core_api.services.checkout.apply_loyalty_points", parent.apply_loyalty_points
        ) as mv_points,
        patch("core_api.services.checkout.compute_delivery_fee", return_value=0),
        patch(
            "core_api.services.checkout.compute_order_total", parent.compute_order_total
        ) as mv_total,
        patch(
            "core_api.services.checkout.compute_estimated_accrual",
            parent.compute_estimated_accrual,
        ) as mv_acc,
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        mv_sub.return_value = 50000
        mv_promo.return_value = (0, 50000)
        mv_points.return_value = (0, 50000)
        mv_total.return_value = 50000
        mv_acc.return_value = 2500

        from core_api.services.checkout import create_order

        try:
            create_order(
                user_id,
                CreateOrderRequest(type=OrderType.PICKUP, points_to_use=0),
                fake_redis,
                fake_session,
            )
        except Exception:
            pass

        names = [c[0] for c in parent.mock_calls]
        expected_order = [
            "compute_subtotal",
            "apply_promocode",
            "apply_loyalty_points",
            "compute_order_total",
            "compute_estimated_accrual",
        ]
        indices = [names.index(n) for n in expected_order]
        assert indices == sorted(indices), (
            f"Порядок pricing-функций нарушен: {[(n, names.index(n)) for n in expected_order]}"
        )


def test_create_order_pricing_delivery_includes_delivery_fee() -> None:
    """type=DELIVERY → compute_delivery_fee вызывается, его значение попадает в compute_order_total."""
    from core_api.schemas.order import CreateOrderRequest, DeliveryAddress
    from shared.enums import OrderType

    user_id = uuid.uuid4()
    fake_redis = fakeredis.FakeRedis()
    _seed_cart(fake_redis, user_id, [_cart_item()])
    fake_session = MagicMock()

    with (
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.validate_promocode", return_value=None),
        patch("core_api.services.checkout.compute_subtotal", return_value=50000),
        patch("core_api.services.checkout.apply_promocode", return_value=(0, 50000)),
        patch("core_api.services.checkout.apply_loyalty_points", return_value=(0, 50000)),
        patch(
            "core_api.services.checkout.compute_delivery_fee", return_value=15000
        ) as mv_fee,
        patch(
            "core_api.services.checkout.compute_order_total", return_value=65000
        ) as mv_total,
        patch("core_api.services.checkout.compute_estimated_accrual", return_value=3000),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        from core_api.services.checkout import create_order

        try:
            create_order(
                user_id,
                CreateOrderRequest(
                    type=OrderType.DELIVERY,
                    delivery_address=DeliveryAddress(**_delivery_address()),
                ),
                fake_redis,
                fake_session,
            )
        except Exception:
            pass

        assert mv_fee.called is True
        assert mv_total.called is True
        # 15000 (fee) должен фигурировать в аргументах compute_order_total
        total_call = mv_total.call_args
        flat = list(total_call.args) + list(total_call.kwargs.values())
        assert 15000 in flat


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (JSONB, enum, FK)")
def test_create_order_pricing_uses_fresh_prices_from_db(
    cart_redis, db_session, _checkout_user
) -> None:
    """orders.subtotal == menu_item.base_price × quantity, прочитанное из БД."""
    from tests._factories.menu import make_menu_item

    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order
    from shared.enums import OrderType
    from shared.models import Order

    user_id, _ = _checkout_user
    item = make_menu_item(db_session, base_price=17000)
    db_session.flush()

    _seed_cart(
        cart_redis,
        user_id,
        [
            {
                "menu_item_id": item.id,
                "size_option_id": None,
                "modifier_ids": [],
                "quantity": 3,
            }
        ],
    )

    with (
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.validate_promocode", return_value=None),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        create_order(
            user_id,
            CreateOrderRequest(type=OrderType.PICKUP),
            cart_redis,
            db_session,
        )

    order = db_session.query(Order).filter(Order.user_id == user_id).one()
    assert order.subtotal == 17000 * 3


# ---------------------------------------------------------------------------
# 6. RED: сервис checkout — DB persistence (total > 0)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_order_inserts_order_row_with_status_created(
    cart_redis, db_session, _checkout_user
) -> None:
    """orders.status == CREATED, type == PICKUP, total > 0."""
    from tests._factories.menu import make_menu_item

    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order
    from shared.enums import OrderStatus, OrderType
    from shared.models import Order

    user_id, _ = _checkout_user
    item = make_menu_item(db_session, base_price=15000)
    db_session.flush()
    _seed_cart(
        cart_redis,
        user_id,
        [{"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 2}],
    )

    with (
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.validate_promocode", return_value=None),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        create_order(
            user_id,
            CreateOrderRequest(type=OrderType.PICKUP),
            cart_redis,
            db_session,
        )

    order = db_session.query(Order).filter(Order.user_id == user_id).one()
    assert order.status == OrderStatus.CREATED
    assert order.type == OrderType.PICKUP
    assert order.user_id == user_id
    assert order.total > 0


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_order_inserts_order_items_with_snapshots(
    cart_redis, db_session, _checkout_user
) -> None:
    """OrderItem.menu_item_name_ru / unit_price / quantity / modifiers_snapshot заполнены."""
    from tests._factories.menu import make_menu_item

    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order
    from shared.enums import OrderType
    from shared.models import Order, OrderItem

    user_id, _ = _checkout_user
    item = make_menu_item(db_session, name_ru="Латте", name_en="Latte", base_price=15000)
    db_session.flush()
    _seed_cart(
        cart_redis,
        user_id,
        [{"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 2}],
    )

    with (
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.validate_promocode", return_value=None),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        create_order(
            user_id,
            CreateOrderRequest(type=OrderType.PICKUP),
            cart_redis,
            db_session,
        )

    order = db_session.query(Order).filter(Order.user_id == user_id).one()
    oi = db_session.query(OrderItem).filter(OrderItem.order_id == order.id).one()
    assert oi.menu_item_name_ru == "Латте"
    assert oi.unit_price == 15000
    assert oi.quantity == 2
    assert isinstance(oi.modifiers_snapshot, list)


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_order_item_stores_menu_item_id_as_reference_not_fk(
    cart_redis, db_session, _checkout_user
) -> None:
    """После архивирования MenuItem строка OrderItem уцелевает (нет FK каскада)."""
    from tests._factories.menu import make_menu_item

    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order
    from shared.enums import OrderType
    from shared.models import Order, OrderItem

    user_id, _ = _checkout_user
    item = make_menu_item(db_session, base_price=15000)
    db_session.flush()
    original_id = item.id
    _seed_cart(
        cart_redis,
        user_id,
        [{"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 1}],
    )

    with (
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.validate_promocode", return_value=None),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        create_order(
            user_id,
            CreateOrderRequest(type=OrderType.PICKUP),
            cart_redis,
            db_session,
        )

    order = db_session.query(Order).filter(Order.user_id == user_id).one()

    # Архивируем MenuItem
    item.archived = True
    db_session.flush()

    oi = db_session.query(OrderItem).filter(OrderItem.order_id == order.id).one()
    assert oi.menu_item_id == original_id


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_order_inserts_payment_with_pending_status_and_idempotency_key(
    cart_redis, db_session, _checkout_user
) -> None:
    """Payment: status=PENDING, amount=total, idempotency_key не пуст."""
    from tests._factories.menu import make_menu_item

    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order
    from shared.enums import OrderType, PaymentStatus
    from shared.models import Order, Payment

    user_id, _ = _checkout_user
    item = make_menu_item(db_session, base_price=25000)
    db_session.flush()
    _seed_cart(
        cart_redis,
        user_id,
        [{"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 1}],
    )

    with (
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.validate_promocode", return_value=None),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        create_order(
            user_id,
            CreateOrderRequest(type=OrderType.PICKUP),
            cart_redis,
            db_session,
        )

    order = db_session.query(Order).filter(Order.user_id == user_id).one()
    payment = db_session.query(Payment).filter(Payment.order_id == order.id).one()
    assert payment.status == PaymentStatus.PENDING
    assert payment.amount == order.total
    assert payment.idempotency_key is not None
    assert len(payment.idempotency_key) > 0


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_order_payment_amount_matches_order_total(
    cart_redis, db_session, _checkout_user
) -> None:
    """payment.amount == order.total."""
    from tests._factories.menu import make_menu_item

    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order
    from shared.enums import OrderType
    from shared.models import Order, Payment

    user_id, _ = _checkout_user
    item = make_menu_item(db_session, base_price=15000)
    db_session.flush()
    _seed_cart(
        cart_redis,
        user_id,
        [{"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 2}],
    )

    with (
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.validate_promocode", return_value=None),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        create_order(
            user_id,
            CreateOrderRequest(type=OrderType.PICKUP),
            cart_redis,
            db_session,
        )

    order = db_session.query(Order).filter(Order.user_id == user_id).one()
    payment = db_session.query(Payment).filter(Payment.order_id == order.id).one()
    assert payment.amount == order.total


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_order_order_items_count_matches_cart_lines(
    cart_redis, db_session, _checkout_user
) -> None:
    """3 строки в корзине → 3 OrderItem."""
    from tests._factories.menu import make_menu_item

    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order
    from shared.enums import OrderType
    from shared.models import Order, OrderItem

    user_id, _ = _checkout_user
    item1 = make_menu_item(db_session, name_ru="A", name_en="A", base_price=10000)
    item2 = make_menu_item(db_session, name_ru="B", name_en="B", base_price=12000)
    item3 = make_menu_item(db_session, name_ru="C", name_en="C", base_price=14000)
    db_session.flush()
    _seed_cart(
        cart_redis,
        user_id,
        [
            {"menu_item_id": item1.id, "size_option_id": None, "modifier_ids": [], "quantity": 1},
            {"menu_item_id": item2.id, "size_option_id": None, "modifier_ids": [], "quantity": 1},
            {"menu_item_id": item3.id, "size_option_id": None, "modifier_ids": [], "quantity": 1},
        ],
    )

    with (
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.validate_promocode", return_value=None),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        create_order(
            user_id,
            CreateOrderRequest(type=OrderType.PICKUP),
            cart_redis,
            db_session,
        )

    order = db_session.query(Order).filter(Order.user_id == user_id).one()
    count = db_session.query(OrderItem).filter(OrderItem.order_id == order.id).count()
    assert count == 3


# ---------------------------------------------------------------------------
# 7. RED: сервис checkout — резервирование баллов лояльности
# ---------------------------------------------------------------------------


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_order_with_loyalty_points_creates_reservation_transaction(
    cart_redis, db_session, _checkout_user
) -> None:
    """points_to_use=5000 → LoyaltyTransaction(type=RESERVATION, amount=-5000)."""
    from tests._factories.menu import make_menu_item

    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order
    from shared.enums import LoyaltyTransactionType, OrderType
    from shared.models import LoyaltyAccount, LoyaltyTransaction, Order

    user_id, _ = _checkout_user
    account = db_session.get(LoyaltyAccount, user_id)
    account.balance = 10000
    db_session.flush()

    item = make_menu_item(db_session, base_price=30000)
    db_session.flush()
    _seed_cart(
        cart_redis,
        user_id,
        [{"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 1}],
    )

    with (
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.validate_promocode", return_value=None),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        create_order(
            user_id,
            CreateOrderRequest(type=OrderType.PICKUP, points_to_use=5000),
            cart_redis,
            db_session,
        )

    order = db_session.query(Order).filter(Order.user_id == user_id).one()
    tx = (
        db_session.query(LoyaltyTransaction)
        .filter(LoyaltyTransaction.order_id == order.id)
        .one()
    )
    assert tx.type == LoyaltyTransactionType.RESERVATION
    assert tx.amount == -5000
    assert tx.user_id == user_id


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_order_with_loyalty_points_debits_account_balance(
    cart_redis, db_session, _checkout_user
) -> None:
    """После резервации 5000 из 10000 → balance == 5000."""
    from tests._factories.menu import make_menu_item

    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order
    from shared.enums import OrderType
    from shared.models import LoyaltyAccount

    user_id, _ = _checkout_user
    account = db_session.get(LoyaltyAccount, user_id)
    account.balance = 10000
    db_session.flush()

    item = make_menu_item(db_session, base_price=30000)
    db_session.flush()
    _seed_cart(
        cart_redis,
        user_id,
        [{"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 1}],
    )

    with (
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.validate_promocode", return_value=None),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        create_order(
            user_id,
            CreateOrderRequest(type=OrderType.PICKUP, points_to_use=5000),
            cart_redis,
            db_session,
        )

    db_session.refresh(account)
    assert account.balance == 5000


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_order_records_points_used_in_order_row(
    cart_redis, db_session, _checkout_user
) -> None:
    """order.points_used == 5000."""
    from tests._factories.menu import make_menu_item

    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order
    from shared.enums import OrderType
    from shared.models import LoyaltyAccount, Order

    user_id, _ = _checkout_user
    account = db_session.get(LoyaltyAccount, user_id)
    account.balance = 10000
    db_session.flush()

    item = make_menu_item(db_session, base_price=30000)
    db_session.flush()
    _seed_cart(
        cart_redis,
        user_id,
        [{"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 1}],
    )

    with (
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.validate_promocode", return_value=None),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        create_order(
            user_id,
            CreateOrderRequest(type=OrderType.PICKUP, points_to_use=5000),
            cart_redis,
            db_session,
        )

    order = db_session.query(Order).filter(Order.user_id == user_id).one()
    assert order.points_used == 5000


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_order_without_points_skips_loyalty_transaction(
    cart_redis, db_session, _checkout_user
) -> None:
    """points_to_use=0 → нет LoyaltyTransaction по заказу."""
    from tests._factories.menu import make_menu_item

    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order
    from shared.enums import OrderType
    from shared.models import LoyaltyTransaction, Order

    user_id, _ = _checkout_user
    item = make_menu_item(db_session, base_price=15000)
    db_session.flush()
    _seed_cart(
        cart_redis,
        user_id,
        [{"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 1}],
    )

    with (
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.validate_promocode", return_value=None),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        create_order(
            user_id,
            CreateOrderRequest(type=OrderType.PICKUP, points_to_use=0),
            cart_redis,
            db_session,
        )

    order = db_session.query(Order).filter(Order.user_id == user_id).one()
    txs = db_session.query(LoyaltyTransaction).filter(LoyaltyTransaction.order_id == order.id).all()
    assert txs == []


# ---------------------------------------------------------------------------
# 8. RED: сервис checkout — промокоды
# ---------------------------------------------------------------------------


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_order_with_promocode_increments_current_uses(
    cart_redis, db_session, _checkout_user
) -> None:
    """promocode.current_uses += 1 после commit."""
    from tests._factories.menu import make_menu_item

    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order
    from shared.enums import OrderType, PromocodeDiscountType
    from shared.models import Promocode

    user_id, _ = _checkout_user
    promo = Promocode(
        code="SUMMER20",
        discount_type=PromocodeDiscountType.PERCENT,
        discount_value=20,
        current_uses=3,
        is_active=True,
    )
    db_session.add(promo)
    db_session.flush()

    item = make_menu_item(db_session, base_price=20000)
    db_session.flush()
    _seed_cart(
        cart_redis,
        user_id,
        [{"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 1}],
    )

    with (
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.validate_promocode", return_value=promo),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        create_order(
            user_id,
            CreateOrderRequest(type=OrderType.PICKUP, promocode_code="SUMMER20"),
            cart_redis,
            db_session,
        )

    db_session.refresh(promo)
    assert promo.current_uses == 4


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_order_with_promocode_inserts_promocode_usage_row(
    cart_redis, db_session, _checkout_user
) -> None:
    """Одна строка PromocodeUsage с promocode_id, user_id, order_id."""
    from tests._factories.menu import make_menu_item

    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order
    from shared.enums import OrderType, PromocodeDiscountType
    from shared.models import Order, Promocode, PromocodeUsage

    user_id, _ = _checkout_user
    promo = Promocode(
        code="SUMMER20",
        discount_type=PromocodeDiscountType.PERCENT,
        discount_value=20,
        current_uses=0,
        is_active=True,
    )
    db_session.add(promo)
    db_session.flush()

    item = make_menu_item(db_session, base_price=20000)
    db_session.flush()
    _seed_cart(
        cart_redis,
        user_id,
        [{"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 1}],
    )

    with (
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.validate_promocode", return_value=promo),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        create_order(
            user_id,
            CreateOrderRequest(type=OrderType.PICKUP, promocode_code="SUMMER20"),
            cart_redis,
            db_session,
        )

    order = db_session.query(Order).filter(Order.user_id == user_id).one()
    usages = (
        db_session.query(PromocodeUsage)
        .filter(
            PromocodeUsage.order_id == order.id,
            PromocodeUsage.user_id == user_id,
            PromocodeUsage.promocode_id == promo.id,
        )
        .all()
    )
    assert len(usages) == 1


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_order_without_promocode_skips_promocode_usage(
    cart_redis, db_session, _checkout_user
) -> None:
    """promocode_code=None → нет PromocodeUsage и orders.promocode_id IS NULL."""
    from tests._factories.menu import make_menu_item

    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order
    from shared.enums import OrderType
    from shared.models import Order, PromocodeUsage

    user_id, _ = _checkout_user
    item = make_menu_item(db_session, base_price=15000)
    db_session.flush()
    _seed_cart(
        cart_redis,
        user_id,
        [{"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 1}],
    )

    with (
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.validate_promocode", return_value=None),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        create_order(
            user_id,
            CreateOrderRequest(type=OrderType.PICKUP, promocode_code=None),
            cart_redis,
            db_session,
        )

    order = db_session.query(Order).filter(Order.user_id == user_id).one()
    usages = db_session.query(PromocodeUsage).filter(PromocodeUsage.order_id == order.id).all()
    assert usages == []
    assert order.promocode_id is None


def test_create_order_stores_discount_amount_on_order() -> None:
    """apply_promocode → discount=15000 попадает в order.discount_amount (unit-тест с моками)."""
    # Проверяем через мок-сессию: смотрим аргументы Order(...) перехватом add()
    from core_api.schemas.order import CreateOrderRequest
    from shared.enums import OrderType

    user_id = uuid.uuid4()
    fake_redis = fakeredis.FakeRedis()
    _seed_cart(fake_redis, user_id, [_cart_item()])
    fake_session = MagicMock()

    added_objects: list[Any] = []
    fake_session.add.side_effect = lambda o: added_objects.append(o)

    with (
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.validate_promocode", return_value=None),
        patch("core_api.services.checkout.compute_subtotal", return_value=50000),
        patch("core_api.services.checkout.apply_promocode", return_value=(15000, 35000)),
        patch("core_api.services.checkout.apply_loyalty_points", return_value=(0, 35000)),
        patch("core_api.services.checkout.compute_delivery_fee", return_value=0),
        patch("core_api.services.checkout.compute_order_total", return_value=35000),
        patch("core_api.services.checkout.compute_estimated_accrual", return_value=1750),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        from core_api.services.checkout import create_order
        from shared.models import Order

        try:
            create_order(
                user_id,
                CreateOrderRequest(type=OrderType.PICKUP),
                fake_redis,
                fake_session,
            )
        except Exception:
            pass

        orders = [o for o in added_objects if isinstance(o, Order)]
        assert orders, "ни один Order не был передан в session.add"
        assert orders[0].discount_amount == 15000


# ---------------------------------------------------------------------------
# 9. RED: сервис checkout — shortcut total=0 (loyalty покрывает всё)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_order_total_zero_commits_order_as_paid(
    cart_redis, db_session, _checkout_user
) -> None:
    """total=0 → OrderResponse.status == PAID и в БД status == PAID."""
    from tests._factories.menu import make_menu_item

    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order
    from shared.enums import OrderStatus, OrderType
    from shared.models import LoyaltyAccount, Order

    user_id, _ = _checkout_user
    account = db_session.get(LoyaltyAccount, user_id)
    account.balance = 100000
    db_session.flush()

    item = make_menu_item(db_session, base_price=20000)
    db_session.flush()
    _seed_cart(
        cart_redis,
        user_id,
        [{"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 1}],
    )

    with (
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
        resp = create_order(
            user_id,
            CreateOrderRequest(type=OrderType.PICKUP, points_to_use=20000),
            cart_redis,
            db_session,
        )

    assert resp.status == OrderStatus.PAID
    order = db_session.query(Order).filter(Order.user_id == user_id).one()
    assert order.status == OrderStatus.PAID


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_order_total_zero_creates_loyalty_transaction_as_redemption(
    cart_redis, db_session, _checkout_user
) -> None:
    """total=0 + points_used>0 → LoyaltyTransaction.type == REDEMPTION."""
    from tests._factories.menu import make_menu_item

    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order
    from shared.enums import LoyaltyTransactionType, OrderType
    from shared.models import LoyaltyAccount, LoyaltyTransaction, Order

    user_id, _ = _checkout_user
    account = db_session.get(LoyaltyAccount, user_id)
    account.balance = 100000
    db_session.flush()

    item = make_menu_item(db_session, base_price=20000)
    db_session.flush()
    _seed_cart(
        cart_redis,
        user_id,
        [{"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 1}],
    )

    with (
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
        create_order(
            user_id,
            CreateOrderRequest(type=OrderType.PICKUP, points_to_use=20000),
            cart_redis,
            db_session,
        )

    order = db_session.query(Order).filter(Order.user_id == user_id).one()
    tx = (
        db_session.query(LoyaltyTransaction)
        .filter(LoyaltyTransaction.order_id == order.id)
        .one()
    )
    assert tx.type == LoyaltyTransactionType.REDEMPTION


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_order_total_zero_deletes_cart_from_redis(
    cart_redis, db_session, _checkout_user
) -> None:
    """total=0 → cart:{user_id} удалён из Redis после коммита."""
    from tests._factories.menu import make_menu_item

    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order
    from shared.enums import OrderType
    from shared.models import LoyaltyAccount

    user_id, _ = _checkout_user
    account = db_session.get(LoyaltyAccount, user_id)
    account.balance = 100000
    db_session.flush()

    item = make_menu_item(db_session, base_price=20000)
    db_session.flush()
    _seed_cart(
        cart_redis,
        user_id,
        [{"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 1}],
    )

    with (
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
        create_order(
            user_id,
            CreateOrderRequest(type=OrderType.PICKUP, points_to_use=20000),
            cart_redis,
            db_session,
        )

    assert cart_redis.exists(f"cart:{user_id}") == 0


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_order_total_zero_does_not_enqueue_celery_task(
    cart_redis, db_session, _checkout_user
) -> None:
    """total=0 → enqueue_payment_task НЕ вызывается."""
    from tests._factories.menu import make_menu_item

    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order
    from shared.enums import OrderType
    from shared.models import LoyaltyAccount

    user_id, _ = _checkout_user
    account = db_session.get(LoyaltyAccount, user_id)
    account.balance = 100000
    db_session.flush()

    item = make_menu_item(db_session, base_price=20000)
    db_session.flush()
    _seed_cart(
        cart_redis,
        user_id,
        [{"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 1}],
    )

    with (
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
        patch("core_api.services.checkout.enqueue_payment_task") as mv_enqueue,
    ):
        create_order(
            user_id,
            CreateOrderRequest(type=OrderType.PICKUP, points_to_use=20000),
            cart_redis,
            db_session,
        )

        assert mv_enqueue.called is False


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_order_total_zero_payment_row_has_amount_zero(
    cart_redis, db_session, _checkout_user
) -> None:
    """total=0 → Payment.amount == 0."""
    from tests._factories.menu import make_menu_item

    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order
    from shared.enums import OrderType
    from shared.models import LoyaltyAccount, Order, Payment

    user_id, _ = _checkout_user
    account = db_session.get(LoyaltyAccount, user_id)
    account.balance = 100000
    db_session.flush()

    item = make_menu_item(db_session, base_price=20000)
    db_session.flush()
    _seed_cart(
        cart_redis,
        user_id,
        [{"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 1}],
    )

    with (
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
        create_order(
            user_id,
            CreateOrderRequest(type=OrderType.PICKUP, points_to_use=20000),
            cart_redis,
            db_session,
        )

    order = db_session.query(Order).filter(Order.user_id == user_id).one()
    payment = db_session.query(Payment).filter(Payment.order_id == order.id).one()
    assert payment.amount == 0


# ---------------------------------------------------------------------------
# 10. RED: сервис checkout — total > 0 → Celery enqueue
# ---------------------------------------------------------------------------


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_order_total_positive_enqueues_celery_task(
    cart_redis, db_session, _checkout_user
) -> None:
    """total>0 → enqueue_payment_task вызван с order_id / total / idempotency_key."""
    from tests._factories.menu import make_menu_item

    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order
    from shared.enums import OrderType
    from shared.models import Order

    user_id, _ = _checkout_user
    item = make_menu_item(db_session, base_price=25000)
    db_session.flush()
    _seed_cart(
        cart_redis,
        user_id,
        [{"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 1}],
    )

    with (
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.validate_promocode", return_value=None),
        patch("core_api.services.checkout.enqueue_payment_task") as mv_enqueue,
    ):
        create_order(
            user_id,
            CreateOrderRequest(type=OrderType.PICKUP),
            cart_redis,
            db_session,
        )

    assert mv_enqueue.call_count == 1
    order = db_session.query(Order).filter(Order.user_id == user_id).one()

    call_args = mv_enqueue.call_args
    flat_kwargs = call_args.kwargs
    flat_args = list(call_args.args)
    flat = [*flat_args, *flat_kwargs.values()]
    assert order.id in flat
    assert order.total in flat
    # idempotency_key — непустая строка в аргументах
    assert any(isinstance(v, str) and len(v) > 0 for v in flat)


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_order_total_positive_leaves_cart_in_redis(
    cart_redis, db_session, _checkout_user
) -> None:
    """total>0 → cart:{user_id} остаётся в Redis (удаление только на PAID per §6.1)."""
    from tests._factories.menu import make_menu_item

    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order
    from shared.enums import OrderType

    user_id, _ = _checkout_user
    item = make_menu_item(db_session, base_price=25000)
    db_session.flush()
    _seed_cart(
        cart_redis,
        user_id,
        [{"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 1}],
    )

    with (
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.validate_promocode", return_value=None),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        create_order(
            user_id,
            CreateOrderRequest(type=OrderType.PICKUP),
            cart_redis,
            db_session,
        )

    assert cart_redis.exists(f"cart:{user_id}") == 1


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_order_total_positive_returns_created_status(
    cart_redis, db_session, _checkout_user
) -> None:
    """total>0 → OrderResponse.status == CREATED, confirmation_url is None (worker не отработал)."""
    from tests._factories.menu import make_menu_item

    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order
    from shared.enums import OrderStatus, OrderType

    user_id, _ = _checkout_user
    item = make_menu_item(db_session, base_price=25000)
    db_session.flush()
    _seed_cart(
        cart_redis,
        user_id,
        [{"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 1}],
    )

    with (
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.validate_promocode", return_value=None),
        patch("core_api.services.checkout.enqueue_payment_task"),
    ):
        resp = create_order(
            user_id,
            CreateOrderRequest(type=OrderType.PICKUP),
            cart_redis,
            db_session,
        )

    assert resp.status == OrderStatus.CREATED
    assert resp.confirmation_url is None


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")
def test_create_order_enqueues_after_db_commit(
    cart_redis, db_session, _checkout_user
) -> None:
    """enqueue_payment_task вызывается ПОСЛЕ коммита: в момент вызова Order уже в БД."""
    from tests._factories.menu import make_menu_item

    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order
    from shared.enums import OrderType
    from shared.models import Order

    user_id, _ = _checkout_user
    item = make_menu_item(db_session, base_price=25000)
    db_session.flush()
    _seed_cart(
        cart_redis,
        user_id,
        [{"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 1}],
    )

    found_in_db: list[bool] = []

    def _record_presence(*args, **kwargs) -> None:
        # Проверяем, что Order уже виден в БД (т.е. commit произошёл)
        order = db_session.query(Order).filter(Order.user_id == user_id).first()
        found_in_db.append(order is not None)

    with (
        patch("core_api.services.checkout.validate_stop_list"),
        patch("core_api.services.checkout.validate_time_slot"),
        patch("core_api.services.checkout.validate_delivery_address"),
        patch("core_api.services.checkout.validate_min_delivery_amount"),
        patch("core_api.services.checkout.validate_promocode", return_value=None),
        patch(
            "core_api.services.checkout.enqueue_payment_task",
            side_effect=_record_presence,
        ),
    ):
        create_order(
            user_id,
            CreateOrderRequest(type=OrderType.PICKUP),
            cart_redis,
            db_session,
        )

    assert found_in_db == [True]
