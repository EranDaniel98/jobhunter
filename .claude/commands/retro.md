---
description: Forced self-evaluation before declaring a task done
---

The user is asking you to retro on the work you just did$ARGUMENTS.

## Your job

Run an honest self-review. Not a summary of what you did — a critique of whether it was good. Write **exactly these sections**, terse:

### Score: X/10

Pick a number. Not 10 unless you genuinely mean it. Anchor honestly:
- **10** = exactly what a skeptical reviewer would have done, no shortcuts, every risk handled
- **7** = works, but has known gaps you'd fix in a real-world deployment
- **5** = works for the happy path but will bite you within a week
- **3** = technically runs but the design is wrong

### What a skeptical reviewer would criticize

Be specific. Name files and lines. "Overbuilt" is not enough — say what was overbuilt and what the simpler version would be.

### Unverified assumptions

What did you take on faith that you didn't prove? e.g., "assumed OneDrive would sync atomically", "assumed the hook watcher picks up new settings mid-session", "assumed jq is installed".

### Load-bearing shortcuts

What shortcuts did you take that would become problems later? Flag them now so you and the user can decide whether to fix or accept them.

### What would make this a 10/10?

The concrete list of changes that would move the score up. Rank them rough effort-vs-value.

### Invented requirements audit

Go through every requirement that shaped the design. For each, was it **said** by the user or **assumed** by you? If anything assumed survived into the final design without being confirmed, call it out explicitly.

---

Be honest. A retro that scores everything 9/10 with no criticism is worse than not running one — it trains the user to distrust the scores. If the work was a 5, say 5.
