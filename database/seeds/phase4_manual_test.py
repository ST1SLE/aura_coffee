"""Фейковые данные для ручного QA Phase 4+ (delivery + full clickthrough).

Идемпотентный сид — повторный запуск не создаёт дубликатов. Наполняет БД
достаточным набором QA-данных для прогона `docs/phase6_manual_test_scenarios.md`
across customer, admin, barista, courier, checkout, loyalty, promocodes, orders,
delivery assignments, refunds, notifications, and menu/media surfaces.

Запуск:
    docker compose exec -T core-api python -m database.seeds.phase4_manual_test

Вставляет / поддерживает:
- shop_settings (PDD §5.2 defaults) — нужен для Haversine-валидации радиуса;
- staff_accounts: courier/courier123, courier2/courier2123, barista/barista123;
- rich QA menu: drinks/food/merch/hidden categories, available/unavailable/
  archived items, sizes, modifiers, and optional media URLs;
- users + profiles + loyalty: active, blocked, and pending QA customers;
- delivery_addresses: default in-radius, secondary in-radius, and out-of-radius;
- promocodes: active percent/fixed, paused, expired, and exhausted states;
- representative order/payment/order_item snapshots across lifecycle states;
- delivery_assignments for delivery handoff and courier available/mine/pickup/
  deliver testing;
- notifications, loyalty transactions, and a refund fixture.

Секреты (bcrypt-хеши, ENCRYPTION_KEY for AES-GCM) — only for dev/test.
"""

# START_MODULE_CONTRACT
#   PURPOSE: Manual-QA fixture seed for Phase 4+ — populates a broad but
#            deterministic test dataset for customer/admin/barista/courier
#            end-to-end clickthroughs.
#   SCOPE:   DEV / TEST ONLY. Not run in production. Idempotent: QA rows are
#            looked up by stable labels/codes/UUIDs before INSERT. Delegates
#            the shop_settings singleton to shop_settings_seed.run().
#   DEPENDS: M-SHARED schemas (staff_accounts, categories, menu_items,
#            modifiers, size_options, users, user_profiles, loyalty_accounts,
#            delivery_addresses, promocodes, orders, order_items, payments,
#            refunds, notifications, delivery_assignments), database.seeds.
#            shop_settings, sqlalchemy, bcrypt, cryptography, stdlib.
#   LINKS:   docs/development-plan.xml M-DATABASE,
#            docs/phase6_manual_test_scenarios.md, PDD §3, §5.2, §6.1-§6.6,
#            INV-002, INV-004, INV-013, INV-014, INV-016.
#   ROLE:    SCRIPT
#   MAP_MODE: LOCALS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   CUSTOMER_PHONE      - dev phone number for the main QA customer
#   CUSTOMER_PHONE_HASH - SHA-256 hex of CUSTOMER_PHONE for users.phone_hash lookup
#   run                 - orchestrates idempotent seed: shop_settings -> staff ->
#                         menu -> customers -> addresses -> promos -> orders.
#   (private helpers are local implementation details.)
# END_MODULE_MAP

from __future__ import annotations

import hashlib
import json
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import create_engine, text

from database.seeds import shop_settings as shop_settings_seed

CUSTOMER_PHONE = "+79991234567"
CUSTOMER_PHONE_HASH = hashlib.sha256(CUSTOMER_PHONE.encode()).hexdigest()
BLOCKED_CUSTOMER_PHONE = "+79990000001"
PENDING_CUSTOMER_PHONE = "+79990000002"

QA_NAMESPACE = uuid.UUID("2e5f0c74-18df-49f5-8f26-9952ce6c55d9")


def _qa_uuid(name: str) -> uuid.UUID:
    return uuid.uuid5(QA_NAMESPACE, name)


def _phone_hash(phone: str) -> str:
    return hashlib.sha256(phone.encode()).hexdigest()


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _encrypt_phone(phone: str, key_hex: str) -> bytes:
    """Тот же AES-256-GCM, что в core_api.utils.crypto: nonce(12) + ciphertext."""
    key = bytes.fromhex(key_hex)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    return nonce + aesgcm.encrypt(nonce, phone.encode(), None)


def _seed_staff(conn) -> dict[str, uuid.UUID]:
    """Seed staff roles needed by all manual panels and return login -> id."""
    result: dict[str, uuid.UUID] = {}
    for login, password, role, display_name in (
        ("courier", "courier123", "courier", "Courier QA"),
        ("courier2", "courier2123", "courier", "Courier QA 2"),
        ("barista", "barista123", "barista", "Barista QA"),
    ):
        conn.execute(
            text(
                """
                INSERT INTO staff_accounts (id, login, password_hash, role, display_name, is_active)
                VALUES (:id, :login, :password_hash, :role, :display_name, true)
                ON CONFLICT (login) DO NOTHING
                """
            ),
            {
                "id": _qa_uuid(f"staff:{login}"),
                "login": login,
                "password_hash": _hash_password(password),
                "role": role,
                "display_name": display_name,
            },
        )
        result[login] = conn.execute(
            text("SELECT id FROM staff_accounts WHERE login = :login"),
            {"login": login},
        ).scalar_one()
    return result


