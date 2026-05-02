# START_MODULE_CONTRACT
#   PURPOSE: Customer cart service — Redis-backed line-storage with server-side
#            stop-list and finite-inventory validation, server-computed pricing
#            (no client trust), line merge by deterministic line_id,
#            optimistic-concurrency via Redis WATCH/MULTI.
#   SCOPE:   add/update/delete/clear cart; hydrate response with current DB
#            prices and availability flags for each line.
#   DEPENDS: M-SHARED (MenuItem, Modifier, SizeOption, MenuItemAvailability),
#            M-DATABASE, Redis, services.pricing, schemas.cart
#   LINKS:   docs/development-plan.xml M-CORE-API, PDD §5.3, INV-006, INV-014
#   ROLE:    RUNTIME
#   MAP_MODE: EXPORTS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   CartValidationError - reason-tagged validation error (stop-list, ownership)
#   CartService         - Redis-backed cart for one user; CRUD + hydration
# END_MODULE_MAP
"""Сервис корзины: хранение в Redis с TTL, валидация стоп-листа (INV-006),
серверный расчёт цен (INV-014), слияние одинаковых строк (design D5).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import redis
from sqlalchemy.orm import Session

from core_api.schemas.cart import (
    CartItemCreate,
    CartItemResponse,
    CartResponse,
    MenuItemCartSnapshot,
    ModifierSnapshot,
    SizeSnapshot,
)
from core_api.services.pricing import compute_line_total, compute_subtotal
from shared.enums import MenuItemAvailability
from shared.models.menu import MenuItem, Modifier, SizeOption


# START_CONTRACT: CartValidationError
#   PURPOSE: Domain error for cart operations carrying a machine-readable reason
#            ("not_found", "item_stop_list", "modifier_not_linked",
#            "quantity_cap", "inventory_insufficient",
#            "concurrent_modification", etc.).
#   INPUTS:  reason: str
#   OUTPUTS: Exception with .reason attribute.
#   SIDE_EFFECTS: none
#   LINKS:   INV-006 (stop-list), INV-014
# END_CONTRACT: CartValidationError
class CartValidationError(Exception):
    """Ошибка валидации корзины с опциональным reason-маркером."""

    def __init__(self, reason: str = "") -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class _ResolvedItem:
    """Результат валидации и загрузки данных из БД для CartItemCreate."""

    menu_item: MenuItem
    size_option: SizeOption | None
    modifiers: list[Modifier]


# START_CONTRACT: CartService
#   PURPOSE: Redis-backed cart for a single user. Owns: line CRUD, server-side
#            availability validation (stop-list, archived, modifier link,
#            finite inventory), server-side pricing, deterministic line_id
#            merge, TTL refresh.
#   INPUTS:  session: Session — DB for catalog reads
#            redis_client: redis.Redis — backend for cart blob
#            user_id: Any — partition key (str/UUID)
#            ttl_seconds: int — TTL refresh interval
#   OUTPUTS: CartService instance.
#   SIDE_EFFECTS: per method — see individual contracts.
#   LINKS:   PDD §5.3, INV-006, INV-014
# END_CONTRACT: CartService
class CartService:
    """Управляет корзиной покупателя через Redis (key=cart:{user_id})."""

    def __init__(
        self,
        *,
        session: Session,
        redis_client: redis.Redis,
        user_id: Any,
        ttl_seconds: int,
    ) -> None:
        self._session = session
        self._redis = redis_client
        self._user_id = user_id
        self._ttl = ttl_seconds

    # ------------------------------------------------------------------
    # Внутренние хелперы
    # ------------------------------------------------------------------

    def _key(self) -> str:
        return f"cart:{self._user_id}"

    def _load(self) -> dict:
        """Читает корзину из Redis; возвращает пустую структуру если ключа нет."""
        raw = self._redis.get(self._key())
        if raw is None:
            return {"items": [], "updated_at": datetime.now(tz=timezone.utc).isoformat()}
        return json.loads(raw)

    def _save(self, payload: dict) -> None:
        """Сохраняет корзину в Redis с TTL атомарно (SET ... EX)."""
        payload["updated_at"] = datetime.now(tz=timezone.utc).isoformat()
        self._redis.set(self._key(), json.dumps(payload), ex=self._ttl)

    def _validate_and_resolve(self, item: CartItemCreate) -> _ResolvedItem:
        """Загружает и валидирует MenuItem, SizeOption, Modifiers из БД.

        Raises CartValidationError при нарушении INV-006 или связей.
        """
        menu_item = self._session.get(MenuItem, item.menu_item_id)
        if menu_item is None:
            raise CartValidationError("not_found")
        if menu_item.archived:
            raise CartValidationError("item_archived")
        if not menu_item.available:
            raise CartValidationError("item_stop_list")

        size_option: SizeOption | None = None
        if item.size_option_id is not None:
            size_option = self._session.get(SizeOption, item.size_option_id)
            if size_option is None:
                raise CartValidationError("not_found")
            if size_option.menu_item_id != menu_item.id:
                raise CartValidationError("size_wrong_item")
            if not size_option.available:
                raise CartValidationError("size_stop_list")

        modifiers: list[Modifier] = []
        if item.modifier_ids:
            linked_ids = {m.id for m in menu_item.modifiers}
            for mod_id in item.modifier_ids:
                mod = self._session.get(Modifier, mod_id)
                if mod is None:
                    raise CartValidationError("not_found")
                if mod_id not in linked_ids:
                    raise CartValidationError("modifier_not_linked")
                if not mod.available:
                    raise CartValidationError("modifier_stop_list")
                modifiers.append(mod)

        self._ensure_inventory_capacity(menu_item, int(item.quantity))
        return _ResolvedItem(menu_item=menu_item, size_option=size_option, modifiers=modifiers)

    def _ensure_inventory_capacity(
        self, menu_item: MenuItem, requested_quantity: int
    ) -> None:
        """Reject finite-stock requests above the current item inventory."""
        if menu_item.inventory_quantity is None:
            return
        if requested_quantity > menu_item.inventory_quantity:
            raise CartValidationError("inventory_insufficient")

    def _hydrate_line(self, raw: dict) -> CartItemResponse:
        """Строит CartItemResponse из сырых данных Redis, читая цены из БД."""
        menu_item = self._session.get(MenuItem, raw["menu_item_id"])

        if menu_item is None:
            # Товар удалён — возвращаем заглушку с ARCHIVED
            raise ValueError(f"MenuItem {raw['menu_item_id']} не найден в БД")

        if menu_item.archived:
            availability = MenuItemAvailability.ARCHIVED
        elif not menu_item.available:
            availability = MenuItemAvailability.STOP_LIST
        else:
            availability = MenuItemAvailability.AVAILABLE

        menu_item_snapshot = MenuItemCartSnapshot(
            name_ru=menu_item.name_ru,
            name_en=menu_item.name_en,
            availability=availability,
            inventory_quantity=menu_item.inventory_quantity,
        )

        size_option: SizeOption | None = None
        size_snapshot: SizeSnapshot | None = None
        if raw.get("size_option_id") is not None:
            size_option = self._session.get(SizeOption, raw["size_option_id"])
            if size_option is not None:
                size_snapshot = SizeSnapshot(label=size_option.label, price=size_option.price)

        modifier_ids: list[int] = raw.get("modifier_ids", [])
        modifiers_snapshot: list[ModifierSnapshot] = []
        modifier_prices: list[int] = []
        for mod_id in modifier_ids:
            mod = self._session.get(Modifier, mod_id)
            if mod is not None:
                modifiers_snapshot.append(
                    ModifierSnapshot(
                        id=mod.id,
                        name_ru=mod.name_ru,
                        name_en=mod.name_en,
                        price=mod.price,
                    )
                )
                modifier_prices.append(mod.price)

        size_price = size_option.price if size_option is not None else None
        unit_price = compute_line_total(
            base_price=menu_item.base_price,
            size_price=size_price,
            modifier_prices=modifier_prices,
            quantity=1,
        )
        quantity = raw["quantity"]
        line_total = unit_price * quantity

        line_id = CartItemResponse.compute_line_id(
            menu_item_id=raw["menu_item_id"],
            size_option_id=raw.get("size_option_id"),
            modifier_ids=modifier_ids,
        )

        return CartItemResponse(
            line_id=line_id,
            menu_item_id=raw["menu_item_id"],
            size_option_id=raw.get("size_option_id"),
            modifier_ids=modifier_ids,
            quantity=quantity,
            unit_price=unit_price,
            line_total=line_total,
            menu_item_snapshot=menu_item_snapshot,
            size_snapshot=size_snapshot,
            modifiers_snapshot=modifiers_snapshot,
        )

    # ------------------------------------------------------------------
    # Публичные методы
    # ------------------------------------------------------------------

    # START_CONTRACT: CartService.get
    #   PURPOSE: Read current cart, hydrate each line with fresh DB prices and
    #            availability snapshot, refresh TTL on access (design D1).
    #   INPUTS:  none
    #   OUTPUTS: CartResponse — items, subtotal, currency, expires_at.
    #   SIDE_EFFECTS: Redis GET + SET (TTL refresh) + DB SELECTs for catalog.
    # END_CONTRACT: CartService.get
    def get(self) -> CartResponse:
        """Возвращает текущую корзину с ценами из БД. Продлевает TTL."""
        payload = self._load()
        items_raw = payload.get("items", [])

        if not items_raw:
            expires_at = datetime.now(tz=timezone.utc).replace(
                second=0, microsecond=0
            ).replace(
                second=0
            )
            from datetime import timedelta
            expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=self._ttl)
            return CartResponse(
                items=[],
                subtotal=0,
                currency="RUB",
                expires_at=expires_at,
            )

        hydrated = [self._hydrate_line(raw) for raw in items_raw]
        subtotal = compute_subtotal([item.line_total for item in hydrated])

        # Продлеваем TTL при чтении (design D1)
        self._save(payload)

        from datetime import timedelta
        expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=self._ttl)

        return CartResponse(
            items=hydrated,
            subtotal=subtotal,
            currency="RUB",
            expires_at=expires_at,
        )

    # START_CONTRACT: CartService.add_item
    #   PURPOSE: Append a new line or merge into an existing line with the same
    #            line_id (menu_item + size + modifiers). Caps quantity at 99
    #            and finite inventory after merge.
    #   INPUTS:  item: CartItemCreate
    #   OUTPUTS: CartResponse (post-hydrate).
    #   SIDE_EFFECTS: Redis WATCH/MULTI loop (up to 3 retries); DB SELECTs for
    #                 validation. Raises CartValidationError on stop-list,
    #                 quantity cap, inventory_insufficient, or concurrent_modification.
    #   LINKS:   INV-006, INV-014
    # END_CONTRACT: CartService.add_item
    def add_item(self, item: CartItemCreate) -> CartResponse:
        """Добавляет позицию в корзину или увеличивает quantity при совпадении line_id."""
        resolved = self._validate_and_resolve(item)

        new_line_id = CartItemResponse.compute_line_id(
            menu_item_id=item.menu_item_id,
            size_option_id=item.size_option_id,
            modifier_ids=item.modifier_ids,
        )

        _MAX_RETRIES = 3

        for attempt in range(_MAX_RETRIES + 1):
            try:
                pipe = self._redis.pipeline(transaction=True)
                pipe.watch(self._key())

                raw_data = pipe.get(self._key())
                if raw_data is not None:
                    payload = json.loads(raw_data)
                else:
                    payload = {"items": []}

                items = payload.get("items", [])

                # Проверяем слияние
                merged = False
                current_item_qty = sum(
                    int(existing.get("quantity", 0))
                    for existing in items
                    if existing.get("menu_item_id") == resolved.menu_item.id
                )
                for existing in items:
                    existing_line_id = CartItemResponse.compute_line_id(
                        menu_item_id=existing["menu_item_id"],
                        size_option_id=existing.get("size_option_id"),
                        modifier_ids=existing.get("modifier_ids", []),
                    )
                    if existing_line_id == new_line_id:
                        new_qty = existing["quantity"] + item.quantity
                        if new_qty > 99:
                            pipe.reset()
                            raise CartValidationError("quantity_cap")
                        new_item_qty = (
                            current_item_qty
                            - int(existing.get("quantity", 0))
                            + int(new_qty)
                        )
                        try:
                            self._ensure_inventory_capacity(
                                resolved.menu_item, new_item_qty
                            )
                        except CartValidationError:
                            pipe.reset()
                            raise
                        existing["quantity"] = new_qty
                        merged = True
                        break

                if not merged:
                    try:
                        self._ensure_inventory_capacity(
                            resolved.menu_item,
                            current_item_qty + int(item.quantity),
                        )
                    except CartValidationError:
                        pipe.reset()
                        raise
                    items.append({
                        "menu_item_id": item.menu_item_id,
                        "size_option_id": item.size_option_id,
                        "modifier_ids": item.modifier_ids,
                        "quantity": item.quantity,
                    })

                payload["items"] = items
                payload["updated_at"] = datetime.now(tz=timezone.utc).isoformat()

                pipe.multi()
                pipe.set(self._key(), json.dumps(payload), ex=self._ttl)
                pipe.execute()
                break

            except redis.WatchError:
                if attempt == _MAX_RETRIES:
                    raise CartValidationError("concurrent_modification")
                continue

        return self.get()

    # START_CONTRACT: CartService.update_item
    #   PURPOSE: Replace an existing line identified by line_id with new payload,
    #            enforcing finite inventory against the resulting item total.
    #   INPUTS:  line_id: str
    #            item: CartItemCreate (full replacement)
    #   OUTPUTS: CartResponse.
    #   SIDE_EFFECTS: Redis WATCH/MULTI; DB validation; raises
    #                 CartValidationError("not_found"/"inventory_insufficient"/
    #                 "concurrent_modification").
    # END_CONTRACT: CartService.update_item
    def update_item(self, line_id: str, item: CartItemCreate) -> CartResponse:
        """Заменяет строку корзины по line_id новыми данными."""
        resolved = self._validate_and_resolve(item)

        _MAX_RETRIES = 3

        for attempt in range(_MAX_RETRIES + 1):
            try:
                pipe = self._redis.pipeline(transaction=True)
                pipe.watch(self._key())

                raw_data = pipe.get(self._key())
                if raw_data is None:
                    pipe.reset()
                    raise CartValidationError("not_found")

                payload = json.loads(raw_data)
                items = payload.get("items", [])

                new_items = []
                found = False
                for existing in items:
                    existing_line_id = CartItemResponse.compute_line_id(
                        menu_item_id=existing["menu_item_id"],
                        size_option_id=existing.get("size_option_id"),
                        modifier_ids=existing.get("modifier_ids", []),
                    )
                    if existing_line_id == line_id:
                        found = True
                        new_items.append({
                            "menu_item_id": item.menu_item_id,
                            "size_option_id": item.size_option_id,
                            "modifier_ids": item.modifier_ids,
                            "quantity": item.quantity,
                        })
                    else:
                        new_items.append(existing)

                if not found:
                    pipe.reset()
                    raise CartValidationError("not_found")

                target_item_qty = sum(
                    int(existing.get("quantity", 0))
                    for existing in new_items
                    if existing.get("menu_item_id") == resolved.menu_item.id
                )
                try:
                    self._ensure_inventory_capacity(
                        resolved.menu_item, target_item_qty
                    )
                except CartValidationError:
                    pipe.reset()
                    raise

                payload["items"] = new_items
                payload["updated_at"] = datetime.now(tz=timezone.utc).isoformat()

                pipe.multi()
                pipe.set(self._key(), json.dumps(payload), ex=self._ttl)
                pipe.execute()
                break

            except redis.WatchError:
                if attempt == _MAX_RETRIES:
                    raise CartValidationError("concurrent_modification")
                continue

        return self.get()

    # START_CONTRACT: CartService.update_item_quantity
    #   PURPOSE: Quantity-only update for a line; re-validates availability
    #            and finite inventory against the resulting item total.
    #   INPUTS:  line_id: str
    #            new_quantity: int
    #   OUTPUTS: CartResponse.
    #   SIDE_EFFECTS: Redis WATCH/MULTI; DB validation; raises
    #                 CartValidationError on missing line, stop-list, finite
    #                 inventory, race.
    # END_CONTRACT: CartService.update_item_quantity
    def update_item_quantity(self, line_id: str, new_quantity: int) -> CartResponse:
        """Обновляет только количество строки корзины по line_id."""
        _MAX_RETRIES = 3

        for attempt in range(_MAX_RETRIES + 1):
            try:
                pipe = self._redis.pipeline(transaction=True)
                pipe.watch(self._key())

                raw_data = pipe.get(self._key())
                if raw_data is None:
                    pipe.reset()
                    raise CartValidationError("not_found")

                payload = json.loads(raw_data)
                items = payload.get("items", [])

                found = False
                for existing in items:
                    existing_line_id = CartItemResponse.compute_line_id(
                        menu_item_id=existing["menu_item_id"],
                        size_option_id=existing.get("size_option_id"),
                        modifier_ids=existing.get("modifier_ids", []),
                    )
                    if existing_line_id == line_id:
                        found = True
                        # Проверяем доступность товара
                        item_create = CartItemCreate(
                            menu_item_id=existing["menu_item_id"],
                            size_option_id=existing.get("size_option_id"),
                            modifier_ids=existing.get("modifier_ids", []),
                            quantity=new_quantity,
                        )
                        resolved = self._validate_and_resolve(item_create)
                        current_item_qty = sum(
                            int(candidate.get("quantity", 0))
                            for candidate in items
                            if candidate.get("menu_item_id") == resolved.menu_item.id
                        )
                        new_item_qty = (
                            current_item_qty
                            - int(existing.get("quantity", 0))
                            + int(new_quantity)
                        )
                        try:
                            self._ensure_inventory_capacity(
                                resolved.menu_item, new_item_qty
                            )
                        except CartValidationError:
                            pipe.reset()
                            raise
                        existing["quantity"] = new_quantity
                        break

                if not found:
                    pipe.reset()
                    raise CartValidationError("not_found")

                payload["updated_at"] = datetime.now(tz=timezone.utc).isoformat()

                pipe.multi()
                pipe.set(self._key(), json.dumps(payload), ex=self._ttl)
                pipe.execute()
                break

            except redis.WatchError:
                if attempt == _MAX_RETRIES:
                    raise CartValidationError("concurrent_modification")
                continue

        return self.get()

    # START_CONTRACT: CartService.delete_item
    #   PURPOSE: Remove a single line by line_id; deletes the cart key entirely
    #            when the last line is removed.
    #   INPUTS:  line_id: str
    #   OUTPUTS: CartResponse.
    #   SIDE_EFFECTS: Redis WATCH/MULTI (SET or DEL); raises CartValidationError
    #                 on missing line / race.
    # END_CONTRACT: CartService.delete_item
    def delete_item(self, line_id: str) -> CartResponse:
        """Удаляет строку корзины по line_id."""
        _MAX_RETRIES = 3

        for attempt in range(_MAX_RETRIES + 1):
            try:
                pipe = self._redis.pipeline(transaction=True)
                pipe.watch(self._key())

                raw_data = pipe.get(self._key())
                if raw_data is None:
                    pipe.reset()
                    raise CartValidationError("not_found")

                payload = json.loads(raw_data)
                items = payload.get("items", [])

                new_items = [
                    existing for existing in items
                    if CartItemResponse.compute_line_id(
                        menu_item_id=existing["menu_item_id"],
                        size_option_id=existing.get("size_option_id"),
                        modifier_ids=existing.get("modifier_ids", []),
                    ) != line_id
                ]

                if len(new_items) == len(items):
                    pipe.reset()
                    raise CartValidationError("not_found")

                pipe.multi()
                if new_items:
                    payload["items"] = new_items
                    payload["updated_at"] = datetime.now(tz=timezone.utc).isoformat()
                    pipe.set(self._key(), json.dumps(payload), ex=self._ttl)
                else:
                    pipe.delete(self._key())
                pipe.execute()
                break

            except redis.WatchError:
                if attempt == _MAX_RETRIES:
                    raise CartValidationError("concurrent_modification")
                continue

        return self.get()

    # START_CONTRACT: CartService.clear
    #   PURPOSE: Drop the entire cart key (used post-checkout or on user action).
    #   INPUTS:  none
    #   OUTPUTS: CartResponse representing an empty cart.
    #   SIDE_EFFECTS: Redis DEL on `cart:<user_id>`.
    # END_CONTRACT: CartService.clear
    def clear(self) -> CartResponse:
        """Очищает корзину целиком."""
        self._redis.delete(self._key())
        return self.get()
