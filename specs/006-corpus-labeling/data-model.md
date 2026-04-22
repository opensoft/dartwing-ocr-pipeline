# Data Model: Corpus Scaffolding & Human Labeling

**Feature**: 006-corpus-labeling
**Phase**: 1 (Design & Contracts)
**Date**: 2026-04-20

This feature introduces no new persisted data types. Its entities are (a) on-disk corpus artifacts whose shape is already frozen by `contract_set_version = "1.0.0"`, and (b) one module-level value added to the validator's public API (a new `ViolationCode`). This document catalogues those entities for reference and traces each back to the authoritative schema.

---

## Scope reminder

**No new JSON Schema is introduced.** The authoritative schema files at `contracts/stage1_vendor_identity/v1.0.0/` are used verbatim:

- `expected.schema.json` — governs every `expected.json` file.
- `folder.schema.json` — governs the per-document folder layout and the corpus root.

Additions made here are **population** of entities (20 concrete documents), **conventions** (documented in `docs/stage1-vendor-identity/labeling-guide.md`), and **one** validator-internal value (`ViolationCode.FOLDER_SOURCE_PDF_UNREADABLE`).

---

## Entities

### 1. CorpusRoot

Filesystem directory that aggregates the 20 per-document folders.

- **Location**: `tests/stage1_vendor_identity/` (repo-relative; mandated by `folder.schema.json#/corpus_root_relative_to_repo`).
- **Children**: exactly 20 `DocumentFolder` subdirectories plus the existing `README.md`.
- **Invariants**:
  - 20 folders total (FR-001, SC-002).
  - Difficulty distribution: exactly 5/5/5/5 across `easy`/`medium`/`hard`/`missing_name` (FR-001).
  - Numeric prefixes contiguous from `001` through `020` with no gaps (FR-002).
  - `document_id` derived from folder names is unique across the corpus (FR-002).
- **Validator**: `validate_corpus()` in `src/ledgerlinc_ocr/validator/corpus.py`.

### 2. DocumentFolder

One real-world invoice's on-disk home.

- **Location**: `tests/stage1_vendor_identity/inv_<NNN>_<difficulty>/`.
- **Name pattern**: `^inv_\d{3}_(easy|medium|hard|missing_name)$` (from `folder.schema.json#/folder_name_pattern`).
- **Unconditional files**: `source.pdf`, `expected.json`.
- **Conditional files**:
  - `notes.md` — **hard** requirement for `hard` and `missing_name`; **soft** (warning only) for `easy` and `medium`.
- **Forbidden at ship time**:
  - Reserved generated filenames: `preprocess_output.json`, `edge_extraction_output.json`, `routing_decision.json`, `final_structured_payload.json`, `evaluation_document.json`.
  - Ensemble-reserved: `votes/` subdirectory and `consensus_output.json` file.
- **Derived value**: `document_id` = the folder name with its `_<difficulty>` suffix stripped (e.g., `inv_007_hard/` → `document_id = "inv_007"`).

### 3. SourcePDF

The original invoice file.

- **Location**: `<DocumentFolder>/source.pdf`.
- **Format**: PDF only (stage 1 scope constraint).
- **Readability gate** (extended by this feature — see § 6 below): file exists, is non-empty, and parses with `pypdf.PdfReader(path, strict=False)` without raising, including a successful `len(reader.pages)` call.
- **Commitability**: must pass the PII/license screening checklist in the labeling guide before inclusion (FR-019, research.md §5).
- **Immutability in this feature**: once a `source.pdf` is placed, it is not edited by subsequent steps; labeling updates only `expected.json` and `notes.md`.

### 4. ExpectedTruth (`expected.json`)

Hand-authored ground truth for one document.

- **Location**: `<DocumentFolder>/expected.json`.
- **Schema authority**: `contracts/stage1_vendor_identity/v1.0.0/expected.schema.json`.
- **Top-level keys** (from the schema, `additionalProperties: false`):

| Key | Type | Notes |
|-----|------|-------|
| `contract_set_version` | string matching `^\d+\.\d+\.\d+$` | Must equal `"1.0.0"` in this feature (FR-004). |
| `document_id` | non-empty string | Equals the folder's `inv_NNN` prefix (FR-005). |
| `difficulty` | enum (`easy` / `medium` / `hard` / `missing_name`) | Must equal the folder-name suffix (FR-005). |
| `challenge_tags` | array of unique strings, closed vocabulary | 18 allowed values per schema (FR-006); coverage rules in FR-015 / FR-016. |
| `expected_review` | object with `manual_review_required` (bool) + `review_reason` (string / null) | Missing-name docs: `true` + `"company_name_inferred"` (FR-008). |
| `expected_vendor_candidate` | nested object (see § 5) | The vendor-identity payload. |
| `notes` | string / null | Optional short labeler note; does not replace `notes.md`. |

