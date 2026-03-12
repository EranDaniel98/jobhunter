"""Add api_usage table for per-user cost tracking."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_usage",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", UUID(as_uuid=True), sa.ForeignKey("candidates.id"), nullable=False, index=True),
        sa.Column("service", sa.String(32), nullable=False, server_default="openai"),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("tokens_in", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer, nullable=False, server_default="0"),
        sa.Column("estimated_cost_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("endpoint", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_api_usage_candidate_created", "api_usage", ["candidate_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_api_usage_candidate_created")
    op.drop_table("api_usage")
