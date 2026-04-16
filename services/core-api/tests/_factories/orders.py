"""Фабричные функции для создания тестовых заказов (Order + OrderItem) в БД.

Используются в тестах order-history и order-repeat. Фабрика умеет создавать
заказы, привязанные к текущим MenuItem/SizeOption/Modifier, И заказы, ссылки
которых (menu_item_id, size_option_id) указывают на отсутствующие/архивные/
стоп-листовые записи — чтобы тестировать Repeat Order Chain (PDD §7.7).

Все ID возвращаются в dataclass'ах, чтобы тесты могли потом подставлять
их в проверяемые функции без повторных запросов.
"""
from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from shared.enums import OrderStatus, OrderType, SizeLabel, UserStatus
from shared.models.menu import Category, MenuItem, Modifier, SizeOption
from shared.models.order import Order
from shared.models.order_item import OrderItem
from shared.models.user import User

from tests._factories.menu import make_category, make_menu_item, make_modifier, make_size_option


@dataclass
class HistoryItemSpec:
    """Описание одной позиции исторического заказа для seed_history_order."""

    # Текущий MenuItem — если None, order_item будет указывать на несуществующий id.
    menu_item: MenuItem | None = None
    # snapshot-имена — обычно копируются из menu_item, но можно переопределить
    menu_item_name_ru: str | None = None
    menu_item_name_en: str | None = None
    # Размер (опционально). Если size_option=None, size_option_id в order_item будет NULL.
    size_option: SizeOption | None = None
    size_label: SizeLabel | None = None
    # Модификаторы, которые ПОПАЛИ В СНИМОК заказа. Список объектов Modifier
    # либо raw id (int) для тестов "модификатор удалён".
    modifiers_snapshot_ids: list[int] = field(default_factory=list)
    unit_price: int = 15000
    quantity: int = 1
    # Для случая "позиция больше не в меню": фиктивный id, которого нет в БД.
    stale_menu_item_id: int | None = None


@dataclass
class HistoryOrderSeed:
    """Результат seed_history_order — всё, что нужно тесту."""

    user_id: uuid.UUID
    order_id: uuid.UUID
    order_item_ids: list[uuid.UUID]
    # Специфические для позиции id (для удобства ассертов)
    menu_item_ids: list[int | None]
    size_option_ids: list[int | None]


def make_user(session: Session) -> User:
    """Создаёт минимального User (ACTIVE) для заказа."""
    user = User(
        phone_hash=secrets.token_hex(32),
        status=UserStatus.ACTIVE,
    )
    session.add(user)
    session.flush()
    return user


def seed_history_order(
    session: Session,
    *,
    user: User | None = None,
    items: list[HistoryItemSpec] | None = None,
    created_at: datetime | None = None,
    order_status: OrderStatus = OrderStatus.COMPLETED,
) -> HistoryOrderSeed:
    """Создаёт User (если не передан), Order и OrderItem-ы согласно спецификации.

    Важно: menu_item_id / size_option_id в order_items — это ССЫЛКИ (не FK).
    Чтобы смоделировать "позицию удалили из меню", передайте
    HistoryItemSpec(menu_item=None, stale_menu_item_id=<любой несуществующий int>).
    """
    if user is None:
        user = make_user(session)
    if items is None:
        # По умолчанию — одна доступная позиция
        cat = make_category(session)
        mi = make_menu_item(session, cat, base_price=15000)
        items = [HistoryItemSpec(menu_item=mi, unit_price=15000, quantity=1)]

    subtotal = sum(spec.unit_price * spec.quantity for spec in items)
    order = Order(
        user_id=user.id,
        status=order_status,
        type=OrderType.PICKUP,
        subtotal=subtotal,
        total=subtotal,
        created_at=created_at or datetime.now(tz=UTC),
    )
    session.add(order)
    session.flush()

    order_item_ids: list[uuid.UUID] = []
    menu_item_ids: list[int | None] = []
    size_option_ids: list[int | None] = []

    for spec in items:
        # Разрешение snapshot-полей
        if spec.menu_item is not None:
            name_ru = spec.menu_item_name_ru or spec.menu_item.name_ru
            name_en = spec.menu_item_name_en or spec.menu_item.name_en
            mi_id = spec.menu_item.id
        else:
            name_ru = spec.menu_item_name_ru or "Удалённая позиция"
            name_en = spec.menu_item_name_en or "Removed item"
            mi_id = spec.stale_menu_item_id

        if spec.size_option is not None:
            so_id = spec.size_option.id
            size_label = (spec.size_label or spec.size_option.label).value \
                if hasattr(spec.size_option.label, "value") else str(spec.size_option.label)
        else:
            so_id = None
            size_label = None

        mods_snapshot = []
        for mid in spec.modifiers_snapshot_ids:
            mods_snapshot.append({"id": mid, "name_ru": "", "name_en": "", "price": 0})

        line_total = spec.unit_price * spec.quantity
        oi = OrderItem(
            order_id=order.id,
            menu_item_id=mi_id,
            menu_item_name_ru=name_ru,
            menu_item_name_en=name_en,
            size_option_id=so_id,
            size_label=size_label,
            unit_price=spec.unit_price,
            modifiers_snapshot=mods_snapshot,
            quantity=spec.quantity,
            line_total=line_total,
        )
        session.add(oi)
        session.flush()

        order_item_ids.append(oi.id)
        menu_item_ids.append(mi_id)
        size_option_ids.append(so_id)

    session.commit()

    return HistoryOrderSeed(
        user_id=user.id,
        order_id=order.id,
        order_item_ids=order_item_ids,
        menu_item_ids=menu_item_ids,
        size_option_ids=size_option_ids,
    )


def seed_n_orders_for_user(
    session: Session,
    user: User,
    *,
    count: int,
    base_time: datetime | None = None,
    step: timedelta = timedelta(minutes=1),
) -> list[uuid.UUID]:
    """Создаёт N заказов одного пользователя с монотонно растущим created_at.

    Возвращает order_id в порядке создания (то есть ASC по created_at).
    """
    t0 = base_time or datetime.now(tz=UTC) - step * count
    cat = make_category(session, name_ru=f"cat-{secrets.token_hex(4)}")
    mi = make_menu_item(session, cat, base_price=10000, name_ru=f"mi-{secrets.token_hex(4)}")

    ids: list[uuid.UUID] = []
    for i in range(count):
        order = Order(
            user_id=user.id,
            status=OrderStatus.COMPLETED,
            type=OrderType.PICKUP,
            subtotal=10000,
            total=10000,
            created_at=t0 + step * i,
        )
        session.add(order)
        session.flush()
        oi = OrderItem(
            order_id=order.id,
            menu_item_id=mi.id,
            menu_item_name_ru=mi.name_ru,
            menu_item_name_en=mi.name_en,
            unit_price=10000,
            modifiers_snapshot=[],
            quantity=1,
            line_total=10000,
        )
        session.add(oi)
        session.flush()
        ids.append(order.id)
    session.commit()
    return ids
