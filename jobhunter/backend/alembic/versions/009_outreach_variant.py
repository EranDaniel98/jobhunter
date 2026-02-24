"""add variant to outreach_messages"""

from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("outreach_messages", sa.Column("variant", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("outreach_messages", "variant")
