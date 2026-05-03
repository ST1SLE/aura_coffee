"""Reset deterministic manual-QA fixture data and re-apply the QA seed.

This is a dev/test utility, not a production data-retention workflow. It avoids
Docker volume deletion while still returning the seeded QA users, menu,
promocodes, orders, payments, assignments, and notifications to a known state.
"""

# START_MODULE_CONTRACT
#   PURPOSE: Guarded local/test reset for deterministic manual-QA fixture rows.
#   SCOPE:   DEV / TEST ONLY. Deletes rows owned by the known Phase 4 QA seed
#            identifiers, then re-runs database.seeds.phase4_manual_test.
#   DEPENDS: database.seeds.phase4_manual_test, SQLAlchemy, environment.
#   LINKS:   docs/phase6_manual_test_scenarios.md,
#            docs/audit-results/2026-05-02-verification-audit.md P2,
#            INV-013, INV-014, INV-016.
#   ROLE:    SCRIPT
#   MAP_MODE: LOCALS
# END_MODULE_CONTRACT
#
# START_MODULE_MAP
#   run - guarded reset and reseed entry point
# END_MODULE_MAP

from __future__ import annotations

import os
import sys
from collections.abc import Iterable, Sequence
from typing import Any

from sqlalchemy import bindparam, create_engine, text

from database.seeds import phase4_manual_test as qa_seed

ALLOWED_ENV_VALUES = {"dev", "development", "local", "test"}
QA_STAFF_LOGINS = ("courier", "courier2", "barista")
QA_CUSTOMER_PHONES = (
    qa_seed.CUSTOMER_PHONE,
    qa_seed.BLOCKED_CUSTOMER_PHONE,
    qa_seed.PENDING_CUSTOMER_PHONE,
)
QA_CUSTOMER_IDS = tuple(
    qa_seed._qa_uuid(f"user:{phone}") for phone in QA_CUSTOMER_PHONES
)
QA_ORDER_KEYS = (
    "pickup-created",
    "pickup-paid",
    "pickup-preparing",
    "pickup-ready",
    "delivery-paid",
    "delivery-preparing",
    "delivery-ready-awaiting",
    "delivery-ready-assigned",
    "delivery-in-delivery",
    "delivery-completed",
    "pickup-completed",
    "delivery-cancelled",
)
QA_ASSIGNMENT_KEYS = (
    "delivery-preparing",
    "delivery-ready-awaiting",
    "delivery-ready-assigned",
    "delivery-in-delivery",
    "delivery-completed",
    "delivery-cancelled",
)
QA_PROMO_CODES = ("QA10", "QA100", "QAPAUSED", "QAEXPIRED", "QAUSED")
QA_CATEGORY_NAMES = (
    "Phase4 QA Drinks",
    "Phase4 QA Food",
    "Phase4 QA Merch",
    "Phase4 QA Hidden",
)
QA_MENU_ITEM_NAMES = (
    "Cappuccino (QA)",
    "Iced latte (QA)",
    "Stop-list espresso (QA)",
    "Croissant (QA)",
    "Coffee beans 250g (QA)",
    "Archived tea (QA)",
)
QA_MODIFIER_NAMES = (
    "Oat milk (QA)",
    "Vanilla syrup (QA)",
    "Cinnamon (QA)",
    "Unavailable topping (QA)",
)
ORDER_ITEMS_IMMUTABLE_DELETE_TRIGGER = "trg_order_items_immutable_delete"


def _guard_environment() -> None:
    env_value = (
        os.environ.get("AURA_ENV") or os.environ.get("APP_ENV") or ""
    ).lower()
    if os.environ.get("ALLOW_QA_RESET") == "1" or env_value in ALLOWED_ENV_VALUES:
        return
    raise RuntimeError(
        "Refusing QA reset outside dev/test/local. Set AURA_ENV=dev|test|local "
        "or ALLOW_QA_RESET=1 for an intentional local reset."
    )


def _as_tuple(values: Iterable[Any]) -> tuple[Any, ...]:
    return tuple(values)


def _select_values(conn, sql: str, param_name: str, values: Sequence[Any]) -> tuple[Any, ...]:
    if not values:
        return ()
    stmt = text(sql).bindparams(bindparam(param_name, expanding=True))
    return _as_tuple(row[0] for row in conn.execute(stmt, {param_name: tuple(values)}))


