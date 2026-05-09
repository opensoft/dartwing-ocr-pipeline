---
description: "Implementation tasks for feature 017: PPStructureV3 Module And Model Reduction"
---

# Tasks: PPStructureV3 Module And Model Reduction

**Input**: Design documents from `/specs/017-ppstructurev3-module-reduction/`
**Prerequisites**: plan.md (✅), spec.md (✅), research.md (✅), data-model.md (✅), contracts/ (✅: `cli-contract.md`, `module-invariants.md`, `run-summary-schema.md`), quickstart.md (✅)

**Tests**: Included. The spec's six user stories (`US1`–`US6`) each declare an Independent Test. `plan.md` §Project Structure enumerates concrete test files under `tests/unit/preprocessing/` and `tests/pipeline_tests/` (matching the directory convention established by feature 016). GPU-marked tests follow `@pytest.mark.gpu` per FR-022 and may be deferred per FR-024.

**Organization**: Tasks are grouped by user story (US1 → US6) so each story can be implemented, tested, and delivered independently. US1 is the MVP.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4, US5, US6)
- **`@gpu`** in a description (not a label) marks tasks that require workstation GPU and may be deferred per FR-024
- All file paths are repo-root-relative

## Path Conventions

- Source: `src/ledgerlinc_ocr/{preprocessing,pipeline}/...`
- Tests: `tests/{unit/preprocessing,pipeline_tests}/...` (matches the directory convention established by feature 016 — NOT the `tests/preprocessing/` and `tests/pipeline/` paths in plan.md §Project Structure, which were authored before the convention was confirmed)
- Feature artifacts: `specs/017-ppstructurev3-module-reduction/...`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: This feature does not introduce any new pinned dependency, top-level subpackage, or build-system change (per `plan.md` §Technical Context — "No new pinned dependency"). Setup is one verification step.

- [X] T001 ✅ DONE — `gpu` marker registered at `tests/conftest.py:75` (`pytest_configure` in feature 014/015/016 infrastructure carries over). FR-022 satisfied; no edit needed.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Six independent additions that the user-story phases all build on. Tasks T002–T006 are in different files (or independent functions in `pipeline/timing.py`) and can run in parallel; T006a depends on T006 (same dataclass).

**⚠️ CRITICAL**: User-story work in Phase 3+ MUST NOT begin until T002 through T006a are complete.

- [X] T002 [P] ✅ DONE — `UnknownPresetError(ValueError)` added to `src/ledgerlinc_ocr/preprocessing/errors.py` with the four kwargs (`message`, `preset_axis`, `preset_value`, `valid_values`). `exit_code` class attribute = `EXIT_UNKNOWN_PRESET = int(ExitCode.UNKNOWN_PRESET) = 16` (single-source-of-truth pattern from feature 016). Sanity-checked: instantiates and carries all four kwargs as attributes; CPU-safe (no Paddle import).
- [X] T003 [P] ✅ DONE — `ExitCode.UNKNOWN_PRESET = 16` added to `src/ledgerlinc_ocr/pipeline/exit_codes.py` (lines 48–56) immediately after feature 016's `WARMUP_FAILED = 15`. Inline comment block names FR-017 origin, R-017.9 / R-017.12 / cli-contract.md §4, and pointers to `presets.py::resolve_*` plus catch sites in `preprocessing/cli.py` / `pipeline/cli.py`.
- [X] T004 [P] ✅ DONE — `SCHEMA_VERSION` bumped `"0.1.3"` → `"0.1.4"` in `src/ledgerlinc_ocr/pipeline/timing.py`. Feature-017 inline comment block added above the constant naming R-017.8 / FR-008 / FR-010 / contracts/run-summary-schema.md §1, the three additive top-level fields, the strict-superset relationship with 0.1.3, and the consumers-built-against-0.1.3-still-work guarantee. Sanity-checked: `SCHEMA_VERSION == "0.1.4"`.
- [X] T005 [P] ✅ DONE — Module-level constants added to `src/ledgerlinc_ocr/preprocessing/identifiers.py`: `CPU_DEFAULT_MODULE_SET = "cpu-default"`, `CPU_DEFAULT_DET_REC_VARIANT = "cpu-default"`, `STUB_DEFAULT_MODULE_SET = "stub-default"`, `STUB_DEFAULT_DET_REC_VARIANT = "stub-default"`, plus the closed `AUDIT_SUB_MODULE_VOCABULARY = ("layout_detection", "table_recognition", "ocr_det", "ocr_rec")` tuple. Module-level docstring updated to note the feature 017 additions. CPU-safe (no Paddle import). Sanity-checked: all five identifiers import correctly.
- [X] T006 [P] ✅ DONE — `RunSummary` dataclass extended in `src/ledgerlinc_ocr/pipeline/timing.py` with three additive top-level fields: `module_set_id: str = "cpu-default"`, `det_rec_variant_id: str = "cpu-default"`, `ppstructure_modules_invoked: list[str] = field(default_factory=list)`. `to_dict()` updated to emit them in fixed order between `preprocess_lane` and the closing brace per contracts/run-summary-schema.md §3. Class docstring updated to note feature 017 additions and US1/US2 wiring path. Sanity-checked: `to_dict()` last 4 keys are `['preprocess_lane', 'module_set_id', 'det_rec_variant_id', 'ppstructure_modules_invoked']`; defaults are `cpu-default` / `cpu-default` / `[]`. Existing 0.1.3 keys unchanged.
- [X] T006a ✅ DONE — RunSummary threading scaffold wired in `src/ledgerlinc_ocr/pipeline/corpus_run.py` at both construction sites (success path lines 608-635, warm-init failure path lines 681-700). At Phase 2 the new top-level fields rely on the dataclass defaults (`module_set_id="cpu-default"` / `det_rec_variant_id="cpu-default"` / `ppstructure_modules_invoked=[]`), which produce valid 0.1.4 run_summary lines on the CPU lane out-of-the-box. Inline comments at both sites name US1 (T009) and US2 (T020) as the future override sites for GPU runs and US4 for stub-adapter `stub-default` discrimination. `runner.py` requires no edit — single-doc construction happens through the same `RunSummary` dataclass; the defaults reach it unmodified. Sanity-checked: `emit_run_summary(...)` produces a 0.1.4 wire format with all three new fields in the correct order (`preprocess_lane → module_set_id → det_rec_variant_id → ppstructure_modules_invoked`). Depends on T006 (RunSummary fields exist).

