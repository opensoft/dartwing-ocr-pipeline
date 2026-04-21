# Contract & Schema Conformance Requirements Checklist: Evaluator & Reporting

**Purpose**: Validate that every contract pin, schema validation obligation, artifact shape, and frozen-version requirement in the spec is complete, unambiguous, consistent across sections, and free of drift from the authoritative `contracts/stage1_vendor_identity/v1.0.0/` set. This is a "unit test for English" — it audits requirements quality, not implementation.
**Created**: 2026-04-21
**Feature**: [spec.md](../spec.md)
**Audience**: pre-PR reviewer (standard depth)

## `contract_set_version` Pinning — Clarity

- [ ] CHK001 Does the spec pin `contract_set_version = "1.0.0"` as the only accepted value for stage 1, in every artifact it produces? [Clarity, Spec §FR-002 / §FR-013 / §FR-014]
- [ ] CHK002 Is the rejection behavior on version drift stated consistently between `expected.json` and `final_structured_payload.json`? [Consistency, Spec §Edge Cases / §FR-013]
- [ ] CHK003 Does the spec require `contract_set_version` to be set on both `evaluation_document.json` and `evaluation_run_summary.json` outputs? [Completeness, Spec §FR-002 / §FR-014]
- [ ] CHK004 Is the pinned version anchored to the contract set (`contract_set.json`) rather than re-stated as a magic string? [Traceability, Spec §Assumptions]

## Input Schema Validation — Coverage

- [ ] CHK005 Does the spec require `expected.json` to be schema-validated before evaluation begins? [Completeness, Spec §Edge Cases (Inputs missing or schema-invalid)]
- [ ] CHK006 Does the spec require `final_structured_payload.json` to be schema-validated before evaluation begins? [Completeness, Spec §Edge Cases]
- [ ] CHK007 Is the validator-reuse decision (evaluator imports `ledgerlinc_ocr.validator`; never re-implements) stated and traceable? [Traceability, research.md §15 / contracts/module-api.md §Stability guarantees]
- [ ] CHK008 Is the "extra fields rejected by `additionalProperties:false`" behavior documented as a spec-level invariant rather than left implicit? [Clarity, Spec §Edge Cases]

## Output Schema Validation — Coverage

- [ ] CHK009 Does the spec require `evaluation_document.json` to be schema-valid before being written to disk? [Completeness, Spec §FR-002]
- [ ] CHK010 Does the spec require `evaluation_run_summary.json` to be schema-valid before being written to disk? [Completeness, Spec §FR-014]
- [ ] CHK011 Is "no partial output on validation failure" stated consistently with "exit non-zero"? [Consistency, Spec §FR-020]
- [ ] CHK012 Is the obligation to validate outputs redundant with client-side validation (i.e., the evaluator does NOT trust downstream to validate)? [Clarity / Gap, Spec §FR-002 / §FR-014]

## `evaluation_document.json` Shape — Completeness

