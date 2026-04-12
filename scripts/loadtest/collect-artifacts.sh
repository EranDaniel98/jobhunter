#!/usr/bin/env bash
# scripts/loadtest/collect-artifacts.sh
#
# Collects Railway logs, Postgres slow query log, and Redis snapshot
# from the staging environment into the results directory.

source "$(dirname "$0")/lib.sh"

DATE=$(date +%Y-%m-%d)
OUT_DIR="docs/superpowers/loadtest-results/$DATE"
mkdir -p "$OUT_DIR"

log "pulling Railway backend logs"
railway logs --service jobhunter --environment staging-loadtest > "$OUT_DIR/railway-logs.txt" || true

log "pulling Postgres slow query log"
railway run --service postgres psql -c "SELECT query, calls, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 50;" \
  > "$OUT_DIR/pg-slow.log" || true

log "pulling Redis info"
railway run --service redis redis-cli INFO > "$OUT_DIR/redis-info.txt" || true

log "artifacts collected in $OUT_DIR"
