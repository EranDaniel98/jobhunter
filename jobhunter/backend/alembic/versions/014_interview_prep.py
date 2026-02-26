"""Interview prep sessions and mock interview messages.

Revision ID: 014
Revises: 013
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interview_prep_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("candidate_id", UUID(as_uuid=True), sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prep_type", sa.String(50), nullable=False),
        sa.Column("content", JSONB),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("error", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_interview_prep_sessions_candidate_company", "interview_prep_sessions", ["candidate_id", "company_id"])
    op.create_index("ix_interview_prep_sessions_status", "interview_prep_sessions", ["status"])

    op.create_table(
        "mock_interview_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("interview_prep_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("turn_number", sa.Integer, nullable=False),
        sa.Column("feedback", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_mock_interview_messages_session_id", "mock_interview_messages", ["session_id"])


def downgrade() -> None:
    op.drop_table("mock_interview_messages")
    op.drop_table("interview_prep_sessions")
