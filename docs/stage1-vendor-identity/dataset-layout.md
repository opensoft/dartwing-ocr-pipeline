# Stage 1 Dataset Layout

## Dataset Scope

The stage 1 test set is a 20-document PDF corpus.

Composition:

- 5 easy
- 5 medium
- 5 hard
- 5 missing company name

These are real-world invoices selected to exercise vendor identification behavior rather than generic OCR demos.

## Folder Structure

Each test document gets its own folder.

```text
tests/stage1_vendor_identity/
  inv_001_easy/
    source.pdf
    expected.json
    notes.md
    preprocess_output.json
    edge_extraction_output.json
    routing_decision.json
    final_structured_payload.json
    evaluation_document.json
  inv_002_easy/
  inv_003_easy/
  ...
  inv_016_missing_name/
  ...
  evaluation_run_summary.json
```

## Why Per-Document Folders

Per-document folders are easier for humans to review because all inputs, truth labels, generated outputs, and notes live together.

This also makes it easier to inspect failures without hunting across multiple directories.

## Required Files Per Document

- `source.pdf`
  - original test document
- `expected.json`
  - human-labeled truth
- `notes.md`
  - human-readable notes about why the document is easy, medium, hard, or missing-name

Generated artifacts:

- `preprocess_output.json`
- `edge_extraction_output.json`
- `routing_decision.json`
- `final_structured_payload.json`
- `evaluation_document.json`

Optional future artifacts for ensemble mode:

- `votes/`
  - per-voter raw outputs when multiple voters are enabled
- `consensus_output.json`
  - a richer consensus artifact if field-level majority logic is stored separately later

## `difficulty`

Allowed values:

- `easy`
- `medium`
- `hard`
- `missing_name`

## `challenge_tags`

**Frozen at contract-set version `1.0.0`.** The validator rejects any `challenge_tags` value outside this closed vocabulary. Additions require the amendment path (`contracts/stage1_vendor_identity/AMENDMENTS.md`) and a contract-set version bump.

Tags:

- `explicit_company_name`
- `missing_company_name`
- `logo_only`
- `footer_only`
- `address_only`
- `website_present`
- `email_domain_present`
- `ein_present`
- `state_tax_id_present`
- `vat_id_present`
- `other_tax_id_present`
- `multi_entity_page`
- `remit_to_differs_from_vendor`
- `low_quality_scan`
- `rotated_scan`
- `dense_header`
- `portal_cover_page`
- `faint_text`

Tags are intentionally flat so they are easy to filter and summarize.

## Missing-Name Cases

The 5 missing-name cases are important enough to define explicitly.

Requirements:

- no explicit company name on the document
- best-guess company inference is allowed
- the inferred name is stored in `company_name.value`
- `company_name.present` must be `false`
- `company_name.inferred` must be `true`
- `manual_review_required` must be `true`

## Ensemble Readiness

The per-document folder layout should remain compatible with the future three-vote architecture.

That means each folder should be able to hold:

- the shared Trijunction preprocessing artifact
- one or more per-voter extraction outputs
- deterministic consensus or routing artifacts

## `notes.md`

`notes.md` is for humans, not the evaluator.

Suggested contents:

- why this document was included
- what makes it easy, medium, hard, or missing-name
- any known traps such as remit-to address mismatch or multiple company names

## Labeling Guidance

The `expected.json` file should store only the truth the system is judged against.

It should not include:

- the model's predicted answer
- intermediate OCR details
- confidence values
- evaluation results

Those belong in separate generated artifacts.
