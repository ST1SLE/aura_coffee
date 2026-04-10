"""RED: menu-admin CRUD and stop-list contract."""

import inspect
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from tests.conftest import _TEST_DB_URL

_IS_SQLITE = _TEST_DB_URL.startswith("sqlite")

# ─────────────────────────────────────────────────────────────────
# Section 2 — AvailabilityPatch schema
# ─────────────────────────────────────────────────────────────────


def test_availability_patch_schema_exists() -> None:
    """AvailabilityPatch должна существовать в core_api.schemas.menu."""
    from core_api.schemas.menu import AvailabilityPatch  # ImportError → red

    assert issubclass(AvailabilityPatch, BaseModel)
    fields = AvailabilityPatch.model_fields
    assert set(fields.keys()) == {"available"}, f"Ожидался только available, получили {set(fields.keys())}"
    assert fields["available"].annotation is bool


def test_availability_patch_rejects_extra_fields() -> None:
    """AvailabilityPatch должна отклонять лишние поля."""
    from core_api.schemas.menu import AvailabilityPatch  # ImportError → red

    with pytest.raises(ValidationError):
        AvailabilityPatch(available=False, price=0)  # type: ignore[call-arg]


# ─────────────────────────────────────────────────────────────────
# Section 3 — MenuAdminService shape
# ─────────────────────────────────────────────────────────────────

_REQUIRED_METHODS = [
    "create_category",
    "update_category",
    "delete_category",
    "list_categories",
    "create_item",
    "update_item",
    "delete_item",
    "list_items",
    "get_item",
    "set_item_availability",
    "create_modifier",
    "update_modifier",
    "delete_modifier",
    "list_modifiers",
    "set_modifier_availability",
    "create_size",
    "update_size",
    "delete_size",
]


def test_menu_admin_service_importable() -> None:
    """MenuAdminService должен существовать и принимать db в __init__."""
    from core_api.services.menu_admin import MenuAdminService  # ModuleNotFoundError → red

    sig = inspect.signature(MenuAdminService.__init__)
    assert "db" in sig.parameters, "MenuAdminService.__init__ должен принимать db"


def test_menu_admin_service_has_required_methods() -> None:
    """MenuAdminService должен экспонировать все 18 методов."""
    from core_api.services.menu_admin import MenuAdminService  # ModuleNotFoundError → red

    missing = [m for m in _REQUIRED_METHODS if not callable(getattr(MenuAdminService, m, None))]
    assert not missing, f"Отсутствующие методы: {missing}"


def test_menu_admin_router_has_no_direct_db_calls() -> None:
    """Роутер не должен содержать прямых обращений к сессии БД."""
    router_path = (
        Path(__file__).parents[1]
        / "src" / "core_api" / "routers" / "menu_admin.py"
    )
    text = router_path.read_text()
    forbidden = ["db.add(", "db.delete(", "db.commit(", "db.flush("]
    found = [pat for pat in forbidden if pat in text]
    assert not found, f"Роутер содержит прямые вызовы к сессии: {found}"


# ─────────────────────────────────────────────────────────────────
# Section 4 — Categories CRUD
# ─────────────────────────────────────────────────────────────────

