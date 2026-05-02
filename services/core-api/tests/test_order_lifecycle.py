"""RED: тесты state machine заказа `core_api.services.order_lifecycle.transition_order`.

Покрывают PDD §6.1 (все разрешённые/запрещённые переходы), INV-010 (ролевой
контроль), INV-016 (исчерпывающий allow-list), INV-003 (начисление лояльности
при COMPLETED).

Все импорты целевых модулей делаются ВНУТРИ тестов — в RED-цикле
`core_api.services.order_lifecycle` не существует, и импорт на уровне модуля
сорвал бы сбор файла.
"""
from __future__ import annotations

import itertools
import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Хелперы: сидируем User + Order + LoyaltyAccount в sqlite-сессии conftest.
# ---------------------------------------------------------------------------

def _fresh_session() -> Session:
    from core_api.deps.database import SessionLocal

    return SessionLocal()


def _seed_user(db: Session) -> uuid.UUID:
    from shared.models import User
    from shared.enums import UserStatus

    u = User(
        phone_hash=uuid.uuid4().hex,
        status=UserStatus.ACTIVE,
    )
    db.add(u)
    db.flush()
    return u.id


def _seed_loyalty(db: Session, user_id: uuid.UUID, balance: int = 0) -> None:
    from shared.models import LoyaltyAccount

    acct = LoyaltyAccount(user_id=user_id, balance=balance)
    db.add(acct)
    db.flush()


def _seed_order(
    db: Session,
    *,
    status: str,
    order_type: str = "pickup",
    total: int = 50000,
    delivery_fee: int = 0,
    points_used: int = 0,
    user_id: uuid.UUID | None = None,
    promocode_id: uuid.UUID | None = None,
) -> uuid.UUID:
    from shared.models import Order
    from shared.enums import OrderStatus, OrderType

    uid = user_id or _seed_user(db)
    _seed_loyalty(db, uid)
    o = Order(
        user_id=uid,
        status=OrderStatus(status),
        type=OrderType(order_type),
        subtotal=total,
        discount_amount=0,
        points_used=points_used,
        delivery_fee=delivery_fee,
        total=total,
        estimated_accrual=0,
        promocode_id=promocode_id,
    )
    db.add(o)
    db.flush()
    return o.id


def _seed_shop_settings(db: Session, *, loyalty_percent: int = 5) -> None:
    from shared.models import ShopSettings

    # Singleton с id=1; если уже есть — обновляем loyalty_percent.
    existing = db.get(ShopSettings, 1)
    if existing is not None:
        existing.loyalty_percent = loyalty_percent
        db.flush()
        return

    db.add(
        ShopSettings(
            id=1,
            shop_lat=55.7,
            shop_lon=37.6,
            delivery_radius_km=5.0,
            min_delivery_amount=0,
            free_delivery_threshold=0,
            delivery_fee=15000,
            loyalty_percent=loyalty_percent,
            default_prep_time_minutes=15,
            estimated_delivery_time_minutes=30,
            working_hours={"mon": "08-22"},
        )
    )
    db.flush()


@pytest.fixture
def db() -> Session:
    """Короткая сессия для каждого теста — тесты чистят за собой через rollback."""
    s = _fresh_session()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture
def notify_mock(monkeypatch):
    """Подмена `send_order_notification` в модуле order_notifications.

    В RED цикле модуля ещё нет — создаём пустой stub в sys.modules, чтобы
    импорты сервиса (`from core_api.services.order_notifications import ...`)
    падали на стороне SUT, а не теста. Но если GREEN уже добавил модуль,
    монkey-патч просто перезапишет функцию.
    """
    import sys
    import types

    mod_name = "core_api.services.order_notifications"
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)
    mock = MagicMock()
    monkeypatch.setattr(
        sys.modules[mod_name],
        "send_order_notification",
        mock,
        raising=False,
    )
    # Также патчим путь, по которому SUT ре-экспортирует функцию после импорта.
    try:
        import core_api.services.order_lifecycle as sut  # noqa: F401
        monkeypatch.setattr(sut, "send_order_notification", mock, raising=False)
    except ModuleNotFoundError:
        pass
    return mock


