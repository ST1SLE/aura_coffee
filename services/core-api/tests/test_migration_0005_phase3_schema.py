"""RED: тесты миграции 0005_phase3_schema + сида shop_settings.

Требуют реального PostgreSQL. URL берётся из TEST_DATABASE_URL через conftest;
при fallback на sqlite каждый тест skip-ается.

Все тесты ДОЛЖНЫ падать (AssertionError/IntegrityError/ImportError) до
создания миграции 0005 и сид-скрипта database/seeds/shop_settings.py.
"""

from __future__ import annotations

import os
import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from tests.conftest import _TEST_DB_URL as TEST_DB_URL

ALEMBIC_INI = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "database", "alembic.ini"
)


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


_IS_SQLITE = _is_sqlite(TEST_DB_URL)


# ---------------------------------------------------------------------------
# Фикстуры
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def alembic_cfg(_ensure_test_database) -> Config:
    if _IS_SQLITE:
        pytest.skip("Тесты миграции требуют PostgreSQL")
    cfg = Config(ALEMBIC_INI)
    cfg.set_main_option("sqlalchemy.url", TEST_DB_URL)
    return cfg


@pytest.fixture(scope="module")
def migrated_engine(alembic_cfg: Config):
    """upgrade head; на teardown — downgrade до 0004."""
    engine = create_engine(TEST_DB_URL)
    command.upgrade(alembic_cfg, "head")
    yield engine
    command.downgrade(alembic_cfg, "0004")
    engine.dispose()


# ---------------------------------------------------------------------------
# Хелперы
# ---------------------------------------------------------------------------

def _tables(engine) -> list[str]:
    return inspect(engine).get_table_names()


def _cols(engine, table: str) -> dict[str, dict]:
    return {c["name"]: c for c in inspect(engine).get_columns(table)}


def _fks(engine, table: str) -> list[dict]:
    return inspect(engine).get_foreign_keys(table)


def _uniques(engine, table: str) -> list[dict]:
    return inspect(engine).get_unique_constraints(table)


def _indexes(engine, table: str) -> list[dict]:
    return inspect(engine).get_indexes(table)


def _enum_values(engine, enum_name: str) -> list[str]:
    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT enumlabel FROM pg_enum "
                "JOIN pg_type ON pg_enum.enumtypid = pg_type.oid "
                "WHERE pg_type.typname = :name "
                "ORDER BY enumsortorder"
            ),
            {"name": enum_name},
        )
        return [row[0] for row in result]


# ---------------------------------------------------------------------------
# 8.1 shop_settings — таблица + JSONB
# ---------------------------------------------------------------------------

def test_upgrade_creates_shop_settings_table(migrated_engine) -> None:
    assert "shop_settings" in _tables(migrated_engine)

    cols = _cols(migrated_engine, "shop_settings")
    required = {
        "id",
        "shop_lat",
        "shop_lon",
        "delivery_radius_km",
        "min_delivery_amount",
        "free_delivery_threshold",
        "delivery_fee",
        "loyalty_percent",
        "default_prep_time_minutes",
        "estimated_delivery_time_minutes",
        "working_hours",
        "updated_at",
    }
    assert set(cols) >= required

    # id — целочисленный singleton
    id_type = str(cols["id"]["type"]).upper()
    assert "INT" in id_type, f"id должен быть целочисленным, получено: {id_type}"

    # working_hours — JSONB
    wh_type = str(cols["working_hours"]["type"]).upper()
    assert "JSON" in wh_type, f"working_hours должен быть JSON/JSONB, получено: {wh_type}"


# ---------------------------------------------------------------------------
# 8.2 shop_settings — CHECK id = 1
# ---------------------------------------------------------------------------

def test_shop_settings_check_id_is_1(migrated_engine) -> None:
    with migrated_engine.connect() as conn:
        trans = conn.begin()
        try:
            conn.execute(
                text(
                    """
                    INSERT INTO shop_settings (
                        id, shop_lat, shop_lon, delivery_radius_km,
                        min_delivery_amount, free_delivery_threshold, delivery_fee,
                        loyalty_percent, default_prep_time_minutes,
                        estimated_delivery_time_minutes, working_hours, updated_at
                    ) VALUES (
                        2, 55.7558, 37.6173, 5,
                        50000, 150000, 20000,
                        5, 15, 30,
                        '{}'::jsonb, now()
                    )
                    """
                )
            )
            trans.rollback()
            pytest.fail("CHECK (id = 1) не сработал: вставка с id=2 прошла")
        except Exception:
            trans.rollback()


