# START_MODULE_CONTRACT
#   PURPOSE: Admin CRUD for menu domain — Categories, MenuItems, Modifiers,
#            SizeOptions, plus availability toggles (stop-list), finite-stock
#            inventory updates, and modifier link management. Translates
#            IntegrityError into HTTP 409.
#   SCOPE:   create/update/delete/list/get + availability + inventory +
#            relations across four menu aggregates.
#   DEPENDS: M-SHARED (Category/MenuItem/Modifier/SizeOption), M-DATABASE,
#            schemas.menu, FastAPI HTTPException
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §5.3, INV-006, INV-010
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   MenuAdminService - container for all menu admin operations
# END_MODULE_MAP
"""Сервисный слой для CRUD меню в админ-панели."""

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from core_api.schemas.menu import (
    CategoryCreate,
    CategoryUpdate,
    MenuItemCreate,
    MenuItemUpdate,
    ModifierCreate,
    ModifierUpdate,
    SizeOptionCreate,
    SizeOptionUpdate,
    _validate_media_combination,
)
from shared.models.menu import Category, MenuItem, Modifier, SizeOption


def _handle_integrity(exc: IntegrityError, detail: str) -> None:
    """Преобразование IntegrityError в HTTP 409."""
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc


def _validate_item_media_state(item: MenuItem) -> None:
    try:
        _validate_media_combination(
            item.media_type,
            item.media_url,
            item.media_poster_url,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


# START_CONTRACT: MenuAdminService
#   PURPOSE: Bundle all admin-side menu CRUD onto a single session-bound object.
#            Each method commits its own change (INV-004 atomicity is per-method
#            since menu writes are not financial mutations).
#   INPUTS:  db: Session — admin-scoped DB session.
#   OUTPUTS: MenuAdminService instance.
#   SIDE_EFFECTS: methods perform DB INSERT/UPDATE/DELETE + commit; map
#                 IntegrityError to HTTPException(409) and 404 for missing rows.
#   LINKS:   PDD §5.3, INV-006 (availability), INV-010 (admin-only RBAC)
# END_CONTRACT: MenuAdminService
class MenuAdminService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ─────────────────────────────────────────────
    # Categories
    # ─────────────────────────────────────────────

    # START_CONTRACT: MenuAdminService.create_category
    #   PURPOSE: INSERT a Category row.
    #   INPUTS:  data: CategoryCreate
    #   OUTPUTS: Category (refreshed)
    #   SIDE_EFFECTS: DB INSERT + commit; IntegrityError → HTTP 409.
    # END_CONTRACT: MenuAdminService.create_category
    def create_category(self, data: CategoryCreate) -> Category:
        cat = Category(**data.model_dump())
        self.db.add(cat)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            _handle_integrity(exc, "integrity error")
        self.db.refresh(cat)
        return cat

    # START_CONTRACT: MenuAdminService.update_category
    #   PURPOSE: PATCH a Category row.
    #   INPUTS:  category_id: int, data: CategoryUpdate
    #   OUTPUTS: Category (refreshed)
    #   SIDE_EFFECTS: DB UPDATE + commit; missing → HTTP 404.
    # END_CONTRACT: MenuAdminService.update_category
    def update_category(self, category_id: int, data: CategoryUpdate) -> Category:
        cat = self.db.get(Category, category_id)
        if cat is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="category not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(cat, field, value)
        self.db.commit()
        self.db.refresh(cat)
        return cat

    # START_CONTRACT: MenuAdminService.delete_category
    #   PURPOSE: DELETE a Category row.
    #   INPUTS:  category_id: int
    #   OUTPUTS: None
    #   SIDE_EFFECTS: DB DELETE + commit; FK violation → HTTP 409 ("category has items").
    # END_CONTRACT: MenuAdminService.delete_category
    def delete_category(self, category_id: int) -> None:
        cat = self.db.get(Category, category_id)
        if cat is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="category not found")
        self.db.delete(cat)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            _handle_integrity(exc, "category has items")

    # START_CONTRACT: MenuAdminService.list_categories
    #   PURPOSE: List all categories ordered by sort_order, id.
    #   INPUTS:  none
    #   OUTPUTS: list[Category]
    #   SIDE_EFFECTS: DB SELECT only.
    # END_CONTRACT: MenuAdminService.list_categories
    def list_categories(self) -> list[Category]:
        return self.db.query(Category).order_by(Category.sort_order, Category.id).all()

    # ─────────────────────────────────────────────
    # Menu items
    # ─────────────────────────────────────────────

    # START_CONTRACT: MenuAdminService.create_item
    #   PURPOSE: INSERT a MenuItem row, validating that the category exists
    #            and media fields form a public, non-secret local asset contract.
    #   INPUTS:  data: MenuItemCreate
    #   OUTPUTS: MenuItem (refreshed)
    #   SIDE_EFFECTS: DB INSERT + commit; missing category → HTTP 404; integrity → HTTP 409.
    # END_CONTRACT: MenuAdminService.create_item
    def create_item(self, data: MenuItemCreate) -> MenuItem:
        # Проверяем что категория существует
        if self.db.get(Category, data.category_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="category not found")
        item = MenuItem(**data.model_dump())
        _validate_item_media_state(item)
        self.db.add(item)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            _handle_integrity(exc, "integrity error")
        self.db.refresh(item)
        return item

    # START_CONTRACT: MenuAdminService.update_item
    #   PURPOSE: PATCH a MenuItem row, rejecting malformed final media state.
    #   INPUTS:  item_id: int, data: MenuItemUpdate
    #   OUTPUTS: MenuItem (refreshed)
    #   SIDE_EFFECTS: DB UPDATE + commit; missing → HTTP 404.
    # END_CONTRACT: MenuAdminService.update_item
    def update_item(self, item_id: int, data: MenuItemUpdate) -> MenuItem:
        item = self.db.get(MenuItem, item_id)
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="item not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        try:
            _validate_item_media_state(item)
        except HTTPException:
            self.db.rollback()
            raise
        self.db.commit()
        self.db.refresh(item)
        return item

    # START_CONTRACT: MenuAdminService.delete_item
    #   PURPOSE: DELETE a MenuItem row (FK guards in DB).
    #   INPUTS:  item_id: int
    #   OUTPUTS: None
    #   SIDE_EFFECTS: DB DELETE + commit; missing → HTTP 404; integrity → HTTP 409.
    # END_CONTRACT: MenuAdminService.delete_item
    def delete_item(self, item_id: int) -> None:
        item = self.db.get(MenuItem, item_id)
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="item not found")
        self.db.delete(item)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            _handle_integrity(exc, "integrity error")

    # START_CONTRACT: MenuAdminService.list_items
    #   PURPOSE: List menu items, optionally filtered by category, with eager
    #            load of size_options and modifiers for admin UI.
    #   INPUTS:  category_id: int | None
    #   OUTPUTS: list[MenuItem]
    #   SIDE_EFFECTS: DB SELECT only; unknown category_id → HTTP 404.
    # END_CONTRACT: MenuAdminService.list_items
    def list_items(self, category_id: int | None = None) -> list[MenuItem]:
        if category_id is not None:
            if self.db.get(Category, category_id) is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="category not found")
        query = (
            self.db.query(MenuItem)
            .options(selectinload(MenuItem.size_options), selectinload(MenuItem.modifiers))
        )
        if category_id is not None:
            query = query.filter(MenuItem.category_id == category_id)
        return query.order_by(MenuItem.sort_order, MenuItem.id).all()

    # START_CONTRACT: MenuAdminService.get_item
    #   PURPOSE: Load a MenuItem with sizes and modifiers eager-loaded.
    #   INPUTS:  item_id: int
    #   OUTPUTS: MenuItem
    #   SIDE_EFFECTS: DB SELECT only; missing → HTTP 404.
    # END_CONTRACT: MenuAdminService.get_item
    def get_item(self, item_id: int) -> MenuItem:
        item = (
            self.db.query(MenuItem)
            .options(selectinload(MenuItem.size_options), selectinload(MenuItem.modifiers))
            .filter(MenuItem.id == item_id)
            .first()
        )
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="item not found")
        return item

    # START_CONTRACT: MenuAdminService.set_item_availability
    #   PURPOSE: Toggle stop-list flag (available=True/False) on a menu item —
    #            authoritative server-side gate (INV-006).
    #   INPUTS:  item_id: int, available: bool
    #   OUTPUTS: MenuItem (with eager relations)
    #   SIDE_EFFECTS: DB UPDATE + commit; missing → HTTP 404.
    #   LINKS:   PDD §5.3, INV-006
    # END_CONTRACT: MenuAdminService.set_item_availability
    def set_item_availability(self, item_id: int, available: bool) -> MenuItem:
        item = self.db.get(MenuItem, item_id)
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="item not found")
        item.available = available
        self.db.commit()
        # Перезагружаем вместе со связями для вычисляемого поля availability
        return self.get_item(item_id)

    # START_CONTRACT: MenuAdminService.set_item_inventory
    #   PURPOSE: Operationally set finite stock for a menu item without
    #            touching the stop-list flag. NULL means unlimited/not tracked;
    #            0 means out of stock.
    #   INPUTS:  item_id: int, inventory_quantity: int | None
    #   OUTPUTS: MenuItem (with eager relations)
    #   SIDE_EFFECTS: DB UPDATE + commit; missing → HTTP 404.
    #   LINKS:   PDD §5.3, INV-002, INV-010
    # END_CONTRACT: MenuAdminService.set_item_inventory
    def set_item_inventory(
        self, item_id: int, inventory_quantity: int | None
    ) -> MenuItem:
        item = self.db.get(MenuItem, item_id)
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="item not found")
        item.inventory_quantity = inventory_quantity
        self.db.commit()
        return self.get_item(item_id)

    # START_CONTRACT: MenuAdminService.set_item_modifiers
    #   PURPOSE: Replace the modifier link list for a menu item; deduplicates
    #            preserving order; rejects unknown modifier ids.
    #   INPUTS:  item_id: int, modifier_ids: list[int]
    #   OUTPUTS: MenuItem (refreshed)
    #   SIDE_EFFECTS: DB UPDATE association + commit; missing item → 404; unknown
    #                 modifier ids → HTTP 422.
    # END_CONTRACT: MenuAdminService.set_item_modifiers
    def set_item_modifiers(self, item_id: int, modifier_ids: list[int]) -> MenuItem:
        # Проверка существования позиции и eager-загрузка связи modifiers
        item = self.get_item(item_id)
        # Дедупликация с сохранением порядка
        unique_ids = list(dict.fromkeys(modifier_ids))
        if unique_ids:
            mods = self.db.query(Modifier).filter(Modifier.id.in_(unique_ids)).all()
            if len(mods) != len(unique_ids):
                missing = sorted(set(unique_ids) - {m.id for m in mods})
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"unknown modifier ids: {missing}",
                )
        else:
            mods = []
        item.modifiers = mods
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            _handle_integrity(exc, "integrity error")
        return self.get_item(item_id)

    # ─────────────────────────────────────────────
    # Modifiers
    # ─────────────────────────────────────────────

    # START_CONTRACT: MenuAdminService.create_modifier
    #   PURPOSE: INSERT a Modifier row.
    #   INPUTS:  data: ModifierCreate
    #   OUTPUTS: Modifier (refreshed)
    #   SIDE_EFFECTS: DB INSERT + commit; integrity → HTTP 409.
    # END_CONTRACT: MenuAdminService.create_modifier
    def create_modifier(self, data: ModifierCreate) -> Modifier:
        mod = Modifier(**data.model_dump())
        self.db.add(mod)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            _handle_integrity(exc, "integrity error")
        self.db.refresh(mod)
        return mod

    # START_CONTRACT: MenuAdminService.update_modifier
    #   PURPOSE: PATCH a Modifier row.
    #   INPUTS:  modifier_id: int, data: ModifierUpdate
    #   OUTPUTS: Modifier (refreshed)
    #   SIDE_EFFECTS: DB UPDATE + commit; missing → HTTP 404.
    # END_CONTRACT: MenuAdminService.update_modifier
    def update_modifier(self, modifier_id: int, data: ModifierUpdate) -> Modifier:
        mod = self.db.get(Modifier, modifier_id)
        if mod is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="modifier not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(mod, field, value)
        self.db.commit()
        self.db.refresh(mod)
        return mod

    # START_CONTRACT: MenuAdminService.delete_modifier
    #   PURPOSE: DELETE a Modifier row.
    #   INPUTS:  modifier_id: int
    #   OUTPUTS: None
    #   SIDE_EFFECTS: DB DELETE + commit; missing → 404; integrity → HTTP 409.
    # END_CONTRACT: MenuAdminService.delete_modifier
    def delete_modifier(self, modifier_id: int) -> None:
        mod = self.db.get(Modifier, modifier_id)
        if mod is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="modifier not found")
        self.db.delete(mod)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            _handle_integrity(exc, "integrity error")

    # START_CONTRACT: MenuAdminService.list_modifiers
    #   PURPOSE: List all modifiers ordered by sort_order, id.
    #   INPUTS:  none
    #   OUTPUTS: list[Modifier]
    #   SIDE_EFFECTS: DB SELECT only.
    # END_CONTRACT: MenuAdminService.list_modifiers
    def list_modifiers(self) -> list[Modifier]:
        return self.db.query(Modifier).order_by(Modifier.sort_order, Modifier.id).all()

    # START_CONTRACT: MenuAdminService.set_modifier_availability
    #   PURPOSE: Toggle stop-list flag on a modifier (INV-006).
    #   INPUTS:  modifier_id: int, available: bool
    #   OUTPUTS: Modifier (refreshed)
    #   SIDE_EFFECTS: DB UPDATE + commit; missing → 404.
    #   LINKS:   PDD §5.3, INV-006
    # END_CONTRACT: MenuAdminService.set_modifier_availability
    def set_modifier_availability(self, modifier_id: int, available: bool) -> Modifier:
        mod = self.db.get(Modifier, modifier_id)
        if mod is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="modifier not found")
        mod.available = available
        self.db.commit()
        self.db.refresh(mod)
        return mod

    # ─────────────────────────────────────────────
    # Size options
    # ─────────────────────────────────────────────

    # START_CONTRACT: MenuAdminService.create_size
    #   PURPOSE: INSERT a SizeOption tied to a menu item.
    #   INPUTS:  data: SizeOptionCreate
    #   OUTPUTS: SizeOption (refreshed)
    #   SIDE_EFFECTS: DB INSERT + commit; missing menu item → 404; duplicate label → 409.
    # END_CONTRACT: MenuAdminService.create_size
    def create_size(self, data: SizeOptionCreate) -> SizeOption:
        if self.db.get(MenuItem, data.menu_item_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="item not found")
        size = SizeOption(**data.model_dump())
        self.db.add(size)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            _handle_integrity(exc, "duplicate size label")
        self.db.refresh(size)
        return size

    # START_CONTRACT: MenuAdminService.update_size
    #   PURPOSE: PATCH a SizeOption row.
    #   INPUTS:  size_id: int, data: SizeOptionUpdate
    #   OUTPUTS: SizeOption (refreshed)
    #   SIDE_EFFECTS: DB UPDATE + commit; missing → 404.
    # END_CONTRACT: MenuAdminService.update_size
    def update_size(self, size_id: int, data: SizeOptionUpdate) -> SizeOption:
        size = self.db.get(SizeOption, size_id)
        if size is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="size not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(size, field, value)
        self.db.commit()
        self.db.refresh(size)
        return size

    # START_CONTRACT: MenuAdminService.delete_size
    #   PURPOSE: DELETE a SizeOption row.
    #   INPUTS:  size_id: int
    #   OUTPUTS: None
    #   SIDE_EFFECTS: DB DELETE + commit; missing → 404; integrity → 409.
    # END_CONTRACT: MenuAdminService.delete_size
    def delete_size(self, size_id: int) -> None:
        size = self.db.get(SizeOption, size_id)
        if size is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="size not found")
        self.db.delete(size)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            _handle_integrity(exc, "integrity error")
