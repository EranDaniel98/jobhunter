"""Composite indexes for cron coordinator queries.

Adds indexes that serve the hot filter predicates run every 15 min
(check_followup_due) and once per day (run_daily_scout, run_weekly_analytics,
expire_stale_actions). At current 10-user scale these are noise; at 1k+ users
they prevent full-table scans from blocking the scheduler.

Uses CREATE INDEX CONCURRENTLY so the migration is safe to run against a live
database without taking a write lock. Each CONCURRENTLY statement runs in its
own transaction via Alembic's autocommit_block().
"""

from alembic import op

revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_candidates_active_last_seen "
            "ON candidates (is_active, last_seen_at) WHERE is_active"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_outreach_messages_cron_followup "
            "ON outreach_messages (channel, status, message_type, sent_at) "
            "WHERE sent_at IS NOT NULL"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_pending_actions_status_created "
            "ON pending_actions (status, created_at)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_pending_actions_status_created")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_outreach_messages_cron_followup")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_candidates_active_last_seen")