def _category_id(
    conn,
    *,
    type_: str,
    name_ru: str,
    name_en: str,
    sort_order: int,
    is_visible: bool,
) -> int:
    existing = conn.execute(
        text("SELECT id FROM categories WHERE name_en = :name_en"),
        {"name_en": name_en},
    ).first()
    if existing is not None:
        conn.execute(
            text(
                """
                UPDATE categories
                SET type = :type, name_ru = :name_ru, sort_order = :sort_order,
                    is_visible = :is_visible
                WHERE id = :id
                """
            ),
            {
                "id": existing.id,
                "type": type_,
                "name_ru": name_ru,
                "sort_order": sort_order,
                "is_visible": is_visible,
            },
        )
        return int(existing.id)

    return int(
        conn.execute(
            text(
                """
                INSERT INTO categories (type, name_ru, name_en, sort_order, is_visible)
                VALUES (:type, :name_ru, :name_en, :sort_order, :is_visible)
                RETURNING id
                """
            ),
            {
                "type": type_,
                "name_ru": name_ru,
                "name_en": name_en,
                "sort_order": sort_order,
                "is_visible": is_visible,
            },
        ).scalar_one()
    )


def _modifier_id(
    conn,
    *,
    name_ru: str,
    name_en: str,
    price: int,
    available: bool,
    sort_order: int,
) -> int:
    existing = conn.execute(
        text("SELECT id FROM modifiers WHERE name_en = :name_en"),
        {"name_en": name_en},
    ).first()
    if existing is not None:
        conn.execute(
            text(
                """
                UPDATE modifiers
                SET name_ru = :name_ru, price = :price, available = :available,
                    sort_order = :sort_order
                WHERE id = :id
                """
            ),
            {
                "id": existing.id,
                "name_ru": name_ru,
                "price": price,
                "available": available,
                "sort_order": sort_order,
            },
        )
        return int(existing.id)

    return int(
        conn.execute(
            text(
                """
                INSERT INTO modifiers (name_ru, name_en, price, available, sort_order)
                VALUES (:name_ru, :name_en, :price, :available, :sort_order)
                RETURNING id
                """
            ),
            {
                "name_ru": name_ru,
                "name_en": name_en,
                "price": price,
                "available": available,
                "sort_order": sort_order,
            },
        ).scalar_one()
    )


def _menu_item_id(
    conn,
    *,
    category_id: int,
    name_ru: str,
    name_en: str,
    description_ru: str | None,
    description_en: str | None,
    base_price: int,
    available: bool,
    archived: bool,
    sort_order: int,
    image_url: str | None = None,
    media_type: str | None = None,
    media_url: str | None = None,
    media_poster_url: str | None = None,
) -> int:
    existing = conn.execute(
        text("SELECT id FROM menu_items WHERE name_en = :name_en"),
        {"name_en": name_en},
    ).first()
    params = {
        "category_id": category_id,
        "name_ru": name_ru,
        "name_en": name_en,
        "description_ru": description_ru,
        "description_en": description_en,
        "base_price": base_price,
        "available": available,
        "archived": archived,
        "sort_order": sort_order,
        "image_url": image_url,
        "media_type": media_type,
        "media_url": media_url,
        "media_poster_url": media_poster_url,
    }
    if existing is not None:
        conn.execute(
            text(
                """
                UPDATE menu_items
                SET category_id = :category_id, name_ru = :name_ru,
                    description_ru = :description_ru,
                    description_en = :description_en, base_price = :base_price,
                    available = :available, archived = :archived,
                    sort_order = :sort_order, image_url = :image_url,
                    media_type = :media_type, media_url = :media_url,
                    media_poster_url = :media_poster_url
                WHERE id = :id
                """
            ),
            {**params, "id": existing.id},
        )
        return int(existing.id)

    return int(
        conn.execute(
            text(
                """
                INSERT INTO menu_items (
                    category_id, name_ru, name_en, description_ru, description_en,
                    base_price, available, archived, sort_order, image_url,
                    media_type, media_url, media_poster_url
                )
                VALUES (
                    :category_id, :name_ru, :name_en, :description_ru,
                    :description_en, :base_price, :available, :archived,
                    :sort_order, :image_url, :media_type, :media_url,
                    :media_poster_url
                )
                RETURNING id
                """
            ),
            params,
        ).scalar_one()
    )


def _size_id(
    conn,
    *,
    menu_item_id: int,
    label: str,
    price: int,
    available: bool,
) -> int:
    existing = conn.execute(
        text(
            """
            SELECT id FROM size_options
            WHERE menu_item_id = :menu_item_id AND label = :label
            """
        ),
        {"menu_item_id": menu_item_id, "label": label},
    ).first()
    if existing is not None:
        conn.execute(
            text(
                """
                UPDATE size_options
                SET price = :price, available = :available
                WHERE id = :id
                """
            ),
            {"id": existing.id, "price": price, "available": available},
        )
        return int(existing.id)

    return int(
        conn.execute(
            text(
                """
                INSERT INTO size_options (menu_item_id, label, price, available)
                VALUES (:menu_item_id, :label, :price, :available)
                RETURNING id
                """
            ),
            {
                "menu_item_id": menu_item_id,
                "label": label,
                "price": price,
                "available": available,
            },
        ).scalar_one()
    )