def _delete_in(
    conn,
    table: str,
    column: str,
    param_name: str,
    values: Sequence[Any],
) -> int:
    if not values:
        return 0
    stmt = text(f"DELETE FROM {table} WHERE {column} IN :{param_name}").bindparams(
        bindparam(param_name, expanding=True)
    )
    result = conn.execute(stmt, {param_name: tuple(values)})
    return int(result.rowcount or 0)


def _delete_where(
    conn,
    sql: str,
    param_name: str,
    values: Sequence[Any],
) -> int:
    if not values:
        return 0
    stmt = text(sql).bindparams(bindparam(param_name, expanding=True))
    result = conn.execute(stmt, {param_name: tuple(values)})
    return int(result.rowcount or 0)


def _trigger_exists(conn, table: str, trigger_name: str) -> bool:
    return bool(
        conn.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_trigger trg
                    JOIN pg_class rel ON rel.oid = trg.tgrelid
                    WHERE rel.relname = :table
                      AND trg.tgname = :trigger_name
                      AND NOT trg.tgisinternal
                )
                """
            ),
            {"table": table, "trigger_name": trigger_name},
        ).scalar_one()
    )


def _delete_qa_order_items(conn, order_ids: Sequence[Any]) -> int:
    if not order_ids:
        return 0

    trigger_exists = _trigger_exists(conn, "order_items", ORDER_ITEMS_IMMUTABLE_DELETE_TRIGGER)
    if trigger_exists:
        conn.execute(
            text(f"ALTER TABLE order_items DISABLE TRIGGER {ORDER_ITEMS_IMMUTABLE_DELETE_TRIGGER}")
        )
    try:
        # QA reset is a guarded dev/test utility; runtime paths still enforce INV-014.
        return _delete_where(
            conn,
            "DELETE FROM order_items WHERE order_id IN :order_ids",
            "order_ids",
            order_ids,
        )
    finally:
        if trigger_exists:
            conn.execute(
                text(f"ALTER TABLE order_items ENABLE TRIGGER {ORDER_ITEMS_IMMUTABLE_DELETE_TRIGGER}")
            )


def _increment(counts: dict[str, int], table: str, count: int) -> None:
    counts[table] = counts.get(table, 0) + count


# START_CONTRACT: run
#   PURPOSE: Delete known manual-QA fixture rows from a guarded local/test DB
#            and re-run the idempotent Phase 4 QA seed.
#   INPUTS:  database_url: str | None — explicit DB URL or DATABASE_URL env.
#   OUTPUTS: dict[str, int] — deleted row counts by table before reseed.
#   SIDE_EFFECTS: DELETEs rows owned by known QA seed identifiers/users,
#                 temporarily disables the order_items delete trigger inside
#                 the guarded reset transaction, then INSERT/UPSERTs the Phase
#                 4 QA seed. Refuses outside dev/test/local unless
#                 ALLOW_QA_RESET=1. Does not drop schemas, databases, or volumes.
#   LINKS:   docs/phase6_manual_test_scenarios.md,
#            docs/audit-results/2026-05-02-verification-audit.md P2,
#            INV-013, INV-014, INV-016.
# END_CONTRACT: run
def run(database_url: str | None = None) -> dict[str, int]:
    _guard_environment()

    url = database_url or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")

    seeded_order_ids = tuple(qa_seed._qa_uuid(f"order:{key}") for key in QA_ORDER_KEYS)
    seeded_payment_ids = tuple(qa_seed._qa_uuid(f"payment:{key}") for key in QA_ORDER_KEYS)
    seeded_refund_ids = (qa_seed._qa_uuid("refund:qa-cancelled-delivery"),)
    seeded_assignment_ids = tuple(
        qa_seed._qa_uuid(f"assignment:{key}") for key in QA_ASSIGNMENT_KEYS
    )
    seeded_notification_ids = tuple(
        qa_seed._qa_uuid(f"notification:{key}") for key in QA_ORDER_KEYS
    )
    seeded_loyalty_tx_ids = (
        qa_seed._qa_uuid("loyalty:qa-admin-adjustment"),
        qa_seed._qa_uuid("loyalty:qa-completed-accrual"),
    )
    qa_phone_hashes = tuple(qa_seed._phone_hash(phone) for phone in QA_CUSTOMER_PHONES)

    engine = create_engine(url)
    counts: dict[str, int] = {}
    try:
        with engine.begin() as conn:
            qa_user_ids = tuple(
                set(
                    _select_values(
                        conn,
                        "SELECT id FROM users WHERE id IN :user_ids",
                        "user_ids",
                        QA_CUSTOMER_IDS,
                    )
                )
                | set(
                    _select_values(
                        conn,
                        "SELECT id FROM users WHERE phone_hash IN :phone_hashes",
                        "phone_hashes",
                        qa_phone_hashes,
                    )
                )
            )
            qa_staff_ids = _select_values(
                conn,
                "SELECT id FROM staff_accounts WHERE login IN :logins",
                "logins",
                QA_STAFF_LOGINS,
            )
            qa_promocode_ids = _select_values(
                conn,
                "SELECT id FROM promocodes WHERE code IN :codes",
                "codes",
                QA_PROMO_CODES,
            )
            qa_order_ids = _select_values(
                conn,
                "SELECT id FROM orders WHERE id IN :seeded_order_ids",
                "seeded_order_ids",
                seeded_order_ids,
            )
            if qa_user_ids:
                qa_order_ids = tuple(
                    set(qa_order_ids)
                    | set(
                        _select_values(
                            conn,
                            "SELECT id FROM orders WHERE user_id IN :qa_user_ids",
                            "qa_user_ids",
                            qa_user_ids,
                        )
                    )
                )
            qa_payment_ids = tuple(
                set(seeded_payment_ids)
                | set(
                    _select_values(
                        conn,
                        "SELECT id FROM payments WHERE order_id IN :order_ids",
                        "order_ids",
                        qa_order_ids,
                    )
                )
            )
            qa_modifier_ids = _select_values(
                conn,
                "SELECT id FROM modifiers WHERE name_en IN :names",
                "names",
                QA_MODIFIER_NAMES,
            )
            qa_category_ids = _select_values(
                conn,
                "SELECT id FROM categories WHERE name_en IN :names",
                "names",
                QA_CATEGORY_NAMES,
            )
            qa_menu_item_ids = _select_values(
                conn,
                "SELECT id FROM menu_items WHERE name_en IN :names",
                "names",
                QA_MENU_ITEM_NAMES,
            )
            if qa_category_ids:
                qa_menu_item_ids = tuple(
                    set(qa_menu_item_ids)
                    | set(
                        _select_values(
                            conn,
                            "SELECT id FROM menu_items WHERE category_id IN :category_ids",
                            "category_ids",
                            qa_category_ids,
                        )
                    )
                )

            _increment(
                counts,
                "promocode_usages",
                _delete_where(
                    conn,
                    "DELETE FROM promocode_usages WHERE order_id IN :order_ids",
                    "order_ids",
                    qa_order_ids,
                ),
            )
            _increment(
                counts,
                "promocode_usages",
                _delete_where(
                    conn,
                    "DELETE FROM promocode_usages WHERE user_id IN :user_ids",
                    "user_ids",
                    qa_user_ids,
                ),
            )
            _increment(
                counts,
                "promocode_usages",
                _delete_where(
                    conn,
                    "DELETE FROM promocode_usages WHERE promocode_id IN :promocode_ids",
                    "promocode_ids",
                    qa_promocode_ids,
                ),
            )
            _increment(
                counts,
                "notifications",
                _delete_where(
                    conn,
                    "DELETE FROM notifications WHERE id IN :notification_ids",
                    "notification_ids",
                    seeded_notification_ids,
                ),
            )
            _increment(
                counts,
                "notifications",
                _delete_where(
                    conn,
                    "DELETE FROM notifications WHERE order_id IN :order_ids",
                    "order_ids",
                    qa_order_ids,
                ),
            )
            _increment(
                counts,
                "notifications",
                _delete_where(
                    conn,
                    "DELETE FROM notifications WHERE user_id IN :user_ids",
                    "user_ids",
                    qa_user_ids,
                ),
            )
            _increment(
                counts,
                "loyalty_transactions",
                _delete_where(
                    conn,
                    "DELETE FROM loyalty_transactions WHERE id IN :loyalty_tx_ids",
                    "loyalty_tx_ids",
                    seeded_loyalty_tx_ids,
                ),
            )
            _increment(
                counts,
                "loyalty_transactions",
                _delete_where(
                    conn,
                    "DELETE FROM loyalty_transactions WHERE order_id IN :order_ids",
                    "order_ids",
                    qa_order_ids,
                ),
            )
            _increment(
                counts,
                "loyalty_transactions",
                _delete_where(
                    conn,
                    "DELETE FROM loyalty_transactions WHERE user_id IN :user_ids",
                    "user_ids",
                    qa_user_ids,
                ),
            )
            _increment(
                counts,
                "refunds",
                _delete_where(
                    conn,
                    "DELETE FROM refunds WHERE id IN :refund_ids",
                    "refund_ids",
                    seeded_refund_ids,
                ),
            )
            _increment(
                counts,
                "refunds",
                _delete_where(
                    conn,
                    "DELETE FROM refunds WHERE payment_id IN :payment_ids",
                    "payment_ids",
                    qa_payment_ids,
                ),
            )
            _increment(
                counts,
                "delivery_assignments",
                _delete_where(
                    conn,
                    "DELETE FROM delivery_assignments WHERE id IN :assignment_ids",
                    "assignment_ids",
                    seeded_assignment_ids,
                ),
            )
            _increment(
                counts,
                "delivery_assignments",
                _delete_where(
                    conn,
                    "DELETE FROM delivery_assignments WHERE order_id IN :order_ids",
                    "order_ids",
                    qa_order_ids,
                ),
            )
            _increment(
                counts,
                "delivery_assignments",
                _delete_where(
                    conn,
                    "DELETE FROM delivery_assignments WHERE courier_id IN :staff_ids",
                    "staff_ids",
                    qa_staff_ids,
                ),
            )
            _increment(
                counts,
                "payments",
                _delete_where(
                    conn,
                    "DELETE FROM payments WHERE id IN :payment_ids",
                    "payment_ids",
                    qa_payment_ids,
                ),
            )
            _increment(
                counts,
                "payments",
                _delete_where(
                    conn,
                    "DELETE FROM payments WHERE order_id IN :order_ids",
                    "order_ids",
                    qa_order_ids,
                ),
            )
            _increment(counts, "order_items", _delete_qa_order_items(conn, qa_order_ids))
            _increment(counts, "orders", _delete_in(conn, "orders", "id", "ids", qa_order_ids))
            _increment(
                counts,
                "delivery_addresses",
                _delete_in(conn, "delivery_addresses", "user_id", "user_ids", qa_user_ids),
            )
            _increment(
                counts,
                "user_profiles",
                _delete_in(conn, "user_profiles", "user_id", "user_ids", qa_user_ids),
            )
            _increment(
                counts,
                "loyalty_accounts",
                _delete_in(conn, "loyalty_accounts", "user_id", "user_ids", qa_user_ids),
            )
            _increment(counts, "users", _delete_in(conn, "users", "id", "ids", qa_user_ids))
            _increment(
                counts,
                "promocodes",
                _delete_in(conn, "promocodes", "id", "ids", qa_promocode_ids),
            )
            _increment(
                counts,
                "staff_accounts",
                _delete_in(conn, "staff_accounts", "id", "ids", qa_staff_ids),
            )
            _increment(
                counts,
                "menu_item_modifiers",
                _delete_where(
                    conn,
                    "DELETE FROM menu_item_modifiers WHERE menu_item_id IN :menu_item_ids",
                    "menu_item_ids",
                    qa_menu_item_ids,
                ),
            )
            _increment(
                counts,
                "menu_item_modifiers",
                _delete_where(
                    conn,
                    "DELETE FROM menu_item_modifiers WHERE modifier_id IN :modifier_ids",
                    "modifier_ids",
                    qa_modifier_ids,
                ),
            )
            _increment(
                counts,
                "size_options",
                _delete_in(conn, "size_options", "menu_item_id", "item_ids", qa_menu_item_ids),
            )
            _increment(
                counts,
                "menu_items",
                _delete_in(conn, "menu_items", "id", "ids", qa_menu_item_ids),
            )
            _increment(
                counts,
                "modifiers",
                _delete_in(conn, "modifiers", "id", "ids", qa_modifier_ids),
            )
            _increment(
                counts,
                "categories",
                _delete_in(conn, "categories", "id", "ids", qa_category_ids),
            )
    finally:
        engine.dispose()

    qa_seed.run(url)
    return counts


if __name__ == "__main__":
    deleted_counts = run()
    summary = ", ".join(
        f"{table}={count}" for table, count in sorted(deleted_counts.items())
    )
    sys.stdout.write(f"reset_qa_data applied; deleted {summary}\n")
