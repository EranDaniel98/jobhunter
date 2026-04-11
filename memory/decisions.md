# Decisions

Architectural, product, or process decisions and the reasoning behind them. Each entry should capture the *why*, not just the *what*, so edge cases can be judged later.

## 2026-04-11 — Project memory lives in-repo at `./memory/`, loaded via `SessionStart` hook

**What:** Four typed markdown files (`user.md`, `preferences.md`, `decisions.md`, `people.md`) committed to the JobSearch private repo. A `SessionStart` hook (`.claude/hooks/session-start-inject-memory.sh`) reads all four files at session start and injects their contents as `hookSpecificOutput.additionalContext` — no action required from Claude. Updates happen via the `/remember` slash command or organic proactive edits. The harness auto-memory is disabled globally (`autoMemoryEnabled: false`) so this is the only memory system for this project.

**Why:** Considered four storage options — harness auto-memory (per-machine, not portable), OneDrive + junction (sync conflicts, no real history, junction doesn't travel across machines anyway), a separate private git repo (extra repo to clone and maintain), or committing in-repo (picked). In-repo won because JobSearch is already private, memory history usefully correlates with code history, cross-machine sync uses the same `git pull`/`git push` already in the workflow, and there's no extra repo to manage. Trade-off accepted: never put secrets in memory; if JobSearch ever goes public, memory leaks; future collaborators see the contents — usually fine because memory is project context, not personal secrets.

**How to apply:** For other "persistent project context" needs on private repos, default to committing in-repo rather than spinning up storage. Only add a separate repo or external sync when the content is genuinely per-user or per-machine, or when the main repo's visibility policy might change.

## 2026-04-11 — No automated end-of-session memory update trigger

**What:** There is no Stop, SessionEnd, or PreCompact hook that updates memory. Updates happen only via `/remember` or organic mid-session edits.

**Why:** First attempt used a Stop hook that blocked once per session via a sentinel file, forcing Claude to update memory before every stop. Abandoned because: (1) it fired on every session including 30-second trivial ones, creating a friction tax the base rate of "worth persisting" didn't justify, (2) the forced ritual incentivized saving noise just to make the interruption feel productive, degrading signal-to-noise, and (3) no automated trigger can actually judge whether a session produced memory-worthy insight — that's an LLM decision. Also considered PreCompact: rejected because `additionalContext` reaches the model *after* compaction, by which point the raw information needed to write memory entries is already condensed away. Recognition, not schedule, is the right trigger.

**How to apply:** For any "do X at end of session / on schedule" feature where X requires LLM judgment, default to *no automation*. Provide an explicit slash command so the user or Claude can invoke it on recognition. Hooks are good for deterministic side effects (formatting, logging, injection), not for judgment calls. If you catch yourself building a sentinel-and-block pattern to work around a framing, stop and question the framing.
