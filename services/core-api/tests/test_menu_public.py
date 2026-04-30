"""Тесты публичного API меню — GET /api/v1/menu."""

import inspect

from fastapi.testclient import TestClient
from sqlalchemy import text

from core_api.main import app

# ---------------------------------------------------------------------------
# Вспомогательные утилиты
# ---------------------------------------------------------------------------

def _all_item_ids_in_response(data: dict) -> list[int]:
    """Все id позиций из ответа (вложенно по всем категориям)."""
    ids = []
    for cat in data.get("categories", []):
        for item in cat.get("items", []):
            ids.append(item["id"])
    return ids


def _find_item(data: dict, item_id: int) -> dict | None:
    """Поиск позиции по id во всех категориях ответа."""
    for cat in data.get("categories", []):
        for item in cat.get("items", []):
            if item["id"] == item_id:
                return item
    return None


# ---------------------------------------------------------------------------
# Группа 2: контракт сервисного слоя
# ---------------------------------------------------------------------------

def test_get_public_menu_service_is_importable() -> None:
    """2.1 RED: get_public_menu должна быть вызываемой — падает с ImportError."""
    from core_api.services.menu_public import get_public_menu  # noqa: F401

    assert callable(get_public_menu)


def test_get_public_menu_signature_uses_keyword_only_flags() -> None:
    """2.2 RED: параметры функции — db, *, only_available, language."""
    from core_api.services.menu_public import get_public_menu

    sig = inspect.signature(get_public_menu)
    params = sig.parameters
    assert "db" in params, "Нет параметра db"
    assert params["db"].kind in (
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.POSITIONAL_ONLY,
    )
    assert "only_available" in params, "Нет параметра only_available"
    assert params["only_available"].kind == inspect.Parameter.KEYWORD_ONLY
    assert params["only_available"].annotation is bool

    assert "language" in params, "Нет параметра language"
    assert params["language"].kind == inspect.Parameter.KEYWORD_ONLY


def test_language_enum_exists() -> None:
    """2.3 RED: Language — Enum с членами RU и EN."""
    import enum

    from core_api.services.menu_public import Language  # noqa: F401

    assert issubclass(Language, enum.Enum)
    assert hasattr(Language, "RU")
    assert hasattr(Language, "EN")


# ---------------------------------------------------------------------------
# Группа 3: Pydantic-схемы Public*
# ---------------------------------------------------------------------------

def test_public_menu_schemas_importable() -> None:
    """3.1 RED: Public-схемы должны быть импортируемы из core_api.schemas.menu."""
    from core_api.schemas.menu import (  # noqa: F401
        PublicCategory,
        PublicMenuModifier,
        PublicMenuItem,
        PublicMenuResponse,
        PublicMenuSizeOption,
    )


def test_public_menu_item_has_no_archived_field() -> None:
    """3.2 RED: PublicMenuItem НЕ экспонирует archived и availability."""
    from core_api.schemas.menu import PublicMenuItem

    assert "archived" not in PublicMenuItem.model_fields
    assert "availability" not in PublicMenuItem.model_fields


def test_public_menu_item_exposes_flat_and_raw_bilingual_fields() -> None:
    """3.3 RED: PublicMenuItem содержит все ожидаемые поля."""
    from core_api.schemas.menu import PublicMenuItem

    expected = {
        "id", "category_id",
        "name", "name_ru", "name_en",
        "description", "description_ru", "description_en",
        "base_price", "image_url",
        "available", "sort_order",
        "size_options", "modifiers",
    }
    for field in expected:
        assert field in PublicMenuItem.model_fields, f"Нет поля {field!r} в PublicMenuItem"


def test_public_category_exposes_flat_and_raw_bilingual_fields() -> None:
    """3.4 RED: PublicCategory содержит все ожидаемые поля."""
    from core_api.schemas.menu import PublicCategory

    expected = {"id", "type", "name", "name_ru", "name_en", "sort_order", "items"}
    for field in expected:
        assert field in PublicCategory.model_fields, f"Нет поля {field!r} в PublicCategory"


