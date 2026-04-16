"""RED: тесты сервиса repeat_order (order-repeat capability, PDD §7.7).

Все импорты core_api.services.order_repeat выполняются ВНУТРИ тел тестов.

БД-тесты требуют PostgreSQL (db_session фикстура skip-ает на sqlite).
"""
from __future__ import annotations

import json
from typing import Any

import fakeredis
import pytest
from sqlalchemy import text

from shared.enums import SizeLabel
from shared.models.menu import Modifier, SizeOption
from tests._factories.menu import (
    make_category,
    make_menu_item,
    make_modifier,
    make_size_option,
)
from tests._factories.orders import (
    HistoryItemSpec,
    make_user,
    seed_history_order,
)


# ---------------------------------------------------------------------------
# 3.1 — модуль отсутствует
# ---------------------------------------------------------------------------

def test_repeat_order_module_missing() -> None:
    from core_api.services.order_repeat import repeat_order  # noqa: F401

    assert callable(repeat_order)


# ---------------------------------------------------------------------------
# Вспомогательный fake CartService, записывающий add_item вызовы.
# ---------------------------------------------------------------------------

class _AddItemRecorder:
    """Перехватчик CartService.add_item — записывает аргументы каждого вызова."""

    def __init__(self) -> None:
        self.calls: list[Any] = []

    def __call__(self, self_cart, item, *args, **kwargs):  # noqa: D401
        """Сигнатура совпадает с CartService.add_item(self, item)."""
        self.calls.append(item)
        # Возвращаем минимально валидный объект — сервисы могут игнорировать
        return None


@pytest.fixture
def recorded_add_item(monkeypatch):
    """Патчит CartService.add_item на рекордер. Возвращает рекордер."""
    from core_api.services.cart import CartService

    recorder = _AddItemRecorder()
    monkeypatch.setattr(CartService, "add_item", recorder, raising=True)
    return recorder


# ---------------------------------------------------------------------------
# 3.2 — happy path: все позиции доступны, текущие цены
# ---------------------------------------------------------------------------

def test_repeat_happy_path_adds_all_items_with_current_prices(
    db_session, recorded_add_item
) -> None:
    """Все 3 позиции доступны → CartService.add_item вызван 3 раза без цен в payload."""
    from core_api.services.order_repeat import repeat_order

    user = make_user(db_session)
    cat = make_category(db_session)
    mi1 = make_menu_item(db_session, cat, base_price=15000, name_ru="Латте")
    mi2 = make_menu_item(db_session, cat, base_price=20000, name_ru="Капучино")
    mi3 = make_menu_item(db_session, cat, base_price=25000, name_ru="Флэт уайт")

    # В снимке заказа цены ДРУГИЕ (ниже), чем текущие — чтобы убедиться,
    # что сервис передаёт в CartItemCreate только id, а цены read from DB.
    seed = seed_history_order(
        db_session,
        user=user,
        items=[
            HistoryItemSpec(menu_item=mi1, unit_price=10000, quantity=2),
            HistoryItemSpec(menu_item=mi2, unit_price=12000, quantity=1),
            HistoryItemSpec(menu_item=mi3, unit_price=14000, quantity=3),
        ],
    )

    fake_redis = fakeredis.FakeRedis()
    result = repeat_order(
        order_id=seed.order_id,
        user_id=user.id,
        redis=fake_redis,
        db_session=db_session,
    )

    assert len(recorded_add_item.calls) == 3
    for call_item in recorded_add_item.calls:
        # CartItemCreate не должен содержать unit_price/line_total/price
        data = getattr(call_item, "model_dump", lambda: dict(call_item))()
        for forbidden in ("unit_price", "line_total", "price"):
            assert forbidden not in data, f"CartItemCreate содержит {forbidden}: {data}"

    added = getattr(result, "added_to_cart", None) or result["added_to_cart"]
    skipped = getattr(result, "skipped", None) or result["skipped"]
    assert added == 3
    assert skipped == []


# ---------------------------------------------------------------------------
# 3.3 — чужой заказ отклоняется
# ---------------------------------------------------------------------------

