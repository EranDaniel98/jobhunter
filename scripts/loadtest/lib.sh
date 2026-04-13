#!/usr/bin/env bash
# scripts/loadtest/lib.sh — shared helpers for load-test orchestration

set -euo pipefail

LOG_PREFIX="[loadtest]"

log() { echo "${LOG_PREFIX} $*" >&2; }
die() { log "FATAL: $*"; exit 1; }

# Cost gate — fail loudly if we've blown the budget
BUDGET_USD="${BUDGET_USD:-70}"
check_budget() {
  local spent="$1"
  if (( $(echo "$spent > $BUDGET_USD" | bc -l) )); then
    die "budget exceeded: \$$spent > \$$BUDGET_USD"
  fi
}

# Require a command to be installed
require() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}