def _link_modifier(conn, menu_item_id: int, modifier_id: int) -> None:
    conn.execute(
        text(
            """
            INSERT INTO menu_item_modifiers (menu_item_id, modifier_id)
            VALUES (:menu_item_id, :modifier_id)
            ON CONFLICT DO NOTHING
            """
        ),
        {"menu_item_id": menu_item_id, "modifier_id": modifier_id},
    )


def _seed_menu(conn) -> dict[str, Any]:
    """Seed a menu graph broad enough for public menu, cart, and admin CRUD QA."""
    drinks_id = _category_id(
        conn,
        type_="drink",
        name_ru="Phase4 QA — Напитки",
        name_en="Phase4 QA Drinks",
        sort_order=0,
        is_visible=True,
    )
    food_id = _category_id(
        conn,
        type_="food",
        name_ru="Phase4 QA — Еда",
        name_en="Phase4 QA Food",
        sort_order=10,
        is_visible=True,
    )
    merch_id = _category_id(
        conn,
        type_="merch",
        name_ru="Phase4 QA — Мерч",
        name_en="Phase4 QA Merch",
        sort_order=20,
        is_visible=True,
    )
    hidden_id = _category_id(
        conn,
        type_="drink",
        name_ru="Phase4 QA — Скрытая",
        name_en="Phase4 QA Hidden",
        sort_order=30,
        is_visible=False,
    )

    mods = {
        "oat": _modifier_id(
            conn,
            name_ru="Овсяное молоко (QA)",
            name_en="Oat milk (QA)",
            price=7000,
            available=True,
            sort_order=10,
        ),
        "syrup": _modifier_id(
            conn,
            name_ru="Ванильный сироп (QA)",
            name_en="Vanilla syrup (QA)",
            price=5000,
            available=True,
            sort_order=20,
        ),
        "cinnamon": _modifier_id(
            conn,
            name_ru="Корица (QA)",
            name_en="Cinnamon (QA)",
            price=0,
            available=True,
            sort_order=30,
        ),
        "unavailable": _modifier_id(
            conn,
            name_ru="Недоступный топпинг (QA)",
            name_en="Unavailable topping (QA)",
            price=9000,
            available=False,
            sort_order=40,
        ),
    }

    cappuccino_id = _menu_item_id(
        conn,
        category_id=drinks_id,
        name_ru="Капучино (QA)",
        name_en="Cappuccino (QA)",
        description_ru="Напиток для тестов меню, корзины, медиа и модификаторов.",
        description_en="QA drink for menu, cart, media and modifier testing.",
        base_price=52000,
        available=True,
        archived=False,
        sort_order=0,
        media_type="video",
        media_url="/media/menu/cappuccino-qa/hero.mp4",
        media_poster_url="/media/menu/cappuccino-qa/poster.webp",
    )
    iced_latte_id = _menu_item_id(
        conn,
        category_id=drinks_id,
        name_ru="Айс латте (QA)",
        name_en="Iced latte (QA)",
        description_ru="Холодный напиток для теста второго товара.",
        description_en="Cold drink for second-item testing.",
        base_price=65000,
        available=True,
        archived=False,
        sort_order=10,
        image_url="/media/menu/cappuccino-qa/poster.webp",
    )
    stop_list_id = _menu_item_id(
        conn,
        category_id=drinks_id,
        name_ru="Эспрессо стоп-лист (QA)",
        name_en="Stop-list espresso (QA)",
        description_ru="Недоступный товар для проверки stop-list UX.",
        description_en="Unavailable item for stop-list UX testing.",
        base_price=25000,
        available=False,
        archived=False,
        sort_order=20,
    )
    croissant_id = _menu_item_id(
        conn,
        category_id=food_id,
        name_ru="Круассан (QA)",
        name_en="Croissant (QA)",
        description_ru="Еда для теста food-категории и корзины без размера.",
        description_en="Food item for category and size-less cart testing.",
        base_price=28000,
        available=True,
        archived=False,
        sort_order=0,
    )
    beans_id = _menu_item_id(
        conn,
        category_id=merch_id,
        name_ru="Зёрна 250 г (QA)",
        name_en="Coffee beans 250g (QA)",
        description_ru="Мерч/ритейл для проверки типа категории.",
        description_en="Retail item for category-type testing.",
        base_price=90000,
        available=True,
        archived=False,
        sort_order=0,
    )
    archived_id = _menu_item_id(
        conn,
        category_id=hidden_id,
        name_ru="Архивный чай (QA)",
        name_en="Archived tea (QA)",
        description_ru="Архивный товар для админских проверок.",
        description_en="Archived item for admin checks.",
        base_price=30000,
        available=False,
        archived=True,
        sort_order=0,
    )

    sizes = {
        "cappuccino_s": _size_id(
            conn, menu_item_id=cappuccino_id, label="S", price=52000, available=True
        ),
        "cappuccino_m": _size_id(
            conn, menu_item_id=cappuccino_id, label="M", price=60000, available=True
        ),
        "cappuccino_l": _size_id(
            conn, menu_item_id=cappuccino_id, label="L", price=68000, available=True
        ),
        "latte_m": _size_id(
            conn, menu_item_id=iced_latte_id, label="M", price=65000, available=True
        ),
        "latte_l": _size_id(
            conn, menu_item_id=iced_latte_id, label="L", price=73000, available=True
        ),
    }
    for mod_id in mods.values():
        _link_modifier(conn, cappuccino_id, mod_id)
    _link_modifier(conn, iced_latte_id, mods["oat"])
    _link_modifier(conn, iced_latte_id, mods["syrup"])

    return {
        "categories": {
            "drinks": drinks_id,
            "food": food_id,
            "merch": merch_id,
            "hidden": hidden_id,
        },
        "items": {
            "cappuccino": cappuccino_id,
            "iced_latte": iced_latte_id,
            "stop_list": stop_list_id,
            "croissant": croissant_id,
            "beans": beans_id,
            "archived": archived_id,
        },
        "sizes": sizes,
        "mods": mods,
    }


