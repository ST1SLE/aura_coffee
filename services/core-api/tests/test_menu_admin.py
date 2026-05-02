"""RED: menu-admin CRUD and stop-list contract."""

import inspect
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
    "set_item_inventory",
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
    """MenuAdminService должен экспонировать все обязательные методы."""
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
    _pg_db_override, admin_headers: dict
) -> None:
    from core_api.main import app
    from shared.models.menu import Category, MenuItem

    engine = _pg_db_override
    with Session(engine) as session:
        cat = Category(type="drink", name_ru="Напитки", name_en="Drinks")
        session.add(cat)
        session.flush()
        item = MenuItem(category_id=cat.id, name_ru="Латте", name_en="Latte", base_price=35000)
        session.add(item)
        session.commit()
        cat_id = cat.id
        item_id = item.id

    try:
        with TestClient(app) as client:
            resp = client.delete(f"/api/v1/admin/menu/categories/{cat_id}", headers=admin_headers)

        assert resp.status_code == 409
        with Session(engine) as session:
            assert session.get(Category, cat_id) is not None
    finally:
        with Session(engine) as session:
            item = session.get(MenuItem, item_id)
            if item is not None:
                session.delete(item)
                session.flush()
            cat = session.get(Category, cat_id)
            if cat is not None:
                session.delete(cat)
            session.commit()


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

    body = {
        "category_id": cat.id,
        "name_ru": "Латте",
        "name_en": "Latte",
        "base_price": 35000,
        "inventory_quantity": 12,
        "media_type": "video",
        "media_url": "/media/menu/latte/hero.mp4",
        "media_poster_url": "/media/menu/latte/poster.webp",
    }
    resp = db_client.post("/api/v1/admin/menu/items", json=body, headers=admin_headers)
    assert resp.status_code == 201, resp.text
    assert resp.json()["availability"] == "available"
    assert resp.json()["inventory_quantity"] == 12
    assert resp.json()["media_type"] == "video"
    assert resp.json()["media_url"] == "/media/menu/latte/hero.mp4"
    assert resp.json()["media_poster_url"] == "/media/menu/latte/poster.webp"


def test_admin_create_item_with_unknown_category_rejected(client: TestClient, admin_headers: dict) -> None:
    body = {"category_id": 999999, "name_ru": "Латте", "name_en": "Latte", "base_price": 35000}
    resp = client.post("/api/v1/admin/menu/items", json=body, headers=admin_headers)
    # 404 или 409 — зависит от реализации green; точный код зафиксировать после green
    assert resp.status_code in {404, 409}, resp.text


