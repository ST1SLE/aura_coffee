"""Сервисный слой для CRUD меню в админ-панели."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from fastapi import HTTPException, status

from shared.models.menu import Category, MenuItem, Modifier, SizeOption
from core_api.schemas.menu import (
    CategoryCreate,
    CategoryUpdate,
    MenuItemCreate,
    MenuItemUpdate,
    ModifierCreate,
    ModifierUpdate,
    SizeOptionCreate,
    SizeOptionUpdate,
)


def _handle_integrity(exc: IntegrityError, detail: str) -> None:
    """Преобразование IntegrityError в HTTP 409."""
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc


class MenuAdminService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ─────────────────────────────────────────────
    # Categories
    # ─────────────────────────────────────────────

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

    def update_category(self, category_id: int, data: CategoryUpdate) -> Category:
        cat = self.db.get(Category, category_id)
        if cat is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="category not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(cat, field, value)
        self.db.commit()
        self.db.refresh(cat)
        return cat

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

    def list_categories(self) -> list[Category]:
        return self.db.query(Category).order_by(Category.sort_order, Category.id).all()

    # ─────────────────────────────────────────────
    # Menu items
    # ─────────────────────────────────────────────

    def create_item(self, data: MenuItemCreate) -> MenuItem:
        # Проверяем что категория существует
        if self.db.get(Category, data.category_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="category not found")
        item = MenuItem(**data.model_dump())
        self.db.add(item)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            _handle_integrity(exc, "integrity error")
        self.db.refresh(item)
        return item

    def update_item(self, item_id: int, data: MenuItemUpdate) -> MenuItem:
        item = self.db.get(MenuItem, item_id)
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="item not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        self.db.commit()
        self.db.refresh(item)
        return item

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

    def set_item_availability(self, item_id: int, available: bool) -> MenuItem:
        item = self.db.get(MenuItem, item_id)
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="item not found")
        item.available = available
        self.db.commit()
        # Перезагружаем вместе со связями для вычисляемого поля availability
        return self.get_item(item_id)

    # ─────────────────────────────────────────────
    # Modifiers
    # ─────────────────────────────────────────────

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

    def update_modifier(self, modifier_id: int, data: ModifierUpdate) -> Modifier:
        mod = self.db.get(Modifier, modifier_id)
        if mod is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="modifier not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(mod, field, value)
        self.db.commit()
        self.db.refresh(mod)
        return mod

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

    def list_modifiers(self) -> list[Modifier]:
        return self.db.query(Modifier).order_by(Modifier.sort_order, Modifier.id).all()

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

    def update_size(self, size_id: int, data: SizeOptionUpdate) -> SizeOption:
        size = self.db.get(SizeOption, size_id)
        if size is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="size not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(size, field, value)
        self.db.commit()
        self.db.refresh(size)
        return size

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
