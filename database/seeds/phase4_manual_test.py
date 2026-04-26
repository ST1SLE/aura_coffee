"""Фейковые данные для ручного QA Phase 4 (delivery).

Идемпотентный сид — повторный запуск не создаёт дубликатов. Наполняет БД
минимумом, необходимым для прогона `docs/phase4_manual_test_scenarios.md`
end-to-end (checkout, маршруты доставки, курьерская панель, RBAC).

Запуск:
    docker compose exec core-api python -m database.seeds.phase4_manual_test

Вставляет:
- shop_settings (PDD §5.2 defaults) — нужен для Haversine-валидации радиуса;
- staff_accounts: courier/courier123 + barista/barista123 (bcrypt);
- categories + menu_items + size_options — один напиток, чтобы корзина
  могла быть непустой и заказ прошёл checkout;
- users + user_profiles + loyalty_accounts: +79991234567 в статусе ACTIVE;
- delivery_addresses: один default-адрес для этого пользователя, внутри радиуса.

Секреты (bcrypt-хеши, ENCRYPTION_KEY для AES-GCM) — только для dev.
"""

# START_MODULE_CONTRACT
#   PURPOSE: Manual-QA fixture seed for Phase 4 (delivery) — populates the
#            minimum set of rows required to exercise the end-to-end checkout
#            -> courier flow described in docs/phase4_manual_test_scenarios.md.
#   SCOPE:   DEV / TEST ONLY. Not run in production. Idempotent: existence
#            checks before each INSERT so reruns are safe. Delegates the
#            shop_settings singleton to shop_settings_seed.run().
#   DEPENDS: M-SHARED (staff_accounts, categories, menu_items, size_options,
#            users, user_profiles, loyalty_accounts, delivery_addresses,
#            shop_settings schemas), database.seeds.shop_settings,
#            sqlalchemy, bcrypt, cryptography (AES-256-GCM), stdlib.
#   LINKS:   docs/development-plan.xml M-DATABASE,
#            docs/phase4_manual_test_scenarios.md, PDD §3 (shop terminology),
#            PDD §5.2 (table groups), INV-002 (auth), INV-013 (PII / phone
#            encryption + phone_hash), INV-014 (no order_items writes here).
#   ROLE:    SCRIPT
#   MAP_MODE: LOCALS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   CUSTOMER_PHONE      - dev phone number for the QA user (+79991234567)
#   CUSTOMER_PHONE_HASH - SHA-256 hex of CUSTOMER_PHONE for users.phone_hash lookup
#   run                 - orchestrates idempotent seed: shop_settings ->
#                         staff -> menu -> customer -> default address.
#   (private helpers _hash_password / _encrypt_phone / _seed_staff /
#    _seed_menu / _seed_customer / _seed_default_address — see code.)
# END_MODULE_MAP

from __future__ import annotations

import hashlib
import os
import sys
import uuid

import bcrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import create_engine, text

from database.seeds import shop_settings as shop_settings_seed

CUSTOMER_PHONE = "+79991234567"
CUSTOMER_PHONE_HASH = hashlib.sha256(CUSTOMER_PHONE.encode()).hexdigest()


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _encrypt_phone(phone: str, key_hex: str) -> bytes:
    """Тот же AES-256-GCM, что в core_api.utils.crypto — nonce(12) + ciphertext."""
    key = bytes.fromhex(key_hex)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    return nonce + aesgcm.encrypt(nonce, phone.encode(), None)


def _seed_staff(conn) -> None:
    for login, password, role, display_name in (
        ("courier", "courier123", "courier", "Courier"),
        ("barista", "barista123", "barista", "Barista"),
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
                "id": uuid.uuid4(),
                "login": login,
                "password_hash": _hash_password(password),
                "role": role,
                "display_name": display_name,
            },
        )


def _seed_menu(conn) -> None:
    # Идемпотентность: проверяем по уникальному сочетанию category.type + name_en.
    # Если уже есть — ничего не делаем.
    row = conn.execute(
        text("SELECT id FROM categories WHERE name_en = :name_en"),
        {"name_en": "Phase4 QA Drinks"},
    ).first()
    if row is not None:
        return

    category_id = conn.execute(
        text(
            """
            INSERT INTO categories (type, name_ru, name_en, sort_order, is_visible)
            VALUES ('drink', 'Phase4 QA — Напитки', 'Phase4 QA Drinks', 0, true)
            RETURNING id
            """
        )
    ).scalar_one()

    item_id = conn.execute(
        text(
            """
            INSERT INTO menu_items (
                category_id, name_ru, name_en,
                description_ru, description_en, base_price,
                available, archived, sort_order
            )
            VALUES (
                :category_id, 'Капучино (QA)', 'Cappuccino (QA)',
                'Фейковый напиток для ручного тестирования.', 'Fake drink for manual QA.', 60000,
                true, false, 0
            )
            RETURNING id
            """
        ),
        {"category_id": category_id},
    ).scalar_one()

    conn.execute(
        text(
            """
            INSERT INTO size_options (menu_item_id, label, price, available)
            VALUES (:menu_item_id, 'M', 60000, true)
            """
        ),
        {"menu_item_id": item_id},
    )


