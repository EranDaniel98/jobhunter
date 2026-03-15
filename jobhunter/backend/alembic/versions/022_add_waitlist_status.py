"""Add waitlist status tracking columns and invite email/nullable invited_by."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- waitlist_entries: new status-tracking columns ---
    op.add_column(
        "waitlist_entries",
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
    )
    op.add_column(
        "waitlist_entries",
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "waitlist_entries",
        sa.Column(
            "invite_code_id",
            UUID(as_uuid=True),
            sa.ForeignKey("invite_codes.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "waitlist_entries",
        sa.Column("invite_error", sa.String(500), nullable=True),
    )
    op.create_index(
        "ix_waitlist_entries_status_created",
        "waitlist_entries",
        ["status", "created_at"],
    )

    # --- invite_codes: add email column ---
    op.add_column(
        "invite_codes",
        sa.Column("email", sa.String(255), nullable=True),
    )

    # --- invite_codes: make invited_by_id nullable ---
    op.alter_column(
        "invite_codes",
        "invited_by_id",
        existing_type=UUID(as_uuid=True),
        nullable=True,
    )


def downgrade() -> None:
    # Revert invited_by_id to non-nullable
    op.alter_column(
        "invite_codes",
        "invited_by_id",
        existing_type=UUID(as_uuid=True),
        nullable=False,
    )

    # Remove invite_codes.email
    op.drop_column("invite_codes", "email")

    # Remove waitlist_entries additions (reverse order)
    op.drop_index("ix_waitlist_entries_status_created", table_name="waitlist_entries")
    op.drop_column("waitlist_entries", "invite_error")
    op.drop_column("waitlist_entries", "invite_code_id")
    op.drop_column("waitlist_entries", "invited_at")
    op.drop_column("waitlist_entries", "status")
