"""Add check constraint for application_stage on job_postings.

Revision ID: 018
Revises: 017
"""
from alembic import op

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_job_posting_application_stage",
        "job_postings",
        "application_stage IN ('saved','applied','phone_screen','interview','offer','rejected')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_job_posting_application_stage", "job_postings", type_="check")
