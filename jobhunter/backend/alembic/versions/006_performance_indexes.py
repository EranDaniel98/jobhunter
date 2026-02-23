"""Add performance indexes for query optimization

Revision ID: 006
Revises: 005
Create Date: 2026-02-23
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_candidates_is_active", "candidates", ["is_active"])
    op.create_index("ix_contacts_company_email", "contacts", ["company_id", "email"])
    op.create_index(
        "ix_outreach_messages_candidate_created",
        "outreach_messages",
        ["candidate_id", "created_at"],
    )
    op.create_index(
        "ix_analytics_events_candidate_occurred",
        "analytics_events",
        ["candidate_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_analytics_events_candidate_occurred", table_name="analytics_events")
    op.drop_index("ix_outreach_messages_candidate_created", table_name="outreach_messages")
    op.drop_index("ix_contacts_company_email", table_name="contacts")
    op.drop_index("ix_candidates_is_active", table_name="candidates")
