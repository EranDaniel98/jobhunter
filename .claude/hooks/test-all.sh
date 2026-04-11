#!/usr/bin/env bash
# Pipe-test every hook in .claude/hooks/ with a canned JSON payload.
# Catches regressions like missing tools (jq), broken JSON output,
# path issues, etc. Run this after changing any hook file.
#
# Usage: bash .claude/hooks/test-all.sh
# Exit code: 0 on success, 1 if any hook fails.

set -uo pipefail

HOOK_DIR="$(cd "$(dirname "$0")" && pwd)"
PASS=0
FAIL=0
FAIL_LIST=()

_record_pass() {
  echo "  PASS"
  PASS=$((PASS + 1))
}

_record_fail() {
  # $1 = test name, $2 = reason tag, $3 = diagnostic output (optional)
  echo "  FAIL: $2"
  if [ -n "${3-}" ]; then
    echo "  output: $3"
  fi
  FAIL=$((FAIL + 1))
  FAIL_LIST+=("$1 ($2)")
}

# Run a hook once and pipe its stdout into a python validator.
# Args: NAME SCRIPT PAYLOAD VALIDATOR(python-source)
# The validator reads the hook's stdout from sys.stdin and raises on failure.
run_test() {
  local name="$1"
  local script="$2"
  local payload="$3"
  local validator="$4"

  echo "--- $name"
  if [ ! -f "$script" ]; then
    echo "  SKIP: $script not found"
    return
  fi

  local output
  if ! output=$(printf '%s' "$payload" | bash "$script" 2>&1); then
    _record_fail "$name" "non-zero exit" "$output"
    return
  fi

  if ! printf '%s' "$output" | python -c "$validator" >/dev/null 2>&1; then
    _record_fail "$name" "validator" "$output"
    return
  fi

  _record_pass
}

# Run a hook twice with identical input; assert byte-identical output.
# Catches nondeterminism (timestamps, dict ordering, filesystem enumeration
# drift) before it becomes a heisenbug.
# Args: NAME SCRIPT PAYLOAD
#
# Implemented at the bash level because python's subprocess.run(["bash",...])
# on Windows resolves to WSL bash, which can't see Git Bash's environment.
run_test_idempotent() {
  local name="$1"
  local script="$2"
  local payload="$3"

  echo "--- $name"
  if [ ! -f "$script" ]; then
    echo "  SKIP: $script not found"
    return
  fi

  local run1 run2
  if ! run1=$(printf '%s' "$payload" | bash "$script" 2>&1); then
    _record_fail "$name" "first run non-zero exit" "$run1"
    return
  fi
  if ! run2=$(printf '%s' "$payload" | bash "$script" 2>&1); then
    _record_fail "$name" "second run non-zero exit" "$run2"
    return
  fi

  if [ "$run1" != "$run2" ]; then
    _record_fail "$name" "outputs differ between runs"
    return
  fi

  # Both runs are equal; ensure the shared output is valid JSON so we don't
  # pass an idempotently-broken hook.
  if ! printf '%s' "$run1" | python -c "import json,sys; json.loads(sys.stdin.read())" >/dev/null 2>&1; then
    _record_fail "$name" "outputs equal but not valid JSON" "$run1"
    return
  fi

  _record_pass
}

# === session-start-inject-memory: happy path + deeper assertions ===
run_test \
  "session-start-inject-memory / happy path" \
  "$HOOK_DIR/session-start-inject-memory.sh" \
  '{"hook_event_name":"SessionStart","session_id":"test"}' \
  '
import json, sys
raw = sys.stdin.read()

# Strict JSON parse (catches trailing garbage, malformed escapes, non-UTF-8)
d = json.loads(raw)

# Exact schema shape the Claude Code harness expects.
assert "hookSpecificOutput" in d, "missing hookSpecificOutput"
hso = d["hookSpecificOutput"]
assert hso["hookEventName"] == "SessionStart", "wrong hookEventName"
assert "additionalContext" in hso, "missing additionalContext"

ctx = hso["additionalContext"]

# Context must be substantial but not unbounded (catches runaway growth
# that would bloat every session start).
assert 500 < len(ctx) < 50000, f"context length out of bounds: {len(ctx)}"

# Every memory file must be represented with its generated section header.
for f in ["user.md","preferences.md","decisions.md","people.md"]:
    assert f"## === {f} ===" in ctx, f"missing section header for {f}"

# The top-of-injection sentinel must be present so Claude can recognize
# the injection in context.
assert "Persistent project memory" in ctx, "missing top-level sentinel"

# Content must be clean text (no null bytes, no unexpected control chars).
for i, c in enumerate(ctx):
    if ord(c) < 32 and c not in "\n\r\t":
        raise AssertionError(f"unexpected control char 0x{ord(c):02x} at offset {i}")
'

# === session-start-inject-memory: idempotence ===
run_test_idempotent \
  "session-start-inject-memory / idempotent" \
  "$HOOK_DIR/session-start-inject-memory.sh" \
  '{"hook_event_name":"SessionStart","session_id":"test"}'

# === Add new hook tests above this line ===

echo
echo "=========================================="
echo "Passed: $PASS   Failed: $FAIL"
if [ $FAIL -gt 0 ]; then
  echo "Failures:"
  for f in "${FAIL_LIST[@]}"; do
    echo "  - $f"
  done
  exit 1
fi
exit 0