def test_repeat_rejects_other_users_order(db_session, recorded_add_item) -> None:
    """repeat_order(chужой order_id, user_id=A) → raises, add_item не вызван."""
    from core_api.services.order_repeat import repeat_order

    user_a = make_user(db_session)
    user_b = make_user(db_session)
    db_session.commit()

    cat = make_category(db_session)
    mi = make_menu_item(db_session, cat, base_price=15000)
    seed_b = seed_history_order(
        db_session, user=user_b, items=[HistoryItemSpec(menu_item=mi)]
    )

    fake_redis = fakeredis.FakeRedis()
    with pytest.raises(Exception):
        repeat_order(
            order_id=seed_b.order_id,
            user_id=user_a.id,
            redis=fake_redis,
            db_session=db_session,
        )

    assert recorded_add_item.calls == []


# ---------------------------------------------------------------------------
# 3.4 — позиция в стоп-листе пропускается
# ---------------------------------------------------------------------------

def test_repeat_skips_stop_listed_item(db_session, recorded_add_item) -> None:
    """MenuItem.available=False → позиция пропущена, notification menu_item_unavailable."""
    from core_api.services.order_repeat import repeat_order

    user = make_user(db_session)
    cat = make_category(db_session)
    mi_ok = make_menu_item(db_session, cat, base_price=15000, name_ru="Латте")
    mi_stop = make_menu_item(
        db_session, cat, base_price=20000, name_ru="Капучино", available=False
    )

    seed = seed_history_order(
        db_session,
        user=user,
        items=[
            HistoryItemSpec(menu_item=mi_ok),
            HistoryItemSpec(menu_item=mi_stop),
        ],
    )

    fake_redis = fakeredis.FakeRedis()
    result = repeat_order(
        order_id=seed.order_id,
        user_id=user.id,
        redis=fake_redis,
        db_session=db_session,
    )

    # В корзину ушла только одна позиция
    assert len(recorded_add_item.calls) == 1

    skipped = getattr(result, "skipped", None) or result["skipped"]
    assert len(skipped) == 1
    entry = skipped[0]
    reason = getattr(entry, "reason", None) or entry["reason"]
    message = getattr(entry, "message_ru", None) or entry["message_ru"]
    assert reason == "menu_item_unavailable"
    assert message == f"{mi_stop.name_ru} сейчас недоступен"


# ---------------------------------------------------------------------------
# 3.5 — архивная позиция пропускается
# ---------------------------------------------------------------------------

def test_repeat_skips_archived_item(db_session, recorded_add_item) -> None:
    """MenuItem.archived=True → пропущен, notification menu_item_archived."""
    from core_api.services.order_repeat import repeat_order

    user = make_user(db_session)
    cat = make_category(db_session)
    mi_arch = make_menu_item(
        db_session, cat, base_price=20000, name_ru="Старый капучино", archived=True
    )

    seed = seed_history_order(
        db_session,
        user=user,
        items=[HistoryItemSpec(menu_item=mi_arch)],
    )

    fake_redis = fakeredis.FakeRedis()
    with pytest.raises(Exception):
        # Все позиции недоступны → raise
        repeat_order(
            order_id=seed.order_id,
            user_id=user.id,
            redis=fake_redis,
            db_session=db_session,
        )

    # Добавим ещё одну доступную позицию и повторим, чтобы проверить skipped-notification.
    cat2 = make_category(db_session, name_ru="Cat2", name_en="Cat2")
    mi_ok = make_menu_item(db_session, cat2, base_price=15000, name_ru="Латте2")
    seed2 = seed_history_order(
        db_session,
        user=user,
        items=[
            HistoryItemSpec(menu_item=mi_ok),
            HistoryItemSpec(menu_item=mi_arch),
        ],
    )
    recorded_add_item.calls.clear()

    result = repeat_order(
        order_id=seed2.order_id,
        user_id=user.id,
        redis=fake_redis,
        db_session=db_session,
    )

    skipped = getattr(result, "skipped", None) or result["skipped"]
    assert len(skipped) == 1
    entry = skipped[0]
    reason = getattr(entry, "reason", None) or entry["reason"]
    message = getattr(entry, "message_ru", None) or entry["message_ru"]
    assert reason == "menu_item_archived"
    assert message == f"{mi_arch.name_ru} больше не в меню"


# ---------------------------------------------------------------------------
# 3.6 — удалённая позиция пропускается
# ---------------------------------------------------------------------------

