# Persistent Memory System

This project uses a file-based memory at `./memory/`, committed to the JobSearch repo alongside the code. Sync across machines happens via the same `git pull` / `git push` you already use for code. The harness auto-memory (`~/.claude/projects/.../memory/MEMORY.md`) is disabled globally via `autoMemoryEnabled: false` — `./memory/` is the only memory system for this project.

**Why in-repo instead of a separate private repo:** JobSearch is already private, memory history correlates usefully with code history, there's no extra repo to clone on new machines, and the sync flow is already part of daily work. Trade-off: never put secrets or anything you wouldn't want a future collaborator to see in these files. If something is genuinely sensitive, don't save it to memory at all.

## The four files

1. `memory/user.md` — who the user is, background, goals, expertise
2. `memory/preferences.md` — how to work (tone, tools, workflows, dos/donts)
3. `memory/decisions.md` — architectural/process decisions with `**Why:**` + `**How to apply:**`
4. `memory/people.md` — collaborators, stakeholders, contacts

## How memory gets loaded

A `SessionStart` hook (`.claude/hooks/session-start-inject-memory.sh`) reads all four files and injects them as `additionalContext` on every session start. **No action required from me** — the content arrives in context automatically. Treat it as authoritative; if it disagrees with the current state of the code, trust the code and update the memory entry.

## How memory gets updated

Two pathways, both explicit — **there is no end-of-session auto-update hook**, because the earlier attempts (Stop-block every session) created noise and friction. Recognition, not schedule, is the right trigger.

1. **`/remember <what>`** — slash command. Use this mid-session whenever something worth persisting comes up. It picks the right file, deduplicates against existing entries, and keeps entries terse.

2. **Organic updates** — when a conversation surfaces a correction, a confirmed non-obvious preference, or a real decision with a clear *why*, proactively edit the relevant file without waiting for `/remember`.

## Update discipline

- **Edit existing entries in place** before appending new ones.
- **Date entries** in `decisions.md` with `## YYYY-MM-DD —` headings so staleness is visible.
- **Keep entries terse.** One fact per entry.
- **Remove entries that are now wrong** — don't just append corrections.
- **Skip ephemeral task state.** If it won't matter in a future session, don't save it.
- **Never commit secrets via memory.** Plaintext, in-repo, treated as code-visible context.

## CI/CD for this project's Claude workflow

Three slash commands / scripts support the workflow defined in `~/.claude/CLAUDE.md`:

- **`/preflight <task>`** — force-run the pre-design discipline rules before any non-trivial change.
- **`/retro`** — forced self-evaluation pass before declaring a task done.
- **`.claude/hooks/test-all.sh`** — pipe-tests every hook in `.claude/hooks/` so regressions (missing tools, broken JSON output) get caught immediately.

## Tooling gaps on this machine

- **No `jq` in Git Bash.** Use `sed` or `python -c 'import json,sys; ...'` for JSON in shell scripts.
- **Windows directory junctions** need PowerShell (`New-Item -ItemType Junction`) or `.NET Directory.Delete`, not `cmd /c mklink` from Git Bash — path translation breaks it.
