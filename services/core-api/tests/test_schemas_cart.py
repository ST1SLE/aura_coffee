"""RED: тесты Pydantic-схем корзины в core_api.schemas.cart.

Все тесты ДОЛЖНЫ падать с ImportError до создания schemas/cart.py.
Группа 3.x: тесты line_id и compute_line_id (добавлены в рамках cart-redis-pricing-red).
"""

import ast
import importlib.util
import pathlib
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# 6.1 CartItemCreate поля (без price-like)
# ---------------------------------------------------------------------------

def test_cart_item_create_exists_with_required_fields() -> None:
    from core_api.schemas.cart import CartItemCreate

    fields = set(CartItemCreate.model_fields.keys())
    assert fields == {"menu_item_id", "size_option_id", "modifier_ids", "quantity"}

    price_like = {f for f in fields if any(p in f for p in ("price", "total", "cost", "amount"))}
    assert not price_like, f"CartItemCreate не должен содержать price-поля: {price_like}"


# ---------------------------------------------------------------------------
# 6.2 quantity bounds
# ---------------------------------------------------------------------------

def test_cart_item_create_quantity_bounds() -> None:
    from core_api.schemas.cart import CartItemCreate

    with pytest.raises(ValidationError):
        CartItemCreate(menu_item_id=1, quantity=0)

    with pytest.raises(ValidationError):
        CartItemCreate(menu_item_id=1, quantity=100)

    # Граничные значения — должны быть допустимы
    CartItemCreate(menu_item_id=1, quantity=1)
    CartItemCreate(menu_item_id=1, quantity=99)


# ---------------------------------------------------------------------------
# 6.3 CartItemResponse содержит серверные поля
# ---------------------------------------------------------------------------

def test_cart_item_response_has_server_computed_fields() -> None:
    from core_api.schemas.cart import CartItemResponse

    fields = set(CartItemResponse.model_fields.keys())
    for required in ("unit_price", "line_total", "menu_item_snapshot", "size_snapshot", "modifiers_snapshot"):
        assert required in fields, f"Поле {required!r} отсутствует в CartItemResponse"


# ---------------------------------------------------------------------------
# 6.4 line_total == unit_price * quantity
# ---------------------------------------------------------------------------

def _make_snapshot():
    from types import SimpleNamespace
    return SimpleNamespace(
        name_ru="Латте",
        name_en="Latte",
        availability="available",
    )


def _make_cart_item_response(unit_price: int, quantity: int, line_total: int):
    from core_api.schemas.cart import CartItemResponse

    return CartItemResponse(
        line_id=CartItemResponse.compute_line_id(1, None, []),
        menu_item_id=1,
        size_option_id=None,
        modifier_ids=[],
        quantity=quantity,
        unit_price=unit_price,
        line_total=line_total,
        menu_item_snapshot={"name_ru": "Латте", "name_en": "Latte", "availability": "available"},
        size_snapshot=None,
        modifiers_snapshot=[],
    )


def test_cart_item_response_line_total_invariant() -> None:
    # Корректный: 15000 * 3 = 45000
    item = _make_cart_item_response(unit_price=15000, quantity=3, line_total=45000)
    assert item.line_total == 45000

    # Некорректный: 15000 * 3 ≠ 40000
    with pytest.raises(ValidationError):
        _make_cart_item_response(unit_price=15000, quantity=3, line_total=40000)


# ---------------------------------------------------------------------------
# 6.5 CartResponse subtotal == sum(line_totals)
# ---------------------------------------------------------------------------

def _make_cart_response(subtotal: int):
    from core_api.schemas.cart import CartResponse

    from core_api.schemas.cart import CartItemResponse as _CIR
    items_data = [
        {
            "line_id": _CIR.compute_line_id(1, None, []),
            "menu_item_id": 1,
            "size_option_id": None,
            "modifier_ids": [],
            "quantity": 1,
            "unit_price": 10000,
            "line_total": 10000,
            "menu_item_snapshot": {"name_ru": "A", "name_en": "A", "availability": "available"},
            "size_snapshot": None,
            "modifiers_snapshot": [],
        },
        {
            "line_id": _CIR.compute_line_id(2, None, []),
            "menu_item_id": 2,
            "size_option_id": None,
            "modifier_ids": [],
            "quantity": 1,
            "unit_price": 25000,
            "line_total": 25000,
            "menu_item_snapshot": {"name_ru": "B", "name_en": "B", "availability": "available"},
            "size_snapshot": None,
            "modifiers_snapshot": [],
        },
        {
            "line_id": _CIR.compute_line_id(3, None, []),
            "menu_item_id": 3,
            "size_option_id": None,
            "modifier_ids": [],
            "quantity": 1,
            "unit_price": 5000,
            "line_total": 5000,
            "menu_item_snapshot": {"name_ru": "C", "name_en": "C", "availability": "available"},
            "size_snapshot": None,
            "modifiers_snapshot": [],
        },
    ]
    return CartResponse(
        items=items_data,
        subtotal=subtotal,
        currency="RUB",
        expires_at=datetime.now(tz=timezone.utc),
    )


def test_cart_response_subtotal_invariant() -> None:
    # Корректный: 10000 + 25000 + 5000 = 40000
    cart = _make_cart_response(subtotal=40000)
    assert cart.subtotal == 40000

    # Некорректный
    with pytest.raises(ValidationError):
        _make_cart_response(subtotal=39000)


# ---------------------------------------------------------------------------
# 6.6 currency locked to RUB
# ---------------------------------------------------------------------------