def test_admin_menu_item_response_still_has_archived() -> None:
    """3.5 GUARD (PASS в RED): MenuItemResponse.model_fields содержит archived."""
    from core_api.schemas.menu import MenuItemResponse

    assert "archived" in MenuItemResponse.model_fields, (
        "MenuItemResponse потерял поле archived — не трогать admin-схему!"
    )


def test_public_menu_modifier_has_bilingual_and_name() -> None:
    """3.6 RED: PublicMenuModifier содержит id, name, name_ru, name_en, price, available."""
    from core_api.schemas.menu import PublicMenuModifier

    expected = {"id", "name", "name_ru", "name_en", "price", "available"}
    for field in expected:
        assert field in PublicMenuModifier.model_fields, f"Нет поля {field!r} в PublicMenuModifier"


def test_public_menu_size_option_has_expected_fields() -> None:
    """3.7 RED: PublicMenuSizeOption содержит id, label, price, available (без билингв)."""
    from core_api.schemas.menu import PublicMenuSizeOption

    expected = {"id", "label", "price", "available"}
    for field in expected:
        assert field in PublicMenuSizeOption.model_fields, (
            f"Нет поля {field!r} в PublicMenuSizeOption"
        )
    for bilingual in ("name", "name_ru", "name_en"):
        assert bilingual not in PublicMenuSizeOption.model_fields, (
            f"SizeOption не должен содержать двуязычное поле {bilingual!r}"
        )


# ---------------------------------------------------------------------------
# Группа 4: HTTP happy path
# ---------------------------------------------------------------------------

def test_get_menu_returns_200_for_anonymous_client(_pg_db_override) -> None:
    """4.1 RED: анонимный запрос должен вернуть 200 с полем categories."""
    with TestClient(app) as c:
        resp = c.get("/api/v1/menu")
    assert resp.status_code == 200, f"Ожидался 200, получен {resp.status_code}"
    body = resp.json()
    assert "categories" in body
    assert isinstance(body["categories"], list)


def test_get_menu_empty_database_returns_empty_list(_pg_db_override) -> None:
    """4.2 RED: при пустой БД возвращается {\"categories\": []}."""
    with _pg_db_override.begin() as conn:
        conn.execute(text("DELETE FROM menu_item_modifiers"))
        conn.execute(text("DELETE FROM size_options"))
        conn.execute(text("DELETE FROM menu_items"))
        conn.execute(text("DELETE FROM modifiers"))
        conn.execute(text("DELETE FROM categories"))

    with TestClient(app) as c:
        resp = c.get("/api/v1/menu")
    assert resp.status_code == 200
    assert resp.json() == {"categories": []}


def test_get_menu_groups_and_orders_categories_and_items(client, seed_public_menu) -> None:
    """4.3 RED: категории и позиции отсортированы; невидимые / modifier скрыты."""
    resp = client.get("/api/v1/menu")
    assert resp.status_code == 200
    data = resp.json()

    cat_ids = [c["id"] for c in data["categories"]]

    # Только видимые не-modifier категории присутствуют
    assert seed_public_menu.cat_drink_id in cat_ids
    assert seed_public_menu.cat_food_id in cat_ids
    assert seed_public_menu.cat_invis_id not in cat_ids
    assert seed_public_menu.cat_mod_type_id not in cat_ids

    # Категории отсортированы по sort_order (drink=10 < food=20)
    drink_pos = cat_ids.index(seed_public_menu.cat_drink_id)
    food_pos = cat_ids.index(seed_public_menu.cat_food_id)
    assert drink_pos < food_pos

    # Позиции внутри категории отсортированы по sort_order
    drink_cat = next(c for c in data["categories"] if c["id"] == seed_public_menu.cat_drink_id)
    item_order = [i["id"] for i in drink_cat["items"] if not i["id"] == seed_public_menu.item_d3_id]
    assert item_order.index(seed_public_menu.item_d1_id) < item_order.index(seed_public_menu.item_d2_id)


