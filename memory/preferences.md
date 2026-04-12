# Preferences

How the user wants me to work: tone, verbosity, tools, workflows, things to do/avoid. Updated when corrections or confirmations reveal a preference.

## Environment constraints

- **No `jq` in Git Bash.** The Windows Git Bash on this machine doesn't have `jq` installed — commands that pipe to `jq` fail with `jq: command not found`. For JSON extraction in shell (especially hook scripts), use `sed` or `python -c 'import json,sys; ...'` instead.
  **Why:** Discovered 2026-04-11 while pipe-testing the memory-update Stop hook — had to rewrite the session_id extraction with sed.
  **How to apply:** Default to sed/python for JSON in any hook script or one-off bash command on this machine. Don't assume jq just because it's standard on Linux.
