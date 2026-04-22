# Contract Alignment Checklist: Single-Voter Edge Extraction (Stage 1)

**Purpose**: PR-review aid for validating that the spec's language matches the frozen
`contracts/stage1_vendor_identity/v1.0.0/edge_extraction_output.schema.json` contract (and the
`preprocess_output.schema.json` contract it consumes) without drift, gaps, or reinterpretation.
Every item tests the requirements themselves — not the implementation.
**Created**: 2026-04-21
**Feature**: [spec.md](../spec.md)
**Depth**: PR-review aid
**Audience**: Spec author + reviewer (pre-`/speckit.tasks`)

## Contract Versioning

- [x] CHK001 Is `contract_set_version` pinned to a specific value (`"1.0.0"`) and cross-referenced to `contracts/stage1_vendor_identity/v1.0.0/`? [Traceability, Spec §FR-002]
- [x] CHK002 Is the distinction between `contract_set_version` (frozen) and `pipeline_version` (build-specific, extractor-identifying) explicitly stated? [Clarity, Spec §FR-002 §FR-022]
- [x] CHK003 Is the refusal-to-run rule on input `contract_set_version != "1.0.0"` stated with a specific failure mode (non-zero exit, no artifact)? [Completeness, Spec §FR-003 §Edge Cases]
- [x] CHK004 Is the "no schema amendment in this slice" posture stated, with the amendment path (`contracts/stage1_vendor_identity/AMENDMENTS.md`) marked out of scope? [Completeness, Spec §Assumptions]

## Required-Key Alignment (Output Artifact)