# ---------------------------------------------------------------------------
# 8.3 orders — таблица, enum-ы, JSONB, TIMESTAMPTZ
# ---------------------------------------------------------------------------

def test_upgrade_creates_orders_table(migrated_engine) -> None:
    assert "orders" in _tables(migrated_engine)

    cols = _cols(migrated_engine, "orders")
    required = {
        "id",
        "user_id",
        "status",
        "type",
        "requested_time",
        "estimated_ready_at",
        "delivery_address_snapshot",
        "subtotal",
        "discount_amount",
        "points_used",
        "delivery_fee",
        "total",
        "estimated_accrual",
        "promocode_id",
        "cancelled_by",
        "cancelled_at",
        "auto_completed",
        "auto_completed_at",
        "created_at",
        "updated_at",
    }
    assert set(cols) >= required

    # enum order_status
    assert _enum_values(migrated_engine, "order_status") == [
        "created",
        "paid",
        "preparing",
        "ready",
        "in_delivery",
        "completed",
        "cancelled",
    ]

    # enum order_type
    assert sorted(_enum_values(migrated_engine, "order_type")) == ["delivery", "pickup"]

    # delivery_address_snapshot — JSONB, nullable
    assert cols["delivery_address_snapshot"]["nullable"] is True
    das_type = str(cols["delivery_address_snapshot"]["type"]).upper()
    assert "JSON" in das_type

    # requested_time, estimated_ready_at — TIMESTAMPTZ, nullable
    for ts_col in ("requested_time", "estimated_ready_at"):
        assert cols[ts_col]["nullable"] is True
        ts_type = str(cols[ts_col]["type"]).upper()
        assert "TIMESTAMP" in ts_type, f"{ts_col} должен быть TIMESTAMPTZ, получено: {ts_type}"


def test_orders_user_fk_behavior(migrated_engine) -> None:
    fks = _fks(migrated_engine, "orders")
    user_fk = next((fk for fk in fks if "users" in fk["referred_table"]), None)
    assert user_fk is not None, "FK orders.user_id → users.id отсутствует"


# ---------------------------------------------------------------------------
# 8.5 order_items
# ---------------------------------------------------------------------------

def test_upgrade_creates_order_items_table(migrated_engine) -> None:
    assert "order_items" in _tables(migrated_engine)

    cols = _cols(migrated_engine, "order_items")
    required = {
        "id",
        "order_id",
        "menu_item_id",
        "menu_item_name_ru",
        "menu_item_name_en",
        "size_option_id",
        "size_label",
        "unit_price",
        "modifiers_snapshot",
        "quantity",
        "line_total",
    }
    assert set(cols) >= required

    mod_type = str(cols["modifiers_snapshot"]["type"]).upper()
    assert "JSON" in mod_type

    # FK order_id → orders ON DELETE RESTRICT (INV-014: no physical cascade)
    fks = _fks(migrated_engine, "order_items")
    order_fk = next((fk for fk in fks if fk["referred_table"] == "orders"), None)
    assert order_fk is not None
    assert order_fk["options"].get("ondelete", "").upper() == "RESTRICT"

    # menu_item_id и size_option_id — НЕ FK
    fk_cols: set[str] = set()
    for fk in fks:
        for col in fk["constrained_columns"]:
            fk_cols.add(col)
    assert "menu_item_id" not in fk_cols, (
        "order_items.menu_item_id НЕ должен быть FK (Repeat Order Chain, INV-014)"
    )
    assert "size_option_id" not in fk_cols, (
        "order_items.size_option_id НЕ должен быть FK (Repeat Order Chain, INV-014)"
    )


