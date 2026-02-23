"""Add is_admin column to candidates

Revision ID: 004
Revises: 003
Create Date: 2026-02-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "candidates",
        sa.Column("is_admin", sa.Boolean, server_default=sa.text("false"), nullable=False),
    )
    # Set the platform owner as admin
    op.execute("UPDATE candidates SET is_admin = true WHERE email = 'erand1998@gmail.com'")


def downgrade() -> None:
    op.drop_column("candidates", "is_admin")