# ---------------------------------------------------------------------------
# Группа 5: правила видимости
# ---------------------------------------------------------------------------

def test_archived_items_are_never_returned(client, seed_public_menu) -> None:
    """5.1 RED: архивированные позиции не возвращаются ни при каком параметре."""
    resp = client.get("/api/v1/menu")
    assert resp.status_code == 200
    all_ids = _all_item_ids_in_response(resp.json())
    assert seed_public_menu.item_d3_id not in all_ids, "item_d3 (archived) не должен быть в ответе"
    assert seed_public_menu.item_f3_id not in all_ids, "item_f3 (archived) не должен быть в ответе"


def test_invisible_category_is_excluded_with_its_items(client, seed_public_menu) -> None:
    """5.2 RED: невидимая категория и её позиции не возвращаются."""
    resp = client.get("/api/v1/menu")
    assert resp.status_code == 200
    data = resp.json()
    cat_ids = [c["id"] for c in data["categories"]]
    assert seed_public_menu.cat_invis_id not in cat_ids
    all_ids = _all_item_ids_in_response(data)
    assert seed_public_menu.item_invis_id not in all_ids


def test_modifier_type_category_is_excluded(client, seed_public_menu) -> None:
    """5.3 RED: категория type=modifier не возвращается."""
    resp = client.get("/api/v1/menu")
    assert resp.status_code == 200
    data = resp.json()
    cat_ids = [c["id"] for c in data["categories"]]
    assert seed_public_menu.cat_mod_type_id not in cat_ids
    for cat in data["categories"]:
        assert cat.get("type") != "modifier", "Категория modifier-type не должна попадать в ответ"


# ---------------------------------------------------------------------------
# Группа 6: параметр available
# ---------------------------------------------------------------------------

def test_default_request_includes_stop_listed_items(client, seed_public_menu) -> None:
    """6.1 RED: без параметра available стоп-листовые позиции возвращаются."""
    resp = client.get("/api/v1/menu")
    assert resp.status_code == 200
    item = _find_item(resp.json(), seed_public_menu.item_d2_id)
    assert item is not None, "item_d2 (stop-listed) должен присутствовать при запросе без фильтра"
    assert item["available"] is False


def test_available_true_hides_stop_listed_items(client, seed_public_menu) -> None:
    """6.2 RED: available=true скрывает стоп-листовые позиции."""
    resp = client.get("/api/v1/menu", params={"available": "true"})
    assert resp.status_code == 200
    all_ids = _all_item_ids_in_response(resp.json())
    assert seed_public_menu.item_d2_id not in all_ids, "item_d2 (stop-listed) должен быть скрыт"
    assert seed_public_menu.item_d1_id in all_ids, "item_d1 (available) должен присутствовать"


def test_available_true_prunes_stop_listed_size_options(client, seed_public_menu) -> None:
    """6.3 RED: available=true убирает стоп-листовые размеры из позиций."""
    resp = client.get("/api/v1/menu", params={"available": "true"})
    assert resp.status_code == 200
    item = _find_item(resp.json(), seed_public_menu.item_d1_id)
    assert item is not None, "item_d1 должен присутствовать"
    size_ids = [s["id"] for s in item["size_options"]]
    assert seed_public_menu.size_d1_S_id not in size_ids, "size_d1_S (unavailable) должен быть скрыт"
    assert seed_public_menu.size_d1_L_id in size_ids, "size_d1_L (available) должен остаться"


def test_available_false_is_treated_as_default(client, seed_public_menu) -> None:
    """6.4 RED: available=false == без фильтра — стоп-лист виден."""
    resp = client.get("/api/v1/menu", params={"available": "false"})
    assert resp.status_code == 200
    item = _find_item(resp.json(), seed_public_menu.item_d2_id)
    assert item is not None, "item_d2 (stop-listed) должен присутствовать при available=false"


