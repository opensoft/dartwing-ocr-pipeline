# Phase 1 Data Model: Freeze Schemas & Folder Contracts

**Feature**: `001-freeze-schemas-folder-contracts`
**Date**: 2026-04-12

Two data models matter here. **Model A** is the *stage 1 artifact entity set* that the contracts describe — these are the seven persisted JSON artifacts and the per-document folder. **Model B** is the *validator's internal entity set* — data structures the validator populates and emits. Both are listed below.

---

## Model A — Stage 1 artifact entities (what the contracts describe)

These entities already have their field-level shapes documented in `docs/stage1-vendor-identity/schemas.md`. This section summarizes the key structural and cross-artifact relationships so the machine-readable schemas in `contracts/stage1_vendor_identity/v1.0.0/` can be generated directly from it.

### `preprocess_output`

- **Purpose**: deterministic OCR + layout output; the basis of the Trijunction evidence packet.
- **Top-level fields**: `contract_set_version`, `pipeline_version`, `document_id`, `source_type` (must be `pdf` in stage 1), `source_file`, `page_count`, `pages[]`, `document_text`, `tables[]`, `quality`, `ingestion_sources`, `warnings[]`.
- **Nested `pages[].blocks[]`**: `block_id` (stable, pattern `^p\d+_b\d+$`), `block_type`, `bbox[4]`, `reading_order`, `text`, `confidence`.
- **Nested `pages[].raw_ocr_lines[]`**: `line_id` (stable, pattern `^p\d+_l\d+$`), `bbox[4]`, `text`, `confidence`.
- **`ingestion_sources`**: three objects (`paddleocr_vl`, `falcon_ocr`, `falcon_perception`), each with `enabled` (bool) and `status` (`success` | `failure` | `not_implemented`). `falcon_ocr` and `falcon_perception` may be `not_implemented` in stage 1 (FR-007).

### `edge_extraction_output`

- **Purpose**: model-driven structured extraction with confidence and evidence, ensemble-ready by shape.
- **Top-level fields**: `contract_set_version`, `pipeline_version`, `document_id`, `processed_at` (ISO 8601 UTC), `model_runtime`, `vote_metadata`, `document_type`, `vendor_candidate`, `invoice_header_fields`, `extraction_notes[]`, `warnings[]`, `status`.
- **`model_runtime`**: `provider`, `model_name`, `model_version`, `runtime` (e.g. `host_ollama_rocm`).
- **`vote_metadata`**: `voter_id`, `voter_role`, `consensus_mode` — required in single-voter runs with `consensus_mode = "single_voter_baseline"` (FR-010, edge case: validator rejects artifacts without `vote_metadata`).
- **`vendor_candidate.company_name`**: `{value, present, inferred, confidence, evidence[]}`.
- **`vendor_candidate.address`**: `{street_1, street_2, city, state, postal_code, country}` — each an object `{value, confidence, evidence[]}` (FR-011).
- **`vendor_candidate.tax_ids`**: `{ein, state_tax_id, vat_id, other_tax_id}` — each an object `{value, confidence, evidence[]}`; no other tax-ID types allowed (FR-012).
- **`vendor_candidate.{website, phone, email}`**: each an object `{value, confidence, evidence[]}`.
- **`invoice_header_fields`**: `{invoice_number, invoice_date, total_amount}` — `total_amount` has a `currency` alongside `value` / `confidence` / `evidence` (FR-013).
- **Evidence references**: every `evidence[]` element is a string matching a `block_id` or `line_id` produced by `preprocess_output` (Tier 2 cross-artifact rule).

### `routing_decision`

