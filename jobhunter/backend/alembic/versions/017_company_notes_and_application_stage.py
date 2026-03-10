"""Add company_notes table and application_stage column to job_postings.

Revision ID: 017
Revises: 016
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_notes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", UUID(as_uuid=True), sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_company_notes_candidate_id", "company_notes", ["candidate_id"])
    op.create_index("ix_company_notes_company_id", "company_notes", ["company_id"])
    # Unique constraint: one note per candidate per company
    op.create_unique_constraint("uq_company_notes_candidate_company", "company_notes", ["candidate_id", "company_id"])

    # Add application_stage column to job_postings
    op.add_column("job_postings", sa.Column("application_stage", sa.String(30), server_default="saved", nullable=False))


def downgrade() -> None:
    op.drop_column("job_postings", "application_stage")
    op.drop_table("company_notes")
