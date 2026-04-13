---
name: "speckit-checklist"
description: "Codex wrapper for the Speckit checklist workflow."
---

# speckit-checklist

Slash label: `/speckit.checklist`.

Use `../../../../.agents/skills/speckit-checklist/SKILL.md` as the source workflow.

Rules:
- Read the source skill before doing anything else.
- Pass any text after `/speckit.checklist` through as the original command input for the source skill.
- Execute the source skill exactly, including checklist creation or append behavior.