def _seed_customer(
    conn,
    encryption_key_hex: str,
    *,
    phone: str,
    display_name: str,
    status: str,
    preferred_language: str = "ru",
    minimum_balance: int = 0,
) -> uuid.UUID:
    phone_hash = _phone_hash(phone)
    user_id = conn.execute(
        text(
            """
            INSERT INTO users (id, phone_hash, status, deleted_at)
            VALUES (:id, :phone_hash, :status, NULL)
            ON CONFLICT (phone_hash) DO UPDATE
            SET status = :status, deleted_at = NULL
            RETURNING id
            """
        ),
        {
            "id": _qa_uuid(f"user:{phone}"),
            "phone_hash": phone_hash,
            "status": status,
        },
    ).scalar_one()

    conn.execute(
        text(
            """
            INSERT INTO user_profiles (user_id, phone, display_name, preferred_language)
            VALUES (:user_id, :phone, :display_name, :preferred_language)
            ON CONFLICT (user_id) DO UPDATE
            SET phone = EXCLUDED.phone,
                display_name = EXCLUDED.display_name,
                preferred_language = EXCLUDED.preferred_language
            """
        ),
        {
            "user_id": user_id,
            "phone": _encrypt_phone(phone, encryption_key_hex),
            "display_name": display_name,
            "preferred_language": preferred_language,
        },
    )
    conn.execute(
        text(
            """
            INSERT INTO loyalty_accounts (user_id, balance)
            VALUES (:user_id, :balance)
            ON CONFLICT (user_id) DO UPDATE
            SET balance = GREATEST(loyalty_accounts.balance, EXCLUDED.balance)
            """
        ),
        {"user_id": user_id, "balance": minimum_balance},
    )
    return user_id


def _seed_customers(conn, encryption_key_hex: str) -> dict[str, uuid.UUID]:
    active_id = _seed_customer(
        conn,
        encryption_key_hex,
        phone=CUSTOMER_PHONE,
        display_name="QA Customer",
        status="active",
        minimum_balance=1200,
    )
    blocked_id = _seed_customer(
        conn,
        encryption_key_hex,
        phone=BLOCKED_CUSTOMER_PHONE,
        display_name="QA Blocked Customer",
        status="blocked",
        minimum_balance=0,
    )
    pending_id = _seed_customer(
        conn,
        encryption_key_hex,
        phone=PENDING_CUSTOMER_PHONE,
        display_name="QA Pending Customer",
        status="pending_verification",
        minimum_balance=0,
    )
    return {"active": active_id, "blocked": blocked_id, "pending": pending_id}


def _upsert_address(
    conn,
    *,
    user_id: uuid.UUID,
    label: str,
    address_text: str,
    lat: float,
    lon: float,
    apartment: str | None,
    entrance: str | None,
    floor: str | None,
    comment: str | None,
    is_default: bool,
) -> uuid.UUID:
    existing = conn.execute(
        text(
            """
            SELECT id FROM delivery_addresses
            WHERE user_id = :user_id AND label = :label
            """
        ),
        {"user_id": user_id, "label": label},
    ).first()
    params = {
        "id": _qa_uuid(f"address:{user_id}:{label}"),
        "user_id": user_id,
        "label": label,
        "address_text": address_text,
        "lat": lat,
        "lon": lon,
        "apartment": apartment,
        "entrance": entrance,
        "floor": floor,
        "comment": comment,
        "is_default": is_default,
    }
    if existing is not None:
        conn.execute(
            text(
                """
                UPDATE delivery_addresses
                SET address_text = :address_text, lat = :lat, lon = :lon,
                    apartment = :apartment, entrance = :entrance, floor = :floor,
                    comment = :comment, is_default = :is_default
                WHERE id = :id
                """
            ),
            {**params, "id": existing.id},
        )
        return existing.id

    return conn.execute(
        text(
            """
            INSERT INTO delivery_addresses (
                id, user_id, label, address_text, lat, lon, apartment,
                entrance, floor, comment, is_default
            )
            VALUES (
                :id, :user_id, :label, :address_text, :lat, :lon, :apartment,
                :entrance, :floor, :comment, :is_default
            )
            RETURNING id
            """
        ),
        params,
    ).scalar_one()


