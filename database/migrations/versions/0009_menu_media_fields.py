"""Add presentational media fields to menu_items.

Revision ID: 0009
Revises: 0008
Create Date: 2026-04-30

Additive nullable schema change for menu presentation media. These fields do
not participate in pricing, order snapshots, payment, loyalty, or state
transitions.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

menu_media_type_enum = sa.Enum("image", "video", name="menu_media_type")


def upgrade() -> None:
    bind = op.get_bind()
    menu_media_type_enum.create(bind, checkfirst=True)
    op.add_column(
        "menu_items",
        sa.Column("media_type", menu_media_type_enum, nullable=True),
    )
    op.add_column(
        "menu_items",
        sa.Column("media_url", sa.String(500), nullable=True),
    )
    op.add_column(
        "menu_items",
        sa.Column("media_poster_url", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("menu_items", "media_poster_url")
    op.drop_column("menu_items", "media_url")
    op.drop_column("menu_items", "media_type")
    menu_media_type_enum.drop(op.get_bind(), checkfirst=True)
