# Contract Alignment Checklist: Final Structured Payload Assembly (Stage 1)

**Purpose**: Release-gate validation that the spec's language matches the frozen
`contracts/stage1_vendor_identity/v1.0.0/final_structured_payload.schema.json` contract
without drift, gaps, or reinterpretation. Every item validates the requirements themselves,
not the implementation.
**Created**: 2026-04-21
**Feature**: [spec.md](../spec.md)
**Depth**: Release gate
**Audience**: Reviewer (PR + contract owner)

## Contract Versioning

- [X] CHK001 Is `contract_set_version` pinned to the exact value `"1.0.0"` and cross-referenced to `contracts/stage1_vendor_identity/v1.0.0/`? [Traceability, Spec §FR-002]
- [X] CHK002 Is the distinction between `contract_set_version` (frozen by the contract set) and `pipeline_version` (assembler build identifier) explicitly stated? [Clarity, Spec §FR-002 §FR-007]
- [X] CHK003 Is `pipeline_version` required to follow the exact structured format `"009-final-payload@<semver>"` (not a free-form string)? [Clarity, Spec §FR-007, Clarifications Q2]
- [X] CHK004 Does the spec state that `pipeline_version` is NOT copied from either input's `pipeline_version` field? [Clarity, Spec §FR-007]
- [X] CHK005 Is the `contracts/stage1_vendor_identity/AMENDMENTS.md` governance path referenced as out-of-scope for this slice? [Completeness, Spec §Assumptions]

## Required-Key Alignment

- [X] CHK006 Does the spec enumerate every top-level required key the schema demands (`contract_set_version`, `pipeline_version`, `document_id`, `processed_at`, `document_type`, `vendor_candidate`, `review_status`, `quality_summary`, `trace`)? [Completeness, Spec §FR-002, US1 AS-3]
- [X] CHK007 Are every required `vendor_candidate` sub-key (`company_name`, `address`, `tax_ids`, `website`, `phone`, `email`) named in the spec? [Completeness, Spec §FR-009..FR-012]
- [X] CHK008 Are every required `address` sub-key (`street_1`, `street_2`, `city`, `state`, `postal_code`, `country`) named in the spec? [Completeness, Spec §FR-010]
- [X] CHK009 Are every required `tax_ids` sub-key (`ein`, `state_tax_id`, `vat_id`, `other_tax_id`) named in the spec? [Completeness, Spec §FR-011]
- [X] CHK010 Are every required `trace` sub-key (`source_file`, `preprocess_output_file`, `edge_extraction_output_file`, `routing_decision_file`) named? [Completeness, Spec §FR-021]
- [X] CHK011 Are every required `quality_summary` sub-key (`overall_vendor_confidence`, `explicit_name_found`, `consensus_level`, `secondary_identifiers_found`) named? [Completeness, Spec §FR-017..FR-020]

## Closed Vocabularies & Enums

- [X] CHK012 Is `document_type` restricted to the single literal `"invoice"` (with the spec stating no other value is possible under v1.0.0)? [Clarity, Spec §FR-008]
- [X] CHK013 Is `quality_summary.consensus_level` restricted to the single literal `"single_voter_baseline"` in stage 1? [Clarity, Spec §FR-017]
- [X] CHK014 Is `quality_summary.secondary_identifiers_found` restricted to the frozen enum `{"address", "ein", "state_tax_id", "vat_id", "other_tax_id", "website", "phone", "email"}`? [Completeness, Spec §FR-020]
- [X] CHK015 Is the ordering of `secondary_identifiers_found` pinned to the schema enum's declared order exactly (not "any deterministic order")? [Clarity, Spec §FR-020, Clarifications Q3]

## Flattening Rules

- [X] CHK016 Is the absence of any `evidence` key anywhere in the output at any nesting depth asserted as a global invariant (not only per-field)? [Completeness, Spec §FR-014, US2 AS-5, SC-003]
- [X] CHK017 For `company_name`, does the spec enumerate the four surviving keys (`value`, `present`, `inferred`, `confidence`) and exclude `evidence`? [Clarity, Spec §FR-009]
- [X] CHK018 For every other scalar field, does the spec state the exact surviving shape `{value, confidence}` with no additional keys? [Consistency, Spec §FR-010..FR-012]
- [X] CHK019 Is the treatment of null scalars (retained as `{value: null, confidence: <number>}`) specified, including confidence=0.0 passthrough? [Coverage, Spec §US2 AS-2]
- [X] CHK020 Is `invoice_header_fields` explicitly excluded from the output, with the reason (not in v1.0.0 schema) stated? [Clarity, Spec §FR-013, Edge Case §4]

## Verbatim Propagation

- [X] CHK021 Is `document_id` specified as byte-identical to both inputs' agreed value (no normalization, no case folding)? [Clarity, Spec §FR-005 §FR-006]
- [X] CHK022 Is `company_name.present` and `company_name.inferred` specified as propagated verbatim (never recomputed by the assembler)? [Clarity, Spec §FR-009, US2 AS-6]
- [X] CHK023 Is `review_status.manual_review_required` and `review_status.review_reason` specified as propagated verbatim from routing, including the canonical string `"company_name_inferred"`? [Clarity, Spec §FR-015, US3]
- [X] CHK024 Does the spec state that the assembler does NOT maintain its own `review_reason` vocabulary and propagates unknown strings untouched? [Clarity, Spec §US3 AS-3, Edge Case §3]

## Trace Block Contract

- [X] CHK025 Are all four `trace` fields required to be relative paths (not absolute) anchored at the per-document folder? [Clarity, Spec §FR-021, US5 AS-3]
- [X] CHK026 Are the exact stage-1 filenames (`source.pdf`, `preprocess_output.json`, `edge_extraction_output.json`, `routing_decision.json`) pinned? [Completeness, Spec §FR-021]
- [X] CHK027 Is the spec's position on trace-file-existence explicit (trace names a path; `source.pdf` is not independently verified by this stage)? [Clarity, Edge Case §7]
