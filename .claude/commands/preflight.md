---
description: Force-run pre-design discipline before touching code
---

The user wants a preflight on this task:

$ARGUMENTS

## Your job

Before you touch any code, write out a short preflight analysis with **exactly these five sections**. Keep it terse — bullet points, not paragraphs. Do not start implementing until the user has seen this.

### 1. Requirements — said vs assumed

List every requirement that's in your head for this task. Tag each as **SAID** (user actually said it) or **ASSUMED** (you invented it). For every ASSUMED, write a one-line clarifying question OR cross it out and commit to dropping it.

Watch for these smells that usually indicate invention: *portable, automatic, reliable, cross-platform, backwards-compatible, graceful degradation, at the end of session, forever.*

### 2. Existing systems

Does the codebase already solve this problem, even partially? Grep/check for: existing hooks, existing config, existing storage, existing abstractions that fit. If yes, name them and say whether you'd **replace / augment / coexist** — don't quietly build alongside.

### 3. Mechanism sanity check

If the task or user framing proposes a specific mechanism (hook, cron, webhook, DB trigger, background job, whatever), verify the mechanism can actually do the job:

- Hooks run shell commands. They cannot make LLM judgments.
- Crons fire on schedule. They cannot react to events.
- Webhooks receive HTTP. They are not a scheduler.

If the mechanism is wrong, **say so and propose the right one**. Do not build a workaround around a broken premise.

### 4. Alternatives

List **2 or more** design options with a one-line tradeoff each. Then pick one with a one-line reason. Even for "obvious" choices — the exercise surfaces things you'd otherwise miss.

### 5. Risks & unknowns

What could bite you? What assumptions are unverified? What do you need to test before shipping? One bullet each, no filler.

---

End the preflight with: **"Proceed?"** Wait for explicit confirmation before making any edits. If the user says "proceed", start implementing. If they push back on any section, revise the preflight first.
