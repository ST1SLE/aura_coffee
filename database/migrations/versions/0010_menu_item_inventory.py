"""Add finite inventory tracking to menu_items.

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-02

Additive nullable schema change. NULL means inventory is unlimited/not tracked;
0 means finite stock is out. The existing available flag remains stop-list only.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "menu_items",
        sa.Column("inventory_quantity", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_menu_items_inventory_quantity_non_negative",
        "menu_items",
        "inventory_quantity >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_menu_items_inventory_quantity_non_negative",
        "menu_items",
        type_="check",
    )
    op.drop_column("menu_items", "inventory_quantity")
