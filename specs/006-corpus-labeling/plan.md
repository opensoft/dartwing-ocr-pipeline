# Implementation Plan: Corpus Scaffolding & Human Labeling (Stage 1 Vendor-Identity)

**Branch**: `006-corpus-labeling` | **Date**: 2026-04-20 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/006-corpus-labeling/spec.md`

## Summary

Ship the 20-document stage 1 vendor-identity corpus (`tests/stage1_vendor_identity/inv_001..inv_020_*/`) with real `source.pdf` files, hand-authored `expected.json` labels conforming to the frozen `expected.schema.json` at `contract_set_version = "1.0.0"`, and `notes.md` files for every `hard` and `missing_name` document. Deliver a labeling guide at `docs/stage1-vendor-identity/labeling-guide.md` that captures all conventions (difficulty definitions, `challenge_tags` assignment rules, null-vs-empty-string policy, company-name provenance decision tree, remit-to vs vendor selection, DBA vs legal name rules, missing-name invariants, and a PII/license screening checklist). Add one narrow code change: the folder validator's `source.pdf` check is extended from "file exists" to "file exists, non-empty, parses with `pypdf` without error" (per clarification Q4).

The corpus blends team-held real-world invoices with publicly-available invoice samples used specifically to fill sparse difficulty buckets and challenge-tag coverage gaps. The single-labeler workflow is hand-editing JSON against the frozen contract, with `python -m ledgerlinc_ocr.validator validate corpus tests/stage1_vendor_identity` as the safety net. No labeling UI, no redaction pipeline, no external-reviewer step for this feature.

## Technical Context

**Language/Version**: Python 3.12 (devcontainer base image, already established)
**Primary Dependencies**: `pypdf >= 5.0, < 7` (already installed; used for PDF structural-integrity check in the validator); `jsonschema >= 4.22`, `pydantic >= 2.7` (already installed; used by existing validator — no new schemas in this feature)
**Storage**: Filesystem only. 20 `source.pdf` + 20 `expected.json` + ≥10 `notes.md` under `tests/stage1_vendor_identity/`. One new Markdown doc at `docs/stage1-vendor-identity/labeling-guide.md`. No database, no network.
**Testing**: `pytest` under `tests/contract_tests/` for the new PDF-readability validator behavior. Corpus coverage itself is verified by `python -m ledgerlinc_ocr.validator validate corpus tests/stage1_vendor_identity` (SC-001, FR-014).
**Target Platform**: Linux devcontainer (Python 3.12). No platform-specific dependencies.
**Project Type**: Single project — harness-side content authoring plus a narrow validator extension. No new package, no new service.
**Performance Goals**: Validator must remain interactive for the full 20-document corpus (well under 5 seconds wall time). PDF structural parse is O(pages) with pypdf's lazy reader and stays light.
**Constraints**: No render-stack dependency (no Poppler, no pdf2image) added to the validator; the structural check must be import-level compatible with the existing devcontainer. Labels are verbatim from source PDFs — no scoring-time normalization at label time. Corpus is "input only" at ship time: no reserved generated filenames or `votes/` subdirectories. All source PDFs must be committable as-is; no redaction workflow.
**Scale/Scope**: 20 documents, 5/5/5/5 across `easy`/`medium`/`hard`/`missing_name`. ≥10 `notes.md` (hard-required for `hard`+`missing_name`). 1 labeling guide. 1 validator code delta + ≥2 pytest cases. Updates to `docs/stage1-vendor-identity/README.md`, `tests/stage1_vendor_identity/README.md`, and `CLAUDE.md` Key References.

## Constitution Check

*Gate: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. One Repo, Clear Runtime Boundaries | PASS | This feature produces harness-side artifacts (corpus) and extends harness-side validator code. No pipeline/harness boundary is collapsed. |
| II. Evidence-First, Schema-First Design | PASS | Uses the frozen `contract_set_version = "1.0.0"` `expected.schema.json` and `folder.schema.json` as-is. No schema change; no new contract. The labeling guide adapts to the contracts, not the reverse. |
| III. Deterministic Control Over Model Output | PASS | No model involved. Labeling is a deterministic human activity. The missing-name invariants are enforced by the schema and by FR-008 / FR-016, not by model output. |
| IV. Provenance and Review Safety | PASS | The 5 `missing_name` labels **are** the canonical reference for provenance: `company_name.present == false`, `company_name.inferred == true`, `manual_review_required == true`, `review_reason == "company_name_inferred"`. FR-007 / FR-008 / FR-016 encode this. |
| V. Benchmarkable and Reproducible Delivery | PASS | This feature *creates the input* to benchmarkable evaluation — without a labeled corpus, the evaluator has nothing to compare against. Delivery is reproducible: every artifact is committed, the validator gate is deterministic, and the labeling guide documents how to reproduce a label. |

**Stage 1 Scope Constraints**: PASS. Corpus is PDF-only, vendor-identity-only, no line items, no cloud path, no latency gate. Matches the constitution's stage 1 scope verbatim.

**Quality Gates** (from constitution §Quality Gates):

1. Pipeline/harness boundary preserved ✅ (harness-side only).
2. Output contracts untouched ✅ (`contract_set_version = "1.0.0"` frozen).
3. No runtime behavior change ✅ (validator extension is harness-side).
4. Verifiable through a concrete local execution path ✅ (`python -m ledgerlinc_ocr.validator validate corpus tests/stage1_vendor_identity` + `pytest tests/contract_tests/`).
5. No runtime/container change ✅.
6. Evaluation comparison against labeled truth is *established* by this feature ✅.

**Gate Result**: **PASS**. No violations. No Complexity Tracking entries required.

## Project Structure

### Documentation (this feature)

```text
specs/006-corpus-labeling/
├── plan.md              # This file (/speckit.plan output)
├── spec.md              # Feature specification (already committed)
├── research.md          # Phase 0 output (/speckit.plan)
├── data-model.md        # Phase 1 output (/speckit.plan)
├── quickstart.md        # Phase 1 output (/speckit.plan)
├── contracts/           # Phase 1 output (/speckit.plan) — see note below
│   └── validator-delta.md  # Narrow module-API delta for the PDF-readability check
├── checklists/
│   └── requirements.md  # (already committed from /speckit.specify)
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

