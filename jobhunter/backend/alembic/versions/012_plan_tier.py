"""add plan_tier and stripe fields to candidates"""

from alembic import op
import sqlalchemy as sa

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidates",
        sa.Column("plan_tier", sa.String(20), server_default="free", nullable=False),
    )
    op.add_column(
        "candidates",
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "candidates",
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
    )
    op.create_index("ix_candidates_plan_tier", "candidates", ["plan_tier"])
    op.create_unique_constraint("uq_candidates_stripe_customer_id", "candidates", ["stripe_customer_id"])
    op.create_unique_constraint("uq_candidates_stripe_subscription_id", "candidates", ["stripe_subscription_id"])


def downgrade() -> None:
    op.drop_constraint("uq_candidates_stripe_subscription_id", "candidates", type_="unique")
    op.drop_constraint("uq_candidates_stripe_customer_id", "candidates", type_="unique")
    op.drop_index("ix_candidates_plan_tier", table_name="candidates")
    op.drop_column("candidates", "stripe_subscription_id")
    op.drop_column("candidates", "stripe_customer_id")
    op.drop_column("candidates", "plan_tier")