def test_repeat_skips_deleted_item(db_session, recorded_add_item) -> None:
    """menu_item_id ссылается на несуществующую строку → пропущен, menu_item_deleted."""
    from core_api.services.order_repeat import repeat_order

    user = make_user(db_session)
    cat = make_category(db_session)
    mi_ok = make_menu_item(db_session, cat, base_price=15000, name_ru="Латте")

    # Id, которого нет в БД (большое число, уникальное)
    stale_id = 9_999_999_991

    seed = seed_history_order(
        db_session,
        user=user,
        items=[
            HistoryItemSpec(menu_item=mi_ok),
            HistoryItemSpec(menu_item=None, stale_menu_item_id=stale_id, unit_price=10000),
        ],
    )

    fake_redis = fakeredis.FakeRedis()
    result = repeat_order(
        order_id=seed.order_id,
        user_id=user.id,
        redis=fake_redis,
        db_session=db_session,
    )

    assert len(recorded_add_item.calls) == 1
    skipped = getattr(result, "skipped", None) or result["skipped"]
    assert len(skipped) == 1
    entry = skipped[0]
    reason = getattr(entry, "reason", None) or entry["reason"]
    message = getattr(entry, "message_ru", None) or entry["message_ru"]
    assert reason == "menu_item_deleted"
    assert message == "Позиция больше не в меню"


# ---------------------------------------------------------------------------
# 3.7 — недоступный размер → пропускается ВСЯ позиция
# ---------------------------------------------------------------------------

def test_repeat_size_unavailable_skips_entire_item(db_session, recorded_add_item) -> None:
    """SizeOption.available=False → пропускается вся позиция, size_unavailable."""
    from core_api.services.order_repeat import repeat_order

    user = make_user(db_session)
    cat = make_category(db_session)
    mi = make_menu_item(db_session, cat, base_price=15000, name_ru="Латте")
    size_bad = make_size_option(
        db_session, mi, label=SizeLabel.L, price=18000, available=False
    )

    seed = seed_history_order(
        db_session,
        user=user,
        items=[
            HistoryItemSpec(
                menu_item=mi,
                size_option=size_bad,
                size_label=SizeLabel.L,
            ),
        ],
    )

    fake_redis = fakeredis.FakeRedis()
    with pytest.raises(Exception):
        # Единственная позиция → все недоступны → raise
        repeat_order(
            order_id=seed.order_id,
            user_id=user.id,
            redis=fake_redis,
            db_session=db_session,
        )

    # Добавим вторую доступную позицию и проверим skipped-entry отдельно.
    mi2 = make_menu_item(db_session, cat, base_price=12000, name_ru="Эспрессо")
    seed2 = seed_history_order(
        db_session,
        user=user,
        items=[
            HistoryItemSpec(menu_item=mi2),
            HistoryItemSpec(
                menu_item=mi,
                size_option=size_bad,
                size_label=SizeLabel.L,
            ),
        ],
    )
    recorded_add_item.calls.clear()

    result = repeat_order(
        order_id=seed2.order_id,
        user_id=user.id,
        redis=fake_redis,
        db_session=db_session,
    )

    # Вторая позиция ушла в корзину, первая с size — нет.
    assert len(recorded_add_item.calls) == 1
    skipped = getattr(result, "skipped", None) or result["skipped"]
    assert len(skipped) == 1
    entry = skipped[0]
    reason = getattr(entry, "reason", None) or entry["reason"]
    message = getattr(entry, "message_ru", None) or entry["message_ru"]
    assert reason == "size_unavailable"
    assert message == f"Размер {SizeLabel.L.value} для {mi.name_ru} недоступен"


# ---------------------------------------------------------------------------
# 3.8 — недоступный модификатор: позиция добавляется без него
# ---------------------------------------------------------------------------

