#!/usr/bin/env bash
# scripts/loadtest/provision-runner.sh
#
# Spins up a Hetzner CPX21 in eu-central, installs k6, copies test scripts,
# and writes the IP to .loadtest-runner-ip for subsequent scripts to read.

source "$(dirname "$0")/lib.sh"
require hcloud
require ssh
require scp

SERVER_NAME="jobhunter-loadtest-$(date +%s)"
SSH_KEY_NAME="${HCLOUD_SSH_KEY:?set HCLOUD_SSH_KEY to the name of an hcloud ssh key}"

log "creating Hetzner CPX21 $SERVER_NAME"
hcloud server create \
  --name "$SERVER_NAME" \
  --type cpx21 \
  --image ubuntu-24.04 \
  --location nbg1 \
  --ssh-key "$SSH_KEY_NAME"

IP=$(hcloud server ip "$SERVER_NAME")
log "runner IP: $IP"
echo "$SERVER_NAME" > .loadtest-runner-name
echo "$IP" > .loadtest-runner-ip

log "waiting 30s for sshd"
sleep 30

log "installing k6"
ssh -o StrictHostKeyChecking=no "root@$IP" bash -s <<'REMOTE'
set -e
apt-get update -qq
apt-get install -y -qq gnupg ca-certificates
gpg -k
gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | tee /etc/apt/sources.list.d/k6.list
apt-get update -qq
apt-get install -y -qq k6
k6 version
REMOTE

log "copying test scripts"
scp -o StrictHostKeyChecking=no -r jobhunter/backend/tests/loadtest "root@$IP:/root/loadtest"

log "runner ready"