**Note on `contracts/`**: This feature does **not** introduce a new JSON Schema. The frozen `expected.schema.json` and `folder.schema.json` at `contract_set_version = "1.0.0"` are used verbatim. The only contract delta is one new `ViolationCode` in the validator's public API (for PDF-readability failures), captured in `contracts/validator-delta.md` rather than in a JSON Schema file.

### Source Code (repository root)

```text
# Corpus content (primary deliverable — 20 document folders)
tests/stage1_vendor_identity/
├── README.md                           # existing; updated with labeling-guide cross-link
├── inv_001_easy/                       # 5 × easy
│   ├── source.pdf
│   └── expected.json
├── inv_002_easy/
│   ├── source.pdf
│   └── expected.json
├── inv_003_easy/
│   ├── source.pdf
│   └── expected.json
├── inv_004_easy/
│   ├── source.pdf
│   └── expected.json
├── inv_005_easy/
│   ├── source.pdf
│   └── expected.json
├── inv_006_medium/                     # 5 × medium
│   ├── source.pdf
│   └── expected.json
├── inv_007_medium/
├── inv_008_medium/
├── inv_009_medium/
├── inv_010_medium/
├── inv_011_hard/                       # 5 × hard (notes.md required)
│   ├── source.pdf
│   ├── expected.json
│   └── notes.md
├── inv_012_hard/
├── inv_013_hard/
├── inv_014_hard/
├── inv_015_hard/
├── inv_016_missing_name/               # 5 × missing_name (notes.md required)
│   ├── source.pdf
│   ├── expected.json
│   └── notes.md
├── inv_017_missing_name/
├── inv_018_missing_name/
├── inv_019_missing_name/
└── inv_020_missing_name/

# Labeling guide (new document; authoritative conventions reference)
docs/stage1-vendor-identity/
├── README.md                           # existing; updated with labeling-guide link
└── labeling-guide.md                   # NEW — FR-017 deliverable

# Validator delta (code change — Q4 clarification)
src/ledgerlinc_ocr/validator/
├── folder.py                           # extended: source.pdf structural-integrity check
└── report.py                           # extended: new ViolationCode (e.g., FOLDER_SOURCE_PDF_UNREADABLE)

# Tests (contract-level unit coverage for the new check)
tests/contract_tests/
└── test_folder_source_pdf_readability.py  # NEW — covers existing/missing/empty/truncated/valid

# Cross-references
CLAUDE.md                               # Key References section gets labeling-guide.md entry
```

**Structure Decision**: This feature lives primarily under `tests/stage1_vendor_identity/` (content) and `docs/stage1-vendor-identity/` (guide). It adds one narrow validator change under `src/ledgerlinc_ocr/validator/` with matching tests under `tests/contract_tests/`. No new packages, no layout changes to the existing code tree. The corpus folders follow the frozen `folder.schema.json` contract (name pattern `^inv_\d{3}_(easy|medium|hard|missing_name)$`, unconditional files `source.pdf` + `expected.json`, conditional `notes.md`). Documents 001-005 are `easy`, 006-010 are `medium`, 011-015 are `hard`, 016-020 are `missing_name` (contiguous numeric prefixes `001`..`020`, 5/5/5/5 bucket distribution, per FR-001/FR-002).

## Complexity Tracking

*Not applicable — Constitution Check passed with no violations.*
