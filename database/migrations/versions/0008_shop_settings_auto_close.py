"""Phase 6: shop_settings.auto_close_minutes (PDD §6.1, §7.1 Phase 6 item 3).

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-20

Additive-миграция: добавляет колонку, параметризующую §6.1 auto-close transition.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "shop_settings",
        sa.Column(
            "auto_close_minutes",
            sa.Integer(),
            nullable=False,
            server_default="60",
        ),
    )


def downgrade() -> None:
    op.drop_column("shop_settings", "auto_close_minutes")
