# Dependencies & Assumptions Checklist: GPU MVP Promotion

**Purpose**: Validate that the workstation prerequisites, upstream feature dependencies, and ambient-environment assumptions behind this validation/promotion slice are written precisely enough that a reviewer can falsify each one against the actual workstation state, and that none of them quietly grow into hidden in-scope work for this feature.
**Created**: 2026-05-18
**Feature**: [spec.md](../spec.md)

This checklist tests the *requirements writing* of the Assumptions block plus every cross-feature dependency the spec/plan reference (feature 020 stacked PRs, feature 007 evaluator, feature 016 warmup discipline, feature 005 voter config, host Ollama, ROCm/Paddle wheel, `.venv-paddle-rocm`, `scripts/start-host-ollama-rocm-wsl.sh`). It does not validate that any prerequisite is *installed* — that is a runbook concern. It validates that each prerequisite is *named, bounded, and verifiable on paper*.

## Workstation Runtime Prerequisites (Assumptions §1–§2)

- [ ] CHK001 Is the AMD ROCm runtime named with a sufficient version-pinning rule (or an explicit "matches features 014–019 conventions" cross-reference) so a reviewer can determine whether a given workstation qualifies? [Clarity, Spec §Assumptions]
- [ ] CHK002 Is the Paddle ROCm wheel (e.g., `paddlepaddle-dcu`) named with the same version-constraint discipline used in features 014–019 (no new pin, but an explicit pointer to the existing pin)? [Consistency, Spec §Assumptions, §FR-031]
- [ ] CHK003 Is `.venv-paddle-rocm` defined precisely enough (path convention, what makes an interpreter "equivalently explicit GPU environment") that an operator can verify its presence without consulting source code? [Clarity, Spec §Assumptions, §FR-003]
- [ ] CHK004 Is the carve-out "or an equivalently explicit GPU environment" bounded — i.e., is there a written rule for what makes an alternative interpreter equivalent (matching wheel, matching ROCm, matching device visibility)? [Clarity, Gap]
- [ ] CHK005 Is the relationship between `.venv-paddle-rocm` (interpreter) and the FR-001 Paddle preflight (gating check) explicit — i.e., is the interpreter the *carrier* of the gate, not a *separate* gate? [Consistency, Spec §Assumptions, §FR-001, §Clarifications Q3]
- [ ] CHK006 Is "workstation provisioning is out of scope for this feature" stated explicitly so a reviewer does not expect setup automation deliverables? [Clarity, Spec §Assumptions, §FR-032]

## Host Ollama Prerequisites (Assumptions §2)

- [ ] CHK007 Is `scripts/start-host-ollama-rocm-wsl.sh` named as the canonical host-Ollama starter, with the rationale (WSL Docker can't see the AMD GPU) cross-linked? [Clarity, Spec §Assumptions, Project CLAUDE.md "Runtime boundaries"]
- [ ] CHK008 Is the prohibition on running Ollama inside a WSL Docker container stated explicitly (not just implied by the "host" qualifier)? [Completeness, Spec §Assumptions]
- [ ] CHK009 Is the requirement that Ollama exposes "the extraction model with GPU placement" bound to the FR-002 wire check (`/api/ps` `size_vram == size`) without restating the rule (no synonym drift)? [Consistency, Spec §Assumptions, §FR-002]
- [ ] CHK010 Is the model identity ("the extraction model") resolved to the FR-002 voter-config-derivation rule (Clarifications Q5) rather than to a hardcoded model name? [Consistency, Spec §Assumptions, §Clarifications Q5]
- [ ] CHK011 Is the Ollama listening address (`http://localhost:11434`) stated as a localhost-only assumption that excludes remote Ollama, with no escape hatch? [Clarity, Spec §FR-002, §Assumptions]

## Feature-020 MVP Prerequisites (Assumptions §4–§5)

- [ ] CHK012 Is the feature-020 MVP slice's landing PR (PR #38) named explicitly so a reviewer can verify its presence on `main` before this feature is approved? [Clarity, Spec §Assumptions]
- [ ] CHK013 Is `RunSummary.SCHEMA_VERSION = 0.1.7` named as the exact required version, with no "≥ 0.1.7" hedge that would tolerate a future bump? [Clarity, Spec §Assumptions]
- [ ] CHK014 Are the four additive top-level `run_summary` fields (`evidence_gate_id`, `evidence_gate_state_counts`, `evidence_gate_documents`, `evidence_gate_suppressed_fallback_count`) enumerated identically in Assumptions and FR-025(d) / US5 Scenario 4? [Consistency, Spec §Assumptions, §FR-025]
- [ ] CHK015 Are the feature-020 stacked PRs (skip-fallback opt-in `--evidence-gate-skip-fallback` / `DARTWING_EVIDENCE_GATE_SKIP_FALLBACK`, CPU-safety guards US5, schema-preservation regression guards US6) enumerated as a closed list of dependencies? [Completeness, Spec §Assumptions]
- [ ] CHK016 Is the "if any of those are still in flight, this feature blocks on them" rule stated as a hard precondition (not soft guidance) so a reviewer can refuse approval until the closed list is on `main`? [Clarity, Measurability, Spec §Assumptions]
- [ ] CHK017 Is the `--evidence-gate-skip-fallback` flag name AND its env-var fallback name (`DARTWING_EVIDENCE_GATE_SKIP_FALLBACK`) reproduced identically wherever the opt-in surface is referenced (FR-026 area, US6 Scenario 4, Assumptions, runbook)? [Consistency, Spec §FR-026, §Assumptions]

## Feature-007 Evaluator Prerequisite (Assumptions §6)

- [ ] CHK018 Is the feature-007 vendor-identity evaluator named as the canonical scoring surface (no implicit alternative), so FR-019's "the existing vendor-identity evaluator" resolves to a single artifact? [Clarity, Spec §Assumptions, §FR-019]
- [ ] CHK019 Is the evaluator's surface bounded as *consumed unchanged* by this feature, with modification explicitly out of scope (cross-link to FR-031/FR-032)? [Consistency, Spec §Assumptions, §FR-031, §FR-032]
- [ ] CHK020 Are the evaluator outputs this feature relies on (per-document score, per-document pass flag) named explicitly so a reviewer can confirm the FR-019 two-metric gate has the inputs it needs? [Completeness, Spec §Assumptions, §FR-019, §FR-020]
- [ ] CHK021 Is the relationship between the evaluator and feature 020's `evidence_gate_documents` per-document table explicit — does the evaluator score against final payloads, against `evidence_gate_documents`, or both? [Clarity, Gap, Spec §FR-019]

## Feature-016 Warmup Discipline Prerequisite (Edge Cases, Risks)

- [ ] CHK022 Is the dependency on feature 016's `MIOPEN_FIND_MODE=2` warmup discipline (and its effect on the four-run benchmark's first-run-discard rationale) named, so a reviewer understands why FR-012's discipline exists? [Traceability, Gap, Spec §Edge Cases, §Risks]
- [ ] CHK023 Is the `~/.cache/miopen` / `~/.cache/comgr` OS cache surface (feature 016) named as an ambient prerequisite that the benchmark inherits but does not own? [Clarity, Spec §Risks]

