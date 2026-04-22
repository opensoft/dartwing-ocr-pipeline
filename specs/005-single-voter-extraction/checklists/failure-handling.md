# Failure-Handling Checklist: Single-Voter Edge Extraction (Stage 1)

**Purpose**: PR-review aid for validating that the spec specifies — unambiguously and without
gaps — how the extractor behaves under model, network, parsing, and input failures. Every item
tests the requirements themselves — not the implementation.
**Created**: 2026-04-21
**Feature**: [spec.md](../spec.md)
**Depth**: PR-review aid
**Audience**: Spec author + reviewer (pre-`/speckit.tasks`)

## Hard / Soft Failure Taxonomy (FR-015 / FR-016 / US5)

- [x] CHK001 Is the hard-vs-soft failure distinction stated in terms of observable behavior (hard: non-zero exit, no artifact; soft: artifact with `status="partial"` or `"failure"`)? [Clarity, Spec §US5 §FR-015 §FR-016]
- [x] CHK002 Is the enumeration of hard-failure triggers complete (Ollama unreachable, configured model unavailable, input packet missing/unreadable/schema-invalid, `contract_set_version` drift, model returns unrepairable content)? [Completeness, Spec §FR-003 §FR-015 §Edge Cases]
- [x] CHK003 Is the enumeration of soft-failure triggers complete (JSON required repair, evidence ID dropped, required sub-field defaulted)? [Completeness, Spec §FR-014 §FR-016]
- [x] CHK004 Does the spec reconcile the two conventions for total-failure reporting named in US5 AC#4 (artifact with `status="failure"` vs. non-zero exit with no artifact) with a single preferred convention? [Consistency, Spec §US5 AC#4]

## Hard-Failure Semantics

