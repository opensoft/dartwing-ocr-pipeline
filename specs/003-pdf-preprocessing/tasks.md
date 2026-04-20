---
description: "Task list for 003-pdf-preprocessing"
---

# Tasks: PDF Preprocessing (Stage 1)

**Input**: Design documents from `/specs/003-pdf-preprocessing/`
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/cli-contract.md`, `quickstart.md`

**Tests**: Included. The spec's per-story "Independent Test" sections and Constitution Principle V (benchmarkable / reproducible delivery) make tests load-bearing for this slice. Every user story gets at least one integration test that exercises its acceptance scenarios.

**Organization**: Tasks are grouped by user story. Phase 1 + Phase 2 are shared infrastructure. Phase 3 is the MVP. Later stories slot in behind the MVP without breaking it.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks).
- **[Story]**: Which user story the task belongs to (US1, US2, US3, US4). Setup / Foundational / Polish tasks carry no story label.
- File paths are absolute within the repo root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project layout and dependency wiring so every later phase starts from a consistent base.

- [x] T001 Create module skeleton `src/ledgerlinc_ocr/preprocessing/` with empty `__init__.py`, `__main__.py`, `cli.py`, `pipeline.py`, `rasterize.py`, `ocr.py`, `identifiers.py`, `quality.py`, `document_text.py`, `ingestion_sources.py`, `artifact.py`, `errors.py`, `version.py`
- [x] T002 Add runtime dependencies to `pyproject.toml` under `[project].dependencies`: `pypdfium2>=4.30,<5`, `paddleocr>=2.8,<3`, `paddlepaddle>=3.0,<4`, `Pillow>=10.4,<11`, `numpy>=1.26,<3`
- [x] T003 [P] Reinstall editable package with new deps: `.venv/bin/pip install -e ".[dev]"` (verifies PaddleOCR CPU wheel resolves on Python 3.12)
- [x] T004 [P] Create test tree: `tests/unit/preprocessing/__init__.py`, `tests/integration/preprocessing/__init__.py`, `tests/fixtures/preprocessing/.gitkeep`
- [x] T005 [P] Register new test paths in `pyproject.toml` under `[tool.pytest.ini_options].testpaths` (add `tests/unit` and `tests/integration` alongside existing `tests/contract_tests`)
- [x] T006 Wire console script entry in `pyproject.toml` under `[project.scripts]`: `ledgerlinc-preprocess = "ledgerlinc_ocr.preprocessing.cli:main"`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core modules that every user story depends on — typed errors, page-scoped identifiers, ingestion-source status assembly, deterministic `document_text` join, and the structured `pipeline_version` builder.

**⚠️ CRITICAL**: No user story work begins until Phase 2 is green.

- [x] T007 [P] Implement typed errors in `src/ledgerlinc_ocr/preprocessing/errors.py`: `MalformedPdfError`, `EncryptedPdfError`, `NonPdfInputError`, `ZeroPagePdfError`, `PageFailure`, `LayoutFailure`, `OcrFailure`, `RasterizationFailure`
- [x] T008 [P] Implement page-scoped ID minter in `src/ledgerlinc_ocr/preprocessing/identifiers.py`: functions `mint_block_id(page_number, n)`, `mint_line_id(page_number, n)`, `assign_reading_order(blocks)` (blocks sorted by top-y, left-x, then detection index; renumbered 1..N). Honor FR-009a — IDs on page X depend only on page X's success.
- [x] T009 [P] Implement `src/ledgerlinc_ocr/preprocessing/ingestion_sources.py`: function `build_status(paddle_per_page_outcomes)` returning the three-key dict per FR-015 + FR-015a (`paddleocr_vl.status = "success"` if ≥1 page produced non-empty `blocks` or `raw_ocr_lines`, else `"failure"`; `falcon_ocr` and `falcon_perception` always `enabled: false`, `status: "not_implemented"`)
- [x] T010 [P] Implement `src/ledgerlinc_ocr/preprocessing/document_text.py`: function `build_document_text(pages)` that joins `blocks[].text` in `reading_order` ascending per page using `"\n"`, then joins pages in `page_number` ascending using `"\n\n"` (FR-010). Separators are module-level constants.
- [x] T011 [P] Implement `src/ledgerlinc_ocr/preprocessing/version.py`: `DPI = 300` constant and `build_pipeline_version()` returning `stage1-preprocess-{semver}+paddleocr{pkg_ver}.{weights_hash7}.dpi{dpi}` per research.md Decision 8. Weights hash computed once at process startup from PaddleOCR-resolved weight file paths.
- [x] T012 [P] Unit test `tests/unit/preprocessing/test_identifiers.py`: verifies `^p\d+_b\d+$` / `^p\d+_l\d+$` patterns, per-page counters reset, and that a simulated failure on page 2 does not renumber page 3 IDs (FR-009a + US1 AC#2 clause).
- [x] T013 [P] Unit test `tests/unit/preprocessing/test_document_text.py`: verifies `"\n"` intra-page separator, `"\n\n"` inter-page separator, `reading_order`-ascending ordering, and empty-page handling (empty string joined around `"\n\n"`).
- [x] T014 [P] Unit test `tests/unit/preprocessing/test_ingestion_sources.py`: verifies ≥1-page-success → `"success"`, all-fail → `"failure"`, Falcon keys always `not_implemented`, and rejects unknown source keys.
- [x] T015 [P] Unit test `tests/unit/preprocessing/test_version.py`: verifies `build_pipeline_version()` format, that mutating the DPI constant, package version, or weights hash yields a different string, and that the same inputs yield the same string byte-for-byte.

**Checkpoint**: Phase 2 green — foundational modules compile, unit tests pass, and `/speckit-implement` (or equivalent) can begin user-story work in parallel.

---

## Phase 3: User Story 1 - Produce a Schema-Valid Preprocessing Artifact for One PDF (Priority: P1) 🎯 MVP

**Goal**: Running preprocessing against a single-page invoice PDF writes a `preprocess_output.json` that validates against the frozen v1.0.0 contract and contains fully populated pages, blocks, raw OCR lines, quality signals, ingestion-source status, and a reading-order-joined `document_text`. No downstream artifacts.

**Independent Test**: Run `python -m ledgerlinc_ocr.preprocessing --document-folder tests/fixtures/preprocessing/us1_single_page/` against a single-page fixture. Exit code `0`, artifact written, `python -m ledgerlinc_ocr.validator validate artifact preprocess_output <path>` passes, `page_count == 1`, `ingestion_sources.paddleocr_vl.status == "success"`, `warnings == []`.

### Tests for User Story 1

> Write these first; they should FAIL until T024 lands.

- [x] T016 [P] [US1] Create single-page fixture PDF `tests/fixtures/preprocessing/us1_single_page/source.pdf` — a small synthetic invoice with known vendor block, one address line, one total amount line. Store generator script alongside if feasible so the fixture is reproducible.
- [x] T017 [P] [US1] Integration test `tests/integration/preprocessing/test_us1_schema_valid.py::test_ac1_schema_valid_single_page` — covers US1 AC#1 (schema validation, `source_type="pdf"`, `document_id` derivation per FR-002, `page_count==1`, one fully populated page entry).
- [x] T018 [P] [US1] Integration test `tests/integration/preprocessing/test_us1_determinism.py::test_ac2_byte_identical_rerun` — covers US1 AC#2 (run twice, diff the two `preprocess_output.json` files byte-for-byte).
- [x] T019 [P] [US1] Integration test `tests/integration/preprocessing/test_us1_ingestion_sources.py::test_ac3_source_flags` — covers US1 AC#3 (`paddleocr_vl.enabled==true, status=="success"`; Falcon keys `enabled==false, status=="not_implemented"`).
- [x] T020 [P] [US1] Integration test `tests/integration/preprocessing/test_us1_quality_and_text.py::test_ac4_quality_populated_no_warnings` + `test_ac5_document_text_reading_order` — covers US1 AC#4 and AC#5.

### Implementation for User Story 1

- [x] T021 [P] [US1] Implement `src/ledgerlinc_ocr/preprocessing/rasterize.py`: `rasterize_pdf(pdf_path) -> list[PageRaster]` using `pypdfium2` at `DPI=300`. Each `PageRaster` carries `page_number`, `width`, `height` (post-rotation per FR-005), `rotation_detected` snapped to `{0, 90, 180, 270}`, `image: PIL.Image`. Surface `EncryptedPdfError` / `MalformedPdfError` from the opener layer.
- [x] T022 [P] [US1] Implement `src/ledgerlinc_ocr/preprocessing/ocr.py`: `run_paddle(page_raster) -> (blocks, raw_ocr_lines, tables_raw)`. Configure `use_gpu=False`, `use_mp=False`, `cpu_threads=1`, `use_angle_cls=True`, `paddle.seed(0)`. Map PP-Structure labels to the closed `block_type` vocabulary per `data-model.md`; append a warning via caller for fallbacks. Sort outputs deterministically by `(bbox[1], bbox[0], detection_index)`.
- [x] T023 [P] [US1] Implement `src/ledgerlinc_ocr/preprocessing/quality.py`: `compute_quality(all_lines, all_pages) -> QualitySignals` using the provisional thresholds from research.md Decision 6 (good/fair/poor on avg confidence + low-confidence ratio; `skew_detected` at ≥2.0°; `noise_level` on low-confidence ratio). Pure function, deterministic constants.
- [x] T024 [US1] Implement `src/ledgerlinc_ocr/preprocessing/artifact.py`: `assemble(invocation, pages, tables, quality, ingestion_sources, warnings) -> dict`, then `validate_and_write(artifact_dict, out_path)` that runs the in-repo validator against `contracts/stage1_vendor_identity/v1.0.0/preprocess_output.schema.json` and performs atomic write via `preprocess_output.json.tmp-{pid}` → rename (FR-019). Raise on schema-invalid assembly; do NOT persist partials.
- [x] T025 [US1] Unit test `tests/unit/preprocessing/test_artifact.py`: verifies atomic-write sequence (temp file exists during write, gone after success; partial-file not visible on simulated crash via monkeypatched `os.rename`), and that a deliberately-malformed dict raises without writing anything.
- [x] T026 [US1] Implement `src/ledgerlinc_ocr/preprocessing/pipeline.py`: `Pipeline.run(invocation) -> Path` that orchestrates: input validation → per-page rasterize → per-page OCR → per-page identifier minting via `identifiers.py` → quality compute → ingestion-source aggregation → `document_text` build → artifact assemble + validate + atomic write. Returns the written path.
- [x] T027 [US1] Implement `src/ledgerlinc_ocr/preprocessing/cli.py` and `src/ledgerlinc_ocr/preprocessing/__main__.py`: argparse with `--document-folder` (required), `--source-file` (default `source.pdf`), `--write-page-images` (flag), `--pipeline-version` (override). Exit codes per `contracts/cli-contract.md`: `0` success, `2` malformed input, `3` schema-validation internal error, `1` unexpected. Emit single stdout JSON line on success `{"status": "ok", ...}`.
- [x] T028 [US1] Wire optional debug `page_*.png` output in `pipeline.py` when `--write-page-images` is set; confirm debug files are never read by the contract path (FR-007).

**Checkpoint**: US1 complete — MVP slice functional. Run quickstart.md Step 1–3 against the `us1_single_page` fixture and confirm all four AC tests green.

---

## Phase 4: User Story 2 - Handle Multi-Page PDFs Deterministically (Priority: P2)

**Goal**: Multi-page PDFs are rasterized page-by-page, each page gets page-scoped IDs (`p{N}_b{n}` / `p{N}_l{n}`), `reading_order` is contiguous per page, and `document_text` concatenates pages in order. Per-page `width` / `height` / `rotation_detected` are independent.

**Independent Test**: Run against a 3-page fixture. Verify `page_count == 3`, `pages[i].page_number == i+1`, identifiers unique across document and carry correct page prefixes, `document_text` contains per-page text in order separated by `"\n\n"`, and per-page rotation is recorded independently.

### Tests for User Story 2

- [x] T029 [P] [US2] Create fixture `tests/fixtures/preprocessing/us2_two_page/source.pdf` — 2 readable pages with distinct content.
- [x] T030 [P] [US2] Create fixture `tests/fixtures/preprocessing/us2_three_page_mixed/source.pdf` — 3 pages: page 1 clean portrait, page 2 rotated 90°, page 3 clean but different dimensions. All readable.
- [x] T031 [P] [US2] Integration test `tests/integration/preprocessing/test_us2_multi_page.py::test_ac1_page_count_and_unique_ids` — covers US2 AC#1.
- [x] T032 [P] [US2] Integration test `tests/integration/preprocessing/test_us2_multi_page.py::test_ac2_reading_order_per_page` — covers US2 AC#2.
- [x] T033 [P] [US2] Integration test `tests/integration/preprocessing/test_us2_multi_page.py::test_ac3_per_page_dimensions_and_rotation` — covers US2 AC#3; asserts page 2's `rotation_detected == 0` post-snap and the rotation warning format pinned in FR-006.
- [x] T034 [P] [US2] Integration test `tests/integration/preprocessing/test_us2_multi_page.py::test_ac4_document_text_concat` — covers US2 AC#4 (`"\n\n"` between pages, order follows `page_number`).

### Implementation for User Story 2

- [x] T035 [US2] Extend `src/ledgerlinc_ocr/preprocessing/pipeline.py` with a per-page loop that constructs pages independently, maintains page-scoped identifier counters (FR-009a), and passes each page's rasterized `width`/`height`/`rotation_detected` through unchanged to the assembler.
- [x] T036 [US2] Extend `src/ledgerlinc_ocr/preprocessing/rasterize.py` to emit the rotation warning string exactly as `"page {page_number}: rotation {orig}° normalized to {snapped}°"` when snapping from non-`{0,90,180,270}` raw angles (FR-006). Warning passed back to pipeline for inclusion in `warnings[]`.

**Checkpoint**: US2 complete — multi-page PDFs produce deterministic schema-valid artifacts. US1 fixtures still pass (regression check).

---

## Phase 5: User Story 3 - Degrade Gracefully on Unreadable Pages and Partial Failures (Priority: P2)

**Goal**: A PDF with a blank page, a corrupted page, or a single rasterization/OCR/layout failure still exits `0` with a schema-valid artifact; failing pages appear with empty arrays and PDF-metadata fallbacks per FR-005a; warnings describe the anomaly. Document-level malformed inputs (encrypted, zero-page, non-PDF, unreadable bytes) exit `2` with no artifact written. Writes are atomic.

**Independent Test**: Run against a PDF with one seeded-unreadable page — exit `0`, artifact valid, failing page has empty `blocks`/`raw_ocr_lines` but populated fallback `width`/`height`/`rotation_detected`, `warnings` names the page. Run against `encrypted.pdf` — exit `2`, no artifact. Run against `malformed.pdf` — exit `2`, no artifact.

### Tests for User Story 3

- [x] T037 [P] [US3] Create fixture `tests/fixtures/preprocessing/us3_partial_failure/source.pdf` — 3 pages where page 2 has a corrupted image stream (synthetic) but pages 1 and 3 are clean.
- [x] T038 [P] [US3] Create fixture `tests/fixtures/preprocessing/us3_blank_page/source.pdf` — 2 pages where page 1 is entirely blank and page 2 has content.
- [x] T039 [P] [US3] Create fixture `tests/fixtures/preprocessing/us3_encrypted/source.pdf` — a password-protected PDF.
- [x] T040 [P] [US3] Create fixture `tests/fixtures/preprocessing/us3_malformed/source.pdf` — a deliberately truncated PDF.
- [x] T041 [P] [US3] Create fixture `tests/fixtures/preprocessing/us3_non_pdf/source.pdf` — a text file renamed to `source.pdf`.
- [x] T042 [P] [US3] Create fixture `tests/fixtures/preprocessing/us3_zero_page/source.pdf` — a PDF whose page count resolves to 0.
- [x] T043 [P] [US3] Integration test `tests/integration/preprocessing/test_us3_partial_failure.py::test_ac1_one_unreadable_page` — covers US3 AC#1 including FR-005a fallback dims.
- [x] T044 [P] [US3] Integration test `tests/integration/preprocessing/test_us3_blank_page.py::test_ac2_blank_page_no_warning` — covers US3 AC#2 (silent success).
- [x] T045 [P] [US3] Integration test `tests/integration/preprocessing/test_us3_malformed_inputs.py::test_ac3_encrypted_exits_2` + `::test_ac3_malformed_exits_2` + `::test_ac3_non_pdf_exits_2` + `::test_ac3_zero_page_exits_2` — covers US3 AC#3 and all clarification cases; asserts no artifact written.
- [x] T046 [P] [US3] Integration test `tests/integration/preprocessing/test_us3_step_failure.py::test_ac4_ocr_failed_layout_succeeded` + `::test_ac4_layout_failed_ocr_succeeded` — covers US3 AC#4 symmetric rule.
- [x] T047 [P] [US3] Integration test `tests/integration/preprocessing/test_us3_source_total_failure.py::test_ac5_paddleocr_total_failure` — covers US3 AC#5 (all pages failed → `paddleocr_vl.status == "failure"`, artifact still valid, warning present). Exercise via monkeypatched `ocr.run_paddle` raising on every page.

### Implementation for User Story 3

- [x] T048 [P] [US3] Extend `src/ledgerlinc_ocr/preprocessing/rasterize.py`: detect encryption (pypdfium2 permission/password error) → raise `EncryptedPdfError`; detect truncated/unreadable bytes → `MalformedPdfError`; detect `page_count == 0` → `ZeroPagePdfError`; implement FR-005a PDF-metadata fallback (`round(point_dim × 300 / 72)`, rotation `0`) when rasterization of a single page fails while the document itself is readable.
- [x] T049 [P] [US3] Extend `src/ledgerlinc_ocr/preprocessing/pipeline.py`: wrap each page in per-step try/except boundaries. On `RasterizationFailure`: emit page record with fallback dims and empty arrays + warning. On `OcrFailure` with successful layout: keep `blocks` (with empty `text`), empty `raw_ocr_lines`, warning. On `LayoutFailure` with successful OCR: keep `raw_ocr_lines`, empty `blocks`, warning. Document-level errors (`MalformedPdfError`, `EncryptedPdfError`, `ZeroPagePdfError`, `NonPdfInputError`) propagate → CLI exit `2`, no artifact write.
- [x] T050 [P] [US3] Extend `src/ledgerlinc_ocr/preprocessing/cli.py`: magic-byte check on the input file before opening (reject non-PDF with `NonPdfInputError`); map exception classes to exit codes per `contracts/cli-contract.md` (malformed → `2`, validator reject → `3`).
- [x] T051 [US3] Extend `tests/unit/preprocessing/test_artifact.py` (created in T025) with an induced-crash test: simulate a crash mid-write via monkeypatched `os.rename` raising, and assert the original `preprocess_output.json` (if any) is untouched and no `.tmp-*` file shadows it on subsequent runs.

**Checkpoint**: US3 complete — corpus's hard and missing_name documents can be run without halting the pipeline; malformed inputs fail loud. US1 and US2 fixtures still pass.

---

## Phase 6: User Story 4 - Capture Tables and Layout Structure When Available (Priority: P3)

**Goal**: Pages with tabular structure produce at least one `block_type == "table"` block and a matching `tables[]` record with pinned shape per FR-011a. No business-field interpretation. When no tables are detected, `tables == []`.

**Independent Test**: Run against a fixture PDF with one known table. Verify at least one block has `block_type == "table"`, `tables` contains exactly one record with keys `{page_number, block_id, bbox, rows, columns}` (and optional `cells`), and no key from the forbidden list (`line_item_description`, `unit_price`, `quantity`, `line_total`) appears anywhere in the artifact.

### Tests for User Story 4

- [x] T052 [P] [US4] Create fixture `tests/fixtures/preprocessing/us4_with_table/source.pdf` — a single-page invoice with a recognizable 3×4 table.
- [x] T053 [P] [US4] Create fixture `tests/fixtures/preprocessing/us4_no_table/source.pdf` — a single-page invoice with zero tabular structure.
- [x] T054 [P] [US4] Integration test `tests/integration/preprocessing/test_us4_tables.py::test_ac1_table_captured` — covers US4 AC#1 (block + record present, bbox alignment).
- [x] T055 [P] [US4] Integration test `tests/integration/preprocessing/test_us4_tables.py::test_ac2_no_tables_empty_array` — covers US4 AC#2.
- [x] T056 [P] [US4] Integration test `tests/integration/preprocessing/test_us4_tables.py::test_ac3_structural_only_no_business_keys` — covers US4 AC#3 + FR-011a (pinned keys, no forbidden keys anywhere in artifact).

### Implementation for User Story 4

- [x] T057 [US4] Extend `src/ledgerlinc_ocr/preprocessing/ocr.py` to request PP-Structure's table recognition output (structure + cell grid) and return normalized `(rows, columns, cells)` alongside the table block's bbox.
- [x] T058 [US4] Extend `src/ledgerlinc_ocr/preprocessing/artifact.py` to assemble `tables[*]` entries with the exact key set pinned in FR-011a (`page_number`, `block_id`, `bbox`, `rows`, `columns`, optional `cells`). Include a guard that strips any unexpected keys before validation.

**Checkpoint**: US4 complete — table structural capture works without crossing into line-item parsing. US1–US3 regressions clean.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Corpus calibration, documentation alignment, and final SC validation before handoff.

- [ ] T059 Run corpus-calibration pass for quality thresholds against `tests/stage1_vendor_identity/inv_*/` and update `src/ledgerlinc_ocr/preprocessing/quality.py` constants if the provisional values in research.md Decision 6 misfire. Record final thresholds inline and bump `{semver}` in `version.py`.
- [ ] T060 [P] Run SC-002 determinism sweep: invoke preprocessing twice over the full 20-document corpus, diff all `preprocess_output.json` pairs, assert 100% byte-identity. Script at `scripts/check_determinism.sh` (create if absent).
- [ ] T061 [P] Run SC-001 schema sweep: run preprocessing over the full corpus, validate every output with `python -m ledgerlinc_ocr.validator validate corpus tests/stage1_vendor_identity/`, assert zero schema errors.
- [ ] T062 [P] Run SC-004 robustness sweep: report exit codes + artifact-written status per document across the 20-doc corpus; expect ≥ 90% success.
- [ ] T063 [P] Run `quickstart.md` end-to-end inside the devcontainer against one `tests/stage1_vendor_identity/inv_XXX_easy/` document; verify SC-008 (no cloud, no GPU, one command, exit 0, validator passes).
- [ ] T064 [P] Update top-level `CLAUDE.md` under "Key References" to include `specs/003-pdf-preprocessing/plan.md`, `research.md`, and the four checklists.
- [ ] T065 [P] Run all four checklists in `specs/003-pdf-preprocessing/checklists/` as a final review gate; any unticked release-gate items must be closed or explicitly deferred with a reason.
- [ ] T066 Verify `pip install -e .` exposes the `ledgerlinc-preprocess` console script and that a fresh shell can invoke it without `python -m`.
- [ ] T067 [P] [US1] Unit test `tests/unit/preprocessing/test_rasterize.py`: verifies `rasterize_pdf` at 300 DPI produces post-rotation `width`/`height` per FR-005, snaps out-of-vocabulary rotations to `{0,90,180,270}` per FR-006, applies the FR-005a metadata fallback (`round(point_dim × 300 / 72)`, rotation `0`) when a single page's rasterization fails, and raises `EncryptedPdfError` / `MalformedPdfError` / `ZeroPagePdfError` at the correct boundaries. Depends on T021 + T048.
- [ ] T068 [P] Unit test `tests/unit/preprocessing/test_null_discipline.py`: asserts FR-020 invariants — missing OCR text is `""` not `null` (exercised via a simulated OCR-fail-layout-succeed page where `blocks[].text == ""` and `raw_ocr_lines == []`), and a recursive walk of the assembled artifact dict finds `null` only in schema-permitted slots. Depends on T024.
- [ ] T069 [P] SC-003 verification script `scripts/check_line_id_stability.py`: run preprocessing twice over the 5 `inv_*_easy/` corpus docs, extract every `line_id` on the page containing the vendor name, assert 100% identity across the two runs. Fails the polish gate if any easy-corpus line_id differs between runs. Depends on T060.
- [ ] T070 [P] Unit test `tests/unit/preprocessing/test_falcon_extension.py`: verifies FR-016 by monkeypatching `ingestion_sources.build_status` to return a populated `falcon_ocr` record (`enabled: true, status: "success"`, contributing blocks into the per-page arrays), assembling the artifact, and confirming schema validation still passes without any edit to `contracts/stage1_vendor_identity/v1.0.0/preprocess_output.schema.json`. Depends on T009 + T024.
- [ ] T071 [P] Integration test `tests/integration/preprocessing/test_no_ollama_no_cloud.py`: verifies FR-022 + FR-023 by running preprocessing on the US1 fixture with `OLLAMA_BASE_URL=http://127.0.0.1:1` (deliberately unreachable) and outbound sockets disabled via `pytest-socket` (allowing only loopback to localhost test fixtures). Assert exit 0, valid artifact, and zero network calls — proving preprocessing is Ollama-free and cloud-free. Add `pytest-socket` to `[project.optional-dependencies].dev` if not present. Depends on T027.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately.
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user stories.
- **Phase 3 (US1, MVP)**: Depends on Phase 2. Blocks nothing else directly, but US2/US3/US4 inherit the CLI + pipeline skeleton it lays down.
- **Phase 4 (US2)**: Depends on Phase 2 + Phase 3's pipeline skeleton (T026).
- **Phase 5 (US3)**: Depends on Phase 2 + Phase 3's pipeline + artifact modules. Independent of US2.
- **Phase 6 (US4)**: Depends on Phase 2 + Phase 3's OCR + artifact modules. Independent of US2 and US3.
- **Phase 7 (Polish)**: Depends on whichever user stories are complete; minimally requires Phase 3 for the MVP lanes.

