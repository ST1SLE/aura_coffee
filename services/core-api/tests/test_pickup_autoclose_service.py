"""RED: тесты сервиса `core_api.services.pickup_autoclose.close_stale_pickups`.

Фиксируют контракт автозакрытия pickup-заказов (§6.1 row
"READY → COMPLETED — Автозакрытие по таймеру", §7.1 Phase 6 item 4):
- фильтр: type=pickup, status=READY, updated_at < now - auto_close_minutes;
- мутация: status=COMPLETED, auto_completed=true, auto_completed_at=now;
- side-effect: loyalty accrual через order_lifecycle (INV-003);
- suppress SMS: send_order_notification не вызывается для авто-закрытия;
- cutoff параметризуется `shop_settings.auto_close_minutes`.

Все импорты SUT делаются ВНУТРИ тестов — в RED-цикле модуля ещё нет,
импорт на уровне файла сорвал бы collection.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Хелперы seed: переиспользуем in-memory sqlite из conftest.
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


def _seed_loyalty(db: Session, user_id: uuid.UUID, balance: int = 0) -> None:
    from shared.models import LoyaltyAccount

    db.add(LoyaltyAccount(user_id=user_id, balance=balance))
    db.flush()


def _seed_shop_settings(
    db: Session,
    *,
    auto_close_minutes: int = 60,
    loyalty_percent: int = 0,
) -> None:
    from shared.models import ShopSettings

    existing = db.get(ShopSettings, 1)
    if existing is not None:
        existing.auto_close_minutes = auto_close_minutes
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
            auto_close_minutes=auto_close_minutes,
            working_hours={"mon": "08-22"},
        )
    )
    db.flush()


def _seed_order_with_updated_at(
    db: Session,
    *,
    status: str,
    order_type: str,
    updated_at: datetime,
    total: int = 20000,
    delivery_fee: int = 0,
    user_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Создаёт Order и форсит `updated_at` через UPDATE (обход onupdate=now())."""
    from shared.enums import OrderStatus, OrderType
    from shared.models import Order

    uid = user_id or _seed_user(db)
    _seed_loyalty(db, uid)
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
    # Форсим updated_at — server_default=now() / onupdate=now() иначе его перезатрёт.
    db.execute(
        sa.text("UPDATE orders SET updated_at = :ts WHERE id = :id"),
        {"ts": updated_at, "id": str(o.id)},
    )
    db.flush()
    return o.id


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
    """Подменяет send_order_notification в order_notifications и order_lifecycle."""
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
    try:
        import core_api.services.order_lifecycle as lifecycle_mod  # noqa: F401
        monkeypatch.setattr(
            lifecycle_mod, "send_order_notification", mock, raising=False
        )
    except ModuleNotFoundError:
        pass
    return mock


# ---------------------------------------------------------------------------
# 2. RED — shape & no-op
# ---------------------------------------------------------------------------

def test_no_stale_orders_returns_zero(db: Session, notify_mock: MagicMock) -> None:
    from core_api.services.pickup_autoclose import close_stale_pickups

    _seed_shop_settings(db, auto_close_minutes=60)
    now = datetime.now(UTC)

    closed = close_stale_pickups(db, now)

    assert closed == 0


# ---------------------------------------------------------------------------
# 3. RED — positive closure
# ---------------------------------------------------------------------------

def test_stale_pickup_ready_is_completed(
    db: Session, notify_mock: MagicMock
) -> None:
    from core_api.services.pickup_autoclose import close_stale_pickups
    from shared.enums import OrderStatus
    from shared.models import Order

    _seed_shop_settings(db, auto_close_minutes=60)
    now = datetime.now(UTC)
    oid = _seed_order_with_updated_at(
        db,
        status="ready",
        order_type="pickup",
        updated_at=now - timedelta(minutes=61),
    )

    closed = close_stale_pickups(db, now)

    assert closed == 1
    row = db.get(Order, oid)
    assert row.status == OrderStatus.COMPLETED
    assert row.auto_completed is True
    assert row.auto_completed_at is not None
    # Сравниваем с точностью до микросекунд — точный момент выставляется сервисом.
    assert row.auto_completed_at.replace(tzinfo=UTC) == now


# ---------------------------------------------------------------------------
# 4. RED — negative filters
# ---------------------------------------------------------------------------

def test_fresh_pickup_ready_is_skipped(
    db: Session, notify_mock: MagicMock
) -> None:
    from core_api.services.pickup_autoclose import close_stale_pickups
    from shared.enums import OrderStatus
    from shared.models import Order

    _seed_shop_settings(db, auto_close_minutes=60)
    now = datetime.now(UTC)
    oid = _seed_order_with_updated_at(
        db,
        status="ready",
        order_type="pickup",
        updated_at=now - timedelta(minutes=30),
    )

    closed = close_stale_pickups(db, now)

    assert closed == 0
    row = db.get(Order, oid)
    assert row.status == OrderStatus.READY
    assert row.auto_completed is False
    assert row.auto_completed_at is None


