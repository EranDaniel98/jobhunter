#!/usr/bin/env bash
# scripts/loadtest/run-test.sh
#
# Runs k6 on the provisioned runner against the staging URL, streams the
# summary JSON back, and unconditionally triggers teardown on exit.

source "$(dirname "$0")/lib.sh"

IP=$(cat .loadtest-runner-ip) || die "no runner IP — run provision-runner.sh first"
URL=$(cat .loadtest-staging-url) || die "no staging URL — run bring-up-staging.sh first"
DATE=$(date +%Y-%m-%d)
OUT_DIR="docs/superpowers/loadtest-results/$DATE"
mkdir -p "$OUT_DIR"

trap '"$(dirname "$0")/teardown-staging.sh" || true' EXIT

log "starting k6 against $URL"
ssh -o StrictHostKeyChecking=no "root@$IP" \
  "cd /root/loadtest && BASE_URL='$URL' ONBOARD_CAP=200 k6 run --summary-export=/root/summary.json main.js" \
  | tee "$OUT_DIR/k6-stdout.log"

log "pulling artifacts"
scp "root@$IP:/root/summary.json" "$OUT_DIR/k6-summary.json"

log "k6 run complete, artifacts in $OUT_DIR"
