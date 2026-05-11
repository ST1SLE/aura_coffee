"""Add operator-controlled ordering pause flag.

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-10

The flag lets staff keep menu browsing available while blocking checkout/order
creation during maintenance, provider outages, or owner-directed pauses.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "shop_settings",
        sa.Column(
            "ordering_paused",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("shop_settings", "ordering_paused")