# ---------------------------------------------------------------------------
# 1.1 — import probe
# ---------------------------------------------------------------------------

def test_order_lifecycle_module_exists() -> None:
    from core_api.services.order_lifecycle import (  # noqa: F401
        OrderTransitionError,
        transition_order,
    )


# ---------------------------------------------------------------------------
# Happy-path transitions
# ---------------------------------------------------------------------------

def test_paid_to_preparing_barista_happy_path(db: Session, notify_mock: MagicMock) -> None:
    from core_api.services.order_lifecycle import transition_order
    from shared.enums import OrderStatus
    from shared.models import Order

    oid = _seed_order(db, status="paid", order_type="pickup")
    transition_order(oid, OrderStatus.PREPARING, "barista", db)

    updated = db.get(Order, oid)
    assert updated.status == OrderStatus.PREPARING
    assert notify_mock.call_count == 1


# GRACE-LDD: order status transitions emit required tx/state/commit markers.
def test_transition_order_emits_ldd_markers(
    db: Session,
    notify_mock: MagicMock,
    grace_logs,
) -> None:
    from core_api.services.order_lifecycle import transition_order
    from shared.enums import OrderStatus

    oid = _seed_order(db, status="paid", order_type="pickup")

    transition_order(oid, OrderStatus.PREPARING, "barista", db)

    grace_logs.assert_trajectory(
        ("order_lifecycle.transition_order", "BLOCK_TX_BEGIN"),
        ("order_lifecycle.transition_order", "BLOCK_STATE_TRANSITION"),
        ("order_lifecycle.transition_order", "BLOCK_TX_COMMIT"),
    )
    assert grace_logs.beliefs(status="MISMATCH") == []
    joined_logs = "\n".join(grace_logs.lines)
    assert "phone" not in joined_logs.lower()
    assert "address" not in joined_logs.lower()


def test_paid_to_cancelled_admin_happy_path(db: Session, notify_mock: MagicMock) -> None:
    from core_api.services.order_lifecycle import transition_order
    from shared.enums import OrderStatus
    from shared.models import Order

    oid = _seed_order(db, status="paid")
    transition_order(oid, OrderStatus.CANCELLED, "admin", db)

    updated = db.get(Order, oid)
    assert updated.status == OrderStatus.CANCELLED
    assert notify_mock.call_count == 1


def test_preparing_to_ready_barista_happy_path(db: Session, notify_mock: MagicMock) -> None:
    from core_api.services.order_lifecycle import transition_order
    from shared.enums import OrderStatus
    from shared.models import Order

    oid = _seed_order(db, status="preparing")
    transition_order(oid, OrderStatus.READY, "barista", db)

    updated = db.get(Order, oid)
    assert updated.status == OrderStatus.READY
    assert notify_mock.call_count == 1


def test_preparing_to_cancelled_admin_only(db: Session, notify_mock: MagicMock) -> None:
    from core_api.services.order_lifecycle import (
        OrderTransitionError,
        transition_order,
    )
    from shared.enums import OrderStatus
    from shared.models import Order

    # ADMIN allowed
    oid_admin = _seed_order(db, status="preparing")
    transition_order(oid_admin, OrderStatus.CANCELLED, "admin", db)
    assert db.get(Order, oid_admin).status == OrderStatus.CANCELLED

    # BARISTA rejected
    oid_barista = _seed_order(db, status="preparing")
    with pytest.raises(OrderTransitionError) as ei:
        transition_order(oid_barista, OrderStatus.CANCELLED, "barista", db)
    assert ei.value.reason == "role_not_allowed"
    assert db.get(Order, oid_barista).status == OrderStatus.PREPARING


