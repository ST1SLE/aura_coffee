"""RED: тесты сцепки Delivery Assignment ↔ Order Lifecycle (PDD §6.1 ↔ §6.3, INV-004).

Покрывают:
  - PAID→PREPARING хук в `transition_order` создаёт `DeliveryAssignment(AWAITING_COURIER)`
    для DELIVERY-заказов (и НЕ создаёт для PICKUP).
  - `pickup_assignment` поднимает order в IN_DELIVERY атомарно (через `transition_order_bridge`).
  - `deliver_assignment` поднимает order в COMPLETED + начисляет лояльность (INV-003).
  - Rollback на RuntimeError из `transition_order_bridge` / `_accrue_loyalty`.
  - Интеграция с `order_cancel.cancel_order` (cancel_assignment_for_order вызывается
    в той же транзакции).

Все импорты целевых модулей — внутри тестов: в RED-цикле модулей нет.
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Seeding helpers
# ---------------------------------------------------------------------------

def _fresh_session() -> Session:
    from core_api.deps.database import SessionLocal

    return SessionLocal()


def _seed_user(db: Session) -> uuid.UUID:
    from shared.enums import UserStatus
    from shared.models import User

    u = User(phone_hash=uuid.uuid4().hex, status=UserStatus.ACTIVE)
    db.add(u)
    db.flush()
    return u.id


def _seed_loyalty(db: Session, uid: uuid.UUID, balance: int = 0) -> None:
    from shared.models import LoyaltyAccount

    db.add(LoyaltyAccount(user_id=uid, balance=balance))
    db.flush()


def _seed_courier(db: Session) -> uuid.UUID:
    from shared.enums import StaffRole
    from shared.models import StaffAccount

    sa = StaffAccount(
        login=f"courier_{uuid.uuid4().hex[:8]}",
        password_hash="x" * 32,
        role=StaffRole.COURIER,
        display_name="Test Courier",
        is_active=True,
    )
    db.add(sa)
    db.flush()
    return sa.id


def _seed_order(
    db: Session,
    *,
    status: str,
    order_type: str = "delivery",
    total: int = 50000,
    delivery_fee: int = 0,
    user_id: uuid.UUID | None = None,
) -> uuid.UUID:
    from shared.enums import OrderStatus, OrderType
    from shared.models import Order

    if user_id is None:
        uid = _seed_user(db)
        _seed_loyalty(db, uid)
    else:
        uid = user_id
    o = Order(
        user_id=uid,
        status=OrderStatus(status),
        type=OrderType(order_type),
        subtotal=total,
        discount_amount=0,
        points_used=0,
        delivery_fee=delivery_fee,
        total=total,
        estimated_accrual=0,
    )
    db.add(o)
    db.flush()
    return o.id


def _seed_assignment(
    db: Session,
    *,
    status: str,
    order_id: uuid.UUID,
    courier_id: uuid.UUID | None = None,
) -> uuid.UUID:
    from shared.enums import DeliveryAssignmentStatus
    from shared.models import DeliveryAssignment

    a = DeliveryAssignment(
        order_id=order_id,
        courier_id=courier_id,
        status=DeliveryAssignmentStatus(status),
    )
    db.add(a)
    db.flush()
    return a.id


def _seed_shop_settings(db: Session, *, loyalty_percent: int = 10) -> None:
    from shared.models import ShopSettings

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
    s = _fresh_session()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture
def notify_mock(monkeypatch):
    """Подмена send_order_notification во всех модулях, которые её используют."""
    import sys
    import types

    mod_name = "core_api.services.order_notifications"
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)
    mock = MagicMock()
    monkeypatch.setattr(
        sys.modules[mod_name], "send_order_notification", mock, raising=False
    )
    for sut_name in (
        "core_api.services.order_lifecycle",
        "core_api.services.order_cancel",
        "core_api.services.delivery_assignment",
    ):
        try:
            mod = __import__(sut_name, fromlist=["*"])
            monkeypatch.setattr(mod, "send_order_notification", mock, raising=False)
        except ModuleNotFoundError:
            pass
    return mock


# ---------------------------------------------------------------------------
# 2.1 — import probe transition_order_bridge
# ---------------------------------------------------------------------------

def test_transition_order_bridge_exists() -> None:
    from core_api.services.order_lifecycle import transition_order_bridge  # noqa: F401


# ---------------------------------------------------------------------------
# 2.2 — PAID→PREPARING хук на DELIVERY создаёт AWAITING_COURIER
# ---------------------------------------------------------------------------

def test_paid_to_preparing_delivery_creates_awaiting_assignment(
    db: Session, notify_mock: MagicMock
) -> None:
    from core_api.services.order_lifecycle import transition_order
    from shared.enums import DeliveryAssignmentStatus, OrderStatus
    from shared.models import DeliveryAssignment

    oid = _seed_order(db, status="paid", order_type="delivery")
    db.commit()

    transition_order(oid, OrderStatus.PREPARING, "barista", db)

    rows = (
        db.query(DeliveryAssignment)
        .filter(DeliveryAssignment.order_id == oid)
        .all()
    )
    assert len(rows) == 1
    a = rows[0]
    assert a.status == DeliveryAssignmentStatus.AWAITING_COURIER
    assert a.courier_id is None


# ---------------------------------------------------------------------------
# 2.3 — PAID→PREPARING для PICKUP не создаёт assignment
# ---------------------------------------------------------------------------

def test_paid_to_preparing_pickup_does_not_create_assignment(
    db: Session, notify_mock: MagicMock
) -> None:
    from core_api.services.order_lifecycle import transition_order
    from shared.enums import OrderStatus
    from shared.models import DeliveryAssignment

    oid = _seed_order(db, status="paid", order_type="pickup")
    db.commit()

    transition_order(oid, OrderStatus.PREPARING, "barista", db)

    rows = (
        db.query(DeliveryAssignment)
        .filter(DeliveryAssignment.order_id == oid)
        .all()
    )
    assert len(rows) == 0


# ---------------------------------------------------------------------------
# 2.4 — pickup поднимает order READY → IN_DELIVERY (реальный bridge)
# ---------------------------------------------------------------------------

def test_pickup_assignment_transitions_order_to_in_delivery(
    db: Session, notify_mock: MagicMock
) -> None:
    from core_api.services.delivery_assignment import pickup_assignment
    from shared.enums import DeliveryAssignmentStatus, OrderStatus
    from shared.models import DeliveryAssignment, Order

    cid = _seed_courier(db)
    oid = _seed_order(db, status="ready", order_type="delivery")
    aid = _seed_assignment(
        db, status="courier_assigned", order_id=oid, courier_id=cid
    )
    db.commit()

    pickup_assignment(aid, cid, db)

    a = db.get(DeliveryAssignment, aid)
    o = db.get(Order, oid)
    assert a.status == DeliveryAssignmentStatus.PICKED_UP
    assert o.status == OrderStatus.IN_DELIVERY


# ---------------------------------------------------------------------------
# 2.5 — deliver поднимает order COMPLETED + начисляет лояльность
# ---------------------------------------------------------------------------

def test_deliver_assignment_transitions_order_to_completed_and_accrues_loyalty(
    db: Session, notify_mock: MagicMock
) -> None:
    from core_api.services.delivery_assignment import deliver_assignment
    from shared.enums import (
        DeliveryAssignmentStatus,
        LoyaltyTransactionType,
        OrderStatus,
    )
    from shared.models import (
        DeliveryAssignment,
        LoyaltyAccount,
        LoyaltyTransaction,
        Order,
    )

    _seed_shop_settings(db, loyalty_percent=10)
    uid = _seed_user(db)
    _seed_loyalty(db, uid, balance=0)
    cid = _seed_courier(db)
    oid = _seed_order(
        db,
        status="in_delivery",
        order_type="delivery",
        total=100000,
        delivery_fee=15000,
        user_id=uid,
    )
    aid = _seed_assignment(
        db, status="picked_up", order_id=oid, courier_id=cid
    )
    db.commit()

    deliver_assignment(aid, cid, db)

    a = db.get(DeliveryAssignment, aid)
    o = db.get(Order, oid)
    assert a.status == DeliveryAssignmentStatus.DELIVERED
    assert o.status == OrderStatus.COMPLETED

    # INV-003: 8500 = (100000 - 15000) * 10 / 100
    accrual_rows = (
        db.query(LoyaltyTransaction)
        .filter(
            LoyaltyTransaction.order_id == oid,
            LoyaltyTransaction.type == LoyaltyTransactionType.ACCRUAL,
        )
        .all()
    )
    assert len(accrual_rows) == 1
    assert accrual_rows[0].amount == 8500

    # Из двух LoyaltyAccount-фикстур (созданных _seed_user внутри _seed_order и
    # явный _seed_loyalty) — обе с balance=0. После начисления баланс должен
    # вырасти на 8500 у владельца заказа.
    acct = db.get(LoyaltyAccount, uid)
    # Допускаем, что _seed_order также создал loyalty (проверяем суммарно).
    assert acct.balance >= 8500


# ---------------------------------------------------------------------------
# 2.6 — pickup откатывается, если transition_order_bridge падает
# ---------------------------------------------------------------------------

def test_pickup_rolls_back_if_order_transition_fails(
    db: Session, notify_mock: MagicMock, monkeypatch
) -> None:
    from core_api.services import delivery_assignment as sut
    from core_api.services.delivery_assignment import pickup_assignment
    from shared.enums import DeliveryAssignmentStatus, OrderStatus
    from shared.models import DeliveryAssignment, Order

    cid = _seed_courier(db)
    oid = _seed_order(db, status="ready", order_type="delivery")
    aid = _seed_assignment(
        db, status="courier_assigned", order_id=oid, courier_id=cid
    )
    db.commit()

    def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(sut, "transition_order_bridge", _boom, raising=False)

    with pytest.raises(RuntimeError):
        pickup_assignment(aid, cid, db)

    db.rollback()
    db.expire_all()

    a = db.get(DeliveryAssignment, aid)
    o = db.get(Order, oid)
    assert a.status == DeliveryAssignmentStatus.COURIER_ASSIGNED
    assert o.status == OrderStatus.READY


# ---------------------------------------------------------------------------
# 2.7 — deliver откатывается, если _accrue_loyalty падает
# ---------------------------------------------------------------------------

def test_deliver_rolls_back_if_accrual_fails(
    db: Session, notify_mock: MagicMock, monkeypatch
) -> None:
    from core_api.services import order_lifecycle as ol_sut
    from core_api.services.delivery_assignment import deliver_assignment
    from shared.enums import (
        DeliveryAssignmentStatus,
        LoyaltyTransactionType,
        OrderStatus,
    )
    from shared.models import DeliveryAssignment, LoyaltyTransaction, Order

    _seed_shop_settings(db, loyalty_percent=10)
    cid = _seed_courier(db)
    oid = _seed_order(
        db,
        status="in_delivery",
        order_type="delivery",
        total=100000,
        delivery_fee=15000,
    )
    aid = _seed_assignment(
        db, status="picked_up", order_id=oid, courier_id=cid
    )
    db.commit()

    def _boom(*args, **kwargs):
        raise RuntimeError("accrual boom")

    monkeypatch.setattr(ol_sut, "_accrue_loyalty", _boom, raising=False)

    with pytest.raises(RuntimeError):
        deliver_assignment(aid, cid, db)

    db.rollback()
    db.expire_all()

    a = db.get(DeliveryAssignment, aid)
    o = db.get(Order, oid)
    assert a.status == DeliveryAssignmentStatus.PICKED_UP
    assert o.status == OrderStatus.IN_DELIVERY

    accrual_rows = (
        db.query(LoyaltyTransaction)
        .filter(
            LoyaltyTransaction.order_id == oid,
            LoyaltyTransaction.type == LoyaltyTransactionType.ACCRUAL,
        )
        .all()
    )
    assert len(accrual_rows) == 0


# ---------------------------------------------------------------------------
# 2.8 — order_cancel вызывает cancel_assignment_for_order в той же txn
# ---------------------------------------------------------------------------

def test_cancel_assignment_for_order_integrates_with_order_cancel(
    db: Session, notify_mock: MagicMock, monkeypatch
) -> None:
    from core_api.services import order_cancel as oc_sut
    from core_api.services.order_cancel import cancel_order
    from core_api.services.order_lifecycle import transition_order
    from shared.enums import DeliveryAssignmentStatus, OrderStatus
    from shared.models import DeliveryAssignment, Order

    # Чтобы cancel_order не дёргал реальный refund-таск.
    monkeypatch.setattr(
        oc_sut.celery_app, "send_task", MagicMock(), raising=False
    )

    oid = _seed_order(db, status="paid", order_type="delivery")
    db.commit()
    transition_order(oid, OrderStatus.PREPARING, "barista", db)
    # Теперь должен существовать assignment AWAITING_COURIER.

    cancel_order(oid, "admin", "test", db)

    o = db.get(Order, oid)
    a = (
        db.query(DeliveryAssignment)
        .filter(DeliveryAssignment.order_id == oid)
        .one()
    )
    assert o.status == OrderStatus.CANCELLED
    assert a.status == DeliveryAssignmentStatus.CANCELLED
