# Implementation Plan: PPStructureV3 Preprocessing Migration

**Branch**: `010-pp-structurev3-preprocessing` | **Date**: 2026-04-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/010-pp-structurev3-preprocessing/spec.md`

## Summary

Swap the stage 1 preprocessing engine from PaddleOCR 2.10 (`PPStructure` + `PaddleOCR` + PP-OCRv4) to PaddleOCR 3.5 (`PPStructureV3` + built-in PP-OCRv5) so layout detection actually returns regions on invoice-style PDFs (today it silently returns zero blocks on `inv_001`). The migration is narrow and mostly contract-preserving: the only schema change is the v1.2.0 AMENDMENTS entry (2026-04-23) widening `block.confidence` and `ocr_line.confidence` to accept `null` when the engine omits a score or emits a value unusable under the contract's `[0.0, 1.0]` numeric domain (FR-004 / R-013); otherwise only which values populate `pages[*].blocks`, `document_text`, `ingestion_sources.paddleocr_vl`, `warnings`, and `pipeline_version` changes. New preprocessing artifacts and evidence packets emit `contract_set_version = "1.2.0"` so nullable-confidence outputs advertise the contract set that permits them.

Alongside the engine swap, preprocessing gains four pinned defensive signals so silent failures can never return:

1. **FR-003 silent-empty-layout**: `len(raw_ocr_lines) > 0 AND len(blocks) == 0` → per-page `[silent_empty_layout]` warning + document-level `ingestion_sources.paddleocr_vl.status = "failure"`.
2. **FR-019 silent-empty-ocr** (symmetric): `len(blocks) > 0 AND len(raw_ocr_lines) == 0` on a page with ≥ 1 text-type block → `[silent_empty_ocr]` warning + status downgrade.
3. **FR-018 suspicious-single-block**: `len(raw_ocr_lines) >= 2 AND len(blocks) == 1` → `[suspicious_single_block]` warning (no status downgrade).
4. **FR-006 unknown-layout-label**: V3 emits a label not in `{text, title, table, figure, header, footer}` → fall back to `"text"` + `[unknown_layout_label]` warning (no status downgrade).

All four categories share the pinned prefix format `"page N: [<category_token>] <human-readable detail>"` (FR-020) for grep-testability (SC-002). Engine-init failure (weight download / paddle exception / import error / `PPStructureV3()` construction raise) becomes a **hard-fail**: non-zero exit, no artifact written, error message names the underlying cause (FR-016).

Corpus baselines (`inv_001..inv_020`) are regenerated in one sweep; if **any document exits non-zero** (`1` unexpected, `2` input_rejected including encrypted PDFs, or `3` internal_error / engine-init), the sweep halts and restarts after the root cause is fixed — no mixed or partial baseline (FR-010, clarified Session 2026-04-23). `pipeline_version` bumps on both axes: preprocessing `v0.1.0 → v0.2.0` (material behavior change) and engine portion `paddleocr2.10.0 → paddleocr3.5.0` (FR-008). The PaddleOCR 2.10 + CDLA fallback stays doc-only in `research.md` — no 2.10 code ships (FR-017).

A second round of clarifications (Session 2026-04-22, Q16–Q19) pinned the value-sourcing and developer-ergonomics rules that were still ambiguous after the initial /speckit.tasks:

1. **FR-007 OCR threshold**: PP-OCRv5 built-in OCR runs with the engine's default recognition confidence threshold — no project override. The exact default value (engine-emitted) is recorded in `research.md` R-012 so an engine bump that moves the default surfaces during FR-010 baseline regeneration review.
2. **FR-004 confidence handling**: every block and every OCR line carries an in-range engine-emitted `confidence` float without clamping, sigmoid, or min-max remapping. Missing, non-finite, or out-of-range scores persist as `null` (not `0.0`).
3. **FR-021 `tables[]` projection**: the artifact's `tables[]` field is populated from PPStructureV3's table recognizer, projected into the frozen v1.0.0 schema shape; richer HTML / cell-level structure the engine emits beyond the schema is discarded at the persistence boundary.
4. **FR-022 debug PNG opt-in**: debug `page_*.png` emission is opt-in only via the existing `--write-page-images` flag; PNGs are never committed to the corpus and are explicitly OUTSIDE FR-004's byte-identical determinism guarantee.

A third round of clarifications (Session 2026-04-23, Q23–Q25) closed the spec-level MEDIUM findings from /speckit.analyze:

5. **FR-010 halt scope (broad)**: the halt-on-fail rule applies to ANY non-zero exit code (`1` unexpected, `2` input_rejected, `3` internal_error), not just FR-016 engine-init failures. Matches the quickstart §5 `set -e` bash loop already prescribed; subsumes the encrypted-PDF edge case (exit `2` halts the sweep like any other failure).
6. **FR-021 strict-current-shape**: `tables[]` projection is bound to the v1.0.0 schema **as of 010's landing commit**. Future AMENDMENTS entries that widen the schema (e.g., adding optional `cell_confidence`) require a matching preprocessing code change — no silent schema-widening auto-pickup.
7. **Zero-overlap edge case**: a page with `len(lines) > 0 AND len(blocks) > 0` but no block-bbox/line-bbox overlap is declared out-of-scope for this slice. If it surfaces in corpus practice, a follow-up slice introduces a fifth warning category (e.g., `[orphan_ocr_lines]`).

Ensemble-readiness, evidence-first design, CPU-only determinism, and single-writer runtime all carry over from the 003 slice unchanged.

## Technical Context

**Language/Version**: Python 3.12 (devcontainer base image, matches 001/002/003/004/005/006/007)
**Primary Dependencies**:
- Bumped:
  - `paddleocr` — from `>=2.8,<3` to `>=3.5,<4` (adds `PPStructureV3`, PP-OCRv5 server det/rec, PP-DocBlockLayout, PP-DocLayout_plus-L, SLANet / SLANeXt cell detectors, RT-DETR-L). Lockfile pins `paddleocr==3.5.0` exactly. Older `<3` pin removed (not commented).
  - `paddlepaddle` — stays at `>=3.0,<4` (CPU build); lockfile pins `paddlepaddle==3.3.1` exactly, matching the engine's oneDNN-bug-era where the `enable_mkldnn=False` workaround is needed.
- Added:
  - `paddlex[ocr]>=3.5,<4` — V3 depends on paddlex for OCR/structure pipelines. Lockfile pins `paddlex[ocr]==3.5.1` exactly.
- Unchanged: `jsonschema>=4.22,<5`, `pydantic>=2.7,<3`, `pypdfium2>=4.30,<5`, `Pillow>=10.4,<11`, `numpy>=1.26,<3`, `httpx>=0.27,<1`, `PyYAML>=6.0,<7`.
- No change to dev deps (`pytest`, `pypdf`, `pytest-socket`).

**Storage**: Filesystem only. Reads `tests/stage1_vendor_identity/inv_XXX_<difficulty>/source.pdf`, writes `preprocess_output.json` (and optional debug `page_*.png`) into the same folder. No DB, no network at steady state; first-run warm-up downloads ~500 MB of weights from `paddlepaddle.bj.bcebos.com` / `paddlex` hosters.

**Testing**: `pytest` under existing `tests/contract_tests/`, `tests/unit/preprocessing/`, and `tests/integration/preprocessing/` harnesses. No new test directory. The integration tests under `tests/integration/preprocessing/` exercise the real engine and are the primary site where OCR-text deltas surface; each diverging test gets an FR-013 free-form comment identifying the OCR-text delta. Contract tests are unaffected (they don't exercise the engine). Pipeline tests (`tests/pipeline_tests/`) are unaffected — they use default stubs.

**Target Platform**: Linux (devcontainer, native WSL Ubuntu 24.04). CPU-only, single-threaded (`cpu_threads=1`, `use_mp=False`), `enable_mkldnn=False`. No GPU, no ROCm, no cloud.

**Project Type**: Single Python package migration. No new top-level package; existing `src/ledgerlinc_ocr/preprocessing/` module is refactored in place. No CLI-surface change — `ledgerlinc-preprocess` (and `python -m ledgerlinc_ocr.preprocessing`) keep the same flags, exit codes, and stdout/stderr shape. The one CLI-observable change is FR-016 hard-fail: engine-init failure now exits non-zero with no artifact, instead of today's behavior where layout exceptions are caught per-page and surfaced as warnings.

**Performance Goals**: No hard deadline imposed by this slice. SC-005 requires that the first-run wall-clock for a single invoice in the devcontainer is **recorded** in `specs/010-pp-structurev3-preprocessing/research.md` under a "Baseline timings" heading (with exact invoice, CPU model, RAM, OS). V3 with `enable_mkldnn=False` is known to be slower than V2 on the same hardware; that's accepted in exchange for correctness.

**Constraints**:
- **Determinism**: two runs on the same PDF with the same deps MUST produce byte-identical `preprocess_output.json` (FR-004, SC-003). Includes block/line ordering, `reading_order` values, identifiers, bbox values, `document_text`, block/line `confidence` values (in-range floats or deterministic `null` placement, FR-004), and `warnings` ordering (FR-020: page-ascending; within a page, vocabulary lexical order). Debug `page_*.png` output is explicitly outside this guarantee (FR-022).
- **Contract change (narrow)**: v1.2.0 AMENDMENTS (2026-04-23) widens `preprocess_output` and mirrored `evidence_packet` structural `block.confidence` / `ocr_line.confidence` fields to accept `null` per FR-004 / R-013. The v1.0.0 and v1.1.0 directories are untouched; v1.2.0 is a strict superset. Every other schema in the stage 1 contract set is unchanged, and numeric confidence values remain bounded to `[0.0, 1.0]`. Richer V3 content (e.g., `parsing_res_list` Markdown-style blocks, V3's per-cell HTML beyond the schema's cell shape) is still discarded at the persistence boundary. `tables[]` is populated from V3's table recognizer projected into the v1.0.0-era shape **as of 010's landing commit** (FR-021 strict-current-shape).
- **No new network deps** beyond first-run model weights (FR-015). After weights are cached, preprocessing runs network-free.
- **CPU-only, single-threaded**. No GPU code path (FR-005).
- **Orientation-classification, dewarping, textline-orientation, formula, seal, chart modules stay off** (FR-005).
- **OCR recognition threshold stays at the engine default** (FR-007). No project-specific cutoff is imposed; `len(raw_ocr_lines)` reflects native PP-OCRv5 filtering only. The actual default value for `paddleocr==3.5.0` is captured in `research.md` R-012 so future bumps surface as a diff.
- **Confidence values** (FR-004). In-range engine confidences persist without clamping or normalization; missing, non-finite, or out-of-range confidences persist as `null`, never `0.0`.
- **Debug PNG output is opt-in** via `--write-page-images` (FR-022). PNGs are never committed to the corpus and are not subject to FR-004 determinism.
- **FR-016 hard-fail** on any engine-init failure — non-zero exit, no artifact, named cause.
- **FR-010 halt-on-any-non-zero** (clarified Session 2026-04-23): the corpus-regeneration sweep halts on ANY non-zero exit (`1` / `2` / `3`), not only engine-init. Encrypted-PDF exits (`2`) halt the sweep like any other failure.

**Scale/Scope**: 20-document stage 1 corpus (`inv_001..inv_020`, 5 easy / 5 medium / 5 hard / 5 missing_name). Typical invoice: 1–4 pages, US Letter / A4. One document per CLI invocation; the corpus regeneration sweep wraps the CLI in a bash loop with halt-on-nonzero.

**Deferred plan-level decisions** (from /speckit.clarify):
- **Block ordering within a page**: keep the existing `(bbox.y0, bbox.x0, det_idx)` stable sort from `src/ledgerlinc_ocr/preprocessing/ocr.py:269`. V3 output is not guaranteed deterministic in list order, so the sort is preserved; `reading_order` is assigned `1..N` from the sorted sequence. No change from 003.
- ~~**FR-013 test-file comment format**~~: promoted into spec FR-013 after `/speckit.analyze` finding I1 (2026-04-22) — spec now pins free-form prose mirroring FR-010. No longer deferred.
- ~~**OCR recognition threshold under PP-OCRv5**~~: resolved in spec FR-007 (Session 2026-04-22, Q16) — engine default, no override; default value recorded in `research.md` R-012. No longer deferred.
- ~~**`tables[]` population under V3**~~: resolved in spec FR-021 (Session 2026-04-22 Q17 + Session 2026-04-23 Q24) — project into v1.0.0 shape as of 010's landing; richer content discarded; future AMENDMENTS require matching code changes. No longer deferred.
- ~~**`confidence` source for blocks and lines**~~: resolved in spec FR-004 (Session 2026-04-22, Q18) — persist in-range floats without clamping; missing, non-finite, or out-of-range values → `null`. No longer deferred.
- ~~**Debug `page_*.png` emission policy**~~: resolved in spec FR-022 (Session 2026-04-22, Q19) — opt-in via `--write-page-images`, never committed, outside FR-004. No longer deferred.
- ~~**FR-010 halt scope**~~: resolved in spec FR-010 (Session 2026-04-23, Q23) — halt on any non-zero exit, not only engine-init. No longer deferred.
- ~~**Zero-overlap edge case handling**~~: resolved as out-of-scope (Session 2026-04-23, Q25). No longer deferred; future slice will introduce `[orphan_ocr_lines]` if corpus surfaces the condition.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against `.specify/memory/constitution.md` **v1.1.0** (2026-04-22 amendment added Quality Gate 7):

| Principle | Gate | Status |
|-----------|------|--------|
| I. One Repo, Clear Runtime Boundaries | Preprocessing stays in the pipeline layer; does not embed extraction, routing, or harness concerns; does not bundle a model server. | **PASS** — `src/ledgerlinc_ocr/preprocessing/` remains pipeline-only. Writes `preprocess_output.json` only. PaddleOCR is a pipeline dependency run in-process, not a served model. Host Ollama is untouched by this slice. |
| II. Evidence-First, Schema-First Design | Artifact MUST validate against the `preprocess_output` contract; prompts/code adapt to the schema, not the reverse. | **PASS** — FR-001 pins validation against the latest `preprocess_output.schema.json`. Contract set v1.2.0 is amended additively (2026-04-23) to permit `confidence: null`, per the FR-004 / R-013 schema-first confidence rule — the widening is documented in `contracts/stage1_vendor_identity/AMENDMENTS.md` and is a strict superset of v1.0.0/v1.1.0. Newly generated preprocessing artifacts and evidence packets emit `contract_set_version = "1.2.0"`. Richer V3 content that doesn't fit the contract is discarded. |
| III. Deterministic Control Over Model Output | Warnings, status downgrades, label-mapping fallback, block ordering, reading-order assignment are deterministic code — no model judgment. | **PASS** — FR-003, FR-006, FR-018, FR-019, FR-020 all specify code-level rules. Label mapping uses a closed dict with a deterministic `"text"` fallback. `ingestion_sources.paddleocr_vl.status` downgrade is rule-based, not model-inferred. Model confidence is a signal only, never a gate. |
| IV. Provenance and Review Safety | Preserve explicit-vs-inferred provenance. | **N/A for this slice** — preprocessing does not produce `company_name` fields. FR-002 explicitly notes preprocessing quality is independent of vendor-identity label polarity (the missing-name subset gets the same quality guarantees). Provenance is the extractor's responsibility. |
| V. Benchmarkable and Reproducible Delivery | One-document end-to-end execution; per-document folder layout preserved; byte-identical reruns. | **PASS** — CLI invocation shape, artifact location, and per-document folder contract are all unchanged. SC-003 pins rerun determinism; SC-004 pins corpus-level validator pass. SC-005 records baseline timing for future regression defense. |

**Stage 1 Scope Constraints** (constitution §"Stage 1 Scope Constraints"):
- PDF input only ✓ (no input-surface change)
- Vendor identity focus ✓ (infrastructure that the extractor needs)
- No line-item extraction ✓ (preprocessing emits `tables` for structure only; line-item interpretation stays out of scope)
- No cloud execution ✓ (FR-015)
- No latency gate ✓ (SC-005 records, does not gate)

**Quality Gates** (constitution §"Quality Gates"):
1. Pipeline vs. harness boundary preserved — this slice is pipeline-only; harness is untouched.
2. Output contracts — one narrow AMENDMENTS entry (v1.2.0, 2026-04-23) widens `preprocess_output` and mirrored `evidence_packet` structural `block.confidence` / `ocr_line.confidence` to accept `null` for engine-missing or otherwise schema-unusable scores. `docs/stage1-vendor-identity/schemas.md` carries a matching null-allowance note. Numeric confidence values remain bounded to `[0.0, 1.0]`; other schemas are unchanged.
3. Runtime behavior — FR-011 updates `docs/stage1-vendor-identity/architecture.md`, `docs/stage1-vendor-identity/ollama-runtime.md` (where it references PaddleOCR versions), `specs/003-pdf-preprocessing/research.md`, and the preprocessing quickstart.
4. Verifiable through concrete local execution — `ledgerlinc-preprocess --document-folder tests/stage1_vendor_identity/inv_001_easy` against the real engine; quickstart walks this end-to-end.
5. Runtime/container changes — dependency pin updates in `pyproject.toml` and `requirements.txt` only; no devcontainer image change, no new compose services. First-run warm-up is called out in docs.
6. Evaluation comparison preserved — `expected.json` labels are untouched. Downstream evaluator still compares `final_structured_payload.json` to `expected.json` on the regenerated baselines.
7. **Consistent with `docs/stage1-vendor-identity/architecture.md`** (constitution v1.1.0 amendment, 2026-04-22) — this spec and plan do not deviate from the target architecture. The trijunction-ingestion → triple-voter → deterministic-routing shape described in architecture.md is preserved; this slice narrows stage 1 to a single-engine (PaddleOCR-only) preprocessing lane, which architecture.md itself identifies as the "stage 1 slice" starting point. No deviation declaration required.

**Result: PASS.** No constitution violations. Complexity Tracking section left empty.

**Post-Phase-1 re-check (after Session 2026-04-22 Q16–Q19 + Session 2026-04-23 Q23–Q25 landed and Phase 1 artifacts were updated):** all five principles + all seven quality gates still PASS. FR-004 schema-first confidence handling and FR-021 strict-current-shape `tables[]` projection both tighten Principle II (Evidence-First, Schema-First Design) — richer engine output stays in-memory but the persistence boundary remains the frozen v1.0.0 schema. FR-007 engine-default OCR threshold and FR-022 debug-PNG opt-in don't touch the constitution surface. FR-010's broadened halt-on-any-non-zero exit strengthens Principle V (Benchmarkable and Reproducible Delivery) by preventing mixed-completion baselines from landing. No new Complexity Tracking entries required.

## Project Structure

### Documentation (this feature)

```text
specs/010-pp-structurev3-preprocessing/
├── plan.md              # This file
├── spec.md              # Feature specification (already exists, clarifications recorded)
├── research.md          # Phase 0 output — V3 wiring, oneDNN workaround, label set, fallback criteria, baseline timings
├── data-model.md        # Phase 1 output — V3-output-to-artifact mapping, warning-category model, status-downgrade rules
├── quickstart.md        # Phase 1 output — devcontainer walk-through: dep bump → warm-up → single-doc → corpus sweep
├── contracts/
│   └── cli-contract.md  # CLI surface delta (the artifact validates against active v1.2.0)
├── checklists/          # Existing: requirements.md, failure-handling.md, determinism.md
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

