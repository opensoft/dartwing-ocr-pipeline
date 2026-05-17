# Module Invariants: `preprocessing/warmup.py` and Wiring Sites

**Feature**: 016-gpu-warmup-miopen-cache
**Decision source**: spec FR-001, FR-003, FR-004, FR-005, FR-007, FR-009, FR-011, FR-018, FR-020; research.md R-016.6, R-016.7, R-016.8, R-016.10.

These invariants govern the warmup pass and its interaction with the existing preprocessing / pipeline machinery. They are stable across the lifetime of feature 016 and are how tests in `tests/unit/preprocessing/test_warmup_unit.py` and `tests/pipeline_tests/test_warmup_*.py` (the latter `@gpu`-marked, deferred per FR-014) express their assertions.

## I-1. One warmup pass per process

The body of `preprocessing.warmup.run_warmup()` is guarded by a module-level `_WARMUP_RAN: bool = False` flag (R-016.10). The first call sets it `True` after `engine.predict(...)` returns; every subsequent call returns the cached `WarmupResult` without re-invoking `engine.predict` and without re-applying env-var defaults.

**Asserted by**: `tests/unit/preprocessing/test_warmup_unit.py::test_run_warmup_calls_predict_exactly_once_then_caches`.

## I-2. No second engine ever

`preprocessing.warmup.run_warmup()` MUST receive an already-constructed `paddleocr.PPStructureV3` instance via its `engine` parameter and MUST NOT call `PPStructureV3(...)` itself. It also MUST NOT touch `ocr._ENGINE` or `ocr._ENGINE_DEVICE` (the singleton is the caller's contract, not warmup's). Callers MUST pass `ocr._get_engine(device="gpu:0")` or equivalent — never `PPStructureV3()` directly.

**Asserted by**: `tests/pipeline_tests/test_warmup_engine_reuse.py @gpu` (deferred per FR-014) checks `id(engine_before) == id(engine_after)` and that `PPStructureV3.__init__` was called exactly once across the run (preserves feature 015 SC-001 / FR-001).

## I-3. Strict ordering: post-adopt, pre-first-doc, OUTSIDE measure_total

The three wiring sites — `preprocessing/cli.py` (single-doc), `pipeline/cli.py::_run_cold` (cold pipeline), and `pipeline/corpus_run.py` (warm corpus) — MUST invoke warmup **after** the engine-adoption step succeeds and **before** any per-document `measure_total` / `measure_phase("rasterization")` call (R-016.10). Per Copilot PR #24 round 3 / FR-007 / SC-004, warmup MUST also run **outside** the caller's `measure_total(stage_timing)` window so its duration is excluded from `phase_timings.total.seconds`. The single-doc and cold-pipeline paths use the hoisted `pipeline.run_warmup_if_active(...)` helper (which calls `ensure_gpu_ready()` then `run_warmup(get_active_engine())`) BEFORE entering any timing wrapper. The warm-corpus path adopts the engine via `_warm_initialize_live_preprocess` and then invokes `run_warmup` inline before the per-document loop opens. The runner (`pipeline/runner.py`) does NOT itself drive warmup — it only translates `WarmupError` to `ExitCode.WARMUP_FAILED` if one were to bubble up via a stage callable.

**Asserted by**: `tests/pipeline_tests/test_warmup_engine_reuse.py @gpu` (deferred per FR-014) checks ordering via timestamps captured during the run; `tests/pipeline_tests/test_warmup_first_doc_exclusion.py @gpu` (deferred) checks the per-doc phase timings exclude warmup (SC-004).

## I-4. Warmup time NEVER folded into per-document phases

The warmup `perf_counter` window MUST NOT be inside any of these context managers / accumulators:

- `phase_timings.total` (the document-level total)
- `phase_timings.rasterization`
- `phase_timings.per_page_inference[*].seconds` (the per-page list)
- `phase_timings.artifact_write`
- legacy flat keys `stages.preprocess.{total_seconds, gpu_init_seconds, gpu_inference_seconds}` (FR-009)

Implementation guarantee: `run_warmup` opens its own `perf_counter` window inside its body; it is not nested inside any `pipeline/timing.measure_*` context manager. The wiring sites in `runner.py` / `corpus_run.py` invoke `run_warmup` **before** entering any `measure_total`/`measure_phase` block, satisfying I-3.

**Asserted by**: `tests/pipeline_tests/test_warmup_first_doc_exclusion.py @gpu` (SC-004, deferred per FR-014); `tests/unit/preprocessing/test_warmup_unit.py::test_run_warmup_returns_seconds_only_via_warmup_result` (CPU-safe, with stub engine — surface contract that warmup seconds flow only through `WarmupResult` rather than any caller dict).

## I-5. Fail-fast surface

When `engine.predict(...)` (or the fixture loader, or the clock anomaly check) raises any exception, `run_warmup` catches it and re-raises as `WarmupError(message=str(exc), cause_class=<taxonomy>, cause_module=<original_module>)`. The cause-class taxonomy is in data-model.md § WarmupError. Callers (`corpus_run.py`, `runner.py`) catch `WarmupError` at the same boundary they already catch `GpuPrerequisiteError`:

1. Print to stderr: `error: warmup failed: <cause_class>: <message>`
2. Exit with code 15 (cli-contract.md § 4)
3. Emit no `run_summary`
4. Write no `preprocess_output.json` for any document that would have been timed after the failed warmup
5. Do NOT silently downgrade to a no-warmup run (FR-007 / SC-011)

