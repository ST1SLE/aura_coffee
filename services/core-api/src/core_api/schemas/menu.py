"""Pydantic-схемы меню: Category, Modifier, SizeOption, MenuItem."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, computed_field

from shared.enums import CategoryType, MenuItemAvailability, SizeLabel

# Общий тип для цен в копейках (>= 0)
PriceKopecks = Annotated[int, Field(ge=0)]


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------

class CategoryBase(BaseModel):
    type: CategoryType
    name_ru: str
    name_en: str
    sort_order: int = 0
    is_visible: bool = True


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    type: CategoryType | None = None
    name_ru: str | None = None
    name_en: str | None = None
    sort_order: int | None = None
    is_visible: bool | None = None


class CategoryResponse(CategoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ---------------------------------------------------------------------------
# Modifier
# ---------------------------------------------------------------------------

class ModifierBase(BaseModel):
    name_ru: str
    name_en: str
    price: PriceKopecks = 0
    available: bool = True
    sort_order: int = 0


class ModifierCreate(ModifierBase):
    pass


class ModifierUpdate(BaseModel):
    name_ru: str | None = None
    name_en: str | None = None
    price: PriceKopecks | None = None
    available: bool | None = None
    sort_order: int | None = None


class ModifierResponse(ModifierBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


# ---------------------------------------------------------------------------
# SizeOption
# ---------------------------------------------------------------------------

class SizeOptionBase(BaseModel):
    label: SizeLabel
    price: PriceKopecks = 0
    available: bool = True


class SizeOptionCreate(SizeOptionBase):
    menu_item_id: int


class SizeOptionUpdate(BaseModel):
    label: SizeLabel | None = None
    price: PriceKopecks | None = None
    available: bool | None = None


class SizeOptionResponse(SizeOptionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    menu_item_id: int


# ---------------------------------------------------------------------------
# MenuItem  (ссылается на SizeOptionResponse и ModifierResponse — нет forward refs)
# ---------------------------------------------------------------------------

class MenuItemBase(BaseModel):
    category_id: int
    name_ru: str
    name_en: str
    description_ru: str | None = None
    description_en: str | None = None
    base_price: PriceKopecks = 0
    image_url: str | None = None
    available: bool = True
    archived: bool = False
    sort_order: int = 0


class MenuItemCreate(MenuItemBase):
    pass


class MenuItemUpdate(BaseModel):
    category_id: int | None = None
    name_ru: str | None = None
    name_en: str | None = None
    description_ru: str | None = None
    description_en: str | None = None
    base_price: PriceKopecks | None = None
    image_url: str | None = None
    available: bool | None = None
    archived: bool | None = None
    sort_order: int | None = None


class MenuItemResponse(MenuItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
    size_options: list[SizeOptionResponse] = []
    modifiers: list[ModifierResponse] = []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def availability(self) -> MenuItemAvailability:
        if self.archived:
            return MenuItemAvailability.ARCHIVED
        if not self.available:
            return MenuItemAvailability.STOP_LIST
        return MenuItemAvailability.AVAILABLE


# ---------------------------------------------------------------------------
# Публичный API меню (клиентская сторона)
# ---------------------------------------------------------------------------

class PublicMenuSizeOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label: SizeLabel
    price: PriceKopecks
    available: bool


class PublicMenuModifier(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    name_ru: str
    name_en: str
    price: PriceKopecks
    available: bool


class PublicMenuItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int
    name: str
    name_ru: str
    name_en: str
    description: str | None = None
    description_ru: str | None = None
    description_en: str | None = None
    base_price: PriceKopecks
    image_url: str | None = None
    available: bool
    sort_order: int
    size_options: list[PublicMenuSizeOption] = []
    modifiers: list[PublicMenuModifier] = []


class PublicCategory(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: CategoryType
    name: str
    name_ru: str
    name_en: str
    sort_order: int
    items: list[PublicMenuItem] = []


class PublicMenuResponse(BaseModel):
    categories: list[PublicCategory] = []
