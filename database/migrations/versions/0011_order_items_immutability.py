"""Enforce order_items immutability at the database layer.

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-02

INV-014 forbids UPDATE and DELETE on order_items. This migration removes the
orders -> order_items physical-delete cascade and installs PostgreSQL triggers
that reject direct row mutation.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FK_NAME = "order_items_order_id_fkey"


def upgrade() -> None:
    op.drop_constraint(_FK_NAME, "order_items", type_="foreignkey")
    op.create_foreign_key(
        _FK_NAME,
        "order_items",
        "orders",
        ["order_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_order_items_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'order_items are immutable (INV-014)'
                USING ERRCODE = 'check_violation';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_order_items_immutable_update
        BEFORE UPDATE ON order_items
        FOR EACH ROW
        EXECUTE FUNCTION prevent_order_items_mutation();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_order_items_immutable_delete
        BEFORE DELETE ON order_items
        FOR EACH ROW
        EXECUTE FUNCTION prevent_order_items_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_order_items_immutable_delete ON order_items")
    op.execute("DROP TRIGGER IF EXISTS trg_order_items_immutable_update ON order_items")
    op.execute("DROP FUNCTION IF EXISTS prevent_order_items_mutation()")

    op.drop_constraint(_FK_NAME, "order_items", type_="foreignkey")
    op.create_foreign_key(
        _FK_NAME,
        "order_items",
        "orders",
        ["order_id"],
        ["id"],
        ondelete="CASCADE",
    )
