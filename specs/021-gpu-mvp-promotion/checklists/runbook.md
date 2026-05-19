# Demo Runbook Quality Checklist: GPU MVP Promotion

**Purpose**: Validate that the demo-runbook requirements (FR-025 plus US5 plus SC-008) are written so a new operator can complete the MVP demo end-to-end using only the runbook — readiness gate first, GPU profiles only, no CPU fallback, observability surfaced, scratch-copy discipline enforced.
**Created**: 2026-05-18
**Feature**: [spec.md](../spec.md)

This checklist tests the *requirements writing* of the runbook deliverable — not the runbook content itself. Items target completeness, clarity, consistency, and measurability of the runbook contract.

## Readiness-First Structure (FR-025(a))

- [X] CHK001 Is the requirement explicit that the runbook STARTS with the FR-001 + FR-002 readiness checks (not just contains them somewhere)? [Clarity, Spec §FR-025(a), §US5 Scenario 1]
- [X] CHK002 Is the order (Paddle preflight FIRST, then Ollama check) specified, or are the two checks unordered? [Clarity, Gap]
- [X] CHK003 Is the requirement that the demo MUST NOT proceed under degraded conditions (US5 Scenario 3) consistent with FR-004 fail-fast? [Consistency, Spec §FR-025, §US5, §FR-004]
- [X] CHK004 Is the runbook required to explain readiness *failures* with operator-actionable remediation, not only the success path? [Coverage, Spec §US5 Scenario 3]

## Profile Specification (FR-025(b))

- [X] CHK005 Is FR-025(b)'s preprocessing profile `ppstructurev3@gpu` named identically in FR-025, US5 narrative, and US5 scenario 2? [Consistency, Spec §FR-025(b)]
- [X] CHK006 Is FR-025(b)'s extraction profile `ollama@gpu` named identically across all references (post-Clarifications), with NO residual `full-workstation` references in the documented demo path? [Consistency, Spec §FR-025(b), §Clarifications]
- [X] CHK007 Is the `full-workstation` exclusion stated explicitly in FR-025 ("the `full-workstation` preset is NOT used in this feature's documented demo path") so a reviewer can falsify a slip? [Clarity, Spec §FR-025(b)]
- [X] CHK008 Is the prohibition on profile substitution (e.g., switching to `ppstructurev3@cpu` for a "quick demo") stated in FR-025(c) or elsewhere? [Coverage, Spec §FR-025(c)]

## CPU-Fallback Prohibition (FR-025(c))

- [X] CHK009 Is "contains no CPU fallback commands" measurable against the runbook text alone (a reviewer can grep for `@cpu`, `stub`, or `cpu-fallback` and confirm zero matches)? [Measurability, Spec §FR-025(c)]
- [X] CHK010 Is the prohibition extended to inline alternatives (e.g., "if GPU fails, try …") — i.e., the runbook contains no degraded path? [Coverage, Spec §FR-025(c)]
- [X] CHK011 Is the boundary between the *demo* runbook (no CPU) and *operator/CI* runbooks (may still document CPU paths) explicit? [Clarity, Spec §FR-025, §FR-030]

## Observability Field Coverage (FR-025(d))

- [X] CHK012 Are the seven required `run_summary` observability fields (`schema_version`, `preprocess_lane`, `preprocess_strategy_id`, `evidence_gate_id`, `evidence_gate_state_counts`, `evidence_gate_documents`, `evidence_gate_suppressed_fallback_count`) enumerated identically in FR-025(d) and US5 scenario 4? [Consistency, Completeness, Spec §FR-025(d)]
- [X] CHK013 Is the requirement to *surface* (operator reads/interprets) distinct from merely emit (system writes) — is the runbook obliged to explain each field's meaning? [Clarity, Spec §FR-025(d), §US5 Scenario 4]
- [X] CHK014 Is the runbook required to explain how to *read* each field "for the audience" (US5 scenario 4) — i.e., is reader-facing context required, not just field names? [Clarity, Spec §US5 Scenario 4]
- [X] CHK015 Is the field list a closed set, or could a reviewer mistake it for a minimal subset that could be augmented? [Clarity, Spec §FR-025(d)]

## Suppression Demonstration (FR-025(e))

- [X] CHK016 Is the requirement to show "whether suppression occurred" (US5 scenario 5) testable from the runbook — does the runbook tell the operator *how* to look at `evidence_gate_suppressed_fallback_count`? [Clarity, Spec §FR-025(e), §US5 Scenario 5]
- [X] CHK017 Is the requirement to show "fallback counts remained correct" defined precisely — which `*_count` fields, against which expected values? [Clarity, Gap]
- [X] CHK018 Is the demonstration required for both the suppression-occurring case AND the no-suppression case, or only the former? [Coverage, Gap]

## Scratch-Copy Discipline in Demo (FR-025(f))

