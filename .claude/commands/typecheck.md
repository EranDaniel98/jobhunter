---
description: Run full-project type checking and linting
---

Run type checking and linting across the full project. Report results and offer to fix issues.

$ARGUMENTS

## Steps

1. **Backend** (from `jobhunter/backend/`):
   - Run `uv run ruff check app/` — report any lint warnings
   - Run `uv run mypy app/ --ignore-missing-imports` — report type errors

2. **Frontend** (from `jobhunter/frontend/`):
   - Run `npx tsc --noEmit` — report type errors
   - Run `npm run lint` — report ESLint warnings

3. **Summary**: List all issues found with file:line references. Offer to fix them.

If $ARGUMENTS specifies "backend" or "frontend", only check that half.