def test_ready_to_in_delivery_courier_happy_path(
    db: Session, notify_mock: MagicMock
) -> None:
    from core_api.services.order_lifecycle import transition_order
    from shared.enums import OrderStatus
    from shared.models import Order

    oid = _seed_order(db, status="ready", order_type="delivery")
    transition_order(oid, OrderStatus.IN_DELIVERY, "courier", db)

    assert db.get(Order, oid).status == OrderStatus.IN_DELIVERY
    assert notify_mock.call_count == 1


def test_ready_to_in_delivery_rejects_pickup_order(
    db: Session, notify_mock: MagicMock
) -> None:
    from core_api.services.order_lifecycle import (
        OrderTransitionError,
        transition_order,
    )
    from shared.enums import OrderStatus
    from shared.models import Order

    oid = _seed_order(db, status="ready", order_type="pickup")
    with pytest.raises(OrderTransitionError) as ei:
        transition_order(oid, OrderStatus.IN_DELIVERY, "courier", db)
    assert ei.value.reason == "wrong_order_type_for_transition"
    assert db.get(Order, oid).status == OrderStatus.READY
    assert notify_mock.call_count == 0


# GRACE-LDD: forbidden transition validation emits no state or commit marker.
def test_forbidden_transition_emits_no_state_or_commit_marker(
    db: Session,
    notify_mock: MagicMock,
    grace_logs,
) -> None:
    from core_api.services.order_lifecycle import (
        OrderTransitionError,
        transition_order,
    )
    from shared.enums import OrderStatus

    oid = _seed_order(db, status="ready", order_type="pickup")
    with pytest.raises(OrderTransitionError):
        transition_order(oid, OrderStatus.IN_DELIVERY, "courier", db)

    assert grace_logs.blocks(
        fn="order_lifecycle.transition_order", blk="BLOCK_TX_BEGIN"
    )
    assert grace_logs.blocks(
        fn="order_lifecycle.transition_order", blk="BLOCK_STATE_TRANSITION"
    ) == []
    assert grace_logs.blocks(
        fn="order_lifecycle.transition_order", blk="BLOCK_TX_COMMIT"
    ) == []


def test_ready_to_completed_pickup_barista(
    db: Session, notify_mock: MagicMock
) -> None:
    from core_api.services.order_lifecycle import transition_order
    from shared.enums import OrderStatus
    from shared.models import Order

    _seed_shop_settings(db, loyalty_percent=0)
    oid = _seed_order(db, status="ready", order_type="pickup")
    transition_order(oid, OrderStatus.COMPLETED, "barista", db)

    assert db.get(Order, oid).status == OrderStatus.COMPLETED
    assert notify_mock.call_count == 1


def test_ready_to_completed_rejects_delivery_order(
    db: Session, notify_mock: MagicMock
) -> None:
    from core_api.services.order_lifecycle import (
        OrderTransitionError,
        transition_order,
    )
    from shared.enums import OrderStatus
    from shared.models import Order

    _seed_shop_settings(db, loyalty_percent=0)
    oid = _seed_order(db, status="ready", order_type="delivery")
    with pytest.raises(OrderTransitionError) as ei:
        transition_order(oid, OrderStatus.COMPLETED, "barista", db)
    assert ei.value.reason == "wrong_order_type_for_transition"
    assert db.get(Order, oid).status == OrderStatus.READY


def test_ready_to_cancelled_admin_only(db: Session, notify_mock: MagicMock) -> None:
    from core_api.services.order_lifecycle import (
        OrderTransitionError,
        transition_order,
    )
    from shared.enums import OrderStatus
    from shared.models import Order

    # ADMIN allowed
    oid_admin = _seed_order(db, status="ready")
    transition_order(oid_admin, OrderStatus.CANCELLED, "admin", db)
    assert db.get(Order, oid_admin).status == OrderStatus.CANCELLED

    for role in ("barista", "courier"):
        oid = _seed_order(db, status="ready")
        with pytest.raises(OrderTransitionError) as ei:
            transition_order(oid, OrderStatus.CANCELLED, role, db)
        assert ei.value.reason == "role_not_allowed"
        assert db.get(Order, oid).status == OrderStatus.READY


