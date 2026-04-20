"""Атомарный инкремент promocodes.current_uses в checkout-пути.

PDD §6.6 «Атомарный инкремент», §7.2 шаг 2, INV-004, INV-011.

RED-цикл: симулируем TOCTOU-гонку через явную подстановку состояния БД
между validate_promocode и инкрементом. Текущая ORM-мутация
(`promocode.current_uses = ... + 1`) не защищена — 1.2 должен падать.
1.3/1.4 — GREEN-contract guards, которые удерживают happy-path.

Требует Postgres: через фикстуру `db_session` из conftest (иначе skip).
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import fakeredis
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.conftest import _TEST_DB_URL as TEST_DB_URL

_IS_SQLITE = TEST_DB_URL.startswith("sqlite")
pytestmark = pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")


def _seed_user(db: Session) -> uuid.UUID:
    from shared.enums import UserStatus
    from shared.models import LoyaltyAccount, User, UserProfile

    u = User(phone_hash=uuid.uuid4().hex, status=UserStatus.ACTIVE)
    db.add(u)
    db.flush()
    db.add(
        UserProfile(
            user_id=u.id,
            phone=b"test-phone-bytes",
            display_name="Race",
            preferred_language="ru",
        )
    )
    db.add(LoyaltyAccount(user_id=u.id, balance=0))
    db.flush()
    return u.id


def _seed_promocode(
    db: Session, *, max_uses: int | None, current_uses: int = 0
) -> tuple[uuid.UUID, str]:
    from shared.enums import PromocodeDiscountType
    from shared.models import Promocode

    code = f"RACE_{uuid.uuid4().hex[:8]}"
    p = Promocode(
        code=code,
        discount_type=PromocodeDiscountType.FIXED_AMOUNT,
        discount_value=1000,
        min_order_amount=0,
        max_uses=max_uses,
        current_uses=current_uses,
        is_active=True,
    )
    db.add(p)
    db.flush()
    return p.id, code


def _seed_menu_item(db: Session, *, base_price: int = 50000) -> int:
    from tests._factories.menu import make_category, make_menu_item

    cat = make_category(db)
    item = make_menu_item(db, category=cat, base_price=base_price)
    return item.id


def _seed_cart(
    redis_client: fakeredis.FakeRedis, user_id: uuid.UUID, menu_item_id: int
) -> None:
    payload = {
        "items": [
            {
                "menu_item_id": menu_item_id,
                "size_option_id": None,
                "modifier_ids": [],
                "quantity": 1,
            }
        ],
        "updated_at": datetime.now(UTC).isoformat(),
    }
    redis_client.set(f"cart:{user_id}", json.dumps(payload), ex=300)


@pytest.fixture
def fake_redis() -> fakeredis.FakeRedis:
    r = fakeredis.FakeRedis()
    yield r
    r.flushall()


# ---------------------------------------------------------------------------
# 1.2 RED — гонка: после validator, до инкремента current_uses уже исчерпан
# ---------------------------------------------------------------------------


def test_race_loss_raises_validation_error_and_does_not_overshoot_max_uses(
    db_session: Session, fake_redis: fakeredis.FakeRedis
) -> None:
    """Race: validator видит current_uses=0, но к моменту инкремента
    другой транзакцией выставлено 1. Ожидаем PromocodeValidationError и
    current_uses=1 (никогда 2).
    """
    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order
    from core_api.services.validators.exceptions import PromocodeValidationError
    from shared.enums import OrderType
    from shared.models import Order, Promocode, PromocodeUsage

    uid = _seed_user(db_session)
    pid, code = _seed_promocode(db_session, max_uses=1, current_uses=0)
    item_id = _seed_menu_item(db_session, base_price=50000)
    db_session.commit()  # фиксируем pre-state, чтобы rollback lose-транзакции его не затёр

    promo_stale = db_session.get(Promocode, pid)
    _seed_cart(fake_redis, uid, item_id)

    with patch(
        "core_api.services.checkout.validate_promocode",
        MagicMock(return_value=promo_stale),
    ):
        # Симулируем winner: current_uses=1 до инкремента lose-пути.
        db_session.execute(
            text("UPDATE promocodes SET current_uses = 1 WHERE id = :pid"),
            {"pid": str(pid)},
        )
        db_session.commit()

        with pytest.raises(PromocodeValidationError) as ei:
            create_order(
                uid,
                CreateOrderRequest(type=OrderType.PICKUP, promocode_code=code),
                fake_redis,
                db_session,
            )
        assert "Global quota exhausted" in str(ei.value)

    # Сбросить pending-flushes lose-транзакции (order/items/payments
    # были flushed до PromocodeValidationError, но НЕ committed); после
    # rollback запросы отражают только committed-состояние, как на проде.
    db_session.rollback()
    db_session.expire_all()
    promo = db_session.get(Promocode, pid)
    assert promo.current_uses == 1, (
        f"current_uses должен остаться 1, а не {promo.current_uses}"
    )
    assert db_session.query(Order).filter(Order.user_id == uid).count() == 0
    assert (
        db_session.query(PromocodeUsage).filter(PromocodeUsage.user_id == uid).count()
        == 0
    )


# ---------------------------------------------------------------------------
# 1.3 — GREEN-contract guard: max_uses IS NULL → инкремент проходит
# ---------------------------------------------------------------------------


def test_unlimited_promocode_still_increments(
    db_session: Session, fake_redis: fakeredis.FakeRedis
) -> None:
    """max_uses=None, current_uses=42 → после create_order current_uses=43."""
    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order
    from shared.enums import OrderType
    from shared.models import Promocode

    uid = _seed_user(db_session)
    pid, code = _seed_promocode(db_session, max_uses=None, current_uses=42)
    item_id = _seed_menu_item(db_session, base_price=50000)
    db_session.flush()

    promo = db_session.get(Promocode, pid)
    _seed_cart(fake_redis, uid, item_id)

    with patch(
        "core_api.services.checkout.validate_promocode",
        MagicMock(return_value=promo),
    ), patch("core_api.services.checkout.enqueue_payment_task", MagicMock()):
        create_order(
            uid,
            CreateOrderRequest(type=OrderType.PICKUP, promocode_code=code),
            fake_redis,
            db_session,
        )

    db_session.expire_all()
    assert db_session.get(Promocode, pid).current_uses == 43


# ---------------------------------------------------------------------------
# 1.4 — GREEN-contract guard: под квотой инкремент матчит ровно 1 строку
# ---------------------------------------------------------------------------


def test_under_quota_single_row_match(
    db_session: Session, fake_redis: fakeredis.FakeRedis
) -> None:
    """max_uses=5, current_uses=2 → после create_order current_uses=3."""
    from core_api.schemas.order import CreateOrderRequest
    from core_api.services.checkout import create_order
    from shared.enums import OrderType
    from shared.models import Promocode

    uid = _seed_user(db_session)
    pid, code = _seed_promocode(db_session, max_uses=5, current_uses=2)
    item_id = _seed_menu_item(db_session, base_price=50000)
    db_session.flush()

    promo = db_session.get(Promocode, pid)
    _seed_cart(fake_redis, uid, item_id)

    with patch(
        "core_api.services.checkout.validate_promocode",
        MagicMock(return_value=promo),
    ), patch("core_api.services.checkout.enqueue_payment_task", MagicMock()):
        create_order(
            uid,
            CreateOrderRequest(type=OrderType.PICKUP, promocode_code=code),
            fake_redis,
            db_session,
        )

    db_session.expire_all()
    assert db_session.get(Promocode, pid).current_uses == 3
