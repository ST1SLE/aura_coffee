"""RED: тесты CartService и CartValidationError (sections 4-7).

Все тесты ДОЛЖНЫ падать с ImportError / AttributeError до реализации cart.py.
Тесты, работающие с БД (sections 5-7), пропускаются без TEST_DATABASE_URL.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import fakeredis
import pytest

from tests.conftest import _TEST_DB_URL as TEST_DB_URL

_IS_SQLITE = TEST_DB_URL.startswith("sqlite")


# ===========================================================================
# 4. Cart service: contract
# ===========================================================================

def test_cart_service_importable_with_expected_methods() -> None:
    """CartService должен существовать с нужными методами."""
    from core_api.services.cart import CartService

    for method_name in ("get", "add_item", "update_item", "update_item_quantity", "delete_item", "clear"):
        assert callable(getattr(CartService, method_name, None)), (
            f"CartService не имеет callable-метода {method_name!r}"
        )


def test_cart_service_constructor_takes_session_and_redis() -> None:
    """CartService должен принимать session, redis_client, user_id, ttl_seconds."""
    from unittest.mock import MagicMock
    from core_api.services.cart import CartService

    fake_session = MagicMock()
    fake_redis = fakeredis.FakeRedis()

    # Не должно бросать исключений
    svc = CartService(
        session=fake_session,
        redis_client=fake_redis,
        user_id=42,
        ttl_seconds=60,
    )
    assert svc is not None


def test_cart_validation_error_exception_exists() -> None:
    """CartValidationError должен существовать и наследовать Exception."""
    from core_api.services.cart import CartValidationError

    assert issubclass(CartValidationError, Exception)

    # Должен конструироваться с reason-параметром
    err = CartValidationError("test_reason")
    assert err is not None


# ===========================================================================
# 5. Cart service: get
# ===========================================================================

@pytest.fixture
def svc_empty(cart_redis, db_session):
    """CartService с пустым Redis и реальной сессией."""
    from core_api.services.cart import CartService
    return CartService(
        session=db_session,
        redis_client=cart_redis,
        user_id=1,
        ttl_seconds=300,
    )


def test_get_returns_empty_cart_when_no_key(svc_empty, cart_redis) -> None:
    """get() без ключа в Redis → пустая CartResponse."""
    from core_api.schemas.cart import CartResponse

    cart = svc_empty.get()

    assert isinstance(cart, CartResponse)
    assert cart.items == []
    assert cart.subtotal == 0
    assert cart.currency == "RUB"
    assert cart.expires_at > datetime.now(tz=timezone.utc)


def test_get_hydrates_line_with_fresh_prices(cart_redis, db_session) -> None:
    """get() с данными в Redis читает цены из БД (не из кэша)."""
    pytest.importorskip("sqlalchemy")  # skip guard — db_session уже делает skip
    from core_api.services.cart import CartService
    from tests._factories.menu import make_menu_item

    item = make_menu_item(db_session, base_price=15000)
    db_session.flush()

    payload = json.dumps({
        "items": [
            {"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 2}
        ],
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    })
    cart_redis.set(f"cart:1", payload)

    svc = CartService(session=db_session, redis_client=cart_redis, user_id=1, ttl_seconds=300)
    cart = svc.get()

    assert len(cart.items) == 1
    line = cart.items[0]
    assert line.unit_price == 15000
    assert line.line_total == 30000
    assert cart.subtotal == 30000
    assert line.menu_item_snapshot.name_ru == item.name_ru


def test_get_reflects_updated_menu_price(cart_redis, db_session) -> None:
    """get() всегда читает актуальную цену из БД."""
    from core_api.services.cart import CartService
    from tests._factories.menu import make_menu_item

    item = make_menu_item(db_session, base_price=15000)
    db_session.flush()

    payload = json.dumps({
        "items": [
            {"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 1}
        ],
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    })
    cart_redis.set("cart:1", payload)

    # Обновляем цену в БД
    item.base_price = 17000
    db_session.flush()

    svc = CartService(session=db_session, redis_client=cart_redis, user_id=1, ttl_seconds=300)
    cart = svc.get()

    assert cart.items[0].unit_price == 17000


def test_get_refreshes_ttl_on_read(cart_redis, db_session) -> None:
    """get() продлевает TTL ключа корзины."""
    from core_api.services.cart import CartService
    from tests._factories.menu import make_menu_item

    item = make_menu_item(db_session, base_price=15000)
    db_session.flush()

    payload = json.dumps({
        "items": [
            {"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 1}
        ],
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    })
    cart_redis.set("cart:1", payload, ex=10)  # короткий TTL

    svc = CartService(session=db_session, redis_client=cart_redis, user_id=1, ttl_seconds=300)
    svc.get()

    ttl = cart_redis.ttl("cart:1")
    assert ttl >= 298, f"TTL должен быть ≈300, получено {ttl}"


def test_get_surfaces_stop_listed_item_without_removing(cart_redis, db_session) -> None:
    """get() не удаляет позицию, если товар попал в стоп-лист после добавления."""
    from core_api.services.cart import CartService
    from shared.enums import MenuItemAvailability
    from tests._factories.menu import make_menu_item

    item = make_menu_item(db_session, available=True)
    db_session.flush()

    payload = json.dumps({
        "items": [
            {"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 1}
        ],
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    })
    cart_redis.set("cart:1", payload)

    # Переводим в стоп-лист
    item.available = False
    db_session.flush()

    svc = CartService(session=db_session, redis_client=cart_redis, user_id=1, ttl_seconds=300)
    cart = svc.get()

    assert len(cart.items) == 1, "Строка должна остаться — get() не удаляет стоп-лист"
    assert cart.items[0].menu_item_snapshot.availability == MenuItemAvailability.STOP_LIST


def test_get_surfaces_archived_item_as_archived(cart_redis, db_session) -> None:
    """get() отображает архивный товар со статусом ARCHIVED."""
    from core_api.services.cart import CartService
    from shared.enums import MenuItemAvailability
    from tests._factories.menu import make_menu_item

    item = make_menu_item(db_session, available=True, archived=False)
    db_session.flush()

    payload = json.dumps({
        "items": [
            {"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 1}
        ],
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    })
    cart_redis.set("cart:1", payload)

    item.archived = True
    db_session.flush()

    svc = CartService(session=db_session, redis_client=cart_redis, user_id=1, ttl_seconds=300)
    cart = svc.get()

    assert len(cart.items) == 1
    assert cart.items[0].menu_item_snapshot.availability == MenuItemAvailability.ARCHIVED


# ===========================================================================
# 6. Cart service: add_item
# ===========================================================================

def test_add_item_creates_new_line(cart_redis, db_session) -> None:
    """add_item() создаёт строку в Redis и возвращает CartResponse."""
    from core_api.schemas.cart import CartItemCreate
    from core_api.services.cart import CartService
    from tests._factories.menu import make_menu_item, make_size_option, make_modifier
    from shared.enums import SizeLabel

    mod = make_modifier(db_session, price=5000)
    item = make_menu_item(db_session, base_price=15000, modifiers=[mod])
    size = make_size_option(db_session, item, label=SizeLabel.M, price=20000)
    db_session.flush()

    svc = CartService(session=db_session, redis_client=cart_redis, user_id=1, ttl_seconds=300)
    result = svc.add_item(CartItemCreate(
        menu_item_id=item.id,
        size_option_id=size.id,
        modifier_ids=[mod.id],
        quantity=2,
    ))

    assert len(result.items) == 1
    assert cart_redis.exists("cart:1") == 1
    assert cart_redis.ttl("cart:1") > 0


def test_add_item_persists_no_prices_in_redis(cart_redis, db_session) -> None:
    """Redis не хранит цены (INV-014)."""
    from core_api.schemas.cart import CartItemCreate
    from core_api.services.cart import CartService
    from tests._factories.menu import make_menu_item

    item = make_menu_item(db_session, base_price=15000)
    db_session.flush()

    svc = CartService(session=db_session, redis_client=cart_redis, user_id=1, ttl_seconds=300)
    svc.add_item(CartItemCreate(menu_item_id=item.id, quantity=1))

    raw = cart_redis.get("cart:1")
    assert raw is not None
    blob = json.loads(raw)

    forbidden_keys = {"unit_price", "line_total", "price", "subtotal",
                      "menu_item_snapshot", "size_snapshot", "modifiers_snapshot"}
    blob_str = json.dumps(blob)
    for key in forbidden_keys:
        assert f'"{key}"' not in blob_str, (
            f"Redis не должен хранить поле {key!r}"
        )


def test_add_item_sets_ttl_atomically(cart_redis, db_session) -> None:
    """TTL устанавливается атомарно вместе с SET."""
    from core_api.schemas.cart import CartItemCreate
    from core_api.services.cart import CartService
    from tests._factories.menu import make_menu_item

    item = make_menu_item(db_session, base_price=15000)
    db_session.flush()

    svc = CartService(session=db_session, redis_client=cart_redis, user_id=1, ttl_seconds=300)
    svc.add_item(CartItemCreate(menu_item_id=item.id, quantity=1))

    ttl = cart_redis.ttl("cart:1")
    assert ttl != -1, "TTL не должен быть -1 (бессрочный ключ)"
    assert ttl <= 300


def test_add_item_merges_into_existing_line_same_shape(cart_redis, db_session) -> None:
    """Добавление той же позиции увеличивает quantity, не создаёт дубликат."""
    from core_api.schemas.cart import CartItemCreate
    from core_api.services.cart import CartService
    from tests._factories.menu import make_menu_item

    item = make_menu_item(db_session, base_price=15000)
    db_session.flush()

    svc = CartService(session=db_session, redis_client=cart_redis, user_id=1, ttl_seconds=300)
    svc.add_item(CartItemCreate(menu_item_id=item.id, quantity=2))
    result = svc.add_item(CartItemCreate(menu_item_id=item.id, quantity=1))

    assert len(result.items) == 1
    assert result.items[0].quantity == 3


def test_add_item_merges_ignoring_modifier_order(cart_redis, db_session) -> None:
    """Порядок modifier_ids не влияет на line_id (merge должен произойти)."""
    from core_api.schemas.cart import CartItemCreate
    from core_api.services.cart import CartService
    from tests._factories.menu import make_menu_item, make_modifier

    mod1 = make_modifier(db_session, name_ru="Мод1", name_en="Mod1")
    mod2 = make_modifier(db_session, name_ru="Мод2", name_en="Mod2")
    item = make_menu_item(db_session, base_price=15000, modifiers=[mod1, mod2])
    db_session.flush()

    svc = CartService(session=db_session, redis_client=cart_redis, user_id=1, ttl_seconds=300)
    svc.add_item(CartItemCreate(menu_item_id=item.id, modifier_ids=[mod1.id, mod2.id], quantity=1))
    result = svc.add_item(CartItemCreate(menu_item_id=item.id, modifier_ids=[mod2.id, mod1.id], quantity=1))

    assert len(result.items) == 1
    assert result.items[0].quantity == 2


def test_add_item_rejects_stop_listed_menu_item(cart_redis, db_session) -> None:
    """add_item() отклоняет позицию в стоп-листе (INV-006)."""
    from core_api.schemas.cart import CartItemCreate
    from core_api.services.cart import CartService, CartValidationError
    from tests._factories.menu import make_menu_item

    item = make_menu_item(db_session, available=False)
    db_session.flush()

    svc = CartService(session=db_session, redis_client=cart_redis, user_id=1, ttl_seconds=300)

    with pytest.raises(CartValidationError):
        svc.add_item(CartItemCreate(menu_item_id=item.id, quantity=1))

    assert cart_redis.exists("cart:1") == 0, "Redis не должен быть записан"


def test_add_item_rejects_archived_menu_item(cart_redis, db_session) -> None:
    """add_item() отклоняет архивную позицию."""
    from core_api.schemas.cart import CartItemCreate
    from core_api.services.cart import CartService, CartValidationError
    from tests._factories.menu import make_menu_item

    item = make_menu_item(db_session, archived=True)
    db_session.flush()

    svc = CartService(session=db_session, redis_client=cart_redis, user_id=1, ttl_seconds=300)

    with pytest.raises(CartValidationError):
        svc.add_item(CartItemCreate(menu_item_id=item.id, quantity=1))


def test_add_item_rejects_stop_listed_size_option(cart_redis, db_session) -> None:
    """add_item() отклоняет недоступный size_option."""
    from core_api.schemas.cart import CartItemCreate
    from core_api.services.cart import CartService, CartValidationError
    from tests._factories.menu import make_menu_item, make_size_option
    from shared.enums import SizeLabel

    item = make_menu_item(db_session, base_price=15000)
    size = make_size_option(db_session, item, label=SizeLabel.M, available=False)
    db_session.flush()

    svc = CartService(session=db_session, redis_client=cart_redis, user_id=1, ttl_seconds=300)

    with pytest.raises(CartValidationError):
        svc.add_item(CartItemCreate(menu_item_id=item.id, size_option_id=size.id, quantity=1))


def test_add_item_rejects_stop_listed_modifier(cart_redis, db_session) -> None:
    """add_item() отклоняет недоступный modifier."""
    from core_api.schemas.cart import CartItemCreate
    from core_api.services.cart import CartService, CartValidationError
    from tests._factories.menu import make_menu_item, make_modifier

    mod_ok = make_modifier(db_session, name_ru="Доступный", name_en="Available", available=True)
    mod_bad = make_modifier(db_session, name_ru="Недоступный", name_en="Unavailable", available=False)
    item = make_menu_item(db_session, base_price=15000, modifiers=[mod_ok, mod_bad])
    db_session.flush()

    svc = CartService(session=db_session, redis_client=cart_redis, user_id=1, ttl_seconds=300)

    with pytest.raises(CartValidationError):
        svc.add_item(CartItemCreate(
            menu_item_id=item.id,
            modifier_ids=[mod_ok.id, mod_bad.id],
            quantity=1,
        ))


def test_add_item_rejects_size_from_different_menu_item(cart_redis, db_session) -> None:
    """size_option_id, принадлежащий другому menu_item, отклоняется."""
    from core_api.schemas.cart import CartItemCreate
    from core_api.services.cart import CartService, CartValidationError
    from tests._factories.menu import make_menu_item, make_size_option
    from shared.enums import SizeLabel

    item1 = make_menu_item(db_session, name_ru="Латте", name_en="Latte")
    item2 = make_menu_item(db_session, name_ru="Капучино", name_en="Cappuccino")
    size_of_item2 = make_size_option(db_session, item2, label=SizeLabel.L)
    db_session.flush()

    svc = CartService(session=db_session, redis_client=cart_redis, user_id=1, ttl_seconds=300)

    with pytest.raises(CartValidationError):
        svc.add_item(CartItemCreate(
            menu_item_id=item1.id,
            size_option_id=size_of_item2.id,
            quantity=1,
        ))


def test_add_item_rejects_modifier_not_linked_to_menu_item(cart_redis, db_session) -> None:
    """Modifier, не связанный с menu_item через M:N, отклоняется."""
    from core_api.schemas.cart import CartItemCreate
    from core_api.services.cart import CartService, CartValidationError
    from tests._factories.menu import make_menu_item, make_modifier

    unlinked_mod = make_modifier(db_session)
    item = make_menu_item(db_session, modifiers=[])  # нет модификаторов
    db_session.flush()

    svc = CartService(session=db_session, redis_client=cart_redis, user_id=1, ttl_seconds=300)

    with pytest.raises(CartValidationError):
        svc.add_item(CartItemCreate(
            menu_item_id=item.id,
            modifier_ids=[unlinked_mod.id],
            quantity=1,
        ))


def test_add_item_rejects_unknown_menu_item_id(cart_redis, db_session) -> None:
    """Несуществующий menu_item_id → CartValidationError."""
    from core_api.schemas.cart import CartItemCreate
    from core_api.services.cart import CartService, CartValidationError

    svc = CartService(session=db_session, redis_client=cart_redis, user_id=1, ttl_seconds=300)

    with pytest.raises(CartValidationError):
        svc.add_item(CartItemCreate(menu_item_id=999999, quantity=1))


def test_add_item_rejects_merge_exceeding_cap(cart_redis, db_session) -> None:
    """Слияние с превышением лимита 99 → CartValidationError, Redis не меняется."""
    from core_api.schemas.cart import CartItemCreate
    from core_api.services.cart import CartService, CartValidationError
    from tests._factories.menu import make_menu_item

    item = make_menu_item(db_session, base_price=15000)
    db_session.flush()

    # Вставляем строку с quantity=95 прямо в Redis
    payload = json.dumps({
        "items": [{"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 95}],
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    })
    cart_redis.set("cart:1", payload, ex=300)

    svc = CartService(session=db_session, redis_client=cart_redis, user_id=1, ttl_seconds=300)

    with pytest.raises(CartValidationError):
        svc.add_item(CartItemCreate(menu_item_id=item.id, quantity=10))

    # Проверяем, что количество не изменилось
    stored = json.loads(cart_redis.get("cart:1"))
    assert stored["items"][0]["quantity"] == 95


def test_add_item_no_partial_write_on_rejection(cart_redis, db_session) -> None:
    """При отклонении Redis остаётся без изменений."""
    from core_api.schemas.cart import CartItemCreate
    from core_api.services.cart import CartService, CartValidationError
    from tests._factories.menu import make_menu_item

    item = make_menu_item(db_session, available=False)
    db_session.flush()

    svc = CartService(session=db_session, redis_client=cart_redis, user_id=1, ttl_seconds=300)

    before_state = cart_redis.get("cart:1")  # None

    with pytest.raises(CartValidationError):
        svc.add_item(CartItemCreate(menu_item_id=item.id, quantity=1))

    after_state = cart_redis.get("cart:1")
    assert before_state == after_state, "Redis не должен изменяться при ошибке"


# ===========================================================================
# 7. Cart service: update_item, delete_item, clear
# ===========================================================================

def test_update_item_changes_quantity(cart_redis, db_session) -> None:
    """update_item() заменяет quantity строки (не суммирует)."""
    from core_api.schemas.cart import CartItemCreate, CartItemResponse
    from core_api.services.cart import CartService
    from tests._factories.menu import make_menu_item

    item = make_menu_item(db_session, base_price=15000)
    db_session.flush()

    svc = CartService(session=db_session, redis_client=cart_redis, user_id=1, ttl_seconds=300)
    result = svc.add_item(CartItemCreate(menu_item_id=item.id, quantity=2))
    line_id = result.items[0].line_id

    updated = svc.update_item(line_id, CartItemCreate(menu_item_id=item.id, quantity=4))

    assert len(updated.items) == 1
    assert updated.items[0].quantity == 4


def test_update_item_recomputes_line_id_when_modifiers_change(cart_redis, db_session) -> None:
    """Изменение модификаторов меняет line_id строки."""
    from core_api.schemas.cart import CartItemCreate, CartItemResponse
    from core_api.services.cart import CartService
    from tests._factories.menu import make_menu_item, make_modifier

    mod1 = make_modifier(db_session, name_ru="М1", name_en="M1")
    mod2 = make_modifier(db_session, name_ru="М2", name_en="M2")
    item = make_menu_item(db_session, modifiers=[mod1, mod2])
    db_session.flush()

    svc = CartService(session=db_session, redis_client=cart_redis, user_id=1, ttl_seconds=300)
    result = svc.add_item(CartItemCreate(menu_item_id=item.id, modifier_ids=[mod1.id], quantity=1))
    old_line_id = result.items[0].line_id

    updated = svc.update_item(
        old_line_id,
        CartItemCreate(menu_item_id=item.id, modifier_ids=[mod1.id, mod2.id], quantity=1),
    )

    new_line_ids = {line.line_id for line in updated.items}
    assert len(updated.items) == 1
    assert old_line_id not in new_line_ids, "Старый line_id должен исчезнуть"


def test_update_item_rejects_unknown_line_id(cart_redis, db_session) -> None:
    """update_item() с несуществующим line_id → CartValidationError."""
    from core_api.schemas.cart import CartItemCreate
    from core_api.services.cart import CartService, CartValidationError
    from tests._factories.menu import make_menu_item

    item = make_menu_item(db_session, base_price=15000)
    db_session.flush()

    svc = CartService(session=db_session, redis_client=cart_redis, user_id=1, ttl_seconds=300)

    with pytest.raises(CartValidationError):
        svc.update_item("deadbeefdeadbeef", CartItemCreate(menu_item_id=item.id, quantity=1))


def test_update_item_rejects_stop_listed_target_state(cart_redis, db_session) -> None:
    """update_item() отклоняет состояние, нарушающее INV-006."""
    from core_api.schemas.cart import CartItemCreate
    from core_api.services.cart import CartService, CartValidationError
    from tests._factories.menu import make_menu_item, make_size_option
    from shared.enums import SizeLabel

    item = make_menu_item(db_session, base_price=15000)
    size = make_size_option(db_session, item, label=SizeLabel.M, available=True)
    db_session.flush()

    svc = CartService(session=db_session, redis_client=cart_redis, user_id=1, ttl_seconds=300)
    result = svc.add_item(CartItemCreate(menu_item_id=item.id, size_option_id=size.id, quantity=2))
    line_id = result.items[0].line_id

    # Переводим size в стоп-лист
    size.available = False
    db_session.flush()

    with pytest.raises(CartValidationError):
        svc.update_item(line_id, CartItemCreate(menu_item_id=item.id, size_option_id=size.id, quantity=4))

    # Redis не изменился
    stored = json.loads(cart_redis.get("cart:1"))
    assert stored["items"][0]["quantity"] == 2


def test_update_item_refreshes_ttl(cart_redis, db_session) -> None:
    """update_item() продлевает TTL."""
    from core_api.schemas.cart import CartItemCreate
    from core_api.services.cart import CartService
    from tests._factories.menu import make_menu_item

    item = make_menu_item(db_session, base_price=15000)
    db_session.flush()

    svc = CartService(session=db_session, redis_client=cart_redis, user_id=1, ttl_seconds=300)
    result = svc.add_item(CartItemCreate(menu_item_id=item.id, quantity=2))
    line_id = result.items[0].line_id

    # Искусственно уменьшаем TTL
    cart_redis.expire("cart:1", 10)

    svc.update_item(line_id, CartItemCreate(menu_item_id=item.id, quantity=3))

    ttl = cart_redis.ttl("cart:1")
    assert ttl >= 298, f"TTL должен быть ≈300, получено {ttl}"


def test_update_item_quantity_changes_only_quantity(cart_redis, db_session) -> None:
    """update_item_quantity() обновляет только quantity, не трогая остальные поля."""
    from core_api.schemas.cart import CartItemCreate
    from core_api.services.cart import CartService
    from tests._factories.menu import make_menu_item

    item = make_menu_item(db_session, base_price=15000)
    db_session.flush()

    svc = CartService(session=db_session, redis_client=cart_redis, user_id=1, ttl_seconds=300)
    result = svc.add_item(CartItemCreate(menu_item_id=item.id, quantity=2))
    line_id = result.items[0].line_id

    updated = svc.update_item_quantity(line_id, 5)

    assert len(updated.items) == 1
    assert updated.items[0].quantity == 5
    assert updated.items[0].line_id == line_id


def test_update_item_quantity_rejects_unknown_line_id(cart_redis, db_session) -> None:
    """update_item_quantity() с несуществующим line_id → CartValidationError."""
    from core_api.services.cart import CartService, CartValidationError

    svc = CartService(session=db_session, redis_client=cart_redis, user_id=1, ttl_seconds=300)

    with pytest.raises(CartValidationError):
        svc.update_item_quantity("deadbeefdeadbeef", 3)


def test_update_item_quantity_rejects_stop_listed(cart_redis, db_session) -> None:
    """update_item_quantity() отклоняет обновление, если товар в стоп-листе."""
    from core_api.schemas.cart import CartItemCreate
    from core_api.services.cart import CartService, CartValidationError
    from tests._factories.menu import make_menu_item

    item = make_menu_item(db_session, base_price=15000, available=True)
    db_session.flush()

    svc = CartService(session=db_session, redis_client=cart_redis, user_id=1, ttl_seconds=300)
    result = svc.add_item(CartItemCreate(menu_item_id=item.id, quantity=2))
    line_id = result.items[0].line_id

    item.available = False
    db_session.flush()

    with pytest.raises(CartValidationError):
        svc.update_item_quantity(line_id, 5)

    stored = json.loads(cart_redis.get("cart:1"))
    assert stored["items"][0]["quantity"] == 2


def test_delete_item_removes_one_line(cart_redis, db_session) -> None:
    """delete_item() удаляет только одну строку из двух."""
    from core_api.schemas.cart import CartItemCreate
    from core_api.services.cart import CartService
    from tests._factories.menu import make_menu_item

    item1 = make_menu_item(db_session, name_ru="Латте", name_en="Latte", base_price=15000)
    item2 = make_menu_item(db_session, name_ru="Капучино", name_en="Cappuccino", base_price=17000)
    db_session.flush()

    svc = CartService(session=db_session, redis_client=cart_redis, user_id=1, ttl_seconds=300)
    r1 = svc.add_item(CartItemCreate(menu_item_id=item1.id, quantity=1))
    line_id_1 = r1.items[0].line_id
    svc.add_item(CartItemCreate(menu_item_id=item2.id, quantity=1))

    result = svc.delete_item(line_id_1)

    assert len(result.items) == 1
    assert result.items[0].menu_item_id == item2.id


def test_delete_item_rejects_unknown_line_id(cart_redis, db_session) -> None:
    """delete_item() с несуществующим line_id → CartValidationError."""
    from core_api.services.cart import CartService, CartValidationError
    from tests._factories.menu import make_menu_item
    from core_api.schemas.cart import CartItemCreate

    item = make_menu_item(db_session, base_price=15000)
    db_session.flush()

    svc = CartService(session=db_session, redis_client=cart_redis, user_id=1, ttl_seconds=300)
    svc.add_item(CartItemCreate(menu_item_id=item.id, quantity=1))

    state_before = cart_redis.get("cart:1")

    with pytest.raises(CartValidationError):
        svc.delete_item("deadbeefdeadbeef")

    assert cart_redis.get("cart:1") == state_before, "Redis не должен изменяться"


def test_delete_last_item_yields_empty_cart_read(cart_redis, db_session) -> None:
    """После удаления последней строки get() возвращает пустую корзину."""
    from core_api.schemas.cart import CartItemCreate
    from core_api.services.cart import CartService
    from tests._factories.menu import make_menu_item

    item = make_menu_item(db_session, base_price=15000)
    db_session.flush()

    svc = CartService(session=db_session, redis_client=cart_redis, user_id=1, ttl_seconds=300)
    r = svc.add_item(CartItemCreate(menu_item_id=item.id, quantity=1))
    line_id = r.items[0].line_id

    svc.delete_item(line_id)

    cart = svc.get()
    assert cart.items == []
    assert cart.subtotal == 0


def test_clear_deletes_redis_key(cart_redis, db_session) -> None:
    """clear() удаляет ключ cart:{user_id} из Redis."""
    from core_api.schemas.cart import CartItemCreate
    from core_api.services.cart import CartService
    from tests._factories.menu import make_menu_item

    item1 = make_menu_item(db_session, name_ru="Л", name_en="L", base_price=15000)
    item2 = make_menu_item(db_session, name_ru="К", name_en="K", base_price=17000)
    db_session.flush()

    svc = CartService(session=db_session, redis_client=cart_redis, user_id=1, ttl_seconds=300)
    svc.add_item(CartItemCreate(menu_item_id=item1.id, quantity=1))
    svc.add_item(CartItemCreate(menu_item_id=item2.id, quantity=1))

    svc.clear()

    assert cart_redis.exists("cart:1") == 0


def test_clear_is_idempotent_on_empty(cart_redis, db_session) -> None:
    """clear() на пустой корзине не бросает исключений, get() возвращает пустоту."""
    from core_api.services.cart import CartService

    svc = CartService(session=db_session, redis_client=cart_redis, user_id=1, ttl_seconds=300)

    svc.clear()  # не должно бросать

    cart = svc.get()
    assert cart.items == []
    assert cart.subtotal == 0


# ===========================================================================
# 9. Concurrency: WATCH/MULTI/EXEC retry (GREEN-phase addition)
# ===========================================================================

def test_add_item_concurrent_modification_retries(cart_redis, db_session) -> None:
    """Одновременная запись между WATCH и EXEC вызывает retry; финальный результат содержит обе мутации."""
    import json as _json
    from datetime import datetime, timezone
    from unittest.mock import patch as _patch

    from core_api.schemas.cart import CartItemCreate
    from core_api.services.cart import CartService
    from tests._factories.menu import make_menu_item

    item = make_menu_item(db_session, base_price=15000)
    db_session.flush()

    svc = CartService(session=db_session, redis_client=cart_redis, user_id=1, ttl_seconds=300)

    # Засеваем корзину напрямую
    payload = _json.dumps({
        "items": [{"menu_item_id": item.id, "size_option_id": None, "modifier_ids": [], "quantity": 1}],
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    })
    cart_redis.set("cart:1", payload, ex=300)

    original_pipeline = cart_redis.pipeline

    call_count = {"n": 0}

    def _pipeline_with_one_watch_error(*args, **kwargs):
        pipe = original_pipeline(*args, **kwargs)
        original_execute = pipe.execute

        def _execute_with_sabotage():
            # На первой попытке execute — подменяем ключ за спиной сервиса
            if call_count["n"] == 0:
                call_count["n"] += 1
                # Меняем quantity в Redis между WATCH и EXEC
                current = _json.loads(cart_redis.get("cart:1"))
                current["items"][0]["quantity"] = 2
                cart_redis.set("cart:1", _json.dumps(current), ex=300)
                # Возвращаем None (имитируем WatchError path) — fakeredis
                # не умеет самостоятельно инициировать WatchError, поэтому
                # вместо этого принудительно кидаем его здесь через патч
                import redis as _redis
                raise _redis.WatchError("simulated")
            return original_execute()

        pipe.execute = _execute_with_sabotage
        return pipe

    with _patch.object(cart_redis, "pipeline", side_effect=_pipeline_with_one_watch_error):
        result = svc.add_item(CartItemCreate(menu_item_id=item.id, quantity=3))

    # После retry: quantity = 2 (из Redis) + 3 (новый) = 5
    assert len(result.items) == 1
    assert result.items[0].quantity == 5
