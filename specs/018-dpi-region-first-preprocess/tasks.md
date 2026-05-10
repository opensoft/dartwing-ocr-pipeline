---
description: "Implementation tasks for feature 018: DPI Reduction And Region-First Vendor Identity Preprocess"
---

# Tasks: DPI Reduction And Region-First Vendor Identity Preprocess

**Input**: Design documents from `/specs/018-dpi-region-first-preprocess/`
**Prerequisites**: plan.md (✅), spec.md (✅), research.md (✅), data-model.md (✅), contracts/ (✅: `cli-contract.md`, `module-invariants.md`, `run-summary-schema.md`), quickstart.md (✅)

**Tests**: Included. The spec's six user stories (`US1`–`US6`) each declare an Independent Test. `plan.md` §Project Structure enumerates concrete test files under `tests/unit/preprocessing/` and `tests/pipeline_tests/` (matching the directory convention established by features 016 and 017). GPU-marked tests follow `@pytest.mark.gpu` per FR-023 and may be deferred per FR-025.

**Organization**: Tasks are grouped by user story (US1 → US6) so each story can be implemented, tested, and delivered independently. **US1 (reduced-DPI) is the MVP**; US2 (region-first) is the second core deliverable and can run in parallel with US1 once Phase 2 is done. US3 (operator visibility) lands automatically once Phase 2's `RunSummary` scaffold + US1/US2 wiring complete.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4, US5, US6)
- **`@gpu`** in a description (not a label) marks tasks that require workstation GPU and may be deferred per FR-025
- All file paths are repo-root-relative

## Path Conventions

- Source: `src/ledgerlinc_ocr/{preprocessing,pipeline}/...`
- Tests: `tests/{unit/preprocessing,pipeline_tests}/...` (matches the directory convention established by features 016 / 017)
- Feature artifacts: `specs/018-dpi-region-first-preprocess/...`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: This feature does not introduce any new pinned dependency, top-level subpackage, or build-system change (per `plan.md` §Technical Context — "No new pinned dependency"). Setup is one verification step.

- [x] T001 Verify the `gpu` pytest marker is registered at `tests/conftest.py` (carried over from features 014–017 infrastructure). FR-023 requires this marker to exist; no new marker is added by this feature.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Six independent additions that the user-story phases all build on. Tasks T002–T006 are in different files (or independent functions in `pipeline/timing.py`) and can run in parallel; T006a depends on T006 (same dataclass).

**⚠️ CRITICAL**: User-story work in Phase 3+ MUST NOT begin until T002 through T006a are complete.

