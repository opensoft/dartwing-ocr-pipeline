---

description: "Task list for 010-pp-structurev3-preprocessing"
---

# Tasks: PPStructureV3 Preprocessing Migration

**Input**: Design documents from `/specs/010-pp-structurev3-preprocessing/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli-contract.md, quickstart.md
**Feature branch**: `010-pp-structurev3-preprocessing`

**Tests**: Test tasks are included because FR-013, FR-014, SC-008 explicitly require preserved/updated test behavior and spec §FR-018 / FR-019 / FR-020 pin behaviors that need new tests. This is NOT a TDD approach — tests follow each implementation slice per the established 003-era discipline.

**Organization**: Tasks grouped by user story. US1 (engine swap) is the MVP. US2 (defensive warnings) and US3 (corpus regeneration + docs) layer on top.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- File paths are repo-relative from `/workspace/projects/ledgerlinc/ledgerlinc-model-ocr-pipeline-worktrees/010-pp-structurev3-preprocessing/`

## Path Conventions

Single Python package. Source at `src/ledgerlinc_ocr/preprocessing/`, tests split across `tests/unit/preprocessing/`, `tests/integration/preprocessing/`, `tests/contract_tests/`, `tests/pipeline_tests/`. Docs at `docs/stage1-vendor-identity/` and `specs/003-pdf-preprocessing/`. No containers or separate frontend/backend paths.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Bump dependency pins and warm the model cache so the subsequent engine swap has a clean surface to land on.

- [X] T001 Bump `paddleocr` pin from `>=2.8,<3` to `>=3.5,<4`, add `paddlex[ocr]>=3.5,<4`, keep `paddlepaddle>=3.0,<4` (do not comment-out old pins — remove per FR-009) in `pyproject.toml`
- [X] T002 Pin exact engine versions (`paddleocr==3.5.0`, `paddlex[ocr]==3.5.1`, `paddlepaddle==3.3.1`) in `requirements.txt`; remove any 2.10-era pins per FR-009
- [X] T003 Reinstall the dev extras in the devcontainer venv: `.venv/bin/pip install -e ".[dev]"` (run from repo root)
- [X] T004 Warm the ~500 MB model-weight cache by running `ledgerlinc-preprocess --document-folder tests/stage1_vendor_identity/inv_001_easy` once (first invocation; downloads PP-DocBlockLayout, PP-DocLayout_plus-L, PP-OCRv5 det/rec, SLANeXt_wired, SLANet_plus, RT-DETR-L into `~/.paddlex/official_models/` per FR-015)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared building blocks that US1, US2, and US3 all depend on — new exception type, warning vocabulary module, version-string bump, and ingestion-source downgrade signal.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete. These four tasks can run in parallel except where noted.

- [X] T005 [P] Bump `SEMVER = "v0.1.0"` to `SEMVER = "v0.2.0"` in `src/ledgerlinc_ocr/preprocessing/version.py` so `build_pipeline_version()` emits `stage1-preprocess-v0.2.0+paddleocr3.5.0.0000000.dpi300` per FR-008 and research R-007
- [X] T006 [P] Add `EngineInitError(PreprocessingError)` to `src/ledgerlinc_ocr/preprocessing/errors.py` with structured fields (`cause_class`, `cause_module`, `missing_weight`, `weight_hoster_url`) and `exit_code = EXIT_INTERNAL_ERROR`, per FR-016 and research R-008
- [X] T007 [P] Create `src/ledgerlinc_ocr/preprocessing/warnings.py` module with `WARNING_CATEGORIES` list, `STATUS_DOWNGRADING` set, `build_warning(page, token, detail) -> str`, and `warning_sort_key(s) -> tuple[int, int]` per FR-020 and research R-009
- [X] T008 Extend `build_ingestion_sources()` signature in `src/ledgerlinc_ocr/preprocessing/ingestion_sources.py` with a `silent_empty_page_detected: bool = False` keyword parameter; document that `status = "failure"` when `all_pages_empty OR silent_empty_page_detected` (per FR-003 + FR-019 + spec Assumptions and data-model §IngestionSource)

**Checkpoint**: Foundation ready — T009+ can begin. T008 should land last in this phase because T025 (unit tests) in US2 will import its new signature; T005/T006/T007 are strictly parallel.

---

## Phase 3: User Story 1 — Preprocessing a Real Invoice Produces Usable Layout Evidence (Priority: P1) 🎯 MVP

**Goal**: Replace the PaddleOCR 2.10 `PPStructure` + `PaddleOCR` pair with PaddleOCR 3.5 `PPStructureV3` so `tests/stage1_vendor_identity/inv_001_easy/source.pdf` yields `pages[0].blocks.length >= 3` and non-empty `document_text` containing a case-insensitive vendor-identity token (SC-001).

**Independent Test**: Per spec §US1 Independent Test — run `ledgerlinc-preprocess --document-folder tests/stage1_vendor_identity/inv_001_easy`, open the generated `preprocess_output.json`, and confirm (a) ≥ 3 blocks, (b) non-empty `document_text`, (c) `ingestion_sources.paddleocr_vl.status == "success"`, (d) artifact validates against v1.0.0 schema. Quickstart §3 commands apply verbatim.

### Engine + pipeline rewrite (US1)

- [X] T009 [US1] Replace the two module-global engine caches (`_OCR_ENGINE`, `_STRUCTURE_ENGINE`) with a single `_ENGINE: PPStructureV3 | None` in `src/ledgerlinc_ocr/preprocessing/ocr.py` per research R-001
- [X] T010 [US1] Implement `_get_engine()` in `src/ledgerlinc_ocr/preprocessing/ocr.py` that constructs `PPStructureV3(use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False, use_formula_recognition=False, use_seal_recognition=False, use_chart_recognition=False, cpu_threads=1, enable_mkldnn=False, device="cpu", lang="en")` per R-001; catch any exception during construction and re-raise as `EngineInitError` with cause classification (weight-download vs. generic) per R-008
- [X] T011 [US1] Extend `PPSTRUCTURE_LABEL_TO_BLOCK_TYPE` in `src/ledgerlinc_ocr/preprocessing/ocr.py` with V3 labels (`paragraph_title → title`, `doc_title → title`, `abstract → text`, `content → text`, `figure_title → text`, `formula_number → text`, `chart_title → text`, `table_title → text`, `seal → text`) per research R-003 and data-model §LayoutBlock
- [X] T012 [US1] Implement `run_page(image, page_number, width, height)` in `src/ledgerlinc_ocr/preprocessing/ocr.py` that invokes `_get_engine()` once, extracts lines from `overall_ocr_res.rec_texts / rec_boxes / rec_scores`, extracts blocks from `layout_det_res.boxes`, and reuses `_parse_table_dims()` for `table_res_list`; returns `(lines, blocks, tables, warnings)` sorted by `(bbox.y0, bbox.x0, det_idx)` per research R-002 / R-004 / R-005
- [X] T013 [US1] Replace the per-page `[unknown_layout_label]` warning emission in `ocr.run_page()` (falling out of the label-mapping branch) with a call to `warnings.build_warning(page_number, "unknown_layout_label", f"label={raw_label}")` per FR-006 + FR-020
- [X] T014 [US1] Retire `ocr.run_ocr_lines()` and the paired `ocr.run_layout()` from `src/ledgerlinc_ocr/preprocessing/ocr.py` once `run_page()` is in place (FR-007) — delete, do not stub
- [X] T015 [US1] Rewire `src/ledgerlinc_ocr/preprocessing/pipeline.py` to call `ocr.run_page(...)` once per rasterized page instead of the `ocr.run_ocr_lines` + `ocr.run_layout` pair; collect returned `(lines, blocks, tables, warnings)` into the existing per-page accumulators
- [X] T016 [US1] Stop catching `EngineInitError` inside `src/ledgerlinc_ocr/preprocessing/pipeline.py`'s per-page loop — let it propagate to the caller so no artifact is ever written on init failure (FR-016)
- [X] T017 [US1] Add an `except EngineInitError` branch to `main()` in `src/ledgerlinc_ocr/preprocessing/cli.py` that emits the FR-016 JSON envelope on stderr (`{"status": "error", "kind": "engine_init_failed", "cause_class": ..., "cause_module": ..., "message": ..., "missing_weight": ..., "weight_hoster_url": ...}`) and returns `EXIT_INTERNAL_ERROR` (`3`) per contracts/cli-contract.md

### Integration-test updates for OCR-text shifts (US1)

- [X] T018 [US1] [P] Update expected OCR tokens in `tests/integration/preprocessing/test_us1_schema_valid.py` for PP-OCRv5 text shifts; add an FR-013 free-form comment next to each changed assertion identifying the OCR-text delta
- [ ] T019 [US1] [P] Update expected OCR tokens in `tests/integration/preprocessing/test_us2_multi_page.py` for PP-OCRv5 text shifts; add FR-013 delta comments
- [X] T020 [US1] [P] Update `tests/integration/preprocessing/test_us4_tables.py` for V3 `table_res_list` cell extraction shape differences vs. V2's `res.cell_bbox`; add FR-013 delta comments
- [X] T021 [US1] [P] Spot-review `tests/integration/preprocessing/test_us1_determinism.py`, `test_us1_ingestion_sources.py`, `test_us1_quality_and_text.py` for any inline OCR-text expectations; apply FR-013 comment + update if deltas arise, leave untouched otherwise

**Checkpoint**: User Story 1 complete — `inv_001_easy` yields ≥ 3 blocks + non-empty `document_text`; engine-init failures hard-fail cleanly.

---

## Phase 4: User Story 2 — Silent Layout Failures Become Visible (Priority: P1)

**Goal**: Pin the four defensive warning categories (FR-003 silent-empty-layout, FR-018 suspicious-single-block, FR-019 silent-empty-ocr, FR-006 unknown-label) in `warnings.py`, wire them into `pipeline.py` per-page checks, thread the silent-empty signal into ingestion-source status downgrade, and enforce the FR-020 ordering rule (SC-002).

**Independent Test**: Per spec §US2 Independent Test — stage a synthetic preprocessing run with a stubbed layout engine returning no regions but real OCR lines; confirm `warnings[]` contains the `[silent_empty_layout]` string and `ingestion_sources.paddleocr_vl.status == "failure"`; artifact still validates. The new integration tests T029–T033 cover each category.

### pipeline.py defensive-check wiring (US2)

- [X] T022 [US2] In `src/ledgerlinc_ocr/preprocessing/pipeline.py`, after `ocr.run_page()` returns for each page, emit the FR-003 warning via `warnings.build_warning(page, "silent_empty_layout", f"OCR produced {len(lines)} lines but layout returned zero blocks")` when `len(lines) > 0 and len(blocks) == 0`, and set a `silent_empty_page_detected = True` accumulator
- [X] T023 [US2] In `src/ledgerlinc_ocr/preprocessing/pipeline.py`, emit the FR-019 symmetric warning via `warnings.build_warning(page, "silent_empty_ocr", f"OCR returned zero lines despite {K} text-type blocks")` when `len(blocks) > 0 and len(lines) == 0 and any(b.block_type in {text,title,header,footer} for b in blocks)`, and set `silent_empty_page_detected = True`
- [X] T024 [US2] In `src/ledgerlinc_ocr/preprocessing/pipeline.py`, emit the FR-018 warning via `warnings.build_warning(page, "suspicious_single_block", f"single block covers {len(lines)} OCR lines")` when `len(lines) >= 2 and len(blocks) == 1`; do NOT set `silent_empty_page_detected`
- [X] T025 [US2] Before writing the artifact, sort `warnings_out` in `src/ledgerlinc_ocr/preprocessing/pipeline.py` using `warnings.warning_sort_key` so page-ascending (categorized first, non-categorized after) + vocabulary-lexical ordering holds per FR-020 and research R-009
- [X] T026 [US2] Pass `silent_empty_page_detected` from `pipeline.run()` into `ingestion_sources.build_ingestion_sources(...)` so `paddleocr_vl.status` downgrades to `"failure"` even when `pages_with_paddleocr_output > 0` (FR-003, FR-019 + data-model §IngestionSource)

### Unit tests (US2)

- [X] T027 [US2] [P] Add `tests/unit/preprocessing/test_warnings.py` covering `build_warning()` string format, `WARNING_CATEGORIES` lexical ordering, `STATUS_DOWNGRADING` membership, `warning_sort_key()` on mixed categorized + non-categorized input
- [X] T028 [US2] [P] Update `tests/unit/preprocessing/test_ingestion_sources.py` with cases for `silent_empty_page_detected=True` (status must be `"failure"` even with `pages_with_paddleocr_output >= 1`) and `silent_empty_page_detected=False` (status unchanged)
- [X] T029 [US2] [P] Update `tests/unit/preprocessing/test_version.py` to expect the new `stage1-preprocess-v0.2.0+paddleocr3.5.0.*.dpi300` shape

### Integration tests (US2)

- [X] T030 [US2] [P] Add `tests/integration/preprocessing/test_silent_empty_layout.py` — stub `ocr.run_page` to return lines with zero blocks on one page; assert `[silent_empty_layout]` warning present, `status == "failure"`, artifact still validates
- [X] T031 [US2] [P] Add `tests/integration/preprocessing/test_silent_empty_ocr.py` — stub `ocr.run_page` to return zero lines + one text-type block on one page; assert `[silent_empty_ocr]` warning present, `status == "failure"`, artifact still validates
- [X] T032 [US2] [P] Add `tests/integration/preprocessing/test_suspicious_single_block.py` — stub `ocr.run_page` to return `>=2` lines + exactly one block; assert `[suspicious_single_block]` warning present, `status == "success"` (no downgrade), artifact still validates
- [X] T033 [US2] [P] Add `tests/integration/preprocessing/test_unknown_layout_label.py` — stub V3 to emit a label not in `PPSTRUCTURE_LABEL_TO_BLOCK_TYPE`; assert mapped to `"text"` and `[unknown_layout_label]` warning present, no status downgrade
- [X] T034 [US2] [P] Add `tests/integration/preprocessing/test_engine_init_hard_fail.py` — stub `PPStructureV3()` to raise during construction (weight-download subcase and generic subcase); assert CLI exits `3`, stderr carries the FR-016 JSON envelope with correct `cause_class` / `cause_module` / conditional `missing_weight`, no `preprocess_output.json` written

**Checkpoint**: User Story 2 complete — silent failures can no longer happen on either axis; warnings are byte-stable; engine-init failure is structured and hard-failing.

---

## Phase 5: User Story 3 — Corpus Baselines Regenerate Deterministically (Priority: P2)

**Goal**: Regenerate `inv_001..inv_020` baselines under the new engine, commit them with the FR-010 per-document shift summary, confirm byte-identical reruns (SC-003) and validator-clean corpus (SC-004), capture the SC-005 baseline timing, and update the four documentation surfaces named in FR-011.

**Independent Test**: Per spec §US3 Independent Test — run preprocessing twice across the corpus, sha256 each `preprocess_output.json`, confirm every digest matches between runs; run the corpus validator and confirm zero errors. Quickstart §4 and §5 commands apply verbatim.

### Corpus regeneration + verification (US3)

- [ ] T035 [US3] Run the halt-on-fail corpus sweep per research R-006 / quickstart §5: `set -e; for folder in tests/stage1_vendor_identity/inv_*/; do ledgerlinc-preprocess --document-folder "$folder"; done`; halt and investigate on any non-zero exit before re-running from the top (no partial commit)
- [ ] T036 [US3] Run the determinism smoke on `inv_001_easy` per quickstart §4: two sequential `ledgerlinc-preprocess` invocations, `diff` the two sha256 digests; fail the gate if they differ (SC-003)
- [ ] T037 [US3] Run `python -m ledgerlinc_ocr.validator validate corpus tests/stage1_vendor_identity` and confirm exit code 0 with zero artifact errors (SC-004)
- [ ] T038 [US3] Run the SC-002 grep-and-cross-reference check per quickstart §5: for every artifact carrying a `[silent_empty_layout]` or `[silent_empty_ocr]` warning, assert `ingestion_sources.paddleocr_vl.status == "failure"`; zero false negatives permitted

### Baseline timing capture (US3)

- [ ] T039 [US3] Measure cold-process + warm-rerun wall-clocks for `inv_001_easy` in the devcontainer (`time ledgerlinc-preprocess ...` twice); fill the "Baseline timings" row in `specs/010-pp-structurev3-preprocessing/research.md` with pages, both wall-clocks, CPU model (`lscpu | grep "Model name"`), RAM (`free -h`), OS (`uname -srm`), and `paddleocr` version (SC-005, Clarifications Q4)

### Documentation updates (US3 — parallel)

- [X] T040 [US3] [P] Update `docs/stage1-vendor-identity/architecture.md` processing-flow section to reference PPStructureV3 + PP-OCRv5 (replacing PPStructure + PP-OCRv4) (FR-011, SC-006)
- [X] T041 [US3] [P] Update `docs/stage1-vendor-identity/ollama-runtime.md` — replace all `paddleocr 2.10` references with `paddleocr 3.5` where applicable (FR-011, SC-006)
- [X] T042 [US3] [P] Add a V3 migration decision entry to `specs/003-pdf-preprocessing/research.md` citing this spec and `docs/stage1-vendor-identity/prd-ppstructurev3-migration.md` (FR-011)
- [X] T043 [US3] [P] Update `specs/003-pdf-preprocessing/quickstart.md` — revise PaddleOCR version references and first-run warm-up weight list (FR-011, SC-006)

### Commit the regenerated baselines (US3)

- [ ] T044 [US3] Stage all 20 regenerated `preprocess_output.json` files + all code/test/doc changes from US1/US2/US3 into a single landing commit; draft the commit body with one free-form line per document whose `document_text` changed vs. the previous baseline (Clarifications Q3 and FR-010); omit documents with no diff; do not create a separate regeneration-notes file

**Checkpoint**: User Story 3 complete — corpus baselines are committed, deterministic, validator-clean; docs reflect the new engine; SC-005 reference point is captured.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final gating — full test run, FR-014 contract/pipeline tests green, FR-020 warning-ordering final byte-stability verification, determinism under failure.

- [ ] T045 Run the full test suite from repo root and confirm green: `.venv/bin/pytest tests/contract_tests/ tests/pipeline_tests/ tests/integration/preprocessing/ tests/unit/preprocessing/` (FR-013, FR-014, SC-008). FR-015 "no new network after weight warm-up" is the regression responsibility of `tests/integration/preprocessing/test_no_ollama_no_cloud.py` within this run — confirm its assertions still reference `pytest-socket`'s network-disable hook and that it passes under V3.
- [ ] T046 Verify FR-020 warning-ordering byte-stability post-sweep: pick three regenerated artifacts, manually inspect `warnings[]` for (a) page-ascending outer, (b) vocabulary-lexical inner within a page, (c) aggregate/non-parseable warnings sorting last; re-run preprocessing on each and sha256-match (spec §FR-020 + §SC-003)
- [ ] T047 [P] Verify FR-002 holds across the corpus: for every page with `len(raw_ocr_lines) > 0`, assert `len(blocks) > 0` OR the page fires FR-003 — no silent contradictions with the clarified operational definition (Clarifications Q1)
- [ ] T048 [P] Re-run `/speckit.analyze` (or equivalent cross-artifact review) to confirm `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/cli-contract.md`, and `quickstart.md` remain consistent after implementation
- [ ] T049 Confirm SC-007: the `enable_mkldnn=False` workaround entry in `specs/010-pp-structurev3-preprocessing/research.md` is discoverable from the table of contents and carries both symptom and upstream link
- [ ] T049a Confirm FR-017: `specs/010-pp-structurev3-preprocessing/research.md` §R-010 carries (a) the three trigger criteria (V3-cannot-init, V3-regresses-on-more-than-one-doc, weights-hoster-unreachable), (b) the per-axis pivot-cost table, and (c) a cross-reference back to FR-017 — none have drifted during implementation

---

## Dependencies

User-story completion order (hard prerequisites):

- **Phase 1 (Setup, T001–T004)** must land first. Every subsequent phase depends on the new deps being installed and the model weights being cached.
- **Phase 2 (Foundational, T005–T008)** must complete before any US1/US2/US3 task.
- **US1 (Phase 3, T009–T021)** unblocks US2 — US2's warning-emission tasks layer onto US1's new `ocr.run_page()` + `pipeline.py` call sites.
- **US1 + US2 (Phases 3 + 4)** must both be green before US3's corpus sweep (T035) — otherwise the committed baselines would be mixed-engine or mixed-feature-set.
- **US3 (Phase 5)** is the last feature phase. T035 is the gating task; T040–T043 (docs) can parallelize with T036–T039 (verification).
- **Polish (Phase 6, T045–T049)** is the final gate before merge.

Story independence summary:

- **US1 is MVP** — it is independently testable (SC-001 on `inv_001_easy`) and delivers the core engine swap. A reviewer could merge US1 alone and the corpus (pre-regeneration) would be incoherent, so US1 alone is not shippable without US3's sweep — but its tests and artifact verification stand on their own.
- **US2 is independently testable** via stubbed-engine integration tests (T030–T034) that do not require US3's corpus regeneration. The warnings mechanism is functionally complete once US2 ends.
- **US3 depends on US1 + US2** being byte-stable. Running the sweep before US2 lands would capture baselines that don't exercise the defensive warnings consistently.

## Parallel execution examples

Within Phase 2 (Foundational), T005, T006, T007 are fully parallel (three separate files with no cross-deps); T008 serializes after them because pipeline.py and tests in US1/US2 import its new signature.

Within Phase 3 (US1), the integration-test updates T018, T019, T020, T021 are fully parallel (four separate test files). The code tasks T009–T017 are sequential within `ocr.py` / `pipeline.py` / `cli.py` — the same files are edited in close succession.

Within Phase 4 (US2), the unit tests (T027, T028, T029) and integration tests (T030, T031, T032, T033, T034) are fully parallel (nine separate test files). The code tasks T022–T026 are sequential within `pipeline.py` / `ingestion_sources.py`.

Within Phase 5 (US3), the four doc-update tasks (T040, T041, T042, T043) are fully parallel (four separate files). The verification tasks (T036, T037, T038, T039) can be run concurrently in separate shells once T035 completes.

Within Phase 6 (Polish), T047 and T048 are parallel (separate reviewers / separate scopes).

## Implementation strategy

**Recommended MVP merge sequence:**

1. Land Phase 1 + Phase 2 in a single preparatory PR (4 + 4 = 8 tasks). Low-risk dependency/version bumps and shared scaffolding.
2. Land Phase 3 (US1, 13 tasks) as the engine-swap PR. `inv_001_easy` produces ≥ 3 blocks; MVP achieved.
3. Land Phase 4 (US2, 13 tasks) as the defensive-warnings PR. Silent failures are gone; warnings are grep-stable.
4. Land Phase 5 (US3, 10 tasks) as the corpus-regeneration PR — the commit body here is the FR-010 per-document shift summary; this is the largest diff (20 `preprocess_output.json` files).
5. Land Phase 6 (Polish, 5 tasks) as the merge-gate PR.

**Alternative**: combine Phases 3 + 4 into one PR if the reviewer prefers a single "migrate + defend" change. Phase 5 should stay on its own PR because the regenerated baselines are a distinct reviewable unit from the code change.

**Incremental-delivery safety net**: If a blocker surfaces in Phase 3 or Phase 4, revert-order is Phase 5 → Phase 4 → Phase 3 → Phase 2 → Phase 1. Each phase touches a disjoint enough set of files that a single-phase revert stays tractable.

## Task count summary

| Phase | Task range | Count |
|-------|-----------|-------|
| Phase 1 (Setup) | T001–T004 | 4 |
| Phase 2 (Foundational) | T005–T008 | 4 |
| Phase 3 (US1) | T009–T021 | 13 |
| Phase 4 (US2) | T022–T034 | 13 |
| Phase 5 (US3) | T035–T044 | 10 |
| Phase 6 (Polish) | T045–T049a | 6 |
| **Total** | **T001–T049a** | **50** |

Parallel-eligible tasks: T005, T006, T007, T018, T019, T020, T021, T027, T028, T029, T030, T031, T032, T033, T034, T040, T041, T042, T043, T047, T048 — **21 of 50** can parallelize against siblings in the same phase.