- [x] CHK005 Is "no partial artifact on hard failure" stated explicitly (the file either is not written, or is schema-valid with `status="failure"` — never a half-written JSON)? [Clarity, Spec §FR-015 §US5 AC#1]
- [x] CHK006 Is the non-zero exit requirement stated for Ollama unreachable (connection refused, DNS failure, or timeout)? [Completeness, Spec §FR-015 §US5 AC#1 §Clarifications Q2]
- [x] CHK007 Is the HTTP timeout behavior specified (single bounded timeout, no retries inside the extractor)? [Clarity, Spec §FR-015 §Clarifications Q2]
- [x] CHK008 Is the behavior for "configured model not available on the endpoint" specified as a hard failure with an identifying error message? [Completeness, Spec §Edge Cases]
- [x] CHK009 Is the "no auto-pull" rule stated (the extractor does not pull models on behalf of the operator)? [Clarity, Spec §Edge Cases]
- [x] CHK010 Is the stderr obligation stated (human-readable error message naming the specific failure cause)? [Completeness, Spec §FR-015 §US5 AC#1]

## Input-Contract Failures

- [x] CHK011 Is the missing `preprocess_output.json` case specified as a hard failure with non-zero exit? [Completeness, Spec §FR-003 §US5 AC#1]
- [x] CHK012 Is the schema-invalid `preprocess_output.json` case specified as a hard failure with non-zero exit? [Completeness, Spec §FR-003]
- [x] CHK013 Is the `contract_set_version != "1.0.0"` case specified as a hard failure naming the drift? [Completeness, Spec §FR-003 §Edge Cases]
- [x] CHK014 Is the "no output on input-contract failure" rule stated (extractor writes nothing, leaves folder untouched)? [Clarity, Spec §FR-003 §FR-019]

## Soft-Failure Artifact (US5 / FR-016)

- [x] CHK015 Is the obligation that every soft-failure artifact still validates against the schema stated? [Clarity, Spec §US5 AC#6]
- [x] CHK016 Is the `status="partial"` condition stated precisely (meaningful artifact produced but at least one non-fatal issue)? [Clarity, Spec §FR-014]
- [x] CHK017 Is the warning-per-issue rule stated (every soft-failure event appends a human-readable warning)? [Completeness, Spec §US5 AC#5 §FR-016]
- [x] CHK018 Are warnings required to be non-empty human-readable strings that name the field, page, or stage? [Clarity, Spec §US5 AC#5]
- [x] CHK019 Is the JSON-repair warning path specified (repair needed → `warnings` entry describing the repair → `status="partial"`)? [Completeness, Spec §US5 AC#2 §FR-014]
- [x] CHK020 Is the defaulted-sub-field warning path specified (missing required sub-field → default shape → `warnings` entry naming the field → `status="partial"`)? [Completeness, Spec §FR-016 §US5 AC#3]
- [x] CHK021 Is the dropped-evidence warning path specified (unresolvable ID → drop → `warnings` entry naming the field and the ID)? [Completeness, Spec §FR-010 §US2 AC#2]

## Total-Failure (status=failure) Semantics

- [x] CHK022 Is the total-failure trigger specified (model returns no usable content: empty response, unparseable that cannot be repaired, explicit refusal)? [Completeness, Spec §US5 AC#4]
- [x] CHK023 Is the total-failure artifact shape specified (all values `null`, all confidences `0.0`, all evidence arrays empty, `warnings` explaining the cause)? [Completeness, Spec §US5 AC#4]
- [x] CHK024 Is the status-vs-validity independence stated (`status="failure"` is a reported outcome, not a schema violation)? [Clarity, Spec §US5 AC#6]

## Edge Cases on Input-Packet Quality

- [x] CHK025 Is the partial-but-schema-valid input packet path specified (proceed best-effort; record input-side partiality in `extraction_notes` or `warnings`; do not refuse to run)? [Completeness, Spec §FR-023 §Edge Cases]
- [x] CHK026 Is the blank-document path specified (zero blocks and zero OCR lines on every page → schema-valid output with `status="failure"` or `"partial"` and an explanatory warning)? [Coverage, Spec §Edge Cases]
- [x] CHK027 Is the "document appears not to be an invoice" path specified (schema-forced `document_type.value = "invoice"`; lower confidence; `extraction_notes` entry)? [Coverage, Spec §Edge Cases §FR-009]
- [x] CHK028 Is the rerun-overwrite behavior specified (second invocation against the same folder overwrites)? [Clarity, Spec §Edge Cases]

## Model-Output Failures (Parse Path)

- [x] CHK029 Is the malformed-JSON repair obligation stated (markdown fences, leading/trailing prose, BOM) as a repair-then-retry step? [Completeness, Spec §US5 AC#2 §Independent Test (c)]
- [x] CHK030 Is the unrepairable-content path specified (no usable JSON → hard failure, exit non-zero, no artifact OR artifact with `status="failure"` per US5 AC#4)? [Completeness, Spec §US5 AC#4]
- [x] CHK031 Is the behavior on "valid JSON but wrong type for a field" specified (default-and-warn rather than hard failure)? [Gap, Spec §FR-016]
- [x] CHK032 Is the behavior on "valid JSON containing extra unknown keys" specified (ignore / warn / fail)? [Gap, Spec §FR-016]

## Evidence Failures

- [x] CHK033 Is the behavior on "model proposes an evidence ID in the correct format but referring to a different document's blocks" specified as a filter-and-warn? [Coverage, Spec §Edge Cases §US2 AC#2]
- [x] CHK034 Is the behavior on "all evidence for a field is dropped, leaving evidence empty" specified (confidence cap + provenance override for `company_name` specifically)? [Completeness, Spec §FR-011 §FR-012]
- [x] CHK035 Is the behavior on "all evidence for every field drops to empty" specified (status derivation falls to `partial` or `failure` accordingly)? [Coverage, Spec §FR-014]

## Non-Extractor Failure Boundaries

- [x] CHK036 Does the spec state that the extractor does not retry — retry policy is an orchestrator / harness concern? [Clarity, Spec §FR-015 §Clarifications Q2]
- [x] CHK037 Does the spec state that the extractor does not invoke routing / consensus / final-payload logic even on failure? [Completeness, Spec §FR-020]
- [x] CHK038 Does the spec state that the extractor does not escalate to a cloud path on failure? [Completeness, Spec §FR-021]

## Operator Diagnostics

- [x] CHK039 Does the spec state that soft failures are discoverable from the artifact alone, without log archaeology? [Clarity, Spec §US5 "Why this priority" §US5 AC#4]
- [x] CHK040 Does the spec state that hard failures are discoverable from stderr + exit code alone? [Clarity, Spec §US5 AC#1]
- [x] CHK041 Does the spec pin a specific exit-code convention (distinct codes per hard-failure category) or explicitly defer it to the plan? [Gap / Ambiguity, Spec §FR-015]

## Measurable Failure Criteria (SC-005 / SC-006)

- [x] CHK042 Is SC-005 measurable (100% non-zero exit on the enumerated hard-failure categories, no artifact)? [Measurability, Spec §SC-005]
- [x] CHK043 Is SC-006 measurable (schema-valid artifact + at least one human-readable `warnings` entry on soft failures)? [Measurability, Spec §SC-006]
- [x] CHK044 Does the spec avoid conflicting guidance between US5 AC#4's two conventions and SC-005's "100% non-zero exit on hard failures"? [Consistency, Spec §US5 AC#4 §SC-005]
