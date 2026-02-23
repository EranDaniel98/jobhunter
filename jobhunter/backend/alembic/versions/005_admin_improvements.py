"""Add is_active column and admin_audit_logs table

Revision ID: 005
Revises: 004
Create Date: 2026-02-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_active to candidates
    op.add_column(
        "candidates",
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true"), nullable=False),
    )

    # Create admin_audit_logs table
    op.create_table(
        "admin_audit_logs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "admin_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("candidates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column(
            "target_user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("candidates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("details", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("admin_audit_logs")
    op.drop_column("candidates", "is_active")
