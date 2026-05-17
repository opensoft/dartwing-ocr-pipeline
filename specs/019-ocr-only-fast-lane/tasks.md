---
description: "Implementation tasks for feature 019: OCR-Only Fast Lane For Vendor Identity"
---

# Tasks: OCR-Only Fast Lane For Vendor Identity

**Input**: Design documents from `/specs/019-ocr-only-fast-lane/`
**Prerequisites**: plan.md (✅), spec.md (✅), research.md (✅), data-model.md (✅), contracts/ (✅: `cli-contract.md`, `module-invariants.md`, `run-summary-schema.md`), quickstart.md (✅)

**Tests**: Included. The spec's six user stories (`US1`–`US6`) each declare an Independent Test. `plan.md` §Project Structure enumerates concrete test files under `tests/unit/preprocessing/` and `tests/pipeline_tests/` (matching the directory convention established by features 016 / 017 / 018). GPU-marked tests follow `@pytest.mark.gpu` per FR-023 and may be deferred per FR-025.

**Organization**: Tasks are grouped by user story (US1 → US6) so each story can be implemented, tested, and delivered independently. **US1 (OCR-only candidate) is the MVP**; US3 (deterministic sufficiency + fallback) is the second core deliverable and depends on US1's `ocr_only.py` infrastructure. US2 (operator visibility) lands automatically once Phase 2's `RunSummary` scaffold + US1/US3 wiring complete.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4, US5, US6)
- **`@gpu`** in a description (not a label) marks tasks that require workstation GPU and may be deferred per FR-025
- All file paths are repo-root-relative

## Path Conventions

- Source: `src/dartwing_ocr/{preprocessing,pipeline}/...`
- Tests: `tests/{unit/preprocessing,pipeline_tests}/...` (matches the directory convention established by features 016 / 017 / 018)
- Feature artifacts: `specs/019-ocr-only-fast-lane/...`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: This feature does not introduce any new pinned dependency, top-level subpackage, or build-system change (per `plan.md` §Technical Context — "No new pinned dependency"). Setup is one verification step.

- [x] T001 Verify the `gpu` pytest marker is registered at `tests/conftest.py` (carried over from features 014–018 infrastructure). FR-023 requires this marker to exist; no new marker is added by this feature. **Verified**: `tests/conftest.py:75-78` registers `"gpu: requires Paddle GPU readiness per FR-001 …"` via `config.addinivalue_line("markers", …)`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Five independent additions that the user-story phases all build on. Tasks T002–T006 are in different files (or independent functions in `pipeline/timing.py`) and can run in parallel; T006a depends on T006 (same dataclass).

**⚠️ CRITICAL**: User-story work in Phase 3+ MUST NOT begin until T002 through T006a are complete.