def test_repeat_modifier_unavailable_keeps_item(db_session, recorded_add_item) -> None:
    """Два модификатора в снимке, один unavailable → item добавлен без него, notif."""
    from core_api.services.order_repeat import repeat_order

    user = make_user(db_session)
    cat = make_category(db_session)
    mod_ok = make_modifier(db_session, name_ru="Сироп ваниль", price=5000, available=True)
    mod_bad = make_modifier(db_session, name_ru="Карамель", price=5000, available=False)
    mi = make_menu_item(
        db_session,
        cat,
        base_price=15000,
        name_ru="Латте",
        modifiers=[mod_ok, mod_bad],
    )

    seed = seed_history_order(
        db_session,
        user=user,
        items=[
            HistoryItemSpec(
                menu_item=mi,
                modifiers_snapshot_ids=[mod_ok.id, mod_bad.id],
            ),
        ],
    )

    fake_redis = fakeredis.FakeRedis()
    result = repeat_order(
        order_id=seed.order_id,
        user_id=user.id,
        redis=fake_redis,
        db_session=db_session,
    )

    # Позиция добавлена с ОДНИМ модификатором (доступным).
    assert len(recorded_add_item.calls) == 1
    call_item = recorded_add_item.calls[0]
    data = getattr(call_item, "model_dump", lambda: dict(call_item))()
    assert data.get("modifier_ids") == [mod_ok.id]

    skipped = getattr(result, "skipped", None) or result["skipped"]
    assert len(skipped) == 1
    entry = skipped[0]
    reason = getattr(entry, "reason", None) or entry["reason"]
    assert reason == "modifier_unavailable"


# ---------------------------------------------------------------------------
# 3.9 — все позиции недоступны → доменная ошибка
# ---------------------------------------------------------------------------

def test_repeat_all_items_unavailable_raises(db_session, recorded_add_item) -> None:
    """Все позиции невалидны → raise с фиксированным RU-сообщением."""
    from core_api.services.order_repeat import repeat_order

    user = make_user(db_session)
    cat = make_category(db_session)
    mi_stop = make_menu_item(
        db_session, cat, base_price=15000, name_ru="Латте", available=False
    )
    mi_arch = make_menu_item(
        db_session, cat, base_price=20000, name_ru="Капучино", archived=True
    )

    seed = seed_history_order(
        db_session,
        user=user,
        items=[
            HistoryItemSpec(menu_item=mi_stop),
            HistoryItemSpec(menu_item=mi_arch),
        ],
    )

    fake_redis = fakeredis.FakeRedis()
    with pytest.raises(Exception) as excinfo:
        repeat_order(
            order_id=seed.order_id,
            user_id=user.id,
            redis=fake_redis,
            db_session=db_session,
        )

    assert str(excinfo.value) == "Ни одна позиция из этого заказа сейчас недоступна" or \
        "Ни одна позиция из этого заказа сейчас недоступна" in str(excinfo.value)
    assert recorded_add_item.calls == []


# ---------------------------------------------------------------------------
# 3.10 — repeat не создаёт новый Order
# ---------------------------------------------------------------------------

def test_repeat_does_not_create_new_order_row(db_session, recorded_add_item) -> None:
    """SELECT count(*) FROM orders неизменён после repeat_order (success или raise)."""
    from core_api.services.order_repeat import repeat_order

    user = make_user(db_session)
    cat = make_category(db_session)
    mi = make_menu_item(db_session, cat, base_price=15000)

    seed = seed_history_order(
        db_session, user=user, items=[HistoryItemSpec(menu_item=mi)]
    )

    fake_redis = fakeredis.FakeRedis()
    before = db_session.execute(text("SELECT count(*) FROM orders")).scalar_one()

    repeat_order(
        order_id=seed.order_id,
        user_id=user.id,
        redis=fake_redis,
        db_session=db_session,
    )

    after = db_session.execute(text("SELECT count(*) FROM orders")).scalar_one()
    assert before == after


# ---------------------------------------------------------------------------
# 3.11 — форма RepeatOrderResult
# ---------------------------------------------------------------------------

def test_repeat_result_shape(db_session, recorded_add_item) -> None:
    """RepeatOrderResult имеет ровно поля added_to_cart и skipped."""
    from core_api.services.order_repeat import RepeatOrderResult

    # Pydantic v2 model? dataclass?
    if hasattr(RepeatOrderResult, "model_fields"):
        fields = set(RepeatOrderResult.model_fields.keys())
    else:
        import dataclasses

        fields = {f.name for f in dataclasses.fields(RepeatOrderResult)}

    assert fields == {"added_to_cart", "skipped"}
