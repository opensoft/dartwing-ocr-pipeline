# Promotion Decision Checklist: GPU MVP Promotion

**Purpose**: Validate that the requirements for the skip-fallback promotion decision (binary stay-opt-in / promote-to-default, explicitly gated by the FR-019 verdict, never automatic) are written precisely enough that the operational posture is determinable from the recorded artifacts without consulting the team.
**Created**: 2026-05-18
**Feature**: [spec.md](../spec.md)

This checklist tests the *requirements writing* of the promotion-decision surface — not the decision itself. Items target completeness, clarity, consistency, and measurability of FR-026 through FR-029, US6, the Promotion Decision Record entity, and the SC-009 acceptance bar.

## Binary Decision Requirement (FR-026)

- [X] CHK001 Is the promotion decision required to be EXACTLY binary (stay opt-in / promote to default), with no third option (e.g., "promote with caveats", "partial promotion")? [Clarity, Spec §FR-026]
- [X] CHK002 Is the recording medium for the decision specified as BOTH feature-020 Appendix B AND the demo runbook, not either-or? [Completeness, Spec §FR-026]
- [X] CHK003 Is "explicit" defined in FR-026 — does the decision text need to literally name one of the two options, or can it be inferred from context? [Clarity, Spec §FR-026]
- [X] CHK004 Is the decision required to cite the FR-019 verdict that gated it (so a reader can trace the decision back to the underlying evidence)? [Traceability, Spec §FR-026, §SC-009]

## Verdict-Gated Permission (FR-027)

- [X] CHK005 Is FR-027 explicit that FAIL → "stay opt-in" is mandatory (not just preferred)? [Clarity, Spec §FR-027]
- [X] CHK006 Is FR-027 explicit that BLOCKED → "stay opt-in" is mandatory (BLOCKED is treated identically to FAIL for the promotion gate)? [Clarity, Spec §FR-027]
- [X] CHK007 Is "promotion is not a permitted option" stated in both FR-027 and US6 scenario 1, with no allowance for override? [Consistency, Spec §FR-027, §US6 Scenario 1]
- [X] CHK008 Is the case "FR-019 verdict is PASS" stated as PERMITTING promotion (FR-027 narrative + US6 scenario 2) but not REQUIRING it (FR-029)? [Consistency, Spec §FR-027, §FR-029]
- [X] CHK009 Is the case "FR-019 has not been run / no recorded verdict" addressed — is the implicit default "stay opt-in", or is the spec ambiguous? [Coverage, Gap]

## Explicit-Off Legacy Path (FR-028)

- [X] CHK010 Is FR-028 explicit that the legacy path is required ONLY when "promote to default" is the recorded decision? [Clarity, Spec §FR-028]
- [X] CHK011 Is "explicit-off legacy path" defined operationally — a flag, an env var, or both? [Clarity, Spec §FR-028]
- [X] CHK012 Is the requirement that the legacy path be "exercised in at least one test" tied to a specific test framework or test location, or left to planning? [Clarity, Spec §FR-028, §SC-009]
- [X] CHK013 Is the case "promote to default chosen, but legacy path not yet implemented" addressed — does the promotion decision require the legacy path to be in place AT decision time, or does the decision permit deferred implementation? [Coverage, Gap]
- [X] CHK014 Is the legacy-path test required to PASS (not merely exist), per SC-009 "exercised by at least one test that passes"? [Consistency, Spec §FR-028, §SC-009]

## No-Automatic-Promotion Rule (FR-029)

- [X] CHK015 Is FR-029 stated as a strict prohibition — a PASS verdict alone MUST NOT promote skip-fallback, even if every other condition is met? [Clarity, Spec §FR-029]
- [X] CHK016 Is "explicit team decision" defined operationally — what artifact constitutes the team's decision (commit message, Appendix B edit, separate decision doc)? [Clarity, Gap]
- [X] CHK017 Is the boundary between "FR-019 verdict computation" (mechanical) and "promotion decision" (deliberative) explicit? [Clarity, Spec §FR-029]
- [X] CHK018 Is the requirement that the promotion-to-default code change (toggling the default) be ATOMIC with the recorded decision, or could the default flip silently before/after the decision is recorded? [Coverage, Gap]

## Promotion Decision Record Entity

- [X] CHK019 Is the Promotion Decision Record entity defined with all four components (binary decision, gating verdict, rationale, explicit-off legacy-path documentation when promoted)? [Completeness, Spec §Key Entities]
- [X] CHK020 Is the "rationale" component required to cite WHY the team chose stay-opt-in vs. promote-to-default (not only WHAT was chosen)? [Clarity, Spec §Key Entities]
- [X] CHK021 Is the recording-medium duplication (Appendix B AND runbook) addressed as "the same record" or "two synchronized records"? [Clarity, Consistency, Spec §FR-026, §Key Entities]