Only the `preprocessing/` module is touched. No other src paths change.

```text
src/ledgerlinc_ocr/
├── preprocessing/
│   ├── ocr.py                # REWRITTEN — retires run_ocr_lines(), replaces PPStructure with PPStructureV3.
│   │                         # Extracts OCR lines from V3's built-in overall_ocr_res; extends
│   │                         # PPSTRUCTURE_LABEL_TO_BLOCK_TYPE with V3 labels (paragraph_title,
│   │                         # doc_title, etc.); raises on engine-init failure instead of silent-retrying.
│   │                         # PP-OCRv5 default recognition threshold is kept (no override per FR-007);
│   │                         # block/line confidence persists as an in-range float or null (FR-004);
│   │                         # tables[] projected into v1.0.0 shape AS OF 010's landing commit, richer
│   │                         # V3 content discarded (FR-021 strict-current-shape).
│   ├── pipeline.py           # MODIFIED — single ocr.run_page() call replaces paired ocr.run_ocr_lines +
│   │                         # ocr.run_layout. Adds FR-003, FR-018, FR-019 warning emission and the
│   │                         # silent-empty status-downgrade signal. Propagates engine-init exceptions
│   │                         # to the CLI instead of catching-and-warning.
│   ├── version.py            # MODIFIED — SEMVER bump "v0.1.0" → "v0.2.0". build_pipeline_version()
│   │                         # produces "stage1-preprocess-v0.2.0+paddleocr3.5.0.<sha>.dpi300".
│   ├── ingestion_sources.py  # MODIFIED — adds a silent_empty_page_detected flag that downgrades
│   │                         # paddleocr_vl.status to "failure" even when pages_with_paddleocr_output > 0.
│   ├── warnings.py           # NEW — small helper module: build_warning(page, category_token, detail) →
│   │                         # "page N: [<token>] <detail>", with a closed-vocabulary dataclass so
│   │                         # FR-020 ordering (page-ascending, then category lexical) is centralized.
│   ├── cli.py                # MINOR — FR-016 error emission: when an engine-init exception escapes
│   │                         # pipeline.run(), CLI prints a structured error naming the cause and
│   │                         # exits non-zero; no artifact is ever created. The existing
│   │                         # --write-page-images flag is the FR-022 opt-in for debug page_*.png
│   │                         # emission; no new flag is introduced in this slice.
│   ├── errors.py             # MINOR — adds EngineInitError(PreprocessingError) with exit_code =
│   │                         # EXIT_INTERNAL_ERROR for weight-download / paddle-runtime / import
│   │                         # failures during PPStructureV3() construction.
│   ├── __init__.py           # unchanged
│   ├── __main__.py           # unchanged
│   ├── artifact.py           # unchanged
│   ├── rasterize.py          # unchanged
│   ├── identifiers.py        # unchanged
│   ├── quality.py            # unchanged
│   └── document_text.py      # unchanged

tests/
├── unit/preprocessing/
│   ├── test_warnings.py             # NEW — build_warning() format, sort order, closed vocabulary.
│   ├── test_ingestion_sources.py    # MODIFIED — new silent_empty_page_detected code path.
│   ├── test_version.py              # MODIFIED — v0.2.0 prefix, new paddleocr3.5.0 segment.
│   └── (existing units preserved)
├── integration/preprocessing/
│   ├── test_us1_schema_valid.py     # MODIFIED — updated expected OCR tokens for PP-OCRv5 text shifts.
│   ├── test_us2_multi_page.py       # MODIFIED — same.
│   ├── test_us3_blank_page.py       # unchanged
│   ├── test_us3_partial_failure.py  # unchanged
│   ├── test_us3_step_failure.py     # unchanged
│   ├── test_us3_source_total_failure.py # unchanged
│   ├── test_us3_malformed_inputs.py # unchanged
│   ├── test_us4_tables.py           # MODIFIED — V3 table cell extraction shape differs from V2; updated.
│   ├── test_silent_empty_layout.py  # NEW — FR-003 violation path (stubbed layout engine, real OCR lines).
│   ├── test_silent_empty_ocr.py     # NEW — FR-019 symmetric violation path.
│   ├── test_suspicious_single_block.py # NEW — FR-018 warning but no status downgrade.
│   ├── test_unknown_layout_label.py # NEW — FR-006 warning but no status downgrade.
│   └── test_engine_init_hard_fail.py # NEW — FR-016 hard-fail: non-zero exit, no artifact, named cause.
├── contract_tests/                  # unchanged — no contract edits.
└── pipeline_tests/                  # unchanged — default stubs.

contracts/stage1_vendor_identity/v1.0.0/  # FROZEN — no files touched.
```

**Structure Decision**: In-place migration of the existing `src/ledgerlinc_ocr/preprocessing/` module. One new submodule (`warnings.py`) to centralize FR-020's closed vocabulary and ordering; everything else is modifying files that already exist. The frozen v1.0.0 contract set is untouched. No new top-level package, no container change, no CLI-surface change beyond FR-016's new hard-fail exit path.

## Complexity Tracking

> No constitution violations to justify. Section intentionally empty.
