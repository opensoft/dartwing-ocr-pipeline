---
name: "speckit-ctp"
description: "Show the latest Speckit worktree path and metadata."
---

# speckit-ctp

Slash label: `/ctp`.

Use this command when you want the latest Speckit worktree details without the "jump there" framing.

Rules:
- Run `.specify/extensions/git/scripts/bash/get-last-worktree.sh --json`.
- Parse the returned JSON and report:
  - `WORKTREE_PATH`
  - `BRANCH_NAME`
  - `BASE_BRANCH`
  - `SOURCE`
- If the current checkout path already equals `WORKTREE_PATH`, state that the user is already in the correct worktree.
- Otherwise, state:
  - the resolved worktree path
  - the branch name
  - the base branch
  - whether the result came from the recorded handoff state or the worktree-root fallback
  - that `/ct` is the shorter jump helper
- If no recent Speckit worktree can be resolved, say that clearly and do not invent a path.