## US6 Acceptance Scenarios

- [X] CHK022 Are all four US6 scenarios (FAIL/BLOCKED → stay opt-in, PASS → binary choice with rationale, promote-to-default operational state, stay-opt-in operational state) each tied to at least one FR? [Traceability, Spec §US6]
- [X] CHK023 Is US6 scenario 3's three-part promote-to-default state (skip-fallback on by default + explicit-off legacy path available + at least one test exercises legacy) testable from a single inspection of code + tests + runbook? [Measurability, Spec §US6 Scenario 3]
- [X] CHK024 Is US6 scenario 4's stay-opt-in state ("`--evidence-gate-skip-fallback` / `DARTWING_EVIDENCE_GATE_SKIP_FALLBACK` remains the only way to enable skip-fallback") consistent with feature-020's opt-in surface? [Consistency, Spec §US6 Scenario 4, §Assumptions]

## Acceptance Criteria for Promotion (SC-009)

- [X] CHK025 Is SC-009's "explicit binary promotion decision … is recorded" measurable against the two recording media (Appendix B + runbook) jointly? [Measurability, Spec §SC-009]
- [X] CHK026 Is SC-009's "cites the FR-019 verdict" testable by inspecting the Appendix B + runbook text for the verdict reference? [Measurability, Spec §SC-009]
- [X] CHK027 Is SC-009's "If 'promote to default' was chosen, an explicit-off legacy path is documented AND exercised by at least one test that passes" measurable from a closed inspection list (decision text + code + tests + CI output)? [Measurability, Spec §SC-009]

## Boundary with Operational Behavior

- [X] CHK028 Is the promotion-to-default code change (single inverted default) defined narrowly enough that a reviewer can verify it doesn't pull in unrelated behavior (telemetry, dashboards, new modes)? [Coverage, Spec §FR-032]
- [X] CHK029 Is the promotion-to-default required to preserve all existing feature-020 observability surfaces (no field removal, no schema change)? [Consistency, Spec §FR-031, §FR-032]
- [X] CHK030 Is the promotion-to-default required to preserve the existing `--evidence-gate-skip-fallback` / env-var surface, just inverted (the same surface continues to exist; only its default changes)? [Coverage, Gap]

## Risk Coverage

- [X] CHK031 Is the PRD §Risks item "GPU demos lose credibility if a command silently runs CPU" mitigated by ensuring the promote-to-default option doesn't disable GPU readiness checks for skip-fallback paths? [Coverage, Gap]
- [X] CHK032 Is the risk that "PASS verdict on a tiny benchmark subset leads to inappropriate promotion of broad skip-fallback behavior" addressed — is the verdict explicitly subset-scoped (the benchmark subset, not all corpus)? [Coverage, Spec §FR-019, §FR-013]
- [X] CHK033 Is the risk of promotion-decision drift (Appendix B says one thing, runbook says another) addressed — is single-source-of-truth or synchronized-recording required? [Coverage, Gap]

## Fallback Compatibility

- [X] CHK034 Is the spec's Fallback discipline (PRD §Fallback echoed in spec front-matter) consistent with FR-027 — i.e., a failed promotion attempt leaves the FR-026 decision as "stay opt-in"? [Consistency, Spec §Fallback, §FR-027]
- [X] CHK035 Is "the MVP remains valid as feature-complete but not GPU-promoted" stated consistently across the Fallback blockquote, FR-027, and US6 scenario 1? [Consistency, Spec-wide]
- [X] CHK036 Is the case "promote-to-default was chosen, but a later regression appears" addressed — does the spec require a re-evaluation path that can revert to stay-opt-in? [Coverage, Gap]

## Gaps to Flag

- [X] CHK037 Are requirements defined for revisiting the promotion decision (e.g., "after N weeks of operation, the team SHOULD re-evaluate")? [Gap]
- [X] CHK038 Is the case "different team members hold different views" addressed — is the team-decision required to be unanimous, majority, or single-owner? [Gap]
- [X] CHK039 Is the case "promote-to-default chosen, but the explicit-off legacy path test is flaky" handled — does flakiness violate SC-009 "passes"? [Gap, Edge Case]
- [X] CHK040 Is the relationship between this feature's promotion decision and feature-020's existing opt-in surface explicit, so a reviewer can confirm no parallel mechanism is introduced? [Gap, Consistency]

## Notes

- This checklist tests whether the promotion-decision *requirements* are well-written, not whether a particular decision is correct.
- The principal failure mode is silent automation — i.e., the PASS verdict mechanically flipping the default; FR-029 + CHK015–CHK018 are the defense at the requirements layer.
- Items CHK009, CHK013, CHK016, CHK018, CHK030, CHK037–CHK040 flag genuine gaps that may benefit from a spec amendment or planning-time decision.