- **Purpose**: deterministic acceptance / review decision derived from extraction.
- **Top-level fields**: `contract_set_version`, `pipeline_version`, `policy_version`, `document_id`, `processed_at`, `status`, `decision` (enum: `edge_accept` | `edge_review_required`), `consensus_summary`, `scores`, `checks`, `review_status`, `reasons[]`.
- **`consensus_summary`**: `{mode, agreement_level}`. In single-voter mode, `mode = "single_voter_baseline"` and `agreement_level = "not_applicable"` (FR-015).
- **`scores`**: `{company_name_score, address_score, tax_id_score, contact_score, overall_vendor_identity_score}` — each a float in `[0.0, 1.0]`.
- **`checks`**: `{company_name_present, company_name_inferred, address_has_minimum_components, at_least_one_tax_id_present, website_or_email_present, post_extraction_spam_gate_passed}` — all bool.
- **`review_status`**: `{manual_review_required, review_reason}`. `review_reason` must be non-null whenever `manual_review_required = true` (FR-017; expressed via JSON Schema `if/then`).

### `final_structured_payload`

- **Purpose**: clean downstream handoff object.
- **Top-level fields**: `contract_set_version`, `pipeline_version`, `document_id`, `processed_at`, `document_type`, `vendor_candidate`, `review_status`, `quality_summary`, `trace`.
- **`vendor_candidate`**: flattened `{value, confidence}` per field — no `evidence[]` (FR-018). `company_name` additionally carries `{present, inferred}` (FR-018).
- **`review_status`**: same shape as in `routing_decision`.
- **`quality_summary`**: `{overall_vendor_confidence, explicit_name_found, consensus_level, secondary_identifiers_found[]}`.
- **`trace`**: `{source_file, preprocess_output_file, edge_extraction_output_file, routing_decision_file}` — relative paths inside the per-document folder.
- **Contract-local rule (FR-019)**: if `vendor_candidate.company_name.present = false`, then `vendor_candidate.company_name.inferred = true` AND `review_status.manual_review_required = true`. Expressed via JSON Schema `if/then/else`.

### `expected`

- **Purpose**: hand-labeled truth for one document; no predictions, no confidence, no evaluation outcomes.
- **Top-level fields**: `contract_set_version`, `document_id`, `difficulty` (enum: `easy` | `medium` | `hard` | `missing_name`), `challenge_tags[]` (closed vocabulary from `dataset-layout.md`), `expected_review`, `expected_vendor_candidate`, `notes` (optional string).
- **`expected_review`**: `{manual_review_required, review_reason}`.
- **`expected_vendor_candidate`**: same vendor-identity field set as `edge_extraction_output` but with plain scalar values (no `confidence`, no `evidence[]`); `company_name` carries `{value, present, inferred}`.
- **`additionalProperties: false`** at every level to forbid predictions, confidence, and any pipeline-generated metadata (FR-023).
- **Contract-local rule (FR-024)**: if `difficulty = missing_name`, then `expected_vendor_candidate.company_name.present = false`, `expected_vendor_candidate.company_name.inferred = true`, `expected_review.manual_review_required = true`, `expected_review.review_reason = "company_name_inferred"`.

### `evaluation_document`

- **Purpose**: per-document comparison result.
- **Top-level fields**: `contract_set_version`, `document_id`, `difficulty`, `challenge_tags[]`, `comparison_summary`, `document_pass_fail`, `field_results`, `notes[]`.
- **`comparison_summary`**: `{applicable_field_count, matched_field_count, mismatched_field_count, missing_prediction_count, unexpected_prediction_count, field_accuracy}`.
- **`document_pass_fail`**: `{vendor_identity_passed, review_routing_passed, overall_passed}`.
- **`field_results`**: object keyed by dotted field path (e.g. `vendor_candidate.company_name.value`); each value has `{expected, actual, result}` where `result` is one of the fixed result vocabulary `match` | `partial_match` | `mismatch` | `missing_prediction` | `unexpected_prediction` | `not_applicable` (FR-026).

### `evaluation_run_summary`