def _insert_order_item_snapshot(conn) -> tuple[str, str]:
    user_id = str(uuid.uuid4())
    conn.execute(
        text(
            """
            INSERT INTO users (id, phone_hash, status)
            VALUES (:user_id, :phone_hash, 'active')
            """
        ),
        {"user_id": user_id, "phone_hash": uuid.uuid4().hex},
    )
    order_id = conn.execute(
        text(
            """
            INSERT INTO orders (user_id, type, subtotal, total)
            VALUES (:user_id, 'pickup', 15000, 15000)
            RETURNING id
            """
        ),
        {"user_id": user_id},
    ).scalar_one()
    item_id = conn.execute(
        text(
            """
            INSERT INTO order_items (
                order_id, menu_item_name_ru, menu_item_name_en, unit_price,
                modifiers_snapshot, quantity, line_total
            )
            VALUES (
                :order_id, 'Латте', 'Latte', 15000, '[]'::jsonb, 1, 15000
            )
            RETURNING id
            """
        ),
        {"order_id": order_id},
    ).scalar_one()
    return str(order_id), str(item_id)


def test_order_items_reject_direct_update(migrated_engine) -> None:
    with migrated_engine.connect() as conn:
        trans = conn.begin()
        try:
            _, item_id = _insert_order_item_snapshot(conn)
            with pytest.raises(Exception, match="order_items are immutable"):
                conn.execute(
                    text("UPDATE order_items SET quantity = 2 WHERE id = :item_id"),
                    {"item_id": item_id},
                )
        finally:
            trans.rollback()


def test_order_items_reject_direct_delete(migrated_engine) -> None:
    with migrated_engine.connect() as conn:
        trans = conn.begin()
        try:
            _, item_id = _insert_order_item_snapshot(conn)
            with pytest.raises(Exception, match="order_items are immutable"):
                conn.execute(
                    text("DELETE FROM order_items WHERE id = :item_id"),
                    {"item_id": item_id},
                )
        finally:
            trans.rollback()


def test_orders_do_not_cascade_delete_order_items(migrated_engine) -> None:
    with migrated_engine.connect() as conn:
        trans = conn.begin()
        try:
            order_id, _ = _insert_order_item_snapshot(conn)
            with pytest.raises(Exception):
                conn.execute(
                    text("DELETE FROM orders WHERE id = :order_id"),
                    {"order_id": order_id},
                )
        finally:
            trans.rollback()


# ---------------------------------------------------------------------------
# 8.6 payments — UNIQUE на order_id (1:1)
# ---------------------------------------------------------------------------

def test_upgrade_creates_payments_table_and_order_unique(migrated_engine) -> None:
    assert "payments" in _tables(migrated_engine)

    cols = _cols(migrated_engine, "payments")
    required = {
        "id",
        "order_id",
        "yukassa_payment_id",
        "amount",
        "status",
        "confirmation_url",
        "idempotency_key",
        "created_at",
        "updated_at",
    }
    assert set(cols) >= required

    # UNIQUE на order_id — либо unique constraint, либо unique index
    uniques = _uniques(migrated_engine, "payments")
    idxs = _indexes(migrated_engine, "payments")
    has_unique_constraint = any(
        set(u["column_names"]) == {"order_id"} for u in uniques
    )
    has_unique_index = any(
        idx["unique"] and list(idx["column_names"]) == ["order_id"]
        for idx in idxs
    )
    assert has_unique_constraint or has_unique_index, (
        "payments.order_id должен быть UNIQUE (1:1 payment-order, PDD §5.2)"
    )

    # enum payment_status
    assert set(_enum_values(migrated_engine, "payment_status")) == {
        "pending",
        "awaiting_confirmation",
        "succeeded",
        "payment_failed",
        "refund_pending",
        "refunded",
        "refund_failed",
    }


# ---------------------------------------------------------------------------
# 8.7 refunds
# ---------------------------------------------------------------------------

def test_upgrade_creates_refunds_table(migrated_engine) -> None:
    assert "refunds" in _tables(migrated_engine)

    cols = _cols(migrated_engine, "refunds")
    assert set(cols) >= {
        "id",
        "payment_id",
        "yukassa_refund_id",
        "amount",
        "status",
        "reason",
        "created_at",
    }

    fks = _fks(migrated_engine, "refunds")
    payment_fk = next((fk for fk in fks if fk["referred_table"] == "payments"), None)
    assert payment_fk is not None

    assert set(_enum_values(migrated_engine, "refund_status")) == {
        "pending",
        "succeeded",
        "failed",
    }


# ---------------------------------------------------------------------------
# 8.8 loyalty_transactions
# ---------------------------------------------------------------------------

