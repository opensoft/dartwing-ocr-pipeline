---
name: "speckit-ct"
description: "Resolve the latest Speckit worktree jump target."
---

# speckit-ct

Slash label: `/ct`.

Use this command as the terse "take me to the current Speckit worktree" helper after `/speckit.specify`.

Rules:
- Run `.specify/extensions/git/scripts/bash/get-last-worktree.sh --json`.
- The helper resolves the latest worktree from the recorded handoff state when available, and otherwise falls back to the configured Speckit worktree root.
- Parse the returned JSON and focus on:
  - `WORKTREE_PATH`
  - `BRANCH_NAME`
- If the current checkout path already equals `WORKTREE_PATH`, state that the user is already in the correct worktree.
- Otherwise, clearly state:
  - the resolved worktree path
  - that slash commands cannot change the user's current shell directory automatically
  - the exact `cd <WORKTREE_PATH>` command
  - that the user can use `/ctp` when they want the full path/branch/base-branch details instead
- If no handoff file exists, say that no recent Speckit worktree has been recorded yet.