- **Purpose**: run-level aggregate across the full corpus.
- **Top-level fields**: `contract_set_version`, `run_id`, `pipeline_version`, `policy_version`, `document_count`, `overall_metrics`, `consensus_metrics`, `by_difficulty`, `by_field`, `documents[]`.
- **`overall_metrics`**: `{field_accuracy, vendor_identity_pass_rate, review_routing_pass_rate, overall_document_pass_rate}`.
- **`consensus_metrics`**: `{single_voter_baseline_runs, majority_vote_documents, split_decision_documents, unanimous_field_rate?, two_of_three_majority_rate?, split_decision_rate?}` — ensemble-only fields are optional so single-voter runs validate (FR-027).
- **`by_difficulty`**: keyed by `easy` | `medium` | `hard` | `missing_name`; each entry `{document_count, field_accuracy, overall_document_pass_rate}`.
- **`by_field`**: object keyed by the scoring-rubric field names (`company_name.value`, `address.street_1`, …, `review_reason`); each value a float in `[0.0, 1.0]`.
- **`documents[]`**: one entry per document with `{document_id, overall_passed, field_accuracy}`.
- **Tier 2 rule (edge case #9)**: `document_count` must equal `len(documents[])`.

### Folder contract (per-document + corpus-root)

- **Corpus root**: `tests/stage1_vendor_identity/`. Contains one subfolder per document plus `evaluation_run_summary.json` at the root (FR-031).
- **Per-document folder naming**: `inv_<NNN>_<difficulty>/` where `NNN` is a zero-padded sequence and `<difficulty>` is one of the four enum values.
- **Required input files**: `source.pdf` (unconditional), `expected.json` (unconditional), `notes.md` (conditional — hard for `hard`/`missing_name`, soft for `easy`/`medium`, per FR-029 and clarification 5).
- **Reserved generated filenames**: `preprocess_output.json`, `edge_extraction_output.json`, `routing_decision.json`, `final_structured_payload.json`, `evaluation_document.json`. Off-limits for anything other than pipeline or evaluator output (FR-032).
- **Reserved for ensemble**: `votes/` subdirectory and `consensus_output.json` filename. Allowed but not required in stage 1 (FR-030).

### Cross-artifact entity: company-name provenance triad

Across `expected` / `edge_extraction_output` / `routing_decision` / `final_structured_payload`, the fields `company_name.present`, `company_name.inferred`, `review_status.manual_review_required`, and `review_status.review_reason` must agree as follows:

- If `present = false`: `inferred` must be `true`, `manual_review_required` must be `true`, and `review_reason` must be `"company_name_inferred"`.
- If `present = true`: `inferred` must be `false`.
- `review_reason` is null iff `manual_review_required = false`.

Enforced by Tier 2 rule (FR-035, SC-004).

---

## Model B — Validator internal entities (what the validator manipulates)

These are the data structures inside `src/ledgerlinc_ocr/validator/`. They are also documented (as a contract) in `specs/001-freeze-schemas-folder-contracts/contracts/report.schema.json` and `module-api.md`.

### `ContractSet`

Loaded once per validator invocation from `contracts/stage1_vendor_identity/v{X.Y.Z}/contract_set.json`.

- `version: str` — e.g. `"1.0.0"`.
- `artifact_schemas: dict[ArtifactName, Path]` — resolved paths to per-artifact JSON Schema files.
- `folder_schema: Path` — path to `folder.schema.json`.
- `challenge_tags: frozenset[str]` — closed vocabulary.
- `cross_artifact_rules: list[RuleId]` — identifiers for Tier 2 rules active in this version.
- `artifact_names: list[ArtifactName]` — the seven names.

### `ArtifactName` (enum)

`preprocess_output` | `edge_extraction_output` | `routing_decision` | `final_structured_payload` | `expected` | `evaluation_document` | `evaluation_run_summary`.

### `Severity` (enum)

`error` (causes validator failure) | `warning` (non-fatal; reported but exit code still 0). Used by folder-contract `notes.md` rule (clarification 5).

### `Violation`

One entry in the structured report. Matches the shape required by FR-036a.

- `target: str` — artifact name (e.g. `"edge_extraction_output"`) or folder path.
- `field_path: str` — JSON Pointer-style path (e.g. `/vendor_candidate/company_name/value`) or empty string for artifact-level / folder-level issues.
- `violation_code: str` — stable machine code (see §Violation codes).
- `reason: str` — human-readable sentence.
- `expected: str | None` — rule or contract name violated (e.g. `"FR-012 tax_ids enum"`, `"FR-029 notes.md conditional"`). Nullable when not applicable.
- `severity: Severity` — `error` or `warning`.
- `source_file: str | None` — path to the offending artifact file (for corpus-level aggregation).

### `ValidationOutcome`

Returned by every public validator call.

- `passed: bool` — `True` iff no `error`-severity violations.
- `violations: list[Violation]`.
- `warnings: list[Violation]` — same shape, filtered by `severity == "warning"`.
- `contract_set_version_checked: str`.
- `target_summary: str` — e.g. `"artifact:edge_extraction_output"`, `"folder:tests/stage1_vendor_identity/inv_001_easy"`, `"corpus:tests/stage1_vendor_identity"`.

### `FolderInspection`

Intermediate data structure used by the folder validator. Not emitted to users directly, but feeds `Violation` construction.

- `folder_path: Path`.
- `detected_difficulty: Difficulty | None` — parsed from folder name suffix AND cross-checked against `expected.json.difficulty` if present.
- `present_files: set[str]`.
- `missing_required: set[str]`.
- `unexpected_reserved: set[str]` — reserved filenames present but holding non-pipeline content (rare; mostly detected by a future hook).
- `notes_md_status: Literal["present", "missing_hard", "missing_soft"]`.

### Violation codes (stable vocabulary)

Violation codes are strings the harness can pattern-match without parsing the `reason` field. Stability is part of the contract set — new codes added via the amendment path.

Initial vocabulary for contract set `1.0.0`:

- `SCHEMA_REQUIRED_MISSING`, `SCHEMA_TYPE_MISMATCH`, `SCHEMA_ENUM_VIOLATION`, `SCHEMA_PATTERN_VIOLATION`, `SCHEMA_ADDITIONAL_PROPERTIES`.
- `NULL_VS_EMPTY_STRING` — FR-003.
- `CONTRACT_SET_VERSION_MISSING`, `CONTRACT_SET_VERSION_INCOMPATIBLE` — FR-005a, FR-037.
- `PIPELINE_VERSION_MISSING`, `POLICY_VERSION_MISSING` — FR-004, FR-005.
- `CHALLENGE_TAG_UNKNOWN` — FR-022.
- `TAX_ID_TYPE_INVALID` — FR-012.
- `VOTE_METADATA_MISSING` — FR-010.
- `REVIEW_REASON_NULL_WHEN_REQUIRED` — FR-017.
- `EXPECTED_HAS_PREDICTIONS` — FR-023.
- `MISSING_NAME_TRIAD_VIOLATION` — FR-024, FR-019.
- `PROVENANCE_TRIAD_INCONSISTENT` — FR-035 (cross-artifact).
- `EVIDENCE_REFERENCE_UNRESOLVED` — Tier 2 evidence-consistency rule.
- `DOCUMENT_COUNT_MISMATCH` — edge case #9.
- `FOLDER_MISSING_REQUIRED_FILE` — FR-029 hard requirements.
- `FOLDER_NOTES_MISSING_SOFT` — FR-029 soft requirements (severity: `warning`).
- `FOLDER_NAME_INVALID` — FR-028 naming convention.
- `FOLDER_RESERVED_FILENAME_COLLISION` — FR-032.

---

## Relationships at a glance

```text
preprocess_output ──evidence IDs──▶ edge_extraction_output ──derives scores──▶ routing_decision ──flattens──▶ final_structured_payload
                                                                                                             │
expected  ◀─────── (comparison, per-field) ─────────────────────────────────────────────────────────────────┘
   │                                                                                                           │
   │                                                                                                           ▼
   └──▶  evaluation_document  ──aggregated──▶  evaluation_run_summary
```

All nodes above stamp `contract_set_version`. The validator's Tier 2 cross-artifact rules draw the dashed provenance-triad line across `expected ↔ edge_extraction_output ↔ routing_decision ↔ final_structured_payload`, which is not shown in the linear flow.