def _seed_addresses(conn, user_id: uuid.UUID) -> dict[str, uuid.UUID]:
    """Seed saved-address variants for checkout/profile/delivery validation QA."""
    conn.execute(
        text(
            """
            UPDATE delivery_addresses
            SET is_default = false
            WHERE user_id = :user_id
            """
        ),
        {"user_id": user_id},
    )
    home = _upsert_address(
        conn,
        user_id=user_id,
        label="Дом (QA)",
        address_text="Москва, Красная площадь, 1",
        lat=55.7558,
        lon=37.6173,
        apartment="12",
        entrance="2",
        floor="3",
        comment="домофон 123",
        is_default=True,
    )
    office = _upsert_address(
        conn,
        user_id=user_id,
        label="Офис (QA)",
        address_text="Москва, Тверская улица, 7",
        lat=55.7601,
        lon=37.6101,
        apartment="45",
        entrance=None,
        floor="6",
        comment="оставить на ресепшене",
        is_default=False,
    )
    outside = _upsert_address(
        conn,
        user_id=user_id,
        label="Вне зоны (QA)",
        address_text="Зеленоград, Центральная площадь, 1",
        lat=55.9965,
        lon=37.2148,
        apartment=None,
        entrance=None,
        floor=None,
        comment="адрес вне радиуса для 409-проверки",
        is_default=False,
    )
    return {"home": home, "office": office, "outside": outside}


def _seed_promocodes(conn) -> dict[str, uuid.UUID]:
    now = datetime.now(UTC)
    specs = (
        {
            "key": "qa10",
            "code": "QA10",
            "discount_type": "percent",
            "discount_value": 10,
            "min_order_amount": 0,
            "valid_from": now - timedelta(days=1),
            "valid_until": now + timedelta(days=30),
            "max_uses": 100,
            "max_uses_per_user": 3,
            "current_uses": 0,
            "is_active": True,
        },
        {
            "key": "qa100",
            "code": "QA100",
            "discount_type": "fixed_amount",
            "discount_value": 10000,
            "min_order_amount": 50000,
            "valid_from": now - timedelta(days=1),
            "valid_until": now + timedelta(days=30),
            "max_uses": 100,
            "max_uses_per_user": 1,
            "current_uses": 0,
            "is_active": True,
        },
        {
            "key": "paused",
            "code": "QAPAUSED",
            "discount_type": "percent",
            "discount_value": 15,
            "min_order_amount": 0,
            "valid_from": now - timedelta(days=1),
            "valid_until": now + timedelta(days=30),
            "max_uses": 100,
            "max_uses_per_user": 1,
            "current_uses": 0,
            "is_active": False,
        },
        {
            "key": "expired",
            "code": "QAEXPIRED",
            "discount_type": "percent",
            "discount_value": 20,
            "min_order_amount": 0,
            "valid_from": now - timedelta(days=30),
            "valid_until": now - timedelta(days=1),
            "max_uses": 100,
            "max_uses_per_user": 1,
            "current_uses": 0,
            "is_active": True,
        },
        {
            "key": "exhausted",
            "code": "QAUSED",
            "discount_type": "fixed_amount",
            "discount_value": 5000,
            "min_order_amount": 0,
            "valid_from": now - timedelta(days=1),
            "valid_until": now + timedelta(days=30),
            "max_uses": 1,
            "max_uses_per_user": 1,
            "current_uses": 1,
            "is_active": True,
        },
    )
    result: dict[str, uuid.UUID] = {}
    for spec in specs:
        promo_id = conn.execute(
            text(
                """
                INSERT INTO promocodes (
                    id, code, discount_type, discount_value, min_order_amount,
                    valid_from, valid_until, max_uses, max_uses_per_user,
                    current_uses, is_active
                )
                VALUES (
                    :id, :code, :discount_type, :discount_value,
                    :min_order_amount, :valid_from, :valid_until, :max_uses,
                    :max_uses_per_user, :current_uses, :is_active
                )
                ON CONFLICT (code) DO UPDATE
                SET discount_type = EXCLUDED.discount_type,
                    discount_value = EXCLUDED.discount_value,
                    min_order_amount = EXCLUDED.min_order_amount,
                    valid_from = EXCLUDED.valid_from,
                    valid_until = EXCLUDED.valid_until,
                    max_uses = EXCLUDED.max_uses,
                    max_uses_per_user = EXCLUDED.max_uses_per_user,
                    current_uses = EXCLUDED.current_uses,
                    is_active = EXCLUDED.is_active
                RETURNING id
                """
            ),
            {**spec, "id": _qa_uuid(f"promocode:{spec['code']}")},
        ).scalar_one()
        result[spec["key"]] = promo_id
    return result


