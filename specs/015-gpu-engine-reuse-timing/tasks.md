---

description: "Task list for feature 015-gpu-engine-reuse-timing"
---

# Tasks: GPU Engine Reuse And Phase Timing

**Input**: Design documents from `/specs/015-gpu-engine-reuse-timing/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/run-summary-schema.md, contracts/module-invariants.md, quickstart.md

**Tests**: Included. The spec's success criteria (SC-001, SC-002, SC-007, SC-008) are counter / wall-clock / negative assertions that are only verifiable through tests, and `contracts/module-invariants.md` already enumerates the testable invariants (CF4–CF7, PT1–PT5, CH1–CH3, ISO1–ISO2, FF1–FF2, FP1–FP2). Per project convention, tests are written **before** the corresponding implementation tasks within each user story.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Maps task to user story (US1, US2, US3, US4)
- All paths are relative to repo root

## Path Conventions

Single Python project. Source under `src/dartwing_ocr/`, tests under `tests/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: minimal — this feature mutates existing modules; no new package directories needed.

- [X] T001 Confirm `.venv-paddle-rocm` is the verification environment for GPU-lane work and document `pip install -e ".[dev]"` is current; record any `paddleocr` / `paddlepaddle-dcu` version pinning observations in `specs/015-gpu-engine-reuse-timing/research.md` only if anything has drifted from R-014's pins (no code change otherwise). — Verified 2026-05-07: shared `.venv` has paddleocr 3.5.0 (in `>=3.5,<4`) + paddlepaddle 3.3.1 (in `>=3.0,<4`); GPU-lane verification venv `.venv-paddle-rocm` exists at parent repo root (carries over from feature 014). No drift; no research.md edit.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: shared infrastructure changes that ALL three P1 stories build on (engine adoption helper, preflight timing fields, per-page accumulator reshape, run_summary schema bump). No user-story phase can begin until these land.

**⚠️ CRITICAL**: Phase 2 changes touch three files (`preprocessing/preflight.py`, `preprocessing/ocr.py`, `pipeline/timing.py`). Order matters within a file but not across files.

### Foundational tests (write first, ensure FAIL before implementation)

- [X] T002 [P] Add `tests/unit/test_preflight_engine_persistence.py` with four cases: (a) CF5 — after `classify(attempt_ppstructurev3_init=True)` returns `PPSTRUCTUREV3_INIT_SUCCEEDED`, `id(ocr._ENGINE)` equals the engine that classify built (use a `paddleocr.PPStructureV3` mock + capture); (b) CF6 — after `classify(attempt_ppstructurev3_init=False)`, `ocr._ENGINE is None` and `ocr._ENGINE_DEVICE is None`; (c) CF4 — after CF5 completes, calling `ocr._get_engine(device="cpu")` raises `RuntimeError`; (d) FF2 — after a successful first `ensure_gpu_ready()`, a second call short-circuits via the `_LAST_READOUT` cache without re-importing paddle and without reconstructing PPStructureV3 (assert `paddleocr.PPStructureV3` mock `call_count == 1` after both calls). Use `ocr.reset_gpu_inference_ns()` + a new helper to clear `_ENGINE` and `preflight._LAST_READOUT` between cases.
- [X] T003 [P] Add `tests/unit/test_phase_timings_unit.py` covering PT1 / PT2 / PT3 / PT4: (a) every value emitted by `pipeline/timing.py`'s new `phase_timings` builder is shape `{"seconds": float}` only (no extra keys); (b) `per_page_inference` items are `{"page": int, "seconds": float}` only; (c) `per_page_inference[*].page` is strictly ascending and 1-based; (d) durations come from monotonic clock (assert `phase_timings.total.seconds >= sum of named child phases - 1e-3` to verify a single clock source).
- [X] T004 [P] Add `tests/pipeline_tests/test_run_summary_schema_0_1_2.py` with three cases: (a) PT5 — `pipeline.timing.SCHEMA_VERSION == "0.1.2"`; (b) CH2 — parse every JSON line from a stub-driven warm-corpus subprocess and assert `set(line["kind"] for line in lines)` is a subset of `{"run_summary","preflight_readout","failure"}` plus the existing per-doc artifact kinds; (c) CH3 — `phase_timings.warmup` is absent on a default GPU run.

### Foundational implementation

