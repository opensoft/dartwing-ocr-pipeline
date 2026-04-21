# Contract Checklist: Deterministic Routing (Stage 1)

**Purpose**: Release-gate validation that the spec pins its conformance to the
frozen `v1.0.0` contract set with the rigor needed for downstream consumers
(evaluator, final-payload). Every item validates the **requirements**, not the
implementation.
**Created**: 2026-04-21
**Feature**: [spec.md](../spec.md)
**Depth**: Release gate
**Audience**: Reviewer (PR + contract-set owner)

## Frozen Contract Boundary

- [ ] CHK001 Is the target contract set pinned to a specific version string (`"1.0.0"`) rather than described qualitatively (e.g., "the current version")? [Clarity, Spec §FR-002 §FR-003]
- [ ] CHK002 Is the rule "output MUST set `contract_set_version = \"1.0.0\"`" stated as a hard requirement, not as a recommendation? [Clarity, Spec §FR-002]
- [ ] CHK003 Is the consequence of input `contract_set_version != "1.0.0"` spelled out (non-zero exit, no artifact written)? [Completeness, Spec §FR-003 §SC-006 §US5 AC#5]
- [ ] CHK004 Does the spec state that the frozen schema is the authoritative artifact shape and that the spec does not redefine field shapes? [Clarity, Spec §FR-002 §Assumptions]
- [ ] CHK005 Does the spec distinguish "major-equal" from "exact-equal" version checking for routing specifically? [Gap — if deferred to plan, is that deferral explicit? Spec §FR-003]

## Two-Layer Schema Validation

- [ ] CHK006 Does the spec require input `edge_extraction_output.json` to be schema-validated before any rule fires? [Completeness, Spec §FR-003 §US5 AC#4]
- [ ] CHK007 Does the spec require output `routing_decision.json` to be schema-validated before any write? [Completeness, Spec §FR-002 §US1 AC#1]
- [ ] CHK008 Is the rule "no `routing_decision.json` is ever written on schema failure" stated unambiguously? [Clarity, Spec §FR-003 §SC-006]
- [ ] CHK009 Are the four distinct input-failure cases (missing, unreadable, schema-invalid, version-drift) each called out, not merged into a generic "bad input" case? [Completeness, Spec §FR-003 §US5 AC#4]

## Required-Key Coverage

- [ ] CHK010 Is every top-level key required by `routing_decision.schema.json` (`contract_set_version`, `pipeline_version`, `policy_version`, `document_id`, `processed_at`, `status`, `decision`, `consensus_summary`, `scores`, `checks`, `review_status`, `reasons`) named in the spec with explicit population rules? [Completeness, Spec §US1 AC#2]
- [ ] CHK011 Is the rule "`document_id` in output equals `document_id` in input" stated, not implied? [Clarity, Spec §FR-004]
- [ ] CHK012 Are each of the six `checks` booleans defined with a deterministic derivation rule? [Completeness, Spec §FR-009 – FR-013]
- [ ] CHK013 Are all five `scores` fields defined with pinned formulas (not "a weighted aggregate" alone)? [Completeness, Spec §FR-017 §Clarifications]
- [ ] CHK014 Is the shape of `consensus_summary` pinned to its stage 1 values (`mode = "single_voter_baseline"`, `agreement_level = "not_applicable"`)? [Completeness, Spec §FR-006 §US1 AC#3]
- [ ] CHK015 Are both `review_status` fields (`manual_review_required`, `review_reason`) covered by explicit rules, including when `review_reason` is `null`? [Completeness, Spec §FR-007]

## Canonical String Vocabulary

- [ ] CHK016 Are the four forcing-rule canonical strings (`"company_name_inferred"`, `"post_extraction_spam_gate_failed"`, `"secondary_identifiers_insufficient"`, `"upstream_extraction_failed"`) named explicitly in the spec, not described generically? [Clarity, Spec §FR-015 §Key Entities]
- [ ] CHK017 Is the rule "canonical strings are part of `policy_version`; renaming requires a policy bump" stated? [Clarity, Spec §FR-005 §SC-010]
- [ ] CHK018 Is `"company_name_inferred"` specifically pinned as the evaluator-coordinated string whose spelling must not change? [Clarity, Spec §FR-008 §SC-002 §US2 §Assumptions]
- [ ] CHK019 Is the rule "zero variants" stated for `"company_name_inferred"` (e.g., not `"name_inferred"` or `"vendor_name_inferred"`)? [Clarity, Spec §FR-008 §US2 AC#1]

## Per-Document Folder Contract

- [ ] CHK020 Is the output location rule "written next to `edge_extraction_output.json` in the same folder" stated? [Completeness, Spec §FR-001 §US1 AC#1]
- [ ] CHK021 Is the rule "no file outside the folder is written or modified" stated? [Completeness, Spec §FR-022 §US1 AC#7]
- [ ] CHK022 Is the rule "reserved downstream filenames (`final_structured_payload.json`, `evaluation_document.json`, `votes/`) are never created or overwritten" stated? [Completeness, Spec §FR-023 §US1 AC#7]
- [ ] CHK023 Is the rule "inputs are read-only" stated for `edge_extraction_output.json` AND for other folder files (`preprocess_output.json`, `expected.json`, `notes.md`, `source.pdf`)? [Completeness, Spec §FR-022 §US1 AC#7]

## Out-of-Scope Surface

- [ ] CHK024 Is the rule "router does not call any model / perform OCR / re-read `preprocess_output.json`" stated as a hard requirement, not as a recommendation? [Clarity, Spec §FR-019]
- [ ] CHK025 Is the rule "router does not implement final-payload assembly, evaluation, consensus comparison, ensemble reconciliation, or cloud escalation" stated? [Completeness, Spec §FR-023]
- [ ] CHK026 Is the rule "corpus-level orchestration lives in the harness, not this feature" stated? [Clarity, Spec §Assumptions]
- [ ] CHK027 Is the rule "cloud escalation, ensemble consensus, and line-item routing are out of scope and will ship with their own policy bumps" stated? [Completeness, Spec §Assumptions]

## Amendment Discipline

- [ ] CHK028 Does the spec state that any change to the frozen schema requires the governance path in `contracts/stage1_vendor_identity/AMENDMENTS.md`? [Completeness, Spec §Assumptions]
- [ ] CHK029 Does the spec state that the v1.0.0 schema is stable for the life of this feature? [Clarity, Spec §Assumptions]
