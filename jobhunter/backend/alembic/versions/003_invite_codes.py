"""Add invite_codes table

Revision ID: 003
Revises: 002
Create Date: 2026-02-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "invite_codes",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column(
            "invited_by_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("candidates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "used_by_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("candidates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_used", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("invite_codes")
