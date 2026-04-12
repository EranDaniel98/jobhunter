#!/usr/bin/env bash
# SessionStart hook: read the four memory files and inject their contents
# into the model context as additionalContext. Guarantees memory is loaded
# on every session without depending on Claude following a CLAUDE.md
# instruction to Read them.
#
# If files grow large, flip this to inject only a TOC and let Claude Read
# on demand.

set -euo pipefail

# Resolve project root from this script's location: hooks/ -> .claude/ -> project root
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

python "$SCRIPT_DIR/session-start-inject-memory.py" "$PROJECT_ROOT/memory"
