"""Pydantic-схемы меню: Category, Modifier, SizeOption, MenuItem."""
# START_MODULE_CONTRACT
#   PURPOSE: Admin + public menu DTOs (categories, modifiers, sizes, items).
#            Defines the price-kopeck type and the public menu projection
#            served to non-authenticated clients.
#   SCOPE:   Base/Create/Update/Response per entity, AvailabilityPatch,
#            MenuItemModifierSet, public PublicCategory/PublicMenuItem/...
#   DEPENDS: pydantic v2, M-SHARED (CategoryType, MenuItemAvailability,
#            MenuMediaType, SizeLabel).
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §6.4 (menu state machine),
#            INV-006 (stop-list server-side), INV-010 (admin-only mutators)
#   ROLE:    TYPES
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   PriceKopecks            - alias type Annotated[int, Field(ge=0)]
#   InventoryQuantity       - alias type Annotated[int, Field(ge=0)]
#   MediaPath               - alias type Annotated[str, Field(...)]
#   CategoryBase            - shared category fields
#   CategoryCreate          - POST body for /admin/menu/categories
#   CategoryUpdate          - PUT body (partial) for /admin/menu/categories/{id}
#   CategoryResponse        - read projection of Category
#   ModifierBase            - shared modifier fields
#   ModifierCreate          - POST body for /admin/menu/modifiers
#   ModifierUpdate          - PUT body (partial)
#   ModifierResponse        - read projection of Modifier
#   SizeOptionBase          - shared size-option fields
#   SizeOptionCreate        - POST body for /admin/menu/sizes
#   SizeOptionUpdate        - PUT body (partial)
#   SizeOptionResponse      - read projection of SizeOption
#   MenuItemBase            - shared menu-item fields
#   MenuItemCreate          - POST body for /admin/menu/items
#   MenuItemUpdate          - PUT body (partial)
#   MenuItemResponse        - admin projection w/ size_options + modifiers
#   AvailabilityPatch       - PATCH body for stop-list toggle (extra=forbid)
#   InventoryPatch          - PATCH body for stock update (extra=forbid)
#   MenuItemModifierSet     - PUT body for setting an item's modifier list
#   PublicMenuSizeOption    - public projection of SizeOption
#   PublicMenuModifier      - public projection of Modifier
#   PublicMenuItem          - public projection of MenuItem
#   PublicCategory          - public projection of Category w/ items
#   PublicMenuResponse      - GET /api/v1/menu top-level body
# END_MODULE_MAP

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from shared.enums import CategoryType, MenuItemAvailability, MenuMediaType, SizeLabel

# Общий тип для цен в копейках (>= 0)
PriceKopecks = Annotated[int, Field(ge=0)]
InventoryQuantity = Annotated[int, Field(ge=0)]
MediaPath = Annotated[str, Field(min_length=1, max_length=500)]

_MEDIA_PATH_PREFIX = "/media/menu/"
_IMAGE_EXTENSIONS = (".avif", ".jpg", ".jpeg", ".png", ".webp")
_VIDEO_EXTENSIONS = (".mp4", ".webm")


def _normalize_media_asset_path(value: object) -> object:
    if value is None:
        return None
    if not isinstance(value, str):
        return value

    path = value.strip()
    if path == "":
        return None

    lowered = path.lower()
    if not path.startswith(_MEDIA_PATH_PREFIX):
        raise ValueError("media paths must be public local paths under /media/menu/")
    if "?" in path or "#" in path:
        raise ValueError("media paths must not include query strings or fragments")
    if "://" in lowered or lowered.startswith("//"):
        raise ValueError("media paths must not be absolute external URLs")
    if any(part == ".." for part in path.split("/")):
        raise ValueError("media paths must not contain parent directory segments")
    if any(ch.isspace() for ch in path):
        raise ValueError("media paths must not contain whitespace")
    return path


def _media_type_value(media_type: MenuMediaType | str | None) -> str | None:
    if media_type is None:
        return None
    if isinstance(media_type, MenuMediaType):
        return media_type.value
    return media_type


def _has_extension(path: str, extensions: tuple[str, ...]) -> bool:
    return path.lower().endswith(extensions)


def _validate_media_combination(
    media_type: MenuMediaType | str | None,
    media_url: str | None,
    media_poster_url: str | None,
) -> None:
    media_type_value = _media_type_value(media_type)
    if media_type_value is None:
        if media_url is not None or media_poster_url is not None:
            raise ValueError("media_type is required when media URLs are set")
        return

    if media_url is None:
        raise ValueError("media_url is required when media_type is set")

    if media_type_value == MenuMediaType.VIDEO.value:
        if media_poster_url is None:
            raise ValueError("media_poster_url is required for video media")
        if not _has_extension(media_url, _VIDEO_EXTENSIONS):
            raise ValueError("video media_url must end with .mp4 or .webm")
        if not _has_extension(media_poster_url, _IMAGE_EXTENSIONS):
            raise ValueError("video media_poster_url must be an image path")
        return

    if media_type_value == MenuMediaType.IMAGE.value:
        if media_poster_url is not None:
            raise ValueError("media_poster_url is only supported for video media")
        if not _has_extension(media_url, _IMAGE_EXTENSIONS):
            raise ValueError("image media_url must be an image path")
        return

    raise ValueError("media_type must be image or video")


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
    media_type: MenuMediaType | None = None
    media_url: MediaPath | None = None
    media_poster_url: MediaPath | None = None
    inventory_quantity: InventoryQuantity | None = None
    available: bool = True
    archived: bool = False
    sort_order: int = 0

    @field_validator("media_url", "media_poster_url", mode="before")
    @classmethod
    def _normalize_media_paths(cls, value: object) -> object:
        return _normalize_media_asset_path(value)

    @model_validator(mode="after")
    def _validate_media(self) -> MenuItemBase:
        _validate_media_combination(
            self.media_type,
            self.media_url,
            self.media_poster_url,
        )
        return self


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
    media_type: MenuMediaType | None = None
    media_url: MediaPath | None = None
    media_poster_url: MediaPath | None = None
    inventory_quantity: InventoryQuantity | None = None
    available: bool | None = None
    archived: bool | None = None
    sort_order: int | None = None

    @field_validator("media_url", "media_poster_url", mode="before")
    @classmethod
    def _normalize_media_paths(cls, value: object) -> object:
        return _normalize_media_asset_path(value)


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
# AvailabilityPatch  (stop-list toggle — единственное поле)
# ---------------------------------------------------------------------------

class AvailabilityPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available: bool


class InventoryPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory_quantity: InventoryQuantity | None


class MenuItemModifierSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    modifier_ids: list[int]


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
    media_type: MenuMediaType | None = None
    media_url: str | None = None
    media_poster_url: str | None = None
    inventory_quantity: InventoryQuantity | None = None
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
