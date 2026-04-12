#!/usr/bin/env bash
# scripts/loadtest/bring-up-staging.sh
#
# Creates a Railway environment named 'staging-loadtest' in the jobhunter project,
# sets LOADTEST_MODE=1 and LOADTEST_AI_BUDGET=200, deploys current main, runs
# migrations, and seeds fixtures. Prints the deployed URL on success.
#
# Idempotent: if the environment already exists, skips creation and just redeploys.

source "$(dirname "$0")/lib.sh"
require railway

ENV_NAME="staging-loadtest"
PROJECT_ID="cc873661-d54c-44b4-acda-975758d196fe"
SERVICE="jobhunter"

log "linking Railway project $PROJECT_ID"
railway link --project "$PROJECT_ID" --service "$SERVICE"

if ! railway environment | grep -q "^$ENV_NAME$"; then
  log "creating environment $ENV_NAME"
  railway environment new "$ENV_NAME"
else
  log "environment $ENV_NAME already exists"
fi
railway environment use "$ENV_NAME"

log "setting loadtest env vars"
railway variables set LOADTEST_MODE=1 LOADTEST_AI_BUDGET=200 OPENAI_MODEL=gpt-4o-mini

log "deploying"
railway up --detach

log "waiting 60s for healthcheck"
sleep 60

URL=$(railway domain | head -1)
log "staging URL: $URL"

log "running migrations"
railway run --service "$SERVICE" alembic upgrade head

log "seeding data"
railway run --service "$SERVICE" python scripts/seed_loadtest_data.py

log "pulling users.json fixture"
railway run --service "$SERVICE" cat tests/loadtest/fixtures/users.json > jobhunter/backend/tests/loadtest/fixtures/users.json

echo "$URL" > .loadtest-staging-url
log "done. URL stored in .loadtest-staging-url"
