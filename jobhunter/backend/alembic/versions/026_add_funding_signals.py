"""Add funding_signals shared pool table."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "funding_signals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_name", sa.String(100), nullable=True),
        sa.Column("company_name", sa.String(200), nullable=True),
        sa.Column("estimated_domain", sa.String(200), nullable=True),
        sa.Column("funding_round", sa.String(50), nullable=True),
        sa.Column("amount", sa.String(50), nullable=True),
        sa.Column("industry", sa.String(100), nullable=True),
        sa.Column("signal_types", JSONB, nullable=True),
        sa.Column("extra_data", JSONB, nullable=True),
        sa.Column("embedding", ARRAY(sa.Float), nullable=True),
        sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("source_url", name="uq_funding_signals_source_url"),
    )
    op.create_index("ix_funding_signals_published_at", "funding_signals", ["published_at"])
    op.create_index("ix_funding_signals_company_name", "funding_signals", ["company_name"])
    op.create_index("ix_funding_signals_expires_at", "funding_signals", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_funding_signals_expires_at", table_name="funding_signals")
    op.drop_index("ix_funding_signals_company_name", table_name="funding_signals")
    op.drop_index("ix_funding_signals_published_at", table_name="funding_signals")
    op.drop_table("funding_signals")
