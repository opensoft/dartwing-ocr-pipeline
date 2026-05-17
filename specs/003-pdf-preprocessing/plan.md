# Implementation Plan: PDF Preprocessing (Stage 1)

**Branch**: `003-pdf-preprocessing` | **Date**: 2026-04-20 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-pdf-preprocessing/spec.md`

## Summary

Build the first real stage 1 slice: a PDF-only preprocessor that rasterizes an
invoice PDF at a fixed 300 DPI, runs PaddleOCR-VL for OCR + layout + tables, and
emits a deterministic `preprocess_output.json` next to `source.pdf`. The artifact
MUST validate against the frozen `contracts/stage1_vendor_identity/v1.0.0/preprocess_output.schema.json`,
carry page-scoped block/line identifiers (`p{N}_b{n}`, `p{N}_l{n}`), declare all
three Trijunction ingestion sources (with `falcon_ocr` and `falcon_perception`
as `not_implemented`), and degrade gracefully on unreadable pages. No extraction,
routing, or final payload assembly. No cloud. No GPU required — PaddleOCR runs
locally in the devcontainer (CPU); host Ollama is not involved in preprocessing.

The slice is ensemble-ready in shape — evidence-first (raw OCR lines + layout
blocks + tables), schema-first (contract is the boundary), deterministic
(byte-identical reruns). Falcon ingestion sources can be added later without
changing the contract.

## Technical Context

**Language/Version**: Python 3.12 (devcontainer base image)
**Primary Dependencies**:
- Existing: `jsonschema>=4.22,<5`, `pydantic>=2.7,<3` (already in `pyproject.toml`)
- **New for this slice**:
  - `pypdfium2>=4.30` — deterministic PDF rasterization at 300 DPI (PDFium-backed; pure-wheel, no poppler system dependency)
  - `paddleocr>=2.8,<3` — OCR + layout + table structure (PP-StructureV2 / VL pipeline). Pinned mode: CPU-only, determinism flags set.
  - `paddlepaddle>=3.0,<4` — required by PaddleOCR (CPU build)
  - `Pillow>=10.4` — image handling glue (already implicitly via paddle)
  - `numpy` — image arrays (already implicitly via paddle)
- Resolves the "paddle on 3.12 CPU" pin in Phase 0 research.
**Storage**: Filesystem only. Reads `tests/stage1_vendor_identity/inv_XXX_<difficulty>/source.pdf`, writes `preprocess_output.json` (and optional debug `page_*.png`) into the same folder. No DB, no network.
**Testing**: `pytest` under `tests/contract_tests/` (existing harness) + new `tests/unit/preprocessing/` and `tests/integration/preprocessing/`. Integration tests run against fixture PDFs checked into the repo under `tests/fixtures/preprocessing/`.
**Target Platform**: Linux (devcontainer, native WSL Ubuntu 24.04). CPU only. No GPU, no cloud.
**Project Type**: Single Python package — extends the existing `src/dartwing_ocr/` package with a new `preprocessing/` module. Adds a new CLI entry point alongside the existing validator CLI.
**Performance Goals**: None as a release gate (per constitution: "no latency target as a release gate"). Soft target: single-page easy invoice < 30s on CPU in devcontainer; 3-page document < 90s. Determinism is the hard requirement, not latency.
**Constraints**:
- Byte-identical `preprocess_output.json` across reruns (FR-012, SC-002).
- No cloud calls, no GPU dependency (FR-023, SC-008).
- Artifact MUST validate against frozen contract `v1.0.0` on first write (FR-019, SC-001).
- Runs in lightweight pipeline container; host Ollama not touched (constitution §I).
**Scale/Scope**: 20-document stage 1 corpus (5 easy / 5 medium / 5 hard / 5 missing_name). Typical invoice: 1–4 pages, US Letter / A4. This slice processes one document per invocation.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against `.specify/memory/constitution.md` v1.0.0:

| Principle | Gate | Status |
|-----------|------|--------|
| I. One Repo, Clear Runtime Boundaries | Preprocessing belongs to the pipeline layer; must not embed extraction, routing, or harness concerns; must not bundle model runtime. | **PASS** — `src/dartwing_ocr/preprocessing/` is pipeline code only. Writes `preprocess_output.json` only (FR-017, FR-022). No model runtime embedded; PaddleOCR is a pipeline dependency, not a served model. Host Ollama untouched. |
| II. Evidence-First, Schema-First Design | Artifact MUST validate against the frozen `preprocess_output` contract; prompts/code adapt to the schema, not the reverse. | **PASS** — FR-019 mandates schema validation before persist. No schema amendment needed; `contract_set_version = "1.0.0"` is consumed as-is. |
| III. Deterministic Control Over Model Output | Quality signals, rotation normalization, block/line ordering, warnings are deterministic code — no model judgment. | **PASS** — FR-013 pins quality thresholds to rule-based metrics (avg confidence, low-confidence %, skew angle). Reading order comes from PP-Structure, not a language model. |
| IV. Provenance and Review Safety | Preserve explicit-vs-inferred provenance. | **N/A for this slice** — preprocessing does not produce `company_name` fields. FR-021 forbids business-field extraction here. Provenance is a downstream slice's responsibility. |
| V. Benchmarkable and Reproducible Delivery | One-document end-to-end execution; per-document folder layout preserved. | **PASS** — CLI processes one document, writes artifact next to `source.pdf` (FR-017). SC-008 requires a documented one-command devcontainer invocation. |

**Stage 1 Scope Constraints** (constitution §"Stage 1 Scope Constraints"):
- PDF input only ✓ (FR-001)
- Vendor identity focus ✓ (this slice is prerequisite infrastructure, does not itself extract vendor identity)
- No line-item extraction ✓ (FR-024: structural tables only, no line interpretation)
- No cloud execution ✓ (FR-023)
- No latency gate ✓ (Performance Goals are soft only)

**Quality Gates** (constitution §"Quality Gates"):
1. Pipeline vs. harness boundary preserved — this slice is pipeline-only; harness changes are out of scope.
2. Output contracts unchanged — this slice consumes the frozen `preprocess_output` schema; no schema edits required. `docs/stage1-vendor-identity/schemas.md` already matches.
3. Runtime behavior — this slice does not change the Ollama runtime story; `ollama-runtime.md` requires no update.
4. Verifiable through concrete local execution — CLI `python -m dartwing_ocr.preprocessing` against a fixture PDF.
5. Runtime/container changes — none (existing `pipeline-dev` devcontainer is sufficient; a new Python package is not a container change).
6. Evaluation comparison preserved — this slice does not modify evaluation; harness still compares `final_structured_payload.json` to `expected.json`.

**Result: PASS. No constitution violations. Complexity Tracking section left empty.**

## Project Structure

### Documentation (this feature)

```text
specs/003-pdf-preprocessing/
├── plan.md              # This file
├── spec.md              # Feature specification (already exists)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── cli-contract.md  # CLI surface (artifact shape is inherited from frozen v1.0.0 schema)
├── checklists/          # Existing (spec-kit checklists)
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
src/dartwing_ocr/
├── __init__.py                         # existing
├── validator/                          # existing — contract validator
└── preprocessing/                      # NEW — this slice
    ├── __init__.py
    ├── __main__.py                     # `python -m dartwing_ocr.preprocessing`
    ├── cli.py                          # argparse entry point
    ├── pipeline.py                     # orchestrates rasterize → OCR → layout → assemble → validate → write
    ├── rasterize.py                    # pypdfium2: PDF bytes → per-page PNG/ndarray at 300 DPI
    ├── ocr.py                          # PaddleOCR-VL wrapper: image → (ocr_lines, blocks, tables)
    ├── identifiers.py                  # page-scoped id minting: p{N}_b{n}, p{N}_l{n}; reading-order assignment
    ├── quality.py                      # deterministic rules for scan_quality / skew_detected / noise_level
    ├── document_text.py                # deterministic reading-order join for document_text
    ├── ingestion_sources.py            # assembles the paddleocr_vl / falcon_ocr / falcon_perception status block
    ├── artifact.py                     # assembles preprocess_output dict, runs validator before returning
    ├── errors.py                       # typed errors: MalformedPdfError, EncryptedPdfError, PageFailure
    └── version.py                      # DPI constant + build_pipeline_version() per FR-018

