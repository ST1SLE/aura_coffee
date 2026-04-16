"""Stop-list validator — PDD §7.2 шаг 1, INV-006.

validate_stop_list(cart_items, db_session) перечитывает MenuItem/SizeOption/Modifier
из БД и возбуждает StopListError на любую недоступную позицию. Возвращает
валидированные позиции с актуальной ценой из БД (клиентский unit_price игнорируется
как источник цены).
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from shared.models.menu import MenuItem, Modifier, SizeOption

from .exceptions import StopListError


def validate_stop_list(
    cart_items: list[dict[str, Any]],
    db_session: Session,
) -> list[dict[str, Any]]:
    """Проверяет каждую позицию корзины и возвращает её с актуальной ценой.

    Формат позиции:
        {"menu_item_id", "size_option_id", "modifier_ids", "quantity", "unit_price"}
    """
    menu_ids = {it["menu_item_id"] for it in cart_items}
    size_ids = {
        it["size_option_id"] for it in cart_items if it.get("size_option_id")
    }
    mod_ids: set[int] = set()
    for it in cart_items:
        mod_ids.update(it.get("modifier_ids") or [])

    menus: dict[int, MenuItem] = {}
    if menu_ids:
        menus = {
            m.id: m
            for m in db_session.query(MenuItem).filter(MenuItem.id.in_(menu_ids)).all()
        }
    sizes: dict[int, SizeOption] = {}
    if size_ids:
        sizes = {
            s.id: s
            for s in db_session.query(SizeOption)
            .filter(SizeOption.id.in_(size_ids))
            .all()
        }
    mods: dict[int, Modifier] = {}
    if mod_ids:
        mods = {
            m.id: m
            for m in db_session.query(Modifier).filter(Modifier.id.in_(mod_ids)).all()
        }

    validated: list[dict[str, Any]] = []
    for it in cart_items:
        mid = it["menu_item_id"]
        menu = menus.get(mid)
        if menu is None or not menu.available:
            raise StopListError(
                f"MenuItem {mid} unavailable",
                item_id=mid,
            )

        size_id = it.get("size_option_id")
        if size_id is not None:
            size = sizes.get(size_id)
            if size is None or not size.available:
                raise StopListError(
                    f"SizeOption {size_id} unavailable",
                    item_id=mid,
                )
            fresh_price = int(size.price)
        else:
            fresh_price = int(menu.base_price)

        for modifier_id in it.get("modifier_ids") or []:
            mod = mods.get(modifier_id)
            if mod is None or not mod.available:
                raise StopListError(
                    f"Modifier {modifier_id} unavailable",
                    item_id=mid,
                )
            fresh_price += int(mod.price)

        validated.append({**it, "unit_price": fresh_price})

    return validated
