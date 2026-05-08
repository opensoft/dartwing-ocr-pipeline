# Module Invariants: `preprocessing/warmup.py` and Wiring Sites

**Feature**: 016-gpu-warmup-miopen-cache
**Decision source**: spec FR-001, FR-003, FR-004, FR-005, FR-007, FR-009, FR-011, FR-018, FR-020; research.md R-016.6, R-016.7, R-016.8, R-016.10.

These invariants govern the warmup pass and its interaction with the existing preprocessing / pipeline machinery. They are stable across the lifetime of feature 016 and are how tests in `tests/preprocessing/test_warmup_unit.py` and `tests/pipeline/test_warmup_*.py` express their assertions.

## I-1. One warmup pass per process

The body of `preprocessing.warmup.run_warmup()` is guarded by a module-level `_WARMUP_RAN: bool = False` flag (R-016.10). The first call sets it `True` after `engine.predict(...)` returns; every subsequent call returns the cached `WarmupResult` without re-invoking `engine.predict` and without re-applying env-var defaults.

**Asserted by**: `test_warmup_unit.py::test_run_warmup_called_twice_returns_cached_no_predict_recall`.

## I-2. No second engine ever

`preprocessing.warmup.run_warmup()` MUST receive an already-constructed `paddleocr.PPStructureV3` instance via its `engine` parameter and MUST NOT call `PPStructureV3(...)` itself. It also MUST NOT touch `ocr._ENGINE` or `ocr._ENGINE_DEVICE` (the singleton is the caller's contract, not warmup's). Callers MUST pass `ocr._get_engine(device="gpu:0")` or equivalent — never `PPStructureV3()` directly.

**Asserted by**: `test_warmup_engine_reuse.py @gpu` checks `id(engine_before) == id(engine_after)` and that `PPStructureV3.__init__` was called exactly once across the run (preserves feature 015 SC-001 / FR-001).

## I-3. Strict ordering: post-adopt, pre-first-doc

The wiring sites in `pipeline/corpus_run.py` and `pipeline/runner.py` MUST invoke `run_warmup` **after** the engine-adoption step succeeds and **before** any per-document `measure_total` / `measure_phase("rasterization")` call. Concretely (see R-016.10 for line-level placement): in `corpus_run.py` immediately after the `if warm_init_failure is not None:` early-return block and before the `for entry in documents:` loop; in `runner.py` after the equivalent engine-adoption step succeeds and before the first stage's `measure_total(timing)`.

**Asserted by**: `test_warmup_engine_reuse.py @gpu` checks ordering via timestamps captured during the run; `test_warmup_first_doc_exclusion.py @gpu` checks the per-doc phase timings exclude warmup (SC-004).

## I-4. Warmup time NEVER folded into per-document phases

The warmup `perf_counter` window MUST NOT be inside any of these context managers / accumulators:

- `phase_timings.total` (the document-level total)
- `phase_timings.rasterization`
- `phase_timings.per_page_inference[*].seconds` (the per-page list)
- `phase_timings.artifact_write`
- legacy flat keys `stages.preprocess.{total_seconds, gpu_init_seconds, gpu_inference_seconds}` (FR-009)

Implementation guarantee: `run_warmup` opens its own `perf_counter` window inside its body; it is not nested inside any `pipeline/timing.measure_*` context manager. The wiring sites in `runner.py` / `corpus_run.py` invoke `run_warmup` **before** entering any `measure_total`/`measure_phase` block, satisfying I-3.

**Asserted by**: `test_warmup_first_doc_exclusion.py @gpu` (SC-004); `test_warmup_unit.py::test_warmup_does_not_modify_caller_phase_timings` (CPU-safe, with stub engine).

## I-5. Fail-fast surface

When `engine.predict(...)` (or the fixture loader, or the clock anomaly check) raises any exception, `run_warmup` catches it and re-raises as `WarmupError(message=str(exc), cause_class=<taxonomy>, cause_module=<original_module>)`. The cause-class taxonomy is in data-model.md § WarmupError. Callers (`corpus_run.py`, `runner.py`) catch `WarmupError` at the same boundary they already catch `GpuPrerequisiteError`:

1. Print to stderr: `error: warmup failed: <cause_class>: <message>`
2. Exit with code 15 (cli-contract.md § 4)
3. Emit no `run_summary`
4. Write no `preprocess_output.json` for any document that would have been timed after the failed warmup
5. Do NOT silently downgrade to a no-warmup run (FR-007 / SC-011)

