"""RED: тесты хелпера get_revenue_and_count (dashboard-api-red).

Используют функциональную фикстуру db_session (savepoint-изоляция).
Все target-импорты — внутри тел тестов.

Каждый тест использует СВОЁ историческое окно created_at
(разные месяцы 2020 года), чтобы строки из соседних тестов/модулей,
даже если прорвутся сквозь savepoint, не попали в выборку.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from shared.enums import OrderStatus, OrderType
from shared.models.order import Order
from tests._factories.orders import make_user


# ===========================================================================
# 2.x — get_revenue_and_count aggregation tests
# ===========================================================================


def test_get_revenue_and_count_symbol_absent() -> None:
    """2.1 — символ get_revenue_and_count должен существовать после GREEN."""
    from core_api.services.admin_stats import get_revenue_and_count  # noqa: F401

    assert callable(get_revenue_and_count)


def test_get_revenue_and_count_empty_range_returns_zeros(db_session) -> None:
    """2.2 — окно без COMPLETED-заказов → (0, 0)."""
    from core_api.services.admin_stats import get_revenue_and_count

    # Окно в далёком прошлом — заведомо пустое.
    t0 = datetime(2020, 1, 15, 0, 0, tzinfo=UTC)
    t1 = datetime(2020, 1, 16, 0, 0, tzinfo=UTC)

    assert get_revenue_and_count(db_session, t0, t1) == (0, 0)


def test_get_revenue_and_count_sums_only_completed(db_session) -> None:
    """2.3 — только COMPLETED попадают в SUM(total) и COUNT(*)."""
    from core_api.services.admin_stats import get_revenue_and_count

    t0 = datetime(2020, 2, 15, 0, 0, tzinfo=UTC)
    t1 = datetime(2020, 2, 16, 0, 0, tzinfo=UTC)

    user = make_user(db_session)
    db_session.commit()

    # Три COMPLETED в окне — с суммами, указанными в сценарии.
    for total, minute in [(10000, 10), (25000, 20), (40000, 30)]:
        db_session.add(Order(
            user_id=user.id,
            status=OrderStatus.COMPLETED,
            type=OrderType.PICKUP,
            subtotal=total,
            total=total,
            created_at=t0 + timedelta(minutes=minute),
        ))

    # CANCELLED и PAID — в окне, но НЕ должны учитываться.
    db_session.add(Order(
        user_id=user.id,
        status=OrderStatus.CANCELLED,
        type=OrderType.PICKUP,
        subtotal=99999,
        total=99999,
        created_at=t0 + timedelta(minutes=40),
    ))
    db_session.add(Order(
        user_id=user.id,
        status=OrderStatus.PAID,
        type=OrderType.PICKUP,
        subtotal=99999,
        total=99999,
        created_at=t0 + timedelta(minutes=50),
    ))
    db_session.commit()

    assert get_revenue_and_count(db_session, t0, t1) == (75000, 3)


def test_get_revenue_and_count_excludes_out_of_range_orders(db_session) -> None:
    """2.4 — COMPLETED вне [start, end) исключаются."""
    from core_api.services.admin_stats import get_revenue_and_count

    t0 = datetime(2020, 3, 15, 0, 0, tzinfo=UTC)
    t1 = datetime(2020, 3, 16, 0, 0, tzinfo=UTC)

    user = make_user(db_session)
    db_session.commit()

    # За час до start
    db_session.add(Order(
        user_id=user.id,
        status=OrderStatus.COMPLETED,
        type=OrderType.PICKUP,
        subtotal=10000,
        total=10000,
        created_at=t0 - timedelta(hours=1),
    ))
    # За час после end
    db_session.add(Order(
        user_id=user.id,
        status=OrderStatus.COMPLETED,
        type=OrderType.PICKUP,
        subtotal=10000,
        total=10000,
        created_at=t1 + timedelta(hours=1),
    ))
    db_session.commit()

    assert get_revenue_and_count(db_session, t0, t1) == (0, 0)


def test_get_revenue_and_count_respects_half_open_interval(db_session) -> None:
    """2.5 — заказ, созданный ровно в end, не учитывается (half-open)."""
    from core_api.services.admin_stats import get_revenue_and_count

    t0 = datetime(2020, 4, 15, 0, 0, tzinfo=UTC)
    t1 = datetime(2020, 4, 16, 0, 0, tzinfo=UTC)

    user = make_user(db_session)
    db_session.commit()

    db_session.add(Order(
        user_id=user.id,
        status=OrderStatus.COMPLETED,
        type=OrderType.PICKUP,
        subtotal=10000,
        total=10000,
        created_at=t1,  # точно на границе end
    ))
    db_session.commit()

    assert get_revenue_and_count(db_session, t0, t1) == (0, 0)
