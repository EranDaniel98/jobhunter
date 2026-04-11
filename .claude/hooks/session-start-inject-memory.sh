#!/usr/bin/env bash
# SessionStart hook: read the four memory files and inject their contents
# into the model context as additionalContext. Guarantees memory is loaded
# on every session without depending on Claude following a CLAUDE.md
# instruction to Read them.
#
# If files grow large, flip this to inject only a TOC and let Claude Read
# on demand.

set -euo pipefail

python "C:/Users/Eran/Desktop/Personal/JobSearch/.claude/hooks/session-start-inject-memory.py"
