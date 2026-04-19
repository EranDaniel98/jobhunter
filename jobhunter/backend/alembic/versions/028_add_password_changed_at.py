"""Add password_changed_at column to candidates (#103)."""

import sqlalchemy as sa
from alembic import op

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidates",
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("candidates", "password_changed_at")
