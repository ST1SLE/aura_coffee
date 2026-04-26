# START_MODULE_CONTRACT
#   PURPOSE: Repeat-order chain: replay an historical order back into the cart
#            applying current pricing and stop-list filters per PDD §7.7.
#            Skips deleted/archived/stop-listed items and unavailable sizes,
#            drops unavailable modifiers; pure cart writes via CartService.
#   SCOPE:   repeat_order entry-point + helper-only private utilities.
#   DEPENDS: M-SHARED (Order, MenuItem, Modifier, SizeOption), M-DATABASE,
#            services.cart, schemas.cart, schemas.order_history
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §7.7, INV-006, INV-013, INV-014
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   OrderNotFoundError    - missing/foreign order id (INV-013, → 404)
#   NoItemsAvailableError - 0 survivors after filtering (→ 422)
#   repeat_order          - main repeat-to-cart orchestration
# END_MODULE_MAP
"""Сервис repeat_order — повтор исторического заказа в корзину (PDD §7.7).

Алгоритм Repeat Order Chain:
- ownership → OrderNotFoundError (router → 404, без утечки существования).
- per-item: deleted / archived / stop-list → entire skip; size unavailable → entire skip;
  modifier unavailable → drop-only + уведомление.
- survivors → CartService.add_item с текущими ценами из БД (INV-006, INV-014).
- added_to_cart == 0 → NoItemsAvailableError (router → 422).
"""
from __future__ import annotations

import uuid
from typing import Any

import redis as redis_lib
from sqlalchemy.orm import Session, selectinload

from core_api.schemas.cart import CartItemCreate
from core_api.schemas.order_history import RepeatOrderResult, RepeatOrderSkippedEntry
from core_api.services.cart import CartService
from core_api.settings import settings
from shared.models.menu import MenuItem, Modifier, SizeOption
from shared.models.order import Order


# START_CONTRACT: OrderNotFoundError
#   PURPOSE: Raised when the order id is missing or belongs to another user
#            (no leak: same shape as missing). Router → HTTP 404.
#   INPUTS:  message: str
#   OUTPUTS: Exception instance.
#   SIDE_EFFECTS: none
#   LINKS:   INV-013
# END_CONTRACT: OrderNotFoundError
class OrderNotFoundError(Exception):
    """Заказ не найден или принадлежит другому пользователю (→ HTTP 404)."""


# START_CONTRACT: NoItemsAvailableError
#   PURPOSE: Raised when none of the items survived availability filtering.
#            Router → HTTP 422.
#   INPUTS:  message: str
#   OUTPUTS: Exception instance.
#   SIDE_EFFECTS: none
# END_CONTRACT: NoItemsAvailableError
class NoItemsAvailableError(Exception):
    """Ни одна позиция не прошла проверку доступности (→ HTTP 422)."""


_ALL_UNAVAILABLE_MSG = "Ни одна позиция из этого заказа сейчас недоступна"


def _modifier_id_from_snapshot_entry(entry: Any) -> int:
    """modifiers_snapshot хранится как JSONB — допускаем dict с 'id' или bare int."""
    if isinstance(entry, dict):
        return int(entry["id"])
    return int(entry)


# START_CONTRACT: repeat_order
#   PURPOSE: Replay items from a historical order into the user's cart, using
#            current DB prices and availability — fully server-trusted (INV-014).
#            Reports skipped items by reason for client UX.
#   INPUTS:  order_id: UUID
#            user_id: UUID
#            redis: redis_lib.Redis — cart backend
#            db_session: Session
#   OUTPUTS: RepeatOrderResult — added_to_cart count + skipped breakdown.
#   SIDE_EFFECTS: DB SELECTs; Redis writes via CartService.add_item per survivor;
#                 raises OrderNotFoundError (foreign/missing) and
#                 NoItemsAvailableError (zero survivors).
#   LINKS:   PDD §7.7, INV-006, INV-013, INV-014
# END_CONTRACT: repeat_order
def repeat_order(
    *,
    order_id: uuid.UUID,
    user_id: uuid.UUID,
    redis: redis_lib.Redis,
    db_session: Session,
) -> RepeatOrderResult:
    order = db_session.execute(
        _select_order_with_items(order_id)
    ).scalar_one_or_none()

    if order is None or order.user_id != user_id:
        raise OrderNotFoundError("order_not_found")

    cart_service = CartService(
        session=db_session,
        redis_client=redis,
        user_id=user_id,
        ttl_seconds=settings.cart_ttl_seconds,
    )

    skipped: list[RepeatOrderSkippedEntry] = []
    survivors: list[CartItemCreate] = []

    for oi in order.items:
        if oi.menu_item_id is None:
            skipped.append(RepeatOrderSkippedEntry(
                reason="menu_item_deleted",
                message_ru="Позиция больше не в меню",
            ))
            continue

        menu_item = db_session.get(MenuItem, oi.menu_item_id)
        if menu_item is None:
            skipped.append(RepeatOrderSkippedEntry(
                reason="menu_item_deleted",
                message_ru="Позиция больше не в меню",
            ))
            continue

        if menu_item.archived:
            skipped.append(RepeatOrderSkippedEntry(
                reason="menu_item_archived",
                message_ru=f"{menu_item.name_ru} больше не в меню",
            ))
            continue

        if not menu_item.available:
            skipped.append(RepeatOrderSkippedEntry(
                reason="menu_item_unavailable",
                message_ru=f"{menu_item.name_ru} сейчас недоступен",
            ))
            continue

        if oi.size_option_id is not None:
            size_option = db_session.get(SizeOption, oi.size_option_id)
            if size_option is None or not size_option.available:
                skipped.append(RepeatOrderSkippedEntry(
                    reason="size_unavailable",
                    message_ru=f"Размер {oi.size_label} для {menu_item.name_ru} недоступен",
                ))
                continue

        surviving_modifier_ids: list[int] = []
        for entry in oi.modifiers_snapshot or []:
            mid = _modifier_id_from_snapshot_entry(entry)
            mod = db_session.get(Modifier, mid)
            if mod is None or not mod.available:
                skipped.append(RepeatOrderSkippedEntry(
                    reason="modifier_unavailable",
                    message_ru=(
                        f"{mod.name_ru} недоступен"
                        if mod is not None
                        else "Модификатор недоступен"
                    ),
                ))
                continue
            surviving_modifier_ids.append(mid)

        survivors.append(CartItemCreate(
            menu_item_id=menu_item.id,
            size_option_id=oi.size_option_id,
            modifier_ids=surviving_modifier_ids,
            quantity=oi.quantity,
        ))

    if not survivors:
        raise NoItemsAvailableError(_ALL_UNAVAILABLE_MSG)

    for item in survivors:
        # Unbound-вызов: тесты патчат CartService.add_item callable-инстансом,
        # который не является дескриптором → self не биндится автоматически.
        CartService.add_item(cart_service, item)

    return RepeatOrderResult(
        added_to_cart=len(survivors),
        skipped=skipped,
    )


def _select_order_with_items(order_id: uuid.UUID):
    from sqlalchemy import select
    return (
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.items))
    )
