"""add resume_bullets to company_dossiers"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("company_dossiers", sa.Column("resume_bullets", ARRAY(sa.String(500)), nullable=True))


def downgrade() -> None:
    op.drop_column("company_dossiers", "resume_bullets")