**Asserted by**: `test_warmup_failure_path.py @gpu` (and a CPU-safe injection variant in `test_warmup_unit.py::test_warmup_predict_raises_wraps_to_warmup_error`).

## I-6. CPU/stub isolation

`preprocessing.warmup` MUST NOT be imported on the CPU or stub code path. The import line lives inside the `if device.startswith("gpu") and warmup_opt_in:` branch in both wiring sites. A host without `paddleocr` / `paddlepaddle-dcu` / ROCm MUST be able to:

- Run `python -m ledgerlinc_ocr.preprocessing --preprocess-profile=ppstructurev3@cpu --gpu-warmup ...` and exit cleanly (warn-and-proceed; cli-contract.md § 3 row 5).
- Run the default test suite (`pytest -m "not gpu"`) without a single `import paddle` or `import miopen` happening.

**Asserted by**: `test_warmup_cpu_no_op.py` (CPU-safe; FR-010 / FR-011 / SC-006 / SC-007).

## I-7. Env-var defaults are scoped to GPU warmup path

The four env vars from data-model.md § "Default env-var configuration" are set ONLY inside the GPU branch of `run_warmup`. They MUST NOT be applied:

- on CPU/stub paths (even when `LEDGERLINC_GPU_WARMUP=1` is set globally — those paths warn-and-proceed without setting env vars per FR-010);
- before `run_warmup` is invoked (so the rest of the process starts with whatever the operator set);
- after `run_warmup` returns, *unsetting* anything (operator-set values persist; defaults persist for the rest of the process).

**Asserted by**: `test_warmup_cpu_no_op.py::test_no_miopen_env_var_mutation_on_cpu_path` and `test_warmup_unit.py::test_run_warmup_respects_operator_set_env`.

## I-8. Determinism of warmup input

`run_warmup`'s default fixture path resolves to `tests/stage1_vendor_identity/inv_001_easy/source.pdf` (R-016.2). The fixture is rasterized through `preprocessing.rasterize.rasterize_page(...)` at the same DPI the active preprocess profile uses (300 DPI for `ppstructurev3@gpu`). The PIL image bytes are sha256'd; the digest is stored in `WarmupResult.fixture_sha256` for diagnostics. If the digest changes between two runs that supposedly used the same fixture, that's an integrity bug — `test_warmup_unit.py::test_fixture_digest_stable` pins the digest.

## I-9. Schema_version codebase-level bump

The `SCHEMA_VERSION` literal in `pipeline/timing.py` MUST be `"0.1.3"` for every run of the new binary, regardless of opt-in state (R-016.9 / FR-008 / /speckit.clarify Q2). Asserted by `test_run_summary_schema_0_1_3.py::test_schema_version_is_0_1_3_regardless_of_warmup`.

## I-10. Byte-identical `preprocess_output.json`

Two runs of `python -m ledgerlinc_ocr.preprocessing --preprocess-profile=ppstructurev3@gpu <doc>`, one with `--gpu-warmup` and one without, MUST produce a byte-identical `preprocess_output.json`. Verified by sha256 equality. This is the strongest contract this feature owes to the corpus baselines (FR-018 / SC-008). Asserted by `test_warmup_engine_reuse.py @gpu`.

## I-11. Joint presence of first-doc one-time GPU phases

The four "first-doc one-time GPU phase" keys — `paddle_import`, `gpu_bind_probe`, `engine_init`, and `warmup` — are attached by the SAME `attach_one_time_gpu_phases(record, readout, *, warmup_seconds=...)` helper (R-016.8). On a successful warmup-enabled `ppstructurev3@gpu` run, all four are present together on the first successful per-doc entry; on a successful warmup-DISABLED `ppstructurev3@gpu` run, the first three are present together (and `warmup` is absent); on a CPU/stub run, all four are absent together. The contract is **joint**: tests asserting any one of the four MAY assume the helper attached them as a coherent set in the relevant scenario. Individual keys MAY still be absent within the coherent set if their underlying source value was `None` (per feature 015 FR-016 — e.g., if `paddle_import` was not measured because paddle was preloaded by an earlier in-process step), but the helper itself never partially attaches the warmup-vs-non-warmup split. **Asserted by**: `test_run_summary_schema_0_1_3.py::test_warmup_attaches_alongside_one_time_phases` (CPU-safe via stub-injected `warmup_seconds`) and `test_warmup_engine_reuse.py @gpu` for the live GPU case.