- [X] CHK019 Is the runbook required to *direct* the operator to use `/tmp` scratch copies (not merely "permit" them)? [Clarity, Spec §FR-025(f)]
- [X] CHK020 Is the prohibition against mutating `tests/stage1_vendor_identity/` (FR-018 echo) repeated in the runbook itself, or only in the spec? [Coverage, Spec §FR-025(f), §FR-018]
- [X] CHK021 Is the scratch-copy rule consistent across US3 (benchmark), US5 (demo), FR-018, FR-025(f), and SC-011? [Consistency, Spec-wide]

## New-Operator Self-Sufficiency (SC-008)

- [X] CHK022 Is SC-008's "new operator can complete the demo end-to-end using only the runbook (no source-code consultation required)" measurable via a dry-run inspection of the runbook against a checklist of required operations? [Measurability, Spec §SC-008]
- [X] CHK023 Is the runbook required to assume a specific operator skill floor (e.g., comfortable with `git`, `python`, `curl`), or is the runbook self-contained even for that? [Clarity, Gap]
- [X] CHK024 Is the runbook required to include verification steps (operator confirms preflight success, operator confirms `size_vram == size`) inline, or to defer them to external docs? [Coverage, Spec §SC-008, §FR-025(a)]
- [X] CHK025 Is the runbook required to define a "demo failure" exit path — what does the operator do when readiness fails, when the demo errors mid-run, when the demo completes but observability looks wrong? [Coverage, Gap]

## Runbook Surface and Owner

- [X] CHK026 Is the canonical runbook file path named (e.g., `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md`), or is the runbook's location left implicit? [Clarity, Gap]
- [X] CHK027 Is the relationship between this runbook and existing operator docs (e.g., `docs/stage1-vendor-identity/ollama-runtime.md`, `docs/stage1-vendor-identity/gpu-warmup-and-cache.md`) explicit — supersede, supplement, or cross-reference? [Clarity, Gap]
- [X] CHK028 Is the requirement explicit that the runbook is a deliverable of THIS feature (FR-025) and not a hand-off to a future doc-only feature? [Clarity, Spec §FR-025]
- [X] CHK029 Is the runbook's update lifecycle defined (e.g., is it re-validated when a future feature changes `evidence_gate_id` or adds a `phase_timings.*` key)? [Coverage, Gap]

## US5 Scenario Coverage

- [X] CHK030 Are all six US5 scenarios (readiness step, GPU profiles only, fail-fast on missing prereq, observability fields surfaced, suppression demonstration, scratch discipline) each tied to a sub-clause of FR-025? [Traceability, Spec §US5, §FR-025]
- [X] CHK031 Is US5 scenario 3's "deliberately missing GPU prerequisite" path consistent with FR-004 (fail-fast names the unmet prerequisite)? [Consistency, Spec §US5 Scenario 3, §FR-004]
- [X] CHK032 Is US5 scenario 6's "outputs land under `/tmp` or another explicit scratch root" testable from the runbook commands alone (paths are visible)? [Measurability, Spec §US5 Scenario 6]

## Demo Audience and Framing

- [X] CHK033 Is the audience for the demo defined (internal reviewer, external stakeholder, both)? [Clarity, Gap]
- [X] CHK034 Are the demo's purpose statements (validate GPU posture, show observability, demonstrate suppression) tied to which artifacts the audience inspects? [Coverage, Gap]
- [X] CHK035 Is the demo length / duration bounded — i.e., is the operator told the expected wall-time so a slow demo is recognizable as a finding? [Coverage, Gap]

## Promotion Decision Visibility in Runbook (FR-026 / FR-028 echo)

- [X] CHK036 Is the requirement that the promotion decision is recorded in the runbook (FR-026) consistent with FR-028 (if promote, explicit-off legacy path is documented in the runbook)? [Consistency, Spec §FR-026, §FR-028]
- [X] CHK037 Is the runbook required to clearly differentiate "stay opt-in" demo behavior from "promote to default" demo behavior — operator can see which mode is active? [Coverage, Spec §FR-028, §US6]

## Gaps to Flag

- [X] CHK038 Is the case "demo runbook executed without the workstation having the Paddle ROCm wheel installed" addressed — does the runbook tell the operator to install the wheel, or assume it's there? [Gap, Coverage]
- [X] CHK039 Is the case "demo runbook executed against a workstation where another team member is running Ollama with a different model" addressed (multi-user contention)? [Gap, Coverage]
- [X] CHK040 Are requirements defined for an "abort and clean up" path — what does the operator do mid-demo to leave the workstation in a clean state? [Gap, Recovery Flow]
- [X] CHK041 Is the requirement explicit that the runbook contains the exact `curl` command (or equivalent) for the FR-002 Ollama check, not just a reference to FR-002? [Coverage, Gap]

## Notes

- This checklist tests whether the runbook's *requirements* are well-written, not whether the runbook content is correct (the content is a downstream deliverable).
- The principal failure mode is silent runbook drift — e.g., a contributor adding a "if GPU is slow, try CPU" alternative; CHK009–CHK011 and CHK037 are the defense at the requirements layer.
- Items CHK023, CHK026, CHK038–CHK041 flag genuine gaps that may benefit from a spec amendment or planning-time decision.