- [ ] CHK013 Does the spec enumerate every top-level key the schema requires (`contract_set_version`, `document_id`, `difficulty`, `challenge_tags`, `comparison_summary`, `document_pass_fail`, `field_results`, `notes`)? [Completeness, Spec §Key Entities / §FR-002]
- [ ] CHK014 Is the propagation of `document_id`, `difficulty`, `challenge_tags` from `expected.json` required verbatim? [Clarity, Spec §FR-003]
- [ ] CHK015 Does the spec explain the intentional absence of a `partial_match_count` key post-clarification (so reviewers don't re-propose adding it)? [Clarity / Traceability, Spec §Clarifications / §FR-011]
- [ ] CHK016 Is the `notes` array's intended use documented (free-form strings; deterministic; not a dumping ground for non-serializable state)? [Gap / Clarity, Spec §Key Entities]

## `evaluation_run_summary.json` Shape — Completeness

- [ ] CHK017 Does the spec require every top-level key the schema mandates (`contract_set_version`, `run_id`, `document_count`, `overall_metrics`, `consensus_metrics`, `by_difficulty`, `by_field`, `documents`)? [Completeness, Spec §FR-014 / §FR-015]
- [ ] CHK018 Is the optional-field behavior for `pipeline_version` and `policy_version` documented (omit vs explicit null)? [Gap, Spec §FR-014 / data-model.md §10]
- [ ] CHK019 Are the four `by_difficulty` keys (easy, medium, hard, missing_name) stated as the complete, closed set? [Completeness, Spec §US2 AC#3]
- [ ] CHK020 Is `by_field`'s key-shape (dotted names matching `field_results`) pinned in the spec, not only the plan/research? [Clarity, Spec §US2 AC#4 / research.md §12]
- [ ] CHK021 Is every value in `by_field` constrained to `[0.0, 1.0]` in the spec, matching the schema? [Consistency, Spec §FR-015]

## `consensus_metrics` Single-Voter Semantics — Consistency

- [ ] CHK022 Does the spec pin `single_voter_baseline_runs == document_count` as a stage-1 rule, not merely a current behavior? [Clarity, Spec §FR-016]
- [ ] CHK023 Are `majority_vote_documents` and `split_decision_documents` required to be `0` in stage 1? [Completeness, Spec §FR-016]
- [ ] CHK024 Is the optional-field behavior for `unanimous_field_rate`, `two_of_three_majority_rate`, `split_decision_rate` stated (omit vs 0.0)? [Gap, Spec §FR-016 / data-model.md §8]
- [ ] CHK025 Is the forward-compatibility clause ("ensemble metrics remain as a shape but aren't populated") stated so a future ensemble voter doesn't require a schema amendment? [Coverage, Spec §FR-024]

## `document_id` Cross-Artifact Integrity — Coverage

- [ ] CHK026 Does the spec require `document_id` consistency between `expected.json` and `final_structured_payload.json`, rejecting on mismatch? [Completeness, Spec §Edge Cases / §FR-013]
- [ ] CHK027 Does the spec require evaluator outputs to carry the same `document_id` as their inputs? [Consistency, Spec §FR-003]

## Folder Contract — Boundary Definition

- [ ] CHK028 Does the spec anchor to the frozen folder contract (`folder.schema.json`) rather than re-defining per-document folder expectations? [Traceability, Spec §Key Entities / §FR-001]
- [ ] CHK029 Is the set of files the evaluator MAY write into a per-document folder (`evaluation_document.json` only) limited and stated? [Completeness, Spec §FR-001 / §FR-019]
- [ ] CHK030 Is the set of files the evaluator MAY write at the corpus root (`evaluation_run_summary.json`, `evaluation_run_summary.md`) limited and stated? [Completeness, Spec §FR-014 / §FR-021]

## Amendment Path — Traceability

- [ ] CHK031 Does the spec direct readers to `contracts/stage1_vendor_identity/AMENDMENTS.md` for any schema change, rather than silent edits? [Traceability, Spec §Assumptions / CLAUDE.md "Stage 1 contracts are machine-validated"]
- [ ] CHK032 Is schema immutability during this feature stated as a precondition (this feature consumes, doesn't amend)? [Clarity, Spec §Assumptions]

## Cross-Reference Integrity — Consistency

- [ ] CHK033 Do the Key Entities bullets agree with the schemas on required fields? [Consistency, Spec §Key Entities vs `contracts/…/v1.0.0/*.schema.json`]
- [ ] CHK034 Are FR references to schema fields (e.g., `comparison_summary.field_accuracy`, `document_pass_fail.overall_passed`) spelled identically to the schema keys? [Consistency, Spec §FR-008–§FR-011]
- [ ] CHK035 Are terminology choices (`overall_passed` vs `overall_document_passed`) aligned with the schema's actual field name? [Consistency, Spec §FR-010 vs scoring.md vs schema]

## Notes

- Check items off as completed: `[x]`.
- A "no" on any item is a contract/spec gap, not a code defect.
- Use `[Gap]` items to trigger spec amendments; use `[Traceability]` items to confirm the paper trail between spec, research, schemas, and AMENDMENTS.md.
