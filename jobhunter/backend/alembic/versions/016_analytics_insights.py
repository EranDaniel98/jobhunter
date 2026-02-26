"""Add analytics_insights table.

Revision ID: 016
Revises: 015
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analytics_insights",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", UUID(as_uuid=True), sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("insight_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(20), server_default="info"),
        sa.Column("data", JSONB),
        sa.Column("is_read", sa.Boolean(), server_default="false"),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_analytics_insights_candidate_id", "analytics_insights", ["candidate_id"])
    op.create_index("ix_analytics_insights_insight_type", "analytics_insights", ["insight_type"])
    op.create_index("ix_analytics_insights_created_at", "analytics_insights", ["created_at"])


def downgrade() -> None:
    op.drop_table("analytics_insights")