def test_in_delivery_to_completed_courier_happy_path(
    db: Session, notify_mock: MagicMock
) -> None:
    from core_api.services.order_lifecycle import transition_order
    from shared.enums import OrderStatus
    from shared.models import Order

    _seed_shop_settings(db, loyalty_percent=0)
    oid = _seed_order(db, status="in_delivery", order_type="delivery")
    transition_order(oid, OrderStatus.COMPLETED, "courier", db)

    assert db.get(Order, oid).status == OrderStatus.COMPLETED
    assert notify_mock.call_count == 1


# ---------------------------------------------------------------------------
# Loyalty accrual at COMPLETED (INV-003, PDD §7.2 step 6)
# ---------------------------------------------------------------------------

def test_completed_accrues_loyalty_pickup(db: Session, notify_mock: MagicMock) -> None:
    from core_api.services.order_lifecycle import transition_order
    from shared.enums import LoyaltyTransactionType, OrderStatus
    from shared.models import LoyaltyAccount, LoyaltyTransaction

    _seed_shop_settings(db, loyalty_percent=5)
    uid = _seed_user(db)
    _seed_loyalty(db, uid, balance=0)

    from shared.models import Order as OrderModel
    from shared.enums import OrderType

    order = OrderModel(
        user_id=uid,
        status=OrderStatus.READY,
        type=OrderType.PICKUP,
        subtotal=12345,
        discount_amount=0,
        points_used=0,
        delivery_fee=0,
        total=12345,
        estimated_accrual=0,
    )
    db.add(order)
    db.flush()
    oid = order.id

    transition_order(oid, OrderStatus.COMPLETED, "barista", db)

    acct = db.get(LoyaltyAccount, uid)
    assert acct.balance == 617  # floor(12345 * 5 / 100)

    txns = (
        db.query(LoyaltyTransaction)
        .filter_by(user_id=uid, type=LoyaltyTransactionType.ACCRUAL)
        .all()
    )
    assert len(txns) == 1
    assert txns[0].amount == 617


def test_completed_accrues_loyalty_delivery_excludes_delivery_fee(
    db: Session, notify_mock: MagicMock
) -> None:
    from core_api.services.order_lifecycle import transition_order
    from shared.enums import LoyaltyTransactionType, OrderStatus, OrderType
    from shared.models import LoyaltyAccount, LoyaltyTransaction, Order as OrderModel

    _seed_shop_settings(db, loyalty_percent=10)
    uid = _seed_user(db)
    _seed_loyalty(db, uid, balance=0)

    order = OrderModel(
        user_id=uid,
        status=OrderStatus.IN_DELIVERY,
        type=OrderType.DELIVERY,
        subtotal=100000,
        discount_amount=0,
        points_used=0,
        delivery_fee=15000,
        total=100000,
        estimated_accrual=0,
    )
    db.add(order)
    db.flush()

    transition_order(order.id, OrderStatus.COMPLETED, "courier", db)

    # after_points = 100000 - 15000 = 85000; floor(85000 * 10 / 100) = 8500
    acct = db.get(LoyaltyAccount, uid)
    assert acct.balance == 8500
    txn = (
        db.query(LoyaltyTransaction)
        .filter_by(user_id=uid, type=LoyaltyTransactionType.ACCRUAL)
        .one()
    )
    assert txn.amount == 8500


