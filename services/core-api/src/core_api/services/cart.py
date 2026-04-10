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

        return _ResolvedItem(menu_item=menu_item, size_option=size_option, modifiers=modifiers)

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
                        existing["quantity"] = new_qty
                        merged = True
                        break

                if not merged:
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

    def clear(self) -> CartResponse:
        """Очищает корзину целиком."""
        self._redis.delete(self._key())
        return self.get()
