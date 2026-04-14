# speckit

This repo-local Codex plugin exposes the Speckit workflows already wrapped under `.codex/skills/` as installable slash commands.

The active skill implementations live under `plugins/speckit/skills/` and retain their existing `agents/openai.yaml` metadata, including the slash-style display labels such as `/speckit.specify` and `/speckit.plan`.

Worktree helpers:
- `/ct` returns the latest Speckit worktree jump target and the exact `cd` command to use
- `/ctp` shows the latest Speckit worktree path and metadata