## Feature-005 Voter-Config Prerequisite (FR-002 Clarification Q5)

- [ ] CHK024 Is the path to the active voter config (e.g., `src/dartwing_ocr/extract/voters/configs/*.yaml` per feature 005) named in a stable form that survives a reorganization of the extract module? [Clarity, Spec §FR-002, §Clarifications Q5]
- [ ] CHK025 Is the voter-config key that holds the model identity named precisely (e.g., the YAML key path) so an operator can extract the name without source-code consultation? [Clarity, Measurability, Spec §FR-002]
- [ ] CHK026 Is the "operator (or a shell helper outside the package) resolves the voter-config model name and queries Ollama" rule consistent with FR-032's "no new pipeline module" prohibition? [Consistency, Spec §FR-002, §FR-032]

## Jitter Band Threshold Form (Assumptions §7)

- [ ] CHK027 Is "no absolute threshold is set at the spec level — the jitter band IS the threshold" stated unambiguously in Assumptions, FR-015, and the Jitter Band entity, with no remnant percentage/seconds hint? [Consistency, Spec §Assumptions, §FR-015]
- [ ] CHK028 Is the "specific numeric form is resolved at `/speckit.plan` time" deferral explicit so a reviewer does not expect a numeric pin in the spec? [Clarity, Spec §Assumptions]

## Extraction-Profile Resolution (Assumptions §8)

- [ ] CHK029 Is the resolution path for `full-workstation` ("either already expands to a GPU-backed profile set OR will be updated by this feature's runbook") consistent with Clarifications Q4's "ollama@gpu only, full-workstation NOT used by the demo path in this feature" decision? [Consistency, Conflict, Spec §Assumptions, §Clarifications Q4]
- [ ] CHK030 Is the Assumptions §8 text reconciled with Q4 — i.e., is the `full-workstation` mention scoped to "not the demo path of this feature" so a reviewer cannot mistake it as a permitted demo lane? [Conflict, Spec §Assumptions, §Clarifications Q4]

## Falsifiability of Every Assumption

- [ ] CHK031 Are all eight Assumptions individually testable on paper — i.e., could a reviewer falsify each one against the recorded run state, voter config, or `git log` of `main` without running anything new? [Measurability, Spec §Assumptions]
- [ ] CHK032 Are the Assumptions free of soft-hedge language ("typically", "usually", "should") in normative positions, so each is a hard precondition for landing? [Clarity, Spec §Assumptions]

## Gaps to Flag

- [ ] CHK033 Is there a stated mechanism for a reviewer to record an Assumption as "verified" vs. "violated" against a candidate workstation (a sign-off line, a runbook checklist row)? [Gap, Measurability]
- [ ] CHK034 Is the dependency on `paddleocr>=3.5,<4` (used by PPStructureV3 and the OCR-only lane both) named explicitly in Assumptions, or only inherited from features 014–019 Active Technologies? [Gap, Traceability]
- [ ] CHK035 Is the dependency on `httpx>=0.27,<1` (used by feature 005 extractor; reachable by tests calling Ollama) named, or is it implicit from feature 005? [Gap, Traceability]

## Notes

- This checklist tests whether the *dependency* and *assumption* requirements are well-written — not whether the dependencies are currently satisfied on any given workstation.
- The principal failure mode here is silent prerequisite drift: a feature-020 stacked PR that lands after this feature freezes, an Ollama model rename, a Paddle wheel bump that changes the preflight semantics. Items CHK012–CHK017 and CHK022–CHK026 are the primary defense at the requirements-writing layer.
- Items CHK004, CHK021, CHK033–CHK035 are genuine gaps a future spec amendment may address; they are not blocking for `/speckit.implement`.