- [x] CHK005 Does the spec enumerate every top-level required key the `edge_extraction_output` schema demands (`contract_set_version`, `pipeline_version`, `document_id`, `processed_at`, `model_runtime`, `vote_metadata`, `document_type`, `vendor_candidate`, `invoice_header_fields`, `extraction_notes`, `warnings`, `status`)? [Completeness, Spec §US1 Independent Test §FR-002..FR-009]
- [x] CHK006 Are the four required `model_runtime` sub-keys enumerated (`provider`, `model_name`, `model_version`, `runtime`) with non-empty-string obligation? [Completeness, Spec §FR-005 §US4 AC#1]
- [x] CHK007 Are the three required `vote_metadata` sub-keys enumerated (`voter_id`, `voter_role`, `consensus_mode`)? [Completeness, Spec §FR-006 §US4 AC#2]
- [x] CHK008 Does the spec enumerate every required `vendor_candidate` sub-field (`company_name`, the six address components, the four tax-ID slots, `website`, `phone`, `email`)? [Completeness, Spec §US1 AC#3 §FR-007]
- [x] CHK009 Are the three required `invoice_header_fields` sub-keys named (`invoice_number`, `invoice_date`, `total_amount`)? [Completeness, Spec §US1 AC#4 §FR-008]
- [x] CHK010 Does the spec name both required sub-fields for `company_name` specifically (`present`, `inferred`) alongside `{value, confidence, evidence}`? [Completeness, Spec §US3 §FR-012 §FR-013]

## Required-Key Alignment (Consumed Input)

- [x] CHK011 Does the spec identify which keys of `preprocess_output.json` the extractor must read (`document_id`, `contract_set_version`, per-page `blocks`, per-page `raw_ocr_lines`, `ingestion_sources`, `warnings`)? [Completeness, Spec §Key Entities §FR-010 §FR-023]
- [x] CHK012 Is the "inputs are read-only" obligation stated for every input file (`preprocess_output.json`, `expected.json`, `notes.md`, `source.pdf`)? [Completeness, Spec §FR-019]

## Closed Vocabulary Conformance

- [x] CHK013 Is `document_type.value` stated as restricted to the single literal `"invoice"`? [Clarity, Spec §FR-009 §Edge Cases]
- [x] CHK014 Is the `voter_role` enum stated in full (`primary_extractor | secondary_extractor | verifier`), with stage 1 pinning `primary_extractor`? [Consistency, Spec §FR-006 §US4 AC#5]
- [x] CHK015 Is `consensus_mode` pinned to the schema's sole allowed value (`"single_voter_baseline"`) with explicit prohibition of any other value? [Consistency, Spec §FR-006]
- [x] CHK016 Is the `status` enum stated in full (`success | partial | failure`) with a deterministic derivation rule per value? [Consistency, Spec §FR-014 §US1 AC#5]

## Field-Shape Contracts

- [x] CHK017 Is the `{value, confidence, evidence}` shape specified uniformly for every scalar extraction field (address parts, tax IDs, website, phone, email, invoice_number, invoice_date)? [Clarity, Spec §FR-007]
- [x] CHK018 Is the expanded `{value, currency, confidence, evidence}` shape specified for `total_amount`, with `value: number | null` and `currency: string | null`? [Clarity, Spec §FR-008 §US1 AC#4]
- [x] CHK019 Is `confidence` bounded to `[0.0, 1.0]` everywhere it appears? [Completeness, Spec §US1 AC#3]
- [x] CHK020 Is `processed_at` required to be a valid ISO-8601 date-time in UTC? [Clarity, Spec §FR-022 §US1 AC#2]
- [x] CHK021 Is `pipeline_version` required to be a non-empty string identifying the build? [Clarity, Spec §FR-022 §US1 AC#2]

## Evidence-ID Contracts

- [x] CHK022 Is the evidence-ID pattern stated as `^p\d+_[bl]\d+$`, matching the schema's regex? [Clarity, Spec §US1 AC#3 §FR-010]
- [x] CHK023 Is the resolution obligation stated (every evidence ID MUST resolve to a real `block_id` or `line_id` in `preprocess_output.json`)? [Completeness, Spec §US2 §FR-010]
- [x] CHK024 Is the filter-and-warn rule for unresolvable evidence IDs specified (drop from final array, append `warnings` entry naming the field and dropped ID)? [Clarity, Spec §US2 AC#2 §FR-010]

## Null / Empty Discipline

- [x] CHK025 Is the null-only-never-empty-string rule stated for scalar string fields? [Clarity, Spec §FR-007]
- [x] CHK026 Are the default shapes for absent sub-fields specified exactly (`{value: null, confidence: 0.0, evidence: []}` for scalars; `{value: null, currency: null, confidence: 0.0, evidence: []}` for `total_amount`)? [Completeness, Spec §FR-016 §US5 AC#3]
- [x] CHK027 Is the empty `evidence: []` case disambiguated from the missing-key case (both are valid; their consequences differ — confidence cap vs. sub-field default)? [Consistency, Spec §FR-010 §FR-011 §FR-016]

## Provenance Invariants (Schema + Constitution)

- [x] CHK028 Is the exclusive-or invariant for `company_name.present` / `company_name.inferred` stated explicitly (never both true, never both false)? [Clarity, Spec §FR-013 §US3 AC#5]
- [x] CHK029 Is the override semantics spelled out — when `company_name.evidence` is empty after reconciliation, `present=false, inferred=true` deterministically, regardless of model claim? [Completeness, Spec §FR-012 §US3 AC#3]
- [x] CHK030 Is the override discoverability requirement stated (`extraction_notes` or `warnings` records the override)? [Completeness, Spec §US2 AC#5 §US3 AC#3]

## Identity Propagation

- [x] CHK031 Is the `document_id` consistency rule stated (output `document_id` MUST equal input `document_id`; never diverge)? [Clarity, Spec §FR-004 §US1 AC#2]
- [x] CHK032 Is the requirement that `vote_metadata.voter_id` be a non-empty string stated? [Completeness, Spec §FR-006]

## Artifact Placement & Boundaries

- [x] CHK033 Is the write location stated unambiguously (`<per-document folder>/edge_extraction_output.json`, next to `preprocess_output.json`)? [Clarity, Spec §FR-001 §US1 AC#1]
- [x] CHK034 Is the reserved-filename rule stated (this slice MUST NOT write `routing_decision.json`, `final_structured_payload.json`, `evaluation_document.json`, `consensus_output.json`, or anything under `votes/`)? [Completeness, Spec §FR-018 §US1 AC#6]
- [x] CHK035 Is the overwrite-on-rerun convention stated (second invocation overwrites the prior `edge_extraction_output.json`)? [Clarity, Spec §Edge Cases]

## Validation Obligation

- [x] CHK036 Does the spec require every emitted artifact to validate against `edge_extraction_output.schema.json` before being persisted? [Completeness, Spec §FR-002 §US1 AC#1]
- [x] CHK037 Is the schema-validity requirement stated as status-independent (even a `status: "failure"` artifact must be schema-valid)? [Clarity, Spec §US5 AC#6]
- [x] CHK038 Is the validator tool identified as a verification path (`python -m ledgerlinc_ocr.validator validate artifact`)? [Traceability, Spec §US1 Independent Test]

## Cross-Artifact Consistency (Gap Check)

- [x] CHK039 Does the spec reconcile `vendor_candidate.address` shape language with the six schema-required components exactly (no sixth-field drift)? [Consistency, Spec §FR-007]
- [x] CHK040 Does the spec reconcile the tax-IDs four-slot shape (`ein`, `state_tax_id`, `vat_id`, `other_tax_id`) with the schema? [Consistency, Spec §FR-007]
- [x] CHK041 Does the spec state that `extraction_notes` and `warnings` are SEPARATE arrays with distinct roles (notes: descriptive; warnings: condition-signals)? [Clarity, Spec §US2 AC#5 §US5 AC#5]
- [x] CHK042 Does the spec state every `warnings` entry is a non-empty, human-readable string? [Completeness, Spec §US5 AC#5]

## Voter-Shape Portability

- [x] CHK043 Does the spec state that artifact shape is identical across voter configurations, with only `model_runtime`, `vote_metadata.voter_id`, and model-dependent values varying? [Clarity, Spec §FR-024 §US4 AC#3]
- [x] CHK044 Does the spec state that `votes/` is reserved for future multi-voter mode and MUST NOT be written during a stage 1 single-voter run? [Completeness, Spec §FR-018 §US4 AC#4]