def _seed_customer(conn, encryption_key_hex: str) -> uuid.UUID:
    existing = conn.execute(
        text("SELECT id FROM users WHERE phone_hash = :ph"),
        {"ph": CUSTOMER_PHONE_HASH},
    ).first()
    if existing is not None:
        return existing.id

    user_id = uuid.uuid4()
    conn.execute(
        text(
            """
            INSERT INTO users (id, phone_hash, status)
            VALUES (:id, :phone_hash, 'active')
            """
        ),
        {"id": user_id, "phone_hash": CUSTOMER_PHONE_HASH},
    )
    conn.execute(
        text(
            """
            INSERT INTO user_profiles (user_id, phone, display_name, preferred_language)
            VALUES (:user_id, :phone, :display_name, 'ru')
            """
        ),
        {
            "user_id": user_id,
            "phone": _encrypt_phone(CUSTOMER_PHONE, encryption_key_hex),
            "display_name": "QA Customer",
        },
    )
    conn.execute(
        text(
            """
            INSERT INTO loyalty_accounts (user_id, balance)
            VALUES (:user_id, 0)
            """
        ),
        {"user_id": user_id},
    )
    return user_id


def _seed_default_address(conn, user_id: uuid.UUID) -> None:
    existing = conn.execute(
        text(
            "SELECT 1 FROM delivery_addresses WHERE user_id = :uid AND label = :lb"
        ),
        {"uid": user_id, "lb": "Дом (QA)"},
    ).first()
    if existing is not None:
        return

    # Координаты центра Москвы — совпадают с shop_lat/shop_lon по умолчанию,
    # чтобы гарантированно попасть внутрь 5-км радиуса.
    conn.execute(
        text(
            """
            INSERT INTO delivery_addresses (
                user_id, label, address_text, lat, lon,
                apartment, entrance, floor, comment, is_default
            )
            VALUES (
                :user_id, 'Дом (QA)', 'Москва, Красная площадь, 1', 55.7558, 37.6173,
                '12', '2', '3', 'домофон 123', true
            )
            """
        ),
        {"user_id": user_id},
    )


# START_CONTRACT: run
#   PURPOSE: Orchestrate the Phase 4 manual-QA seed end-to-end. Calls
#            shop_settings_seed.run() first (so Haversine validation has a
#            singleton row), then idempotently seeds staff, menu, customer,
#            and a default delivery address inside the shop radius.
#   INPUTS:  database_url: str | None — explicit connection URL; falls back to
#            os.environ["DATABASE_URL"] when None. Also reads ENCRYPTION_KEY
#            (hex) for AES-256-GCM phone encryption.
#   OUTPUTS: None
#   SIDE_EFFECTS: idempotent INSERTs into shop_settings (via dedicated seed),
#                 staff_accounts, categories, menu_items, size_options, users,
#                 user_profiles, loyalty_accounts, delivery_addresses. Each
#                 helper guards with an existence check or ON CONFLICT DO
#                 NOTHING. Raises RuntimeError if DATABASE_URL or
#                 ENCRYPTION_KEY is missing. Engine is disposed in finally.
#                 INV-013: phone is AES-GCM encrypted before INSERT.
#                 INV-014: deliberately does NOT insert into order_items.
#   LINKS:   docs/phase4_manual_test_scenarios.md, PDD §5.2,
#            INV-002 (bcrypt staff passwords), INV-013, INV-014.
# END_CONTRACT: run
def run(database_url: str | None = None) -> None:
    url = database_url or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    encryption_key_hex = os.environ.get("ENCRYPTION_KEY")
    if not encryption_key_hex:
        raise RuntimeError("ENCRYPTION_KEY is not set")

    # shop_settings — отдельный сид (тот же апсерт, что и при deploy).
    shop_settings_seed.run(url)

    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            _seed_staff(conn)
            _seed_menu(conn)
            user_id = _seed_customer(conn, encryption_key_hex)
            _seed_default_address(conn, user_id)
    finally:
        engine.dispose()


if __name__ == "__main__":
    run()
    sys.stdout.write("phase4_manual_test seed applied\n")