### User Story Dependencies

- **US1 (P1)**: Pure dependency on Phase 2.
- **US2 (P2)**: Needs the pipeline skeleton from US1 (T026 for the per-page loop hook point). Tests and fixtures are independent.
- **US3 (P2)**: Needs the pipeline skeleton from US1 + the atomic-write path (T024, T051). Tests and fixtures are independent.
- **US4 (P3)**: Needs the OCR wrapper from US1 (T022) + artifact assembler (T024). Tests and fixtures are independent.

### Within Each User Story

- Tests are authored first and expected to FAIL until the paired implementation lands (TDD-flavored; spec-kit convention).
- Fixtures (`[P]`) can be authored in parallel with test files.
- Module implementations within a story marked `[P]` touch different files and can run in parallel.
- Pipeline / CLI wiring tasks (usually the single non-`[P]` task in a story) are serial because they integrate the parallel work.

### Parallel Opportunities

- **Phase 1**: T003/T004/T005 all `[P]`.
- **Phase 2**: T007–T015 all `[P]` (different files).
- **Phase 3**: T016–T020 (fixtures + tests) all `[P]`; T021–T023 (rasterize + ocr + quality) all `[P]`; T024/T026/T027/T028 are serial inside artifact + pipeline + CLI.
- **Phase 4**: T029–T034 all `[P]`; T035/T036 touch different files → `[P]` each, effectively parallel with test authoring.
- **Phase 5**: T037–T047 all `[P]`; T048/T049/T050 touch different files → `[P]` each.
- **Phase 6**: T052–T056 all `[P]`; T057/T058 touch different files.
- **Phase 7**: T060–T065, T067–T071 all `[P]`.