def test_upgrade_creates_loyalty_transactions_table(migrated_engine) -> None:
    assert "loyalty_transactions" in _tables(migrated_engine)

    cols = _cols(migrated_engine, "loyalty_transactions")
    assert set(cols) >= {
        "id",
        "user_id",
        "order_id",
        "type",
        "amount",
        "balance_after",
        "description",
        "created_at",
    }
    assert cols["order_id"]["nullable"] is True

    assert set(_enum_values(migrated_engine, "loyalty_transaction_type")) == {
        "accrual",
        "redemption",
        "reversal",
        "reservation",
        "admin_adjustment",
    }


# ---------------------------------------------------------------------------
# 8.9 promocodes
# ---------------------------------------------------------------------------

def test_upgrade_creates_promocodes_table(migrated_engine) -> None:
    assert "promocodes" in _tables(migrated_engine)

    cols = _cols(migrated_engine, "promocodes")
    assert set(cols) >= {
        "id",
        "code",
        "discount_type",
        "discount_value",
        "min_order_amount",
        "valid_from",
        "valid_until",
        "max_uses",
        "max_uses_per_user",
        "current_uses",
        "is_active",
        "created_at",
    }

    # UNIQUE на code
    uniques = _uniques(migrated_engine, "promocodes")
    idxs = _indexes(migrated_engine, "promocodes")
    has_unique_code = any(set(u["column_names"]) == {"code"} for u in uniques) or any(
        idx["unique"] and list(idx["column_names"]) == ["code"] for idx in idxs
    )
    assert has_unique_code, "promocodes.code должен быть UNIQUE"

    assert set(_enum_values(migrated_engine, "promocode_discount_type")) == {
        "percent",
        "fixed_amount",
    }


# ---------------------------------------------------------------------------
# 8.10 promocode_usages
# ---------------------------------------------------------------------------

def test_upgrade_creates_promocode_usages_table(migrated_engine) -> None:
    assert "promocode_usages" in _tables(migrated_engine)

    cols = _cols(migrated_engine, "promocode_usages")
    assert set(cols) >= {"id", "promocode_id", "user_id", "order_id", "created_at"}

    fks = _fks(migrated_engine, "promocode_usages")
    referred = {fk["referred_table"] for fk in fks}
    assert {"promocodes", "users", "orders"} <= referred


# ---------------------------------------------------------------------------
# 8.11 notifications
# ---------------------------------------------------------------------------

def test_upgrade_creates_notifications_table(migrated_engine) -> None:
    assert "notifications" in _tables(migrated_engine)

    cols = _cols(migrated_engine, "notifications")
    assert set(cols) >= {
        "id",
        "user_id",
        "order_id",
        "channel",
        "type",
        "message_ru",
        "message_en",
        "status",
        "sent_at",
        "created_at",
    }
    assert cols["order_id"]["nullable"] is True
    assert cols["sent_at"]["nullable"] is True

    assert set(_enum_values(migrated_engine, "notification_channel")) == {"in_app", "sms"}
    assert set(_enum_values(migrated_engine, "notification_type")) == {
        "order_status_change",
        "otp",
    }
    assert set(_enum_values(migrated_engine, "notification_status")) == {
        "pending",
        "sent",
        "failed",
    }


# ---------------------------------------------------------------------------
# 8.12 Индексы (PDD §5.4)
# ---------------------------------------------------------------------------