def test_admin_create_item_rejects_video_without_poster(client: TestClient, admin_headers: dict) -> None:
    body = {
        "category_id": 1,
        "name_ru": "Латте",
        "name_en": "Latte",
        "base_price": 35000,
        "media_type": "video",
        "media_url": "/media/menu/latte/hero.mp4",
    }
    resp = client.post("/api/v1/admin/menu/items", json=body, headers=admin_headers)
    assert resp.status_code == 422, resp.text


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
def test_admin_updates_item_media_fields(
    db_client: TestClient, migrated_db_session: Session, admin_headers: dict
) -> None:
    from shared.models.menu import Category, MenuItem

    cat = Category(type="drink", name_ru="Напитки", name_en="Drinks")
    migrated_db_session.add(cat)
    migrated_db_session.flush()
    item = MenuItem(category_id=cat.id, name_ru="Латте", name_en="Latte", base_price=35000)
    migrated_db_session.add(item)
    migrated_db_session.flush()

    resp = db_client.put(
        f"/api/v1/admin/menu/items/{item.id}",
        json={
            "media_type": "video",
            "media_url": "/media/menu/latte/hero.mp4",
            "media_poster_url": "/media/menu/latte/poster.webp",
            "inventory_quantity": 5,
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["media_type"] == "video"
    assert body["media_url"] == "/media/menu/latte/hero.mp4"
    assert body["media_poster_url"] == "/media/menu/latte/poster.webp"
    assert body["inventory_quantity"] == 5


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (TEST_DATABASE_URL)")
def test_barista_updates_item_inventory_without_touching_stop_list(
    db_client: TestClient, migrated_db_session: Session, barista_headers: dict
) -> None:
    from shared.models.menu import Category, MenuItem

    cat = Category(type="food", name_ru="Еда", name_en="Food")
    migrated_db_session.add(cat)
    migrated_db_session.flush()
    item = MenuItem(
        category_id=cat.id,
        name_ru="Круассан",
        name_en="Croissant",
        base_price=20000,
        inventory_quantity=3,
        available=True,
    )
    migrated_db_session.add(item)
    migrated_db_session.flush()

    resp = db_client.patch(
        f"/api/v1/admin/menu/items/{item.id}/inventory",
        json={"inventory_quantity": 0},
        headers=barista_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["inventory_quantity"] == 0
    assert body["available"] is True
    assert body["availability"] == "available"

    migrated_db_session.expire_all()
    refreshed = migrated_db_session.get(MenuItem, item.id)
    assert refreshed.inventory_quantity == 0
    assert refreshed.available is True


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (TEST_DATABASE_URL)")
def test_admin_sets_item_inventory_to_untracked(
    db_client: TestClient, migrated_db_session: Session, admin_headers: dict
) -> None:
    from shared.models.menu import Category, MenuItem

    cat = Category(type="food", name_ru="Еда", name_en="Food")
    migrated_db_session.add(cat)
    migrated_db_session.flush()
    item = MenuItem(
        category_id=cat.id,
        name_ru="Сэндвич",
        name_en="Sandwich",
        base_price=25000,
        inventory_quantity=2,
    )
    migrated_db_session.add(item)
    migrated_db_session.flush()

    resp = db_client.patch(
        f"/api/v1/admin/menu/items/{item.id}/inventory",
        json={"inventory_quantity": None},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["inventory_quantity"] is None


def test_customer_blocked_from_item_inventory(client: TestClient, customer_headers: dict) -> None:
    resp = client.patch(
        "/api/v1/admin/menu/items/1/inventory",
        json={"inventory_quantity": 1},
        headers=customer_headers,
    )
    assert resp.status_code == 403


def test_courier_blocked_from_item_inventory(client: TestClient, courier_headers: dict) -> None:
    resp = client.patch(
        "/api/v1/admin/menu/items/1/inventory",
        json={"inventory_quantity": 1},
        headers=courier_headers,
    )
    assert resp.status_code == 403


def test_item_inventory_patch_rejects_negative_and_extra_fields(
    client: TestClient, admin_headers: dict
) -> None:
    negative = client.patch(
        "/api/v1/admin/menu/items/1/inventory",
        json={"inventory_quantity": -1},
        headers=admin_headers,
    )
    assert negative.status_code == 422

    extra = client.patch(
        "/api/v1/admin/menu/items/1/inventory",
        json={"inventory_quantity": 1, "available": False},
        headers=admin_headers,
    )
    assert extra.status_code == 422


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (TEST_DATABASE_URL)")
def test_admin_update_item_rejects_signed_or_external_media_url(
    db_client: TestClient, migrated_db_session: Session, admin_headers: dict
) -> None:
    from shared.models.menu import Category, MenuItem

    cat = Category(type="drink", name_ru="Напитки", name_en="Drinks")
    migrated_db_session.add(cat)
    migrated_db_session.flush()
    item = MenuItem(category_id=cat.id, name_ru="Латте", name_en="Latte", base_price=35000)
    migrated_db_session.add(item)
    migrated_db_session.flush()

    resp = db_client.put(
        f"/api/v1/admin/menu/items/{item.id}",
        json={
            "media_type": "video",
            "media_url": "https://storage.example/latte.mp4?token=secret",
            "media_poster_url": "/media/menu/latte/poster.webp",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 422, resp.text


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


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (TEST_DATABASE_URL)")
def test_barista_lists_items_allowed(db_client: TestClient, barista_headers: dict) -> None:
    resp = db_client.get("/api/v1/admin/menu/items", headers=barista_headers)
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


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (TEST_DATABASE_URL)")
def test_item_availability_patch_404_on_missing_id(
    db_client: TestClient, admin_headers: dict
) -> None:
    resp = db_client.patch(
        "/api/v1/admin/menu/items/999999/availability",
        json={"available": False},
        headers=admin_headers,
    )
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
    ("PATCH",  "/api/v1/admin/menu/items/{item_id}/inventory"),
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


def test_rbac_matrix_operational_routes_allow_barista() -> None:
    """PATCH operational menu routes should allow barista and admin."""
    from core_api.rbac_matrix import ROUTE_MATRIX

    operational_entries = [
        ("PATCH", "/api/v1/admin/menu/items/{item_id}/availability"),
        ("PATCH", "/api/v1/admin/menu/items/{item_id}/inventory"),
        ("PATCH", "/api/v1/admin/menu/modifiers/{modifier_id}/availability"),
    ]
    for entry in operational_entries:
        roles = ROUTE_MATRIX.get(entry, set())
        assert "barista" in roles, f"{entry} должен допускать barista"
        assert "admin" in roles, f"{entry} должен допускать admin"

    non_operational_mutation = [
        (method, path) for (method, path), _roles in ROUTE_MATRIX.items()
        if path.startswith("/api/v1/admin/menu")
        and method != "GET"
        and not path.endswith("/availability")
        and not path.endswith("/inventory")
    ]
    for entry in non_operational_mutation:
        roles = ROUTE_MATRIX[entry]
        assert "barista" not in roles, f"{entry} не должен допускать barista"


def test_rbac_matrix_mutations_admin_only() -> None:
    """Each non-operational mutating admin menu route is admin-only."""
    from core_api.rbac_matrix import ROUTE_MATRIX

    for (method, path), roles in ROUTE_MATRIX.items():
        if not path.startswith("/api/v1/admin/menu"):
            continue
        if method == "GET" or path.endswith("/availability") or path.endswith("/inventory"):
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
    "/api/v1/admin/menu/items/{item_id}/inventory": {"patch"},
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


# ─────────────────────────────────────────────────────────────────
# Section 9 — category_id filter on GET /admin/menu/items
# ─────────────────────────────────────────────────────────────────


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (TEST_DATABASE_URL)")
def test_admin_items_list_filters_by_category(
    db_client: TestClient, admin_headers: dict, barista_headers: dict
) -> None:
    """GET /admin/menu/items?category_id=<id> должен фильтровать по категории."""
    # (a) создаём две категории через API
    cat_a_resp = db_client.post(
        "/api/v1/admin/menu/categories",
        json={"type": "drink", "name_ru": "Категория А", "name_en": "Category A", "sort_order": 0, "is_visible": True},
        headers=admin_headers,
    )
    assert cat_a_resp.status_code == 201, cat_a_resp.text
    cat_a_id = cat_a_resp.json()["id"]

    cat_b_resp = db_client.post(
        "/api/v1/admin/menu/categories",
        json={"type": "food", "name_ru": "Категория Б", "name_en": "Category B", "sort_order": 1, "is_visible": True},
        headers=admin_headers,
    )
    assert cat_b_resp.status_code == 201, cat_b_resp.text
    cat_b_id = cat_b_resp.json()["id"]

    # (b) создаём по два товара в каждой категории
    def _create_item(category_id: int, name_ru: str, name_en: str) -> int:
        resp = db_client.post(
            "/api/v1/admin/menu/items",
            json={"category_id": category_id, "name_ru": name_ru, "name_en": name_en, "base_price": 25000},
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        return resp.json()["id"]

    item_a1 = _create_item(cat_a_id, "Латте А1", "Latte A1")
    item_a2 = _create_item(cat_a_id, "Капучино А2", "Cappuccino A2")
    item_b1 = _create_item(cat_b_id, "Сэндвич Б1", "Sandwich B1")
    item_b2 = _create_item(cat_b_id, "Круассан Б2", "Croissant B2")

    a_ids = {item_a1, item_a2}
    b_ids = {item_b1, item_b2}
    all_ids = a_ids | b_ids

    # (c) без фильтра — возвращаются все четыре товара
    resp_all = db_client.get("/api/v1/admin/menu/items", headers=admin_headers)
    assert resp_all.status_code == 200, resp_all.text
    returned_ids = {item["id"] for item in resp_all.json()}
    assert all_ids.issubset(returned_ids), f"Ожидались все 4 товара, получили ids={returned_ids}"

    # (d) фильтр по категории А — только товары А, без товаров Б
    resp_a = db_client.get(f"/api/v1/admin/menu/items?category_id={cat_a_id}", headers=admin_headers)
    assert resp_a.status_code == 200, resp_a.text
    filtered_ids = {item["id"] for item in resp_a.json()}
    assert filtered_ids == a_ids, f"Ожидались только {a_ids}, получили {filtered_ids}"
    assert not filtered_ids & b_ids, "Товары категории Б не должны попадать в ответ"

    # (e) несуществующая категория → 404
    resp_404 = db_client.get("/api/v1/admin/menu/items?category_id=999999", headers=admin_headers)
    assert resp_404.status_code == 404, resp_404.text
    assert resp_404.json()["detail"] == "category not found"

    # (f) category_id=0 → 422
    resp_zero = db_client.get("/api/v1/admin/menu/items?category_id=0", headers=admin_headers)
    assert resp_zero.status_code == 422, resp_zero.text

    # (g) category_id=abc → 422
    resp_str = db_client.get("/api/v1/admin/menu/items?category_id=abc", headers=admin_headers)
    assert resp_str.status_code == 422, resp_str.text

    # (h) бариста тоже может фильтровать по категории
    resp_barista = db_client.get(f"/api/v1/admin/menu/items?category_id={cat_a_id}", headers=barista_headers)
    assert resp_barista.status_code == 200, resp_barista.text
    assert {item["id"] for item in resp_barista.json()} == a_ids


# ─────────────────────────────────────────────────────────────────
# Section 10 — PUT /admin/menu/items/{item_id}/modifiers (set-replacement)
# ─────────────────────────────────────────────────────────────────


@pytest.mark.skipif(_IS_SQLITE, reason="Требует PostgreSQL (TEST_DATABASE_URL)")
def test_admin_set_item_modifiers(
    db_client: TestClient, admin_headers: dict, barista_headers: dict
) -> None:
    """PUT /admin/menu/items/{id}/modifiers должен заменять набор модификаторов."""
    # (a) сидим одну категорию и один товар через admin API
    cat_resp = db_client.post(
        "/api/v1/admin/menu/categories",
        json={
            "type": "drink",
            "name_ru": "Напитки ModSet",
            "name_en": "Drinks ModSet",
            "sort_order": 0,
            "is_visible": True,
        },
        headers=admin_headers,
    )
    assert cat_resp.status_code == 201, cat_resp.text
    cat_id = cat_resp.json()["id"]

    item_resp = db_client.post(
        "/api/v1/admin/menu/items",
        json={
            "category_id": cat_id,
            "name_ru": "Латте ModSet",
            "name_en": "Latte ModSet",
            "base_price": 25000,
        },
        headers=admin_headers,
    )
    assert item_resp.status_code == 201, item_resp.text
    item_id = item_resp.json()["id"]

    # (b) сидим три модификатора
    def _create_mod(name_ru: str, name_en: str, price: int) -> int:
        resp = db_client.post(
            "/api/v1/admin/menu/modifiers",
            json={"name_ru": name_ru, "name_en": name_en, "price": price, "sort_order": 0},
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text
        return resp.json()["id"]

    mod_a = _create_mod("Сироп А", "Syrup A", 3000)
    mod_b = _create_mod("Сироп Б", "Syrup B", 3500)
    mod_c = _create_mod("Сироп В", "Syrup C", 4000)

    url = f"/api/v1/admin/menu/items/{item_id}/modifiers"

    # (c) прикрепляем три модификатора → 200, полный набор
    resp_c = db_client.put(url, json={"modifier_ids": [mod_a, mod_b, mod_c]}, headers=admin_headers)
    assert resp_c.status_code == 200, resp_c.text
    body_c = resp_c.json()
    assert {m["id"] for m in body_c["modifiers"]} == {mod_a, mod_b, mod_c}

    # (d) заменяем на один mod_b → replacement, не union
    resp_d = db_client.put(url, json={"modifier_ids": [mod_b]}, headers=admin_headers)
    assert resp_d.status_code == 200, resp_d.text
    body_d = resp_d.json()
    assert len(body_d["modifiers"]) == 1
    assert body_d["modifiers"][0]["id"] == mod_b

    # (e) пустой список → отцепить все
    resp_e = db_client.put(url, json={"modifier_ids": []}, headers=admin_headers)
    assert resp_e.status_code == 200, resp_e.text
    assert resp_e.json()["modifiers"] == []

    # Перед (f) восстановим набор [mod_a], чтобы проверить, что 422 не меняет состояние
    resp_prep = db_client.put(url, json={"modifier_ids": [mod_a]}, headers=admin_headers)
    assert resp_prep.status_code == 200, resp_prep.text
    before_f = db_client.get(f"/api/v1/admin/menu/items/{item_id}", headers=admin_headers)
    assert before_f.status_code == 200, before_f.text
    before_mods = {m["id"] for m in before_f.json()["modifiers"]}
    assert before_mods == {mod_a}

    # (f) неизвестный id → 422, detail упоминает 999999, состояние не меняется
    resp_f = db_client.put(url, json={"modifier_ids": [mod_a, 999999]}, headers=admin_headers)
    assert resp_f.status_code == 422, resp_f.text
    assert "999999" in str(resp_f.json().get("detail", "")), resp_f.text
    after_f = db_client.get(f"/api/v1/admin/menu/items/{item_id}", headers=admin_headers)
    assert after_f.status_code == 200, after_f.text
    assert {m["id"] for m in after_f.json()["modifiers"]} == before_mods

    # (g) неизвестный item_id → 404
    resp_g = db_client.put(
        "/api/v1/admin/menu/items/999999/modifiers",
        json={"modifier_ids": [mod_a]},
        headers=admin_headers,
    )
    assert resp_g.status_code == 404, resp_g.text

    # (h) дубликаты → дедуп, 200
    resp_h = db_client.put(
        url,
        json={"modifier_ids": [mod_a, mod_a, mod_b]},
        headers=admin_headers,
    )
    assert resp_h.status_code == 200, resp_h.text
    assert {m["id"] for m in resp_h.json()["modifiers"]} == {mod_a, mod_b}

    # (i) бариста → 403 вне зависимости от тела
    resp_i_empty = db_client.put(url, json={"modifier_ids": []}, headers=barista_headers)
    assert resp_i_empty.status_code == 403, resp_i_empty.text
    resp_i_full = db_client.put(url, json={"modifier_ids": [mod_a]}, headers=barista_headers)
    assert resp_i_full.status_code == 403, resp_i_full.text

    # (j) без Authorization → 401
    resp_j = db_client.put(url, json={"modifier_ids": [mod_a]})
    assert resp_j.status_code == 401, resp_j.text