def test_completed_zero_goods_total_accrues_nothing(
    db: Session, notify_mock: MagicMock
) -> None:
    """Если total == delivery_fee (товары = 0), баланс лояльности не меняется (INV-003)."""
    from core_api.services.order_lifecycle import transition_order
    from shared.enums import OrderStatus, OrderType
    from shared.models import LoyaltyAccount, Order as OrderModel

    _seed_shop_settings(db, loyalty_percent=5)
    uid = _seed_user(db)
    _seed_loyalty(db, uid, balance=500)

    order = OrderModel(
        user_id=uid,
        status=OrderStatus.READY,
        type=OrderType.PICKUP,
        subtotal=0,
        discount_amount=0,
        points_used=0,
        delivery_fee=0,
        total=0,
        estimated_accrual=0,
    )
    db.add(order)
    db.flush()

    transition_order(order.id, OrderStatus.COMPLETED, "barista", db)

    acct = db.get(LoyaltyAccount, uid)
    # Баланс не мог измениться: либо нет ACCRUAL-записи, либо amount=0.
    assert acct.balance == 500


# ---------------------------------------------------------------------------
# Forbidden transitions (INV-016, INV-010)
# ---------------------------------------------------------------------------

_ALL_STATUSES = [
    "created",
    "paid",
    "preparing",
    "ready",
    "in_delivery",
    "completed",
    "cancelled",
]

# Разрешённые переходы из PDD §6.1, которые обрабатывает ЭТОТ сервис.
# CREATED→PAID и CREATED→CANCELLED — территория payment-webhook; здесь запрещены.
_ALLOWED: set[tuple[str, str]] = {
    ("paid", "preparing"),
    ("paid", "cancelled"),
    ("preparing", "ready"),
    ("preparing", "cancelled"),
    ("ready", "in_delivery"),
    ("ready", "completed"),
    ("ready", "cancelled"),
    ("in_delivery", "completed"),
}


def _forbidden_pairs() -> list[tuple[str, str]]:
    pairs = []
    for src, dst in itertools.product(_ALL_STATUSES, repeat=2):
        if src == dst:
            continue
        if (src, dst) in _ALLOWED:
            continue
        pairs.append((src, dst))
    return pairs


@pytest.mark.parametrize(("src", "dst"), _forbidden_pairs())
def test_forbidden_transitions_raise(
    db: Session, notify_mock: MagicMock, src: str, dst: str
) -> None:
    from core_api.services.order_lifecycle import (
        OrderTransitionError,
        transition_order,
    )
    from shared.enums import OrderStatus
    from shared.models import Order

    # Для IN_DELIVERY сидируем delivery; для prep/ready — PICKUP (значения типа
    # не проверяются на этих переходах, главное — src валиден в базе).
    otype = "delivery" if src in ("in_delivery",) else "pickup"
    oid = _seed_order(db, status=src, order_type=otype)
    with pytest.raises(OrderTransitionError) as ei:
        transition_order(oid, OrderStatus(dst), "admin", db)
    assert ei.value.reason == "forbidden_transition"
    assert db.get(Order, oid).status == OrderStatus(src)


def test_customer_role_cannot_transition(
    db: Session, notify_mock: MagicMock
) -> None:
    from core_api.services.order_lifecycle import (
        OrderTransitionError,
        transition_order,
    )
    from shared.enums import OrderStatus

    for src, dst in _ALLOWED:
        otype = "delivery" if dst == "in_delivery" or src == "in_delivery" else "pickup"
        oid = _seed_order(db, status=src, order_type=otype)
        with pytest.raises(OrderTransitionError) as ei:
            transition_order(oid, OrderStatus(dst), "customer", db)
        assert ei.value.reason == "role_not_allowed"


def test_order_not_found_raises(db: Session, notify_mock: MagicMock) -> None:
    from core_api.services.order_lifecycle import (
        OrderTransitionError,
        transition_order,
    )
    from shared.enums import OrderStatus

    with pytest.raises(OrderTransitionError) as ei:
        transition_order(uuid.uuid4(), OrderStatus.PREPARING, "admin", db)
    assert ei.value.reason == "order_not_found"
