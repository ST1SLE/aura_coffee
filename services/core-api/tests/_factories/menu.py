"""Фабричные функции для создания тестовых записей меню в БД.

Используются в тестах корзины (test_cart_service.py, test_route_cart.py).
Каждая функция принимает открытую SQLAlchemy-сессию и сразу делает flush,
чтобы ID были доступны без commit.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from shared.enums import CategoryType, SizeLabel
from shared.models.menu import Category, MenuItem, Modifier, SizeOption


def make_category(session: Session, *, name_ru: str = "Напитки", name_en: str = "Drinks") -> Category:
    """Создаёт и фиксирует категорию."""
    cat = Category(
        type=CategoryType.DRINK,
        name_ru=name_ru,
        name_en=name_en,
        sort_order=0,
        is_visible=True,
    )
    session.add(cat)
    session.flush()
    return cat


def make_modifier(
    session: Session,
    *,
    name_ru: str = "Сироп",
    name_en: str = "Syrup",
    price: int = 5000,
    available: bool = True,
) -> Modifier:
    """Создаёт и фиксирует модификатор."""
    mod = Modifier(
        name_ru=name_ru,
        name_en=name_en,
        price=price,
        available=available,
        sort_order=0,
    )
    session.add(mod)
    session.flush()
    return mod


def make_size_option(
    session: Session,
    menu_item: MenuItem,
    *,
    label: SizeLabel = SizeLabel.M,
    price: int = 20000,
    available: bool = True,
) -> SizeOption:
    """Создаёт SizeOption и привязывает к menu_item."""
    size = SizeOption(
        menu_item_id=menu_item.id,
        label=label,
        price=price,
        available=available,
    )
    session.add(size)
    session.flush()
    return size


def make_menu_item(
    session: Session,
    category: Category | None = None,
    *,
    name_ru: str = "Латте",
    name_en: str = "Latte",
    base_price: int = 15000,
    available: bool = True,
    archived: bool = False,
    sizes: list[dict] | None = None,
    modifiers: list[Modifier] | None = None,
) -> MenuItem:
    """Создаёт MenuItem с опциональными размерами и модификаторами.

    Args:
        session: открытая сессия SQLAlchemy.
        category: категория; создаётся автоматически если None.
        sizes: список kwargs для make_size_option (без menu_item).
        modifiers: уже созданные Modifier объекты; прикрепляются через M:N.
    """
    if category is None:
        category = make_category(session)

    item = MenuItem(
        category_id=category.id,
        name_ru=name_ru,
        name_en=name_en,
        base_price=base_price,
        available=available,
        archived=archived,
        sort_order=0,
    )
    session.add(item)
    session.flush()

    if sizes:
        for size_kwargs in sizes:
            make_size_option(session, item, **size_kwargs)

    if modifiers:
        item.modifiers.extend(modifiers)
        session.flush()

    return item
