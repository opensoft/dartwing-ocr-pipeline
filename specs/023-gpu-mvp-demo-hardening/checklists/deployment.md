# Deployment / Operability Requirements Quality Checklist: GPU MVP Demo Hardening

**Purpose**: Release-gate audit of deployment/operability requirements — runbook deliverable, prerequisite environment, host Ollama startup, Paddle ROCm venv, minimum Ollama version, ROCm/MIOpen caches, and the "fresh operator" promise (SC-001).
**Created**: 2026-05-24
**Feature**: [spec.md](../spec.md)

## Runbook Deliverable

- [ ] CHK001 Is the runbook target file (`docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md`) explicit, with the in-place extension semantics (not a new file)? [Clarity, Spec §Clarifications]
- [ ] CHK002 Is the runbook's required content scoped — every operator step the demo requires, plus every recovery action for every named failure class? [Completeness, Spec §FR-006/Dependencies]
- [ ] CHK003 Is the runbook required to document the minimum Ollama version, OLLAMA_CONTEXT_LENGTH, and Paddle ROCm venv name in a single visible place? [Completeness, Spec §FR-006/FR-023, Assumptions]
- [ ] CHK004 Is the relationship between this feature's runbook updates and the existing feature 021 runbook contents specified (additive only? superseding?)? [Consistency, Spec §Clarifications]

## Prerequisite Environment

- [ ] CHK005 Is the Paddle ROCm venv name (`.venv-paddle-rocm` or its successor) required to be documented as an operator prerequisite, with provisioning out of scope? [Completeness, Spec §FR-002, Assumptions]
- [ ] CHK006 Is the host Ollama startup script (`scripts/start-host-ollama-rocm-wsl.sh`) required to be invoked exactly as documented, with no alternative startup path supported? [Clarity, Spec §FR-006]
- [ ] CHK007 Is the operator obligation to start Ollama *before* invoking the demo command explicit, vs. the demo auto-starting Ollama? [Completeness, Spec §FR-006]
- [ ] CHK008 Are GPU-availability prerequisites (AMD `gfx1151`, WSL2 ROCm exposure) explicit, with bootstrapping out of scope? [Completeness, Spec §Assumptions]

## Minimum Ollama Version

- [ ] CHK009 Is the minimum Ollama version specified as a concrete value (e.g., `0.4.0`) somewhere — runbook or spec — before this feature lands? [Completeness, Spec §FR-023, Deferred]
- [ ] CHK010 Is the operator's upgrade path documented (e.g., re-run the startup script after upgrading Ollama; no in-script upgrade)? [Coverage — Recovery, Gap]
- [ ] CHK011 Is the version-discovery mechanism (`/api/version` endpoint or otherwise) required to be referenced in the runbook? [Completeness, Spec §FR-023, Gap]

## ROCm / MIOpen Cache Lifecycle

- [ ] CHK012 Are the ROCm/MIOpen cache locations (`~/.cache/miopen`, `~/.cache/comgr`) referenced as expected side effects, with operator awareness documented? [Completeness, Spec §Dependencies, Gap]
- [ ] CHK013 Are cache-clearance procedures documented (when to clear, how to verify), so operators do not blame the demo for cold-cache slowness? [Coverage — Recovery, Gap]
- [ ] CHK014 Is the spec explicit that cache state may affect the first of three SC-006 runs (cold-vs-warm), and that the smoke gate tolerates this? [Consistency, Spec §SC-006, Gap]

## "Fresh Operator" Promise (SC-001)

- [ ] CHK015 Is the "fresh operator" actor defined precisely — someone with workstation login but no prior interaction with this repo? [Clarity, Spec §SC-001]
- [ ] CHK016 Is the "without any undocumented commands or tribal knowledge" promise enforceable — i.e., is there a documented procedure for verifying the runbook is self-sufficient (e.g., a colleague who has never run this dry-runs the runbook)? [Measurability, Spec §SC-001, Gap]
- [ ] CHK017 Is the runbook required to include a troubleshooting section that maps each failure class (FR-016 closed vocabulary) to a recovery procedure? [Completeness, Spec §FR-016, Gap]

## Rollback / Unwind

- [ ] CHK018 Is the operator's path to *uninstall* or *back out* the demo specified, even if minimal (e.g., "no installation; just stop using the command")? [Coverage — Recovery, Gap]
- [ ] CHK019 Are requirements specified for backing out a partial-failure run (e.g., re-run handles it per FR-017; no manual git restore needed)? [Coverage — Recovery, Spec §FR-017]
- [ ] CHK020 Is the spec explicit that this feature does NOT introduce installable artifacts (no new system packages, no daemon, no service), so rollback is just "stop running the command"? [Clarity, Gap]

## Workstation Assumption

- [ ] CHK021 Is the spec explicit that the demo is *workstation-only* — not designed for production servers, multi-user hosts, or CI runners with GPU? [Clarity, Spec §Assumptions]
- [ ] CHK022 Are requirements specified for multi-workstation deployment (e.g., two different operators with two different Ollama configs) — or is multi-workstation out of scope? [Coverage — Edge Case, Spec §SC-006, Gap]

## CI / Automation Boundary

- [ ] CHK023 Is the spec explicit that the workstation manual GPU smoke (SC-008) is NOT a CI gate — it's a manual gate before adopting the demo as the integration-test checkpoint? [Clarity, Spec §SC-006/SC-008]
- [ ] CHK024 Are requirements specified for what *CI* runs vs. what the *workstation* runs, so the operator knows where each test runs? [Clarity, Spec §SC-008]

## Documentation Versioning

- [ ] CHK025 Is the runbook required to record the demo version (or commit SHA) it was authored against, so version drift between code and docs is detectable? [Coverage, Gap]
- [ ] CHK026 Are runbook update obligations on each FR change explicit (e.g., a change to FR-006 must update the runbook section on Ollama startup)? [Consistency, Spec §FR-006, Gap]

## Primary / Alternate / Exception / Recovery / Non-Functional Coverage

- [ ] CHK027 Are deployment requirements defined for the **primary** flow (operator on configured workstation following the runbook → success)? [Coverage — Primary, Spec §SC-001]
- [ ] CHK028 Are deployment requirements defined for **alternate** flows (operator with stale Paddle wheel; operator with new Ollama version; operator with custom voter config)? [Coverage — Alternate, Spec §Edge Cases]
- [ ] CHK029 Are deployment requirements defined for **exception** flows (every prerequisite missing in isolation)? [Coverage — Exception, Spec §FR-016]
- [ ] CHK030 Are deployment **recovery** requirements defined (how to recover from each prerequisite failure)? [Coverage — Recovery, Gap]
- [ ] CHK031 Are deployment **non-functional** properties specified (the runbook is self-contained; the demo introduces no daemons)? [Coverage — Non-Functional, Gap]

## Ambiguities & Conflicts

- [ ] CHK032 Is the spec consistent about whether the Docker Desktop / WSL container Ollama is *explicitly out of scope* (Assumptions, Out of Scope) and never an option for the demo? [Consistency, Spec §Out of Scope, Assumptions]
- [ ] CHK033 Is the relationship between the host Ollama startup script (operator-visible) and the demo command's readiness checks (which assume the script ran) made explicit, so an operator who skips the script gets a clear diagnostic? [Clarity, Spec §FR-006, FR-007]


---

**Plan coverage verification (2026-05-25):** see [plan-coverage.md](./plan-coverage.md) for the cross-reference of this checklist's items against `plan.md` / `research.md` / `data-model.md` / `contracts/` / `quickstart.md`.
