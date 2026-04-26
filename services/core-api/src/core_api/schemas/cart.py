"""Pydantic-схемы корзины (Redis-backed, без ORM).

Цены хранятся в копейках (int >= 0).
Снапшоты — эфемерные DTO для отображения; не заменяют иммутабельные
снапшоты позиций заказа (INV-014), которые формируются при checkout.
"""
# START_MODULE_CONTRACT
#   PURPOSE: Cart DTOs — request bodies + server-side responses with computed
#            line totals and snapshots. Redis-backed cart, not persisted via ORM.
#   SCOPE:   Snapshots, create/update bodies, response models, deterministic
#            line_id computation helper on CartItemResponse.
#   DEPENDS: pydantic v2, M-SHARED (MenuItemAvailability, SizeLabel enums).
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §6.2 (cart),
#            INV-006 (server-side stop-list), INV-014 (cart snapshots are
#            ephemeral — order_items have their own immutable snapshots)
#   ROLE:    TYPES
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   MenuItemCartSnapshot   - menu-item display snapshot in cart
#   SizeSnapshot           - chosen size snapshot
#   ModifierSnapshot       - chosen modifier snapshot
#   CartItemCreate         - body for adding/changing a cart line
#   CartItemQuantityUpdate - body for changing only quantity
#   CartItemResponse       - cart line w/ server-computed line_total + snapshots
#   CartResponse           - whole cart with subtotal/expiry
# END_MODULE_MAP

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from shared.enums import MenuItemAvailability, SizeLabel


# ---------------------------------------------------------------------------
# Снапшоты (серверная сторона, только для чтения)
# ---------------------------------------------------------------------------

class MenuItemCartSnapshot(BaseModel):
    """Снапшот позиции меню для отображения в корзине."""

    name_ru: str
    name_en: str
    availability: MenuItemAvailability


class SizeSnapshot(BaseModel):
    """Снапшот выбранного размера."""

    label: SizeLabel
    price: Annotated[int, Field(ge=0)]


class ModifierSnapshot(BaseModel):
    """Снапшот выбранного модификатора."""

    id: int
    name_ru: str
    name_en: str
    price: Annotated[int, Field(ge=0)]


# ---------------------------------------------------------------------------
# Входящие данные от клиента
# ---------------------------------------------------------------------------

class CartItemCreate(BaseModel):
    """Данные добавления/изменения позиции в корзине.

    Цена намеренно отсутствует — всегда вычисляется на сервере (INV-006).
    """

    menu_item_id: int
    size_option_id: int | None = None
    modifier_ids: list[int] = []
    quantity: Annotated[int, Field(ge=1, le=99)]


class CartItemQuantityUpdate(BaseModel):
    """Обновление количества позиции в корзине."""

    quantity: Annotated[int, Field(ge=1, le=99)]


# ---------------------------------------------------------------------------
# Ответы сервера
# ---------------------------------------------------------------------------

class CartItemResponse(BaseModel):
    """Позиция корзины с серверно-вычисленной ценой и снапшотами."""

    @classmethod
    def compute_line_id(
        cls,
        menu_item_id: int,
        size_option_id: int | None,
        modifier_ids: list[int],
    ) -> str:
        """Детерминированный хеш строки корзины (design D2).

        Идентифицирует уникальную комбинацию товар+размер+модификаторы.
        Порядок modifier_ids не важен — список сортируется перед хешированием.
        """
        key = f"{menu_item_id}|{size_option_id or 0}|{','.join(str(i) for i in sorted(modifier_ids))}"
        return hashlib.sha1(key.encode()).hexdigest()[:16]

    line_id: str
    menu_item_id: int
    size_option_id: int | None
    modifier_ids: list[int]
    quantity: Annotated[int, Field(ge=1, le=99)]
    unit_price: Annotated[int, Field(ge=0)]
    line_total: Annotated[int, Field(ge=0)]
    menu_item_snapshot: MenuItemCartSnapshot
    size_snapshot: SizeSnapshot | None
    modifiers_snapshot: list[ModifierSnapshot]

    @model_validator(mode="after")
    def check_line_total(self) -> CartItemResponse:
        expected = self.unit_price * self.quantity
        if self.line_total != expected:
            raise ValueError(
                f"line_total должен равняться unit_price * quantity "
                f"({self.unit_price} * {self.quantity} = {expected}), "
                f"получено {self.line_total}"
            )
        return self


class CartResponse(BaseModel):
    """Полная корзина клиента."""

    items: list[CartItemResponse]
    subtotal: Annotated[int, Field(ge=0)]
    currency: Literal["RUB"]
    expires_at: datetime

    @model_validator(mode="after")
    def check_subtotal(self) -> CartResponse:
        expected = sum(item.line_total for item in self.items)
        if self.subtotal != expected:
            raise ValueError(
                f"subtotal должен равняться сумме line_total позиций "
                f"({expected}), получено {self.subtotal}"
            )
        return self
