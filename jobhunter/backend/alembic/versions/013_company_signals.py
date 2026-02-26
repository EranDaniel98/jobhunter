"""add company source field and company_signals table"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add source column to companies
    op.add_column(
        "companies",
        sa.Column("source", sa.String(50), server_default="manual", nullable=False),
    )

    # Create company_signals table
    op.create_table(
        "company_signals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("candidate_id", UUID(as_uuid=True), sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("signal_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("source_url", sa.String(1000), nullable=True),
        sa.Column("signal_strength", sa.Float, nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_", JSONB, nullable=True),
    )
    op.create_index("ix_company_signals_company_id_signal_type", "company_signals", ["company_id", "signal_type"])
    op.create_index("ix_company_signals_candidate_id", "company_signals", ["candidate_id"])
    op.create_index("ix_company_signals_detected_at", "company_signals", ["detected_at"])


def downgrade() -> None:
    op.drop_index("ix_company_signals_detected_at", table_name="company_signals")
    op.drop_index("ix_company_signals_candidate_id", table_name="company_signals")
    op.drop_index("ix_company_signals_company_id_signal_type", table_name="company_signals")
    op.drop_table("company_signals")
    op.drop_column("companies", "source")
