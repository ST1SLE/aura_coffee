# START_MODULE_CONTRACT
#   PURPOSE: HTTP routes for ADMIN menu CRUD under /api/v1/admin/menu —
#            categories, items, modifiers, sizes, item↔modifier wiring,
#            and stop-list availability flips (INV-006).
#   SCOPE:   Full CRUD over MenuCategory, MenuItem, Modifier, SizeOption.
#            Availability PATCHes implement server-side stop-list (INV-006).
#            Inventory PATCHes update finite stock without changing stop-list.
#   DEPENDS: M-DATABASE (Session), core_api.services.menu_admin,
#            core_api.deps.database, RBACMiddleware (ADMIN-only).
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §5, §6, §7.1 menu,
#            INV-002, INV-006 (server-side stop-list), INV-010.
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   router                       - APIRouter("/api/v1/admin/menu", tags=["menu-admin"])
#   create_category              - POST   /api/v1/admin/menu/categories
#   list_categories              - GET    /api/v1/admin/menu/categories
#   update_category              - PUT    /api/v1/admin/menu/categories/{category_id}
#   delete_category              - DELETE /api/v1/admin/menu/categories/{category_id}
#   create_item                  - POST   /api/v1/admin/menu/items
#   list_items                   - GET    /api/v1/admin/menu/items
#   get_item                     - GET    /api/v1/admin/menu/items/{item_id}
#   update_item                  - PUT    /api/v1/admin/menu/items/{item_id}
#   delete_item                  - DELETE /api/v1/admin/menu/items/{item_id}
#   set_item_availability        - PATCH  /api/v1/admin/menu/items/{item_id}/availability
#   set_item_inventory           - PATCH  /api/v1/admin/menu/items/{item_id}/inventory
#   set_item_modifiers           - PUT    /api/v1/admin/menu/items/{item_id}/modifiers
#   create_modifier              - POST   /api/v1/admin/menu/modifiers
#   list_modifiers               - GET    /api/v1/admin/menu/modifiers
#   update_modifier              - PUT    /api/v1/admin/menu/modifiers/{modifier_id}
#   delete_modifier              - DELETE /api/v1/admin/menu/modifiers/{modifier_id}
#   set_modifier_availability    - PATCH  /api/v1/admin/menu/modifiers/{modifier_id}/availability
#   create_size                  - POST   /api/v1/admin/menu/sizes
#   update_size                  - PUT    /api/v1/admin/menu/sizes/{size_id}
#   delete_size                  - DELETE /api/v1/admin/menu/sizes/{size_id}
#   get_menu_admin_service       - FastAPI Depends factory (not a route)
# END_MODULE_MAP

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from core_api.deps.database import get_db
from core_api.schemas.menu import (
    AvailabilityPatch,
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    InventoryPatch,
    MenuItemCreate,
    MenuItemModifierSet,
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

# START_CONTRACT: create_category
#   PURPOSE: Create a new menu category.
#   INPUTS:  body: CategoryCreate, MenuAdminService.
#   OUTPUTS: 201 CategoryResponse.
#   SIDE_EFFECTS: DB insert into menu_categories.
#   LINKS:   PDD §5, INV-002, INV-010, services.menu_admin.
# END_CONTRACT: create_category
@router.post(
    "/categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать категорию",
)
def create_category(body: CategoryCreate, svc: _Svc) -> CategoryResponse:
    return CategoryResponse.model_validate(svc.create_category(body))


# START_CONTRACT: list_categories
#   PURPOSE: List all menu categories (admin view, no archive filter).
#   INPUTS:  MenuAdminService.
#   OUTPUTS: 200 list[CategoryResponse].
#   SIDE_EFFECTS: none.
#   LINKS:   PDD §5, INV-002, INV-010, services.menu_admin.
# END_CONTRACT: list_categories
@router.get(
    "/categories",
    response_model=list[CategoryResponse],
    summary="Список категорий",
)
def list_categories(svc: _Svc) -> list[CategoryResponse]:
    return [CategoryResponse.model_validate(c) for c in svc.list_categories()]


# START_CONTRACT: update_category
#   PURPOSE: Update an existing menu category.
#   INPUTS:  category_id: int, body: CategoryUpdate, MenuAdminService.
#   OUTPUTS: 200 CategoryResponse; 404 if missing (raised by service).
#   SIDE_EFFECTS: DB update on menu_categories row.
#   LINKS:   PDD §5, INV-002, INV-010, services.menu_admin.
# END_CONTRACT: update_category
@router.put(
    "/categories/{category_id}",
    response_model=CategoryResponse,
    summary="Обновить категорию",
)
def update_category(category_id: int, body: CategoryUpdate, svc: _Svc) -> CategoryResponse:
    return CategoryResponse.model_validate(svc.update_category(category_id, body))


# START_CONTRACT: delete_category
#   PURPOSE: Delete (or archive) a menu category.
#   INPUTS:  category_id: int, MenuAdminService.
#   OUTPUTS: 204 No Content.
#   SIDE_EFFECTS: DB delete/update on menu_categories row.
#   LINKS:   PDD §5, INV-002, INV-010, services.menu_admin.
# END_CONTRACT: delete_category
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

# START_CONTRACT: create_item
#   PURPOSE: Create a new menu item.
#   INPUTS:  body: MenuItemCreate, MenuAdminService.
#   OUTPUTS: 201 MenuItemResponse.
#   SIDE_EFFECTS: DB insert into menu_items.
#   LINKS:   PDD §5, INV-002, INV-010, services.menu_admin.
# END_CONTRACT: create_item
@router.post(
    "/items",
    response_model=MenuItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать позицию меню",
)
def create_item(body: MenuItemCreate, svc: _Svc) -> MenuItemResponse:
    return MenuItemResponse.model_validate(svc.create_item(body))


# START_CONTRACT: list_items
#   PURPOSE: List menu items, optionally filtered by category_id.
#   INPUTS:  MenuAdminService, category_id (query, optional, gt=0).
#   OUTPUTS: 200 list[MenuItemResponse].
#   SIDE_EFFECTS: none.
#   LINKS:   PDD §5, INV-002, INV-010, services.menu_admin.
# END_CONTRACT: list_items
@router.get(
    "/items",
    response_model=list[MenuItemResponse],
    summary="Список позиций меню",
)
def list_items(
    svc: _Svc,
    category_id: Annotated[int | None, Query(gt=0)] = None,
) -> list[MenuItemResponse]:
    return [MenuItemResponse.model_validate(i) for i in svc.list_items(category_id=category_id)]


# START_CONTRACT: get_item
#   PURPOSE: Return a single menu item by id.
#   INPUTS:  item_id: int, MenuAdminService.
#   OUTPUTS: 200 MenuItemResponse; 404 if missing (raised by service).
#   SIDE_EFFECTS: none.
#   LINKS:   PDD §5, INV-002, INV-010, services.menu_admin.
# END_CONTRACT: get_item
@router.get(
    "/items/{item_id}",
    response_model=MenuItemResponse,
    summary="Получить позицию меню",
)
def get_item(item_id: int, svc: _Svc) -> MenuItemResponse:
    return MenuItemResponse.model_validate(svc.get_item(item_id))


# START_CONTRACT: update_item
#   PURPOSE: Update an existing menu item.
#   INPUTS:  item_id: int, body: MenuItemUpdate, MenuAdminService.
#   OUTPUTS: 200 MenuItemResponse.
#   SIDE_EFFECTS: DB update on menu_items row.
#   LINKS:   PDD §5, INV-002, INV-010, services.menu_admin.
# END_CONTRACT: update_item
@router.put(
    "/items/{item_id}",
    response_model=MenuItemResponse,
    summary="Обновить позицию меню",
)
def update_item(item_id: int, body: MenuItemUpdate, svc: _Svc) -> MenuItemResponse:
    return MenuItemResponse.model_validate(svc.update_item(item_id, body))


# START_CONTRACT: delete_item
#   PURPOSE: Delete or archive a menu item.
#   INPUTS:  item_id: int, MenuAdminService.
#   OUTPUTS: 204 No Content.
#   SIDE_EFFECTS: DB delete/archive on menu_items row.
#   LINKS:   PDD §5, INV-002, INV-010, services.menu_admin.
# END_CONTRACT: delete_item
@router.delete(
    "/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить позицию меню",
)
def delete_item(item_id: int, svc: _Svc) -> None:
    svc.delete_item(item_id)


# START_CONTRACT: set_item_availability
#   PURPOSE: Stop-list flip — toggle MenuItem.available without touching
#            archived (INV-006 server-side stop-list).
#   INPUTS:  item_id: int, body: AvailabilityPatch, MenuAdminService.
#   OUTPUTS: 200 MenuItemResponse.
#   SIDE_EFFECTS: DB update on menu_items.available.
#   LINKS:   PDD §5, INV-002, INV-006, INV-010, services.menu_admin.
# END_CONTRACT: set_item_availability
@router.patch(
    "/items/{item_id}/availability",
    response_model=MenuItemResponse,
    summary="Стоп-лист: переключить доступность позиции",
    description="Устанавливает флаг `available` на позиции. Не затрагивает поле `archived`.",
)
def set_item_availability(item_id: int, body: AvailabilityPatch, svc: _Svc) -> MenuItemResponse:
    return MenuItemResponse.model_validate(svc.set_item_availability(item_id, body.available))


# START_CONTRACT: set_item_inventory
#   PURPOSE: Operational stock update — set MenuItem.inventory_quantity while
#            preserving MenuItem.available as stop-list only.
#   INPUTS:  item_id: int, body: InventoryPatch, MenuAdminService.
#   OUTPUTS: 200 MenuItemResponse.
#   SIDE_EFFECTS: DB update on menu_items.inventory_quantity.
#   LINKS:   PDD §5, INV-002, INV-010, services.menu_admin.
# END_CONTRACT: set_item_inventory
@router.patch(
    "/items/{item_id}/inventory",
    response_model=MenuItemResponse,
    summary="Обновить остаток позиции меню",
    description="Устанавливает `inventory_quantity`; null означает не отслеживать остаток.",
)
def set_item_inventory(item_id: int, body: InventoryPatch, svc: _Svc) -> MenuItemResponse:
    return MenuItemResponse.model_validate(
        svc.set_item_inventory(item_id, body.inventory_quantity)
    )


# START_CONTRACT: set_item_modifiers
#   PURPOSE: Replace the full set of modifiers wired to a menu item.
#   INPUTS:  item_id: int, body: MenuItemModifierSet, MenuAdminService.
#   OUTPUTS: 200 MenuItemResponse.
#   SIDE_EFFECTS: DB writes — replaces association rows in
#                 menu_item_modifiers.
#   LINKS:   PDD §5, INV-002, INV-010, services.menu_admin.
# END_CONTRACT: set_item_modifiers
@router.put(
    "/items/{item_id}/modifiers",
    response_model=MenuItemResponse,
    summary="Заменить набор модификаторов у позиции меню",
)
def set_item_modifiers(item_id: int, body: MenuItemModifierSet, svc: _Svc) -> MenuItemResponse:
    return MenuItemResponse.model_validate(svc.set_item_modifiers(item_id, body.modifier_ids))


# ─────────────────────────────────────────────
# Modifiers
# ─────────────────────────────────────────────

# START_CONTRACT: create_modifier
#   PURPOSE: Create a new modifier (e.g., milk type, syrup).
#   INPUTS:  body: ModifierCreate, MenuAdminService.
#   OUTPUTS: 201 ModifierResponse.
#   SIDE_EFFECTS: DB insert into modifiers.
#   LINKS:   PDD §5, INV-002, INV-010, services.menu_admin.
# END_CONTRACT: create_modifier
@router.post(
    "/modifiers",
    response_model=ModifierResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать модификатор",
)
def create_modifier(body: ModifierCreate, svc: _Svc) -> ModifierResponse:
    return ModifierResponse.model_validate(svc.create_modifier(body))


# START_CONTRACT: list_modifiers
#   PURPOSE: List all modifiers.
#   INPUTS:  MenuAdminService.
#   OUTPUTS: 200 list[ModifierResponse].
#   SIDE_EFFECTS: none.
#   LINKS:   PDD §5, INV-002, INV-010, services.menu_admin.
# END_CONTRACT: list_modifiers
@router.get(
    "/modifiers",
    response_model=list[ModifierResponse],
    summary="Список модификаторов",
)
def list_modifiers(svc: _Svc) -> list[ModifierResponse]:
    return [ModifierResponse.model_validate(m) for m in svc.list_modifiers()]


# START_CONTRACT: update_modifier
#   PURPOSE: Update an existing modifier.
#   INPUTS:  modifier_id: int, body: ModifierUpdate, MenuAdminService.
#   OUTPUTS: 200 ModifierResponse.
#   SIDE_EFFECTS: DB update on modifiers row.
#   LINKS:   PDD §5, INV-002, INV-010, services.menu_admin.
# END_CONTRACT: update_modifier
@router.put(
    "/modifiers/{modifier_id}",
    response_model=ModifierResponse,
    summary="Обновить модификатор",
)
def update_modifier(modifier_id: int, body: ModifierUpdate, svc: _Svc) -> ModifierResponse:
    return ModifierResponse.model_validate(svc.update_modifier(modifier_id, body))


# START_CONTRACT: delete_modifier
#   PURPOSE: Delete or archive a modifier.
#   INPUTS:  modifier_id: int, MenuAdminService.
#   OUTPUTS: 204 No Content.
#   SIDE_EFFECTS: DB delete/archive on modifiers row.
#   LINKS:   PDD §5, INV-002, INV-010, services.menu_admin.
# END_CONTRACT: delete_modifier
@router.delete(
    "/modifiers/{modifier_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить модификатор",
)
def delete_modifier(modifier_id: int, svc: _Svc) -> None:
    svc.delete_modifier(modifier_id)


# START_CONTRACT: set_modifier_availability
#   PURPOSE: Stop-list flip for a modifier (INV-006 server-side stop-list).
#   INPUTS:  modifier_id: int, body: AvailabilityPatch, MenuAdminService.
#   OUTPUTS: 200 ModifierResponse.
#   SIDE_EFFECTS: DB update on modifiers.available.
#   LINKS:   PDD §5, INV-002, INV-006, INV-010, services.menu_admin.
# END_CONTRACT: set_modifier_availability
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

# START_CONTRACT: create_size
#   PURPOSE: Add a new size option to a menu item.
#   INPUTS:  body: SizeOptionCreate, MenuAdminService.
#   OUTPUTS: 201 SizeOptionResponse.
#   SIDE_EFFECTS: DB insert into menu_item_size_options.
#   LINKS:   PDD §5, INV-002, INV-010, services.menu_admin.
# END_CONTRACT: create_size
@router.post(
    "/sizes",
    response_model=SizeOptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить размер к позиции меню",
)
def create_size(body: SizeOptionCreate, svc: _Svc) -> SizeOptionResponse:
    return SizeOptionResponse.model_validate(svc.create_size(body))


# START_CONTRACT: update_size
#   PURPOSE: Update a size option.
#   INPUTS:  size_id: int, body: SizeOptionUpdate, MenuAdminService.
#   OUTPUTS: 200 SizeOptionResponse.
#   SIDE_EFFECTS: DB update on menu_item_size_options row.
#   LINKS:   PDD §5, INV-002, INV-010, services.menu_admin.
# END_CONTRACT: update_size
@router.put(
    "/sizes/{size_id}",
    response_model=SizeOptionResponse,
    summary="Обновить размер",
)
def update_size(size_id: int, body: SizeOptionUpdate, svc: _Svc) -> SizeOptionResponse:
    return SizeOptionResponse.model_validate(svc.update_size(size_id, body))


# START_CONTRACT: delete_size
#   PURPOSE: Delete a size option.
#   INPUTS:  size_id: int, MenuAdminService.
#   OUTPUTS: 204 No Content.
#   SIDE_EFFECTS: DB delete on menu_item_size_options row.
#   LINKS:   PDD §5, INV-002, INV-010, services.menu_admin.
# END_CONTRACT: delete_size
@router.delete(
    "/sizes/{size_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить размер",
)
def delete_size(size_id: int, svc: _Svc) -> None:
    svc.delete_size(size_id)