- [x] T002 [P] Extend `UnknownPresetError.preset_axis: Literal[...]` from `Literal["module_set", "det_rec_variant"]` to `Literal["module_set", "det_rec_variant", "raster_profile", "region_strategy"]` in `src/ledgerlinc_ocr/preprocessing/errors.py`. Additive widening only — no new exception class, no new caller signature, no `exit_code` change (per R-018.12 / data-model.md §UnknownPresetError). Verify the Stability stance docstring in `errors.py` still reads accurately for four axes; update the inline comment block to name `raster_profile` and `region_strategy` as the two new axes added by feature 018.
- [x] T003 [P] Verify `ExitCode.UNKNOWN_PRESET = 16` in `src/ledgerlinc_ocr/pipeline/exit_codes.py` is left UNCHANGED (per R-018.12 — feature 018 reuses feature 017's exit code, does not add a new one). Update the inline comment block above the constant to note that feature 018 also routes its `raster_profile` and `region_strategy` axis fail-fast through this code.
- [x] T004 [P] Bump `SCHEMA_VERSION` `"0.1.4"` → `"0.1.5"` in `src/ledgerlinc_ocr/pipeline/timing.py`. Add a feature-018 inline comment block above the constant naming R-018.14 / FR-008 / FR-009 / FR-010 / FR-011 / `contracts/run-summary-schema.md` §1, the three additive top-level fields (`raster_profile_id`, `region_strategy_id`, `region_strategy_fallback_count`), the strict-superset relationship with 0.1.4, and the consumers-built-against-0.1.4-still-work guarantee. Sanity-check: `from ledgerlinc_ocr.pipeline.timing import SCHEMA_VERSION; assert SCHEMA_VERSION == "0.1.5"`.
- [x] T005 [P] Add module-level constants to `src/ledgerlinc_ocr/preprocessing/identifiers.py` per `data-model.md` §Identifier-string constants: `LEGACY_RASTER_PROFILE = "legacy"`, `CPU_DEFAULT_RASTER_PROFILE = "cpu-default"`, `STUB_DEFAULT_RASTER_PROFILE = "stub-default"`, `LEGACY_REGION_STRATEGY = "full-page"`, `CPU_DEFAULT_REGION_STRATEGY = "cpu-default"`, `STUB_DEFAULT_REGION_STRATEGY = "stub-default"`. Module docstring updated to note feature 018 additions alongside feature 017's existing constants. CPU-safe (no Paddle import). Sanity-check: all six identifiers import correctly.
- [x] T006 [P] Extend the `RunSummary` dataclass in `src/ledgerlinc_ocr/pipeline/timing.py` with three additive top-level fields (per `data-model.md` §RunSummary additive top-level fields and `contracts/run-summary-schema.md` §2): `raster_profile_id: str = CPU_DEFAULT_RASTER_PROFILE`, `region_strategy_id: str = CPU_DEFAULT_REGION_STRATEGY`, `region_strategy_fallback_count: int = 0`. Update `RunSummary.to_dict()` to emit them in fixed order AFTER feature 017's three fields (`module_set_id`, `det_rec_variant_id`, `ppstructure_modules_invoked`) and before the closing brace per `contracts/run-summary-schema.md` §2 table. Class docstring updated to note feature 018 additions. Sanity-check: `to_dict()` last 3 keys are `["raster_profile_id", "region_strategy_id", "region_strategy_fallback_count"]`; defaults are `cpu-default` / `cpu-default` / `0`. Existing 0.1.4 keys unchanged.
- [x] T006a Wire RunSummary threading scaffold for the three new fields through `src/ledgerlinc_ocr/pipeline/corpus_run.py` (success path + warm-init failure path) and `src/ledgerlinc_ocr/pipeline/runner.py`. At Phase 2 the new top-level fields rely on the dataclass defaults, which produce valid 0.1.5 run_summary lines on the CPU lane out-of-the-box. Inline comments at both sites name US1 (T009 / T010) as the future override site for `raster_profile_id` on GPU runs, US2 (T019 / T020) as the override site for `region_strategy_id` and `region_strategy_fallback_count`, and US4 (T033) for stub-adapter `stub-default` discrimination. Sanity-check: the stub-adapter / CPU CLI paths emit `schema_version: "0.1.5"` and the three new fields with the correct defaults. Depends on T006 (RunSummary fields exist).

**Checkpoint**: foundational pieces in place. US1 (T007–T015) and US2 (T016–T028) can begin in parallel by different developers (US1 owns `raster_profiles.py`; US2 owns `region_strategies.py` + the orchestrator changes in `pipeline.py`). US3 (T029–T031) can begin once T006a lands. US4 / US5 / US6 begin after their explicit dependencies — see §Dependencies & Execution Order below.

---

## Phase 3: User Story 1 — Reduced-DPI rasterization candidate on the GPU lane (Priority: P1) 🎯 MVP

**Goal**: A `ppstructurev3@gpu` run with `--raster-profile=reduced-v1` produces a `preprocess_output.json` valid against the existing v1.2.0 schema and a measurably lower `phase_timings.rasterization` value than the legacy DPI run on the same fixture, with `raster_profile_id="reduced-v1"` on the run_summary.

**Independent Test** (per `spec.md` §US1): single-doc `--raster-profile=reduced-v1 --preprocess-profile=ppstructurev3@gpu` run on `tests/stage1_vendor_identity/inv_001_easy/source.pdf`; legacy run on the same fixture; both produce schema-valid `preprocess_output.json`; reduced run's `phase_timings.rasterization` is strictly lower than legacy's; reduced configuration is selected via explicit configuration; legacy DPI default remains a valid selection.

### Implementation for User Story 1

- [x] T007 [P] [US1] Create `src/ledgerlinc_ocr/preprocessing/raster_profiles.py` with: (a) `RasterProfile` frozen dataclass per `data-model.md` §RasterProfile (fields `name: str`, `dpi: int`); (b) `RASTER_PROFILES` registry containing the four entries from R-018.2 — `legacy` (with `dpi = preprocessing.version.DPI` per I-018.11 single-source-of-truth), `reduced-v1` (with `dpi = 200` per R-018.3), `cpu-default` (with `dpi = 300` identity), `stub-default` (with `dpi = 300` identity); (c) `resolve_raster_profile(name: str) -> RasterProfile` raising `UnknownPresetError(preset_axis="raster_profile", preset_value=name, valid_values=tuple(RASTER_PROFILES.keys()))` on unknown name. **CPU-safe at module-load** — NO `import paddleocr` / `import paddle` at module level (FR-015 / I-018.2); only `from ledgerlinc_ocr.preprocessing.version import DPI` is imported at module load.
- [x] T008 [US1] Wire `raster_profile.dpi` into `src/ledgerlinc_ocr/preprocessing/rasterize.py`: add an optional `dpi: int = DPI` parameter to `rasterize_pdf(pdf_path, dpi=DPI)` (default preserves existing behavior); use the passed-in value in the per-page render loop. The existing `_dimensions_for_page` helper (line 98) keeps using the module-level `DPI` for the empty-page schema-fallback path; new code paths in `pipeline.py` use the resolved `RasterProfile.dpi` instead. Sanity-check: a `rasterize_pdf(pdf, dpi=200)` call produces images at 200 DPI; `rasterize_pdf(pdf)` produces images at 300 DPI (back-compat).
- [x] T009 [US1] Add `--raster-profile ID` flag + `LEDGERLINC_RASTER_PROFILE` env-var fallback to `src/ledgerlinc_ocr/preprocessing/cli.py` (single-doc) and `src/ledgerlinc_ocr/pipeline/cli.py` (warm-corpus mode) per `contracts/cli-contract.md` §1–§2. Help text per `contracts/cli-contract.md` §2 (next to feature 017's `--module-set` / `--det-rec-variant`). Read env-var fallback at CLI parse time (CLI flag wins per R-018.1). Invoke `resolve_raster_profile(value)` IMMEDIATELY after argv parse, BEFORE any Paddle / preflight import; on `UnknownPresetError`, the existing CLI catch site (already routing feature 017's `UnknownPresetError`) prints `error: unknown raster_profile: <preset_value!r> — valid values are: <…>` to stderr and exits with `ExitCode.UNKNOWN_PRESET = 16` (R-018.12 / contracts/cli-contract.md §3 / §5).
- [x] T010 [US1] Wire `raster_profile` resolution into `src/ledgerlinc_ocr/preprocessing/pipeline.py` (the orchestrator). Read the resolved `RasterProfile` from the parsed CLI args / `PreflightContext`; pass `dpi=raster_profile.dpi` into every `rasterize_pdf(...)` call site. Thread `raster_profile.name` into the `RunSummary.raster_profile_id` override site marked by T006a's inline comment in `corpus_run.py` and `runner.py`. Same-engine guarantee preserved (engine adoption from preflight unchanged). Sanity-check: a `--raster-profile=reduced-v1` run on a CPU profile uses `dpi=300` (CPU lane is unaffected per FR-015 / I-018.2 — the `dpi` parameter on the CPU rasterizer continues to default to the module-level `DPI = 300`).

### Tests for User Story 1

- [x] T011 [P] [US1] CPU-safe unit tests in `tests/unit/preprocessing/test_raster_profiles_unit.py` (per `plan.md` §Project Structure): assert (a) `set(RASTER_PROFILES.keys()) == {"legacy", "reduced-v1", "cpu-default", "stub-default"}` (I-018.1); (b) `RASTER_PROFILES["legacy"].dpi == preprocessing.version.DPI` (I-018.11 — single-source-of-truth); (c) `RASTER_PROFILES["reduced-v1"].dpi == 200` (R-018.3); (d) `RASTER_PROFILES["cpu-default"].dpi == 300` and `RASTER_PROFILES["stub-default"].dpi == 300` (R-018.2); (e) `resolve_raster_profile("legacy")` returns the legacy preset; (f) `resolve_raster_profile("reduced-v99")` raises `UnknownPresetError` with `preset_axis="raster_profile"` and `valid_values` containing all four valid names (I-018.1 / R-018.12); (g) the registry is import-safe on a host without Paddle (mock `sys.modules["paddleocr"] = None`; assert the module still imports — I-018.2).
- [x] T012 [P] [US1] CPU-safe schema-version test in `tests/pipeline_tests/test_run_summary_schema_0_1_5.py` (initial slice — assert `raster_profile_id` only; T025 / T030 extend this same file with `region_strategy_id` and `region_strategy_fallback_count` checks): `schema_version == "0.1.5"` on every emitted `run_summary`; `raster_profile_id` is present on every run; default value is `"cpu-default"` on the CPU profile and `"stub-default"` on the stub adapter; on GPU runs (parametrized under `@pytest.mark.gpu` — covers the spot-check formerly tracked as T014), the value matches the resolved preset name (`"legacy"` for no-flag and `--raster-profile=legacy` GPU runs; `"reduced-v1"` for `--raster-profile=reduced-v1` GPU runs). The `@pytest.mark.gpu` parametrization may be deferred per FR-025 and tracked in T038.
- [x] T013 [P] [US1] CPU-safe unknown-preset fail-fast test in `tests/unit/preprocessing/test_unknown_preset_value.py` (extends feature 017's coverage to feature 018's two new axes — adds `raster_profile` cases here; T026 adds `region_strategy` cases to the same file): launch the preprocess CLI subprocess with `--raster-profile=reduced-v99 --preprocess-profile=ppstructurev3@cpu`; assert exit code 16; stderr contains literal `error: unknown raster_profile:` and the four valid values; assert no `run_summary` is emitted on stdout (search for `"kind":"run_summary"` and confirm absent — I-018.1 / R-018.12).
- [ ] T014 [US1] ⏸ DEFERRED per FR-025 — `@gpu` GPU regression test in `tests/pipeline_tests/test_dpi_benchmark.py` (`@pytest.mark.gpu`): single-doc `--raster-profile=legacy --preprocess-profile=ppstructurev3@gpu` and `--raster-profile=reduced-v1 --preprocess-profile=ppstructurev3@gpu` on `tests/stage1_vendor_identity/inv_001_easy/source.pdf`; assert reduced's `phase_timings.rasterization` is strictly lower than legacy's; both `preprocess_output.json` files validate against `contracts/stage1_vendor_identity/v1.2.0/preprocess_output.schema.json`; bbox values may differ by ±1 pixel between the two outputs (per I-018.7). This is the cell `(reduced-v1, full-page)` of the four-corner matrix; T028's region-first variant supplies the other two cells of US1+US2's joint coverage. Defer per FR-025 if no GPU at landing; capture deferral in T038.
- [ ] T015 [US1] ⏸ DEFERRED per FR-025 — `@gpu` Workstation benchmark numbers — run T014 manually + record the actual `phase_timings.rasterization` and `phase_timings.per_page_inference` numbers for `(legacy, full-page)` and `(reduced-v1, full-page)` cells into `specs/018-dpi-region-first-preprocess/quickstart.md` Appendix A.1 / A.2. If GPU access is unavailable at landing, defer per FR-025 and capture the deferral in T038.

**Checkpoint**: US1 fully functional and testable independently — this is the MVP for DPI reduction. US2 may now begin (US2 depends only on Phase 2, not on US1's runtime wiring).

---

## Phase 4: User Story 2 — Region-first / header-first preprocessing path for vendor identity (Priority: P1)

**Goal**: A `ppstructurev3@gpu` run with `--region-strategy=header-first-v1` on a multi-page invoice produces a `preprocess_output.json` where page 1 carries header-band-derived blocks and pages 2..N are empty page records (per Clarifications Q2), with `region_strategy_id="header-first-v1"` on `run_summary` and `region_strategy_fallback_count == 0` when the trigger does not fire (or `== 1` when it does, with the document's `pages[]` populated by the full-page fallback per R-018.7).

**Independent Test** (per `spec.md` §US2): single-doc `--region-strategy=header-first-v1 --preprocess-profile=ppstructurev3@gpu` run on a multi-page invoice fixture; verify `preprocess_output.json.pages.length == page_count`; verify page 1 has populated `blocks[]` / `raw_ocr_lines[]` and pages 2..N have empty arrays (per Clarifications Q2 / I-018.6); verify `run_summary.region_strategy_fallback_count == 0` on a fixture that does NOT trigger fallback; on a forced-trigger fixture, verify the fallback path produces a fully-populated `pages[]` and `region_strategy_fallback_count == 1` (per R-018.7).

### Implementation for User Story 2

- [x] T016 [P] [US2] Create `src/ledgerlinc_ocr/preprocessing/region_strategies.py` with: (a) `RegionStrategy` frozen dataclass per `data-model.md` §RegionStrategy (fields `name: str`, `page_targeting: Callable[[PdfDocument, int], Optional[BBox]]`, `trigger_fired: Callable[[list[Block]], bool]`); (b) `BBox` frozen dataclass per `data-model.md` §BBox (PDF-pt coordinates: `x0_pt`, `y0_pt`, `x1_pt`, `y1_pt`); (c) `REGION_STRATEGIES` registry with four entries from R-018.4 — `full-page` (page_targeting always returns `None`; trigger_fired always returns `False`), `header-first-v1` (page_targeting returns `BBox(0, 0, width_pt, 0.30 * height_pt)` for `page_index == 0` and `None` for `page_index > 0` per R-018.5; trigger_fired implements `not "".join(b.text for b in blocks).strip()` per R-018.7 / Clarifications Q3), `cpu-default` and `stub-default` (full-page aliases — same callables as `full-page` but distinct `name`); (d) `resolve_region_strategy(name: str) -> RegionStrategy` raising `UnknownPresetError(preset_axis="region_strategy", ...)` on unknown name. **CPU-safe at module-load** — NO Paddle imports.
- [x] T017 [US2] Add a sibling helper `rasterize_page_band(pdf_path: Path, page_index: int, band_bbox_pt: BBox, dpi: int) -> Image.Image` to `src/ledgerlinc_ocr/preprocessing/rasterize.py`. The helper renders ONLY the targeted band of one page using `pypdfium2`'s page-rendering API and returns the cropped `Image` (Pillow). Used only by `header-first-v1` (R-018.5). The existing `rasterize_pdf` helper (extended in T008) is unchanged. **Coordinate-axis verification (per Analysis U3)**: `pypdfium2.PdfPage.get_size()` returns `(width_pt, height_pt)` in PDF point space (PostScript convention is bottom-left origin), but `pypdfium2`'s rendering API (`render_to`/`render`) writes to a top-left-origin bitmap. R-018.5's BBox is in top-left-origin convention (matching the rendered bitmap). Implementer MUST verify at code-write time by rendering page 1 of `inv_001_easy/source.pdf` cropped to `BBox(0, 0, width_pt, 0.30 * height_pt)` and confirming visually that the cropped image covers the page HEADER (logo + company name area), NOT the page footer. If the crop covers the footer, flip the y-axis interpretation in `page_targeting`'s BBox computation in `region_strategies.py` BEFORE landing T018.
- [x] T018 [US2] Wire region-strategy orchestration into `src/ledgerlinc_ocr/preprocessing/pipeline.py` per R-018.5 / R-018.7 / R-018.9 / R-018.10 / R-018.15. The orchestrator's per-page loop becomes: (1) ask `region_strategy.page_targeting(pdf_doc, i)` for the targeted region; (2) if `None` AND strategy is `full-page` / `cpu-default` / `stub-default`, render the whole page and call `engine.predict(image)`; (3) if `None` AND strategy is `header-first-v1` AND `i > 0`, build the empty page record per R-018.6 (page_number, derived width/height/rotation from `pdf_doc.get_page(i).get_size()` × resolved `RasterProfile.dpi`, `blocks: []`, `raw_ocr_lines: []`); (4) if `BBox` returned, call `rasterize_page_band(pdf_path, i, band_bbox_pt, raster_profile.dpi)` then `engine.predict(crop_image)`, then translate every returned bbox back to full-page pixel coordinates via the helper from T021. After page 1's `header-first-v1` predict completes, evaluate `region_strategy.trigger_fired(targeted_blocks)`; on `True`, discard the partial output entirely and re-run the document under the `full-page` orchestrator path on the SAME engine instance (per R-018.9 — preserves feature 015 FR-001), accumulate the second pass's wall-clock cost into the same per-document `phase_timings.rasterization` / `phase_timings.per_page_inference` (R-018.10), and increment a per-run accumulator that lands in `RunSummary.region_strategy_fallback_count` (R-018.8). Same-engine guarantee preserved.
- [x] T019 [US2] Add `--region-strategy ID` flag + `LEDGERLINC_REGION_STRATEGY` env-var fallback to `src/ledgerlinc_ocr/preprocessing/cli.py` and `src/ledgerlinc_ocr/pipeline/cli.py` per `contracts/cli-contract.md` §1–§2 / §5. Same parse-order, same `UnknownPresetError` → exit-16 behavior as T009. Help text per `contracts/cli-contract.md` §2.
- [x] T020 [US2] Wire the `region_strategy_fallback_count` per-run accumulator from T018's orchestrator into `src/ledgerlinc_ocr/pipeline/corpus_run.py` and `src/ledgerlinc_ocr/pipeline/runner.py` at the override site marked by T006a's inline comment. The accumulator increments by exactly 1 per fallen-back document (per R-018.8 / I-018.10 — per-document granularity, NOT per-page); the final value lands on `RunSummary.region_strategy_fallback_count` via `to_dict()`. On `region_strategy_id == "full-page"` / `cpu-default` / `stub-default` runs, the accumulator stays at 0 (no fallback path active) and the always-emit-with-default-0 contract from `contracts/run-summary-schema.md` §3 is satisfied.
- [x] T021 [P] [US2] Add a `translate_bbox(crop_relative_bbox, crop_offset_px) -> BBox` helper to `src/ledgerlinc_ocr/preprocessing/region_strategies.py` (or a sibling module per `plan.md` §Project Structure) per R-018.15. The helper performs `(x0+dx, y0+dy, x1+dx, y1+dy)` so PaddleOCR's crop-relative pixel bboxes are translated back to full-page pixel coordinates before `preprocess_output.json` write. For `header-first-v1` the offset is `(0, 0)` (header band starts at top-left); the helper is structured so a future preset cropping a non-top-left region works without further refactor. CPU-safe.

### Tests for User Story 2

- [x] T022 [P] [US2] CPU-safe unit tests in `tests/unit/preprocessing/test_region_strategies_unit.py`: assert (a) `set(REGION_STRATEGIES.keys()) == {"full-page", "header-first-v1", "cpu-default", "stub-default"}` (I-018.1); (b) `resolve_region_strategy("full-page")` returns the full-page preset; (c) `resolve_region_strategy("header-first-v99")` raises `UnknownPresetError` with `preset_axis="region_strategy"` and `valid_values` of length 4 (R-018.12); (d) construct a synthetic `pdf_doc` (or stub) with known page sizes; assert `header-first-v1.page_targeting(doc, 0)` returns `BBox(0, 0, width_pt, 0.30 * height_pt)` and `header-first-v1.page_targeting(doc, i)` returns `None` for every `i > 0` (I-018.4 / R-018.5); (e) `full-page.page_targeting(doc, i)` returns `None` for every `i` and `full-page.trigger_fired([...])` returns `False` always (I-018.4); (f) the registry is import-safe on a host without Paddle (mock `sys.modules`).
- [x] T023 [P] [US2] CPU-safe trigger-fired unit test in `tests/unit/preprocessing/test_region_strategies_trigger.py` covering Clarifications Q3 boundary cases: empty list ⇒ `True`; list with one whitespace-only `text` (e.g., `"  \t\n"`) ⇒ `True`; list with one Unicode-NBSP-only `text` ⇒ `True`; list with one block whose `text == "Acme Corp"` ⇒ `False`; list with one whitespace-only block AND one non-whitespace block ⇒ `False` (any non-whitespace text in the targeted region prevents fallback). All cases assert `header-first-v1.trigger_fired(blocks) == expected` (R-018.7 / I-018.5).
- [x] T024 [P] [US2] CPU-safe coordinate-translation unit test in `tests/unit/preprocessing/test_coordinate_translation.py`: given a synthetic crop offset `(dx, dy)` and a list of crop-relative bboxes, assert `translate_bbox(bbox, (dx, dy))` returns the hand-computed full-page bbox `(x0+dx, y0+dy, x1+dx, y1+dy)` for every entry. Cover `(0, 0)` (header-first-v1's actual offset) and a non-zero `(50, 100)` (future-preset coverage). R-018.15 / I-018.7.
- [x] T025 [P] [US2] Extend `tests/pipeline_tests/test_run_summary_schema_0_1_5.py` (created in T012) with `region_strategy_id` field-level checks: present on every run; default value is `"cpu-default"` on CPU profile and `"stub-default"` on stub adapter; on GPU runs, value matches the resolved preset name (`"full-page"` for no-flag and `--region-strategy=full-page` GPU runs; `"header-first-v1"` for `--region-strategy=header-first-v1` GPU runs). The `@pytest.mark.gpu` parametrization may be deferred per FR-025 and tracked in T038. (FR-008 / FR-011 / contracts/run-summary-schema.md §3)
- [x] T026 [P] [US2] Extend `tests/unit/preprocessing/test_unknown_preset_value.py` (created in T013) with `region_strategy` axis cases: launch the preprocess CLI subprocess with `--region-strategy=header-first-v99 --preprocess-profile=ppstructurev3@cpu`; assert exit code 16; stderr contains literal `error: unknown region_strategy:` and the four valid values; assert no `run_summary` is emitted (I-018.1 / R-018.12 / contracts/cli-contract.md §3).
- [ ] T027 [US2] ⏸ DEFERRED per FR-025 — `@gpu` GPU pages[] invariant test in `tests/pipeline_tests/test_region_first_pages_invariant.py` (`@pytest.mark.gpu`): single-doc `--region-strategy=header-first-v1 --preprocess-profile=ppstructurev3@gpu` on a multi-page invoice fixture from `tests/stage1_vendor_identity/` (e.g., `inv_002_easy` if it has multiple pages; otherwise `tasks.md`-pin a multi-page fixture from R-017.11); assert `len(preprocess_output.json.pages) == page_count`; assert `pages[0]` has populated `blocks` / `raw_ocr_lines`; assert `pages[i]` for `i > 0` has `blocks: []`, `raw_ocr_lines: []`, and valid geometry from `pypdfium2`; assert `run_summary.region_strategy_fallback_count == 0` (clean run, no trigger). I-018.6 / Clarifications Q2.
- [ ] T028 [US2] ⏸ DEFERRED per FR-025 — `@gpu` GPU fallback-path test in `tests/pipeline_tests/test_region_first_fallback.py` (`@pytest.mark.gpu`): requires a fallback-forcing fixture (a PDF where page 1's top 30% has no vendor-identity-relevant text — e.g., a cover-page invoice or one whose company-name text is below the band). **Fixture-selection procedure** (executed at the time T028 is staged, BEFORE the test is written): (1) audit the existing 20-doc corpus by running `--region-strategy=header-first-v1` on each `inv_*` document and inspecting `region_strategy_fallback_count` on the run_summary line; (2) if any existing document triggers the fallback, pin its name into THIS task description and use it; (3) if no existing document triggers the fallback, the corpus does not currently exercise this path — capture this as a separate follow-up via `docs/stage1-vendor-identity/dataset-layout.md` and `labeling-guide.md` (NOT through this feature's PR per FR-019), defer T028 in T038, and note "no fallback-forcing fixture in current corpus" in T038's audit-trail entry. With the chosen fixture: single-doc `--region-strategy=header-first-v1 --preprocess-profile=ppstructurev3@gpu`; assert `run_summary.region_strategy_fallback_count == 1`; assert ALL `pages[]` are populated (because the full-page strategy ran post-fallback per R-018.7); assert `phase_timings.rasterization` and `phase_timings.per_page_inference` reflect combined wall-clock cost (R-018.10); assert via instrumentation that `PPStructureV3.__init__` was called exactly once (single-engine reuse on fallback per R-018.9 / I-018.3 — preserves feature 015 FR-001).

**Checkpoint**: US2 fully functional and testable independently. US3 may now begin (US3 depends only on Phase 2; identifier visibility wires through the foundational `RunSummary` dataclass that is already in place).

---

## Phase 5: User Story 3 — Active rasterization / region strategy is visible in operator-facing output (Priority: P1)

**Goal**: Every `run_summary` line emitted by the new binary carries `raster_profile_id`, `region_strategy_id`, and `region_strategy_fallback_count` as additive top-level fields; two runs that differ only in DPI carry different `raster_profile_id` values; two runs that differ only in region strategy carry different `region_strategy_id` values; CPU and stub runs emit the appropriate default identifiers.

**Independent Test** (per `spec.md` §US3): GPU lane runs of all four corners of the matrix (`(legacy, full-page)`, `(reduced-v1, full-page)`, `(legacy, header-first-v1)`, `(reduced-v1, header-first-v1)`) produce four `run_summary` lines whose two identifier fields differ in the expected axes; CPU runs carry `cpu-default` for both; stub-adapter runs carry `stub-default` for both; repeating any one of the four runs produces the same identifier-pair value.

### Implementation for User Story 3

- [x] T029 [US3] Audit the run_summary emission point in `src/ledgerlinc_ocr/pipeline/timing.py` and the wiring in `corpus_run.py` / `runner.py` to confirm `RunSummary.to_dict()` emits the three new fields in the deterministic order from `contracts/run-summary-schema.md` §2 AFTER feature 017's three fields and before the closing brace; verify no per-document `phase_timings.*` field is mutated by this feature (FR-010 / I-018.8); verify `region_strategy_fallback_count` does NOT appear inside `preprocess_output.json` (FR-009 / FR-020 / contracts/run-summary-schema.md §4).

### Tests for User Story 3

- [x] T030 [P] [US3] Extend `tests/pipeline_tests/test_run_summary_schema_0_1_5.py` (created in T012, extended in T025) with `region_strategy_fallback_count` field-level checks: present on every run; default `0` on CPU profile and stub adapter; on `region_strategy_id != "header-first-v1"` runs, value is always `0`; on `header-first-v1` GPU runs without trigger, value is `0`; on `header-first-v1` GPU runs with trigger (covered by T028), value is `1` per fallen-back document (R-018.8 / I-018.10).
- [x] T031 [P] [US3] CPU-safe identifier-stability test in `tests/pipeline_tests/test_identifier_stability.py`: two consecutive CPU runs with identical inputs produce identical values for all three new top-level fields (SC-004 within-configuration stability). Add a third run with a flag combination that warn-and-proceeds on CPU (`--raster-profile=reduced-v1 --region-strategy=header-first-v1`); assert all three fields are STILL identical to the first two runs (CPU lane's identifiers reflect profile defaults regardless of flag values per I-018.2).

**Checkpoint**: US3 fully functional and testable independently. US4 may now begin.

---

## Phase 6: User Story 4 — Default CPU profile and CI without GPU stay safe (Priority: P2)

**Goal**: Setting either or both new flags on `ppstructurev3@cpu` or any stub adapter triggers the FR-014 warn-and-proceed pattern (warn + no DPI change + no region targeting + same exit status), the run completes normally with the CPU/stub-default identifiers on `run_summary`, and the default test suite passes on a host without Paddle GPU.

**Independent Test** (per `spec.md` §US4): default `ppstructurev3@cpu` profile on a host without Paddle GPU runs both with and without the new GPU-only switches set; both invocations succeed with identical exit codes; stderr carries one `--<axis> ignored:` warning line per set switch; `preprocess_output.json` is byte-identical to a no-flag CPU run; `@pytest.mark.gpu`-marked tests skip rather than fail.

### Implementation for User Story 4

- [x] T032 [US4] Wire CPU/stub warn-and-proceed for both new flags into `src/ledgerlinc_ocr/preprocessing/cli.py` and `src/ledgerlinc_ocr/pipeline/cli.py` at the cross-profile evaluation point (AFTER `resolve_*` succeeds for both axes, BEFORE the orchestrator runs — order per contracts/cli-contract.md §5). When the active profile is `ppstructurev3@cpu` (or a stub adapter) AND `--raster-profile` was set, emit a single stderr line literally containing `--raster-profile ignored: active preprocess profile is 'ppstructurev3@cpu', not 'ppstructurev3@gpu'` (substring `--raster-profile ignored:` is grep-able per contracts/cli-contract.md §3). Same for `--region-strategy`. Override the resolved `RasterProfile` / `RegionStrategy` to the active profile's identity preset (`cpu-default` or `stub-default`) AFTER warning, so downstream code sees the identity preset and the run proceeds with no DPI / region change. Exit code unchanged from a no-flag CPU run (FR-014 / SC-005).

### Tests for User Story 4

- [x] T033 [P] [US4] CPU-safe warn-and-proceed test in `tests/unit/preprocessing/test_cpu_warn_and_proceed.py` covering all eight argv permutations per contracts/cli-contract.md §3 behavior matrix: profile `cpu` × `--raster-profile=reduced-v1` set/unset × `--region-strategy=header-first-v1` set/unset (4 cases); same matrix for the stub adapter (4 cases). For each case, assert: (a) exit code matches the no-flag baseline for that profile; (b) stderr contains exactly the expected number of `… ignored:` lines (0, 1, or 2 depending on flag count); (c) `run_summary.raster_profile_id` is `cpu-default` (or `stub-default` on stub) and `region_strategy_id` is `cpu-default` (or `stub-default`); (d) `region_strategy_fallback_count == 0` always (no fallback path runs on CPU/stub). FR-014 / SC-005 / failure-handling.md CHK009–CHK015.
- [x] T034 [P] [US4] CPU-safe byte-identity test in `tests/pipeline_tests/test_legacy_byte_identity.py` (CPU variant; an optional `@gpu` variant is covered by T015's benchmark cells): a `--raster-profile=legacy --region-strategy=full-page` run on the CPU profile produces a `preprocess_output.json` byte-identical to a no-flag CPU run on the same fixture; the run_summary differs ONLY in the three new top-level fields (whose values are the CPU defaults — actually identical because both invocations are CPU and the explicit flags warn-and-proceed). FR-019 / SC-007 / non-regression.md CHK012.

**Checkpoint**: US4 fully functional and testable independently. US5 may now begin.

---

## Phase 7: User Story 5 — Output schema and downstream contracts unchanged (Priority: P2)

**Goal**: For each evaluated `(raster_profile_id, region_strategy_id)` cell of the four-corner matrix, an end-to-end pipeline run on the fixed 5-doc subset (preprocess → evidence packet → extract → route → assemble → evaluate) produces every artifact validating against its existing schema in the active contract set, and `evaluation_run_summary.{json,md}` is produced.

**Independent Test** (per `spec.md` §US5): for each of the four cells, run the full pipeline on the 5-doc subset; assert every artifact (`preprocess_output.json`, `evidence_packet.json` if generated, `edge_extraction_output.json`, `routing_decision.json`, `final_structured_payload.json`, `evaluation_document.json`, `evaluation_run_summary.{json,md}`) validates against its existing schema; assert `schema_version`, `contract_set_version`, and `pipeline_version` shape are unchanged from `main`.

### Tests for User Story 5

- [ ] T035 [US5] ⏸ DEFERRED per FR-025 (CPU-safe portions can land independently) — `@gpu` end-to-end pipeline regression test in `tests/pipeline_tests/test_end_to_end_pipeline.py` (`@pytest.mark.gpu`): for each of the four cells of the matrix on the fixed 5-doc subset (R-018.13 = R-017.11 subset), run the full pipeline as in `quickstart.md` §8; assert every emitted artifact validates against its existing schema in the active contract set (`contracts/stage1_vendor_identity/v1.2.0/`); assert empty page records (pages 2..N under `header-first-v1`) flow through evidence-packet → extract → route → assemble → evaluate without contract changes (per Clarifications Q2 + non-regression.md CHK040). SC-008 / FR-022 / FR-026.

**Checkpoint**: US5 fully functional and testable independently. US6 may now begin.

---

## Phase 8: User Story 6 — Quality-gate guard before any GPU default change (Priority: P3)

**Goal**: A candidate `(raster_profile_id, region_strategy_id)` configuration may be promoted to the new `ppstructurev3@gpu` default ONLY when both quality-gate metrics (per R-018.11 / FR-016) on the same fixed 5-doc subset are at parity with or better than the legacy default; promotion that fails the gate is rejected and the legacy default stays in place.

**Independent Test** (per `spec.md` §US6): for each non-legacy candidate cell of the four-corner matrix, compare BOTH (a) the per-corpus aggregate vendor-identity field score from `evaluation_run_summary.json` AND (b) the per-document pass count per `docs/stage1-vendor-identity/scoring.md` to the legacy `(legacy, full-page)` cell's values on the same subset; the gate passes iff both candidate values are `>=` legacy values.

### Implementation for User Story 6

- [ ] T036 [US6] ⏸ DEFERRED per FR-025 — `@gpu` Two-metric quality-gate test in `tests/pipeline_tests/test_quality_gate_two_metric.py` (`@pytest.mark.gpu`): parametrize over the three non-legacy cells (`(reduced-v1, full-page)`, `(legacy, header-first-v1)`, `(reduced-v1, header-first-v1)`); for each cell, read `aggregate.vendor_identity_field_score` from the cell's `evaluation_run_summary.json` and the per-document pass count from each `evaluation_document.json.pass_status == "pass"`; assert the gate predicate `candidate_field_score >= legacy_field_score AND candidate_pass_count >= legacy_pass_count`. The test does NOT promote a default — it records the gate result for the FR-017 evidence in research.md Appendix B. R-018.11 / FR-016 / SC-009.
- [ ] T037 [US6] ⏸ DEFERRED per FR-025 (depends on T036's outputs) — Workstation evidence capture: record per-cell numbers from T036 into `specs/018-dpi-region-first-preprocess/research.md` Appendix B. If a cell passes the gate AND the team chooses to promote it, additionally name the promoted `(raster_profile_id, region_strategy_id)` pair in Appendix B's "Promotion decision" line and edit (a) `RASTER_PROFILES` / `REGION_STRATEGIES` in `src/ledgerlinc_ocr/preprocessing/raster_profiles.py` and `src/ledgerlinc_ocr/preprocessing/region_strategies.py` IF the registry definitions need a new entry (typically not — the promoted preset already lives in the registry as opt-in), AND (b) the GPU-default-when-flag-unset logic in `src/ledgerlinc_ocr/preprocessing/cli.py` and `src/ledgerlinc_ocr/pipeline/cli.py` so a no-flag GPU run after this feature lands selects the promoted preset (per R-018.1 / contracts/cli-contract.md §1 — "default `legacy` on the GPU profile" is the line that flips). Optionally also update default-constant references in `src/ledgerlinc_ocr/preprocessing/identifiers.py` if the team chooses to rename the `LEGACY_RASTER_PROFILE` / `LEGACY_REGION_STRATEGY` constants to reflect the new default (recommended: keep the `LEGACY_*` names pointing at the historically-legacy values for traceability, and add new constants like `DEFAULT_RASTER_PROFILE` / `DEFAULT_REGION_STRATEGY` for the current default). If no cell passes, record "no promotion at landing — legacy stays GPU default; both new presets stay opt-in only" in Appendix B. The legacy `(raster_profile_id, region_strategy_id)` configuration MUST remain selectable per FR-018 either way. FR-016 / FR-017 / FR-018 / preprocessing-policy.md CHK026–CHK029.

**Checkpoint**: US6 complete. The full feature surface is now landed; the FR-025 deferral set (if any) is captured in T038.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [x] T038 Capture the FR-025 GPU-verification deferral set in BOTH this `tasks.md` (each ⏸ DEFERRED task above is the durable audit-trail entry) AND `specs/018-dpi-region-first-preprocess/quickstart.md` Appendix B. Items deferred at landing: T014 / T015 (US1 GPU), T027 / T028 (US2 GPU pages-invariant + fallback path), T035 (US5 end-to-end), T036 / T037 (US6 quality-gate evidence + promotion decision), plus the GPU parametrization of T012 / T025 / T030 if not run at landing. All deferrals follow feature 016 FR-014 / feature 017 FR-024 anti-skip discipline. Follow-up issue/PR identifier: TBD when GPU verification window opens; this task block IS the durable audit-trail entry per FR-025.
- [x] T039 [P] Cross-checklist consistency audit: walk every CHK item in the seven release-gate checklists under `specs/018-dpi-region-first-preprocess/checklists/` (`requirements.md`, `contract.md`, `determinism.md`, `failure-handling.md`, `preprocessing-policy.md`, `non-regression.md`, `fallback-path.md`) and confirm each maps to either (a) a Phase 2–8 task that satisfies it, (b) an explicit `[Gap]` deferral with a follow-up item in T038, or (c) a documented out-of-scope decision in spec.md / research.md. Tick the checkbox (`- [x]`) for every CHK item that is satisfied; leave open `- [ ]` items unchanged with a brief inline note about why. Additionally note in this audit that **FR-012, FR-013, FR-021, and FR-026 are "MUST NOT" / negative requirements** — they have no explicit task because they are satisfied by the *absence* of contradicting work in `tasks.md`. Verification: FR-012 (CPU stays default) is verified by T034 byte-identity; FR-013 (GPU stays opt-in) is verified by T011's no-flag CPU run defaulting to `cpu-default`; FR-021 (no new persisted artifact) is verified by reviewing `tasks.md` for any task that creates a new artifact under `tests/stage1_vendor_identity/` or elsewhere (none exists); FR-026 (no OCR-only fast lane) is verified by reviewing T018's orchestrator for any code path that bypasses the existing PPStructureV3 module set (none exists — region-first still calls `engine.predict(crop_image)`).
- [x] T040 Quickstart walkthrough verification — CPU portions: run quickstart §0 (one-time environment), §5 (CPU warn-and-proceed), and §6 (unknown-preset fail-fast on either axis) end-to-end and confirm each command's expected output matches the documented expectation. GPU portions (§1 / §2 / §3 / §4 / §7 fallback path / §8 end-to-end) require workstation GPU and are deferred under T038 if no GPU is available at landing.
- [x] T041 [P] Validator pass and corpus-baseline immutability check: `python -m ledgerlinc_ocr.validator validate corpus tests/stage1_vendor_identity/` returns success against contract set 1.2.0; `git diff main -- tests/stage1_vendor_identity/` returns empty (this feature has not modified any committed corpus baseline, per FR-019 / SC-007).
- [x] T042 [P] Run the existing `tests/contract_tests/` suite (the v1.2.0 contract tests must continue to pass unchanged per FR-020). Confirm the existing feature-014/015/016/017 test suites also pass unchanged after this feature's changes (FR-022 carry-forward).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories. T002–T006 can run in parallel; T006a depends on T006.
- **User Stories (Phase 3+)**: All depend on Foundational phase completion.
- **Polish (Phase 9)**: Depends on all desired user stories being complete; T038 (deferral capture) can be drafted as soon as it is known which `@gpu`-marked tasks will be deferred.

### User Story Dependencies

- **US1 (P1)**: Depends only on Phase 2. No dependencies on other user stories.
- **US2 (P1)**: Depends only on Phase 2. T016 creates `region_strategies.py` and is independent of US1's `raster_profiles.py`. T018 (orchestrator) edits `pipeline.py` independently of T010 (US1's `pipeline.py` thread for `raster_profile.dpi`); developers should sequence T010 → T018 within a single PR if both axes land together to avoid same-file merge contention. If two developers split the work, US1 should land first and US2 rebases on it.
- **US3 (P1)**: Depends only on Phase 2 (T006 created the `RunSummary` fields and T006a wired the threading scaffold). T009 / T010 (US1) and T019 / T020 (US2) feed identifier values into that scaffold; US3's audit task T029 verifies the emission contract is satisfied and does not depend on US1/US2 being complete.
- **US4 (P2)**: Depends on Phase 2 + the CLI-flag wiring done in T009 (US1) and T019 (US2) — T032's warn-and-proceed branch sits AFTER `resolve_*` succeeds in the parse path.
- **US5 (P2)**: Depends on US1 + US2 having produced GPU runtime outputs (T014, T028). US5's CPU-safe portions are minimal; T035 itself is `@gpu` and lands as part of T038's deferral set if no GPU at landing.
- **US6 (P3)**: Depends on US5's end-to-end runs (T035) producing per-cell `evaluation_run_summary.json` and `evaluation_document.json` files; T036 / T037 are `@gpu` and follow the same deferral path as T035.

### Within Each User Story

- Tests can be written (and SHOULD fail initially) before the implementation tasks they validate, but several tasks are CPU-safe assertion-only tests against the foundational structures from Phase 2 (T011, T012, T022, T023, T024, T025, T030, T031, T033) — those are ready to write as soon as Phase 2 lands.
- Models / data-shape work (preset registries) before runtime wiring (rasterizer / orchestrator / CLI threading).
- Runtime wiring before observation (run_summary identifier emission).
- Observation before promotion-gate evaluation.

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel — Phase 1 has only T001 (verification only).
- All five Foundational tasks (T002 – T006) marked [P] can run in parallel within Phase 2; T006a depends on T006.
- Once Foundational completes, US1 (T007–T015) and US2 (T016–T028) can be developed in parallel by different developers; the only same-file contention point is `pipeline.py` (T010 vs T018) which should be sequenced inside one PR, AND `cli.py` (T009 vs T019) which similarly should be sequenced.
- Within each user story, all tests marked [P] can run in parallel; CPU-safe and `@gpu`-marked tests target different test files / different fixtures so they do not contend.
- Polish phase tasks T039 / T041 / T042 can run in parallel; T038 is a single audit-trail entry; T040 is sequential.

---

## Parallel Example: User Stories 1 + 2

```bash
# After Phase 2 completes, launch US1 + US2 implementation in parallel (one developer per story):

# Developer A — US1 (DPI axis):
Task: "Create raster_profiles.py per T007"
Task: "Wire raster_profile.dpi into rasterize.py per T008"
Task: "Add --raster-profile CLI flag per T009"
Task: "Wire raster_profile into pipeline.py per T010"

# Developer B — US2 (region-strategy axis):
Task: "Create region_strategies.py per T016"
Task: "Add rasterize_page_band helper per T017"
Task: "Wire region-strategy orchestration into pipeline.py per T018"
Task: "Add --region-strategy CLI flag per T019"
Task: "Wire region_strategy_fallback_count accumulator per T020"
Task: "Add coordinate translation helper per T021"

# Note: Both developers touch pipeline.py (T010 vs T018) and cli.py (T009 vs T019).
# Sequence within each branch and resolve as a fast-follow merge to avoid edit conflicts.

# CPU-safe tests can be authored in parallel with implementation:
Task: "Raster profiles registry test per T011"
Task: "Region strategies registry test per T022"
Task: "Trigger-fired unit test per T023"
Task: "Coordinate translation unit test per T024"
Task: "Schema-version test per T012 (extended by T025 + T030)"
Task: "Unknown-preset fail-fast test per T013 (extended by T026)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only — Reduced-DPI)

1. Complete Phase 1: Setup (T001 — verify gpu marker).
2. Complete Phase 2: Foundational (T002–T006 — five parallel additions; T006a sequential after T006). CRITICAL — blocks all stories.
3. Complete Phase 3: User Story 1 (T007–T015).
4. **STOP and VALIDATE**: run T011–T013 CPU-safe tests; run T014 / T015 if workstation GPU is available, else defer per FR-025 in T038.
5. Deploy/demo if ready — DPI reduction landing alone is shippable value (operators can opt into `reduced-v1` and observe the timing improvement on `run_summary`).

### Incremental Delivery

1. Setup + Foundational → Foundation ready.
2. Add US1 → CPU-safe tests + (optionally) `@gpu` benchmark → Deploy/Demo (MVP — DPI reduction).
3. Add US2 → CPU-safe tests + (optionally) `@gpu` pages-invariant + fallback path → Deploy/Demo (region-first opt-in).
4. Add US3 → identifier-stability tests pass → Deploy/Demo (operator-facing identifier surface complete on both axes).
5. Add US4 → CPU/CI non-regression confirmed → Safe for production CI image without GPU.
6. Add US5 → end-to-end pipeline regression on each cell → Safe for downstream-stage compatibility across the four-corner matrix.
7. Add US6 → promotion-gate evidence captured → Safe to promote a new GPU default if any cell passes the gate.
8. Each story adds value without breaking previous stories.

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (one PR with T002–T006 + T006a).
2. Once Foundational is done:
   - Developer A: US1 (T007–T015) — DPI axis
   - Developer B: US2 (T016–T028) — region-strategy axis + fallback path
   - Developer C: US3 + US4 (T029–T034) — operator visibility + CPU/stub safety
3. Once US1 + US2 are done:
   - Developer A or D: US5 (T035) — end-to-end pipeline regression on the four-corner matrix
   - Developer A or D: US6 (T036–T037) — promotion-gate evidence + (optional) default-flip
4. Polish phase by whoever is available.

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks.
- [Story] label maps task to specific user story for traceability.
- `@gpu` in a description marks tasks that need workstation GPU; per FR-025 these MAY be deferred and tracked in T038 if workstation GPU is unavailable at landing.
- Each user story should be independently completable and testable.
- Verify CPU-safe tests pass before moving to `@gpu` workstation verification.
- Commit after each task or logical group (the existing `before_*` git hooks in `.specify/extensions.yml` will prompt).
- Stop at any checkpoint to validate the story independently.
- Avoid: vague tasks, same-file conflicts (the `pipeline.py` and `cli.py` tasks within US1/US2 are sequential within their story to avoid this; if split across developers, sequence at merge time), cross-story dependencies that break independence.
- This feature reuses feature 017's `UnknownPresetError` (R-018.12 — additive widening of `preset_axis: Literal[…]`) and `ExitCode.UNKNOWN_PRESET = 16` rather than introducing a new exception class or exit code; this is captured in T002 and T003 as verification-only / additive-only tasks.
