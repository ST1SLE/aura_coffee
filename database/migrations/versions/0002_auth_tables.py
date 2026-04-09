"""Auth tables: users, user_profiles, loyalty_accounts.

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-09

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

user_status_enum = sa.Enum(
    "pending_verification", "active", "blocked", "deleted", name="user_status"
)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("phone_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("status", user_status_enum, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_phone_hash", "users", ["phone_hash"])

    op.create_table(
        "user_profiles",
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            primary_key=True,
        ),
        sa.Column("phone", sa.LargeBinary, nullable=False),
        sa.Column("display_name", sa.String(100), nullable=True),
        sa.Column("preferred_language", sa.String(2), nullable=False, server_default="ru"),
    )

    op.create_table(
        "loyalty_accounts",
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            primary_key=True,
        ),
        sa.Column("balance", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("loyalty_accounts")
    op.drop_table("user_profiles")
    op.drop_index("ix_users_phone_hash", table_name="users")
    op.drop_table("users")
    user_status_enum.drop(op.get_bind(), checkfirst=True)
