"""RED: тесты валидатора стоп-листа (PDD §7.2 шаг 1, INV-006).

Контракт `validate_stop_list(cart_items, db_session)`:
- Загружает текущее состояние MenuItem / SizeOption / Modifier из БД.
- Если что-то `available=False` → raises StopListError (из
  core_api.services.validators.exceptions).
- Возвращает список валидированных позиций со свежими ценами (INV-006:
  "все цены берутся из БД на момент расчёта, не из кэша клиента").

Формат cart_items (формализуется в GREEN): список dict со структурой
{"menu_item_id": int, "size_option_id": int | None, "modifier_ids": list[int],
 "quantity": int, "unit_price": int (stale, проверяем что validator перезапишет)}.

Каждая функция импортирует target внутри тела — ImportError всплывёт как
падение конкретного теста.
"""
from __future__ import annotations

import pytest


def test_validate_stop_list_all_available_returns_validated_items(db_session) -> None:
    from core_api.services.validators import validate_stop_list
    from tests._factories.menu import make_menu_item

    item = make_menu_item(db_session, base_price=35000, available=True)
    db_session.commit()

    cart_items = [
        {
            "menu_item_id": item.id,
            "size_option_id": None,
            "modifier_ids": [],
            "quantity": 2,
            "unit_price": 35000,
        }
    ]
    result = validate_stop_list(cart_items, db_session)
    assert len(result) == 1


def test_validate_stop_list_menu_item_unavailable_raises(db_session) -> None:
    from core_api.services.validators import validate_stop_list
    from core_api.services.validators.exceptions import StopListError
    from tests._factories.menu import make_menu_item

    item = make_menu_item(db_session, base_price=35000, available=False)
    db_session.commit()

    cart_items = [
        {
            "menu_item_id": item.id,
            "size_option_id": None,
            "modifier_ids": [],
            "quantity": 1,
            "unit_price": 35000,
        }
    ]
    with pytest.raises(StopListError):
        validate_stop_list(cart_items, db_session)


def test_validate_stop_list_size_option_unavailable_raises(db_session) -> None:
    from shared.enums import SizeLabel

    from core_api.services.validators import validate_stop_list
    from core_api.services.validators.exceptions import StopListError
    from tests._factories.menu import make_menu_item, make_size_option

    item = make_menu_item(db_session, base_price=35000, available=True)
    size = make_size_option(db_session, item, label=SizeLabel.M, price=40000, available=False)
    db_session.commit()

    cart_items = [
        {
            "menu_item_id": item.id,
            "size_option_id": size.id,
            "modifier_ids": [],
            "quantity": 1,
            "unit_price": 40000,
        }
    ]
    with pytest.raises(StopListError):
        validate_stop_list(cart_items, db_session)


def test_validate_stop_list_modifier_unavailable_raises(db_session) -> None:
    from core_api.services.validators import validate_stop_list
    from core_api.services.validators.exceptions import StopListError
    from tests._factories.menu import make_menu_item, make_modifier

    item = make_menu_item(db_session, base_price=35000, available=True)
    mod = make_modifier(db_session, price=5000, available=False)
    db_session.commit()

    cart_items = [
        {
            "menu_item_id": item.id,
            "size_option_id": None,
            "modifier_ids": [mod.id],
            "quantity": 1,
            "unit_price": 40000,
        }
    ]
    with pytest.raises(StopListError):
        validate_stop_list(cart_items, db_session)


def test_validate_stop_list_returns_fresh_prices_not_client_prices(db_session) -> None:
    """INV-006: сервер — источник правды для цен.

    Клиент прислал stale unit_price=20000. В БД base_price=25000.
    Валидатор должен вернуть позицию с ценой 25000 (не 20000).
    """
    from core_api.services.validators import validate_stop_list
    from tests._factories.menu import make_menu_item

    item = make_menu_item(db_session, base_price=25000, available=True)
    db_session.commit()

    cart_items = [
        {
            "menu_item_id": item.id,
            "size_option_id": None,
            "modifier_ids": [],
            "quantity": 1,
            "unit_price": 20000,  # stale
        }
    ]
    result = validate_stop_list(cart_items, db_session)
    # GREEN-контракт: каждая валидированная позиция экспонирует актуальную цену.
    # Форма (attribute vs key) — прерогатива GREEN; здесь проверяем оба варианта.
    validated = result[0]
    price = validated["unit_price"] if isinstance(validated, dict) else validated.unit_price
    assert price == 25000


def test_validate_stop_list_error_carries_offending_item_id(db_session) -> None:
    from core_api.services.validators import validate_stop_list
    from core_api.services.validators.exceptions import StopListError
    from tests._factories.menu import make_menu_item

    item = make_menu_item(db_session, base_price=35000, available=False)
    db_session.commit()

    cart_items = [
        {
            "menu_item_id": item.id,
            "size_option_id": None,
            "modifier_ids": [],
            "quantity": 1,
            "unit_price": 35000,
        }
    ]
    with pytest.raises(StopListError) as exc_info:
        validate_stop_list(cart_items, db_session)
    # Ошибка несёт ID недоступной позиции — приёмный контракт:
    # либо `.item_id`, либо `.menu_item_id`.
    err = exc_info.value
    offending = getattr(err, "item_id", None) or getattr(err, "menu_item_id", None)
    assert offending == item.id