_CAT_BODY = {"type": "drink", "name_ru": "Напитки", "name_en": "Drinks", "sort_order": 0, "is_visible": True}


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (TEST_DATABASE_URL)")
def test_admin_creates_category(
    db_client: TestClient, migrated_db_session: Session, admin_headers: dict
) -> None:
    resp = db_client.post("/api/v1/admin/menu/categories", json=_CAT_BODY, headers=admin_headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name_ru"] == "Напитки"
    assert data["type"] == "drink"
    assert "id" in data


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (TEST_DATABASE_URL)")
def test_admin_updates_category(
    db_client: TestClient, migrated_db_session: Session, admin_headers: dict
) -> None:
    from shared.models.menu import Category

    cat = Category(type="drink", name_ru="Напитки", name_en="Drinks")
    migrated_db_session.add(cat)
    migrated_db_session.flush()

    resp = db_client.put(
        f"/api/v1/admin/menu/categories/{cat.id}",
        json={"name_en": "Beverages"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name_en"] == "Beverages"


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (TEST_DATABASE_URL)")
def test_admin_lists_categories_returns_seeded_rows(
    db_client: TestClient, migrated_db_session: Session, admin_headers: dict
) -> None:
    from shared.models.menu import Category

    cat1 = Category(type="drink", name_ru="Напитки", name_en="Drinks")
    cat2 = Category(type="food", name_ru="Еда", name_en="Food")
    migrated_db_session.add_all([cat1, cat2])
    migrated_db_session.flush()

    resp = db_client.get("/api/v1/admin/menu/categories", headers=admin_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (TEST_DATABASE_URL)")
def test_barista_lists_categories_allowed(
    db_client: TestClient, migrated_db_session: Session, barista_headers: dict
) -> None:
    from shared.models.menu import Category

    migrated_db_session.add(Category(type="drink", name_ru="Напитки", name_en="Drinks"))
    migrated_db_session.flush()

    resp = db_client.get("/api/v1/admin/menu/categories", headers=barista_headers)
    assert resp.status_code == 200


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (TEST_DATABASE_URL)")
def test_admin_deletes_empty_category(
    db_client: TestClient, migrated_db_session: Session, admin_headers: dict
) -> None:
    from shared.models.menu import Category

    cat = Category(type="merch", name_ru="Мерч", name_en="Merch")
    migrated_db_session.add(cat)
    migrated_db_session.flush()
    cat_id = cat.id

    resp = db_client.delete(f"/api/v1/admin/menu/categories/{cat_id}", headers=admin_headers)
    assert resp.status_code == 204
    migrated_db_session.expire_all()
    assert migrated_db_session.get(Category, cat_id) is None


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (TEST_DATABASE_URL)")
def test_admin_delete_referenced_category_returns_409(
    db_client: TestClient, migrated_db_session: Session, admin_headers: dict
) -> None:
    from shared.models.menu import Category, MenuItem

    cat = Category(type="drink", name_ru="Напитки", name_en="Drinks")
    migrated_db_session.add(cat)
    migrated_db_session.flush()
    item = MenuItem(category_id=cat.id, name_ru="Латте", name_en="Latte", base_price=35000)
    migrated_db_session.add(item)
    migrated_db_session.flush()

    resp = db_client.delete(f"/api/v1/admin/menu/categories/{cat.id}", headers=admin_headers)
    assert resp.status_code == 409
    migrated_db_session.expire_all()
    assert migrated_db_session.get(Category, cat.id) is not None


def test_barista_cannot_create_category(client: TestClient, barista_headers: dict) -> None:
    resp = client.post("/api/v1/admin/menu/categories", json=_CAT_BODY, headers=barista_headers)
    assert resp.status_code == 403


def test_barista_cannot_delete_category(client: TestClient, barista_headers: dict) -> None:
    resp = client.delete("/api/v1/admin/menu/categories/999", headers=barista_headers)
    assert resp.status_code == 403


def test_customer_blocked_from_categories_crud(client: TestClient, customer_headers: dict) -> None:
    assert client.get("/api/v1/admin/menu/categories", headers=customer_headers).status_code == 403
    assert client.post("/api/v1/admin/menu/categories", json=_CAT_BODY, headers=customer_headers).status_code == 403
    assert client.delete("/api/v1/admin/menu/categories/1", headers=customer_headers).status_code == 403


# ─────────────────────────────────────────────────────────────────
# Section 5 — Menu items CRUD
# ─────────────────────────────────────────────────────────────────


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (TEST_DATABASE_URL)")
def test_admin_creates_menu_item(
    db_client: TestClient, migrated_db_session: Session, admin_headers: dict
) -> None:
    from shared.models.menu import Category

    cat = Category(type="drink", name_ru="Напитки", name_en="Drinks")
    migrated_db_session.add(cat)
    migrated_db_session.flush()

    body = {"category_id": cat.id, "name_ru": "Латте", "name_en": "Latte", "base_price": 35000}
    resp = db_client.post("/api/v1/admin/menu/items", json=body, headers=admin_headers)
    assert resp.status_code == 201, resp.text
    assert resp.json()["availability"] == "available"


def test_admin_create_item_with_unknown_category_rejected(client: TestClient, admin_headers: dict) -> None:
    body = {"category_id": 999999, "name_ru": "Латте", "name_en": "Latte", "base_price": 35000}
    resp = client.post("/api/v1/admin/menu/items", json=body, headers=admin_headers)
    # 404 или 409 — зависит от реализации green; точный код зафиксировать после green
    assert resp.status_code in {404, 409}, resp.text


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (TEST_DATABASE_URL)")
def test_admin_updates_item_archives_it(
    db_client: TestClient, migrated_db_session: Session, admin_headers: dict
) -> None:
    from shared.models.menu import Category, MenuItem

    cat = Category(type="drink", name_ru="Напитки", name_en="Drinks")
    migrated_db_session.add(cat)
    migrated_db_session.flush()
    item = MenuItem(category_id=cat.id, name_ru="Латте", name_en="Latte", base_price=35000)
    migrated_db_session.add(item)
    migrated_db_session.flush()

    resp = db_client.put(f"/api/v1/admin/menu/items/{item.id}", json={"archived": True}, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["availability"] == "archived"


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (TEST_DATABASE_URL)")
def test_admin_lists_items(
    db_client: TestClient, migrated_db_session: Session, admin_headers: dict
) -> None:
    from shared.models.menu import Category, MenuItem

    cat = Category(type="drink", name_ru="Напитки", name_en="Drinks")
    migrated_db_session.add(cat)
    migrated_db_session.flush()
    items = [
        MenuItem(category_id=cat.id, name_ru=f"Напиток {i}", name_en=f"Drink {i}", base_price=10000)
        for i in range(3)
    ]
    migrated_db_session.add_all(items)
    migrated_db_session.flush()

    resp = db_client.get("/api/v1/admin/menu/items", headers=admin_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 3


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (TEST_DATABASE_URL)")
def test_admin_gets_single_item_with_sizes_and_modifiers(
    db_client: TestClient, migrated_db_session: Session, admin_headers: dict
) -> None:
    from shared.models.menu import Category, MenuItem, Modifier, SizeOption

    cat = Category(type="drink", name_ru="Напитки", name_en="Drinks")
    migrated_db_session.add(cat)
    migrated_db_session.flush()

    item = MenuItem(category_id=cat.id, name_ru="Латте", name_en="Latte", base_price=35000)
    migrated_db_session.add(item)
    migrated_db_session.flush()

    s1 = SizeOption(menu_item_id=item.id, label="S", price=30000)
    s2 = SizeOption(menu_item_id=item.id, label="L", price=40000)
    mod = Modifier(name_ru="Сироп", name_en="Syrup", price=5000)
    migrated_db_session.add_all([s1, s2, mod])
    migrated_db_session.flush()
    item.modifiers.append(mod)
    migrated_db_session.flush()

    resp = db_client.get(f"/api/v1/admin/menu/items/{item.id}", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["size_options"]) == 2
    assert len(data["modifiers"]) == 1


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (TEST_DATABASE_URL)")
def test_admin_deletes_item(
    db_client: TestClient, migrated_db_session: Session, admin_headers: dict
) -> None:
    from shared.models.menu import Category, MenuItem

    cat = Category(type="drink", name_ru="Напитки", name_en="Drinks")
    migrated_db_session.add(cat)
    migrated_db_session.flush()
    item = MenuItem(category_id=cat.id, name_ru="Латте", name_en="Latte", base_price=35000)
    migrated_db_session.add(item)
    migrated_db_session.flush()

    resp = db_client.delete(f"/api/v1/admin/menu/items/{item.id}", headers=admin_headers)
    assert resp.status_code == 204


def test_barista_lists_items_allowed(client: TestClient, barista_headers: dict) -> None:
    resp = client.get("/api/v1/admin/menu/items", headers=barista_headers)
    assert resp.status_code == 200


def test_barista_cannot_delete_item(client: TestClient, barista_headers: dict) -> None:
    resp = client.delete("/api/v1/admin/menu/items/999", headers=barista_headers)
    assert resp.status_code == 403


def test_customer_blocked_from_items_crud(client: TestClient, customer_headers: dict) -> None:
    assert client.get("/api/v1/admin/menu/items", headers=customer_headers).status_code == 403
    assert client.delete("/api/v1/admin/menu/items/1", headers=customer_headers).status_code == 403


# ─────────────────────────────────────────────────────────────────
# Section 6 — Modifiers CRUD
# ─────────────────────────────────────────────────────────────────

_MOD_BODY = {"name_ru": "Сироп ваниль", "name_en": "Vanilla syrup", "price": 5000, "sort_order": 0}


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (TEST_DATABASE_URL)")
def test_admin_creates_modifier(
    db_client: TestClient, migrated_db_session: Session, admin_headers: dict
) -> None:
    resp = db_client.post("/api/v1/admin/menu/modifiers", json=_MOD_BODY, headers=admin_headers)
    assert resp.status_code == 201, resp.text


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (TEST_DATABASE_URL)")
def test_admin_updates_modifier_price(
    db_client: TestClient, migrated_db_session: Session, admin_headers: dict
) -> None:
    from shared.models.menu import Modifier

    mod = Modifier(name_ru="Сироп", name_en="Syrup", price=3000)
    migrated_db_session.add(mod)
    migrated_db_session.flush()

    resp = db_client.put(f"/api/v1/admin/menu/modifiers/{mod.id}", json={"price": 5000}, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["price"] == 5000


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (TEST_DATABASE_URL)")
def test_admin_deletes_modifier(
    db_client: TestClient, migrated_db_session: Session, admin_headers: dict
) -> None:
    from shared.models.menu import Modifier

    mod = Modifier(name_ru="Сироп", name_en="Syrup", price=3000)
    migrated_db_session.add(mod)
    migrated_db_session.flush()

    resp = db_client.delete(f"/api/v1/admin/menu/modifiers/{mod.id}", headers=admin_headers)
    assert resp.status_code == 204


def test_delete_missing_modifier_returns_404(client: TestClient, admin_headers: dict) -> None:
    resp = client.delete("/api/v1/admin/menu/modifiers/999999", headers=admin_headers)
    assert resp.status_code == 404


def test_barista_lists_modifiers_allowed(client: TestClient, barista_headers: dict) -> None:
    resp = client.get("/api/v1/admin/menu/modifiers", headers=barista_headers)
    assert resp.status_code == 200


def test_barista_cannot_update_modifier(client: TestClient, barista_headers: dict) -> None:
    resp = client.put("/api/v1/admin/menu/modifiers/999", json={"price": 1000}, headers=barista_headers)
    assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────
# Section 7 — Size options CRUD
# ─────────────────────────────────────────────────────────────────


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (TEST_DATABASE_URL)")
def test_admin_creates_size_for_item(
    db_client: TestClient, migrated_db_session: Session, admin_headers: dict
) -> None:
    from shared.models.menu import Category, MenuItem

    cat = Category(type="drink", name_ru="Напитки", name_en="Drinks")
    migrated_db_session.add(cat)
    migrated_db_session.flush()
    item = MenuItem(category_id=cat.id, name_ru="Латте", name_en="Latte", base_price=35000)
    migrated_db_session.add(item)
    migrated_db_session.flush()

    body = {"menu_item_id": item.id, "label": "M", "price": 35000}
    resp = db_client.post("/api/v1/admin/menu/sizes", json=body, headers=admin_headers)
    assert resp.status_code == 201, resp.text
    assert resp.json()["menu_item_id"] == item.id


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (TEST_DATABASE_URL)")
def test_duplicate_size_label_on_same_item_returns_409(
    db_client: TestClient, migrated_db_session: Session, admin_headers: dict
) -> None:
    from shared.models.menu import Category, MenuItem

    cat = Category(type="drink", name_ru="Напитки", name_en="Drinks")
    migrated_db_session.add(cat)
    migrated_db_session.flush()
    item = MenuItem(category_id=cat.id, name_ru="Латте", name_en="Latte", base_price=35000)
    migrated_db_session.add(item)
    migrated_db_session.flush()

    body = {"menu_item_id": item.id, "label": "M", "price": 35000}
    resp1 = db_client.post("/api/v1/admin/menu/sizes", json=body, headers=admin_headers)
    assert resp1.status_code == 201
    resp2 = db_client.post("/api/v1/admin/menu/sizes", json=body, headers=admin_headers)
    assert resp2.status_code == 409


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (TEST_DATABASE_URL)")
def test_admin_updates_size_price(
    db_client: TestClient, migrated_db_session: Session, admin_headers: dict
) -> None:
    from shared.models.menu import Category, MenuItem, SizeOption

    cat = Category(type="drink", name_ru="Напитки", name_en="Drinks")
    migrated_db_session.add(cat)
    migrated_db_session.flush()
    item = MenuItem(category_id=cat.id, name_ru="Латте", name_en="Latte", base_price=35000)
    migrated_db_session.add(item)
    migrated_db_session.flush()
    size = SizeOption(menu_item_id=item.id, label="M", price=30000)
    migrated_db_session.add(size)
    migrated_db_session.flush()

    resp = db_client.put(f"/api/v1/admin/menu/sizes/{size.id}", json={"price": 40000}, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["price"] == 40000


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (TEST_DATABASE_URL)")
def test_admin_deletes_size(
    db_client: TestClient, migrated_db_session: Session, admin_headers: dict
) -> None:
    from shared.models.menu import Category, MenuItem, SizeOption

    cat = Category(type="drink", name_ru="Напитки", name_en="Drinks")
    migrated_db_session.add(cat)
    migrated_db_session.flush()
    item = MenuItem(category_id=cat.id, name_ru="Латте", name_en="Latte", base_price=35000)
    migrated_db_session.add(item)
    migrated_db_session.flush()
    size = SizeOption(menu_item_id=item.id, label="S", price=25000)
    migrated_db_session.add(size)
    migrated_db_session.flush()

    resp = db_client.delete(f"/api/v1/admin/menu/sizes/{size.id}", headers=admin_headers)
    assert resp.status_code == 204


def test_barista_cannot_create_size(client: TestClient, barista_headers: dict) -> None:
    body = {"menu_item_id": 1, "label": "M", "price": 35000}
    resp = client.post("/api/v1/admin/menu/sizes", json=body, headers=barista_headers)
    assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────
# Section 8 — Item stop-list toggle
# ─────────────────────────────────────────────────────────────────


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (TEST_DATABASE_URL)")
def test_barista_stop_lists_item(
    db_client: TestClient, migrated_db_session: Session, barista_headers: dict
) -> None:
    from shared.models.menu import Category, MenuItem

    cat = Category(type="drink", name_ru="Напитки", name_en="Drinks")
    migrated_db_session.add(cat)
    migrated_db_session.flush()
    item = MenuItem(category_id=cat.id, name_ru="Латте", name_en="Latte", base_price=35000, available=True)
    migrated_db_session.add(item)
    migrated_db_session.flush()

    resp = db_client.patch(
        f"/api/v1/admin/menu/items/{item.id}/availability",
        json={"available": False},
        headers=barista_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["availability"] == "stop_list"


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (TEST_DATABASE_URL)")
def test_barista_unstops_item(
    db_client: TestClient, migrated_db_session: Session, barista_headers: dict
) -> None:
    from shared.models.menu import Category, MenuItem

    cat = Category(type="drink", name_ru="Напитки", name_en="Drinks")
    migrated_db_session.add(cat)
    migrated_db_session.flush()
    item = MenuItem(category_id=cat.id, name_ru="Капучино", name_en="Cappuccino", base_price=32000, available=False)
    migrated_db_session.add(item)
    migrated_db_session.flush()

    resp = db_client.patch(
        f"/api/v1/admin/menu/items/{item.id}/availability",
        json={"available": True},
        headers=barista_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["availability"] == "available"


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (TEST_DATABASE_URL)")
def test_archived_item_availability_unchanged_by_toggle(
    db_client: TestClient, migrated_db_session: Session, barista_headers: dict
) -> None:
    from shared.models.menu import Category, MenuItem

    cat = Category(type="drink", name_ru="Напитки", name_en="Drinks")
    migrated_db_session.add(cat)
    migrated_db_session.flush()
    item = MenuItem(
        category_id=cat.id, name_ru="Старый продукт", name_en="Old product",
        base_price=10000, available=False, archived=True,
    )
    migrated_db_session.add(item)
    migrated_db_session.flush()

    resp = db_client.patch(
        f"/api/v1/admin/menu/items/{item.id}/availability",
        json={"available": True},
        headers=barista_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["availability"] == "archived"
    migrated_db_session.expire_all()
    assert migrated_db_session.get(MenuItem, item.id).archived is True


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (TEST_DATABASE_URL)")
def test_admin_stop_lists_item(
    db_client: TestClient, migrated_db_session: Session, admin_headers: dict
) -> None:
    from shared.models.menu import Category, MenuItem

    cat = Category(type="drink", name_ru="Напитки", name_en="Drinks")
    migrated_db_session.add(cat)
    migrated_db_session.flush()
    item = MenuItem(category_id=cat.id, name_ru="Эспрессо", name_en="Espresso", base_price=25000, available=True)
    migrated_db_session.add(item)
    migrated_db_session.flush()

    resp = db_client.patch(
        f"/api/v1/admin/menu/items/{item.id}/availability",
        json={"available": False},
        headers=admin_headers,
    )
    assert resp.status_code == 200


def test_customer_blocked_from_item_availability(client: TestClient, customer_headers: dict) -> None:
    resp = client.patch("/api/v1/admin/menu/items/1/availability", json={"available": False}, headers=customer_headers)
    assert resp.status_code == 403


def test_courier_blocked_from_item_availability(client: TestClient, courier_headers: dict) -> None:
    resp = client.patch("/api/v1/admin/menu/items/1/availability", json={"available": False}, headers=courier_headers)
    assert resp.status_code == 403


def test_item_availability_patch_404_on_missing_id(client: TestClient, admin_headers: dict) -> None:
    resp = client.patch("/api/v1/admin/menu/items/999999/availability", json={"available": False}, headers=admin_headers)
    assert resp.status_code == 404


def test_item_availability_patch_rejects_extra_fields(client: TestClient, admin_headers: dict) -> None:
    resp = client.patch(
        "/api/v1/admin/menu/items/1/availability",
        json={"available": False, "price": 0},
        headers=admin_headers,
    )
    assert resp.status_code == 422


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (TEST_DATABASE_URL)")
def test_item_availability_patch_only_touches_available_column(
    db_client: TestClient, migrated_db_session: Session, barista_headers: dict
) -> None:
    from shared.models.menu import Category, MenuItem

    cat = Category(type="drink", name_ru="Напитки", name_en="Drinks")
    migrated_db_session.add(cat)
    migrated_db_session.flush()
    item = MenuItem(category_id=cat.id, name_ru="Флэт", name_en="Flat White", base_price=38000, available=True)
    migrated_db_session.add(item)
    migrated_db_session.flush()

    db_client.patch(
        f"/api/v1/admin/menu/items/{item.id}/availability",
        json={"available": False},
        headers=barista_headers,
    )
    migrated_db_session.expire_all()
    refreshed = migrated_db_session.get(MenuItem, item.id)
    assert refreshed.base_price == 38000


# ─────────────────────────────────────────────────────────────────
# Section 9 — Modifier stop-list toggle
# ─────────────────────────────────────────────────────────────────


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (TEST_DATABASE_URL)")
def test_barista_stop_lists_modifier(
    db_client: TestClient, migrated_db_session: Session, barista_headers: dict
) -> None:
    from shared.models.menu import Modifier

    mod = Modifier(name_ru="Сироп", name_en="Syrup", price=5000, available=True)
    migrated_db_session.add(mod)
    migrated_db_session.flush()

    resp = db_client.patch(
        f"/api/v1/admin/menu/modifiers/{mod.id}/availability",
        json={"available": False},
        headers=barista_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["available"] is False


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (TEST_DATABASE_URL)")
def test_admin_stop_lists_modifier(
    db_client: TestClient, migrated_db_session: Session, admin_headers: dict
) -> None:
    from shared.models.menu import Modifier

    mod = Modifier(name_ru="Молоко овсяное", name_en="Oat milk", price=7000, available=True)
    migrated_db_session.add(mod)
    migrated_db_session.flush()

    resp = db_client.patch(
        f"/api/v1/admin/menu/modifiers/{mod.id}/availability",
        json={"available": False},
        headers=admin_headers,
    )
    assert resp.status_code == 200


def test_customer_blocked_from_modifier_availability(client: TestClient, customer_headers: dict) -> None:
    resp = client.patch("/api/v1/admin/menu/modifiers/1/availability", json={"available": False}, headers=customer_headers)
    assert resp.status_code == 403


def test_courier_blocked_from_modifier_availability(client: TestClient, courier_headers: dict) -> None:
    resp = client.patch("/api/v1/admin/menu/modifiers/1/availability", json={"available": False}, headers=courier_headers)
    assert resp.status_code == 403


def test_modifier_availability_patch_404_on_missing_id(client: TestClient, admin_headers: dict) -> None:
    resp = client.patch("/api/v1/admin/menu/modifiers/999999/availability", json={"available": False}, headers=admin_headers)
    assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────
# Section 10 — RBAC matrix coverage
# ─────────────────────────────────────────────────────────────────

# Полный список (метод, путь) из design.md §D1
_EXPECTED_MATRIX_ENTRIES: list[tuple[str, str]] = [
    ("POST",   "/api/v1/admin/menu/categories"),
    ("GET",    "/api/v1/admin/menu/categories"),
    ("PUT",    "/api/v1/admin/menu/categories/{category_id}"),
    ("DELETE", "/api/v1/admin/menu/categories/{category_id}"),
    ("POST",   "/api/v1/admin/menu/items"),
    ("GET",    "/api/v1/admin/menu/items"),
    ("GET",    "/api/v1/admin/menu/items/{item_id}"),
    ("PUT",    "/api/v1/admin/menu/items/{item_id}"),
    ("DELETE", "/api/v1/admin/menu/items/{item_id}"),
    ("PATCH",  "/api/v1/admin/menu/items/{item_id}/availability"),
    ("POST",   "/api/v1/admin/menu/modifiers"),
    ("GET",    "/api/v1/admin/menu/modifiers"),
    ("PUT",    "/api/v1/admin/menu/modifiers/{modifier_id}"),
    ("DELETE", "/api/v1/admin/menu/modifiers/{modifier_id}"),
    ("PATCH",  "/api/v1/admin/menu/modifiers/{modifier_id}/availability"),
    ("POST",   "/api/v1/admin/menu/sizes"),
    ("PUT",    "/api/v1/admin/menu/sizes/{size_id}"),
    ("DELETE", "/api/v1/admin/menu/sizes/{size_id}"),
]


def test_rbac_matrix_contains_admin_menu_routes() -> None:
    """ROUTE_MATRIX должна содержать все маршруты admin menu из §D1."""
    from core_api.rbac_matrix import ROUTE_MATRIX

    missing = [entry for entry in _EXPECTED_MATRIX_ENTRIES if entry not in ROUTE_MATRIX]
    assert not missing, f"Отсутствующие записи в ROUTE_MATRIX: {missing}"


def test_rbac_matrix_availability_routes_allow_barista() -> None:
    """Только PATCH .../availability должны иметь barista в ролях."""
    from core_api.rbac_matrix import ROUTE_MATRIX

    availability_entries = [
        ("PATCH", "/api/v1/admin/menu/items/{item_id}/availability"),
        ("PATCH", "/api/v1/admin/menu/modifiers/{modifier_id}/availability"),
    ]
    for entry in availability_entries:
        roles = ROUTE_MATRIX.get(entry, set())
        assert "barista" in roles, f"{entry} должен допускать barista"
        assert "admin" in roles, f"{entry} должен допускать admin"

    non_availability_mutation = [
        (method, path) for (method, path), _roles in ROUTE_MATRIX.items()
        if path.startswith("/api/v1/admin/menu")
        and method != "GET"
        and not path.endswith("/availability")
    ]
    for entry in non_availability_mutation:
        roles = ROUTE_MATRIX[entry]
        assert "barista" not in roles, f"{entry} не должен допускать barista"


def test_rbac_matrix_mutations_admin_only() -> None:
    """Каждый мутирующий (не-GET, не /availability) маршрут admin menu → только admin."""
    from core_api.rbac_matrix import ROUTE_MATRIX

    for (method, path), roles in ROUTE_MATRIX.items():
        if not path.startswith("/api/v1/admin/menu"):
            continue
        if method == "GET" or path.endswith("/availability"):
            continue
        assert roles == {"admin"}, f"{method} {path} → ожидался {{'admin'}}, получили {roles}"


def test_admin_menu_routes_not_public() -> None:
    """Ни один маршрут admin menu не должен быть в PUBLIC_ROUTES."""
    from core_api.rbac_matrix import PUBLIC_ROUTES

    leaks = [(m, p) for (m, p) in PUBLIC_ROUTES if "/admin/menu" in p]
    assert not leaks, f"Публичные маршруты admin menu: {leaks}"


def test_unauthenticated_admin_menu_request_401(client: TestClient) -> None:
    resp = client.get("/api/v1/admin/menu/categories")
    assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────────
# Section 11 — OpenAPI surface
# ─────────────────────────────────────────────────────────────────

_EXPECTED_PATHS = {
    "/api/v1/admin/menu/categories": {"post", "get"},
    "/api/v1/admin/menu/categories/{category_id}": {"put", "delete"},
    "/api/v1/admin/menu/items": {"post", "get"},
    "/api/v1/admin/menu/items/{item_id}": {"get", "put", "delete"},
    "/api/v1/admin/menu/items/{item_id}/availability": {"patch"},
    "/api/v1/admin/menu/modifiers": {"post", "get"},
    "/api/v1/admin/menu/modifiers/{modifier_id}": {"put", "delete"},
    "/api/v1/admin/menu/modifiers/{modifier_id}/availability": {"patch"},
    "/api/v1/admin/menu/sizes": {"post"},
    "/api/v1/admin/menu/sizes/{size_id}": {"put", "delete"},
}


def test_openapi_exposes_menu_admin_paths(client: TestClient) -> None:
    """OpenAPI должен содержать все маршруты admin menu из §D1."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json().get("paths", {})
    missing: list[str] = []
    for path, methods in _EXPECTED_PATHS.items():
        if path not in paths:
            missing.append(f"path {path!r} отсутствует")
            continue
        for method in methods:
            if method not in paths[path]:
                missing.append(f"{method.upper()} {path!r} отсутствует")
    assert not missing, "\n".join(missing)


def test_openapi_menu_admin_tag_is_consistent(client: TestClient) -> None:
    """Каждая операция admin menu должна иметь тег menu-admin."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json().get("paths", {})
    wrong: list[str] = []
    for path, path_item in paths.items():
        if not path.startswith("/api/v1/admin/menu"):
            continue
        for method, operation in path_item.items():
            tags = operation.get("tags", [])
            if "menu-admin" not in tags:
                wrong.append(f"{method.upper()} {path}")
    assert not wrong, f"Операции без тега menu-admin: {wrong}"
