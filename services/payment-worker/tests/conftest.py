"""Общие фикстуры для RED-тестов payment-worker.

В RED-цикле многие производственные модули ещё не существуют
(yukassa_client.py, webhook.py, обновлённый tasks.py/settings.py) — тесты,
которые их импортируют, должны падать с ImportError/AttributeError. Эти
фикстуры готовят изолированный окружение: SQLite + таблицы Phase-3 +
fakeredis + env-переменные ЮKassa. GREEN будет использовать эти же
фикстуры.
"""

from __future__ import annotations

import os
import pathlib
import sys
import uuid
from collections.abc import Generator
from typing import Any

import pytest

# Корень репо в sys.path — чтобы тесты могли импортировать `shared.*`
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Минимальные env-переменные до импорта приложения
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")


@pytest.fixture(scope="session")
def sqlite_engine():
    """Единый SQLite-движок для всех Phase-3 моделей (in-memory, StaticPool).

    Регистрируем python-функцию ``now()`` для SQLite — иначе server_default
    = text("now()") на Phase-3 моделях падает (у SQLite нет такой функции).
    """
    from datetime import datetime, timezone

    from sqlalchemy import create_engine, event
    from sqlalchemy.pool import StaticPool

    import shared.models  # noqa: F401 — регистрируем модели в Base.metadata
    from shared.models import Base

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _sqlite_now(dbapi_conn, _record):
        dbapi_conn.create_function(
            "now", 0, lambda: datetime.now(timezone.utc).isoformat()
        )

    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(sqlite_engine) -> Generator[Any, None, None]:
    """Чистая сессия на тест: полная очистка всех таблиц перед началом."""
    from sqlalchemy.orm import Session

    # Чистим таблицы в обратном порядке FK-зависимостей
    from shared.models import Base

    with sqlite_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())

    session = Session(bind=sqlite_engine, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def seed_user_order_payment(db_session):
    """Базовый seed: User + LoyaltyAccount + Promocode + Order + Payment + RESERVATION.

    Используется тестами create_payment/initiate_refund/webhook. Значения:
    - points_used=100, loyalty balance_after seeding = 0 (после reservation на -100)
    - promocode.current_uses=1
    - Order.status=CREATED, Payment.status=PENDING
    """
    from shared.enums import (
        LoyaltyTransactionType,
        OrderStatus,
        OrderType,
        PaymentStatus,
        PromocodeDiscountType,
        UserStatus,
    )
    from shared.models.loyalty_account import LoyaltyAccount
    from shared.models.loyalty_transaction import LoyaltyTransaction
    from shared.models.order import Order
    from shared.models.payment import Payment
    from shared.models.promocode import Promocode
    from shared.models.user import User

    user = User(
        id=uuid.uuid4(),
        phone_hash="hash-" + uuid.uuid4().hex[:10],
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    db_session.flush()

    loyalty = LoyaltyAccount(user_id=user.id, balance=0)
    db_session.add(loyalty)

    promo = Promocode(
        id=uuid.uuid4(),
        code="WELCOME-" + uuid.uuid4().hex[:6].upper(),
        discount_type=PromocodeDiscountType.PERCENT,
        discount_value=10,
        current_uses=1,
        is_active=True,
    )
    db_session.add(promo)
    db_session.flush()

    order = Order(
        id=uuid.uuid4(),
        user_id=user.id,
        status=OrderStatus.CREATED,
        type=OrderType.PICKUP,
        subtotal=20000,
        discount_amount=2000,
        points_used=100,
        delivery_fee=0,
        total=17900,
        estimated_accrual=900,
        promocode_id=promo.id,
    )
    db_session.add(order)
    db_session.flush()

    # RESERVATION: списание 100 баллов
    reservation = LoyaltyTransaction(
        id=uuid.uuid4(),
        user_id=user.id,
        order_id=order.id,
        type=LoyaltyTransactionType.RESERVATION,
        amount=-100,
        balance_after=0,
        description="reserved for order",
    )
    db_session.add(reservation)

    payment = Payment(
        id=uuid.uuid4(),
        order_id=order.id,
        amount=order.total,
        status=PaymentStatus.PENDING,
    )
    db_session.add(payment)
    db_session.commit()

    return {
        "user": user,
        "loyalty": loyalty,
        "promocode": promo,
        "order": order,
        "payment": payment,
        "reservation": reservation,
    }


@pytest.fixture
def fake_redis():
    """fakeredis-клиент для идемпотентности webhook + удаления cart:{user_id}."""
    import fakeredis

    return fakeredis.FakeRedis(decode_responses=False)


@pytest.fixture
def yukassa_env(monkeypatch) -> dict[str, str]:
    """Стандартное окружение ЮKassa для тестов."""
    env = {
        "YUKASSA_SHOP_ID": "test_shop",
        "YUKASSA_SECRET_KEY": "test_secret",
        "YUKASSA_WEBHOOK_IPS": "185.71.76.1,185.71.76.2,127.0.0.1",
        "YUKASSA_BASE_URL": "https://api.yookassa.ru/v3",
        "DATABASE_URL": "sqlite://",
        "REDIS_URL": "redis://localhost:6379/0",
    }
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return env


@pytest.fixture(autouse=True)
def _webhook_deps_patch(request, sqlite_engine, fake_redis):
    """Webhook-тесты ожидают, что get_engine/get_redis в payment_worker.webhook
    возвращают sqlite_engine и fake_redis в течение всего теста. ``_make_client``
    применяет патчи через ``with`` и выходит из контекста до запроса, поэтому
    инфраструктурно держим патчи активными весь тест через autouse.
    """
    if "test_webhook" not in request.node.nodeid:
        yield
        return
    from unittest.mock import patch

    patches = [
        patch(
            "payment_worker.webhook.get_engine",
            return_value=sqlite_engine,
            create=True,
        ),
        patch(
            "payment_worker.webhook.get_redis",
            return_value=fake_redis,
            create=True,
        ),
    ]
    for p in patches:
        p.start()
    try:
        yield
    finally:
        for p in patches:
            p.stop()
