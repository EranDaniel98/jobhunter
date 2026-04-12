#!/usr/bin/env bash
# PostToolUse hook: auto-format and lint Python files under jobhunter/backend/
# Runs after every Write|Edit tool call. Must exit 0 always (never block edits).

# Read stdin into a variable
INPUT=$(cat)

# Extract file path using Python via stdin (safe — no shell-quoting issues)
FILE_PATH=$(printf '%s' "$INPUT" | python -c "
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)

# Edit tool uses tool_input.file_path
# Write tool uses tool_response.filePath
path = (d.get('tool_input') or {}).get('file_path') or \
       (d.get('tool_response') or {}).get('filePath') or ''
print(path, end='')
" 2>/dev/null) || true

# Exit silently if no path extracted
if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# Only process .py files
if [[ "$FILE_PATH" != *.py ]]; then
    exit 0
fi

# Normalize path separators and check prefix
NORMALIZED="${FILE_PATH//\\//}"
if [[ "$NORMALIZED" != jobhunter/backend/* ]]; then
    exit 0
fi

# Store project root (hook runs from project root)
PROJECT_ROOT="$(pwd)"

# Run ruff format (suppress all output, never block on failure)
(cd "$PROJECT_ROOT/jobhunter/backend" && uv run ruff format "$PROJECT_ROOT/$NORMALIZED" >/dev/null 2>&1) || true

# Run ruff check and capture warnings (exit code 1 = violations, 0 = clean)
WARNINGS=$(cd "$PROJECT_ROOT/jobhunter/backend" && uv run ruff check "$PROJECT_ROOT/$NORMALIZED" --output-format full 2>&1)
RUFF_EXIT=$?

# Output JSON context only if ruff found actual violations (exit code non-zero)
if [ "$RUFF_EXIT" -ne 0 ] && [ -n "$WARNINGS" ]; then
    printf '%s' "$WARNINGS" | python -c "
import json, sys
warnings = sys.stdin.read()
output = {
    'hookSpecificOutput': {
        'hookEventName': 'PostToolUse',
        'additionalContext': 'Ruff warnings:\n' + warnings
    }
}
print(json.dumps(output))
"
fi

exit 0
