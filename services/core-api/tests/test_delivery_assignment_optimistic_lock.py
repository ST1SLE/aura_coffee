"""RED: тест optimistic-lock-семантики `take_assignment` (PDD §6.3).

Две независимые сессии на один и тот же AWAITING_COURIER assignment:
первый `take_assignment` побеждает, второй получает `AssignmentAlreadyTakenError`.

Требует двух независимых PostgreSQL-соединений — для sqlite-in-memory
(StaticPool, единое connection) тест skip-ается.
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "sqlite://")


# ---------------------------------------------------------------------------
# 4.1 — import probe
# ---------------------------------------------------------------------------

def test_optimistic_lock_module_exists() -> None:
    from core_api.services.delivery_assignment import (  # noqa: F401
        AssignmentAlreadyTakenError,
        take_assignment,
    )


# ---------------------------------------------------------------------------
# 4.2 — две независимые сессии: только одна выигрывает
# ---------------------------------------------------------------------------

def test_two_couriers_race_one_wins() -> None:
    if _TEST_DB_URL.startswith("sqlite"):
        pytest.skip(
            "Optimistic-lock race требует двух независимых PG-соединений; "
            "sqlite-in-memory использует StaticPool с единственным connection."
        )

    from core_api.services.delivery_assignment import (
        AssignmentAlreadyTakenError,
        take_assignment,
    )
    from shared.enums import (
        DeliveryAssignmentStatus,
        OrderStatus,
        OrderType,
        StaffRole,
        UserStatus,
    )
    from shared.models import (
        DeliveryAssignment,
        LoyaltyAccount,
        Order,
        StaffAccount,
        User,
    )

    engine = create_engine(_TEST_DB_URL)

    aid: uuid.UUID
    c1_id: uuid.UUID
    c2_id: uuid.UUID

    # ── Сессия SEED: создаём пользователя, заказ, AWAITING-assignment, двух курьеров
    with Session(engine) as seed:
        u = User(phone_hash=uuid.uuid4().hex, status=UserStatus.ACTIVE)
        seed.add(u)
        seed.flush()
        seed.add(LoyaltyAccount(user_id=u.id, balance=0))
        order = Order(
            user_id=u.id,
            status=OrderStatus.PREPARING,
            type=OrderType.DELIVERY,
            subtotal=50000,
            discount_amount=0,
            points_used=0,
            delivery_fee=0,
            total=50000,
            estimated_accrual=0,
        )
        seed.add(order)
        seed.flush()
        a = DeliveryAssignment(
            order_id=order.id,
            courier_id=None,
            status=DeliveryAssignmentStatus.AWAITING_COURIER,
        )
        seed.add(a)
        c1 = StaffAccount(
            login=f"c1_{uuid.uuid4().hex[:8]}",
            password_hash="x" * 32,
            role=StaffRole.COURIER,
            display_name="C1",
            is_active=True,
        )
        c2 = StaffAccount(
            login=f"c2_{uuid.uuid4().hex[:8]}",
            password_hash="x" * 32,
            role=StaffRole.COURIER,
            display_name="C2",
            is_active=True,
        )
        seed.add_all([c1, c2])
        seed.commit()
        aid, c1_id, c2_id = a.id, c1.id, c2.id

    # ── Сессия A: первый курьер берёт заказ
    with Session(engine) as db_a:
        take_assignment(aid, c1_id, db_a)
        db_a.commit()

    # ── Сессия B: второй курьер пытается взять — ловим AssignmentAlreadyTakenError
    with Session(engine) as db_b:
        with pytest.raises(AssignmentAlreadyTakenError):
            take_assignment(aid, c2_id, db_b)

    # ── Сессия C: проверяем итог в БД
    with Session(engine) as db_c:
        a = db_c.get(DeliveryAssignment, aid)
        assert a.courier_id == c1_id
        assert a.status == DeliveryAssignmentStatus.COURIER_ASSIGNED

    engine.dispose()
