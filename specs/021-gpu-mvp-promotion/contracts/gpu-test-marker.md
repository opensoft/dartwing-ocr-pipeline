# Contract: GPU Test Marker (FR-006 – FR-010, SC-004)

**Path**: `tests/pipeline_tests/test_evidence_gate_*.py` + `tests/unit/preprocessing/test_warmup_skip_fallback_exception.py`
**Spec refs**: [spec.md §FR-006 – FR-010](../spec.md), [research.md §R-021.8](../research.md)
**Constitution refs**: §V (reproducibility)

This contract defines how the five formerly-deferred GPU placeholder test files are converted from inert (`@pytest.mark.skip(reason="R-020.15")`) to real GPU-asserting tests while keeping CPU CI green.

## Files in scope

| File                                                                                              | US scenario(s) covered |
|---------------------------------------------------------------------------------------------------|------------------------|
| `tests/pipeline_tests/test_evidence_gate_skip_fallback.py`                                        | US2-1 (sufficient suppress) |
| `tests/pipeline_tests/test_evidence_gate_skip_fallback_borderline.py`                             | US2-2 (borderline/insufficient fallback) |
| `tests/pipeline_tests/test_evidence_gate_all_suppressed_lazy_construction.py`                     | US2-3 (lazy construction) + US2-4 (`--gpu-warmup` exception, partial) |
| `tests/unit/preprocessing/test_warmup_skip_fallback_exception.py`                                 | US2-4 (`--gpu-warmup` exception) |
| `tests/pipeline_tests/test_quality_gate_two_metric_evidence_gate.py`                              | US4 (two-metric quality gate) |

## Marker contract

### File-level (unchanged)

Each file MUST retain its top-level:

```python
pytestmark = pytest.mark.gpu
```

This is the **collection-level** gate. CPU CI runs with `pytest -m 'not gpu'` (or equivalent) and continues to skip these files entirely. GPU validation runs with `pytest -m gpu` against `.venv-paddle-rocm`.

### Per-test (this feature changes)

The per-test `@pytest.mark.skip(reason="R-020.15")` decorator MUST be **removed** from every test function in these files. Test bodies that were previously empty placeholders are replaced with real GPU assertions wired to the spec's acceptance scenarios.

### Marker registration

`pyproject.toml` `[tool.pytest.ini_options]` (or `pytest.ini` `[pytest]`) MUST register the `gpu` marker to silence `PytestUnknownMarkWarning`:

```toml
[tool.pytest.ini_options]
markers = [
    "gpu: requires AMD ROCm + paddlepaddle-dcu + host Ollama on GPU (workstation only; CPU CI skips)",
]
```

If a `markers` entry already exists, add `gpu` to it; do NOT introduce duplicate entries.

## Test body contracts

Each converted test MUST satisfy the acceptance criteria already captured in spec §User Story 2 / §User Story 4. Below is the per-test acceptance shape; implementation details belong in `tasks.md`.

### `test_evidence_gate_skip_fallback.py::test_skip_fallback_sufficient_suppresses_ppstructurev3_gpu`

- **Given**: a known `sufficient` OCR-only document in `tests/stage1_vendor_identity/` (e.g., `inv_001_easy`).
- **When**: pipeline runs on `ppstructurev3@gpu` with `--evidence-gate-skip-fallback` (or `DARTWING_EVIDENCE_GATE_SKIP_FALLBACK=1`).
- **Then**: `run_summary.evidence_gate_suppressed_fallback_count == 1` (or matches the per-document count) AND the run does NOT include `phase_timings.engine_init` / `phase_timings.warmup` for that document (verifiable from the stdout `run_summary` JSON).

### `test_evidence_gate_skip_fallback_borderline.py::test_skip_fallback_borderline_still_falls_back_gpu`

- **Given**: a known `borderline` or `insufficient` document.
- **When**: same `--evidence-gate-skip-fallback` invocation as above.
- **Then**: PPStructureV3 fallback IS executed for that document (`engine_init` / `warmup` phase keys are present) AND `evidence_gate_suppressed_fallback_count` does NOT increment for that document.

### `test_evidence_gate_all_suppressed_lazy_construction.py::test_all_sufficient_no_warmup_keeps_ppstructurev3_unconstructed_gpu`

- **Given**: a run where every input document is `sufficient` AND `--gpu-warmup` is NOT passed.
- **When**: pipeline runs on `ppstructurev3@gpu` with `--evidence-gate-skip-fallback`.
- **Then**: NO `phase_timings.engine_init` / `phase_timings.warmup` key appears in any per-document `run_summary` line (lazy construction confirmed).

### `test_evidence_gate_all_suppressed_lazy_construction.py::test_all_sufficient_with_gpu_warmup_constructs_ppstructurev3_gpu`

- **Given**: same all-`sufficient` input AND `--gpu-warmup` IS passed.
- **When**: pipeline runs on `ppstructurev3@gpu` with `--evidence-gate-skip-fallback`.
- **Then**: `phase_timings.engine_init` AND `phase_timings.warmup` appear in the `run_summary` line (explicit operator trade-off; not a regression).

### `test_warmup_skip_fallback_exception.py::test_gpu_warmup_overrides_skip_fallback_lazy_construction`

- **Given**: same all-`sufficient` input AND `--gpu-warmup` IS passed.
- **When**: the warmup path is invoked.
- **Then**: PPStructureV3 IS constructed; the warmup phase key is present even though every document is later suppressed.

### `test_quality_gate_two_metric_evidence_gate.py::test_two_metric_quality_gate_pass_or_fail_or_blocked_gpu`

- **Given**: legacy and candidate runs on the FR-011 five-document subset produced via the GPU lane.
- **When**: feature-007 evaluator runs on each lane's scratch root.
- **Then**: the test reads the FR-019 aggregate vendor-identity pass rate (`overall_metrics.vendor_identity_pass_rate`) and corpus field-level accuracy (`overall_metrics.field_accuracy`) for each lane (R-021.13, verification-round revision) and asserts the verdict resolution:
  - `candidate_pass_rate >= legacy_pass_rate AND candidate_field_accuracy >= legacy_field_accuracy` → PASS
  - At least one regression → FAIL with the specific metric named
  - Unable to compute due to hardware/runtime cause → BLOCKED (test marks itself BLOCKED via a `pytest.xfail(strict=False)` with the named cause); the BLOCKED verdict is NOT treated as test failure but IS recorded in Appendix B per FR-022.

## CI behavior contract

- **CPU CI** (e.g., GitHub Actions on Linux without ROCm): `pytest -m 'not gpu'`. All five converted files are skipped at collection time via the file-level `pytestmark = pytest.mark.gpu`. CPU-safe twins (`*_cpu.py`) continue to provide the existing coverage of the same invariants.
- **GPU validation** (workstation operator): `pytest -m gpu -v` against `.venv-paddle-rocm`. All five files run and produce real PASS/FAIL/BLOCKED results.
- **Mixed** (rare): `pytest` without a marker filter runs both; the GPU files will FAIL or skip with import errors on a non-GPU environment, which is the intended cost of explicit invocation.

## What this contract does NOT cover

- It does not pin the exact pytest fixtures or assertion APIs — those belong in `tasks.md`.
- It does not modify the CPU-safe twin tests (`*_cpu.py`); those remain unchanged.
- It does not introduce new test files except for the conditional FR-028 explicit-off legacy-path test (if `promote to default` is the recorded decision; that test lives at `tests/unit/preprocessing/test_skip_fallback_explicit_off_legacy.py` per plan §Project Structure).
