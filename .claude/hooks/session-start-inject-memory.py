"""SessionStart hook body: read memory/*.md and emit JSON to stdout.

Called by session-start-inject-memory.sh. Kept as a standalone .py file
(not an inline python -c) to avoid f-string escaping hell.

Usage: python session-start-inject-memory.py <path-to-memory-dir>
"""

import json
import pathlib
import sys

FILES = ["user.md", "preferences.md", "decisions.md", "people.md"]


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: session-start-inject-memory.py <memory-dir>", file=sys.stderr)
        sys.exit(1)

    base = pathlib.Path(sys.argv[1])
    parts = ["# Persistent project memory (loaded by SessionStart hook)"]
    for name in FILES:
        path = base / name
        if not path.exists():
            continue
        body = path.read_text(encoding="utf-8")
        parts.append(f"\n## === {name} ===\n{body}")

    content = "\n".join(parts)

    # Size guard: if content exceeds 8000 chars, use TOC only
    if len(content) > 8000:
        toc_lines = ["# Persistent project memory (loaded by SessionStart hook)", ""]
        toc_lines.append("## Table of Contents")
        toc_lines.append("")
        toc_lines.append("| File | Lines | Summary |")
        toc_lines.append("|------|-------|---------|")

        for name in FILES:
            path = base / name
            if not path.exists():
                continue

            body = path.read_text(encoding="utf-8")
            line_count = len(body.splitlines())

            # Find first non-empty, non-comment line (first heading or first content)
            first_content = ""
            for line in body.splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    first_content = stripped[:50]  # Truncate to 50 chars
                    if len(stripped) > 50:
                        first_content += "..."
                    break

            if not first_content:
                # If no content line, use first heading
                for line in body.splitlines():
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        first_content = stripped[1:].strip()[:50]
                        if len(stripped) > 51:
                            first_content += "..."
                        break

            toc_lines.append(f"| {name} | {line_count} | {first_content} |")

        toc_lines.append("")
        toc_lines.append("Memory files exceed 8000 chars. Use Read tool to load specific files on demand.")
        content = "\n".join(toc_lines)

    out = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": content,
        }
    }
    print(json.dumps(out))


if __name__ == "__main__":
    main()
