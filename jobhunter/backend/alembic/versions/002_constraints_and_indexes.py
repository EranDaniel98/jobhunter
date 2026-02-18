"""Add constraints, indexes, and parse_status column

Revision ID: 002
Revises: 001
Create Date: 2026-02-18
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # H1: Unique constraint on (candidate_id, domain) for companies
    op.create_unique_constraint(
        "uq_company_candidate_domain", "companies", ["candidate_id", "domain"]
    )

    # H3: Add parse_status column to resumes
    op.add_column(
        "resumes",
        sa.Column("parse_status", sa.String(20), server_default="pending", nullable=False),
    )

    # M5: Composite indexes for outreach_messages queries
    op.create_index(
        "ix_outreach_messages_contact_status",
        "outreach_messages",
        ["contact_id", "status"],
    )
    op.create_index(
        "ix_outreach_messages_candidate_status",
        "outreach_messages",
        ["candidate_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_outreach_messages_candidate_status", table_name="outreach_messages")
    op.drop_index("ix_outreach_messages_contact_status", table_name="outreach_messages")
    op.drop_column("resumes", "parse_status")
    op.drop_constraint("uq_company_candidate_domain", "companies", type_="unique")