---

## Parallel Example: User Story 1

```bash
# Kick off fixtures + tests in parallel before any implementation lands:
Task: "T016 Create single-page fixture PDF tests/fixtures/preprocessing/us1_single_page/source.pdf"
Task: "T017 Integration test tests/integration/preprocessing/test_us1_schema_valid.py"
Task: "T018 Integration test tests/integration/preprocessing/test_us1_determinism.py"
Task: "T019 Integration test tests/integration/preprocessing/test_us1_ingestion_sources.py"
Task: "T020 Integration test tests/integration/preprocessing/test_us1_quality_and_text.py"

# Then kick off the three leaf modules in parallel:
Task: "T021 Implement src/ledgerlinc_ocr/preprocessing/rasterize.py"
Task: "T022 Implement src/ledgerlinc_ocr/preprocessing/ocr.py"
Task: "T023 Implement src/ledgerlinc_ocr/preprocessing/quality.py"

# Once leaves land, serialize through the integrator tasks:
Task: "T024 Implement src/ledgerlinc_ocr/preprocessing/artifact.py"
Task: "T026 Implement src/ledgerlinc_ocr/preprocessing/pipeline.py"
Task: "T027 Implement src/ledgerlinc_ocr/preprocessing/cli.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (Setup) and Phase 2 (Foundational).
2. Complete Phase 3 (US1) — schema-valid artifact for single-page PDF.
3. **STOP and VALIDATE** — US1 tests green, quickstart.md walk-through works, `python -m ledgerlinc_ocr.validator validate artifact preprocess_output <path>` passes.
4. Ship MVP to unblock downstream extraction/routing slices.

### Incremental Delivery

1. MVP → US1 shipped.
2. Add US2 — multi-page support. Regression-check US1.
3. Add US3 — graceful degradation. Regression-check US1 + US2.
4. Add US4 — table structural capture. Regression-check US1 + US2 + US3.
5. Polish phase runs the corpus sweeps and calibrates quality thresholds.

### Parallel Team Strategy

With multiple contributors after Phase 2:

- Developer A: US1 (drives the pipeline shape; all later stories fold into it).
- Developer B (starts after US1's pipeline skeleton lands): US2 multi-page + US3 degradation; these share a failure/aggregation theme.
- Developer C (starts after US1's OCR + artifact modules land): US4 tables.

---

## Notes

- `[P]` = different files, no dependencies on incomplete tasks. Many fixtures and tests can be authored while modules are still being built; they will fail until their paired implementation lands.
- `[Story]` label maps a task to a user story for traceability. Setup / Foundational / Polish tasks carry no story label.
- Each user story is independently testable via its own fixture under `tests/fixtures/preprocessing/us{N}_*/`.
- Commit after each task or logical group.
- Respect the determinism contract at every boundary — any change that could shift byte output must bump `pipeline_version` per FR-018 and research.md Decision 8.
- Do not edit `contracts/stage1_vendor_identity/v1.0.0/*` or `src/ledgerlinc_ocr/validator/` in any task; those are consumed, not modified (per Assumptions in spec.md).
