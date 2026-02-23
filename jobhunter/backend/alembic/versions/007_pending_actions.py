"""Add pending_actions table for approval gateway

Revision ID: 007
Revises: 006
Create Date: 2026-02-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pending_actions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", UUID(as_uuid=True), sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False, server_default="outreach_message"),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("ai_reasoning", sa.Text),
        sa.Column("metadata", JSONB),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_pending_actions_candidate_id", "pending_actions", ["candidate_id"])
    op.create_index("ix_pending_actions_entity_id", "pending_actions", ["entity_id"])
    op.create_index("ix_pending_actions_status", "pending_actions", ["status"])
    op.create_index("ix_pending_actions_candidate_status", "pending_actions", ["candidate_id", "status"])
    op.create_index("ix_pending_actions_entity", "pending_actions", ["entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_index("ix_pending_actions_entity", table_name="pending_actions")
    op.drop_index("ix_pending_actions_candidate_status", table_name="pending_actions")
    op.drop_index("ix_pending_actions_status", table_name="pending_actions")
    op.drop_index("ix_pending_actions_entity_id", table_name="pending_actions")
    op.drop_index("ix_pending_actions_candidate_id", table_name="pending_actions")
    op.drop_table("pending_actions")
