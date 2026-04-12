---
description: Create a pull request with auto-generated description
---

Create a pull request for the current branch.

$ARGUMENTS

## Steps

1. Determine base branch: use $ARGUMENTS if provided, otherwise default to `main`
2. Check if branch has a remote tracking branch. If not, push with `-u`
3. Gather context:
   - `git log <base>..HEAD --oneline` — all commits on this branch
   - `git diff <base>...HEAD --stat` — files changed summary
4. Generate PR title: conventional-commit style, under 70 characters, based on the commits
5. Generate PR body using this format:
   ```
   ## Summary
   <2-4 bullet points summarizing the changes>

   ## Test plan
   <bulleted checklist of testing items>
   ```
6. Create the PR: `gh pr create --title "<title>" --body "<body>"`
7. Return the PR URL
