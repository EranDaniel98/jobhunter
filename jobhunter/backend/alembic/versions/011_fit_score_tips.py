"""add fit_score_tips to company_dossiers"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("company_dossiers", sa.Column("fit_score_tips", ARRAY(sa.String(500)), nullable=True))


def downgrade() -> None:
    op.drop_column("company_dossiers", "fit_score_tips")
