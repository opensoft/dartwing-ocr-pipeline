# Scope Checklist: Final Structured Payload Assembly (Stage 1)

**Purpose**: Release-gate validation that the spec's scope boundaries — what is and is NOT
in this slice — are written clearly and comprehensively, so no reviewer or implementer can
drift into adjacent work without noticing. Every item validates the requirements themselves,
not the implementation.
**Created**: 2026-04-21
**Feature**: [spec.md](../spec.md)
**Depth**: Release gate
**Audience**: Reviewer (PR + contract owner)

## Input / Output Scope

- [X] CHK001 Is the exact input set pinned (one per-document folder; reads `edge_extraction_output.json` and `routing_decision.json`; touches nothing else except trace references)? [Clarity, Spec §FR-001 §FR-023]
- [X] CHK002 Is the exact output set pinned (one `final_structured_payload.json` in the same folder, nothing else)? [Clarity, Spec §FR-001, US1 AS-5]
- [X] CHK003 Is reading `preprocess_output.json` for content (as opposed to trace referencing) explicitly excluded? [Clarity, Spec §FR-023]
- [X] CHK004 Is mutation of any input file explicitly forbidden, with the list of read-only files enumerated (extractor, routing, preprocess, expected, notes, source.pdf)? [Completeness, Spec §FR-024]

## Excluded Fields in the Output

- [X] CHK005 Is `invoice_header_fields` (invoice_number, invoice_date, total_amount) explicitly excluded from the output with the reason (not in v1.0.0 schema) stated? [Clarity, Spec §FR-013, Edge Case §4]
- [X] CHK006 Is every `evidence` key at every nesting depth excluded from the output, and is the reason (downstream consumers should not re-reason about grounding) stated? [Clarity, Spec §FR-014, US2]
- [X] CHK007 Is `document_type.confidence` specified as dropped (the final payload's `document_type` is a bare string), with the reason (schema enum has no confidence channel) stated? [Clarity, Spec §Edge Case §5]
- [X] CHK008 Are `extraction_notes`, `warnings`, `status`, `model_runtime`, `vote_metadata`, and other extractor-internal keys specified as NOT propagated? [Completeness, Gap — check spec covers these beyond the FIELDS_TO_FLATTEN table]

## Excluded Responsibilities

- [X] CHK009 Is "no model call" stated as a hard requirement on this slice? [Clarity, Spec §FR-023]
- [X] CHK010 Is "no OCR, no preprocessing, no re-reading of `preprocess_output.json`" stated as a hard requirement? [Clarity, Spec §FR-023]
- [X] CHK011 Is "no routing logic, no consensus, no ensemble reconciliation" specified as out-of-scope (routing owns those; this stage consumes the output)? [Clarity, Spec §FR-025]
- [X] CHK012 Is "no evaluation" specified as out-of-scope (the evaluator 007 consumes this stage's output)? [Clarity, Spec §FR-025]
- [X] CHK013 Is "no line-item extraction, no cloud escalation, no multi-document orchestration" specified as out-of-scope? [Completeness, Spec §FR-025]

## Stage 1 Scope Constraints

- [X] CHK014 Is `document_type` being hard-coded to `"invoice"` (rather than copied from the extractor) justified by the v1.0.0 enum having only that value? [Clarity, Spec §FR-008]
- [X] CHK015 Is `quality_summary.consensus_level` being hard-coded to `"single_voter_baseline"` specified as a stage-1-only pin (multi-voter requires an amendment)? [Clarity, Spec §FR-017, Edge Case §10]
- [X] CHK016 Is PDF-only input inherited from the upstream contract (this stage is artifact-to-artifact, so it does not re-enforce PDF-only but assumes it)? [Consistency, Spec §Assumptions]
- [X] CHK017 Is "no latency gate" inherited from the constitution (SC-001's 200 ms is an internal target, not a release gate)? [Consistency, Spec §SC-001]

## Amendment Paths for Out-of-Scope Items

- [X] CHK018 Is the future-amendment path for adding `invoice_header_fields` to the final payload mentioned (via `contracts/stage1_vendor_identity/AMENDMENTS.md`)? [Completeness, Spec §Assumptions]
- [X] CHK019 Is the future-amendment path for adding `document_type.confidence` to the final payload mentioned? [Completeness, Spec §Assumptions]
- [X] CHK020 Is the future-amendment path for adding multi-voter consensus levels mentioned, and is the current stage-1 behavior distinguished from the future one? [Clarity, Spec §FR-017, Assumptions]

## Orchestration Scope

- [X] CHK021 Is "one invocation per document" pinned as the only orchestration mode in scope for this feature? [Clarity, Spec §Assumptions]
- [X] CHK022 Is corpus-level orchestration (running across all 20 documents) specified as living in the harness/outside-this-feature? [Clarity, Spec §Assumptions]
- [X] CHK023 Is the end-to-end stage-1 pipeline composition (003 + 005 + 008 + 009) stated as the integration shape, with each feature owning its own slice? [Consistency, Spec §SC-010]

## Constitutional Alignment

- [X] CHK024 Does the spec assert that this feature does not collapse the pipeline/harness boundary (constitution §I)? [Traceability, Constitution §I, Spec §FR-025]
- [X] CHK025 Does the spec assert that this feature does not re-derive provenance (`company_name.present`/`inferred`) or review decisions, preserving deterministic control (constitution §III + §IV)? [Traceability, Constitution §III §IV, Spec §FR-009 §FR-015]