- [X] T005 In `src/dartwing_ocr/preprocessing/preflight.py`, extend `PreflightEvidence` with `paddle_import_seconds: Optional[float] = None` and `gpu_bind_probe_seconds: Optional[float] = None` (after the existing `runtime_device_exposure` field; preserve frozen-dataclass-with-defaults positional rules). Update `PreflightReadout.to_json_dict()` to include both new keys (None ⇒ JSON null). Update `to_text()` to omit them when None (mirroring existing fields). [R-015.2 / data-model §GPU Readiness Result]
- [X] T006 In `src/dartwing_ocr/preprocessing/preflight.py::classify()`, wrap step 2 (`import paddle`) in `t0 = time.perf_counter_ns(); ...; paddle_import_ns = time.perf_counter_ns() - t0` and pass the rounded six-decimal seconds into the next `PreflightEvidence(...)` build via `paddle_import_seconds=`. Do the same around step 5's `paddle.device.set_device("gpu:0") + to_tensor(...)` block, recording `gpu_bind_probe_seconds`. Both fields must remain `None` on early-exit fail states (steps 1, 3, 4 fail-out paths). [R-015.2]
- [X] T007 In `src/dartwing_ocr/preprocessing/ocr.py`, add `_adopt_engine(engine: Any, device: str) -> None` that sets `_ENGINE`, `_ENGINE_DEVICE`, and `_PADDLE_SEEDED = True`. Document with a one-line comment: "Called by preflight.classify() to persist the step-6 engine into the runtime singleton (R-015.1 / CF5)." Export via `__all__` if needed by the test, otherwise leave module-private. [R-015.1 / data-model §CF5]
- [X] T008 In `src/dartwing_ocr/preprocessing/preflight.py::classify()`, modify the step-6 success branch: replace `_engine = PPStructureV3(...); del _engine` with `engine = PPStructureV3(...); from dartwing_ocr.preprocessing import ocr as _ocr_mod; _ocr_mod._adopt_engine(engine, "gpu:0")`. Keep the existing `start_ns` / `elapsed` timing of step 6 (this becomes `ppstructurev3_init_seconds` and feeds the `engine_init` phase). Do NOT change the `attempt_ppstructurev3_init=False` branch — that branch must NOT touch `ocr._ENGINE` (CF6). [R-015.1, CF5, CF6]
- [X] T009 In `src/dartwing_ocr/preprocessing/ocr.py`, replace the `_GPU_INFERENCE_NS_TOTAL: int` + `_GPU_INFERENCE_PAGES: int` module globals with `_GPU_INFERENCE_NS_BY_PAGE: list[tuple[int, int]] = []` (page_number, ns). Update `_record_gpu_inference_ns(ns: int)` to require a `page_number` arg and append. Add `take_gpu_inference_per_page() -> list[tuple[int, float]] | None` that drains the list, returning rounded-second tuples (None when empty). Keep `take_gpu_inference_seconds()` as a back-compat wrapper that sums the drained list (or returns None). [R-015.3]
- [X] T010 In `src/dartwing_ocr/preprocessing/ocr.py::run_page()`, change the per-page GPU timing capture to call `_record_gpu_inference_ns(page_number, time.monotonic_ns() - _gpu_start_ns)` (the page_number is already a parameter). Preserve all existing finally/exception ordering. [R-015.3]
- [X] T011 In `src/dartwing_ocr/pipeline/timing.py`, bump `SCHEMA_VERSION = "0.1.1"` → `SCHEMA_VERSION = "0.1.2"` and update the docstring comment to reference feature 015 / R-015.4. [R-015.4 / PT5]
- [X] T012 In `src/dartwing_ocr/pipeline/timing.py`, extend `build_per_document_success(...)` and `build_per_document_failure(...)` to accept two new keyword-only parameters: `phase_timings: dict[str, dict[str, float]] | None = None` and `per_page_inference: list[dict[str, Any]] | None = None`. When non-None, attach them to the returned dict under the same key names. Phases-not-performed are passed in as omitted dict keys (callers' responsibility per FR-016). [R-015.4 / R-015.5 / FP1, FP2]

**Checkpoint**: Engine reuse mechanics, preflight timing fields, per-page accumulator, and run_summary 0.1.2 carriers are all in place. T002 / T003 / T004 should now PASS for the Foundational scope. P1 stories can begin.

---

## Phase 3: User Story 1 — Single GPU run constructs PPStructureV3 once (Priority: P1) 🎯 MVP

**Goal**: a cold single-document `ppstructurev3@gpu` run constructs PPStructureV3 exactly once per process and emits a final `kind: "run_summary"` line carrying the new `phase_timings` + `per_page_inference` blocks alongside the legacy flat keys.

**Independent Test**: `python -m dartwing_ocr.preprocessing --document-folder tests/stage1_vendor_identity/inv_001_easy --preprocess-profile ppstructurev3@gpu` — assert PPStructureV3 constructor invoked exactly once, `preprocess_output.json` validates against contract set 1.2.0, `pipeline_version` ends in `.gpu0`, and the final stdout `run_summary` line has the expected `phase_timings` keys.

### Tests for User Story 1 (write FIRST, ensure FAIL before implementation)

- [X] T013 [P] [US1] Add `tests/preprocessing/test_single_doc_one_construction.py` (CF7 single-doc): use a `paddleocr.PPStructureV3` mock + counter; invoke `preprocessing.pipeline.run(Invocation(..., preprocess_lane="gpu0"))` once; assert constructor `call_count == 1`. Reset module state (`ocr._ENGINE = None`, `_ENGINE_DEVICE = None`, `_PADDLE_SEEDED = False`, `preflight._LAST_READOUT = None`) in setUp.
- [X] T014 [P] [US1] Add `tests/preprocessing/test_single_doc_run_summary_emission.py`: invoke the single-doc CLI subprocess against a stub-friendly fixture; capture stdout; assert exactly one final JSON line has `kind: "run_summary"`, `documents_total: 1`, `documents_succeeded: 1`, `preprocess_lane: "gpu0"`, `per_document[0].phase_timings` contains keys `{paddle_import, gpu_bind_probe, engine_init, rasterization, artifact_write, total}` (no `warmup`), and `per_document[0].per_page_inference` is a non-empty array of `{page: int, seconds: float}`. Mark with `@pytest.mark.gpu` so non-GPU CI skips.
- [X] T015 [P] [US1] Add `tests/preprocessing/test_single_doc_preprocess_output_unchanged.py` (CH1 / FR-010 / SC-003 four sub-criteria): assert that on a feature-015 GPU run on `inv_001_easy/source.pdf`: (a) `preprocess_output.json` validates against the active stage 1 contract set (1.2.0) — call `python -m dartwing_ocr.validator validate artifact <path> --kind preprocess_output` and assert exit 0; (b) `pipeline_version` ends in `.gpu0`; (c) `document_text` (assembled from text-bearing blocks) is non-empty; (d) the count of layout blocks across all pages is ≥ 3; AND (e) top-level keys equal exactly `{schema_version, contract_set_version, pipeline_version, document_id, source_file, pages, tables, quality, ingestion_sources, warnings}` — i.e., no `phase_timings`, no `per_page_inference`, no other timing additions.

### Implementation for User Story 1

- [X] T016 [US1] In `src/dartwing_ocr/preprocessing/pipeline.py::run()`, add an optional keyword-only parameter `stage_timing: StageTiming | None = None` (imported from `pipeline.timing`). When `None`, construct an internal `StageTiming(stage="preprocess")` to use locally. Wrap the rasterize loop in `with measure_phase(stage_timing, "rasterization"):`, the per-page `ocr.run_page` invocation already records GPU inference into `_GPU_INFERENCE_NS_BY_PAGE`; wrap `artifact_mod.validate_and_write(art, out_path)` in `with measure_phase(stage_timing, "artifact_write"):`. Wrap the entire body (after input validation) in `with measure_total(stage_timing):` so `total_ns` is always populated. Return type stays `Path` — caller reads phase data off the `stage_timing` it passed in. Sub-bullet — Runner contract: when `pipeline.run()` is invoked from `runner.run_plan(...)`, runner MUST pass its existing `result.timings.stages[Stage.PREPROCESS]` `StageTiming` instance as `stage_timing=` so the same channel powers single-doc and warm-corpus paths (closes U1). [FR-013 / FR-014]
- [X] T017 [US1] In `src/dartwing_ocr/preprocessing/cli.py`, the single-doc CLI must thread phase timing into the new `pipeline.run(stage_timing=…)` signature: (a) construct a `StageTiming(stage="preprocess")` and a placeholder for per-page entries; (b) call `pipeline.run(invocation, stage_timing=st)` (return is still `Path`); (c) drain `ocr.take_gpu_inference_per_page()` into `per_page_inference` (skip when CPU lane — see T033); (d) build a `phase_timings` dict by iterating `st.phases_ns.items()` and converting each `<key>` → `{<key>: {"seconds": round(ns/1e9, 6)}}`; add `total: {"seconds": round(st.total_ns/1e9, 6)}`; (e) on GPU lane only, attach the GPU one-time phase keys via the new `pipeline.timing.attach_one_time_gpu_phases(record, _LAST_READOUT)` helper (created in T027); (f) build a single-document `RunSummary` with `documents_total=1`, `documents_succeeded=1`, `preprocess_lane=<resolved lane>`, and one `per_document` entry via `build_per_document_success(..., phase_timings=…, per_page_inference=…)`; (g) emit it via `pipeline.timing.emit_run_summary(summary)` as the final stdout JSON line. [R-015.6 / FR-014]
- [X] T018 [US1] In `src/dartwing_ocr/preprocessing/cli.py`, on GPU-prereq failure (caught `GpuPrerequisiteError`), preserve the existing FR-009 stderr emission AND additionally emit a partial `RunSummary` with `documents_total=1`, `documents_succeeded=0`, `documents_failed=1`, and a single `per_document` failure entry built via `build_per_document_failure(...)` carrying whatever `phase_timings` were captured before the failure (typically just `paddle_import` if step 1 ran, or empty). [Q5 / FP1 / R-015.6]

**Checkpoint**: User Story 1 is functional — single-doc GPU runs construct PPStructureV3 once and emit phase timings. T013, T014, T015 PASS. The MVP slice is shippable.

---

## Phase 4: User Story 2 — Warm corpus run reuses one engine (Priority: P1)

**Goal**: a `ppstructurev3@gpu` run over ≥ 2 documents in one process constructs PPStructureV3 exactly once across the whole corpus and reports init/warmup phases on the first document only.

**Independent Test**: provide a documents-file with two known-good PDFs, invoke the warm-corpus driver, assert (a) PPStructureV3 constructor `call_count == 1` across the whole run, (b) doc 0's `phase_timings` contains the GPU one-time keys, (c) doc 1's `phase_timings` does NOT contain those keys, (d) both docs have `per_page_inference` arrays.

### Tests for User Story 2 (write FIRST)

- [X] T019 [P] [US2] Add `tests/pipeline/test_warm_corpus_one_init.py` (SC-001 / SC-002 / CF7 corpus): mock `paddleocr.PPStructureV3` with a counter; invoke `corpus_run.run_warm_corpus(...)` over a 2-document fixture list; assert constructor `call_count == 1`. Then parse the captured stdout, locate the `kind: "run_summary"` line, assert `per_document[0].phase_timings` contains `paddle_import`, `gpu_bind_probe`, `engine_init`, while `per_document[1].phase_timings` does NOT contain any of those three keys. Both per_document entries must contain `rasterization`, `artifact_write`, `total`, and a non-empty `per_page_inference`. Mark `@pytest.mark.gpu`.
- [X] T020 [P] [US2] Add `tests/pipeline/test_failure_phase_timings.py` (FP1 / FP2 / Q5): drive a 2-document corpus where doc 0 succeeds and doc 1 fails inference on its second page (use a mock that raises `RuntimeError` on the third `engine.predict` call). Assert: (a) `per_document[1].status == "failure"`; (b) `per_document[1].phase_timings` contains `rasterization`, `total` and a partial `per_page_inference` with exactly one entry (`page: 1`); (c) `per_document[1].phase_timings` does NOT contain `artifact_write` (page 2 raised before write); (d) `per_document[1]` does NOT contain any of the GPU one-time keys (those only attach to doc 0).

### Implementation for User Story 2

- [X] T021 [US2] In `src/dartwing_ocr/pipeline/corpus_run.py`, replace the existing per-document `success_record` build to thread the new shape: after `runner.run_plan(...)` returns success, read `result.timings.stages[Stage.PREPROCESS].phases_ns` (now populated by T016's `measure_phase` wrappers, which Runner forwards via the StageTiming Runner already owns — see T016 sub-bullet); convert each `<key>` → `{<key>: {"seconds": round(ns/1e9, 6)}}` to build `phase_timings`. Add `total: {"seconds": round(result.timings.stages[PREPROCESS].total_ns/1e9, 6)}`. Drain `ocr.take_gpu_inference_per_page()` into `per_page_inference` (skip when CPU lane — see T032 gate). Pass both into `build_per_document_success(...)`. [R-015.4 / FR-013 / FR-014]
- [X] T022 [US2] In `src/dartwing_ocr/pipeline/corpus_run.py`, after the per-document loop ends, replace the existing first-doc `gpu_init_seconds`-attachment block with the new structured form: when `_resolved_preprocess_lane.startswith("gpu")` and `_PREFLIGHT_READOUT` is not None, locate the FIRST per-document entry whose `status == "success"` and add three new keys to its `phase_timings`: `paddle_import: {seconds: <_PREFLIGHT_READOUT.evidence.paddle_import_seconds>}`, `gpu_bind_probe: {seconds: <_PREFLIGHT_READOUT.evidence.gpu_bind_probe_seconds>}`, `engine_init: {seconds: <_PREFLIGHT_READOUT.evidence.ppstructurev3_init_seconds>}`. Skip any whose source value is None (FR-016 omission). Preserve the existing legacy `gpu_init_seconds` flat-key attachment (back-compat). [FR-015 / SC-002 / R-015.4]
- [X] T023 [US2] In `src/dartwing_ocr/pipeline/corpus_run.py`'s failure path (`if result.exit_code != ExitCode.SUCCESS:` branch), thread `phase_timings` and `per_page_inference` into `build_per_document_failure(...)` exactly like the success path: read `result.timings.stages[Stage.PREPROCESS].phases_ns` (which under `measure_phase` semantics records whatever phases ran — including the one in which the failure occurred — but does NOT register keys for phases that never started); convert each into `{<key>: {"seconds": round(ns/1e9, 6)}}` and add `total`. Drain `ocr.take_gpu_inference_per_page()` for whatever pages completed (gate on GPU lane per T032). Phases not started MUST be absent from the dict, not zeroed (FR-016 / FP2). [Q5 / FP1 / FP2]
- [X] T024 [US2] In `src/dartwing_ocr/pipeline/corpus_run.py`, in `_emit_warm_init_failure_summary(...)`, extend the constructed failure `per_document` entry with whatever partial GPU phase timings were captured (e.g., `paddle_import` from `_PREFLIGHT_READOUT.evidence` when step 1 ran). Match the same omission rule. [Q5 / FP1]

**Checkpoint**: User Story 2 is functional — warm corpus reuses one engine, first-doc/subsequent-doc rule holds, failure-path partial timings work. T019, T020 PASS.

---

## Phase 5: User Story 3 — Phase timing explains remaining latency (Priority: P1)

**Goal**: every preprocessing run (single-doc or corpus) surfaces the FR-013 phase set in the run_summary stdout line, and a reader can identify the slowest phase from the output alone (SC-005).

**Most of US3's work landed in Phases 2–4** (the schema bump, the phase_timings carriers, the wiring in single-doc and corpus paths). US3's own phase covers the cross-cutting **observability requirements** that don't belong to one source code site: the schema-shape regression test, the consistency check between FR-013's bulleted list and the actually-emitted keys, and the quickstart "slowest phase" smoke.

**Independent Test**: invoke any successful `ppstructurev3@gpu` run, parse the run_summary line, and pipe through the quickstart §"Identifying the slowest phase" snippet — output must list each FR-013 phase with a numeric seconds value and a sortable order.

### Tests for User Story 3 (write FIRST)

- [X] T025 [P] [US3] Extend `tests/pipeline/test_run_summary_schema_0_1_2.py` (created in T004) with two more cases tied to US3 specifically: (a) PT3 — `per_document[0].per_page_inference[*].page` strictly increasing and 1-based; (b) Consistency — the SET of `phase_timings` keys present on a successful first-doc GPU run is a subset of the FR-013 vocabulary `{paddle_import, gpu_bind_probe, engine_init, warmup, rasterization, artifact_write, total}` and a superset of `{paddle_import, gpu_bind_probe, engine_init, rasterization, artifact_write, total}` (warmup absent per Q2; rest required).
- [X] T026 [P] [US3] Add `tests/pipeline/test_slowest_phase_identifiable.py` (SC-005): run a stub-driven 1-doc subprocess; parse the `run_summary` line; sort `phase_timings.items()` by `seconds` desc; assert the top item's `seconds > 0` and that the operation succeeded. This is a smoke-grade assertion — the goal is to prove the data shape supports the SC-005 reader-experience requirement, not to assert which phase is actually slowest.

### Implementation for User Story 3

- [X] T027 [US3] In `src/dartwing_ocr/pipeline/timing.py`, add a small helper `attach_one_time_gpu_phases(record: dict, readout: PreflightReadout) -> None` that reads `readout.evidence.{paddle_import_seconds, gpu_bind_probe_seconds, ppstructurev3_init_seconds}` and inserts them into `record["phase_timings"]` under the structured form (omitting any whose source value is None). Refactor T022 and T017 to use this helper instead of duplicating the dict construction. Pure refactor — no behavior change beyond DRY. [R-015.4]
- [X] T028 [US3] In `src/dartwing_ocr/preprocessing/pipeline.py`, ensure that on **every** rasterize-failure path (a page raster failure that returns a `PageRasterFailure` sentinel), the per-document `rasterization` phase timer (the `measure_phase(stage_timing, "rasterization")` block introduced in T016) still ticks for the time spent up to the failure. Validate by inspection that the existing `for pr in rasters:` loop's exception handling does not exit the `measure_phase` context prematurely (the context manager's `finally` clause already handles the exception path correctly per `pipeline/timing.py::measure_phase`). [FR-016 / FP2]
- [X] T029 [US3] Sanity-check that `specs/015-gpu-engine-reuse-timing/quickstart.md` "Identifying the slowest phase" snippet runs end-to-end. Pass criterion: the Python one-liner exits 0, prints exactly one `slowest phases:` header followed by ≥ 5 `<phase>: <seconds>` lines (matching the expected FR-013 phase set minus the omitted warmup), and one `per-page inference:` header followed by ≥ 1 `page <N>: <seconds>` line. If the snippet needs adjustment for the actual emitted shape, edit the snippet (no code change). [SC-005]

**Checkpoint**: User Story 3 is functional — every successful run emits the FR-013 phase set, the data shape supports SC-005, and the quickstart's slowest-phase recipe works.

---

## Phase 6: User Story 4 — CPU and stub paths pay no GPU cost (Priority: P2)

**Goal**: `ppstructurev3@cpu` and stub-adapter runs emit no GPU phase keys, no GPU bind probe, and no GPU readiness probe. Default test suite continues to pass on a host without GPU.

**Independent Test**: run `pytest` (default suite) on a host without GPU; assert exit 0 and that GPU-marked tests are skipped, not failed. Run a `ppstructurev3@cpu` smoke and confirm `per_document[0].phase_timings` ⊆ `{rasterization, artifact_write, total}` and `per_page_inference` is absent.

### Tests for User Story 4 (write FIRST)

- [X] T030 [P] [US4] Add `tests/pipeline/test_cpu_lane_no_gpu_phase_keys.py` (ISO1 / SC-006 / FR-009): drive a corpus run with NO `--preprocess-profile` argument (default-profile path); parse the `run_summary` line; assert (a) `preprocess_lane == "cpu"` (FR-009 default-profile invariant), (b) for every `per_document` entry, `phase_timings.keys() ⊆ {"rasterization","artifact_write","total"}`, (c) `per_page_inference` key is absent on every entry. Then add a second case driving the run with explicit `--preprocess-profile ppstructurev3@cpu` and assert the same shape (explicit-CPU path matches default).
- [X] T031 [P] [US4] Add `tests/pipeline/test_default_suite_passes_without_gpu.py` (SC-008): use `subprocess.run(["pytest","-q","--collect-only"], …)` on a `gpu`-less environment shim; assert that `gpu`-marked tests are reported as `skipped` and that the collection exit code is 0. The actual full suite is run by CI; this test guards the marker plumbing. (If this becomes flaky in subprocess form, downgrade to a unit-style assertion that imports `tests.conftest` and inspects the marker registration.)

### Implementation for User Story 4

- [X] T032 [US4] In `src/dartwing_ocr/pipeline/corpus_run.py`'s success-path attachment (T021), explicitly gate the `per_page_inference` emission on `_resolved_preprocess_lane.startswith("gpu")`. CPU runs MUST drain `ocr.take_gpu_inference_per_page()` (always — to avoid leaking state) but MUST NOT attach the result to the per-document record. Same gate applies in T023 (failure path). [FR-017 / ISO1]
- [X] T033 [US4] In `src/dartwing_ocr/preprocessing/cli.py` (T017), gate the `paddle_import` / `gpu_bind_probe` / `engine_init` attachment via the same `lane.startswith("gpu")` check; CPU lane omits all four GPU one-time keys. [FR-017]
- [X] T034 [US4] Audit `tests/conftest.py` to confirm the existing `gpu` pytest marker correctly skips GPU-only tests when no GPU is available. If new tests added in earlier phases (T013, T014, T019, T020, T026, T030) need the marker, ensure each has `@pytest.mark.gpu` or is structured so it does not require GPU hardware (e.g., uses constructor mocks). [FR-019 / SC-008]

**Checkpoint**: User Story 4 is functional — CPU/stub paths emit no GPU phase keys, default suite passes without GPU. T030, T031 PASS.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: cross-cutting verifications, fail-fast budget regression, back-compat checks, doc updates.

- [X] T035 [P] Add `tests/preprocessing/test_fail_fast_budget.py` (FF1 / SC-007 / FR-008): use `subprocess.run([... preprocessing CLI ...])` on a host with no GPU (or with `HIP_VISIBLE_DEVICES=""` to force `GPU_NOT_EXPOSED`); measurement boundary per spec §SC-007 = OS exec to first non-zero exit. Record `t0 = time.perf_counter()` immediately before `subprocess.run(...)` and `t1 = time.perf_counter()` immediately after it returns; assert `(t1 - t0) < 10.0`. Exit code MUST be one of {10, 11, 12, 13, 14}. Assert (a) no `preprocess_output.json` whose `pipeline_version` ends in `.gpu0` was written by this run, AND (b) FR-008 silent-fallback guard — no `preprocess_output.json` whose `pipeline_version` ends in `.cpu0` was written either (silent fallback to CPU is forbidden). The simplest way: assert the fixture document folder contains no `preprocess_output.json` newer than `t0`. Do not mark `@pytest.mark.gpu` — this test must run on GPU-less hosts.
- [X] T036 [P] Add `tests/pipeline/test_legacy_flat_keys_preserved.py` (R-015.4 back-compat): drive a feature-015 corpus run; parse `run_summary`; for every successful per_document entry assert that `stages.preprocess.total_seconds`, `stages.preprocess.gpu_init_seconds` (first doc only), and `stages.preprocess.gpu_inference_seconds` are still emitted (the legacy keys must coexist with the new structured form for one schema version). [Plan §Constitution Check II]
- [X] T037 [P] Add `tests/preprocessing/test_legacy_take_gpu_inference_seconds.py`: confirm the legacy `ocr.take_gpu_inference_seconds()` helper still returns the SUM of seconds across drained pages (back-compat for any external caller that built against feature 014 directly). [R-015.3]
- [X] T038 Update `specs/015-gpu-engine-reuse-timing/checklists/release-gate.md` — pass over the 52 items, mark `[x]` for any whose underlying spec language is now precise enough; record any remaining `[Gap]` / `[Conflict]` / `[Ambiguity]` items in the "Deferred items" section at the bottom with one-line rationale.
- [ ] T039 Run the full `quickstart.md` walkthrough (Smoke 1 single-doc GPU, Smoke 2 warm corpus, Smoke 3 fail-fast on GPU-less, Smoke 4 CPU isolation, "Identifying the slowest phase" recipe). Record any deviations from documented expected outputs in the worktree under `specs/015-gpu-engine-reuse-timing/notes-quickstart-run.md` (creating the file is OK; do NOT commit if everything matches the documented expectations).
- [X] T040 Verify `pyproject.toml` is unchanged (no new pinned dependencies — see plan.md Technical Context). If feature work has accidentally introduced a dependency, justify or back out.
- [ ] T041 Run `pytest -m "not gpu" -q` and `pytest -m gpu -q` (the second only on the workstation host with `.venv-paddle-rocm` active). Both must report all-pass / all-skip-when-marked. Capture the wall-clock of the warm-corpus GPU smoke for the quickstart's reference output. [SC-008]
- [X] T042 [P] Verify FR-011 corpus baseline preservation. Run `git status --porcelain tests/stage1_vendor_identity/` from the worktree root and assert the output is empty (no committed-corpus files modified or staged by this feature). Additionally, `git log --oneline tests/stage1_vendor_identity/ ^main` MUST show no commits introduced on this feature branch that touch the corpus directory. If either check fails, investigate which task introduced the change and revert (corpus changes belong to feature 006 or the dataset-rebuild flow, not feature 015). [FR-011]

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: trivial — no blockers.
- **Phase 2 (Foundational)**: blocks ALL user stories. Must complete before any of US1/US2/US3/US4 begins.
- **Phase 3 (US1)**: depends on Phase 2.
- **Phase 4 (US2)**: depends on Phase 2 — independent of US1, but US2's tests assert the same engine-reuse invariant, so running US1 first surfaces single-doc bugs cheaper.
- **Phase 5 (US3)**: depends on US1 + US2 implementations (not just Phase 2) because T025/T026 verify the actually-emitted phase sets from both single-doc and corpus paths.
- **Phase 6 (US4)**: depends on Phase 2 — independent of US1/US2/US3 (CPU/stub path doesn't exercise the GPU code).
- **Phase 7 (Polish)**: depends on US1+US2+US3+US4 substantively complete.

### Within each user story

- Tests are written FIRST and MUST FAIL before the corresponding implementation tasks land (project convention).
- File-level dependencies inside a story are documented inline in each task; tasks marked `[P]` touch different files and may run in parallel.

### Parallel opportunities

- All Foundational tests (T002, T003, T004) can run in parallel — different files.
- T005 vs. T009 — different files (preflight.py vs. ocr.py); independent within Phase 2.
- T013, T014, T015 — different test files, [P].
- T019, T020 — different test files, [P].
- T025, T026 — different test files, [P].
- T030, T031 — different test files, [P].
- T035, T036, T037, T042 — different test files / process checks, [P].
- US1 and US2 implementations touch overlapping files (`corpus_run.py` for US2, `preprocessing/cli.py` and `preprocessing/pipeline.py` for US1) — internally sequential. US4 is wholly independent.

---

## Parallel Example: Foundational Tests

```bash
# Launch the three foundational test scaffolds together:
Task: "Add tests/preprocessing/test_preflight_engine_persistence.py per T002"
Task: "Add tests/preprocessing/test_phase_timings_unit.py per T003"
Task: "Add tests/pipeline/test_run_summary_schema_0_1_2.py per T004"

# After T005–T012 land in their owning files, all three test files should pass.
```

## Parallel Example: User Story 4 (CPU/Stub Isolation)

```bash
# US4 has no source-code dependency on US1/US2/US3 — its implementation tasks T032–T034
# can be staffed in parallel with US1's T016–T018 once Phase 2 is complete.
Developer A: T013 → T014 → T015 → T016 → T017 → T018      (US1 lane)
Developer B: T030 → T031 → T032 → T033 → T034              (US4 lane)
```

---

## Implementation Strategy

### MVP First (US1 only, the dedupe + single-doc emission)

1. Phase 1: Setup (T001 — confirmation only).
2. Phase 2: Foundational (T002–T012). Foundational tests fail; foundational implementation tasks land; tests pass.
3. Phase 3: User Story 1 (T013–T018). Single-doc GPU run constructs PPStructureV3 once and emits the new structured run_summary line.
4. **STOP and VALIDATE**: run `pytest -m gpu tests/preprocessing/test_single_doc_one_construction.py tests/preprocessing/test_single_doc_run_summary_emission.py -v`. The MVP is shippable as the engine-dedupe + single-doc observability slice.

### Incremental Delivery

1. Setup + Foundational ⇒ shared infrastructure ready.
2. US1 ⇒ single-doc engine reuse + observability (MVP).
3. US2 ⇒ corpus engine reuse + per-document first-doc/steady-state rule.
4. US3 ⇒ cross-cutting observability tests + quickstart recipe (largely a verification phase given Phase 2/3/4 did the data-flow work).
5. US4 ⇒ CPU/stub isolation + default-suite green on GPU-less hosts.
6. Polish ⇒ fail-fast budget + back-compat + quickstart walkthrough.

### Stopping points (ship-ready checkpoints)

- After US1: dedupe-only slice. Single-doc run shows the win on `inv_001_easy/source.pdf`.
- After US2: corpus slice. Warm-corpus operator gets the warm-CPU-equivalent on GPU.
- After US3: full FR-013 observability surface available across both modes.
- After US4: production-safe (CI green on GPU-less).
- After Polish: release-grade.

---

## Notes

- `[P]` tasks edit different files and have no dependency on incomplete tasks.
- `[Story]` label maps each story-phase task to spec.md user stories US1/US2/US3/US4. Setup, Foundational, and Polish phases carry no story label.
- Tests are written FIRST in each story phase; commit the failing test, then commit the implementation that makes it pass.
- After each commit, run `pytest -m "not gpu" -q` to ensure the default suite stays green.
- GPU-only tests (`@pytest.mark.gpu`) run on the workstation host with `.venv-paddle-rocm` active; CI without GPU hardware skips them.
- The release-gate checklist (`checklists/release-gate.md`) is a separate concern — pass over it before opening the PR.
- Avoid: reordering existing flat run_summary keys, changing `preprocess_output.json` schema, adding new dependencies to `pyproject.toml`, introducing new stdout `kind` values, or implementing a synthetic warmup pass (Q2 explicit).
