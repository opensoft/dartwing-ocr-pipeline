---
name: "speckit-taskstoissues"
description: "Codex wrapper for the Speckit task-to-issues workflow."
---

# speckit-taskstoissues

Slash label: `/speckit.taskstoissues`.

Use `../../../.agents/skills/speckit-taskstoissues/SKILL.md` as the source workflow.

Rules:
- Read the source skill before doing anything else.
- Pass any text after `/speckit.taskstoissues` through as the original command input for the source skill.
- Execute the source skill exactly, including issue conversion and sync behavior.