def test_upgrade_creates_phase3_indexes(migrated_engine) -> None:
    orders_idxs = {idx["name"]: idx for idx in _indexes(migrated_engine, "orders")}

    # orders(user_id, created_at DESC)
    user_created = [
        idx for idx in orders_idxs.values()
        if list(idx["column_names"]) == ["user_id", "created_at"]
    ]
    assert user_created, "Нет индекса orders(user_id, created_at)"

    # Partial orders(status) WHERE status NOT IN (completed, cancelled)
    status_partial = [
        idx for idx in orders_idxs.values()
        if list(idx["column_names"]) == ["status"]
        and (
            "completed" in str(idx.get("dialect_options", {}).get("postgresql_where", "")).lower()
            and "cancelled" in str(idx.get("dialect_options", {}).get("postgresql_where", "")).lower()
        )
    ]
    assert status_partial, (
        "Нет partial-индекса orders(status) WHERE status NOT IN (completed, cancelled)"
    )

    # orders(type, status)
    type_status = [
        idx for idx in orders_idxs.values()
        if list(idx["column_names"]) == ["type", "status"]
    ]
    assert type_status, "Нет индекса orders(type, status)"

    # promocode_usages(promocode_id, user_id)
    pu_idxs = {idx["name"]: idx for idx in _indexes(migrated_engine, "promocode_usages")}
    pu_match = [
        idx for idx in pu_idxs.values()
        if list(idx["column_names"]) == ["promocode_id", "user_id"]
    ]
    assert pu_match, "Нет индекса promocode_usages(promocode_id, user_id)"

    # loyalty_transactions(user_id, created_at)
    lt_idxs = {idx["name"]: idx for idx in _indexes(migrated_engine, "loyalty_transactions")}
    lt_match = [
        idx for idx in lt_idxs.values()
        if list(idx["column_names"]) == ["user_id", "created_at"]
    ]
    assert lt_match, "Нет индекса loyalty_transactions(user_id, created_at)"

    # notifications(user_id, created_at)
    n_idxs = {idx["name"]: idx for idx in _indexes(migrated_engine, "notifications")}
    n_match = [
        idx for idx in n_idxs.values()
        if list(idx["column_names"]) == ["user_id", "created_at"]
    ]
    assert n_match, "Нет индекса notifications(user_id, created_at)"


# ---------------------------------------------------------------------------
# 8.13–8.14 Сид shop_settings
# ---------------------------------------------------------------------------

def test_shop_settings_seed_populates_defaults(migrated_engine) -> None:
    from database.seeds.shop_settings import run

    run(TEST_DB_URL)

    with migrated_engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT id, shop_lat, shop_lon, delivery_radius_km,
                       min_delivery_amount, free_delivery_threshold, delivery_fee,
                       loyalty_percent, default_prep_time_minutes,
                       estimated_delivery_time_minutes, working_hours
                  FROM shop_settings
                """
            )
        ).one()

    assert row.id == 1
    assert float(row.shop_lat) == pytest.approx(55.7558)
    assert float(row.shop_lon) == pytest.approx(37.6173)
    assert float(row.delivery_radius_km) == pytest.approx(5)
    assert row.min_delivery_amount == 50000
    assert row.free_delivery_threshold == 150000
    assert row.delivery_fee == 20000
    assert row.loyalty_percent == 5
    assert row.default_prep_time_minutes == 15
    assert row.estimated_delivery_time_minutes == 30

    wh = row.working_hours
    assert set(wh.keys()) == {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
    for day, slot in wh.items():
        assert slot == {"open": "08:00", "close": "22:00"}, f"{day}: {slot!r}"


def test_shop_settings_seed_is_idempotent(migrated_engine) -> None:
    from database.seeds.shop_settings import run

    run(TEST_DB_URL)
    run(TEST_DB_URL)

    with migrated_engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM shop_settings")).scalar()
    assert count == 1, f"После повторного запуска seed-а должна остаться 1 строка, найдено: {count}"


# ---------------------------------------------------------------------------
# 8.15 downgrade
# ---------------------------------------------------------------------------

def test_downgrade_removes_phase3_tables_and_enums(alembic_cfg: Config) -> None:
    """Отдельный прогон: up → down → проверяем отсутствие Phase 3 таблиц/enum-ов."""
    engine = create_engine(TEST_DB_URL)
    try:
        command.upgrade(alembic_cfg, "head")
        command.downgrade(alembic_cfg, "0004")

        tables = inspect(engine).get_table_names()
        phase3_tables = {
            "shop_settings",
            "orders",
            "order_items",
            "payments",
            "refunds",
            "loyalty_transactions",
            "promocodes",
            "promocode_usages",
            "notifications",
        }
        remaining_tables = phase3_tables & set(tables)
        assert remaining_tables == set(), (
            f"После downgrade остались таблицы Phase 3: {remaining_tables}"
        )

        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT typname FROM pg_type
                     WHERE typname IN (
                        'order_status', 'order_type', 'payment_status',
                        'refund_status', 'notification_channel', 'notification_type',
                        'notification_status', 'loyalty_transaction_type',
                        'promocode_discount_type'
                     )
                       AND typtype = 'e'
                    """
                )
            )
            remaining = [row[0] for row in rows]
        assert remaining == [], f"После downgrade остались enum-ы Phase 3: {remaining}"
    finally:
        engine.dispose()
