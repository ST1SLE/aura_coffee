"""Staff accounts table.

Schema-only migration. Initial admin seeding lives in
``database/seeds/initial_admin.py`` and must be run separately.

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-09

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

staff_role_enum = sa.Enum("admin", "barista", "courier", name="staff_role")


def upgrade() -> None:
    op.create_table(
        "staff_accounts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("login", sa.String(100), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", staff_role_enum, nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column(
            "is_active", sa.Boolean, nullable=False, server_default="true"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_staff_accounts_login", "staff_accounts", ["login"])


def downgrade() -> None:
    op.drop_index("ix_staff_accounts_login", table_name="staff_accounts")
    op.drop_table("staff_accounts")
    staff_role_enum.drop(op.get_bind(), checkfirst=True)
