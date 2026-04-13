#!/usr/bin/env bash
# scripts/loadtest/teardown-staging.sh
#
# Unconditional cleanup: destroys the staging Railway environment AND the
# Hetzner runner VM. Safe to call multiple times (idempotent).

source "$(dirname "$0")/lib.sh"

ENV_NAME="staging-loadtest"

if command -v railway >/dev/null; then
  log "destroying Railway env $ENV_NAME"
  railway environment delete "$ENV_NAME" --yes || log "railway env delete failed (may already be gone)"
fi

if command -v hcloud >/dev/null && [[ -f .loadtest-runner-name ]]; then
  RUNNER=$(cat .loadtest-runner-name)
  log "destroying Hetzner runner $RUNNER"
  hcloud server delete "$RUNNER" || log "hcloud delete failed (may already be gone)"
  rm -f .loadtest-runner-name .loadtest-runner-ip
fi

rm -f .loadtest-staging-url
log "teardown complete"
