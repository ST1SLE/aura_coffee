"""Delivery addresses table: CRUD for saved Customer addresses (PDD §3, §5.2, INV-013).

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-20

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "delivery_addresses",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("address_text", sa.String(500), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("apartment", sa.String(20), nullable=True),
        sa.Column("entrance", sa.String(20), nullable=True),
        sa.Column("floor", sa.String(20), nullable=True),
        sa.Column("comment", sa.String(500), nullable=True),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
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
    op.create_index(
        "ix_delivery_addresses_user_id",
        "delivery_addresses",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_delivery_addresses_user_default",
        "delivery_addresses",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_default = true"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_delivery_addresses_user_default", table_name="delivery_addresses"
    )
    op.drop_index("ix_delivery_addresses_user_id", table_name="delivery_addresses")
    op.drop_table("delivery_addresses")
