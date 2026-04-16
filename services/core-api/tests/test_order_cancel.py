"""RED: тесты цепочки отмены заказа `core_api.services.order_cancel.cancel_order`.

Покрывают PDD §7.6 (все 6 шагов в одной DB-транзакции), INV-004 (атомарность),
INV-005 (клиент может отменить только PAID).

Импорты целевых модулей — внутри тестов: в RED-цикле `order_cancel` не
существует.
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
    from shared.models import User
    from shared.enums import UserStatus

    u = User(phone_hash=uuid.uuid4().hex, status=UserStatus.ACTIVE)
    db.add(u)
    db.flush()
    return u.id


def _seed_loyalty(db: Session, uid: uuid.UUID, balance: int) -> None:
    from shared.models import LoyaltyAccount

    db.add(LoyaltyAccount(user_id=uid, balance=balance))
    db.flush()


def _seed_promocode(db: Session, *, current_uses: int = 1) -> uuid.UUID:
    from shared.enums import PromocodeDiscountType
    from shared.models import Promocode

    p = Promocode(
        code=f"TEST_{uuid.uuid4().hex[:8]}",
        discount_type=PromocodeDiscountType.FIXED_AMOUNT,
        discount_value=1000,
        min_order_amount=0,
        max_uses=100,
        current_uses=current_uses,
        is_active=True,
    )
    db.add(p)
    db.flush()
    return p.id


def _seed_promocode_usage(
    db: Session, *, promocode_id: uuid.UUID, user_id: uuid.UUID, order_id: uuid.UUID
) -> uuid.UUID:
    from shared.models import PromocodeUsage

    usage = PromocodeUsage(
        promocode_id=promocode_id, user_id=user_id, order_id=order_id
    )
    db.add(usage)
    db.flush()
    return usage.id


def _seed_order_full(
    db: Session,
    *,
    status: str,
    order_type: str = "pickup",
    points_used: int = 0,
    promocode_id: uuid.UUID | None = None,
    payment_amount: int | None = 50000,
    user_id: uuid.UUID | None = None,
    loyalty_balance: int = 1000,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID | None]:
    """Return (order_id, user_id, payment_id)."""
    from shared.enums import OrderStatus, OrderType, PaymentStatus
    from shared.models import Order, Payment

    uid = user_id or _seed_user(db)
    _seed_loyalty(db, uid, balance=loyalty_balance)
    order = Order(
        user_id=uid,
        status=OrderStatus(status),
        type=OrderType(order_type),
        subtotal=50000,
        discount_amount=0,
        points_used=points_used,
        delivery_fee=0,
        total=50000,
        estimated_accrual=0,
        promocode_id=promocode_id,
    )
    db.add(order)
    db.flush()

    pid: uuid.UUID | None = None
    if payment_amount is not None:
        payment = Payment(
            order_id=order.id,
            amount=payment_amount,
            status=PaymentStatus.SUCCEEDED,
            yukassa_payment_id=uuid.uuid4().hex,
        )
        db.add(payment)
        db.flush()
        pid = payment.id

    return order.id, uid, pid


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
    """Подмена send_order_notification внутри order_cancel модуля."""
    import sys
    import types

    mod_name = "core_api.services.order_notifications"
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)
    mock = MagicMock()
    monkeypatch.setattr(
        sys.modules[mod_name], "send_order_notification", mock, raising=False
    )
    try:
        import core_api.services.order_cancel as sut  # noqa: F401
        monkeypatch.setattr(sut, "send_order_notification", mock, raising=False)
    except ModuleNotFoundError:
        pass
    return mock


@pytest.fixture
def send_task_mock(monkeypatch):
    """Подмена celery_app.send_task в order_cancel модуле."""
    import sys
    import types

    # Заглушка core_api.celery_app для RED — GREEN создаст реальный модуль.
    ca_name = "core_api.celery_app"
    if ca_name not in sys.modules:
        stub = types.ModuleType(ca_name)
        stub.celery_app = types.SimpleNamespace(send_task=lambda *a, **kw: None)
        sys.modules[ca_name] = stub

    mock = MagicMock()
    try:
        import core_api.services.order_cancel as sut
        monkeypatch.setattr(sut.celery_app, "send_task", mock, raising=False)
    except (ModuleNotFoundError, AttributeError):
        # GREEN ещё не добавил sut.celery_app — при последующем импорте
        # тесты будут патчить корректно; в RED мы только фиксируем сигнатуру.
        pass
    return mock


# ---------------------------------------------------------------------------
# 2.1 — import probe
# ---------------------------------------------------------------------------

def test_order_cancel_module_exists() -> None:
    from core_api.services.order_cancel import (  # noqa: F401
        OrderCancelError,
        cancel_order,
    )


# ---------------------------------------------------------------------------
# Happy path — customer + full chain
# ---------------------------------------------------------------------------

def test_customer_cancels_paid_order_full_chain(
    db: Session, notify_mock: MagicMock, send_task_mock: MagicMock
) -> None:
    from core_api.services.order_cancel import cancel_order
    from shared.enums import LoyaltyTransactionType, OrderStatus
    from shared.models import (
        LoyaltyAccount,
        LoyaltyTransaction,
        Order,
        Promocode,
        PromocodeUsage,
    )

    promo_id = _seed_promocode(db, current_uses=3)
    oid, uid, pid = _seed_order_full(
        db,
        status="paid",
        points_used=200,
        promocode_id=promo_id,
        payment_amount=50000,
        loyalty_balance=1000,
    )
    _seed_promocode_usage(db, promocode_id=promo_id, user_id=uid, order_id=oid)

    cancel_order(oid, "customer", None, db)
    db.flush()

    # 1. status + cancelled_by + cancelled_at
    order = db.get(Order, oid)
    assert order.status == OrderStatus.CANCELLED
    assert order.cancelled_by == "customer"
    assert order.cancelled_at is not None

    # 2. promocode decremented, usage removed
    promo = db.get(Promocode, promo_id)
    assert promo.current_uses == 2
    usages = db.query(PromocodeUsage).filter_by(order_id=oid).all()
    assert usages == []

    # 3. loyalty reversal
    txns = (
        db.query(LoyaltyTransaction)
        .filter_by(user_id=uid, type=LoyaltyTransactionType.REVERSAL)
        .all()
    )
    assert len(txns) == 1
    assert txns[0].amount == 200
    assert db.get(LoyaltyAccount, uid).balance == 1200

    # 4. refund task enqueued with correct args
    assert send_task_mock.call_count == 1
    args, kwargs = send_task_mock.call_args
    assert args[0] == "payment_worker.initiate_refund"
    # args/kwargs могут быть разными формами вызова — собираем обе стороны
    payload = list(args[1:]) + list(kwargs.get("args", []))
    assert str(pid) in (str(x) for x in payload[0] if isinstance(payload[0], list)) \
        or str(pid) in [str(x) for x in payload]

    # 5. notification called
    assert notify_mock.call_count == 1


def test_admin_cancels_preparing_order_full_chain(
    db: Session, notify_mock: MagicMock, send_task_mock: MagicMock
) -> None:
    from core_api.services.order_cancel import cancel_order
    from shared.enums import OrderStatus
    from shared.models import Order

    oid, uid, _ = _seed_order_full(
        db, status="preparing", points_used=0, payment_amount=50000
    )

    cancel_order(oid, "admin", "some reason", db)
    db.flush()

    order = db.get(Order, oid)
    assert order.status == OrderStatus.CANCELLED
    assert order.cancelled_by == "admin"
    # reason должен быть проброшен в уведомление
    assert notify_mock.call_count == 1
    # в одном из позиционных/именованных аргументов есть "some reason"
    flat = list(notify_mock.call_args.args) + list(notify_mock.call_args.kwargs.values())
    assert any(x == "some reason" for x in flat)


def test_admin_cancels_ready_order(
    db: Session, notify_mock: MagicMock, send_task_mock: MagicMock
) -> None:
    from core_api.services.order_cancel import cancel_order
    from shared.enums import OrderStatus
    from shared.models import Order

    oid, _, _ = _seed_order_full(db, status="ready", payment_amount=25000)
    cancel_order(oid, "admin", None, db)
    assert db.get(Order, oid).status == OrderStatus.CANCELLED
    assert send_task_mock.call_count == 1


# ---------------------------------------------------------------------------
# Rights check (INV-005)
# ---------------------------------------------------------------------------

def test_customer_cannot_cancel_preparing(
    db: Session, notify_mock: MagicMock, send_task_mock: MagicMock
) -> None:
    from core_api.services.order_cancel import OrderCancelError, cancel_order
    from shared.enums import OrderStatus
    from shared.models import Order

    oid, _, _ = _seed_order_full(db, status="preparing")
    with pytest.raises(OrderCancelError) as ei:
        cancel_order(oid, "customer", None, db)
    assert ei.value.reason == "customer_cannot_cancel_in_this_status"
    assert db.get(Order, oid).status == OrderStatus.PREPARING
    assert send_task_mock.call_count == 0
    assert notify_mock.call_count == 0


@pytest.mark.parametrize(
    "src",
    ["created", "preparing", "ready", "in_delivery", "completed", "cancelled"],
)
def test_customer_cannot_cancel_non_paid_statuses(
    db: Session, notify_mock: MagicMock, send_task_mock: MagicMock, src: str
) -> None:
    from core_api.services.order_cancel import OrderCancelError, cancel_order

    otype = "delivery" if src == "in_delivery" else "pickup"
    oid, _, _ = _seed_order_full(db, status=src, order_type=otype)
    with pytest.raises(OrderCancelError):
        cancel_order(oid, "customer", None, db)


@pytest.mark.parametrize("src", ["in_delivery", "completed", "cancelled"])
def test_admin_cannot_cancel_terminal_or_in_delivery(
    db: Session, notify_mock: MagicMock, send_task_mock: MagicMock, src: str
) -> None:
    from core_api.services.order_cancel import OrderCancelError, cancel_order

    otype = "delivery" if src == "in_delivery" else "pickup"
    oid, _, _ = _seed_order_full(db, status=src, order_type=otype)
    with pytest.raises(OrderCancelError) as ei:
        cancel_order(oid, "admin", "need cancel", db)
    assert ei.value.reason == "not_cancellable_in_this_status"


# ---------------------------------------------------------------------------
# Skipping optional steps
# ---------------------------------------------------------------------------

def test_no_promocode_skips_promo_step(
    db: Session, notify_mock: MagicMock, send_task_mock: MagicMock
) -> None:
    from core_api.services.order_cancel import cancel_order
    from shared.enums import OrderStatus
    from shared.models import Order, PromocodeUsage

    oid, _, _ = _seed_order_full(db, status="paid", promocode_id=None)
    cancel_order(oid, "customer", None, db)

    assert db.get(Order, oid).status == OrderStatus.CANCELLED
    assert db.query(PromocodeUsage).filter_by(order_id=oid).count() == 0


def test_no_points_used_skips_loyalty_step(
    db: Session, notify_mock: MagicMock, send_task_mock: MagicMock
) -> None:
    from core_api.services.order_cancel import cancel_order
    from shared.enums import LoyaltyTransactionType
    from shared.models import LoyaltyAccount, LoyaltyTransaction

    oid, uid, _ = _seed_order_full(
        db, status="paid", points_used=0, loyalty_balance=500
    )
    cancel_order(oid, "customer", None, db)

    reversals = (
        db.query(LoyaltyTransaction)
        .filter_by(user_id=uid, type=LoyaltyTransactionType.REVERSAL)
        .count()
    )
    assert reversals == 0
    assert db.get(LoyaltyAccount, uid).balance == 500


def test_zero_payment_amount_skips_refund(
    db: Session, notify_mock: MagicMock, send_task_mock: MagicMock
) -> None:
    from core_api.services.order_cancel import cancel_order
    from shared.enums import OrderStatus
    from shared.models import Order

    oid, _, _ = _seed_order_full(db, status="paid", payment_amount=0)
    cancel_order(oid, "customer", None, db)

    assert send_task_mock.call_count == 0
    assert db.get(Order, oid).status == OrderStatus.CANCELLED


# ---------------------------------------------------------------------------
# Atomicity (INV-004)
# ---------------------------------------------------------------------------

def test_celery_send_task_failure_rolls_back_everything(
    db: Session, notify_mock: MagicMock
) -> None:
    """send_task выбросил исключение → всё откатывается, частичного состояния нет."""
    import core_api.services.order_cancel as sut
    from core_api.services.order_cancel import cancel_order
    from shared.enums import OrderStatus
    from shared.models import (
        LoyaltyAccount,
        LoyaltyTransaction,
        Order,
        Promocode,
        PromocodeUsage,
    )

    promo_id = _seed_promocode(db, current_uses=3)
    oid, uid, _ = _seed_order_full(
        db,
        status="paid",
        points_used=200,
        promocode_id=promo_id,
        payment_amount=50000,
        loyalty_balance=1000,
    )
    _seed_promocode_usage(db, promocode_id=promo_id, user_id=uid, order_id=oid)
    db.commit()  # фиксируем «pre-state» на диск, чтобы rollback вернул именно его

    # Патчим send_task напрямую на модуле
    sut.celery_app.send_task = MagicMock(side_effect=RuntimeError("boom"))

    with pytest.raises(RuntimeError):
        cancel_order(oid, "customer", None, db)

    # После исключения состояние БД должно совпадать с pre-state.
    db.rollback()
    db.expire_all()

    order = db.get(Order, oid)
    assert order.status == OrderStatus.PAID
    assert order.cancelled_by is None
    assert order.cancelled_at is None

    promo = db.get(Promocode, promo_id)
    assert promo.current_uses == 3
    assert db.query(PromocodeUsage).filter_by(order_id=oid).count() == 1

    assert (
        db.query(LoyaltyTransaction)
        .filter_by(user_id=uid)
        .count()
        == 0
    )
    assert db.get(LoyaltyAccount, uid).balance == 1000


def test_notification_failure_rolls_back_and_no_task_enqueued(
    db: Session, monkeypatch, send_task_mock: MagicMock
) -> None:
    """Notification выбросил исключение → rollback + send_task не был вызван.

    GREEN-дизайн требует, чтобы send_task вызывался только на полностью
    успешном пути. Тест фиксирует контракт: либо enqueue ПОСЛЕ уведомления,
    либо обе операции — после фиксации БД, но ни в одном случае не
    до rollback’а.
    """
    import core_api.services.order_cancel as sut
    from core_api.services.order_cancel import cancel_order
    from shared.enums import OrderStatus
    from shared.models import Order

    oid, _, _ = _seed_order_full(db, status="paid", payment_amount=50000)
    db.commit()

    monkeypatch.setattr(sut, "send_order_notification", MagicMock(side_effect=RuntimeError("boom")))

    with pytest.raises(RuntimeError):
        cancel_order(oid, "customer", None, db)

    db.rollback()
    db.expire_all()
    assert db.get(Order, oid).status == OrderStatus.PAID
    assert send_task_mock.call_count == 0


# ---------------------------------------------------------------------------
# Not-found
# ---------------------------------------------------------------------------

def test_order_not_found_raises_cancel(
    db: Session, notify_mock: MagicMock, send_task_mock: MagicMock
) -> None:
    from core_api.services.order_cancel import OrderCancelError, cancel_order

    with pytest.raises(OrderCancelError) as ei:
        cancel_order(uuid.uuid4(), "customer", None, db)
    assert ei.value.reason == "order_not_found"
