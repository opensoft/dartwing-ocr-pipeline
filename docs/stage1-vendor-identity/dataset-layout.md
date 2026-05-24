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

### Semantic-quality corpus root (feature 022)

Feature 022 introduces a SECOND stage 1 corpus root for the deterministic semantic / table OCR quality gate, **distinct from the vendor-identity baseline** (Clarifications Q1 / Q15 / FR-026):

```text
tests/stage1_semantic_quality/
  inv_001_hard/
    preprocess_output.json    (hand-authored — Q25 / MI-25, no source.pdf)
    semantic_table_truth.json (sidecar; row-text-tokens + currency truth)
  inv_NNN_<difficulty>/
  ...
```

Both roots follow the SAME canonical subfolder pattern: `^inv_\d{3}_(easy|medium|hard)$` (Clarifications Q40). The closed difficulty vocabulary (`easy` / `medium` / `hard`) is the same as the vendor-identity baseline. The same §2 pre-inclusion PII / license screening from `labeling-guide.md` applies identically to fixtures under `tests/stage1_semantic_quality/` (Clarifications Q44 — see `labeling-guide.md` §2.1).

`tests/stage1_vendor_identity/` MUST remain the stable 20-document vendor-identity MVP baseline and MUST NOT be extended with degraded-body / semantic-quality fixtures (FR-026).

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

## Calibration folders and the canonical-pattern allowlist

Feature 022 (Clarifications Q23) pins a **default-exclude** rule for scored corpus folders:

- A subfolder of either corpus root is a **scored corpus folder** ONLY when its basename fully matches `^inv_\d{3}_(easy|medium|hard)$` (the Q40 canonical pattern, implemented as `dartwing_ocr.validator.corpus_pattern.CANONICAL_FOLDER_PATTERN` and reused by both the validator and the gate metrics aggregator).
- Every other basename — including any name carrying an extra suffix such as `inv_024_hard_degraded_body`, wrong digit count (`inv_1_hard`), wrong delimiter (`INV_001_HARD`), or unrecognized difficulty word — is **calibration / test-fixture material**. Calibration folders are validated (mandatory artifacts checked, sidecar validated when present) but they are **NEVER** silently included in scored corpus aggregation.
- This rule is the SINGLE source of truth referenced by:
  - [`MI-20`](../../specs/022-ocr-semantic-quality-gate/contracts/module-invariants.md) — calibration folders appear in per-document `semantic_document_statuses` entries but are EXCLUDED from `semantic_table_quality_metrics` aggregate counts and the `semantic_table_quality_pass_rate` computation in `evaluation_run_summary.json` (Clarifications Q39).
  - [`MI-21`](../../specs/022-ocr-semantic-quality-gate/contracts/module-invariants.md) — the canonical-pattern allowlist regex is the sole authority for determining whether a folder is a scored corpus folder; no folder with an extra suffix may appear in scored corpus evaluation output unless promoted through the full dataset / labeling / folder-contract / evaluator-contract amendment path.

The `validate corpus` subcommand renders a partitioned reporting block per [`validator-cli-contract.md`](../../specs/022-ocr-semantic-quality-gate/contracts/validator-cli-contract.md) §`validate corpus` — separate counts and valid/invalid breakdowns for the scored and calibration partitions.

Promoting a calibration folder (e.g. `inv_024_hard_degraded_body`) into committed scored corpus data requires the same change to also deliver the dataset, labeling-guide, folder-contract, and evaluator-contract amendments needed to validate and score it (FR-026 / SC-009).

## `difficulty`

Allowed values:

- `easy`
- `medium`
- `hard`
- `missing_name`

## `document_id`

The stage 1 corpus `document_id` is the full per-document folder name, including the difficulty suffix.

Examples:

- folder `inv_001_easy/` -> `document_id` `"inv_001_easy"`
- folder `inv_011_hard/` -> `document_id` `"inv_011_hard"`
- folder `inv_016_missing_name/` -> `document_id` `"inv_016_missing_name"`

The numeric prefix alone, such as `"inv_001"`, is not the corpus `document_id`.

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