def test_cart_response_currency_locked_to_rub() -> None:
    from core_api.schemas.cart import CartResponse

    CartResponse(items=[], subtotal=0, currency="RUB", expires_at=datetime.now(tz=timezone.utc))

    with pytest.raises(ValidationError):
        CartResponse(items=[], subtotal=0, currency="USD", expires_at=datetime.now(tz=timezone.utc))


# ---------------------------------------------------------------------------
# 6.7 Нет импортов sqlalchemy / redis / ORM
# ---------------------------------------------------------------------------

def test_cart_schemas_do_not_import_orm_or_redis() -> None:
    cart_path = pathlib.Path(__file__).parents[2] / "src" / "core_api" / "schemas" / "cart.py"
    if not cart_path.exists():
        pytest.skip("schemas/cart.py ещё не создан — тест будет актуален после GREEN")

    source = cart_path.read_text()
    tree = ast.parse(source)

    forbidden = {"sqlalchemy", "redis", "core_api.models", "core_api.database"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = ""
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name
                    for bad in forbidden:
                        assert not module.startswith(bad), (
                            f"schemas/cart.py не должен импортировать {bad!r}, найдено: {module!r}"
                        )
            elif isinstance(node, ast.ImportFrom) and node.module:
                module = node.module
                for bad in forbidden:
                    assert not module.startswith(bad), (
                        f"schemas/cart.py не должен импортировать {bad!r}, найдено: {module!r}"
                    )


# ===========================================================================
# Группа 3.x — line_id в CartItemResponse (cart-redis-pricing-red)
# ===========================================================================

# ---------------------------------------------------------------------------
# 3.1 line_id присутствует в CartItemResponse.model_fields
# ---------------------------------------------------------------------------

def test_cart_item_response_has_line_id() -> None:
    from core_api.schemas.cart import CartItemResponse

    assert "line_id" in CartItemResponse.model_fields, (
        "CartItemResponse должен содержать поле line_id: str"
    )
    field = CartItemResponse.model_fields["line_id"]
    # Проверяем аннотацию типа
    import typing
    annotation = field.annotation
    assert annotation is str or annotation == str, (
        f"line_id должен быть str, получено: {annotation}"
    )


# ---------------------------------------------------------------------------
# 3.2 compute_line_id детерминирован и возвращает 16-символьный hex
# ---------------------------------------------------------------------------

def test_cart_item_response_compute_line_id_is_deterministic() -> None:
    from core_api.schemas.cart import CartItemResponse

    result1 = CartItemResponse.compute_line_id(1, 3, [5, 7])
    result2 = CartItemResponse.compute_line_id(1, 3, [5, 7])

    assert result1 == result2
    assert len(result1) == 16
    assert result1 == result1.lower()
    # Проверяем что это hex
    int(result1, 16)  # поднимет ValueError если не hex


# ---------------------------------------------------------------------------
# 3.3 Порядок модификаторов не влияет на line_id
# ---------------------------------------------------------------------------

def test_cart_item_response_compute_line_id_modifier_order_independent() -> None:
    from core_api.schemas.cart import CartItemResponse

    assert (
        CartItemResponse.compute_line_id(1, 3, [5, 7])
        == CartItemResponse.compute_line_id(1, 3, [7, 5])
    )


# ---------------------------------------------------------------------------
# 3.4 line_id чувствителен к size_option_id
# ---------------------------------------------------------------------------

def test_cart_item_response_compute_line_id_size_sensitive() -> None:
    from core_api.schemas.cart import CartItemResponse

    assert (
        CartItemResponse.compute_line_id(1, 3, [5])
        != CartItemResponse.compute_line_id(1, 4, [5])
    )


# ---------------------------------------------------------------------------
# 3.5 line_id чувствителен к набору модификаторов
# ---------------------------------------------------------------------------

def test_cart_item_response_compute_line_id_modifier_sensitive() -> None:
    from core_api.schemas.cart import CartItemResponse

    assert (
        CartItemResponse.compute_line_id(1, 3, [5])
        != CartItemResponse.compute_line_id(1, 3, [5, 7])
    )


# ---------------------------------------------------------------------------
# 3.6 size_option_id=None стабильно
# ---------------------------------------------------------------------------

def test_cart_item_response_compute_line_id_size_option_none_stable() -> None:
    from core_api.schemas.cart import CartItemResponse

    result1 = CartItemResponse.compute_line_id(1, None, [])
    result2 = CartItemResponse.compute_line_id(1, None, [])

    assert result1 == result2
    assert len(result1) == 16
    int(result1, 16)  # hex guard


# ---------------------------------------------------------------------------
# 3.7 CartItemCreate не имеет поля line_id
# ---------------------------------------------------------------------------

def test_cart_item_create_has_no_line_id_field() -> None:
    from core_api.schemas.cart import CartItemCreate

    assert "line_id" not in CartItemCreate.model_fields


# ---------------------------------------------------------------------------
# 3.8 Полный round-trip CartItemResponse с line_id
# ---------------------------------------------------------------------------

def test_full_cart_item_response_round_trip_with_line_id() -> None:
    from core_api.schemas.cart import CartItemResponse

    expected_line_id = CartItemResponse.compute_line_id(1, None, [])

    item = CartItemResponse(
        line_id=expected_line_id,
        menu_item_id=1,
        size_option_id=None,
        modifier_ids=[],
        quantity=3,
        unit_price=15000,
        line_total=45000,
        menu_item_snapshot={"name_ru": "Латте", "name_en": "Latte", "availability": "available"},
        size_snapshot=None,
        modifiers_snapshot=[],
    )

    assert item.line_id == expected_line_id
    assert item.line_total == 45000
