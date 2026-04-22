# Failure-Handling Checklist: Final Structured Payload Assembly (Stage 1)

**Purpose**: Release-gate validation that the spec's failure-path requirements (cross-input
invariants, hard-fail modes, error messaging) are written clearly, completely, and
consistently. Every item validates the requirements themselves, not the implementation.
**Created**: 2026-04-21
**Feature**: [spec.md](../spec.md)
**Depth**: Release gate
**Audience**: Reviewer (PR + contract owner)

## Cross-Input Invariant Enumeration

- [X] CHK001 Does the spec enumerate every hard-fail cross-input invariant with a unique FR reference? [Completeness, Spec §FR-003 §FR-004 §FR-005 §FR-016]
- [X] CHK002 Are "missing input", "unreadable input", and "schema-invalid input" distinguished as separate failure kinds rather than bundled? [Clarity, Spec §FR-003, US6 AS-1, AS-2, AS-5]
- [X] CHK003 Is `contract_set_version != "1.0.0"` specified as a hard-fail (no fallback, no upgrade path) and scoped to both inputs? [Clarity, Spec §FR-004, US6 AS-4]
- [X] CHK004 Is `document_id` disagreement between the two inputs specified as a hard-fail with both `document_id` values reported in the error? [Clarity, Spec §FR-005, US6 AS-3]
- [X] CHK005 Is the FR-016 routing-contradiction case (routing `decision` vs. `review_status` inconsistent) specified as a hard-fail (not a soft surface), with all four possible contradictions covered? [Clarity, Spec §FR-016, US3 AS-5, Clarifications Q1]

## Hard-Fail Semantics

- [X] CHK006 Is "no `final_structured_payload.json` is written" stated as a guarantee on every hard-fail branch (not only the examples)? [Completeness, Spec §FR-003 §FR-004 §FR-005 §FR-016, US6 Independent Test]
- [X] CHK007 Is "assembler exits non-zero" stated as a guarantee on every hard-fail branch? [Completeness, Spec §SC-005, US6]
- [X] CHK008 Is the requirement that the error message "names the specific failure cause" specified uniformly across all hard-fail modes? [Consistency, Spec §FR-003..FR-005, SC-005]
- [X] CHK009 Is mutation of any input file explicitly forbidden on every failure path (read-only inputs)? [Completeness, Spec §FR-024]
- [X] CHK010 Is "100% of the time" stated as the quantified reliability target for the exit-non-zero guarantee? [Measurability, Spec §SC-005]

## Order of Invariant Checks

- [X] CHK011 Does the spec or plan specify the order in which cross-input invariants are checked, so reviewers can predict which error kind wins when multiple invariants fail simultaneously? [Clarity, Gap — potentially addressed in plan §data-model Cross-input invariant table]
- [X] CHK012 Is the failure behavior specified when BOTH `contract_set_version` drifts AND `document_id` mismatches — which error takes precedence? [Coverage, Spec §FR-004 §FR-005, Gap]

## Upstream-Status Handling

- [X] CHK013 Is the spec's position on upstream `status == "failure"` or `"partial"` explicit — the assembler still produces the payload because routing has already handled upstream partiality? [Clarity, Spec §US6 AS-6, Edge Case §9]
- [X] CHK014 Is the distinction between "status is a per-stage signal that flows through" and "contract_set_version/document_id are cross-input invariants the assembler enforces" called out? [Clarity, Spec §US6 AS-6]

## Error Message Content

- [X] CHK015 For each hard-fail kind, is the information the error must name specified (missing file name, both document_ids, drifting contract_set_version, schema validation diagnostic, both conflicting routing fields)? [Completeness, Spec §US6 AS-1..AS-5, FR-016]
- [X] CHK016 Is "human-readable" stated as a requirement for every error message (not only some)? [Consistency, Spec §FR-003..FR-005, SC-005]

## Overwrite / Idempotency on Success

- [X] CHK017 Is the behavior when `final_structured_payload.json` already exists specified (overwrite vs. refuse)? [Clarity, Spec §Edge Case §6]
- [X] CHK018 Is the requirement that the assembler writes nothing outside the target folder on any path (success or failure) stated? [Completeness, Spec §US1 AS-5]
- [X] CHK019 Is the list of reserved filenames the assembler must NOT touch (e.g., `preprocess_output.json`, `evaluation_document.json`, `consensus_output.json`, `votes/`) enumerated? [Completeness, Spec §US1 AS-5]

## Evidence of Failure Coverage

- [X] CHK020 Does the US6 "Independent Test" fixture list cover all six hard-fail modes (missing extractor, missing routing, doc_id mismatch, contract drift, schema-invalid input, routing contradiction)? [Coverage, Spec §US6 Independent Test]
- [X] CHK021 Is there a requirement (or assertion) that no partial `final_structured_payload.json` with a broken `trace` reference is ever written? [Completeness, Spec §US5 AS-4, FR-021]
