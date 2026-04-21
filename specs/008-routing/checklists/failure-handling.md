# Failure-Handling Checklist: Deterministic Routing (Stage 1)

**Purpose**: Release-gate validation that the spec prescribes clear, loud, and
non-silent failure behavior with the rigor needed for a deterministic gate.
Every item validates the **requirements**, not the implementation.
**Created**: 2026-04-21
**Feature**: [spec.md](../spec.md)
**Depth**: Release gate
**Audience**: Reviewer (PR + pipeline operator)

## Hard-Error Exit Conditions

- [x] CHK001 Are the four distinct hard-error conditions (input missing, input unreadable, input schema-invalid, input version-drifted) each named explicitly? [Completeness, Spec §FR-003 §US5 AC#4]
- [x] CHK002 Is the rule "non-zero exit on hard error" stated as a hard requirement? [Clarity, Spec §FR-003 §SC-006]
- [x] CHK003 Is the rule "no `routing_decision.json` written on hard error" stated as a hard requirement (not just "usually no output")? [Clarity, Spec §FR-003 §SC-006 §US5 AC#4]
- [x] CHK004 Is the rule "human-readable error names the specific failure cause" stated? [Clarity, Spec §FR-003 §US5 AC#4 §SC-006]
- [x] CHK005 Is version-drift (`contract_set_version != "1.0.0"`) called out as a hard error, not a warning? [Clarity, Spec §FR-003 §US5 AC#5]
- [x] CHK006 Is the rule "100% of hard failures exit non-zero with no artifact" stated as a success criterion? [Measurability, Spec §SC-006]

## No Partial Artifact Guarantee

- [x] CHK007 Is the rule "no partial `routing_decision.json` is ever persisted on failure" stated (not just "usually not")? [Clarity, Spec §FR-003]
- [x] CHK008 Is atomic-write behavior stated as the persistence requirement (write-then-rename, no intermediate dangling files)? [Gap — is this pinned at spec level or deferred? Spec §FR-002]

## Upstream `status` Propagation

- [x] CHK009 Is the behavior for input `status == "success"` defined (output `status == "success"` unless the router itself flags an issue)? [Completeness, Spec §FR-020 §US5 AC#1]
- [x] CHK010 Is the behavior for input `status == "partial"` defined (output `status == "partial"`; rules still fire; `reasons` includes an upstream-partial entry)? [Completeness, Spec §FR-020 §US5 AC#2]
- [x] CHK011 Is the behavior for input `status == "failure"` defined (output `status` is `"partial"` or `"failure"`; `decision` defaults to `edge_review_required`; `reasons` names the upstream failure)? [Completeness, Spec §FR-020 §US5 AC#3]
- [x] CHK012 Is the canonical reason string for upstream failure pinned (`"upstream_extraction_failed"`)? [Clarity, Spec §FR-020 §Key Entities]
- [x] CHK013 Is the rule "schema validity of the output holds even when `status` is `"partial"` or `"failure"`" stated? [Completeness, Spec §US5 AC#5 §SC-007]
- [x] CHK014 Does the spec state that a failed upstream extraction never silently auto-accepts? [Clarity, Spec §FR-020 §US5 AC#3]

## Contract-Violation Defensive Path (FR-024)

- [x] CHK015 Are the specific forbidden input combinations enumerated (`present == true AND inferred == true`, and `present == false AND inferred == false`)? [Completeness, Spec §FR-024 §Edge Cases]
- [x] CHK016 Is the defensive handling rule stated (set `status = "partial"`, set `decision = "edge_review_required"`, add a reasons entry naming the violation)? [Completeness, Spec §FR-024]
- [x] CHK017 Is the rule "router does NOT silently 'correct' an extractor contract violation" stated? [Clarity, Spec §FR-024 §Edge Cases]
- [x] CHK018 Does the spec pin a canonical informational string for contract violations (or explicitly defer it to the plan/research)? [Gap, Spec §FR-024]

## Error Visibility

- [x] CHK019 Is the rule "the `decision` is reconstructible from the artifact alone, even on partial/failure inputs" stated? [Completeness, Spec §SC-005 §US5 AC#6]
- [x] CHK020 Is the rule "upstream issues are always visible in the artifact, never silent" stated as a success criterion? [Measurability, Spec §SC-007]
- [x] CHK021 Is the rule "warnings and narrative from the input are surfaced in `reasons` for traceability, even when they do not drive the decision" stated? [Clarity, Spec §Edge Cases]

## Defensive Decision Defaults

- [x] CHK022 Is the rule "on any upstream-failure input, `decision` defaults to `edge_review_required` (never to `edge_accept`)" stated? [Clarity, Spec §FR-020 §US5 AC#3]
- [x] CHK023 Is the rule "any review-forcing rule overrides any `edge_accept`-permitting signal" stated? [Clarity, Spec §Edge Cases]
- [x] CHK024 Does the spec state that the router does not attempt to "guess a meaningful decision from a failed extraction"? [Clarity, Spec §US5 AC#3]

## Observability of Failures

- [x] CHK025 Does the spec describe stderr/stdout behavior for failures (vs. silent exit codes)? [Gap — deferred to CLI contract? Spec §FR-003]
- [x] CHK026 Does the spec distinguish "bad input" (external cause) from "bad policy" / "bad routing code" (internal cause) in the exit-code taxonomy? [Gap — deferred to CLI contract? Spec §FR-003]

## Recovery & Idempotency

- [x] CHK027 Is the rule "re-running after a hard-error fix produces a normal artifact (no stale state)" implied by the no-partial-write and read-only-input rules? [Completeness, Spec §FR-003 §FR-022]
- [x] CHK028 Does the spec state that an existing `routing_decision.json` is safely overwritten on success (no merge)? [Gap — deferred to CLI contract? Spec §FR-001]