def test_archived_filter_is_independent_of_available_param(client, seed_public_menu) -> None:
    """6.5 RED: архивированные позиции скрыты и без, и с available=true."""
    for params in [{}, {"available": "true"}]:
        resp = client.get("/api/v1/menu", params=params)
        assert resp.status_code == 200
        all_ids = _all_item_ids_in_response(resp.json())
        assert seed_public_menu.item_d3_id not in all_ids, (
            f"item_d3 (archived) не должен быть в ответе при params={params}"
        )


# ---------------------------------------------------------------------------
# Группа 7: Accept-Language
# ---------------------------------------------------------------------------

def test_default_language_is_russian(client, seed_public_menu) -> None:
    """7.1 RED: без Accept-Language name == name_ru для всех категорий и позиций."""
    resp = client.get("/api/v1/menu")
    assert resp.status_code == 200
    for cat in resp.json()["categories"]:
        assert cat["name"] == cat["name_ru"], f"Категория {cat['id']}: name должен == name_ru"
        for item in cat["items"]:
            assert item["name"] == item["name_ru"], f"Позиция {item['id']}: name должен == name_ru"
            if item["description"] is not None or item["description_ru"] is not None:
                assert item["description"] == item["description_ru"]


def test_accept_language_en_selects_english(client, seed_public_menu) -> None:
    """7.2 RED: Accept-Language: en → name == name_en; raw-поля присутствуют."""
    resp = client.get("/api/v1/menu", headers={"Accept-Language": "en"})
    assert resp.status_code == 200
    for cat in resp.json()["categories"]:
        assert cat["name"] == cat["name_en"]
        assert "name_ru" in cat and "name_en" in cat
        for item in cat["items"]:
            assert item["name"] == item["name_en"]
            assert "name_ru" in item and "name_en" in item
            if item["description"] is not None or item["description_en"] is not None:
                assert item["description"] == item["description_en"]


def test_accept_language_en_us_is_treated_as_english(client, seed_public_menu) -> None:
    """7.3 RED: Accept-Language: en-US,en;q=0.9 трактуется как EN."""
    resp = client.get("/api/v1/menu", headers={"Accept-Language": "en-US,en;q=0.9"})
    assert resp.status_code == 200
    for cat in resp.json()["categories"]:
        assert cat["name"] == cat["name_en"]


def test_unknown_accept_language_falls_back_to_russian(client, seed_public_menu) -> None:
    """7.4 RED: Accept-Language: fr-FR → fallback на RU."""
    resp = client.get("/api/v1/menu", headers={"Accept-Language": "fr-FR"})
    assert resp.status_code == 200
    for cat in resp.json()["categories"]:
        assert cat["name"] == cat["name_ru"]


def test_null_description_projects_as_null(client, seed_public_menu) -> None:
    """7.5 RED: позиция с description_ru=NULL и description_en=NULL → description=null."""
    # item_d2: description_ru=None, description_en=None
    resp = client.get("/api/v1/menu")
    assert resp.status_code == 200
    item = _find_item(resp.json(), seed_public_menu.item_d2_id)
    assert item is not None
    assert item["description"] is None
    assert item["description_ru"] is None
    assert item["description_en"] is None


def test_modifier_name_is_projected_bilingually(client, seed_public_menu) -> None:
    """7.6 RED: Accept-Language: en → modifier.name == modifier.name_en; raw-поля есть."""
    resp = client.get("/api/v1/menu", headers={"Accept-Language": "en"})
    assert resp.status_code == 200
    found_modifier = False
    for cat in resp.json()["categories"]:
        for item in cat["items"]:
            for mod in item.get("modifiers", []):
                found_modifier = True
                assert mod["name"] == mod["name_en"], f"Модификатор {mod['id']}: name должен == name_en"
                assert "name_ru" in mod
                assert "name_en" in mod
    assert found_modifier, "Ни один модификатор не найден в ответе"


# ---------------------------------------------------------------------------
# Группа 8: размеры и модификаторы
# ---------------------------------------------------------------------------

