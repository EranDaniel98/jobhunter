"""Add last_seen_at column to candidates."""

import sqlalchemy as sa
from alembic import op

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidates",
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_candidates_last_seen_at", "candidates", ["last_seen_at"])


def downgrade() -> None:
    op.drop_index("ix_candidates_last_seen_at", table_name="candidates")
    op.drop_column("candidates", "last_seen_at")