def _seed_order(
    conn,
    *,
    key: str,
    user_id: uuid.UUID,
    menu: dict[str, Any],
    status: str,
    type_: str,
    payment_status: str,
    subtotal: int,
    delivery_fee: int,
    total: int,
    created_at: datetime,
    delivery_snapshot: dict[str, Any] | None = None,
    discount_amount: int = 0,
    points_used: int = 0,
    promocode_id: uuid.UUID | None = None,
    cancelled_by: str | None = None,
    cancelled_at: datetime | None = None,
) -> uuid.UUID:
    order_id = _qa_uuid(f"order:{key}")
    conn.execute(
        text(
            """
            INSERT INTO orders (
                id, user_id, status, type, requested_time, estimated_ready_at,
                delivery_address_snapshot, subtotal, discount_amount,
                points_used, delivery_fee, total, estimated_accrual,
                promocode_id, cancelled_by, cancelled_at, created_at, updated_at
            )
            VALUES (
                :id, :user_id, :status, :type, NULL, :estimated_ready_at,
                CAST(:delivery_address_snapshot AS jsonb), :subtotal,
                :discount_amount, :points_used, :delivery_fee, :total,
                :estimated_accrual, :promocode_id, :cancelled_by, :cancelled_at,
                :created_at, :updated_at
            )
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {
            "id": order_id,
            "user_id": user_id,
            "status": status,
            "type": type_,
            "estimated_ready_at": created_at + timedelta(minutes=15),
            "delivery_address_snapshot": (
                json.dumps(delivery_snapshot, ensure_ascii=False)
                if delivery_snapshot is not None
                else None
            ),
            "subtotal": subtotal,
            "discount_amount": discount_amount,
            "points_used": points_used,
            "delivery_fee": delivery_fee,
            "total": total,
            "estimated_accrual": total * 5 // 100,
            "promocode_id": promocode_id,
            "cancelled_by": cancelled_by,
            "cancelled_at": cancelled_at,
            "created_at": created_at,
            "updated_at": created_at,
        },
    )

    item_id = _qa_uuid(f"order-item:{key}:cappuccino")
    modifiers_snapshot = [
        {
            "id": menu["mods"]["oat"],
            "name_ru": "Овсяное молоко (QA)",
            "name_en": "Oat milk (QA)",
            "price": 7000,
        }
    ]
    conn.execute(
        text(
            """
            INSERT INTO order_items (
                id, order_id, menu_item_id, menu_item_name_ru, menu_item_name_en,
                size_option_id, size_label, unit_price, modifiers_snapshot,
                quantity, line_total
            )
            VALUES (
                :id, :order_id, :menu_item_id, 'Капучино (QA)',
                'Cappuccino (QA)', :size_option_id, 'M', 67000,
                CAST(:modifiers_snapshot AS jsonb), 1, 67000
            )
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {
            "id": item_id,
            "order_id": order_id,
            "menu_item_id": menu["items"]["cappuccino"],
            "size_option_id": menu["sizes"]["cappuccino_m"],
            "modifiers_snapshot": json.dumps(modifiers_snapshot, ensure_ascii=False),
        },
    )
    conn.execute(
        text(
            """
            INSERT INTO payments (
                id, order_id, yukassa_payment_id, amount, status,
                confirmation_url, idempotency_key, created_at, updated_at
            )
            VALUES (
                :id, :order_id, :yukassa_payment_id, :amount, :status,
                :confirmation_url, :idempotency_key, :created_at, :updated_at
            )
            ON CONFLICT (order_id) DO NOTHING
            """
        ),
        {
            "id": _qa_uuid(f"payment:{key}"),
            "order_id": order_id,
            "yukassa_payment_id": f"qa-pay-{key}",
            "amount": total,
            "status": payment_status,
            "confirmation_url": (
                f"https://yookassa.example/qa/{key}"
                if payment_status in {"pending", "awaiting_confirmation"}
                else None
            ),
            "idempotency_key": str(_qa_uuid(f"idempotency:{key}")),
            "created_at": created_at,
            "updated_at": created_at,
        },
    )
    conn.execute(
        text(
            """
            INSERT INTO notifications (
                id, user_id, order_id, channel, type, message_ru, message_en,
                status, sent_at, created_at
            )
            VALUES (
                :id, :user_id, :order_id, 'in_app', 'order_status_change',
                :message_ru, :message_en, :status, :sent_at, :created_at
            )
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {
            "id": _qa_uuid(f"notification:{key}"),
            "user_id": user_id,
            "order_id": order_id,
            "message_ru": f"QA заказ: {status}",
            "message_en": f"QA order: {status}",
            "status": "sent",
            "sent_at": created_at,
            "created_at": created_at,
        },
    )
    return order_id


def _seed_assignment(
    conn,
    *,
    key: str,
    order_id: uuid.UUID,
    status: str,
    courier_id: uuid.UUID | None,
    created_at: datetime,
) -> uuid.UUID:
    assignment_id = _qa_uuid(f"assignment:{key}")
    conn.execute(
        text(
            """
            INSERT INTO delivery_assignments (
                id, order_id, courier_id, status, assigned_at, picked_up_at,
                delivered_at, cancelled_at, created_at, updated_at
            )
            VALUES (
                :id, :order_id, :courier_id, :status, :assigned_at,
                :picked_up_at, :delivered_at, NULL, :created_at, :updated_at
            )
            ON CONFLICT (order_id) DO NOTHING
            """
        ),
        {
            "id": assignment_id,
            "order_id": order_id,
            "courier_id": courier_id,
            "status": status,
            "assigned_at": (
                created_at + timedelta(minutes=2)
                if status in {"courier_assigned", "picked_up", "delivered"}
                else None
            ),
            "picked_up_at": (
                created_at + timedelta(minutes=8)
                if status in {"picked_up", "delivered"}
                else None
            ),
            "delivered_at": (
                created_at + timedelta(minutes=25) if status == "delivered" else None
            ),
            "created_at": created_at,
            "updated_at": created_at,
        },
    )
    return assignment_id


def _seed_loyalty_transactions(
    conn,
    *,
    user_id: uuid.UUID,
    completed_order_id: uuid.UUID,
    created_at: datetime,
) -> None:
    rows = (
        {
            "id": _qa_uuid("loyalty:qa-admin-adjustment"),
            "order_id": None,
            "type": "admin_adjustment",
            "amount": 1000,
            "balance_after": 1000,
            "description": "QA opening balance",
            "created_at": created_at - timedelta(days=3),
        },
        {
            "id": _qa_uuid("loyalty:qa-completed-accrual"),
            "order_id": completed_order_id,
            "type": "accrual",
            "amount": 200,
            "balance_after": 1200,
            "description": "QA completed order accrual",
            "created_at": created_at - timedelta(days=2),
        },
    )
    for row in rows:
        conn.execute(
            text(
                """
                INSERT INTO loyalty_transactions (
                    id, user_id, order_id, type, amount, balance_after,
                    description, created_at
                )
                VALUES (
                    :id, :user_id, :order_id, :type, :amount, :balance_after,
                    :description, :created_at
                )
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {**row, "user_id": user_id},
        )


def _seed_refund(conn, *, payment_order_id: uuid.UUID, created_at: datetime) -> None:
    payment_id = conn.execute(
        text("SELECT id FROM payments WHERE order_id = :order_id"),
        {"order_id": payment_order_id},
    ).scalar_one_or_none()
    if payment_id is None:
        return
    conn.execute(
        text(
            """
            INSERT INTO refunds (id, payment_id, yukassa_refund_id, amount, status, reason, created_at)
            VALUES (:id, :payment_id, :yukassa_refund_id, :amount, 'succeeded', :reason, :created_at)
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {
            "id": _qa_uuid("refund:qa-cancelled-delivery"),
            "payment_id": payment_id,
            "yukassa_refund_id": "qa-refund-cancelled-delivery",
            "amount": 87000,
            "reason": "QA cancelled order refund",
            "created_at": created_at,
        },
    )


def _seed_orders(
    conn,
    *,
    user_id: uuid.UUID,
    staff_ids: dict[str, uuid.UUID],
    menu: dict[str, Any],
    addresses: dict[str, uuid.UUID],
    promocodes: dict[str, uuid.UUID],
) -> None:
    now = datetime.now(UTC)
    home_snapshot = {
        "text": "Москва, Красная площадь, 1",
        "lat": 55.7558,
        "lon": 37.6173,
        "apartment": "12",
        "entrance": "2",
        "floor": "3",
        "comment": "домофон 123",
    }
    # Read the address ids once so the variable is intentionally used by the
    # seed: this documents that these orders are tied to seeded saved-address QA.
    _ = addresses["home"]

    order_specs = (
        ("pickup-created", "created", "pickup", "pending", 67000, 0, 67000, None),
        ("pickup-paid", "paid", "pickup", "succeeded", 67000, 0, 67000, None),
        ("pickup-preparing", "preparing", "pickup", "succeeded", 67000, 0, 67000, None),
        ("pickup-ready", "ready", "pickup", "succeeded", 67000, 0, 67000, None),
        ("delivery-paid", "paid", "delivery", "succeeded", 67000, 20000, 87000, home_snapshot),
        ("delivery-preparing", "preparing", "delivery", "succeeded", 67000, 20000, 87000, home_snapshot),
        ("delivery-ready-awaiting", "ready", "delivery", "succeeded", 67000, 20000, 87000, home_snapshot),
        ("delivery-ready-assigned", "ready", "delivery", "succeeded", 67000, 20000, 87000, home_snapshot),
        ("delivery-in-delivery", "in_delivery", "delivery", "succeeded", 67000, 20000, 87000, home_snapshot),
        ("delivery-completed", "completed", "delivery", "succeeded", 67000, 20000, 87000, home_snapshot),
        ("pickup-completed", "completed", "pickup", "succeeded", 67000, 0, 67000, None),
        ("delivery-cancelled", "cancelled", "delivery", "refunded", 67000, 20000, 87000, home_snapshot),
    )
    orders: dict[str, uuid.UUID] = {}
    for index, spec in enumerate(order_specs):
        key, status, type_, payment_status, subtotal, fee, total, snapshot = spec
        orders[key] = _seed_order(
            conn,
            key=key,
            user_id=user_id,
            menu=menu,
            status=status,
            type_=type_,
            payment_status=payment_status,
            subtotal=subtotal,
            delivery_fee=fee,
            total=total,
            created_at=now - timedelta(minutes=240 - index * 10),
            delivery_snapshot=snapshot,
            discount_amount=10000 if key == "pickup-completed" else 0,
            points_used=500 if key == "pickup-completed" else 0,
            promocode_id=promocodes["qa100"] if key == "pickup-completed" else None,
            cancelled_by="admin" if status == "cancelled" else None,
            cancelled_at=(
                now - timedelta(minutes=240 - index * 10 - 5)
                if status == "cancelled"
                else None
            ),
        )

    _seed_assignment(
        conn,
        key="delivery-preparing",
        order_id=orders["delivery-preparing"],
        status="awaiting_courier",
        courier_id=None,
        created_at=now - timedelta(minutes=85),
    )
    _seed_assignment(
        conn,
        key="delivery-ready-awaiting",
        order_id=orders["delivery-ready-awaiting"],
        status="awaiting_courier",
        courier_id=None,
        created_at=now - timedelta(minutes=75),
    )
    _seed_assignment(
        conn,
        key="delivery-ready-assigned",
        order_id=orders["delivery-ready-assigned"],
        status="courier_assigned",
        courier_id=staff_ids["courier"],
        created_at=now - timedelta(minutes=65),
    )
    _seed_assignment(
        conn,
        key="delivery-in-delivery",
        order_id=orders["delivery-in-delivery"],
        status="picked_up",
        courier_id=staff_ids["courier"],
        created_at=now - timedelta(minutes=55),
    )
    _seed_assignment(
        conn,
        key="delivery-completed",
        order_id=orders["delivery-completed"],
        status="delivered",
        courier_id=staff_ids["courier"],
        created_at=now - timedelta(days=1),
    )
    _seed_assignment(
        conn,
        key="delivery-cancelled",
        order_id=orders["delivery-cancelled"],
        status="cancelled",
        courier_id=staff_ids["courier2"],
        created_at=now - timedelta(days=2),
    )
    _seed_loyalty_transactions(
        conn,
        user_id=user_id,
        completed_order_id=orders["pickup-completed"],
        created_at=now,
    )
    _seed_refund(
        conn,
        payment_order_id=orders["delivery-cancelled"],
        created_at=now - timedelta(days=2),
    )


# START_CONTRACT: run
#   PURPOSE: Orchestrate the Phase 4+ manual-QA seed end-to-end. Calls
#            shop_settings_seed.run() first, then seeds staff, rich menu,
#            QA customers, addresses, promocodes, orders, assignments,
#            notifications, loyalty ledger and refund fixtures. Assignments
#            cover PREPARING handoff plus ready/assigned/picked-up/delivered/cancelled.
#   INPUTS:  database_url: str | None — explicit connection URL; falls back to
#            os.environ["DATABASE_URL"] when None. Also reads ENCRYPTION_KEY
#            (hex) for AES-256-GCM phone encryption.
#   OUTPUTS: None
#   SIDE_EFFECTS: Idempotent INSERT/UPSERT into shop_settings (via dedicated
#                 seed), staff_accounts, categories, menu_items, modifiers,
#                 size_options, menu_item_modifiers, users, user_profiles,
#                 loyalty_accounts, delivery_addresses, promocodes, orders,
#                 order_items, payments, delivery_assignments, notifications,
#                 loyalty_transactions and refunds. Raises RuntimeError if
#                 DATABASE_URL or ENCRYPTION_KEY is missing. Engine disposed in
#                 finally. INV-013: phones are AES-GCM encrypted before INSERT.
#                 INV-014: order_items are seeded as immutable snapshots; this
#                 script only inserts missing QA snapshot rows.
#   LINKS:   docs/phase6_manual_test_scenarios.md, PDD §5.2, §6.1-§6.6,
#            INV-002, INV-004, INV-013, INV-014, INV-016.
# END_CONTRACT: run
def run(database_url: str | None = None) -> None:
    url = database_url or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    encryption_key_hex = os.environ.get("ENCRYPTION_KEY")
    if not encryption_key_hex:
        raise RuntimeError("ENCRYPTION_KEY is not set")

    shop_settings_seed.run(url)

    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            staff_ids = _seed_staff(conn)
            menu = _seed_menu(conn)
            customers = _seed_customers(conn, encryption_key_hex)
            addresses = _seed_addresses(conn, customers["active"])
            promocodes = _seed_promocodes(conn)
            _seed_orders(
                conn,
                user_id=customers["active"],
                staff_ids=staff_ids,
                menu=menu,
                addresses=addresses,
                promocodes=promocodes,
            )
    finally:
        engine.dispose()


if __name__ == "__main__":
    run()
    sys.stdout.write("phase4_manual_test seed applied\n")