def test_size_options_are_ordered_S_M_L(client, seed_public_menu) -> None:
    """8.1 RED: размеры возвращаются в enum-порядке S→M→L (вставлены L, S)."""
    resp = client.get("/api/v1/menu")
    assert resp.status_code == 200
    item = _find_item(resp.json(), seed_public_menu.item_d1_id)
    assert item is not None
    sizes = item["size_options"]
    assert len(sizes) >= 2
    labels = [s["label"] for s in sizes]
    # Вставлены L, S → ожидаем S, L (enum-порядок)
    size_d1_S = next(s for s in sizes if s["id"] == seed_public_menu.size_d1_S_id)
    size_d1_L = next(s for s in sizes if s["id"] == seed_public_menu.size_d1_L_id)
    assert labels.index("S") < labels.index("L"), (
        f"Размеры должны идти S < L, получили {labels}"
    )
    assert size_d1_S["label"] == "S"
    assert size_d1_L["label"] == "L"


def test_modifiers_ordered_by_sort_order_then_id(client, seed_public_menu) -> None:
    """8.2 RED: модификаторы отсортированы по sort_order, затем id."""
    resp = client.get("/api/v1/menu")
    assert resp.status_code == 200
    item = _find_item(resp.json(), seed_public_menu.item_d1_id)
    assert item is not None
    mods = item["modifiers"]
    assert len(mods) >= 2
    mod_ids = [m["id"] for m in mods]
    # mod1 sort_order=10, mod2 sort_order=20 → mod1 первым
    assert mod_ids.index(seed_public_menu.mod1_id) < mod_ids.index(seed_public_menu.mod2_id)


def test_stop_listed_modifiers_still_visible_under_available_true(
    client, seed_public_menu
) -> None:
    """8.3 RED: модификаторы с available=False остаются видимыми при available=true."""
    resp = client.get("/api/v1/menu", params={"available": "true"})
    assert resp.status_code == 200
    item = _find_item(resp.json(), seed_public_menu.item_d1_id)
    assert item is not None, "item_d1 должен быть в ответе"
    mod_ids = [m["id"] for m in item.get("modifiers", [])]
    assert seed_public_menu.mod2_id in mod_ids, (
        "mod2 (available=False) должен остаться в модификаторах даже при available=true"
    )


# ---------------------------------------------------------------------------
# Группа 9: аутентификация, форма запроса, делегирование сервису
# ---------------------------------------------------------------------------

def test_anonymous_request_has_no_rbac_entry() -> None:
    """9.1 GUARD (PASS в RED): маршрут отсутствует в ROUTE_MATRIX."""
    from core_api.rbac_matrix import ROUTE_MATRIX

    assert ("GET", "/api/v1/menu") not in ROUTE_MATRIX, (
        "GET /api/v1/menu не должен быть в ROUTE_MATRIX — это публичный маршрут"
    )


def test_public_menu_query_is_bounded(client, seed_public_menu) -> None:
    """9.2 RED: не более 4 SQL-запросов на GET /api/v1/menu."""
    from sqlalchemy import event as sa_event

    query_count = 0

    def _count(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001, ANN202
        nonlocal query_count
        query_count += 1

    sa_event.listen(seed_public_menu.engine, "before_cursor_execute", _count)
    try:
        resp = client.get("/api/v1/menu")
        assert resp.status_code == 200, f"Ожидался 200, получен {resp.status_code}"
        assert query_count >= 1, "Ожидается минимум 1 SQL-запрос"
        assert query_count <= 4, f"Слишком много SQL-запросов: {query_count}, ожидалось ≤ 4"
    finally:
        sa_event.remove(seed_public_menu.engine, "before_cursor_execute", _count)


def test_router_delegates_to_service(client) -> None:
    """9.3 RED: роутер вызывает get_public_menu ровно один раз."""
    from unittest.mock import patch

    from core_api.schemas.menu import PublicMenuResponse  # ImportError в RED

    fake_response = PublicMenuResponse(categories=[])

    with patch(
        "core_api.services.menu_public.get_public_menu",
        return_value=fake_response,
    ) as mock_fn:
        resp = client.get("/api/v1/menu")
        assert resp.status_code == 200
        mock_fn.assert_called_once()
