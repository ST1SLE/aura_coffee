"""RED: тесты Pydantic-схем меню в core_api.schemas.menu.

Все тесты ДОЛЖНЫ падать с ImportError до создания schemas/menu.py.
"""

import pytest
from pydantic import BaseModel, ValidationError


# ---------------------------------------------------------------------------
# 5.1 Category schemas exist
# ---------------------------------------------------------------------------

def test_category_schemas_exist() -> None:
    from core_api.schemas.menu import (
        CategoryBase,
        CategoryCreate,
        CategoryUpdate,
        CategoryResponse,
    )

    for cls in (CategoryBase, CategoryCreate, CategoryUpdate, CategoryResponse):
        assert issubclass(cls, BaseModel), f"{cls.__name__} должен быть BaseModel"


# ---------------------------------------------------------------------------
# 5.2 CategoryCreate rejects unknown type
# ---------------------------------------------------------------------------

def test_category_create_rejects_unknown_type() -> None:
    from core_api.schemas.menu import CategoryCreate

    with pytest.raises(ValidationError):
        CategoryCreate(type="BEVERAGE", name_ru="Напиток", name_en="Drink")


# ---------------------------------------------------------------------------
# 5.3 MenuItem schemas exist
# ---------------------------------------------------------------------------

def test_menu_item_schemas_exist() -> None:
    from core_api.schemas.menu import (
        MenuItemBase,
        MenuItemCreate,
        MenuItemUpdate,
        MenuItemResponse,
    )

    for cls in (MenuItemBase, MenuItemCreate, MenuItemUpdate, MenuItemResponse):
        assert issubclass(cls, BaseModel), f"{cls.__name__} должен быть BaseModel"


# ---------------------------------------------------------------------------
# 5.4 MenuItemCreate rejects negative price
# ---------------------------------------------------------------------------

def test_menu_item_create_rejects_negative_price() -> None:
    from core_api.schemas.menu import MenuItemCreate

    with pytest.raises(ValidationError):
        MenuItemCreate(
            category_id=1,
            name_ru="Латте",
            name_en="Latte",
            base_price=-1,
        )


def test_menu_item_create_accepts_video_media_contract() -> None:
    from core_api.schemas.menu import MenuItemCreate
    from shared.enums import MenuMediaType

    item = MenuItemCreate(
        category_id=1,
        name_ru="Латте",
        name_en="Latte",
        base_price=35000,
        media_type="video",
        media_url="/media/menu/latte/hero.mp4",
        media_poster_url="/media/menu/latte/poster.webp",
    )

    assert item.media_type == MenuMediaType.VIDEO
    assert item.media_url == "/media/menu/latte/hero.mp4"
    assert item.media_poster_url == "/media/menu/latte/poster.webp"


def test_menu_item_create_rejects_malformed_media_contracts() -> None:
    from core_api.schemas.menu import MenuItemCreate

    base = {
        "category_id": 1,
        "name_ru": "Латте",
        "name_en": "Latte",
        "base_price": 35000,
    }

    with pytest.raises(ValidationError):
        MenuItemCreate(
            **base,
            media_type="video",
            media_url="/media/menu/latte/hero.mp4",
        )

    with pytest.raises(ValidationError):
        MenuItemCreate(
            **base,
            media_url="/media/menu/latte/hero.mp4",
        )

    with pytest.raises(ValidationError):
        MenuItemCreate(
            **base,
            media_type="video",
            media_url="https://storage.example/latte.mp4?token=secret",
            media_poster_url="/media/menu/latte/poster.webp",
        )


# ---------------------------------------------------------------------------
# 5.5 MenuItemResponse derives availability
# ---------------------------------------------------------------------------

def test_menu_item_response_derives_availability() -> None:
    from types import SimpleNamespace

    from core_api.schemas.menu import MenuItemResponse
    from shared.enums import MenuItemAvailability

    def make_item(**kwargs):
        defaults = {
            "id": 1,
            "category_id": 1,
            "name_ru": "Латте",
            "name_en": "Latte",
            "description_ru": None,
            "description_en": None,
            "base_price": 35000,
            "image_url": None,
            "media_type": None,
            "media_url": None,
            "media_poster_url": None,
            "sort_order": 0,
            "created_at": None,
            "updated_at": None,
            "size_options": [],
            "modifiers": [],
        }
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    resp = MenuItemResponse.model_validate(make_item(available=True, archived=False))
    assert resp.availability == MenuItemAvailability.AVAILABLE

    resp = MenuItemResponse.model_validate(make_item(available=False, archived=False))
    assert resp.availability == MenuItemAvailability.STOP_LIST

    resp = MenuItemResponse.model_validate(make_item(available=True, archived=True))
    assert resp.availability == MenuItemAvailability.ARCHIVED


# ---------------------------------------------------------------------------
# 5.6 SizeOption schemas exist
# ---------------------------------------------------------------------------

def test_size_option_schemas_exist() -> None:
    from core_api.schemas.menu import (
        SizeOptionBase,
        SizeOptionCreate,
        SizeOptionUpdate,
        SizeOptionResponse,
    )

    for cls in (SizeOptionBase, SizeOptionCreate, SizeOptionUpdate, SizeOptionResponse):
        assert issubclass(cls, BaseModel), f"{cls.__name__} должен быть BaseModel"


# ---------------------------------------------------------------------------
# 5.7 Modifier schemas exist
# ---------------------------------------------------------------------------

def test_modifier_schemas_exist() -> None:
    from core_api.schemas.menu import (
        ModifierBase,
        ModifierCreate,
        ModifierUpdate,
        ModifierResponse,
    )

    for cls in (ModifierBase, ModifierCreate, ModifierUpdate, ModifierResponse):
        assert issubclass(cls, BaseModel), f"{cls.__name__} должен быть BaseModel"


# ---------------------------------------------------------------------------
# 5.8 MenuItemResponse round-trip from ORM
# ---------------------------------------------------------------------------

def test_menu_item_response_from_orm_roundtrip() -> None:
    from types import SimpleNamespace

    from core_api.schemas.menu import MenuItemResponse

    size = SimpleNamespace(id=1, menu_item_id=1, label="M", price=35000, available=True)
    modifier = SimpleNamespace(id=1, name_ru="Сироп", name_en="Syrup", price=5000, available=True, sort_order=0)
    item = SimpleNamespace(
        id=1,
        category_id=1,
        name_ru="Латте",
        name_en="Latte",
        description_ru=None,
        description_en=None,
        base_price=35000,
        image_url=None,
        media_type="video",
        media_url="/media/menu/latte/hero.mp4",
        media_poster_url="/media/menu/latte/poster.webp",
        available=True,
        archived=False,
        sort_order=0,
        created_at=None,
        updated_at=None,
        size_options=[size],
        modifiers=[modifier],
    )

    resp = MenuItemResponse.model_validate(item)
    assert len(resp.size_options) == 1
    assert len(resp.modifiers) == 1
    assert resp.media_type == "video"
    assert resp.media_url == "/media/menu/latte/hero.mp4"
    assert resp.media_poster_url == "/media/menu/latte/poster.webp"
