# Quickstart: GPU Engine Reuse And Phase Timing

This walkthrough verifies the feature-015 changes end-to-end: PPStructureV3 is constructed exactly once per process, the `kind: "run_summary"` stdout line carries the new `phase_timings` and `per_page_inference` blocks at `schema_version: "0.1.2"`, and CPU/stub paths remain GPU-cost-free.

The walkthrough assumes the workstation ROCm Paddle path established in feature 014 (host WSL `.venv-paddle-rocm` with `paddlepaddle-dcu` bound to `gpu:0`).

## Prerequisites

```bash
# from the repo root
source .venv-paddle-rocm/bin/activate           # workstation GPU lane
# OR
source .venv/bin/activate                        # CPU/stub lane

pip install -e ".[dev]"                          # idempotent
```

Confirm the environment:

```bash
python -m ledgerlinc_ocr.preprocessing.preflight --json
# expect: {"kind":"preflight_readout","state":"ppstructurev3_init_succeeded", …}
# AND total wall-clock under ~60 s (this is the standalone CLI; the runtime gate persists the engine and pays this cost only once total per process)
```

## Smoke 1 — single-document GPU run, one PPStructureV3 construction

```bash
python -m ledgerlinc_ocr.preprocessing \
    --document-folder tests/stage1_vendor_identity/inv_001_easy \
    --preprocess-profile ppstructurev3@gpu \
    --pretty-stdout
```

Expected:

1. The CLI emits a final `kind: "run_summary"` JSON line on stdout.
2. `schema_version` is `"0.1.2"`.
3. `documents_total: 1`, `documents_succeeded: 1`, `preprocess_lane: "gpu0"`.
4. The single `per_document[0]` entry contains:
   - `phase_timings` with keys `paddle_import`, `gpu_bind_probe`, `engine_init`, `rasterization`, `artifact_write`, `total` (no `warmup` — Q2 reserved phase only).
   - `per_page_inference` with one or more `{ "page": <1-based>, "seconds": <float> }` records.
5. The legacy `stages.preprocess.{total_seconds, gpu_init_seconds, gpu_inference_seconds}` flat keys are still present.
6. The on-disk `preprocess_output.json` validates against contract set `1.2.0` and has `pipeline_version` ending in `.gpu0`. `document_text` is non-empty and at least three layout blocks are present (SC-003).

Verify engine reuse from a Python REPL in the same process:

```python
from ledgerlinc_ocr.preprocessing import ocr, preflight
preflight.ensure_gpu_ready()                 # cached after the CLI run above? No — CLI ran in a subprocess.
# Instead, run within one Python process:
from ledgerlinc_ocr.preprocessing.pipeline import run, Invocation
from pathlib import Path

inv = Invocation(
    document_folder=Path("tests/stage1_vendor_identity/inv_001_easy"),
    preprocess_lane="gpu0",
)
run(inv)
e1 = id(ocr._ENGINE)
run(inv)                                      # second invocation in same process
assert id(ocr._ENGINE) == e1                  # CF5 — same instance
```

## Smoke 2 — warm corpus run, one engine across two documents

Create a documents file:

```bash
cat > /tmp/feature015_warm.txt <<EOF
tests/stage1_vendor_identity/inv_001_easy
tests/stage1_vendor_identity/inv_002_easy
EOF
```

Run:

```bash
python -m ledgerlinc_ocr.pipeline \
    --documents-file /tmp/feature015_warm.txt \
    --preprocess-profile ppstructurev3@gpu
```

Expected:

1. The final `run_summary` line has `documents_total: 2`, `documents_succeeded: 2`.
2. `per_document[0].phase_timings` contains all four GPU one-time keys (`paddle_import`, `gpu_bind_probe`, `engine_init`) plus per-document keys.
3. `per_document[1].phase_timings` contains ONLY the per-document keys (`rasterization`, `artifact_write`, `total`) and a `per_page_inference` array. The four GPU one-time keys MUST be absent on the second document (SC-002).
4. `per_document[1].stages.preprocess` does NOT contain `gpu_init_seconds` (legacy form mirrors the new shape's first-doc-only rule).
5. Across the two documents, only one `PPStructureV3(...)` constructor call happened (SC-001 / CF7). Verifiable via `pytest tests/pipeline/test_warm_corpus_one_init.py` which mocks the constructor and asserts `call_count == 1`.

## Smoke 3 — fail-fast budget on a GPU-less host

On a host where `paddlepaddle-dcu` is not installed (or `gpu:0` is not visible):

```bash
time python -m ledgerlinc_ocr.preprocessing \
    --document-folder tests/stage1_vendor_identity/inv_001_easy \
    --preprocess-profile ppstructurev3@gpu
```

Expected:

1. Exit code is non-zero (one of 10–14, mapped from the FR-001 fail state).
2. `time` reports wall-clock < 10 s (SC-007 / Clarification Q4).
3. stderr contains the FR-009 form: `error: --preprocess-profile=ppstructurev3@gpu: <state>; <recommendation>`.
4. No `preprocess_output.json` was written (or, if a stale one existed, it is unchanged).

## Smoke 4 — CPU lane stays GPU-cost-free

```bash
python -m ledgerlinc_ocr.preprocessing \
    --document-folder tests/stage1_vendor_identity/inv_001_easy \
    --preprocess-profile ppstructurev3@cpu \
    --pretty-stdout
```

Expected:

1. `run_summary` is emitted at `schema_version: "0.1.2"` with `preprocess_lane: "cpu"`.
2. `per_document[0].phase_timings` contains ONLY `rasterization`, `artifact_write`, `total`.
3. `per_document[0].phase_timings.paddle_import`, `gpu_bind_probe`, `engine_init`, `warmup` are absent (FR-017 / ISO1).
4. `per_document[0].per_page_inference` is absent (CPU collapses per-page time into `total`).
5. No GPU preflight ran — verifiable from logs (no `preflight_readout` line emitted on CPU runs).

## Test-suite verification

```bash
# Run the full default test suite — must pass on any host (FR-018 / SC-008)
pytest

# Run the GPU-only suite — only meaningful on GPU-capable hosts
pytest -m gpu
```

The default suite skips `gpu`-marked tests via `tests/conftest.py`, so a CI run without GPU hardware reports skips (not failures) for the GPU-specific tests added by this feature (FR-019 / SC-008).

## Identifying the slowest phase (SC-005)

After Smoke 1, parse the run_summary line:

```bash
python -m ledgerlinc_ocr.preprocessing \
    --document-folder tests/stage1_vendor_identity/inv_001_easy \
    --preprocess-profile ppstructurev3@gpu \
    --pretty-stdout 2>/dev/null \
  | tail -1 \
  | python -c "
import json, sys
summary = json.loads(sys.stdin.read())
doc = summary['per_document'][0]
phases = doc.get('phase_timings', {})
ranked = sorted(phases.items(), key=lambda kv: -kv[1]['seconds'])
print('slowest phases:')
for name, val in ranked[:5]:
    print(f'  {name}: {val[\"seconds\"]:.3f} s')
pages = doc.get('per_page_inference', [])
if pages:
    print('per-page inference:')
    for p in pages:
        print(f'  page {p[\"page\"]}: {p[\"seconds\"]:.3f} s')
"
```

Output gives an immediate human-readable answer to "where is the time going?" — satisfying SC-005 without rerunning.
