---
name: "speckit-tasks"
description: "Codex wrapper for the Speckit task generation workflow."
---

# speckit-tasks

Slash label: `/speckit.tasks`.

Use `../../../../.agents/skills/speckit-tasks/SKILL.md` as the source workflow.

Rules:
- Read the source skill before doing anything else.
- Pass any text after `/speckit.tasks` through as the original command input for the source skill.
- Execute the source skill exactly, including prerequisite checks and task generation.
