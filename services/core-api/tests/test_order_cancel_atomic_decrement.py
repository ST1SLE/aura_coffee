"""Атомарный декремент promocodes.current_uses с zero-floor в cancel-пути.

PDD §6.6 «Атомарный инкремент», §7.6 шаг 2, INV-004, INV-011.

Двойной вызов `_return_promocode` на одном и том же заказе НЕ должен
уводить current_uses ниже нуля. Текущий `promo.current_uses -= 1` без
защиты — тест 2.2 должен падать. 2.3 — guard happy-path.

Требует Postgres через `db_session`-фикстуру.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from tests.conftest import _TEST_DB_URL as TEST_DB_URL

_IS_SQLITE = TEST_DB_URL.startswith("sqlite")
pytestmark = pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL")


def _seed_user(db: Session) -> uuid.UUID:
    from shared.enums import UserStatus
    from shared.models import User

    u = User(phone_hash=uuid.uuid4().hex, status=UserStatus.ACTIVE)
    db.add(u)
    db.flush()
    return u.id


def _seed_promocode(db: Session, *, current_uses: int) -> uuid.UUID:
    from shared.enums import PromocodeDiscountType
    from shared.models import Promocode

    p = Promocode(
        code=f"DEC_{uuid.uuid4().hex[:8]}",
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


def _seed_paid_order(
    db: Session, *, user_id: uuid.UUID, promocode_id: uuid.UUID
) -> uuid.UUID:
    from shared.enums import OrderStatus, OrderType
    from shared.models import Order, PromocodeUsage

    order = Order(
        user_id=user_id,
        status=OrderStatus.PAID,
        type=OrderType.PICKUP,
        subtotal=50000,
        discount_amount=1000,
        points_used=0,
        delivery_fee=0,
        total=49000,
        estimated_accrual=0,
        promocode_id=promocode_id,
    )
    db.add(order)
    db.flush()
    db.add(PromocodeUsage(promocode_id=promocode_id, user_id=user_id, order_id=order.id))
    db.flush()
    return order.id


# ---------------------------------------------------------------------------
# 2.2 RED — двойной декремент не уходит ниже нуля
# ---------------------------------------------------------------------------


def test_double_cancel_does_not_drive_counter_below_zero(db_session: Session) -> None:
    """Второй _return_promocode — zero-rowcount no-op, current_uses=0 (не -1)."""
    from core_api.services.order_cancel import _return_promocode
    from shared.models import Order, Promocode

    uid = _seed_user(db_session)
    pid = _seed_promocode(db_session, current_uses=1)
    oid = _seed_paid_order(db_session, user_id=uid, promocode_id=pid)
    db_session.flush()

    order = db_session.get(Order, oid)
    _return_promocode(order, db_session)
    db_session.flush()
    assert db_session.get(Promocode, pid).current_uses == 0

    _return_promocode(order, db_session)
    db_session.flush()
    db_session.expire_all()

    assert db_session.get(Promocode, pid).current_uses == 0, (
        f"current_uses ушёл ниже нуля: {db_session.get(Promocode, pid).current_uses}"
    )


# ---------------------------------------------------------------------------
# 2.3 — GREEN-contract guard: обычный декремент = -1
# ---------------------------------------------------------------------------


def test_normal_decrement_matches_single_row(db_session: Session) -> None:
    """current_uses=3 → после _return_promocode current_uses=2 и usage-row удалена."""
    from core_api.services.order_cancel import _return_promocode
    from shared.models import Order, Promocode, PromocodeUsage

    uid = _seed_user(db_session)
    pid = _seed_promocode(db_session, current_uses=3)
    oid = _seed_paid_order(db_session, user_id=uid, promocode_id=pid)
    db_session.flush()

    order = db_session.get(Order, oid)
    _return_promocode(order, db_session)
    db_session.flush()
    db_session.expire_all()

    assert db_session.get(Promocode, pid).current_uses == 2
    assert db_session.query(PromocodeUsage).filter_by(order_id=oid).count() == 0
