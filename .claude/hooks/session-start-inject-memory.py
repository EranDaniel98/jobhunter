"""SessionStart hook body: read memory/*.md and emit JSON to stdout.

Called by session-start-inject-memory.sh. Kept as a standalone .py file
(not an inline python -c) to avoid f-string escaping hell.
"""

import json
import pathlib

BASE = pathlib.Path("C:/Users/Eran/Desktop/Personal/JobSearch/memory")
FILES = ["user.md", "preferences.md", "decisions.md", "people.md"]


def main() -> None:
    parts = ["# Persistent project memory (loaded by SessionStart hook)"]
    for name in FILES:
        path = BASE / name
        if not path.exists():
            continue
        body = path.read_text(encoding="utf-8")
        parts.append(f"\n## === {name} ===\n{body}")

    content = "\n".join(parts)
    out = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": content,
        }
    }
    print(json.dumps(out))


if __name__ == "__main__":
    main()