def test_delivery_ready_is_skipped(
    db: Session, notify_mock: MagicMock
) -> None:
    from core_api.services.pickup_autoclose import close_stale_pickups
    from shared.enums import OrderStatus
    from shared.models import Order

    _seed_shop_settings(db, auto_close_minutes=60)
    now = datetime.now(UTC)
    oid = _seed_order_with_updated_at(
        db,
        status="ready",
        order_type="delivery",
        updated_at=now - timedelta(minutes=90),
    )

    closed = close_stale_pickups(db, now)

    assert closed == 0
    row = db.get(Order, oid)
    assert row.status == OrderStatus.READY


def test_pickup_preparing_is_skipped(
    db: Session, notify_mock: MagicMock
) -> None:
    from core_api.services.pickup_autoclose import close_stale_pickups
    from shared.enums import OrderStatus
    from shared.models import Order

    _seed_shop_settings(db, auto_close_minutes=60)
    now = datetime.now(UTC)
    oid = _seed_order_with_updated_at(
        db,
        status="preparing",
        order_type="pickup",
        updated_at=now - timedelta(minutes=90),
    )

    closed = close_stale_pickups(db, now)

    assert closed == 0
    row = db.get(Order, oid)
    assert row.status == OrderStatus.PREPARING


# ---------------------------------------------------------------------------
# 5. RED — loyalty accrual side-effect
# ---------------------------------------------------------------------------

def test_auto_close_fires_loyalty_accrual(
    db: Session, notify_mock: MagicMock
) -> None:
    from core_api.services.pickup_autoclose import close_stale_pickups
    from shared.enums import LoyaltyTransactionType
    from shared.models import LoyaltyAccount, LoyaltyTransaction

    _seed_shop_settings(db, auto_close_minutes=60, loyalty_percent=10)
    now = datetime.now(UTC)
    uid = _seed_user(db)
    _seed_loyalty(db, uid, balance=0)

    oid = _seed_order_with_updated_at(
        db,
        status="ready",
        order_type="pickup",
        updated_at=now - timedelta(minutes=61),
        total=20000,
        delivery_fee=0,
        user_id=uid,
    )

    closed = close_stale_pickups(db, now)
    assert closed == 1

    txs = (
        db.query(LoyaltyTransaction)
        .filter(LoyaltyTransaction.order_id == oid)
        .all()
    )
    accruals = [t for t in txs if t.type == LoyaltyTransactionType.ACCRUAL]
    assert len(accruals) == 1
    assert accruals[0].amount == 2000

    acct = db.get(LoyaltyAccount, uid)
    assert acct.balance == 2000


# ---------------------------------------------------------------------------
# 6. RED — SMS suppression
# ---------------------------------------------------------------------------

def test_auto_close_does_not_send_sms(
    db: Session, notify_mock: MagicMock
) -> None:
    from core_api.services.pickup_autoclose import close_stale_pickups

    _seed_shop_settings(db, auto_close_minutes=60)
    now = datetime.now(UTC)
    _seed_order_with_updated_at(
        db,
        status="ready",
        order_type="pickup",
        updated_at=now - timedelta(minutes=61),
    )

    close_stale_pickups(db, now)

    notify_mock.assert_not_called()


# ---------------------------------------------------------------------------
# 7. RED — cutoff parametrization
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "auto_close_minutes, age_minutes, expected_closed",
    [
        (60, 59, False),
        (60, 61, True),
        (120, 119, False),
        (120, 121, True),
    ],
)
def test_cutoff_respects_auto_close_minutes(
    db: Session,
    notify_mock: MagicMock,
    auto_close_minutes: int,
    age_minutes: int,
    expected_closed: bool,
) -> None:
    from core_api.services.pickup_autoclose import close_stale_pickups
    from shared.enums import OrderStatus
    from shared.models import Order

    _seed_shop_settings(db, auto_close_minutes=auto_close_minutes)
    now = datetime.now(UTC)
    oid = _seed_order_with_updated_at(
        db,
        status="ready",
        order_type="pickup",
        updated_at=now - timedelta(minutes=age_minutes),
    )

    closed = close_stale_pickups(db, now)

    row = db.get(Order, oid)
    if expected_closed:
        assert closed == 1
        assert row.status == OrderStatus.COMPLETED
        assert row.auto_completed is True
    else:
        assert closed == 0
        assert row.status == OrderStatus.READY
        assert row.auto_completed is False
