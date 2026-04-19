"""Lowercase existing candidate emails so case-insensitive login works.

Aborts if lowercasing would create a duplicate — the operator must resolve
collisions manually before re-running.
"""

from alembic import op

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    dup = conn.exec_driver_sql(
        "SELECT LOWER(email) AS e, COUNT(*) AS n "
        "FROM candidates GROUP BY LOWER(email) HAVING COUNT(*) > 1"
    ).fetchall()
    if dup:
        emails = ", ".join(row[0] for row in dup)
        raise RuntimeError(
            f"Cannot lowercase emails — duplicates would result for: {emails}. "
            "Resolve the conflicts (merge or delete accounts) and re-run."
        )
    conn.exec_driver_sql("UPDATE candidates SET email = LOWER(email) WHERE email <> LOWER(email)")


def downgrade() -> None:
    # Not reversible — pre-existing case information is lost.
    pass
