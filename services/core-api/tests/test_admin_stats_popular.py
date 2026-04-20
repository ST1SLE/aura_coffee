"""RED: тесты хелпера get_popular_items (dashboard-api-red).

Группировка — по снимку (name_ru, name_en) из order_items (INV-014).
Окна created_at — в далёком прошлом, по месяцу на тест, чтобы данные
из соседних тестов не пересекались.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from shared.enums import OrderStatus, OrderType
from shared.models.order import Order
from shared.models.order_item import OrderItem
from tests._factories.orders import make_user


# ===========================================================================
# 3.x — get_popular_items aggregation tests
# ===========================================================================


def _seed_order_with_item(
    db_session,
    *,
    user_id,
    status: OrderStatus,
    created_at: datetime,
    name_ru: str,
    name_en: str,
    quantity: int,
    menu_item_id: int | None = None,
    unit_price: int = 10000,
) -> Order:
    """Создаёт один Order + один OrderItem с заданным snapshot-именем."""
    order = Order(
        user_id=user_id,
        status=status,
        type=OrderType.PICKUP,
        subtotal=unit_price * quantity,
        total=unit_price * quantity,
        created_at=created_at,
    )
    db_session.add(order)
    db_session.flush()

    db_session.add(OrderItem(
        order_id=order.id,
        menu_item_id=menu_item_id,
        menu_item_name_ru=name_ru,
        menu_item_name_en=name_en,
        unit_price=unit_price,
        modifiers_snapshot=[],
        quantity=quantity,
        line_total=unit_price * quantity,
    ))
    db_session.flush()
    return order


def test_get_popular_items_symbol_absent() -> None:
    """3.1 — символ get_popular_items должен существовать после GREEN."""
    from core_api.services.admin_stats import get_popular_items  # noqa: F401

    assert callable(get_popular_items)


def test_get_popular_items_same_snapshot_aggregates_to_one_row(db_session) -> None:
    """3.2 — одинаковый snapshot (name_ru, name_en) → одна строка, quantity=сумма."""
    from core_api.services.admin_stats import get_popular_items

    t0 = datetime(2020, 5, 15, 0, 0, tzinfo=UTC)
    t1 = datetime(2020, 5, 16, 0, 0, tzinfo=UTC)

    user = make_user(db_session)
    db_session.commit()

    _seed_order_with_item(
        db_session, user_id=user.id, status=OrderStatus.COMPLETED,
        created_at=t0 + timedelta(minutes=10),
        name_ru="Латте", name_en="Latte", quantity=2,
    )
    _seed_order_with_item(
        db_session, user_id=user.id, status=OrderStatus.COMPLETED,
        created_at=t0 + timedelta(minutes=20),
        name_ru="Латте", name_en="Latte", quantity=3,
    )
    db_session.commit()

    result = get_popular_items(db_session, t0, t1)

    matching = [row for row in result if row.name_ru == "Латте" and row.name_en == "Latte"]
    assert len(matching) == 1
    assert matching[0].quantity == 5


def test_get_popular_items_different_snapshots_produce_two_rows(db_session) -> None:
    """3.3 — один menu_item_id, разные snapshot-имена → две строки (INV-014)."""
    from core_api.services.admin_stats import get_popular_items

    t0 = datetime(2020, 6, 15, 0, 0, tzinfo=UTC)
    t1 = datetime(2020, 6, 16, 0, 0, tzinfo=UTC)

    user = make_user(db_session)
    db_session.commit()

    shared_menu_item_id = 424242

    _seed_order_with_item(
        db_session, user_id=user.id, status=OrderStatus.COMPLETED,
        created_at=t0 + timedelta(minutes=10),
        name_ru="Латте", name_en="Latte", quantity=1,
        menu_item_id=shared_menu_item_id,
    )
    _seed_order_with_item(
        db_session, user_id=user.id, status=OrderStatus.COMPLETED,
        created_at=t0 + timedelta(minutes=20),
        name_ru="Латте Ваниль", name_en="Vanilla Latte", quantity=1,
        menu_item_id=shared_menu_item_id,
    )
    db_session.commit()

    result = get_popular_items(db_session, t0, t1)

    matching = [
        row for row in result
        if row.name_ru in {"Латте", "Латте Ваниль"}
        and row.name_en in {"Latte", "Vanilla Latte"}
    ]
    assert len(matching) == 2
    for row in matching:
        assert row.quantity == 1
    names = {(row.name_ru, row.name_en) for row in matching}
    assert names == {("Латте", "Latte"), ("Латте Ваниль", "Vanilla Latte")}


def test_get_popular_items_cancelled_excluded(db_session) -> None:
    """3.4 — CANCELLED-заказы исключаются из выборки."""
    from core_api.services.admin_stats import get_popular_items

    t0 = datetime(2020, 7, 15, 0, 0, tzinfo=UTC)
    t1 = datetime(2020, 7, 16, 0, 0, tzinfo=UTC)

    user = make_user(db_session)
    db_session.commit()

    _seed_order_with_item(
        db_session, user_id=user.id, status=OrderStatus.CANCELLED,
        created_at=t0 + timedelta(minutes=10),
        name_ru="X", name_en="X", quantity=99,
    )
    _seed_order_with_item(
        db_session, user_id=user.id, status=OrderStatus.COMPLETED,
        created_at=t0 + timedelta(minutes=20),
        name_ru="Y", name_en="Y", quantity=1,
    )
    db_session.commit()

    result = get_popular_items(db_session, t0, t1)

    names = {(row.name_ru, row.name_en) for row in result}
    assert ("Y", "Y") in names
    assert ("X", "X") not in names


def test_get_popular_items_limits_to_ten_ordered_desc(db_session) -> None:
    """3.5 — 11 разных snapshot → 10 строк по quantity DESC, без quantity=1."""
    from core_api.services.admin_stats import get_popular_items

    t0 = datetime(2020, 8, 15, 0, 0, tzinfo=UTC)
    t1 = datetime(2020, 8, 16, 0, 0, tzinfo=UTC)

    user = make_user(db_session)
    db_session.commit()

    # Сеем 11 уникальных (name_ru_i, name_en_i) с quantity=i для i=1..11.
    for i in range(1, 12):
        _seed_order_with_item(
            db_session, user_id=user.id, status=OrderStatus.COMPLETED,
            created_at=t0 + timedelta(minutes=i),
            name_ru=f"name_ru_{i}", name_en=f"name_en_{i}", quantity=i,
        )
    db_session.commit()

    result = get_popular_items(db_session, t0, t1, limit=10)

    # Оставляем только строки из этого теста.
    filtered = [row for row in result if row.name_ru.startswith("name_ru_")]
    assert len(filtered) == 10

    quantities = [row.quantity for row in filtered]
    assert quantities == sorted(quantities, reverse=True)
    assert quantities[0] == 11
    assert quantities[-1] == 2
    assert 1 not in quantities


def test_get_popular_items_out_of_range_excluded(db_session) -> None:
    """3.6 — заказы вне [start, end) исключаются."""
    from core_api.services.admin_stats import get_popular_items

    t0 = datetime(2020, 9, 15, 0, 0, tzinfo=UTC)
    t1 = datetime(2020, 9, 16, 0, 0, tzinfo=UTC)

    user = make_user(db_session)
    db_session.commit()

    _seed_order_with_item(
        db_session, user_id=user.id, status=OrderStatus.COMPLETED,
        created_at=t0 - timedelta(hours=1),
        name_ru="A", name_en="A", quantity=100,
    )
    _seed_order_with_item(
        db_session, user_id=user.id, status=OrderStatus.COMPLETED,
        created_at=t0 + timedelta(minutes=30),
        name_ru="B", name_en="B", quantity=1,
    )
    db_session.commit()

    result = get_popular_items(db_session, t0, t1)

    names = {(row.name_ru, row.name_en) for row in result}
    assert ("B", "B") in names
    assert ("A", "A") not in names
