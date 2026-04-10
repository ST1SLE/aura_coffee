"""Сервис публичного меню — читает и фильтрует данные для клиента."""

import enum

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from core_api.schemas.menu import (
    PublicCategory,
    PublicMenuModifier,
    PublicMenuItem,
    PublicMenuResponse,
    PublicMenuSizeOption,
)
from shared.enums import CategoryType, SizeLabel
from shared.models.menu import Category, MenuItem, Modifier


class Language(str, enum.Enum):
    RU = "ru"
    EN = "en"


# Порядок размеров по enum (S < M < L)
_SIZE_ORDER: dict[SizeLabel, int] = {SizeLabel.S: 0, SizeLabel.M: 1, SizeLabel.L: 2}


def _pick(language: Language, ru: str | None, en: str | None) -> str | None:
    """Выбирает RU или EN строку по языку запроса."""
    return en if language is Language.EN else ru


def _map_modifier(mod: Modifier, language: Language) -> PublicMenuModifier:
    return PublicMenuModifier(
        id=mod.id,
        name=_pick(language, mod.name_ru, mod.name_en),  # type: ignore[arg-type]
        name_ru=mod.name_ru,
        name_en=mod.name_en,
        price=mod.price,
        available=mod.available,
    )


def _map_item(item: MenuItem, language: Language, *, only_available: bool) -> PublicMenuItem:
    sizes = list(item.size_options)
    if only_available:
        sizes = [s for s in sizes if s.available]
    sizes.sort(key=lambda s: _SIZE_ORDER.get(s.label, 99))

    mods = sorted(item.modifiers, key=lambda m: (m.sort_order, m.id))

    return PublicMenuItem(
        id=item.id,
        category_id=item.category_id,
        name=_pick(language, item.name_ru, item.name_en),  # type: ignore[arg-type]
        name_ru=item.name_ru,
        name_en=item.name_en,
        description=_pick(language, item.description_ru, item.description_en),
        description_ru=item.description_ru,
        description_en=item.description_en,
        base_price=item.base_price,
        image_url=item.image_url,
        available=item.available,
        sort_order=item.sort_order,
        size_options=[
            PublicMenuSizeOption(
                id=s.id,
                label=s.label,
                price=s.price,
                available=s.available,
            )
            for s in sizes
        ],
        modifiers=[_map_modifier(m, language) for m in mods],
    )


def _map_category(
    cat: Category, language: Language, *, only_available: bool
) -> PublicCategory:
    items = [item for item in cat.menu_items if not item.archived]
    if only_available:
        items = [item for item in items if item.available]
    items.sort(key=lambda i: (i.sort_order, i.id))

    return PublicCategory(
        id=cat.id,
        type=cat.type,
        name=_pick(language, cat.name_ru, cat.name_en),  # type: ignore[arg-type]
        name_ru=cat.name_ru,
        name_en=cat.name_en,
        sort_order=cat.sort_order,
        items=[_map_item(i, language, only_available=only_available) for i in items],
    )


def get_public_menu(
    db: Session,
    *,
    only_available: bool,
    language: Language,
) -> PublicMenuResponse:
    """Возвращает активное меню, сгруппированное по категориям.

    Правила видимости:
    - archived=True позиции никогда не попадают в ответ
    - is_visible=False категории скрыты
    - type=modifier категории скрыты (модификаторы встроены в позиции)
    - При only_available=True дополнительно скрываются стоп-листовые позиции и размеры
    """
    stmt = (
        select(Category)
        .where(
            Category.is_visible.is_(True),
            Category.type != CategoryType.MODIFIER,
        )
        .order_by(Category.sort_order, Category.id)
        .options(
            selectinload(Category.menu_items).options(
                selectinload(MenuItem.size_options),
                selectinload(MenuItem.modifiers),
            )
        )
    )
    categories = db.execute(stmt).scalars().all()

    return PublicMenuResponse(
        categories=[
            _map_category(cat, language, only_available=only_available)
            for cat in categories
        ]
    )
