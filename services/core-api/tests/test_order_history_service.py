"""RED: тесты сервиса list_orders (order-history capability, PDD §7.7).

Все импорты core_api.services.order_history выполняются ВНУТРИ тел тестов —
в RED-фазе модуль отсутствует, и import на уровне файла сорвал бы сборку.

БД-тесты требуют PostgreSQL (db_session фикстура skip-ает на sqlite).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from tests._factories.orders import (
    HistoryItemSpec,
    make_user,
    seed_history_order,
    seed_n_orders_for_user,
)


# ---------------------------------------------------------------------------
# 2.1 — модуль отсутствует (RED-маркер: ModuleNotFoundError)
# ---------------------------------------------------------------------------

def test_list_orders_module_missing() -> None:
    """В RED-фазе core_api.services.order_history не существует."""
    from core_api.services.order_history import list_orders  # noqa: F401

    # Если мы сюда дошли — модуль уже реализован (GREEN). Тест проходит.
    assert callable(list_orders)


# ---------------------------------------------------------------------------
# 2.2 — пустая история
# ---------------------------------------------------------------------------

def test_list_orders_empty_user_returns_zero_total(db_session) -> None:
    """Пользователь без заказов → total_count=0, orders=[]."""
    from core_api.services.order_history import list_orders

    user = make_user(db_session)
    db_session.commit()

    result = list_orders(user_id=user.id, page=1, per_page=20, db_session=db_session)

    assert getattr(result, "orders", None) == [] or result["orders"] == []
    assert (getattr(result, "total_count", None) or result["total_count"]) == 0
    assert (getattr(result, "page", None) or result["page"]) == 1
    assert (getattr(result, "per_page", None) or result["per_page"]) == 20


# ---------------------------------------------------------------------------
# 2.3 — сортировка created_at DESC
# ---------------------------------------------------------------------------

def test_list_orders_sorts_desc_by_created_at(db_session) -> None:
    """3 заказа T1<T2<T3 → результат [T3, T2, T1]."""
    from core_api.services.order_history import list_orders

    user = make_user(db_session)
    db_session.commit()

    t0 = datetime.now(tz=UTC) - timedelta(hours=3)
    ids_asc = seed_n_orders_for_user(
        db_session, user, count=3, base_time=t0, step=timedelta(minutes=30)
    )
    # ids_asc: [id_T1, id_T2, id_T3] (в порядке создания)

    result = list_orders(user_id=user.id, page=1, per_page=20, db_session=db_session)
    orders = getattr(result, "orders", None) or result["orders"]
    returned_ids = [getattr(o, "id", None) or o["id"] for o in orders]

    assert returned_ids == list(reversed(ids_asc)), (
        f"expected DESC [T3, T2, T1], got {returned_ids}"
    )


# ---------------------------------------------------------------------------
# 2.4 — пагинация: слайс и total_count
# ---------------------------------------------------------------------------

def test_list_orders_pagination_slice_and_total(db_session) -> None:
    """25 заказов, page=2, per_page=10 → total=25, orders = DESC-slice 11..20."""
    from core_api.services.order_history import list_orders

    user = make_user(db_session)
    db_session.commit()

    t0 = datetime.now(tz=UTC) - timedelta(hours=25)
    ids_asc = seed_n_orders_for_user(
        db_session, user, count=25, base_time=t0, step=timedelta(minutes=1)
    )
    ids_desc = list(reversed(ids_asc))  # [T25, T24, ..., T1]

    result = list_orders(user_id=user.id, page=2, per_page=10, db_session=db_session)
    orders = getattr(result, "orders", None) or result["orders"]
    returned_ids = [getattr(o, "id", None) or o["id"] for o in orders]

    total = getattr(result, "total_count", None) or result["total_count"]
    assert total == 25
    assert returned_ids == ids_desc[10:20]


# ---------------------------------------------------------------------------
# 2.5 — без утечек между пользователями
# ---------------------------------------------------------------------------

def test_list_orders_does_not_leak_across_users(db_session) -> None:
    """A: 3 заказа, B: 2 заказа → list_orders(A) возвращает только A."""
    from core_api.services.order_history import list_orders

    user_a = make_user(db_session)
    user_b = make_user(db_session)
    db_session.commit()

    seed_n_orders_for_user(db_session, user_a, count=3)
    seed_n_orders_for_user(db_session, user_b, count=2)

    result = list_orders(user_id=user_a.id, page=1, per_page=20, db_session=db_session)
    orders = getattr(result, "orders", None) or result["orders"]
    total = getattr(result, "total_count", None) or result["total_count"]

    assert total == 3
    for o in orders:
        owner = getattr(o, "user_id", None) or o["user_id"]
        assert owner == user_a.id


# ---------------------------------------------------------------------------
# 2.6 — order_items подгружаются eagerly
# ---------------------------------------------------------------------------

def test_list_orders_eagerly_loads_items(db_session) -> None:
    """Обращение к order.items НЕ должно вызывать дополнительных SELECT FROM order_items."""
    from sqlalchemy import event

    from core_api.services.order_history import list_orders

    user = make_user(db_session)
    db_session.commit()

    # 3 заказа, каждый с 1 item
    seed_n_orders_for_user(db_session, user, count=3)

    engine = db_session.get_bind()
    item_selects: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def _before_cursor(conn, cursor, statement, parameters, context, executemany):
        sl = statement.lower()
        if "from order_items" in sl:
            item_selects.append(statement)

    try:
        result = list_orders(user_id=user.id, page=1, per_page=20, db_session=db_session)
        orders = getattr(result, "orders", None) or result["orders"]

        # Зафиксируем число SELECT order_items ДО обхода relationship
        selects_before = len(item_selects)

        # Теперь обходим items — если они не eager, здесь пойдут N дополнительных запросов.
        for o in orders:
            items = getattr(o, "items", None)
            if items is None:
                # Если результат — dict / pydantic, пропускаем (eager-тест имеет смысл
                # только для ORM-инстансов; если сервис возвращает Pydantic — assert
                # делается по списку items в DTO, загруженному за один pass).
                items = getattr(o, "order_items", None)
            # Форсируем материализацию
            list(items or [])

        selects_after = len(item_selects)
    finally:
        event.remove(engine, "before_cursor_execute", _before_cursor)

    assert selects_after == selects_before, (
        f"Lazy load обнаружен: {selects_after - selects_before} доп. SELECT FROM order_items. "
        f"Запросы: {item_selects[selects_before:]}"
    )