- **Forbidden content**: predicted values, confidence scores, evidence pointers, OCR lines, evaluator verdicts (FR-010). The schema's `additionalProperties: false` enforces key closure; the prohibition on prediction data is a governance guarantee called out in SC-008.

### 5. VendorCandidateFields (nested under `expected_vendor_candidate`)

Fields describing the vendor's identity.

- **`company_name`**: object `{ value: string | null, present: boolean, inferred: boolean }`.
  - Non-missing docs: `present = true`, `inferred = false`, `value` is the verbatim reading of the explicit company name (FR-007).
  - Missing-name docs: `present = false`, `inferred = true`, `value` is the labeler's best guess or `null` if no defensible inference exists (FR-008, FR-009).
- **`address`**: object with `street_1`, `street_2`, `city`, `state`, `postal_code`, `country` — each `string | null`. `null` for every field absent from the source (FR-009).
- **`tax_ids`**: object with `ein`, `state_tax_id`, `vat_id`, `other_tax_id` — each `string | null`. `null` when absent.
- **`website`**, **`phone`**, **`email`**: `string | null` each; `null` when absent.

**State transitions**: none — labels are authored once and then read-only for the life of the feature. Any correction is a Git commit, not a runtime state change.

### 6. ReviewerNotes (`notes.md`)

Human-readable explanation of difficulty and traps.

- **Location**: `<DocumentFolder>/notes.md`.
- **Requirement**: mandatory for every `hard` and every `missing_name` document (10 total); soft-recommended for `easy` and `medium`.
- **Minimum content** (for the 10 hard-required files):
  - Why the document was placed in its difficulty bucket.
  - At least one concrete trap / feature that justifies the document's `challenge_tags` (FR-011, SC-005).
  - For `missing_name` documents specifically: why no explicit name was findable, what was inferred as a best-guess vendor, and which alternative entities on the page (remit-to, parent company, billing-to) were rejected (US3 Scenario 3).
- **No schema**: free-form Markdown; the validator checks presence and non-emptiness, not structure.

### 7. LabelingGuide (`docs/stage1-vendor-identity/labeling-guide.md`)

Authoritative conventions document (new in this feature).

- **Location**: `docs/stage1-vendor-identity/labeling-guide.md` (from Clarification Q1).
- **Discoverability**: cross-linked from `docs/stage1-vendor-identity/README.md` and listed in `CLAUDE.md` Key References (FR-017).
- **Required sections**: purpose, screening checklist, folder layout and naming, difficulty definitions, `expected.json` field walk-through, company-name provenance decision tree, remit-to vs vendor rules, DBA vs legal name rules, null handling, labeling workflow, dispute resolution, amendment process (research.md §4).
- **No schema**: free-form Markdown. Cross-reference accuracy and completeness are reviewer-enforced, not machine-validated for this feature.

### 8. ValidatorViolationCode (module-API addition)

One new value added to the enum in `src/ledgerlinc_ocr/validator/report.py`:

- **Name**: `FOLDER_SOURCE_PDF_UNREADABLE`.
- **Meaning**: `source.pdf` exists but is empty or fails `pypdf` structural parse.
- **Severity when emitted**: `Severity.ERROR`.
- **Target**: the document folder (same `target` convention as `FOLDER_MISSING_REQUIRED_FILE`).
- **`expected` short-citation**: `"FR-003 readable source.pdf"`.
- **Documented in**: `specs/006-corpus-labeling/contracts/validator-delta.md`.

This is the **only** public-API change introduced by this feature.

---

## Relationships

```text
CorpusRoot (tests/stage1_vendor_identity/)
  └── 20 × DocumentFolder (inv_NNN_<difficulty>/)
        ├── 1 × SourcePDF (source.pdf)          [mandatory]
        ├── 1 × ExpectedTruth (expected.json)    [mandatory]
        │       └── VendorCandidateFields
        └── 0..1 × ReviewerNotes (notes.md)      [mandatory for hard/missing_name]

docs/stage1-vendor-identity/
  └── LabelingGuide (labeling-guide.md)         [authoritative reference]

src/ledgerlinc_ocr/validator/
  └── ValidatorViolationCode.FOLDER_SOURCE_PDF_UNREADABLE   [API addition]
```

---

## Cross-references

- Folder contract: `contracts/stage1_vendor_identity/v1.0.0/folder.schema.json`
- Expected-truth contract: `contracts/stage1_vendor_identity/v1.0.0/expected.schema.json`
- Spec traceability: FR-001 through FR-020 in `spec.md` map onto the invariants listed here; each SC in `spec.md` is a measurable claim about one or more of these entities.
- Downstream consumer: `specs/003-pdf-preprocessing/quickstart.md` reads from `CorpusRoot` and each `SourcePDF`. No adapter required (SC-009).
