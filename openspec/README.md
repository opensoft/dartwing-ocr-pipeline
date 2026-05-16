# OpenSpec Workflow

OpenSpec is the change-governance layer for this repository. It captures the
intent, scope, and design decisions for non-trivial work before implementation.

Speckit remains the implementation layer. Use Speckit to create feature
worktrees, produce implementation plans and task lists, and drive code changes.

## When To Use OpenSpec

Create or update an OpenSpec change before implementation when the work affects
one of these project boundaries:

- stage 1 artifact schemas or folder contracts
- runtime/container/model orchestration
- consensus, routing, review, or escalation policy
- Jetson/edge deployment constraints
- changes to the development workflow itself

Skip OpenSpec for small implementation-only fixes where the existing `specs/`
artifact already defines the behavior and no product or architecture decision is
being made.

## Handoff To Speckit

OpenSpec should not duplicate Speckit task lists. The expected handoff is:

1. Capture the decision in `openspec/changes/<change-name>/`.
2. Ensure the decision is consistent with `docs/stage1-vendor-identity/` and
   `.specify/memory/constitution.md`.
3. Start or update exactly one Speckit feature under `specs/NNN-*` for the
   implementation work.
4. Archive the OpenSpec change after the corresponding Speckit work and PR land.

## CLI

Run OpenSpec from the bench/workbench container, not from the lightweight
Dartwing project container. The expected bench image provides `openspec` on
`PATH`; the current workbench-compatible version is `1.3.1`.
