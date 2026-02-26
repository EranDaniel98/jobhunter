"""Job postings for apply agent.

Revision ID: 015
Revises: 014
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_postings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", UUID(as_uuid=True), sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="SET NULL")),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("company_name", sa.String(255)),
        sa.Column("url", sa.String(1000)),
        sa.Column("raw_text", sa.Text, nullable=False),
        sa.Column("parsed_requirements", JSONB),
        sa.Column("ats_keywords", ARRAY(sa.String(255))),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_job_postings_candidate_id", "job_postings", ["candidate_id"])
    op.create_index("ix_job_postings_company_id", "job_postings", ["company_id"])
    op.create_index("ix_job_postings_status", "job_postings", ["status"])


def downgrade() -> None:
    op.drop_table("job_postings")