- [x] T002 [P] Extend `UnknownPresetError.preset_axis: Literal[...]` from the post-018 4-value literal `Literal["module_set", "det_rec_variant", "raster_profile", "region_strategy"]` to the post-019 5-value literal `Literal["module_set", "det_rec_variant", "raster_profile", "region_strategy", "preprocess_strategy"]` in `src/dartwing_ocr/preprocessing/errors.py`. Additive widening only — no new exception class, no new caller signature, no `exit_code` change (per R-019.12 / `data-model.md` §UnknownPresetError extension). Update the docstring's "**Stability stance**" block to read "closed five-element string literal type" (was "four-element"); add a `# feature 019 (R-019.12)` inline comment block above the new literal value naming the axis added by this feature.
- [x] T003 [P] Verify `ExitCode.UNKNOWN_PRESET = 16` in `src/dartwing_ocr/pipeline/exit_codes.py` is left UNCHANGED (per R-019.12 — feature 019 reuses feature 017's exit code, does not add a new one). Update the inline comment block above the constant to note that feature 019 also routes its `preprocess_strategy` axis fail-fast through this code (mirroring the feature-018 widening that named `raster_profile` / `region_strategy`).
- [x] T004 [P] Bump `SCHEMA_VERSION` `"0.1.5"` → `"0.1.6"` in `src/dartwing_ocr/pipeline/timing.py`. Add a feature-019 inline comment block above the constant naming R-019.14 / FR-007 / FR-008 / FR-010 / `contracts/run-summary-schema.md` §1, the two additive top-level fields (`preprocess_strategy_id`, `ocr_only_fallback_count`), the strict-superset relationship with 0.1.5, and the consumers-built-against-0.1.5-still-work guarantee. Sanity-check: `from dartwing_ocr.pipeline.timing import SCHEMA_VERSION; assert SCHEMA_VERSION == "0.1.6"`.
- [x] T005 [P] Add module-level constants to `src/dartwing_ocr/preprocessing/identifiers.py` per `data-model.md` §Identifier-string constants: `LEGACY_PREPROCESS_STRATEGY = "ppstructurev3"` (R-019.4 — GPU-lane no-flag default), `OCR_ONLY_V1_PREPROCESS_STRATEGY = "ocr-only-v1"` (R-019.2 — the OCR-only preset name), `CPU_DEFAULT_PREPROCESS_STRATEGY = "cpu-default"` (R-019.3), `STUB_DEFAULT_PREPROCESS_STRATEGY = "stub-default"` (R-019.3). Module docstring updated to note feature 019 additions alongside features 017/018 existing constants. CPU-safe (no Paddle import). Sanity-check: all four identifiers import correctly.
- [x] T006 [P] Extend the `RunSummary` dataclass in `src/dartwing_ocr/pipeline/timing.py` with two additive top-level fields (per `data-model.md` §RunSummary additive fields and `contracts/run-summary-schema.md` §2): `preprocess_strategy_id: str = CPU_DEFAULT_PREPROCESS_STRATEGY`, `ocr_only_fallback_count: int = 0`. Update `RunSummary.to_dict()` to emit them in fixed order AFTER feature 018's three fields (`raster_profile_id`, `region_strategy_id`, `region_strategy_fallback_count`) and before the closing brace per `contracts/run-summary-schema.md` §2 / §4 emission order. Class docstring updated to note feature 019 additions. Sanity-check: `to_dict()` last 2 keys are `["preprocess_strategy_id", "ocr_only_fallback_count"]`; defaults are `cpu-default` / `0`. Existing 0.1.5 keys unchanged.
- [x] T006a Wire RunSummary threading scaffold for the two new fields through `src/dartwing_ocr/pipeline/corpus_run.py` (success path + warm-init failure path) and `src/dartwing_ocr/pipeline/runner.py`. At Phase 2 the new top-level fields rely on the dataclass defaults, which produce valid 0.1.6 run_summary lines on the CPU lane out-of-the-box. Inline comments at both sites name US1 (T009 / T011) as the future override site for `preprocess_strategy_id` on GPU runs, US3 (T022) as the override site for `ocr_only_fallback_count`, and US4 (T028) for stub-adapter `stub-default` discrimination. Sanity-check: the stub-adapter / CPU CLI paths emit `schema_version: "0.1.6"` and the two new fields with the correct defaults. Depends on T006 (RunSummary fields exist).

**Checkpoint**: foundational pieces in place. US1 (T007–T017) can begin; US3 (T020–T027) requires T008 (`ocr_only.py`) from US1's first task and otherwise can begin in parallel with US1's remaining tasks. US2 / US4 / US5 / US6 begin after their explicit dependencies — see §Dependencies & Execution Order below.

---

## Phase 3: User Story 1 — OCR-only preprocessing candidate on the GPU lane (Priority: P1) 🎯 MVP

**Goal**: A `ppstructurev3@gpu` run with `--preprocess-strategy=ocr-only-v1` produces a `preprocess_output.json` valid against the existing v1.2.0 schema (with `blocks[]` reassembled by deterministic Y-axis line clustering, `block_type = "text"`) and a measurably lower `phase_timings.per_page_inference` value than the `ppstructurev3` run on the same fixture, with `preprocess_strategy_id="ocr-only-v1"` on the run_summary.

**Independent Test** (per `spec.md` §US1): single-doc `--preprocess-strategy=ocr-only-v1 --preprocess-profile=ppstructurev3@gpu` run on `tests/stage1_vendor_identity/inv_001_easy/source.pdf`; `ppstructurev3` run on the same fixture; both produce schema-valid `preprocess_output.json` (with no field added, removed, renamed, or retyped per FR-003); OCR-only run's `phase_timings.per_page_inference` is strictly lower than `ppstructurev3`'s; OCR-only strategy is selected via explicit configuration; `ppstructurev3` remains a valid selection; no PPStructureV3 layout / table-recognition / formula / seal module is invoked on the OCR-only run.

### Implementation for User Story 1

- [x] T007 [P] [US1] Create `src/dartwing_ocr/preprocessing/preprocess_strategies.py` with: (a) `PreprocessStrategy` frozen dataclass per `data-model.md` §PreprocessStrategy (fields `name: str`, `kind: Literal["ppstructurev3", "ocr-only", "identity"]`, `token_threshold: int | None`, `confidence_threshold: float | None`, `confidence_aggregator: Literal["mean"] | None`); (b) `PREPROCESS_STRATEGIES` registry containing the four entries from R-019.2 — `ppstructurev3` (kind=`ppstructurev3`, all threshold fields `None`), `ocr-only-v1` (kind=`ocr-only`, token_threshold=`8` per R-019.5, confidence_threshold=`0.60` per R-019.6, confidence_aggregator=`"mean"` per R-019.6), `cpu-default` (kind=`identity`, all threshold fields `None`), `stub-default` (kind=`identity`, all threshold fields `None`); (c) `resolve_preprocess_strategy(name: str) -> PreprocessStrategy` raising `UnknownPresetError(preset_axis="preprocess_strategy", preset_value=name, valid_values=tuple(PREPROCESS_STRATEGIES.keys()))` on unknown name. **CPU-safe at module-load** — NO `import paddleocr` / `import paddle` at module level (FR-014 / I-019.10); only stdlib + `from dartwing_ocr.preprocessing.identifiers import LEGACY_PREPROCESS_STRATEGY, OCR_ONLY_V1_PREPROCESS_STRATEGY, CPU_DEFAULT_PREPROCESS_STRATEGY, STUB_DEFAULT_PREPROCESS_STRATEGY` for the keys.
- [x] T008 [P] [US1] Create `src/dartwing_ocr/preprocessing/ocr_only.py` per `plan.md` §Project Structure and `data-model.md` §OcrOnlyLine / §OcrOnlyPagePredict. Module-level state: `_OCR_ENGINE: Any = None`, `_OCR_ENGINE_DEVICE: Optional[str] = None` (mirrors `ocr.py:_ENGINE` / `_ENGINE_DEVICE`). Public API: (a) `_get_ocr_engine(device: str, text_detection_model_name: str, text_recognition_model_name: str) -> Any` constructs `paddleocr.PaddleOCR(device=device, text_detection_model_name=..., text_recognition_model_name=..., use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False)` exactly once per process; raises `RuntimeError` on subsequent different-device request (per I-019.2 single-device-per-engine guard); imports `paddleocr` LAZILY inside this function only — module-load remains CPU-safe (I-019.10); (b) `run_ocr_only_page(engine: Any, page_image: Image.Image, page_number: int) -> OcrOnlyPagePredict` runs det+rec on the page image and returns a list of `OcrOnlyLine` (bbox, text, detector_confidence) plus page geometry; (c) `cluster_lines_into_blocks(lines: list[OcrOnlyLine]) -> list[Block]` performs the R-019.8 deterministic Y-axis line clustering (sort by `cy`, compute median line height `H`, greedy cluster on `cy` distance `<= 1.5 * H`, build Block objects with `block_type = "text"` per I-019.6, reading order by cluster index); empty input returns `[]`. T020 (US3) adds `check_eligibility` to this same module; place the eligibility function below `cluster_lines_into_blocks` in the file. **CPU-safe at module-load** — NO Paddle import at module level (I-019.10).
- [x] T009 [US1] Add `--preprocess-strategy ID` flag + `DARTWING_PREPROCESS_STRATEGY` env-var fallback to `src/dartwing_ocr/preprocessing/cli.py` (single-doc) and `src/dartwing_ocr/pipeline/cli.py` (warm-corpus mode) per `contracts/cli-contract.md` §1–§2. Help text per `contracts/cli-contract.md` §1 (next to feature 018's `--raster-profile` / `--region-strategy`). Read env-var fallback at CLI parse time (CLI flag wins per R-019.1). Invoke `resolve_preprocess_strategy(value)` IMMEDIATELY after argv parse, BEFORE any Paddle / preflight import; on `UnknownPresetError`, the existing CLI catch site (already routing feature 017/018's `UnknownPresetError`) prints `error: unknown preprocess_strategy: <preset_value!r> — valid values are: <…>` to stderr and exits with `ExitCode.UNKNOWN_PRESET = 16` (R-019.12 / contracts/cli-contract.md §4).
- [x] T010 [P] [US1] Create `src/dartwing_ocr/preprocessing/preprocess_strategy_optin.py` per `plan.md` §Project Structure, mirroring `region_strategy_optin.py` exactly. Public API: `PREPROCESS_STRATEGY_ENV_VAR = "DARTWING_PREPROCESS_STRATEGY"`; `resolve_preprocess_strategy_value(cli_value: str | None, env: Mapping[str, str] | None = None) -> str | None` honors CLI > env > unset precedence with verbatim env-var literal-value handling (no `.strip()`, no case normalization), empty-string env counts as unset (R-019.1); `preprocess_strategy_warn_message(active_profile: str) -> str` returns the FR-013 stderr warn line containing the grep-able marker `--preprocess-strategy ignored:` per I-019.14; `derive_run_summary_preprocess_strategy_id(*, threaded_preprocess_strategy: str | None, preprocess_lane: str) -> str` maps the CLI's threaded value → `run_summary.preprocess_strategy_id` (GPU + value ⇒ value; GPU + None ⇒ `LEGACY_PREPROCESS_STRATEGY`; non-GPU ⇒ `CPU_DEFAULT_PREPROCESS_STRATEGY`); re-export `is_gpu_lane` from `warmup_optin` for symmetry. **CPU-safe at module-load** (I-019.10).
- [x] T011 [US1] Wire preprocess-strategy resolution into `src/dartwing_ocr/preprocessing/pipeline.py` (the orchestrator). Read the resolved `PreprocessStrategy` from the parsed CLI args / `PreflightContext`. Dispatch by `kind`: (a) `kind == "ppstructurev3"` invokes the existing PPStructureV3 path (unchanged — `engine.predict(image)` via `ocr._get_engine`); (b) `kind == "ocr-only"` invokes `ocr_only._get_ocr_engine(...)` lazily on first predict, then `ocr_only.run_ocr_only_page(engine, page_image, page_number)` for each targeted page region (uses feature 018's `region_strategy.page_targeting` exactly as the PPStructureV3 path does — region-strategy axis composes orthogonally per FR-026 / R-019.11), then `ocr_only.cluster_lines_into_blocks(lines)` to reassemble `blocks[]`; (c) `kind == "identity"` is treated as a no-op (CPU/stub default; warn-and-proceed already nulled the strategy upstream — see T028). Thread `preprocess_strategy.name` into the `RunSummary.preprocess_strategy_id` override site marked by T006a's inline comment in `corpus_run.py` and `runner.py` via `derive_run_summary_preprocess_strategy_id(...)` from T010. Same-engine guarantees preserved per I-019.2 (each engine constructed at most once per process *when invoked*). T021 (US3) adds the eligibility check + fallback orchestration to this same orchestrator AFTER the OCR-only predict completes for a document.

### Tests for User Story 1

- [x] T012 [P] [US1] CPU-safe unit tests in `tests/unit/preprocessing/test_preprocess_strategies_unit.py` (per `plan.md` §Project Structure): assert (a) `set(PREPROCESS_STRATEGIES.keys()) == {"ppstructurev3", "ocr-only-v1", "cpu-default", "stub-default"}` (I-019.1); (b) `PREPROCESS_STRATEGIES["ppstructurev3"].kind == "ppstructurev3"`; `PREPROCESS_STRATEGIES["ocr-only-v1"].kind == "ocr-only"` with `token_threshold == 8` (R-019.5) and `confidence_threshold == 0.60` (R-019.6) and `confidence_aggregator == "mean"` (R-019.6); `PREPROCESS_STRATEGIES["cpu-default"].kind == "identity"` and `PREPROCESS_STRATEGIES["stub-default"].kind == "identity"`; (c) `resolve_preprocess_strategy("ocr-only-v1")` returns the OCR-only preset; (d) `resolve_preprocess_strategy("ocr-only-v99")` raises `UnknownPresetError` with `preset_axis="preprocess_strategy"` and `valid_values` containing all four valid names (I-019.1 / R-019.12); (e) the registry is import-safe on a host without Paddle (mock `sys.modules["paddleocr"] = None`; assert the module still imports — I-019.10).
- [x] T013 [P] [US1] CPU-safe optin-module test in `tests/unit/preprocessing/test_preprocess_strategy_optin_unit.py`: assert (a) `PREPROCESS_STRATEGY_ENV_VAR == "DARTWING_PREPROCESS_STRATEGY"`; (b) `resolve_preprocess_strategy_value("ocr-only-v1", env={})` returns `"ocr-only-v1"` (CLI wins, no env set); (c) `resolve_preprocess_strategy_value(None, env={"DARTWING_PREPROCESS_STRATEGY": "ocr-only-v1"})` returns `"ocr-only-v1"` (env fallback); (d) `resolve_preprocess_strategy_value("ppstructurev3", env={"DARTWING_PREPROCESS_STRATEGY": "ocr-only-v1"})` returns `"ppstructurev3"` (CLI wins per R-019.1); (e) `resolve_preprocess_strategy_value(None, env={"DARTWING_PREPROCESS_STRATEGY": ""})` returns `None` (empty-string env = unset, matches feature 016/017/018 pattern); (f) `preprocess_strategy_warn_message("ppstructurev3@cpu")` contains the literal substring `--preprocess-strategy ignored:` (I-019.14); (g) `derive_run_summary_preprocess_strategy_id(threaded_preprocess_strategy="ocr-only-v1", preprocess_lane="gpu")` returns `"ocr-only-v1"`; (h) same call with `threaded_preprocess_strategy=None` returns `"ppstructurev3"` (R-019.4); (i) same call with `preprocess_lane="cpu"` returns `"cpu-default"` regardless of threaded value (R-019.3). **CPU-safe** — no Paddle import.
- [x] T014 [P] [US1] CPU-safe block-clustering unit tests in `tests/unit/preprocessing/test_ocr_only_block_clustering.py`: assert (a) `cluster_lines_into_blocks([])` returns `[]` (empty input → no blocks); (b) `cluster_lines_into_blocks([single_line])` returns one block whose bbox equals the line's bbox and text equals the line's text (single-line case); (c) two lines with vertical centers within `1.5 * H` of each other ⇒ one block containing both lines, with bbox = per-axis min/max envelope, text = `"line1\nline2"`; (d) two lines with vertical centers MORE than `1.5 * H` apart ⇒ two blocks, one per line, in `cy`-ascending order; (e) every block returned has `block_type == "text"` (I-019.6 — OCR-only never emits other block_type values); (f) deterministic re-run: calling `cluster_lines_into_blocks(lines)` twice with the same input produces identical Block objects (I-019.8). Cover at least the four bullet boundary cases plus the determinism check.
- [x] T015 [P] [US1] CPU-safe schema-version test in `tests/pipeline_tests/test_run_summary_schema_0_1_6.py` (initial slice — assert `preprocess_strategy_id` only; T019 / T024 extend this same file with feature-019 axis checks): `schema_version == "0.1.6"` on every emitted `run_summary`; `preprocess_strategy_id` is present on every run; default value is `"cpu-default"` on the CPU profile and `"stub-default"` on the stub adapter; on GPU runs (parametrized under `@pytest.mark.gpu` — covers the spot-check formerly tracked as T017), the value matches the resolved preset name (`"ppstructurev3"` for no-flag and `--preprocess-strategy=ppstructurev3` GPU runs; `"ocr-only-v1"` for `--preprocess-strategy=ocr-only-v1` GPU runs). The `@pytest.mark.gpu` parametrization may be deferred per FR-025 and tracked in T034.
- [x] T016 [P] [US1] CPU-safe unknown-preset fail-fast test in `tests/unit/preprocessing/test_unknown_preset_value.py` (extends feature 017/018's coverage to the new feature-019 axis — adds `preprocess_strategy` cases here): launch the preprocess CLI subprocess with `--preprocess-strategy=ocr-only-v99 --preprocess-profile=ppstructurev3@cpu`; assert exit code 16; stderr contains literal `error: unknown preprocess_strategy:` and the four valid values; assert no `run_summary` is emitted on stdout (search for `"kind":"run_summary"` and confirm absent — I-019.1 / R-019.12).
- [ ] T017 [US1] (tracked as [#27](https://github.com/opensoft/dartwing-ocr-pipeline/issues/27)) ⏸ DEFERRED per FR-025 — `@gpu` GPU per-page-inference comparison test in `tests/pipeline_tests/test_ocr_only_per_page_inference.py` (`@pytest.mark.gpu`): single-doc `--preprocess-strategy=ppstructurev3 --preprocess-profile=ppstructurev3@gpu` and `--preprocess-strategy=ocr-only-v1 --preprocess-profile=ppstructurev3@gpu` on `tests/stage1_vendor_identity/inv_001_easy/source.pdf` (a vendor-identity-rich fixture chosen so no fallback fires — verify `ocr_only_fallback_count == 0`); assert OCR-only's `phase_timings.per_page_inference` is strictly lower than `ppstructurev3`'s on the same fixture (SC-001 / SC-003); both `preprocess_output.json` files validate against `contracts/stage1_vendor_identity/v1.2.0/preprocess_output.schema.json`; assert via instrumentation that `_ENGINE` (PPStructureV3) is `None` after the OCR-only run (`ocr_only.v1` constructs only `_OCR_ENGINE` per I-019.2). Defer per FR-025 if no GPU at landing; capture deferral in T034.

**Checkpoint**: US1 fully functional and testable independently — this is the MVP for OCR-only on the GPU lane. US3 (T020–T027) may now begin (US3 depends on US1's `ocr_only.py` from T008).

---

## Phase 4: User Story 2 — Active preprocessing strategy is visible in operator-facing output (Priority: P1)

**Goal**: Every `run_summary` line emitted by the new binary carries `preprocess_strategy_id` as an additive top-level string field alongside (not replacing) feature 017's three fields and feature 018's three fields; two runs that differ on the preprocessing-strategy axis carry different `preprocess_strategy_id` values; CPU and stub runs emit `cpu-default` / `stub-default` respectively.

**Independent Test** (per `spec.md` §US2): GPU lane runs of `--preprocess-strategy=ppstructurev3` and `--preprocess-strategy=ocr-only-v1` on the same fixture produce two `run_summary` lines whose `preprocess_strategy_id` values differ; CPU runs carry `cpu-default`; stub-adapter runs carry `stub-default`; repeating any one run produces the same `preprocess_strategy_id` value.

### Implementation for User Story 2

- [x] T018 [US2] Audit the run_summary emission point in `src/dartwing_ocr/pipeline/timing.py` and the wiring in `corpus_run.py` / `runner.py` to confirm `RunSummary.to_dict()` emits the two new fields in the deterministic order from `contracts/run-summary-schema.md` §4 AFTER feature 018's three fields and before the closing brace; verify no per-document `phase_timings.*` field is mutated by this feature (FR-009 / I-019.11); verify `ocr_only_fallback_count` does NOT appear inside `preprocess_output.json` (FR-009 / FR-020 / contracts/run-summary-schema.md §3 / I-019.13).

### Tests for User Story 2

- [x] T019 [P] [US2] Extend `tests/pipeline_tests/test_run_summary_schema_0_1_6.py` (created in T015) with `preprocess_strategy_id` cross-configuration tests: assert two CPU-safe stub-adapter runs with different `--preprocess-strategy` flag values still produce `preprocess_strategy_id == "stub-default"` (because warn-and-proceed nulls the strategy on stub per FR-013); assert one no-flag GPU run + one `--preprocess-strategy=ocr-only-v1` GPU run produce distinct values (`"ppstructurev3"` vs `"ocr-only-v1"`) per SC-004 (the GPU portion is parametrized under `@pytest.mark.gpu` and may be deferred per FR-025 / T034).

**Checkpoint**: US2 fully functional and testable independently. US3 may now begin in parallel.

---

## Phase 5: User Story 3 — Deterministic OCR-only sufficiency and fallback rule (Priority: P1)

**Goal**: When an OCR-only run cannot produce enough evidence for stage 1 vendor identity on a given document (per the FR-005 combined two-threshold check), the disposition is deterministic and decided in code — the OCR-only path falls back to `ppstructurev3` on that document, the resulting `preprocess_output.json` is the `ppstructurev3` output, and `ocr_only_fallback_count` on `run_summary` is incremented by 1.

**Independent Test** (per `spec.md` §US3): construct two probe inputs on the same subset — one where OCR-only produces clearly sufficient vendor-identity evidence and one where it does not. Run `--preprocess-strategy=ocr-only-v1` on both. Confirm: schema-valid `preprocess_output.json` on each; the disposition (accept OCR-only output / fall back to `ppstructurev3` on that document) is observable from `run_summary` via `preprocess_strategy_id` plus `ocr_only_fallback_count`; re-running produces the same disposition; no extraction / classification / vendor-identity model output participates; `ocr_only_fallback_count` follows the always-emit pattern from feature 018 FR-009.

### Implementation for User Story 3

- [x] T020 [US3] Implement `check_eligibility(prediction: OcrOnlyPagePredict | list[OcrOnlyLine], *, token_threshold: int, confidence_threshold: float, confidence_aggregator: str) -> EligibilityVerdict` in `src/dartwing_ocr/preprocessing/ocr_only.py` per `data-model.md` §OcrOnlyEligibilityRule and I-019.3 / R-019.5 / R-019.6 / R-019.7. Algorithm: (a) if input is empty (`len(lines) == 0`) ⇒ return `INSUFFICIENT` unconditionally (R-019.7 zero-detection short-circuit, evaluated BEFORE any arithmetic); (b) compute `token_count = sum(len(line.text.split()) for line in lines)` (R-019.9 Unicode-whitespace splitting via Python's `str.split()`); (c) compute `mean_confidence = sum(line.detector_confidence for line in lines) / len(lines)` (R-019.6 arithmetic mean — I-019.9 forbids weighted-mean / median / max/min); (d) return `SUFFICIENT` iff `token_count >= token_threshold AND mean_confidence >= confidence_threshold` (I-019.3 AND-semantics is non-negotiable); else `INSUFFICIENT`. `EligibilityVerdict` is an `enum.Enum` (or `Literal["SUFFICIENT", "INSUFFICIENT"]`) — pick the existing convention used by feature 018's `BBox` and friends. CPU-safe.
- [x] T021 [US3] Wire the FR-005 eligibility check + fallback orchestration into `src/dartwing_ocr/preprocessing/pipeline.py` per R-019.10 / R-019.11 / R-019.15. After T011's OCR-only predict completes for ALL pages of a document AND `cluster_lines_into_blocks` produces the `blocks[]`, aggregate all detected lines across the targeted pages into one `list[OcrOnlyLine]` and call `check_eligibility(aggregated_lines, token_threshold=preprocess_strategy.token_threshold, confidence_threshold=preprocess_strategy.confidence_threshold, confidence_aggregator=preprocess_strategy.confidence_aggregator)`. On `SUFFICIENT` ⇒ emit the OCR-only `preprocess_output.json` and continue. On `INSUFFICIENT` ⇒ (i) discard the partial OCR-only output for that document entirely; (ii) ensure PPStructureV3 is constructed (`ocr._get_engine(...)` on first fallback in the run — this is the moment `_ENGINE` may transition from `None` to constructed mid-run per R-019.10 / I-019.2); (iii) re-run the fallen-back document under the `ppstructurev3` strategy on the SAME engine instance and on the SAME active `region_strategy_id` (R-019.11 preserves region-strategy axis orthogonality — if `header-first-v1` is active, the `ppstructurev3` fallback also runs on the header band; feature 018's region-strategy-side fallback can still fire independently); (iv) accumulate the second pass's wall-clock cost into the same per-document `phase_timings.rasterization` and `phase_timings.per_page_inference` surfaces per I-019.11 / R-019.15 (combined-cost rule — never folded back into `phase_timings.warmup`); (v) increment a per-run accumulator that lands in `RunSummary.ocr_only_fallback_count` by exactly 1 for THIS document (I-019.4 per-document granularity — not per-page, not per threshold trip).
- [x] T022 [US3] Wire the `ocr_only_fallback_count` per-run accumulator from T021's orchestrator into `src/dartwing_ocr/pipeline/corpus_run.py` and `src/dartwing_ocr/pipeline/runner.py` at the override site marked by T006a's inline comment. The accumulator increments by exactly 1 per fallen-back document (per I-019.4 / R-019.10 — per-document granularity, NOT per-page, NOT per threshold trip); the final value lands on `RunSummary.ocr_only_fallback_count` via `to_dict()`. On `preprocess_strategy_id == "ppstructurev3"` / `"cpu-default"` / `"stub-default"` runs, the accumulator stays at `0` (no OCR-only attempts) and the always-emit-with-default-0 contract from `contracts/run-summary-schema.md` §3 is satisfied.

### Tests for User Story 3

- [x] T023 [P] [US3] CPU-safe eligibility unit tests in `tests/unit/preprocessing/test_ocr_only_eligibility.py` covering R-019.5 / R-019.6 / R-019.7 and I-019.3's AND-semantics: (a) empty `lines` list (zero detections) ⇒ `INSUFFICIENT` (R-019.7); (b) one line with text `"Acme Corp"` (2 tokens, conf=0.9) and `token_threshold=8`, `confidence_threshold=0.60` ⇒ `INSUFFICIENT` (token count below threshold; AND-semantics ⇒ insufficient); (c) eight short lines totaling 10 tokens with mean confidence 0.5 ⇒ `INSUFFICIENT` (mean below threshold; AND-semantics); (d) eight short lines totaling 10 tokens with mean confidence 0.8 ⇒ `SUFFICIENT` (both above threshold); (e) edge: exactly `token_count == 8` and `mean_confidence == 0.60` ⇒ `SUFFICIENT` (inclusive `>=`); (f) edge: `token_count == 7` and `mean_confidence == 0.95` ⇒ `INSUFFICIENT` (token side trips); (g) Unicode-whitespace tokenization: a line with text `"foo bar"` (NBSP) splits to 2 tokens per R-019.9 (Python's `str.split()` honors Unicode whitespace); (h) determinism: two runs of `check_eligibility` on the same input return the same verdict (I-019.3 re-derivability).
- [x] T024 [P] [US3] Extend `tests/pipeline_tests/test_run_summary_schema_0_1_6.py` (created in T015, extended in T019) with `ocr_only_fallback_count` field-level checks: present on every run; default `0` on CPU profile and stub adapter; on `preprocess_strategy_id != "ocr-only-v1"` runs, value is always `0`; on `--preprocess-strategy=ocr-only-v1` GPU runs without trigger (covered by T026), value is `0`; on `--preprocess-strategy=ocr-only-v1` GPU runs WITH trigger (covered by T026), value matches the number of fallen-back documents per I-019.4. (FR-007 / FR-010 / contracts/run-summary-schema.md §3)
- [x] T025 [P] [US3] CPU-safe identifier-stability test in `tests/pipeline_tests/test_identifier_stability.py` (or extend feature 018's file by the same name if present): two consecutive CPU stub-adapter runs with identical inputs produce identical values for `preprocess_strategy_id` AND `ocr_only_fallback_count` (SC-004 within-configuration stability). Add a third run with a flag combination that warn-and-proceeds on CPU (`--preprocess-strategy=ocr-only-v1`); assert both new fields are STILL identical to the first two runs (`"cpu-default"` / `0`) — CPU lane's identifiers reflect profile defaults regardless of flag values per I-019.10.
- [ ] T026 [US3] (tracked as [#28](https://github.com/opensoft/dartwing-ocr-pipeline/issues/28)) ⏸ DEFERRED per FR-025 — `@gpu` GPU fallback-path test in `tests/pipeline_tests/test_ocr_only_fallback.py` (`@pytest.mark.gpu`): requires a fallback-forcing fixture (a PDF where OCR-only's output on the targeted region trips the combined two-threshold check — either too-few tokens, or too-low mean confidence, or both). **Fixture-selection procedure** (executed at the time T026 is staged, BEFORE the test is written): (1) audit the existing 20-doc corpus by running `--preprocess-strategy=ocr-only-v1 --preprocess-profile=ppstructurev3@gpu` on each `inv_*` document and inspecting `ocr_only_fallback_count` on the run_summary line and the per-doc token-count / mean-confidence; (2) if any existing document triggers the fallback, pin its name into THIS task description and use it; (3) if no existing document triggers the fallback at the chosen thresholds (token_threshold=8, confidence_threshold=0.60), consider adjusting thresholds in T007 (defer T026 in T034) OR capture as a follow-up via `docs/stage1-vendor-identity/dataset-layout.md` for a fallback-forcing fixture to be added (NOT through this feature's PR per FR-019). With the chosen fixture: single-doc `--preprocess-strategy=ocr-only-v1 --preprocess-profile=ppstructurev3@gpu`; assert `run_summary.ocr_only_fallback_count == 1`; assert the emitted `preprocess_output.json` is the `ppstructurev3` output (layout-derived blocks, possibly multi-type `block_type` values) and validates against the existing schema; assert `phase_timings.rasterization` and `phase_timings.per_page_inference` reflect combined wall-clock cost (R-019.15); assert via instrumentation that `_OCR_ENGINE` AND `_ENGINE` are BOTH constructed (each exactly once per I-019.2) after the run. R-019.10 / I-019.4 / FR-005.
- [ ] T027 [US3] (tracked as [#29](https://github.com/opensoft/dartwing-ocr-pipeline/issues/29)) ⏸ DEFERRED per FR-025 — `@gpu` Orthogonality test in `tests/pipeline_tests/test_ocr_only_with_header_first.py` (`@pytest.mark.gpu`): single-doc `--preprocess-strategy=ocr-only-v1 --region-strategy=header-first-v1 --preprocess-profile=ppstructurev3@gpu` on a multi-page invoice fixture; assert OCR-only rasterizes ONLY the page-1 header band (via instrumentation on `rasterize_page_band`), runs PaddleOCR det+rec on that crop, emits a schema-valid `preprocess_output.json` with header-band blocks on page 1 and empty records on pages 2..N per feature 018 Clarifications Q2; assert `preprocess_strategy_id == "ocr-only-v1"` AND `region_strategy_id == "header-first-v1"` on `run_summary` (the two axes compose orthogonally per FR-026 / R-019.11); assert that on a fixture chosen to trip BOTH axes' triggers, both `ocr_only_fallback_count` AND `region_strategy_fallback_count` are `1` (or whichever combination the chosen fixture produces) — independent counters per R-019.11. Defer per FR-025 if no GPU at landing.

**Checkpoint**: US3 fully functional and testable independently. US4 may now begin.

---

## Phase 6: User Story 4 — Default CPU profile and CI without GPU stay safe (Priority: P2)

**Goal**: Setting `--preprocess-strategy=ocr-only-v1` on `ppstructurev3@cpu` or any stub adapter triggers the FR-013 warn-and-proceed pattern (warn + no preprocessing-strategy change + same exit status), the run completes normally with `cpu-default` / `stub-default` identifiers on `run_summary`, and the default test suite passes on a host without Paddle GPU.

**Independent Test** (per `spec.md` §US4): default `ppstructurev3@cpu` profile on a host without Paddle GPU runs both with and without `--preprocess-strategy=ocr-only-v1` set; both invocations succeed with identical exit codes; stderr carries one `--preprocess-strategy ignored:` warning line when set; `preprocess_output.json` is byte-identical to a no-flag CPU run; `@pytest.mark.gpu`-marked tests skip rather than fail.

### Implementation for User Story 4

- [x] T028 [US4] Wire CPU/stub warn-and-proceed for `--preprocess-strategy` into `src/dartwing_ocr/preprocessing/cli.py` and `src/dartwing_ocr/pipeline/cli.py` at the cross-profile evaluation point (AFTER `resolve_preprocess_strategy` succeeds, BEFORE the orchestrator runs — order per `contracts/cli-contract.md` §3). When the active profile is `ppstructurev3@cpu` (or a stub adapter) AND `--preprocess-strategy` was set, emit a single stderr line literally containing `--preprocess-strategy ignored: active preprocess profile is 'ppstructurev3@cpu', not 'ppstructurev3@gpu'` (substring `--preprocess-strategy ignored:` is grep-able per I-019.14 / contracts/cli-contract.md §3). Override the resolved `PreprocessStrategy` to the active profile's identity preset (`cpu-default` or `stub-default`) AFTER warning, so downstream code sees the identity preset and the run proceeds with no preprocessing-strategy change. Exit code unchanged from a no-flag CPU run (FR-013 / SC-005). The CPU/stub paths MUST NOT import `ocr_only.py` (CPU-import discipline per I-019.10 / FR-014); the identity-kind dispatch in T011 ensures the orchestrator never reaches `ocr_only.run_ocr_only_page` on a CPU/stub run.

### Tests for User Story 4

- [x] T029 [P] [US4] CPU-safe warn-and-proceed test in `tests/unit/preprocessing/test_cpu_warn_and_proceed.py` (extends feature 017/018's coverage): cover the four argv permutations per `contracts/cli-contract.md` §5 behavior matrix on the CPU profile and the stub adapter: `--preprocess-strategy` set vs. unset × `cpu` vs. `stub` profile (4 cases). For each case, assert: (a) exit code matches the no-flag baseline for that profile; (b) stderr contains exactly one `--preprocess-strategy ignored:` line iff the flag is set (else zero); (c) `run_summary.preprocess_strategy_id` is `cpu-default` (or `stub-default` on stub); (d) `ocr_only_fallback_count == 0` always (no fallback path runs on CPU/stub per I-019.10). Also exercise the combined case `--preprocess-strategy=ocr-only-v1 --raster-profile=reduced-v1 --region-strategy=header-first-v1` on the CPU profile and assert all THREE flags emit separate `… ignored:` lines independently per `contracts/cli-contract.md` §3. FR-013 / SC-005 / failure-handling.md CHK010–CHK015.
- [x] T030 [P] [US4] CPU-safe byte-identity test in `tests/pipeline_tests/test_legacy_byte_identity.py` (CPU variant; an optional `@gpu` variant is covered by T017's benchmark cells): a `--preprocess-strategy=ppstructurev3` run on the CPU profile produces a `preprocess_output.json` byte-identical to a no-flag CPU run on the same fixture; the run_summary differs ONLY in the two new top-level fields (whose values are the CPU defaults — actually identical because both invocations are CPU and the explicit flag warn-and-proceeds). FR-019 / SC-007 / non-regression.md CHK014.

**Checkpoint**: US4 fully functional and testable independently. US5 may now begin.

---

## Phase 7: User Story 5 — Output schema and downstream contracts unchanged (Priority: P2)

**Goal**: For each evaluated `preprocess_strategy_id` cell (`ppstructurev3` baseline + `ocr-only-v1` candidate), an end-to-end pipeline run on the fixed 5-doc subset (preprocess → evidence packet → extract → route → assemble → evaluate) produces every artifact validating against its existing schema in the active contract set, and `evaluation_run_summary.{json,md}` is produced.

**Independent Test** (per `spec.md` §US5): for each of the two cells, run the full pipeline on the 5-doc subset; assert every artifact (`preprocess_output.json`, `evidence_packet.json` if generated, `edge_extraction_output.json`, `routing_decision.json`, `final_structured_payload.json`, `evaluation_document.json`, `evaluation_run_summary.{json,md}`) validates against its existing schema; assert `schema_version`, `contract_set_version`, and `pipeline_version` shape are unchanged from `main`.

### Tests for User Story 5

- [ ] T031 [US5] (tracked as [#30](https://github.com/opensoft/dartwing-ocr-pipeline/issues/30)) ⏸ DEFERRED per FR-025 (CPU-safe portions can land independently) — `@gpu` end-to-end pipeline regression test in `tests/pipeline_tests/test_end_to_end_pipeline_ocr_only.py` (`@pytest.mark.gpu`): for each of the two cells (`ppstructurev3` baseline, `ocr-only-v1` candidate) on the fixed 5-doc subset (R-019.13 = R-018.13 = R-017.11 subset), run the full pipeline as in `quickstart.md` §1 / §2; assert every emitted artifact validates against its existing schema in the active contract set (`contracts/stage1_vendor_identity/v1.2.0/`); assert that OCR-only `preprocess_output.json` outputs (whose `blocks[]` are line-clustering-derived per R-019.8 with `block_type = "text"` per I-019.6) flow through evidence-packet → extract → route → assemble → evaluate without contract changes; assert that fallen-back documents (when any) flow through the same downstream pipeline correctly. SC-008 / FR-022 / FR-026.

**Checkpoint**: US5 fully functional and testable independently. US6 may now begin.

---

## Phase 8: User Story 6 — Quality-gate guard before any GPU default change (Priority: P3)

**Goal**: A `preprocess_strategy_id = ocr-only-v1` candidate may be promoted to the new `ppstructurev3@gpu` default ONLY when both quality-gate metrics (per FR-016) on the same fixed 5-doc subset are at parity with or better than the `ppstructurev3` baseline; promotion that fails the gate is rejected and the legacy `ppstructurev3` default stays in place.

**Independent Test** (per `spec.md` §US6): compare BOTH (a) the per-corpus aggregate vendor-identity field score from `evaluation_run_summary.json` AND (b) the per-document pass count per `docs/stage1-vendor-identity/scoring.md` between the `ocr-only-v1` cell and the `ppstructurev3` baseline cell on the same subset; the gate passes iff both candidate values are `>=` baseline values.

### Implementation for User Story 6

- [ ] T032 [US6] (tracked as [#31](https://github.com/opensoft/dartwing-ocr-pipeline/issues/31)) ⏸ DEFERRED per FR-025 — `@gpu` Two-metric quality-gate test in `tests/pipeline_tests/test_quality_gate_two_metric_ocr.py` (`@pytest.mark.gpu`): for the `ocr-only-v1` candidate cell, read `aggregate.vendor_identity_field_score` from the cell's `evaluation_run_summary.json` and the per-document pass count from each `evaluation_document.json.pass_status == "pass"`; assert the gate predicate `candidate_field_score >= baseline_field_score AND candidate_pass_count >= baseline_pass_count` where the baseline is the `ppstructurev3` cell on the same subset. The test does NOT promote a default — it records the gate result for the FR-017 evidence in research.md Appendix B. FR-016 / SC-009.
- [ ] T033 [US6] (tracked as [#32](https://github.com/opensoft/dartwing-ocr-pipeline/issues/32)) ⏸ DEFERRED per FR-025 (depends on T032's outputs) — Workstation evidence capture: record the candidate-vs-baseline numbers from T032 into `specs/019-ocr-only-fast-lane/research.md` Appendix B. If the `ocr-only-v1` cell passes the gate AND the team chooses to promote it, additionally name the promoted `preprocess_strategy_id` value in Appendix B's "Promotion decision" line and edit (a) the GPU-default-when-flag-unset logic in `src/dartwing_ocr/preprocessing/preprocess_strategy_optin.py` (`derive_run_summary_preprocess_strategy_id`'s "GPU + None ⇒ LEGACY_PREPROCESS_STRATEGY" branch) so a no-flag GPU run after this feature lands selects `ocr-only-v1` instead of `ppstructurev3`, AND (b) update `LEGACY_PREPROCESS_STRATEGY` references — recommended: keep `LEGACY_PREPROCESS_STRATEGY = "ppstructurev3"` pointing at the historically-legacy value for traceability, and add a new constant `DEFAULT_PREPROCESS_STRATEGY` for the current default. If no promotion, record "no promotion at landing — `ppstructurev3` stays GPU default; `ocr-only-v1` stays opt-in only" in Appendix B. The legacy `preprocess_strategy_id = ppstructurev3` configuration MUST remain selectable per FR-018 either way. FR-016 / FR-017 / FR-018 / preprocessing-policy.md CHK027.

**Checkpoint**: US6 complete. The full feature surface is now landed; the FR-025 deferral set (if any) is captured in T034.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [x] T034 Capture the FR-025 GPU-verification deferral set in BOTH this `tasks.md` (each ⏸ DEFERRED task above is the durable audit-trail entry) AND `specs/019-ocr-only-fast-lane/quickstart.md` Appendix B. Items deferred at landing: T017 (US1 GPU per-page-inference comparison), T026 (US3 GPU fallback path), T027 (US3 GPU orthogonality with feature 018 region-strategy), T031 (US5 end-to-end), T032 / T033 (US6 quality-gate evidence + promotion decision), plus the GPU parametrization of T015 / T019 / T024 if not run at landing. All deferrals follow feature 016 FR-014 / feature 017 FR-024 / feature 018 FR-025 anti-skip discipline. **Follow-up feature: `020-feature-019-gpu-verification`** (or roll into a combined `020-features-018-019-gpu-verification` if feature 018's deferrals are still open) — picks up T017 / T026 / T027 / T031 / T032 / T033 plus the deferred GPU parametrizations once feature 019 lands on `main`. This task block remains the durable audit-trail entry per FR-025; future features reference it by ID rather than duplicating it.
- [x] T035 Q3 warmup-binding wiring: update `src/dartwing_ocr/preprocessing/warmup.py` (and its callers in `preflight.py` / `preflight_cli.py`) per I-019.16. When the resolved `preprocess_strategy_id == "ocr-only-v1"`, the warmup pass MUST invoke `ocr_only._get_ocr_engine(device, ...)` (PaddleOCR) instead of the existing `ocr._get_engine(device, ...)` (PPStructureV3) branch. When `preprocess_strategy_id ∈ {"ppstructurev3", "cpu-default", "stub-default"}`, warmup behavior is unchanged from feature 016. The warn-and-proceed path in T028 ensures the CPU/stub case never reaches `ocr_only` code (FR-014 / I-019.10). Forbidden: warming both engines on `ocr-only-v1` (I-019.16); skipping warmup entirely (I-019.16). On `ocr-only-v1` warmup failure, `WarmupError` is raised with the same shape as feature 016 (exit code 15, `cause_class` taxonomy unchanged) — no new exception class. CPU-safe path: the `warmup.py` dispatch reads `preprocess_strategy_id` from the preflight context and selects which `_get_*_engine` call to make at warmup time; the actual GPU work is GPU-only and deferred to T036.
- [ ] T036 [US3] (tracked as [#33](https://github.com/opensoft/dartwing-ocr-pipeline/issues/33)) ⏸ DEFERRED per FR-025 — `@gpu` GPU warmup-binding test in `tests/pipeline_tests/test_warmup_engine_binding.py` (`@pytest.mark.gpu`): single-doc `--gpu-warmup --preprocess-strategy=ocr-only-v1 --preprocess-profile=ppstructurev3@gpu` on `tests/stage1_vendor_identity/inv_001_easy/source.pdf`; assert via instrumentation that `_OCR_ENGINE` is constructed during warmup AND `_ENGINE` (PPStructureV3) remains `None` after warmup; assert `phase_timings.warmup` is non-zero and measures PaddleOCR's warmup cost only (not the sum across engines). Symmetric run with `--preprocess-strategy=ppstructurev3 --gpu-warmup`: assert `_ENGINE` is constructed and `_OCR_ENGINE` remains `None`. Third run with a fallback-forcing fixture (same as T026): assert post-run `_OCR_ENGINE != None` AND `_ENGINE != None` (both constructed mid-run for the fallback document) AND the fallback document's `phase_timings.per_page_inference` includes the PPStructureV3 cold-start cost per R-019.15. R-019.16 / I-019.16. Defer per FR-025 if no GPU at landing.
- [ ] T037 [P] (tracked as [#34](https://github.com/opensoft/dartwing-ocr-pipeline/issues/34)) Cross-checklist consistency audit: walk every CHK item in the eight release-gate checklists under `specs/019-ocr-only-fast-lane/checklists/` (`requirements.md`, `contract.md`, `determinism.md`, `failure-handling.md`, `fallback-path.md`, `non-regression.md`, `preprocessing-policy.md`, `engine-coordination.md`) and confirm each maps to either (a) a Phase 2–8 task that satisfies it, (b) an explicit `[Gap]` deferral with a follow-up item in T034, or (c) a documented out-of-scope decision in spec.md / research.md. Tick the checkbox (`- [x]`) for every CHK item that is satisfied; leave open `- [ ]` items unchanged with a brief inline note about why. Additionally note in this audit that **FR-011, FR-012, FR-021, and FR-027 are "MUST NOT" / negative requirements** — they have no explicit task because they are satisfied by the *absence* of contradicting work in `tasks.md`. Verification: FR-011 (CPU stays default) is verified by T030 byte-identity; FR-012 (GPU stays opt-in) is verified by T029's no-flag CPU run defaulting to `cpu-default`; FR-021 (no new persisted artifact) is verified by reviewing `tasks.md` for any task that creates a new artifact under `tests/stage1_vendor_identity/` or elsewhere (none exists); FR-027 (no new OCR engine) is verified by reviewing T007's `PREPROCESS_STRATEGIES` for any value that names a non-Paddle engine (none exists) and T008's `ocr_only.py` for any non-`paddleocr` import (none exists).
- [x] T038 Quickstart walkthrough verification — CPU portions: run quickstart §4 (CPU warn-and-proceed) and §5 (unknown-preset fail-fast on the new axis) end-to-end and confirm each command's expected output matches the documented expectation. GPU portions (§1 / §2 / §3 / §6 / Appendix A benchmark) require workstation GPU and are deferred under T034 if no GPU is available at landing.
- [x] T039 [P] Validator pass and corpus-baseline immutability check: `python -m dartwing_ocr.validator validate corpus tests/stage1_vendor_identity/` returns success against contract set 1.2.0; `git diff main -- tests/stage1_vendor_identity/` returns empty (this feature has not modified any committed corpus baseline, per FR-019 / SC-007).
- [x] T040 [P] Run the existing `tests/contract_tests/` suite (the v1.2.0 contract tests must continue to pass unchanged per FR-020). Confirm the existing feature-014/015/016/017/018 test suites also pass unchanged after this feature's changes (FR-022 carry-forward).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories. T002–T006 can run in parallel; T006a depends on T006.
- **User Stories (Phase 3+)**: All depend on Foundational phase completion.
- **Polish (Phase 9)**: Depends on all desired user stories being complete; T034 (deferral capture) can be drafted as soon as it is known which `@gpu`-marked tasks will be deferred. T035 (Q3 warmup wiring) depends on T008 (`ocr_only.py` exists) and T011 (orchestrator dispatches on `preprocess_strategy.kind`); land it with US1 or as its own commit before merge.

### User Story Dependencies

- **US1 (P1)**: Depends only on Phase 2. T007 creates `preprocess_strategies.py` and T008 creates `ocr_only.py` — they are independent of each other and can be authored in parallel. T009 (CLI flag) depends on T007 (registry exists for `resolve_preprocess_strategy` import). T011 (orchestrator) depends on T007 + T008 + T010 (optin module exposes `derive_run_summary_preprocess_strategy_id`).
- **US2 (P1)**: Depends only on Phase 2 (T006 created the `RunSummary` fields and T006a wired the threading scaffold). T009 / T011 (US1) feeds the `preprocess_strategy_id` value into that scaffold; US2's audit task T018 verifies the emission contract is satisfied and does not depend on US1 being complete (it depends on Phase 2 only).
- **US3 (P1)**: Depends on Phase 2 + T008 (US1's `ocr_only.py` provides the module where `check_eligibility` is added in T020). T021 (orchestrator fallback wiring) depends on T011 (orchestrator dispatch exists) AND T020 (`check_eligibility` exists). US3 can start in parallel with US1 once T008 lands (developers can split T020 / T021 / T022 / T023 / T024 / T025 from T009 / T012 / T013 / T014 / T015 / T016 / T017).
- **US4 (P2)**: Depends on Phase 2 + the CLI-flag wiring done in T009 (US1) — T028's warn-and-proceed branch sits AFTER `resolve_preprocess_strategy` succeeds in the parse path.
- **US5 (P2)**: Depends on US1 + US3 having produced GPU runtime outputs (T017, T026 / T027). US5's CPU-safe portions are minimal; T031 itself is `@gpu` and lands as part of T034's deferral set if no GPU at landing.
- **US6 (P3)**: Depends on US5's end-to-end runs (T031) producing per-cell `evaluation_run_summary.json` and `evaluation_document.json` files; T032 / T033 are `@gpu` and follow the same deferral path as T031.

### Within Each User Story

- Tests can be written (and SHOULD fail initially) before the implementation tasks they validate, but several tasks are CPU-safe assertion-only tests against the foundational structures from Phase 2 (T012, T013, T014, T015, T016, T019, T023, T024, T025, T029, T030) — those are ready to write as soon as Phase 2 lands.
- Models / data-shape work (preset registry, OCR-only module) before runtime wiring (orchestrator / CLI threading).
- Runtime wiring before observation (run_summary identifier emission).
- Observation before promotion-gate evaluation.

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel — Phase 1 has only T001 (verification only).
- All five Foundational tasks (T002 – T006) marked [P] can run in parallel within Phase 2; T006a depends on T006.
- Once Foundational completes, US1's T007 (registry) + T008 (ocr_only.py) + T010 (optin) can run in parallel, then T009 (CLI) + T011 (orchestrator) sequentially after them.
- US3 can begin in parallel with US1's remaining tasks once T008 lands (T020 in `ocr_only.py`, T021 in `pipeline.py`, T022 in `corpus_run.py` / `runner.py`).
- Same-file contention points: `pipeline.py` (T011 in US1 vs. T021 in US3) MUST be sequenced inside one PR; `cli.py` (T009 in US1 vs. T028 in US4) MUST be sequenced inside one PR.
- Within each user story, all tests marked [P] can run in parallel; CPU-safe and `@gpu`-marked tests target different test files / different fixtures so they do not contend.
- Polish phase tasks T037 / T039 / T040 can run in parallel; T034 is a single audit-trail entry; T035 / T036 / T038 are sequential.

---

## Parallel Example: User Stories 1 + 3

```bash
# After Phase 2 completes, launch US1 + US3 implementation in parallel (one developer per story):

# Developer A — US1 (preprocess-strategy axis + OCR-only engine):
Task: "Create preprocess_strategies.py per T007"
Task: "Create ocr_only.py per T008 (registry + run_ocr_only_page + cluster_lines_into_blocks)"
Task: "Add --preprocess-strategy CLI flag per T009"
Task: "Create preprocess_strategy_optin.py per T010"
Task: "Wire preprocess strategy into pipeline.py orchestrator per T011"

# Developer B — US3 (eligibility + fallback orchestration), starts as soon as T008 lands:
Task: "Implement check_eligibility in ocr_only.py per T020"
Task: "Wire fallback orchestration in pipeline.py per T021"
Task: "Wire ocr_only_fallback_count accumulator per T022"

# Note: Both developers touch pipeline.py (T011 vs T021).
# Sequence within each branch and resolve as a fast-follow merge to avoid edit conflicts.

# CPU-safe tests can be authored in parallel with implementation:
Task: "Preprocess strategies registry test per T012"
Task: "Optin module test per T013"
Task: "Block clustering unit test per T014"
Task: "Eligibility unit test per T023"
Task: "Schema-version test per T015 (extended by T019 + T024)"
Task: "Unknown-preset fail-fast test per T016"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only — OCR-only candidate)

1. Complete Phase 1: Setup (T001 — verify gpu marker).
2. Complete Phase 2: Foundational (T002–T006 — five parallel additions; T006a sequential after T006). CRITICAL — blocks all stories.
3. Complete Phase 3: User Story 1 (T007–T017).
4. **STOP and VALIDATE**: run T012–T016 CPU-safe tests; run T017 if workstation GPU is available, else defer per FR-025 in T034.
5. Deploy/demo if ready — OCR-only candidate landing alone is shippable value (operators can opt into `ocr-only-v1` and observe the latency reduction on `run_summary`). Note: without US3's fallback path, an OCR-only run on a thin-evidence document silently produces sparse output — landing US1 without US3 is acceptable only if the team accepts that risk for the demo window.

### Incremental Delivery

1. Setup + Foundational → Foundation ready.
2. Add US1 → CPU-safe tests + (optionally) `@gpu` per-page-inference comparison → Deploy/Demo (MVP — OCR-only opt-in, no fallback yet).
3. Add US3 → CPU-safe eligibility tests + (optionally) `@gpu` fallback + orthogonality tests → Deploy/Demo (deterministic sufficiency + fallback wired).
4. Add US2 → identifier-stability tests pass → Deploy/Demo (operator-facing identifier surface complete on this axis).
5. Add US4 → CPU/CI non-regression confirmed → Safe for production CI image without GPU.
6. Add US5 → end-to-end pipeline regression on each cell → Safe for downstream-stage compatibility.
7. Add US6 → promotion-gate evidence captured → Safe to promote a new GPU default if `ocr-only-v1` passes the gate.
8. Land T035 (Q3 warmup wiring) at any point after T008 + T011 are complete; recommend folding into the US1 PR or as a fast-follow.
9. Each story adds value without breaking previous stories.

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (one PR with T002–T006 + T006a).
2. Once Foundational is done:
   - Developer A: US1 (T007–T017) — preprocess-strategy axis + OCR-only engine
   - Developer B: US3 (T020–T027) — eligibility + fallback orchestration; starts after T008 lands
   - Developer C: US2 + US4 (T018–T019, T028–T030) — operator visibility + CPU/stub safety
3. Once US1 + US3 are done:
   - Developer A or D: US5 (T031) — end-to-end pipeline regression on the two cells
   - Developer A or D: US6 (T032–T033) — promotion-gate evidence + (optional) default-flip
4. T035 (Q3 warmup wiring) by Developer A (owns OCR-only engine context) — fold into US1 PR or fast-follow.
5. Polish phase by whoever is available.

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks.
- [Story] label maps task to specific user story for traceability.
- `@gpu` in a description marks tasks that need workstation GPU; per FR-025 these MAY be deferred and tracked in T034 if workstation GPU is unavailable at landing.
- Each user story should be independently completable and testable.
- Verify CPU-safe tests pass before moving to `@gpu` workstation verification.
- Commit after each task or logical group (the existing `before_*` git hooks in `.specify/extensions.yml` will prompt).
- Stop at any checkpoint to validate the story independently.
- Avoid: vague tasks, same-file conflicts (the `pipeline.py` tasks T011 vs T021 are sequential within their PRs to avoid this; `cli.py` tasks T009 vs T028 similarly sequential), cross-story dependencies that break independence.
- This feature reuses feature 017's `UnknownPresetError` (R-019.12 — additive widening of `preset_axis: Literal[…]`) and `ExitCode.UNKNOWN_PRESET = 16` rather than introducing a new exception class or exit code; this is captured in T002 and T003 as verification-only / additive-only tasks.
- The two new threshold values (`OCR_ONLY_MIN_TOKEN_COUNT = 8`, `OCR_ONLY_MIN_CONFIDENCE_MEAN = 0.60`) live on `PreprocessStrategy("ocr-only-v1")` — tuning is a code change plus (potentially) a new `preprocess_strategy_id` value per FR-001, never a runtime knob.
- The Q3 warmup-binding rule (T035) is the single point where this feature touches feature 016's warmup machinery; all other feature 016 invariants are untouched per FR-022.