**Asserted by**: `tests/pipeline_tests/test_warmup_failure_path.py @gpu` (deferred per FR-014) and the CPU-safe taxonomy + wrap variants in `tests/unit/preprocessing/test_warmup_unit.py` (`test_warmup_error_wraps_unknown_failure`, `test_warmup_error_routes_paddle_failure_to_paddle_error`, `test_warmup_error_routes_miopen_failure_to_miopen_error`, `test_warmup_error_routes_comgr_failure_to_miopen_error`, `test_warmup_error_does_not_set_warmup_ran_flag`).

## I-6. CPU/stub isolation

`preprocessing.warmup` MUST NOT be imported on the CPU or stub code path. The import line lives inside the `if device.startswith("gpu") and warmup_opt_in:` branch in both wiring sites. A host without `paddleocr` / `paddlepaddle-dcu` / ROCm MUST be able to:

- Run `python -m dartwing_ocr.preprocessing --preprocess-profile=ppstructurev3@cpu --gpu-warmup ...` and exit cleanly (warn-and-proceed; cli-contract.md § 3 row 5).
- Run the default test suite (`pytest -m "not gpu"`) without a single `import paddle` or `import miopen` happening.

**Asserted by**: `tests/unit/preprocessing/test_warmup_cpu_no_op.py` (CPU-safe; FR-010 / FR-011 / SC-006 / SC-007). The strong-form import-attempt check in `test_cpu_warmup_optin_emits_stderr_warning_and_no_warmup_pass` patches `builtins.__import__` to detect any attempt to load `preprocessing.warmup` regardless of whether the module is already cached in `sys.modules` (Copilot PR #24 round 5).

## I-7. Env-var defaults are scoped to GPU warmup path

The four env vars from data-model.md § "Default env-var configuration" are set ONLY inside the GPU branch of `run_warmup`. They MUST NOT be applied:

- on CPU/stub paths (even when `DARTWING_GPU_WARMUP=1` is set globally — those paths warn-and-proceed without setting env vars per FR-010);
- before `run_warmup` is invoked (so the rest of the process starts with whatever the operator set);
- after `run_warmup` returns, *unsetting* anything (operator-set values persist; defaults persist for the rest of the process).

**Asserted by**: `tests/unit/preprocessing/test_warmup_cpu_no_op.py::test_cpu_warmup_optin_does_not_mutate_miopen_env` and `tests/unit/preprocessing/test_warmup_unit.py::test_run_warmup_preserves_operator_set_env`.

## I-8. Determinism of warmup input

`run_warmup`'s default fixture path resolves to `tests/stage1_vendor_identity/inv_001_easy/source.pdf` (R-016.2), or to the path given in the `DARTWING_WARMUP_FIXTURE_PATH` env var when set (operator-side override for installed-distribution use, per Copilot PR #24 round 4). The fixture is rasterized through `preprocessing.rasterize.rasterize_page(...)` at the same DPI the active preprocess profile uses (300 DPI for `ppstructurev3@gpu`). The PIL image bytes are sha256'd; the digest is stored in `WarmupResult.fixture_sha256` for diagnostics. If the digest changes between two runs that supposedly used the same fixture, that's an integrity bug — `tests/unit/preprocessing/test_warmup_unit.py::test_fixture_digest_stable_across_invocations` pins the digest.

## I-9. Schema_version codebase-level bump

The `SCHEMA_VERSION` literal in `pipeline/timing.py` MUST be `"0.1.3"` for every run of the new binary, regardless of opt-in state (R-016.9 / FR-008 / /speckit.clarify Q2). Asserted by `tests/pipeline_tests/test_run_summary_schema_0_1_3.py::test_schema_version_is_0_1_3_codebase_level` and `tests/pipeline_tests/test_run_summary_schema_0_1_2.py::test_pt5_schema_version_is_current_chain_head` (the version-chain invariant).

## I-10. Byte-identical `preprocess_output.json`

Two runs of `python -m dartwing_ocr.preprocessing --preprocess-profile=ppstructurev3@gpu <doc>`, one with `--gpu-warmup` and one without, MUST produce a byte-identical `preprocess_output.json`. Verified by sha256 equality. This is the strongest contract this feature owes to the corpus baselines (FR-018 / SC-008). Asserted by `tests/pipeline_tests/test_warmup_engine_reuse.py @gpu` (deferred per FR-014 — see issue #23).

## I-11. Joint presence of first-doc one-time GPU phases

The four "first-doc one-time GPU phase" keys — `paddle_import`, `gpu_bind_probe`, `engine_init`, and `warmup` — are attached by the SAME `attach_one_time_gpu_phases(record, readout, *, warmup_seconds=...)` helper (R-016.8). On a successful warmup-enabled `ppstructurev3@gpu` run, all four are present together on the first successful per-doc entry; on a successful warmup-DISABLED `ppstructurev3@gpu` run, the first three are present together (and `warmup` is absent); on a CPU/stub run, all four are absent together. The contract is **joint**: tests asserting any one of the four MAY assume the helper attached them as a coherent set in the relevant scenario. Individual keys MAY still be absent within the coherent set if their underlying source value was `None` (per feature 015 FR-016 — e.g., if `paddle_import` was not measured because paddle was preloaded by an earlier in-process step), but the helper itself never partially attaches the warmup-vs-non-warmup split. **Asserted by**: `tests/pipeline_tests/test_run_summary_schema_0_1_3.py::test_warmup_attaches_alongside_one_time_phases` (CPU-safe via stub-injected `warmup_seconds`) and `tests/pipeline_tests/test_warmup_engine_reuse.py @gpu` for the live GPU case (deferred per FR-014).