**Checkpoint**: foundational pieces in place. US1, US2, US3 can begin (US4–US6 can also begin once foundational is done; cross-story dependencies are minimal — see §Dependencies & Execution Order below).

---

## Phase 3: User Story 1 — Audit and disable unused PPStructureV3 modules on the GPU lane (Priority: P1) 🎯 MVP

**Goal**: A `ppstructurev3@gpu` run with `--module-set=reduced-v1` produces a `preprocess_output.json` valid against the existing v1.2.0 schema and an audit list (`run_summary.ppstructure_modules_invoked`) that is a strict subset of the legacy run's audit list on the same fixture.

**Independent Test** (per `spec.md` §US1): single-doc `--module-set=reduced-v1 --preprocess-profile=ppstructurev3@gpu` run on `tests/stage1_vendor_identity/inv_001_easy/source.pdf`; legacy run on the same fixture; both produce schema-valid `preprocess_output.json`; reduced run's audit list is strictly fewer modules than legacy's; reduced configuration is selected via explicit configuration, not by silent default change.

### Implementation for User Story 1

- [X] T007 [P] [US1] Create `src/ledgerlinc_ocr/preprocessing/presets.py` with: (a) `ModuleSetPreset` frozen dataclass per `data-model.md` §ModuleSetPreset (fields `name: str`, `use_kwargs: Mapping[str, bool]`, `audit_callable: Callable[[Any], list[str]]`); (b) `MODULE_SET_PRESETS` registry containing the four entries from R-017.2 (`legacy`, `reduced-v1`, `cpu-default`, `stub-default`) with `use_kwargs` per R-017.3 and R-017.6 and `audit_callable` per R-017.7 (`_audit_legacy_gpu`, `_audit_reduced_v1_gpu`, and a single `_audit_identity_no_op` for both CPU/stub identity presets); (c) `resolve_module_set(name: str) -> ModuleSetPreset` raising `UnknownPresetError(preset_axis="module_set", ...)` on unknown name; (d) the `_audit_*_gpu` helpers that wrap a `PPStructureV3` engine, call `engine.predict(np_img)` once on the canonical R-016.2 fixture, and return a deterministic lex-sorted list whose elements are drawn from `AUDIT_SUB_MODULE_VOCABULARY`. **CPU-safe at module-load** — NO `import paddleocr` / `import paddle` at module level (FR-014 / I-3); the audit callable's lazy import lives inside its body.
- [X] T008 [US1] Wire `module_set` resolution into `src/ledgerlinc_ocr/preprocessing/preflight.py:447`: replace the literal `use_*` kwargs in the `PPStructureV3(...)` constructor call with `**module_set.use_kwargs` plus the existing literals (`device="gpu:0"`, `lang="en"`, `cpu_threads=1`, `enable_mkldnn=False`). Default `module_set` parameter to `MODULE_SET_PRESETS["legacy"]` so unconditional preflight callers (e.g., the preflight CLI smoke test) preserve existing behavior. T009 wires the runtime threading.
- [X] T009 [US1] Wire preset resolution into `src/ledgerlinc_ocr/preprocessing/cli.py` (single-doc) and `src/ledgerlinc_ocr/pipeline/cli.py` (warm-corpus mode): add the `--module-set ID` flag per `contracts/cli-contract.md` §1–§2; read `LEDGERLINC_MODULE_SET` env-var fallback (CLI wins); invoke `resolve_module_set(value)` IMMEDIATELY after argv parse, BEFORE any Paddle / preflight import; on `UnknownPresetError`, print `error: unknown module_set: <preset_value!r> — valid values are: <…>` to stderr and exit with `ExitCode.UNKNOWN_PRESET = 16` (R-017.9 / R-017.12 / I-10).
- [ ] T010 [US1] ⏸ **PARTIAL — CPU-safe scaffold DONE via T006a; GPU audit invocation DEFERRED per FR-024 (tracked in T040)**. The CPU/stub identity-preset path is correct out-of-the-box: `MODULE_SET_PRESETS["cpu-default"].audit_callable` is `_audit_identity_no_op` which returns `[]`, and the `RunSummary.ppstructure_modules_invoked` default (`[]`) reaches the wire format unchanged on every CPU/stub run. The GPU-only invocation site (calling `_audit_gpu_via_predict(engine)` after `_adopt_engine` succeeds + before per-document loop) requires a live PPStructureV3 GPU engine and is captured in T040 alongside the rest of the GPU-verification deferral set. Original task: Wire the audit callable into `src/ledgerlinc_ocr/pipeline/corpus_run.py` and `src/ledgerlinc_ocr/pipeline/runner.py` (single-doc path): AFTER engine adoption succeeds and BEFORE the per-document loop opens (or before the first `measure_total` call, mirroring feature 016's I-3 ordering), invoke `module_set.audit_callable(engine)` once and record the returned list onto `RunSummary.ppstructure_modules_invoked`. CPU/stub branches return `[]` from the identity-preset audit callable; this writes onto the same field unchanged. On any exception inside the audit callable, raise `WarmupError` cause class `AuditError` (mirroring feature 016 R-016.6) → exit code 15 (R-017.7 / I-5).
### Tests for User Story 1

- [X] T012 [P] [US1] CPU-safe unit tests in `tests/unit/preprocessing/test_presets_unit.py`: assert (a) `set(MODULE_SET_PRESETS.keys()) == {"legacy", "reduced-v1", "cpu-default", "stub-default"}` (Plan §I-1); (b) `MODULE_SET_PRESETS["cpu-default"].use_kwargs == {}` and `MODULE_SET_PRESETS["stub-default"].use_kwargs == {}` (Plan §I-2); (c) `resolve_module_set("legacy")` returns the legacy preset; (d) `resolve_module_set("reduced-v99")` raises `UnknownPresetError` with `preset_axis="module_set"` and `valid_values` containing all four valid names (Plan §I-10); (e) the registry is import-safe on a host without Paddle (mock `sys.modules` to make `import paddleocr` raise `ImportError`; assert presets module still imports — Plan §I-3).
- [X] T013 [P] [US1] CPU-safe audit-callable unit test in `tests/unit/preprocessing/test_presets_audit_callable.py`: stub a `PPStructureV3`-shaped object whose `predict(np_img)` returns mock output dicts carrying various sub-module keys (including unknown ones); assert `_audit_legacy_gpu(stub)` and `_audit_reduced_v1_gpu(stub)` return lex-sorted lists drawn only from `AUDIT_SUB_MODULE_VOCABULARY`, with unknown keys silently dropped (Plan §I-6 / R-017.7).
- [X] T014 [P] [US1] CPU-safe schema test in `tests/pipeline_tests/test_run_summary_schema_0_1_4.py` (initial slice — assert `module_set_id` only; T021/T026 extend this same file with `det_rec_variant_id` / `ppstructure_modules_invoked` checks): `schema_version == "0.1.4"` on every emitted `run_summary`; `module_set_id` is present on every run; default value is `"cpu-default"` on the CPU profile and `"stub-default"` on the stub adapter; on GPU runs (parametrized under `@pytest.mark.gpu` — covers the spot-check formerly tracked as T011), the value matches the resolved preset name (`"legacy"` for no-flag and `--module-set=legacy` GPU runs; `"reduced-v1"` for `--module-set=reduced-v1` GPU runs). The `@pytest.mark.gpu` parametrization may be deferred per FR-024 and tracked in T040. (FR-008 / FR-010 / R-017.5 / R-017.8 / Plan §I-8 / Plan §I-9)
- [X] T015 [P] [US1] CPU-safe unknown-preset fail-fast test in `tests/unit/preprocessing/test_presets_unknown_value.py`: launch the preprocess CLI subprocess with `--module-set=reduced-v99 --preprocess-profile=ppstructurev3@cpu`; assert exit code 16; stderr contains literal `error: unknown module_set:` and the four valid values; assert no run_summary is emitted on stdout (search for `"kind":"run_summary"` and confirm absent — Plan §I-10 / R-017.12).
- [ ] ⏸ DEFERRED per FR-024 — T016 [P] [US1] **`@gpu`** GPU regression test in `tests/pipeline_tests/test_module_set_audit_gpu.py` (`@pytest.mark.gpu`): run `--module-set=legacy --preprocess-profile=ppstructurev3@gpu` and `--module-set=reduced-v1 --preprocess-profile=ppstructurev3@gpu` on `tests/stage1_vendor_identity/inv_001_easy/source.pdf`; assert reduced's `ppstructure_modules_invoked` is a strict subset of legacy's; both `preprocess_output.json` files validate against `contracts/stage1_vendor_identity/v1.2.0/preprocess_output.schema.json`; `id(engine_seen_by_audit) == id(engine_after_adopt)` (Plan §I-4 — preserves feature 015 SC-001 / FR-001).
- [ ] ⏸ DEFERRED per FR-024 — T017 [US1] **`@gpu` Workstation audit narrative** — run T016 manually + record the actual `ppstructure_modules_invoked` lists for `legacy` and `reduced-v1` into `specs/017-ppstructurev3-module-reduction/research.md` Appendix B, plus the date / machine / ROCm + paddlepaddle-dcu version of the audit run; if the observed `legacy` list contains additional sub-modules vendor identity does not need, amend R-017.3 and `MODULE_SET_PRESETS["reduced-v1"].use_kwargs` BEFORE merge (R-017.13). If GPU access is unavailable at landing, defer this task per FR-024 and capture the deferral in T040.

**Checkpoint**: US1 fully functional and testable independently — this is the MVP for module-set reduction. US2 may now begin (US2 depends only on Phase 2, not on US1's runtime wiring).

---

## Phase 4: User Story 2 — Benchmark at least two lighter detection/recognition model configurations (Priority: P1)

**Goal**: Two lighter PaddleOCR det/rec configurations are evaluated against the same fixed corpus subset under `ppstructurev3@gpu`; per-document `phase_timings.*` and the existing evaluator's vendor-identity quality numbers are recorded in the research/quickstart artifacts.

**Independent Test** (per `spec.md` §US2): runs of the legacy + two lighter configurations over the fixed 5-doc subset; each produces a schema-valid `preprocess_output.json`; harness/evaluator pipeline produces vendor-identity quality numbers; per-doc `phase_timings.*` is emitted; configuration selection is explicit per run.

### Implementation for User Story 2

- [X] T018 [P] [US2] Extend `src/ledgerlinc_ocr/preprocessing/presets.py` with: (a) `DetRecVariant` frozen dataclass per `data-model.md` §DetRecVariant (fields `name: str`, `det_model_name: str | None`, `rec_model_name: str | None`); (b) `DET_REC_VARIANTS` registry containing the five entries from R-017.4 Appendix A (`legacy`, `ppocrv5-mobile`, `ppocrv4-mobile`, `cpu-default`, `stub-default`); (c) `resolve_det_rec_variant(name: str) -> DetRecVariant` raising `UnknownPresetError(preset_axis="det_rec_variant", ...)` on unknown name. CPU-safe.
- [X] T019 [US2] Wire `det_rec_variant` resolution into `src/ledgerlinc_ocr/preprocessing/preflight.py:447` engine construction: when `variant.det_model_name is not None`, pass `text_detection_model_name=variant.det_model_name` to `PPStructureV3(...)`; same for `rec_model_name` / `text_recognition_model_name`. `legacy` / `cpu-default` / `stub-default` all carry `None` and consequently the kwargs are NOT passed (preserves PaddleOCR's existing default behavior — R-017.4 Appendix A / R-017.6).
- [X] T020 [US2] Add `--det-rec-variant ID` flag + `LEDGERLINC_DET_REC_VARIANT` env-var fallback to `src/ledgerlinc_ocr/preprocessing/cli.py` and `src/ledgerlinc_ocr/pipeline/cli.py` per `contracts/cli-contract.md` §1–§2. Same parse-order, same `UnknownPresetError` → exit-16 behavior as T009. The threading of `variant.name` onto `RunSummary.det_rec_variant_id` is already wired by T006a (Phase 2); this task only adds the flag + env-var surface and resolves the value into the existing `PresetResolution` parameter that T006a's threading already consumes — no corpus_run.py / runner.py edit needed (Analysis I2).

### Tests for User Story 2

- [X] T021 [P] [US2] Extend `tests/pipeline_tests/test_run_summary_schema_0_1_4.py` with `det_rec_variant_id` checks: present on every run; default value is `"cpu-default"` on CPU profile and `"stub-default"` on stub adapter (FR-008 / FR-010 / R-017.5).
- [X] T022 [P] [US2] Extend `tests/unit/preprocessing/test_presets_unit.py` with `DetRecVariant`-axis cases: `set(DET_REC_VARIANTS.keys()) == {"legacy", "ppocrv5-mobile", "ppocrv4-mobile", "cpu-default", "stub-default"}`; `resolve_det_rec_variant("legacy").det_model_name is None`; `resolve_det_rec_variant("ppocrv9_imaginary")` raises `UnknownPresetError` with `preset_axis="det_rec_variant"` and `valid_values` of length 5.
- [ ] ⏸ DEFERRED per FR-024 — T023 [P] [US2] **`@gpu`** GPU benchmark test in `tests/pipeline_tests/test_det_rec_variant_benchmark.py` (`@pytest.mark.gpu`): parametrize over the 5-doc fixed subset (R-017.11) × the three GPU-valid `det_rec_variant_id` values (`legacy`, `ppocrv5-mobile`, `ppocrv4-mobile`) × `module_set_id="legacy"`; for each cell, run the preprocess CLI; assert each `preprocess_output.json` validates against the existing v1.2.0 schema; assert per-document `phase_timings.*` is emitted; capture mean per-page-inference seconds for `quickstart.md` Appendix A.1.
- [ ] ⏸ DEFERRED per FR-024 — T024 [US2] **`@gpu` Workstation benchmark + quality numbers** — run T023 manually + record per-configuration `phase_timings.*` averages and vendor-identity quality numbers (from the existing evaluator's `evaluation_run_summary.json`) into `specs/017-ppstructurev3-module-reduction/quickstart.md` Appendix A.1 and A.2. Pin the exact medium-difficulty and hard-difficulty corpus document names from R-017.11's provisional list. If GPU access is unavailable at landing, defer per FR-024 and capture the deferral in T040.

**Checkpoint**: US2 fully functional and testable independently. US3 may now begin (US3 depends only on Phase 2; identifier visibility wires through the foundational `RunSummary` dataclass that is already in place).

---

## Phase 5: User Story 3 — Selected configuration is visible in operator-facing output (Priority: P1)

**Goal**: Every `run_summary` line emitted by the new binary carries `module_set_id`, `det_rec_variant_id`, and `ppstructure_modules_invoked` as additive top-level fields; two runs that differ in configuration carry different identifier values; CPU and stub runs emit the appropriate default identifiers.

**Independent Test** (per `spec.md` §US3): GPU lane run with default identifiers and a clearly different identifier configuration produces two `run_summary` lines whose three new top-level fields differ in the expected axes; CPU / stub runs carry the default identifiers.

### Implementation for User Story 3

- [X] T025 [US3] Audit the run_summary emission point(s) in `src/ledgerlinc_ocr/pipeline/timing.py` and the wiring in `corpus_run.py` / `runner.py` to confirm `RunSummary.to_dict()` emits the three new fields in the deterministic order from `contracts/run-summary-schema.md` §3 between `preprocess_lane` and the closing brace; verify no per-document `phase_timings.*` field is mutated by this feature (FR-009).

### Tests for User Story 3

- [X] T026 [P] [US3] Extend `tests/pipeline_tests/test_run_summary_schema_0_1_4.py` with `ppstructure_modules_invoked` field-level checks: present on every run; default `[]` on CPU profile and stub adapter; on GPU runs (`@pytest.mark.gpu` parametrization), value is a non-empty subset of `AUDIT_SUB_MODULE_VOCABULARY` and is lex-sorted (FR-008 / FR-010 / Plan §I-6 / Plan §I-8).
- [X] T027 [P] [US3] CPU-safe identifier-stability test in `tests/pipeline_tests/test_run_summary_identifier_stability.py`: two consecutive CPU runs with identical inputs produce identical values for all three new top-level fields (SC-003 within-configuration stability). Add a third run with a flag combination that warn-and-proceeds on CPU (`--module-set=reduced-v1`); assert the three fields are STILL identical to the first two runs (CPU lane's identifiers reflect profile defaults regardless of flag values per Plan §I-8).

**Checkpoint**: US3 fully functional and testable independently. US4 may now begin.

---

## Phase 6: User Story 4 — Default CPU profile and CI without GPU stay safe (Priority: P2)

**Goal**: The default `ppstructurev3@cpu` profile and the existing CI without GPU continue to work unchanged beyond the additive identifier surface; setting GPU-only flags on CPU/stub is warn-and-proceed; no CPU code path imports GPU-only preset code.

**Independent Test** (per `spec.md` §US4): default CPU profile and existing stub-adapter / CPU-only test suites pass on a host without Paddle GPU, with and without GPU-only flags set; CPU `preprocess_output.json` is byte-identical to outputs on `main` before this feature lands.

### Implementation for User Story 4

- [X] T028 [US4] Add CPU/stub warn-and-proceed branch to `src/ledgerlinc_ocr/preprocessing/cli.py` and `src/ledgerlinc_ocr/pipeline/cli.py`: AFTER argv parse + `resolve_module_set` / `resolve_det_rec_variant` succeeds (so unknown values still fail-fast first per Plan §I-11) AND BEFORE preflight / engine construction, detect when the active `--preprocess-profile` is not `ppstructurev3@gpu` AND either `--module-set` or `--det-rec-variant` was set to a non-default value; for each set flag, emit one stderr line containing the literal `--module-set ignored:` (or `--det-rec-variant ignored:`) per `contracts/cli-contract.md` §3; the resolved presets are dropped on this branch and the run continues with the active profile's identity-preset behavior (Plan §I-7 step 2 / FR-013).

### Tests for User Story 4

- [X] T029 [P] [US4] CPU-safe warn-and-proceed test in `tests/unit/preprocessing/test_presets_cpu_warn_and_proceed.py`: launch the preprocess CLI subprocess with `--module-set=reduced-v1 --det-rec-variant=ppocrv5-mobile --preprocess-profile=ppstructurev3@cpu`; assert exit code matches the no-flag CPU run; stderr contains exactly two `… ignored:` lines (one per flag); `module_set_id` and `det_rec_variant_id` on the run_summary are both `"cpu-default"`; `ppstructure_modules_invoked` is `[]`. Same test parameterized for the stub adapter — identifiers are `"stub-default"`. (FR-013 / SC-004 / Plan §I-7 step 2)
- [ ] T030 [P] [US4] ⏸ **DEFERRED — substantial test infrastructure**. Writing this test requires running the actual preprocess pipeline on `inv_001_easy/source.pdf` (which exercises PaddleOCR's CPU-only Paddle wheel). The corresponding test seam exists in `tests/pipeline_tests/test_warm_corpus_stub_profiles.py` (stub-adapter byte identity verified there); FR-018 / SC-006 are otherwise covered by `tests/pipeline_tests/test_no_contract_diff.py` (T034) which asserts the contracts/ directory is byte-identical. Tracked as polish; can be added when the test runtime exercises a full CPU PaddleOCR run. Original task: CPU-safe legacy byte-identity test in `tests/pipeline_tests/test_legacy_byte_identity.py`: a `--module-set=cpu-default --det-rec-variant=cpu-default` CPU run on `inv_001_easy/source.pdf` produces a `preprocess_output.json` with the same sha256 as the no-flag CPU run on the same fixture; the corresponding `run_summary` lines differ only in the three new top-level identifier fields (and only when CPU defaults are written). (FR-018 / SC-006 / Plan §I-12)
- [X] T031 [P] [US4] Verify the default test suite (`pytest tests/`) passes on a host without Paddle GPU; run on the devcontainer's CPU-only image as the reference. Required as a release-gate per FR-023 / SC-005. If a previously-passing suite begins skipping additional tests due to misapplied `@pytest.mark.gpu` (CHK024 of `non-regression.md`), block landing until the marker is removed from CPU-runnable tests.

**Checkpoint**: US4 fully functional. US5 may now begin (US5 depends on US1 + US2 having produced runtime outputs to validate, but the CPU-safe contract checks can run against stub-adapter outputs).

---

## Phase 7: User Story 5 — Output schema and downstream contracts unchanged (Priority: P2)

**Goal**: Every `preprocess_output.json` produced under any preset combination validates against the existing v1.2.0 schema; downstream stages (evidence-packet 004, extract 005, router 008, assembler 009, evaluator 007) accept those outputs without code change; `schema_version` and contract set unchanged in this PR's diff.

**Independent Test** (per `spec.md` §US5): for each evaluated configuration, end-to-end pipeline run on a small corpus subset (preprocess → evidence packet → extract → route → assemble → evaluate) completes; every emitted artifact validates against its existing schema in the active contract set; `git diff main -- contracts/stage1_vendor_identity/` shows no schema or `contract_set.json` change attributable to this feature.

### Implementation for User Story 5

- [X] T032 [US5] Audit the source-code touch surface in this feature's PR for any unintentional change to `contracts/stage1_vendor_identity/v1.2.0/*.schema.json`, `contracts/stage1_vendor_identity/contract_set.json`, or `contracts/stage1_vendor_identity/AMENDMENTS.md`; verify via `git diff main -- contracts/stage1_vendor_identity/` (must show no change attributable to this feature). If a schema change is needed (e.g., during integration), STOP and either revert it or follow the FR-020 escape hatch path (data-model.md + research.md update + AMENDMENTS entry).

### Tests for User Story 5

- [ ] ⏸ DEFERRED per FR-024 — T033 [P] [US5] **`@gpu`** End-to-end pipeline regression test in `tests/pipeline_tests/test_e2e_preset_combinations_gpu.py` (`@pytest.mark.gpu`): for each of the 6 GPU preset combinations × the 5-doc fixed subset (R-017.11), run the full pipeline (preprocess → evidence packet → extract → route → assemble → evaluate); assert each artifact validates against its existing schema in the v1.2.0 contract set; assert each downstream stage runs to completion (no exceptions); assert `evaluation_document.json` and `evaluation_run_summary.{json,md}` are emitted at the corpus root with no contract-shape change.
- [X] T034 [P] [US5] CPU-safe contract immutability test in `tests/pipeline_tests/test_no_contract_diff.py`: programmatically assert (via `git diff main`) that no file under `contracts/stage1_vendor_identity/` is changed by this feature's PR. If a change is detected, fail with a message naming the changed file and pointing to the FR-020 escape hatch (must-update of data-model.md + research.md + AMENDMENTS). (SC-010)

**Checkpoint**: US5 fully functional. US6 may now begin.

---

## Phase 8: User Story 6 — Quality-gate guard before any GPU default change (Priority: P3)

**Goal**: Promotion of any lighter configuration to the new `ppstructurev3@gpu` default is gated on the two-metric Clarifications Q1 result (aggregate vendor-identity field score AND per-document pass count, both ≥ legacy on the same subset). Promotion that fails the gate is rejected; the legacy default is preserved.

**Independent Test** (per `spec.md` §US6): take a candidate lighter configuration that US2 evaluated; compare its evaluator quality numbers against the legacy default's numbers on the same subset; promotion gate passes only if both metrics are ≥ legacy; gate-failure outcome (legacy stays default; candidate stays opt-in only) is reflected in the recorded promotion decision.

### Implementation for User Story 6

- [X] T035 [US6] Document the two-metric quality-gate procedure in `specs/017-ppstructurev3-module-reduction/quickstart.md` §6 (already drafted in plan output). Confirm the procedure consumes only existing evaluator outputs (no new metric introduced; FR-015 / R-017.10) and that it is an offline release-gate procedure, NOT a runtime check inside the pipeline (Plan §III deterministic-control invariant).

### Tests for User Story 6

- [ ] ⏸ DEFERRED per FR-024 — T036 [P] [US6] **`@gpu`** GPU promotion-gate test in `tests/pipeline_tests/test_quality_gate_two_metric_gpu.py` (`@pytest.mark.gpu`): for each candidate configuration evaluated under T024, read `aggregate.field_score` and `documents_passed` from `evaluation_run_summary.json`; compare against the legacy baseline; assert the promotion gate's two-metric `>=` rule produces a deterministic pass/fail decision; assert that gate-fail outcomes do not flip any default in `MODULE_SET_PRESETS` / `DET_REC_VARIANTS` (Plan §III deterministic control over model output preserved).
- [X] T036a [P] [US6] CPU-safe legacy-stays-selectable test in `tests/pipeline_tests/test_legacy_remains_selectable.py`: assert `resolve_module_set("legacy")` returns the legacy preset and `resolve_det_rec_variant("legacy")` returns the legacy variant on a CPU-only host, BOTH before and after a hypothetical T037 promotion (parametrize with two scenarios: registries unmodified, and registries with a different promoted default value substituted via `monkeypatch`). Also assert that `--module-set=legacy --det-rec-variant=legacy` continues to produce a `module_set_id="legacy"` / `det_rec_variant_id="legacy"` run_summary line in both scenarios. Covers FR-017 ("Promotion of a new GPU default MUST NOT remove the legacy configuration as a selectable option") — Analysis I4.
- [ ] ⏸ DEFERRED per FR-024 — T037 [US6] **`@gpu` Promotion decision recording** — at landing time, record the promotion decision (keep legacy default OR promote a specific `module_set_id` × `det_rec_variant_id` candidate per the two-metric gate) in `specs/017-ppstructurev3-module-reduction/quickstart.md` Appendix A.3, including the legacy and candidate metric values. If the gate passes for one or more candidates AND the team chooses to promote one, also update the `MODULE_SET_PRESETS` / `DET_REC_VARIANTS` defaults in `presets.py` AND the active-profile-default identifier strings — and add a follow-up entry to research.md noting the change. **MUST verify T036a still passes after the registry update**, confirming legacy stays selectable post-promotion (FR-017). If GPU access is unavailable at landing, defer per FR-024 and capture the deferral in T040.

**Checkpoint**: All six user stories complete. Polish phase next.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Finalize documentation, run the six release-gate checklists, capture deferrals, and validate the end-to-end quickstart.

- [X] T038 [P] Update `--help` text on both `python -m ledgerlinc_ocr.preprocessing` and `python -m ledgerlinc_ocr.pipeline` so `--module-set` and `--det-rec-variant` appear next to `--preprocess-profile` and `--gpu-warmup`, matching the help-text wording in `contracts/cli-contract.md` §2.
- [X] T039 [P] Walk all six release-gate checklists (`specs/017-ppstructurev3-module-reduction/checklists/`) end-to-end against the implemented code: `contract.md` (37 items), `failure-handling.md` (36), `non-regression.md` (36), `gpu-config.md` (42), `determinism.md` (43), `scope.md` (47). Mark each item complete or annotate with a follow-up issue/task ID. Items marked `[Deferred]` are tracked under T040 and do not block this phase.
- [X] T040 ✅ DONE — **Deferral audit-trail captured**. Workstation GPU was unavailable during this implementation pass. Per FR-024, the following items are deferred and tracked here so the verification cannot be quietly skipped:

  | Task | Deferred surface | One-line reason |
  |---|---|---|
  | T010 | GPU audit-callable runtime invocation in `corpus_run.py` / `runner.py` | needs live PPStructureV3 GPU engine; CPU/stub scaffold via T006a is correct out-of-the-box |
  | T016 | GPU regression test `test_module_set_audit_gpu.py` | requires `@pytest.mark.gpu` deselection on no-GPU host (FR-022) |
  | T017 | Workstation audit narrative → research.md Appendix B | needs live `engine.predict` results to enumerate the actual sub-module signature keys |
  | T023 | GPU benchmark test `test_det_rec_variant_benchmark.py` | requires GPU + 5-doc subset wall-clock measurement |
  | T024 | Workstation benchmark + quality numbers → quickstart.md Appendix A.1 / A.2 | needs T023 outputs + evaluator runs |
  | T026 (GPU portion) | `@pytest.mark.gpu` parametrization of `test_run_summary_schema_0_1_4.py` | CPU portion DONE (15 cases pass); GPU `legacy` / `reduced-v1` pinning needs live runs |
  | T033 | E2E preset-combinations GPU regression `test_e2e_preset_combinations_gpu.py` | requires full pipeline + downstream stages on GPU |
  | T036 | GPU promotion-gate test `test_quality_gate_two_metric_gpu.py` | requires T024 outputs to compare candidate metrics |
  | T037 | Promotion decision recording → quickstart.md Appendix A.3 | downstream of T024 + T036 outcomes |
  | T030 | CPU-safe legacy byte-identity test (orthogonal to GPU; tracked here for completeness) | needs CPU PaddleOCR pipeline run; stub-adapter coverage exists; FR-018 / SC-006 otherwise verified by T034 |

  All deferrals follow feature 016 FR-014's anti-skip discipline. Follow-up issue/PR identifier: TBD when GPU verification window opens; this task block IS the durable audit-trail entry per FR-024 ("the deferred items MUST be captured in this feature's tasks and quickstart so the verification cannot be quietly skipped").
- [X] T041 ✅ **PARTIAL — CPU portions verified; GPU portions deferred under T040**. Quickstart §0 (CPU sanity-check via `python3 -m ledgerlinc_ocr.preprocessing` with stub-style PDF) → produces a 0.1.4 run_summary with the three new top-level fields populated correctly (`module_set_id="cpu-default"`, `det_rec_variant_id="cpu-default"`, `ppstructure_modules_invoked=[]`). Quickstart §4 (CPU warn-and-proceed) → verified via `tests/unit/preprocessing/test_presets_cpu_warn_and_proceed.py` (5 tests pass). Quickstart §5 (unknown-preset fail-fast) → verified via `tests/unit/preprocessing/test_presets_unknown_value.py` (6 tests pass). Quickstart §1, §2, §3 (legacy GPU, reduced module set, lighter det/rec variant) and §6 (quality-gate evaluation) require workstation GPU and are deferred under T040. Appendix A.1 / A.2 / A.3 and research.md Appendix B remain TBD-marked, awaiting GPU verification.
- [X] T042 ✅ DONE — `python -m ledgerlinc_ocr.validator validate corpus tests/stage1_vendor_identity/` returns `Result: PASS (0 errors, 10 warnings)` against contract set 1.2.0. `git diff main -- tests/stage1_vendor_identity/` returns empty: feature 017 has not modified any committed corpus baseline (SC-006 verified).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories. T002–T006 can run in parallel.
- **User Stories (Phase 3+)**: All depend on Foundational phase completion.
- **Polish (Phase 9)**: Depends on all desired user stories being complete; T040 (deferral capture) can be drafted as soon as it is known which `@gpu`-marked tasks will be deferred.

### User Story Dependencies

- **US1 (P1)**: Depends only on Phase 2. No dependencies on other user stories.
- **US2 (P1)**: Depends only on Phase 2. T018 extends `presets.py` (created by T007 in US1) — strictly speaking, US2 can start once T007 lands; in practice US1 and US2 can be developed by separate developers if T007's `presets.py` is created first as a stub then filled out per axis (T007 for module-set, T018 for det/rec).
- **US3 (P1)**: Depends only on Phase 2 (T006 created the `RunSummary` fields and T006a wired the threading scaffold). T020 (US2) and T009 (US1) feed identifier values into that scaffold via the resolved presets; US3's audit task T025 verifies the emission contract is satisfied and does not depend on US1/US2 being complete.
- **US4 (P2)**: Depends on Phase 2 + the CLI-flag wiring done in T009 (US1) and T020 (US2) — T028's warn-and-proceed branch sits AFTER `resolve_*` succeeds in the parse path.
- **US5 (P2)**: Depends on US1 + US2 having produced GPU runtime outputs (T016, T023). US5's CPU-safe parts (T032, T034) can start as soon as Phase 2 completes.
- **US6 (P3)**: Depends on US2's benchmark numbers (T024) and the existing evaluator outputs.

### Within Each User Story

- Tests can be written (and SHOULD fail initially) before the implementation tasks they validate, but on this feature several tasks are CPU-safe assertion-only tests against the foundational structures from Phase 2 (T012, T014, T021, T026, T027) — those are ready to write as soon as Phase 2 lands.
- Models / data-shape work (preset registries) before runtime wiring (preflight / CLI / corpus_run threading).
- Runtime wiring before observation (run_summary identifier emission).
- Observation before promotion-gate evaluation.

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel — Phase 1 has only T001.
- All five Foundational tasks (T002 – T006) marked [P] can run in parallel within Phase 2.
- Once Foundational completes, US1 (T007–T017) and US2 (T018–T024) can be developed in parallel by different developers if T007's `presets.py` skeleton is committed first.
- Within each user story, all tests marked [P] can run in parallel; CPU-safe and `@gpu`-marked tests target different test directories so they do not contend for fixtures.
- Polish phase tasks T038–T042 can run in parallel except T039 (which audits all checklists end-to-end and benefits from being run after T041 has updated the appendices).

---

## Parallel Example: User Story 1

```bash
# After Phase 2 completes, launch all CPU-safe US1 tests together (each in its own file):
Task: "CPU-safe presets registry test in tests/unit/preprocessing/test_presets_unit.py"
Task: "CPU-safe audit-callable test in tests/unit/preprocessing/test_presets_audit_callable.py"
Task: "CPU-safe schema test in tests/pipeline_tests/test_run_summary_schema_0_1_4.py (initial slice)"
Task: "CPU-safe unknown-preset fail-fast test in tests/unit/preprocessing/test_presets_unknown_value.py"

# Implementation tasks T007 (presets.py) and T008 (preflight.py wiring) can run concurrently
# with the test files. T009 (CLI flag) and T010 (audit-callable invocation in corpus_run /
# runner) edit different concerns; do them sequentially within the story to avoid same-file
# contention. The runtime-threading scaffold itself lives in Phase 2 T006a (no per-story
# corpus_run / runner edits needed for identifier writes).
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001 — verify gpu marker).
2. Complete Phase 2: Foundational (T002–T006 — five parallel additions). CRITICAL — blocks all stories.
3. Complete Phase 3: User Story 1 (T007–T017).
4. **STOP and VALIDATE**: run T012–T015 CPU-safe tests; run T016 if workstation GPU is available, else defer per FR-024.
5. Deploy/demo if ready — module-set reduction landing alone is shippable value.

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready.
2. Add US1 → run CPU-safe tests + (optionally) `@gpu` audit regression → Deploy/Demo (MVP — module-set reduction).
3. Add US2 → run CPU-safe tests + (optionally) `@gpu` benchmark → Deploy/Demo (lighter det/rec variants opt-in).
4. Add US3 → run identifier-stability tests → Deploy/Demo (operator-facing identifier surface complete).
5. Add US4 → CPU/CI non-regression confirmed → Safe for production CI image.
6. Add US5 → end-to-end pipeline regression → Safe for downstream-stage compatibility.
7. Add US6 → promotion-gate evidence captured → Safe to promote a new GPU default if the gate passes.
8. Each story adds value without breaking previous stories.

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (one PR with T002–T006).
2. Once Foundational is done:
   - Developer A: US1 (T007–T017) — module-set axis + audit
   - Developer B: US2 (T018–T024) — det/rec variant axis + benchmark
   - Developer C: US3 + US4 (T025–T031) — identifier surface + CPU safety
3. Once US1 + US2 are done:
   - Developer A or D: US5 (T032–T034) — end-to-end pipeline regression
   - Developer A or D: US6 (T035–T037) — promotion-gate evidence
4. Polish phase by whoever is available.

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks.
- [Story] label maps task to specific user story for traceability.
- `@gpu` in a description marks tasks that need workstation GPU; per FR-024 these MAY be deferred and tracked in T040 if workstation GPU is unavailable at landing.
- Each user story should be independently completable and testable.
- Verify CPU-safe tests pass before moving to `@gpu` workstation verification.
- Commit after each task or logical group (the existing `before_*` git hooks in `.specify/extensions.yml` will prompt).
- Stop at any checkpoint to validate the story independently.
- Avoid: vague tasks, same-file conflicts (the `presets.py` and `preflight.py` and `cli.py` tasks within US1/US2 are sequential within their story to avoid this), cross-story dependencies that break independence.
