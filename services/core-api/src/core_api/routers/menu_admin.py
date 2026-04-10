from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from core_api.deps.database import get_db
from core_api.schemas.menu import (
    AvailabilityPatch,
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    MenuItemCreate,
    MenuItemResponse,
    MenuItemUpdate,
    ModifierCreate,
    ModifierResponse,
    ModifierUpdate,
    SizeOptionCreate,
    SizeOptionResponse,
    SizeOptionUpdate,
)
from core_api.services.menu_admin import MenuAdminService

router = APIRouter(prefix="/api/v1/admin/menu", tags=["menu-admin"])


def get_menu_admin_service(db: Annotated[Session, Depends(get_db)]) -> MenuAdminService:
    return MenuAdminService(db)


_Svc = Annotated[MenuAdminService, Depends(get_menu_admin_service)]


# ─────────────────────────────────────────────
# Categories
# ─────────────────────────────────────────────

@router.post(
    "/categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать категорию",
)
def create_category(body: CategoryCreate, svc: _Svc) -> CategoryResponse:
    return CategoryResponse.model_validate(svc.create_category(body))


@router.get(
    "/categories",
    response_model=list[CategoryResponse],
    summary="Список категорий",
)
def list_categories(svc: _Svc) -> list[CategoryResponse]:
    return [CategoryResponse.model_validate(c) for c in svc.list_categories()]


@router.put(
    "/categories/{category_id}",
    response_model=CategoryResponse,
    summary="Обновить категорию",
)
def update_category(category_id: int, body: CategoryUpdate, svc: _Svc) -> CategoryResponse:
    return CategoryResponse.model_validate(svc.update_category(category_id, body))


@router.delete(
    "/categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить категорию",
)
def delete_category(category_id: int, svc: _Svc) -> None:
    svc.delete_category(category_id)


# ─────────────────────────────────────────────
# Menu items
# ─────────────────────────────────────────────

@router.post(
    "/items",
    response_model=MenuItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать позицию меню",
)
def create_item(body: MenuItemCreate, svc: _Svc) -> MenuItemResponse:
    return MenuItemResponse.model_validate(svc.create_item(body))


@router.get(
    "/items",
    response_model=list[MenuItemResponse],
    summary="Список позиций меню",
)
def list_items(svc: _Svc) -> list[MenuItemResponse]:
    return [MenuItemResponse.model_validate(i) for i in svc.list_items()]


@router.get(
    "/items/{item_id}",
    response_model=MenuItemResponse,
    summary="Получить позицию меню",
)
def get_item(item_id: int, svc: _Svc) -> MenuItemResponse:
    return MenuItemResponse.model_validate(svc.get_item(item_id))


@router.put(
    "/items/{item_id}",
    response_model=MenuItemResponse,
    summary="Обновить позицию меню",
)
def update_item(item_id: int, body: MenuItemUpdate, svc: _Svc) -> MenuItemResponse:
    return MenuItemResponse.model_validate(svc.update_item(item_id, body))


@router.delete(
    "/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить позицию меню",
)
def delete_item(item_id: int, svc: _Svc) -> None:
    svc.delete_item(item_id)


@router.patch(
    "/items/{item_id}/availability",
    response_model=MenuItemResponse,
    summary="Стоп-лист: переключить доступность позиции",
    description="Устанавливает флаг `available` на позиции. Не затрагивает поле `archived`.",
)
def set_item_availability(item_id: int, body: AvailabilityPatch, svc: _Svc) -> MenuItemResponse:
    return MenuItemResponse.model_validate(svc.set_item_availability(item_id, body.available))


# ─────────────────────────────────────────────
# Modifiers
# ─────────────────────────────────────────────

@router.post(
    "/modifiers",
    response_model=ModifierResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать модификатор",
)
def create_modifier(body: ModifierCreate, svc: _Svc) -> ModifierResponse:
    return ModifierResponse.model_validate(svc.create_modifier(body))


@router.get(
    "/modifiers",
    response_model=list[ModifierResponse],
    summary="Список модификаторов",
)
def list_modifiers(svc: _Svc) -> list[ModifierResponse]:
    return [ModifierResponse.model_validate(m) for m in svc.list_modifiers()]


@router.put(
    "/modifiers/{modifier_id}",
    response_model=ModifierResponse,
    summary="Обновить модификатор",
)
def update_modifier(modifier_id: int, body: ModifierUpdate, svc: _Svc) -> ModifierResponse:
    return ModifierResponse.model_validate(svc.update_modifier(modifier_id, body))


@router.delete(
    "/modifiers/{modifier_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить модификатор",
)
def delete_modifier(modifier_id: int, svc: _Svc) -> None:
    svc.delete_modifier(modifier_id)


@router.patch(
    "/modifiers/{modifier_id}/availability",
    response_model=ModifierResponse,
    summary="Стоп-лист: переключить доступность модификатора",
)
def set_modifier_availability(modifier_id: int, body: AvailabilityPatch, svc: _Svc) -> ModifierResponse:
    return ModifierResponse.model_validate(svc.set_modifier_availability(modifier_id, body.available))


# ─────────────────────────────────────────────
# Size options
# ─────────────────────────────────────────────

@router.post(
    "/sizes",
    response_model=SizeOptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить размер к позиции меню",
)
def create_size(body: SizeOptionCreate, svc: _Svc) -> SizeOptionResponse:
    return SizeOptionResponse.model_validate(svc.create_size(body))


@router.put(
    "/sizes/{size_id}",
    response_model=SizeOptionResponse,
    summary="Обновить размер",
)
def update_size(size_id: int, body: SizeOptionUpdate, svc: _Svc) -> SizeOptionResponse:
    return SizeOptionResponse.model_validate(svc.update_size(size_id, body))


@router.delete(
    "/sizes/{size_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить размер",
)
def delete_size(size_id: int, svc: _Svc) -> None:
    svc.delete_size(size_id)
