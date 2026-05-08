# Contract: Module-Level Invariants For Engine Reuse And Phase Timing

These invariants are the testable code-level rules that back the spec's FRs and SCs. Each row has a one-line statement, the responsible module, and the test file that asserts it.

## Engine reuse

| ID | Statement | Module | Test |
|---|---|---|---|
| CF4 | After `ocr._ENGINE_DEVICE` is set on first construction, any `_get_engine(device=other)` where `other != _ENGINE_DEVICE` MUST raise `RuntimeError`. | `preprocessing/ocr.py` | Existing — pre-feature-015 tests, unchanged. |
| CF5 | After `classify(attempt_ppstructurev3_init=True)` returns `PPSTRUCTUREV3_INIT_SUCCEEDED`, `ocr._ENGINE` MUST be the engine instance constructed in classify step 6 and `ocr._ENGINE_DEVICE == "gpu:0"`. Subsequent `ocr._get_engine(device="gpu:0")` MUST return that same instance (verified via `id(...)`). | `preprocessing/preflight.py` ↔ `preprocessing/ocr.py` | New — `tests/preprocessing/test_preflight_engine_persistence.py`. |
| CF6 | `classify(attempt_ppstructurev3_init=False)` MUST NOT touch `ocr._ENGINE` or `ocr._ENGINE_DEVICE`. | `preprocessing/preflight.py` | Same test file as CF5 (negative case). |
| CF7 | The total count of PPStructureV3 constructor invocations across one process MUST be ≤ 1 on the GPU lane (SC-001). | Both modules | New — uses a `paddleocr.PPStructureV3` mock + counter to assert call count == 1 across a two-document warm corpus run. |

## Phase timing shape (Clarification Q3)

| ID | Statement | Module | Test |
|---|---|---|---|
| PT1 | Each `phase_timings[<name>]` value MUST be a JSON object with exactly the key `seconds` (float, ≥ 0). No extra keys (e.g., no `started_at`). | `pipeline/timing.py` | New — `tests/preprocessing/test_phase_timings_unit.py::test_phase_timings_record_shape`. |
| PT2 | `per_page_inference` MUST be a JSON array of objects, each with exactly `page` (int ≥ 1) and `seconds` (float ≥ 0), no extra keys. | `pipeline/timing.py` | Same test file. |
| PT3 | `per_page_inference[*].page` values MUST be strictly increasing (ascending), 1-based, and match `preprocess_output.json[*].pages[*].page_number` for the same document. | `pipeline/timing.py` | Same. |
| PT4 | All durations MUST be derived from `time.perf_counter_ns()` deltas, six-decimal-rounded to seconds. | `preprocessing/preflight.py`, `preprocessing/ocr.py`, `pipeline/timing.py`, `preprocessing/pipeline.py` | Same — asserts that the value of `phase_timings.total.seconds` is approximately equal to the sum of named child phases (within float tolerance), implying a consistent monotonic clock. |
| PT5 | The `RunSummary.SCHEMA_VERSION` constant MUST equal `"0.1.2"`. | `pipeline/timing.py` | New — `tests/pipeline/test_run_summary_schema_0_1_2.py::test_schema_version_bumped`. |

## Channel and isolation (Clarifications Q1, Q2; FR-014, FR-017–FR-019)

| ID | Statement | Module | Test |
|---|---|---|---|
| CH1 | `phase_timings` and `per_page_inference` MUST appear ONLY inside the `kind: "run_summary"` stdout JSON line — NOT inside `preprocess_output.json`. | All call sites | New — golden-file assertion that `preprocess_output.json` for a feature-015 GPU run is byte-identical to the v1.2.0 contract-test fixture (no new fields). |
| CH2 | No new stdout `kind` is introduced. The only emitted kinds are the existing `run_summary`, `preflight_readout`, `failure`, and the existing per-doc artifacts emission. | CLI surfaces | New — `tests/pipeline/test_run_summary_schema_0_1_2.py::test_no_new_stdout_kinds` (parses every JSONL stdout line from a corpus run and asserts the `kind` set is a subset of the pre-existing vocabulary plus `run_summary`). |
| CH3 | `phase_timings.warmup` MUST be **absent** by default; feature 015 does not introduce a synthetic warmup pass. | `pipeline/timing.py`, `preprocessing/pipeline.py` | New — `test_run_summary_schema_0_1_2.py::test_warmup_phase_omitted_by_default`. |
| ISO1 | A CPU-lane run MUST NOT emit `paddle_import`, `gpu_bind_probe`, `engine_init`, `warmup`, or `per_page_inference` keys on any per_document entry. | `pipeline/corpus_run.py`, `preprocessing/cli.py` | New — `tests/pipeline/test_cpu_lane_no_gpu_phase_keys.py`. |
| ISO2 | A stub-adapter run MUST NOT execute preflight or any of the GPU phase timers. | Stub adapter wiring | Existing stub-adapter tests; new assertion that no GPU phase keys appear on stub run output. |

## Fail-fast budget (Clarification Q4 / SC-007)

| ID | Statement | Module | Test |
|---|---|---|---|
| FF1 | A GPU lane run on a host where prerequisites are missing MUST exit non-zero within 10 s wall-clock from process start (measured outside, around the CLI subprocess). The subprocess MUST NOT have produced a `preprocess_output.json` whose `pipeline_version` ends in `.gpu0`. | CLI entrypoints | New — `tests/preprocessing/test_fail_fast_budget.py`. Uses the `gpu` pytest marker; on a GPU-less host classifier returns `PADDLE_NOT_INSTALLED` or `GPU_NOT_EXPOSED`, both well under 10 s. |
| FF2 | After a successful `ensure_gpu_ready()` in one process, subsequent calls MUST short-circuit on `_LAST_READOUT` cache without re-running `import paddle` or the bind probe. | `preprocessing/preflight.py` | Existing — preserved from feature 014. |

## Failure-path emission (Clarification Q5)

| ID | Statement | Module | Test |
|---|---|---|---|
| FP1 | A per-document failure record MUST carry partial `phase_timings` (omitting phases that did not run) and partial `per_page_inference` (only pages that completed inference). The record MUST keep `status: "failure"` and the existing `failed_stage` / `exit_code` / `message` fields. | `pipeline/timing.py` (`build_per_document_failure`), `pipeline/corpus_run.py` | New — `tests/pipeline/test_failure_phase_timings.py`. |
| FP2 | Phases that did NOT run on a failed document MUST be **absent** from `phase_timings`, not set to `null` or `0.0`. | Same module | Same test. |