tests/
├── contract_tests/                     # existing
├── unit/preprocessing/                 # NEW
│   ├── test_identifiers.py
│   ├── test_quality.py
│   ├── test_document_text.py
│   ├── test_ingestion_sources.py
│   ├── test_version.py
│   ├── test_artifact.py                # atomic-write + schema-invalid-dict rejection
│   ├── test_rasterize.py               # 300 DPI, rotation snap, FR-005a fallback, error boundaries
│   ├── test_null_discipline.py         # FR-020 — no null outside schema-permitted slots
│   └── test_falcon_extension.py        # FR-016 — ingestion-source shape accepts future Falcon wiring
├── integration/preprocessing/          # NEW — per-story files; one acceptance-scenario test per AC
│   ├── test_us1_schema_valid.py        # US1 AC#1
│   ├── test_us1_determinism.py         # US1 AC#2
│   ├── test_us1_ingestion_sources.py   # US1 AC#3
│   ├── test_us1_quality_and_text.py    # US1 AC#4 + AC#5
│   ├── test_us2_multi_page.py          # US2 all ACs
│   ├── test_us3_partial_failure.py     # US3 AC#1 + FR-005a fallback
│   ├── test_us3_blank_page.py          # US3 AC#2 (silent success)
│   ├── test_us3_malformed_inputs.py    # US3 AC#3 — encrypted / malformed / non-pdf / zero-page
│   ├── test_us3_step_failure.py        # US3 AC#4 symmetric rule
│   ├── test_us3_source_total_failure.py # US3 AC#5
│   ├── test_us4_tables.py              # US4 all ACs + FR-011a pinned keys
│   └── test_no_ollama_no_cloud.py      # FR-022 / FR-023 — preprocessing is network-free
└── fixtures/preprocessing/             # NEW — small, redistributable fixture PDFs
    ├── single_page_clean.pdf
    ├── two_page_clean.pdf
    ├── three_page_mixed.pdf            # one blank + one rotated + one clean
    ├── encrypted.pdf
    ├── malformed.pdf                   # deliberately truncated
    └── with_table.pdf
```

**Structure Decision**: Single-project Python package. The new slice lives under
`src/dartwing_ocr/preprocessing/` to sit alongside the existing `validator/`
package, preserving the "pipeline code owns preprocessing" boundary from the
constitution. The CLI is exposed both as a module (`python -m
dartwing_ocr.preprocessing`) and as a future console script (added in `pyproject.toml`
in Phase 2 tasks). Tests split into `unit/` (pure functions, no PaddleOCR) and
`integration/` (real PDF → real PaddleOCR → real schema validation).

## Complexity Tracking

> No constitution violations to justify. Section intentionally empty.
