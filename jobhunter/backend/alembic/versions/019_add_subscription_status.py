"""Add subscription_status to candidates."""

from alembic import op
import sqlalchemy as sa

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidates",
        sa.Column("subscription_status", sa.String(50), server_default="inactive", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("candidates", "subscription_status")
