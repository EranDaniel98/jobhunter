# Claude Infrastructure Overhaul — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Claude deeply project-aware from turn one, auto-format/lint backend edits, clean up stale config, and reduce baseline token cost by ~4,800 tokens/session.

**Architecture:** All changes are to Claude Code config files (`CLAUDE.md`, `.claude/`, `~/.claude/`), plus one new hook script. No application code changes. Hook scripts use Python for JSON, bash for orchestration (no jq on this machine).

**Spec:** `docs/superpowers/specs/2026-04-12-claude-infrastructure-overhaul-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Rewrite | `~/.claude/CLAUDE.md` | Trim RTK to 3 lines, keep pre-design rules |
| Modify | `~/.claude/settings.json` | Disable 4 plugins |
| Rewrite | `CLAUDE.md` | Deep codebase guide (terse style) |
| Rewrite | `.claude/settings.local.json` | Clean permissions (151 → ~40) |
| Modify | `.claude/settings.json` | Add PostToolUse hook entry |
| Create | `.claude/hooks/post-edit.sh` | Format + lint backend files after edit |
| Modify | `.claude/hooks/session-start-inject-memory.py` | Add size guard (>8000 chars → TOC only) |
| Create | `.claude/commands/typecheck.md` | Full-project type check + lint |
| Create | `.claude/commands/pr.md` | PR creation helper |
| Modify | `.claude/hooks/test-all.sh` | Add post-edit hook tests |
| Modify | `memory/decisions.md` | Record infrastructure decisions |

---

### Task 1: Trim global CLAUDE.md RTK section

**Files:**
- Modify: `~/.claude/CLAUDE.md` (lines 1-133)

- [ ] **Step 1: Replace the RTK section with a 3-line version**

Replace everything between `<!-- rtk-instructions v2 -->` and `<!-- /rtk-instructions -->` (inclusive) with:

```markdown
# RTK
Always prefix shell commands with `rtk`, even in chains (`rtk git add . && rtk git commit -m "msg"`).
RTK filters output for 60-90% token savings. If no filter exists for a command, it passes through unchanged — always safe to use.
```

Keep the `# Pre-design discipline` section and everything below it unchanged.

- [ ] **Step 2: Verify**

Run: `wc -l ~/.claude/CLAUDE.md`
Expected: ~35 lines (down from ~164). The pre-design rules are ~30 lines + 3 RTK lines + blank lines.

- [ ] **Step 3: Commit**

This is a global file outside the repo — no git commit. Just verify it saved correctly.

---

### Task 2: Disable unused plugins

**Files:**
- Modify: `~/.claude/settings.json`

- [ ] **Step 1: Remove 4 plugins from enabledPlugins**

Remove these keys from the `enabledPlugins` object:
- `"example-skills@anthropic-agent-skills": true` (duplicate of document-skills)
- `"claude-mem@thedotmack": true` (redundant — project has its own memory system)
- `"frontend-design@claude-plugins-official": true` (rarely used for this project)
- `"feature-dev@claude-plugins-official": true` (overlaps with superpowers brainstorming)

Keep these 8:
- `github`, `context7`, `superpowers`, `code-review`, `repomix-mcp`, `repomix-commands`, `repomix-explorer`, `document-skills`

- [ ] **Step 2: Validate JSON**

Run: `python -c "import json; d=json.load(open('$HOME/.claude/settings.json')); print('plugins:', len(d['enabledPlugins']))"`
Expected: `plugins: 8`

---

### Task 3: Rewrite project CLAUDE.md (deep codebase guide, terse style)

**Files:**
- Rewrite: `CLAUDE.md`

This is the largest task. The full content is specified below. Write it as a single `Write` tool call.

- [ ] **Step 1: Write the new CLAUDE.md**

Content — terse bullet-point style, ~200 lines, organized as:

1. **Memory System** — trimmed: 4 files, SessionStart hook, `/remember`, update rules. Remove historical "why" paragraphs (that's in `memory/decisions.md`).
2. **Tech Stack** — one-paragraph summary
3. **Project Layout** — directory tree with one-line descriptions
4. **Backend Conventions** — bullet points: layering, DI, Protocols, LangGraph, events, quotas, config
5. **Frontend Conventions** — bullet points: all client components, TanStack Query hooks, auth, forms, WebSocket, UI
6. **Testing** — how to run, frameworks, fixtures, coverage targets
7. **Run Commands** — exact commands grouped by backend/frontend/docker
8. **Linting & Formatting** — Ruff config, mypy, ESLint. Note: PostToolUse hook auto-formats `.py` files
9. **Git Conventions** — Conventional Commits format, types, scopes
10. **Deployment** — Railway, health check URL, staging pattern
11. **CI/CD Reference** — one line per workflow
12. **Tooling Gaps** — no jq, Windows junction notes, WSL-vs-Git-Bash subprocess issue
13. **Slash Commands** — list all available: `/preflight`, `/retro`, `/remember`, `/typecheck`, `/pr`

- [ ] **Step 2: Verify line count and token estimate**

Run: `wc -l CLAUDE.md && wc -w CLAUDE.md`
Target: <220 lines, <2000 words (~2500 tokens)

- [ ] **Step 3: Commit**

```bash
rtk git add CLAUDE.md && rtk git commit -m "docs: rewrite CLAUDE.md with deep codebase guide (terse style)"
```

---

### Task 4: PostToolUse format + lint hook

**Files:**
- Create: `.claude/hooks/post-edit.sh`
- Modify: `.claude/settings.json`

- [ ] **Step 1: Write the post-edit.sh script**

The script:
1. Reads stdin JSON, extracts file path from `tool_input.file_path` (Edit) or `tool_response.filePath` (Write)
2. If file is `.py` under `jobhunter/backend/`:
   - Run `ruff format <file>` (silent)
   - Run `ruff check <file> --output-format text`
   - If warnings exist, output `{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"Ruff warnings:\n<output>"}}`
3. All other files: exit 0 silently
4. Never exit non-zero (don't block edits)

Use Python for JSON extraction (no jq). Use bash for running ruff.

- [ ] **Step 2: Pipe-test the script**

Test with a Python file path:
```bash
echo '{"tool_name":"Edit","tool_input":{"file_path":"jobhunter/backend/app/main.py"}}' | bash .claude/hooks/post-edit.sh
echo "exit=$?"
```
Expected: exit 0 (ruff runs, output depends on file state)

Test with a non-Python file:
```bash
echo '{"tool_name":"Edit","tool_input":{"file_path":"jobhunter/frontend/src/app/page.tsx"}}' | bash .claude/hooks/post-edit.sh
echo "exit=$?"
```
Expected: exit 0, no output (skip)

- [ ] **Step 3: Add PostToolUse hook to `.claude/settings.json`**

Merge into the existing settings.json (which already has SessionStart). Add:
```json
"PostToolUse": [
  {
    "matcher": "Write|Edit",
    "hooks": [
      {
        "type": "command",
        "command": "bash .claude/hooks/post-edit.sh"
      }
    ]
  }
]
```

- [ ] **Step 4: Validate settings.json**

```bash
python -c "import json; d=json.load(open('.claude/settings.json')); print('SessionStart:', 'SessionStart' in d['hooks']); print('PostToolUse:', 'PostToolUse' in d['hooks'])"
```
Expected: both `True`

- [ ] **Step 5: Commit**

```bash
rtk git add .claude/hooks/post-edit.sh .claude/settings.json
rtk git commit -m "feat(claude): add PostToolUse hook for backend auto-format and lint"
```

---

### Task 5: Add size guard to SessionStart memory injection

**Files:**
- Modify: `.claude/hooks/session-start-inject-memory.py`

- [ ] **Step 1: Add size check after building content**

After `content = "\n".join(parts)`, add:
- If `len(content) > 8000`: replace `content` with a table-of-contents listing each file name + line count + first heading. Append: `"\n\nMemory files exceed 8000 chars. Use Read tool to load specific files on demand."`

- [ ] **Step 2: Pipe-test**

Normal case (current files are ~4900 chars, under limit):
```bash
echo '{}' | bash .claude/hooks/session-start-inject-memory.sh | python -c "import json,sys; d=json.loads(sys.stdin.read()); print('len:', len(d['hookSpecificOutput']['additionalContext'])); assert 'user.md' in d['hookSpecificOutput']['additionalContext']"
```
Expected: `len: ~4900`, assertion passes (full content injected)

- [ ] **Step 3: Commit**

```bash
rtk git add .claude/hooks/session-start-inject-memory.py
rtk git commit -m "fix(claude): add size guard to memory injection (>8000 chars → TOC only)"
```

---

### Task 6: Slash commands — /typecheck and /pr

**Files:**
- Create: `.claude/commands/typecheck.md`
- Create: `.claude/commands/pr.md`

- [ ] **Step 1: Write /typecheck**

The command runs full-project type checking + linting:
- Backend: `cd jobhunter/backend && uv run mypy app/ --ignore-missing-imports` + `uv run ruff check app/`
- Frontend: `cd jobhunter/frontend && npx tsc --noEmit` + `npm run lint`

Report results, offer to fix issues found.

- [ ] **Step 2: Write /pr**

The command creates a pull request:
1. Detect base branch (default: `main`)
2. Gather commits since diverging: `git log main..HEAD --oneline`
3. Gather diff summary: `git diff main...HEAD --stat`
4. Generate PR title (conventional-commit style, <70 chars) and body (summary + test plan)
5. Push if needed, create with `gh pr create`

Accept optional argument for base branch override.

- [ ] **Step 3: Commit**

```bash
rtk git add .claude/commands/typecheck.md .claude/commands/pr.md
rtk git commit -m "feat(claude): add /typecheck and /pr slash commands"
```

---

### Task 7: Permissions cleanup

**Files:**
- Rewrite: `.claude/settings.local.json`

- [ ] **Step 1: Read current file, note existing structure**

Read `.claude/settings.local.json`. Preserve the JSON structure (`{"permissions":{"allow":[...]}}`). Replace the `allow` array contents.

- [ ] **Step 2: Write clean permissions list**

Replace the 151 entries with this ~40-entry list:

```json
[
  "Bash(git:*)", "Bash(gh:*)", "Bash(rtk:*)",
  "Bash(uv:*)", "Bash(python:*)", "Bash(python3:*)", "Bash(pip:*)",
  "Bash(npm:*)", "Bash(npx:*)",
  "Bash(docker:*)", "Bash(docker compose:*)",
  "Bash(railway:*)", "Bash(curl:*)",
  "Bash(bash:*)", "Bash(powershell.exe:*)",
  "Bash(ls:*)", "Bash(cat:*)", "Bash(head:*)", "Bash(tail:*)",
  "Bash(find:*)", "Bash(grep:*)", "Bash(wc:*)", "Bash(rm:*)",
  "Bash(mkdir:*)", "Bash(cp:*)", "Bash(mv:*)", "Bash(chmod:*)",
  "Bash(echo:*)", "Bash(cd:*)", "Bash(sort:*)", "Bash(xargs:*)",
  "Bash(test:*)", "Bash(timeout:*)", "Bash(touch:*)", "Bash(sed:*)",
  "Bash(netstat:*)", "Bash(taskkill:*)", "Bash(nslookup:*)",
  "WebSearch",
  "WebFetch(domain:deepwiki.com)",
  "mcp__plugin_context7_context7__query-docs",
  "mcp__plugin_context7_context7__resolve-library-id",
  "mcp__plugin_github_github__list_issues",
  "mcp__plugin_github_github__issue_write",
  "mcp__plugin_github_github__add_issue_comment",
  "mcp__plugin_github_github__get_file_contents",
  "mcp__plugin_claude-mem_mcp-search__search"
]
```

Note: keep `mcp__plugin_claude-mem_mcp-search__search` even though the plugin is being disabled — MCP permission entries don't hurt if the plugin is off, and it's there in case re-enabled.

- [ ] **Step 3: Validate**

```bash
python -c "import json; d=json.load(open('.claude/settings.local.json')); print('entries:', len(d['permissions']['allow'])); assert 'Bash(*)' not in d['permissions']['allow'], 'Bash(*) still present!'"
```
Expected: `entries: ~47`, no assertion error.

- [ ] **Step 4: Do NOT commit**

This file is gitignored (`.claude/settings.local.json`). No commit needed.

---

### Task 8: Update hook test harness

**Files:**
- Modify: `.claude/hooks/test-all.sh`

- [ ] **Step 1: Add post-edit.sh happy path test**

Add a `run_test` call for `post-edit.sh` with a Python file input:
```bash
run_test \
  "post-edit / python file" \
  "$HOOK_DIR/post-edit.sh" \
  '{"tool_name":"Edit","tool_input":{"file_path":"jobhunter/backend/app/main.py"}}' \
  'import json, sys; raw = sys.stdin.read(); True'
```
Validator: just assert exit 0 and no crash. The output varies depending on ruff findings.

- [ ] **Step 2: Add post-edit.sh skip test for non-Python file**

```bash
run_test \
  "post-edit / tsx file (skip)" \
  "$HOOK_DIR/post-edit.sh" \
  '{"tool_name":"Edit","tool_input":{"file_path":"jobhunter/frontend/src/app/page.tsx"}}' \
  'import sys; raw = sys.stdin.read().strip(); assert len(raw) == 0, f"expected no output for non-py file, got: {raw!r}"'
```

- [ ] **Step 3: Add post-edit.sh idempotence test**

```bash
run_test_idempotent \
  "post-edit / idempotent" \
  "$HOOK_DIR/post-edit.sh" \
  '{"tool_name":"Edit","tool_input":{"file_path":"jobhunter/backend/app/main.py"}}'
```

- [ ] **Step 4: Run full test harness**

```bash
bash .claude/hooks/test-all.sh
```
Expected: all tests pass (existing 2 + new 3 = 5 total)

- [ ] **Step 5: Commit**

```bash
rtk git add .claude/hooks/test-all.sh
rtk git commit -m "test(claude): add post-edit hook tests to harness"
```

---

### Task 9: Update memory/decisions.md

**Files:**
- Modify: `memory/decisions.md`

- [ ] **Step 1: Add infrastructure overhaul entry**

Append a new dated section:

```markdown
## 2026-04-12 — Claude infrastructure overhaul: deep CLAUDE.md, auto-lint, permissions cleanup, token reduction

**What:** Rewrote CLAUDE.md with full codebase guide (~200 lines, terse). Added PostToolUse hook for Ruff auto-format+lint on backend `.py` files only. Replaced 151 stale permissions with ~40 specific patterns (removed `Bash(*)` wildcard). Trimmed global RTK instructions from 133 lines to 3. Disabled 4 redundant plugins. Added size guard to memory injection.

**Why:** Claude was rediscovering codebase patterns every session (~10min wasted). Per-edit ESLint was too slow (2-5s) but Ruff is instant (~50ms). The Bash(*) wildcard made all other Bash permissions meaningless and a hardcoded JWT token sat in the allowlist. Token baseline was ~12k/session; reductions bring it to ~7k even with the deep CLAUDE.md addition.

**How to apply:** For future hooks, benchmark latency before making them PostToolUse — anything over ~200ms will feel slow. For permissions, use specific patterns over wildcards so genuinely unusual commands still get prompted. For CLAUDE.md, prefer terse tables and bullets over prose — same info, fewer tokens.
```

- [ ] **Step 2: Commit**

```bash
rtk git add memory/decisions.md
rtk git commit -m "docs: record infrastructure overhaul decisions in memory"
```

---

## Execution Order

Tasks 1-2 are global config (no git). Tasks 3-9 are project files (committed).

Tasks 1 and 2 can run in parallel (independent files).
Task 3 (CLAUDE.md) is standalone.
Task 4 (hook) depends on nothing.
Task 5 (size guard) depends on nothing.
Task 6 (slash commands) depends on nothing.
Task 7 (permissions) depends on nothing.
Task 8 (test harness) depends on Task 4 (needs post-edit.sh to exist).
Task 9 (memory) depends on nothing but should be last (captures final decisions).

**Recommended parallel batches:**
1. Tasks 1 + 2 (global config, no git)
2. Tasks 3 + 4 + 5 + 6 + 7 (all independent project changes)
3. Task 8 (depends on task 4)
4. Task 9 (final)
