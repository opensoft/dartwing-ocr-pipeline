---
name: "speckit-clarify"
description: "Codex wrapper for the Speckit clarification workflow."
---

# speckit-clarify

Slash label: `/speckit.clarify`.

Use `../../../../.agents/skills/speckit-clarify/SKILL.md` as the source workflow.

Rules:
- Read the source skill before doing anything else.
- Pass any text after `/speckit.clarify` through as the original command input for the source skill.
- Execute the source skill exactly, including clarification handling and spec updates.
