"""Menu tables: categories, menu_items, size_options, modifiers, menu_item_modifiers.

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-10

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

category_type_enum = sa.Enum(
    "drink", "food", "merch", "modifier",
    name="category_type",
)

size_label_enum = sa.Enum(
    "S", "M", "L",
    name="size_label",
)


def upgrade() -> None:
    # --- categories ---
    op.create_table(
        "categories",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("type", category_type_enum, nullable=False),
        sa.Column("name_ru", sa.String(120), nullable=False),
        sa.Column("name_en", sa.String(120), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_visible", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # --- menu_items ---
    op.create_table(
        "menu_items",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "category_id",
            sa.BigInteger(),
            sa.ForeignKey("categories.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name_ru", sa.String(200), nullable=False),
        sa.Column("name_en", sa.String(200), nullable=False),
        sa.Column("description_ru", sa.Text(), nullable=True),
        sa.Column("description_en", sa.Text(), nullable=True),
        sa.Column(
            "base_price",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("image_url", sa.String(500), nullable=True),
        sa.Column("available", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("base_price >= 0", name="ck_menu_items_base_price_non_negative"),
    )

    # --- size_options ---
    op.create_table(
        "size_options",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "menu_item_id",
            sa.BigInteger(),
            sa.ForeignKey("menu_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", size_label_enum, nullable=False),
        sa.Column("price", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available", sa.Boolean(), nullable=False, server_default="true"),
        sa.CheckConstraint("price >= 0", name="ck_size_options_price_non_negative"),
        sa.UniqueConstraint("menu_item_id", "label", name="uq_size_options_item_label"),
    )

    # --- modifiers ---
    op.create_table(
        "modifiers",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name_ru", sa.String(120), nullable=False),
        sa.Column("name_en", sa.String(120), nullable=False),
        sa.Column("price", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("price >= 0", name="ck_modifiers_price_non_negative"),
    )

    # --- menu_item_modifiers (M:N junction) ---
    op.create_table(
        "menu_item_modifiers",
        sa.Column(
            "menu_item_id",
            sa.BigInteger(),
            sa.ForeignKey("menu_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "modifier_id",
            sa.BigInteger(),
            sa.ForeignKey("modifiers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("menu_item_id", "modifier_id", name="pk_menu_item_modifiers"),
    )

    # --- Indexes (PDD §5.4) ---
    op.create_index(
        "ix_menu_items_category_sort",
        "menu_items",
        ["category_id", "sort_order"],
    )
    op.create_index(
        "ix_menu_items_active",
        "menu_items",
        ["available", "archived"],
        postgresql_where=sa.text("archived = false"),
    )
    op.create_index(
        "ix_size_options_menu_item",
        "size_options",
        ["menu_item_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_size_options_menu_item", table_name="size_options")
    op.drop_index("ix_menu_items_active", table_name="menu_items")
    op.drop_index("ix_menu_items_category_sort", table_name="menu_items")

    op.drop_table("menu_item_modifiers")
    op.drop_table("modifiers")
    op.drop_table("size_options")
    op.drop_table("menu_items")
    op.drop_table("categories")

    size_label_enum.drop(op.get_bind(), checkfirst=True)
    category_type_enum.drop(op.get_bind(), checkfirst=True)
