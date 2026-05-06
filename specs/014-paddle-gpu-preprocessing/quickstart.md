# Quickstart: Workstation Paddle GPU Preprocessing Validation

**Feature**: 014-paddle-gpu-preprocessing
**Date**: 2026-05-06

This walkthrough is the developer-facing companion to `spec.md`,
`plan.md`, and `research.md`. It assumes a workstation that *might*
have AMD/ROCm GPU support and you want to find out, decide whether to
use the new GPU preprocessing lane, and capture warm CPU vs. warm GPU
timing.

Run every command from the feature worktree root:

```bash
cd /workspace/projects/ledgerlinc/ledgerlinc-model-ocr-pipeline-worktrees/014-paddle-gpu-preprocessing
```

---

## 0. Install (once)

The base install path is unchanged from feature 010 and ships
**CPU-only** Paddle:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

If you want to attempt the GPU lane, install the workstation-only
ROCm-enabled Paddle wheel **outside** of `pyproject.toml` (FR-024,
R-014.11). The exact wheel and index URL are pinned in
`docs/stage1-vendor-identity/paddle-gpu-preflight.md`. Do not edit
`requirements.txt` or `pyproject.toml`; this install path is
intentionally additive and workstation-specific:

```bash
# Example only — see docs/stage1-vendor-identity/paddle-gpu-preflight.md
# for the currently pinned wheel version.
.venv/bin/pip uninstall -y paddlepaddle
.venv/bin/pip install paddlepaddle-gpu==<pinned> -f <official-rocm-wheel-index>
```

If you skip this step, preflight will report `paddle_cpu_only` and the
GPU lane will fail-fast — that is the intended diagnostic.

---

## 1. Run the preflight (P1)

```bash
.venv/bin/python -m ledgerlinc_ocr.preprocessing.preflight
```

Expected output for each FR-001 state (excerpts):

### Success

```text
[preflight] state: ppstructurev3_init_succeeded
interpreter_path: /workspace/.../.venv/bin/python
paddle_version: 3.0.0
paddleocr_version: 3.5.0
paddle_compiled_with_rocm: true
visible_device_count: 1
selected_device: gpu:0
ppstructurev3_init_seconds: 8.4213

recommendation: GPU lane is ready. You can now run --preprocess-profile=ppstructurev3@gpu.
{"kind":"preflight_readout","schema_version":"0.1.0","state":"ppstructurev3_init_succeeded",...}
```

Exit code: `0`.

### Paddle CPU-only

```text
[preflight] state: paddle_cpu_only
paddle_version: 3.0.0
paddle_compiled_with_cuda: false
paddle_compiled_with_rocm: false

recommendation: Install a GPU-enabled paddlepaddle wheel; see docs/stage1-vendor-identity/paddle-gpu-preflight.md.
```

Exit code: `11`.

### GPU not exposed (e.g. inside Docker without `/dev/kfd`)

```text
[preflight] state: gpu_not_exposed
paddle_compiled_with_rocm: true
visible_device_count: 0
runtime_device_exposure.dev_kfd_present: false
runtime_device_exposure.running_in_container: true

recommendation: GPU device file /dev/kfd is not mapped into this container; expose it or run on the host.
```

Exit code: `12`.

### Paddle can't bind

```text
[preflight] state: gpu_exposed_paddle_cant_bind
ppstructurev3_init_error: HipErrorNoBinaryForGpu...

recommendation: Paddle GPU build does not match the workstation ROCm driver version; see docs/stage1-vendor-identity/paddle-gpu-preflight.md for the supported wheel-driver combination.
```

Exit code: `13`.

### Network-restricted shell (no first-run weights)

```bash
.venv/bin/python -m ledgerlinc_ocr.preprocessing.preflight --no-init
```

Will report up through `gpu_exposed_paddle_cant_bind` cleanly without
attempting `PPStructureV3(...)`. The JSON payload's
`ppstructurev3_init_skipped_reason` will be
`"caller_disabled_init_attempt"`.

---

## 2. Run the GPU preprocessing lane on one document (P2)

Once preflight returns `ppstructurev3_init_succeeded`:

```bash
.venv/bin/python -m ledgerlinc_ocr.preprocessing.cli \
    --input tests/stage1_vendor_identity/inv_001_easy/source.pdf \
    --document-id inv_001_easy \
    --preprocess-profile ppstructurev3@gpu \
    --start-at preprocess --stop-after preprocess \
    --output-dir tests/stage1_vendor_identity/inv_001_easy
```

Verify:

```bash
.venv/bin/python -c "
import json, re
data = json.loads(open('tests/stage1_vendor_identity/inv_001_easy/preprocess_output.json').read())
m = re.search(r'\\.(cpu|gpu\\d+)$', data['pipeline_version'])
assert m and m.group(1).startswith('gpu'), f'expected gpu lane, got {data[\"pipeline_version\"]}'
print('lane:', m.group(1))
print('blocks:', sum(len(p['blocks']) for p in data['pages']))
print('document_text non-empty:', bool(data['document_text'].strip()))
"
```

Expected output: lane is `gpu0`, at least 3 blocks, non-empty
`document_text` (US2 acceptance scenario 1).

### Failing fast when prerequisites are missing

If you uninstall `paddlepaddle-gpu` and reinstall the CPU wheel, then
re-run the same command, the pipeline must fail before any artifact
write:

```bash
.venv/bin/pip uninstall -y paddlepaddle
.venv/bin/pip install paddlepaddle==<cpu-pinned>
.venv/bin/python -m ledgerlinc_ocr.preprocessing.cli \
    --input tests/stage1_vendor_identity/inv_001_easy/source.pdf \
    --document-id inv_001_easy \
    --preprocess-profile ppstructurev3@gpu \
    --start-at preprocess --stop-after preprocess \
    --output-dir tests/stage1_vendor_identity/inv_001_easy
echo "exit: $?"
# Expected stderr: error: --preprocess-profile=ppstructurev3@gpu: paddle_cpu_only; ...
# Expected exit:   11
```

`preprocess_output.json` must NOT have been overwritten by this run.

---

## 3. Compare warm CPU vs. warm GPU timing (P3)

Reuse a small corpus run to capture both lanes:

```bash
# CPU run (default)
.venv/bin/python -m ledgerlinc_ocr.pipeline \
    --documents-file tests/stage1_vendor_identity/_documents.txt \
    --start-at preprocess --stop-after preprocess \
    > /tmp/run_summary_cpu.jsonl

# GPU run
.venv/bin/python -m ledgerlinc_ocr.pipeline \
    --documents-file tests/stage1_vendor_identity/_documents.txt \
    --preprocess-profile ppstructurev3@gpu \
    --start-at preprocess --stop-after preprocess \
    > /tmp/run_summary_gpu.jsonl
```

Extract timing from the last line of each:

```bash
.venv/bin/python -c "
import json
def last(f): return json.loads(open(f).readlines()[-1])
cpu = last('/tmp/run_summary_cpu.jsonl')
gpu = last('/tmp/run_summary_gpu.jsonl')
print('lane (cpu run):', cpu.get('preprocess_lane'))
print('lane (gpu run):', gpu.get('preprocess_lane'))
print('init seconds (cpu):', cpu['profile_initialization_seconds'].get('preprocess'))
print('init seconds (gpu):', gpu['profile_initialization_seconds'].get('preprocess'))
for tag, run in (('cpu', cpu), ('gpu', gpu)):
    for d in run['per_document']:
        if d['status'] != 'success': continue
        s = d['stages'].get('preprocess', {})
        print(tag, d['document_id'], 'total:', s.get('total_seconds'), 'gpu_inference:', s.get('gpu_inference_seconds'))
"
```

Expected (US3 acceptance scenarios 1, 2):

- CPU run prints `preprocess_lane: cpu`, no `gpu_*` keys.
- GPU run prints `preprocess_lane: gpu0`, `gpu_init_seconds` on the
  first document, `gpu_inference_seconds` on every successful document.
- GPU per-document `total_seconds` is measurably lower than CPU
  per-document `total_seconds` (SC-008).

No new committed file has been produced (FR-022) — the timing lives
on stdout only.

---

## 4. CPU determinism check (FR-017, SC-006)

After installing this feature, run the CPU lane twice on the same
input and confirm byte-stability:

```bash
rm -f tests/stage1_vendor_identity/inv_001_easy/preprocess_output.json
.venv/bin/python -m ledgerlinc_ocr.preprocessing.cli \
    --input tests/stage1_vendor_identity/inv_001_easy/source.pdf \
    --document-id inv_001_easy \
    --start-at preprocess --stop-after preprocess \
    --output-dir tests/stage1_vendor_identity/inv_001_easy
sha256sum tests/stage1_vendor_identity/inv_001_easy/preprocess_output.json | tee /tmp/sha_run1

rm -f tests/stage1_vendor_identity/inv_001_easy/preprocess_output.json
.venv/bin/python -m ledgerlinc_ocr.preprocessing.cli \
    --input tests/stage1_vendor_identity/inv_001_easy/source.pdf \
    --document-id inv_001_easy \
    --start-at preprocess --stop-after preprocess \
    --output-dir tests/stage1_vendor_identity/inv_001_easy
sha256sum tests/stage1_vendor_identity/inv_001_easy/preprocess_output.json | tee /tmp/sha_run2

diff /tmp/sha_run1 /tmp/sha_run2 && echo "byte-stable ✓"
```

Both runs MUST produce identical SHA-256 sums. Any difference is a
regression of FR-017.

---

## 5. Run the test suite

Default (no GPU available — CI behavior):

```bash
.venv/bin/pytest
```

GPU-marked tests are skipped with a reason that names a specific
FR-001 state (FR-019). Inspect the skip reason:

```bash
.venv/bin/pytest -m gpu --collect-only -q
# Each gpu-marked test prints "skipped: state=<FR-001 state>; <recommendation>"
```

To run only the GPU-marked tests on a workstation that passes
preflight:

```bash
.venv/bin/pytest -m gpu
```

If the workstation does not pass preflight, every `gpu`-marked test
is skipped — never failed (FR-019).

---

## 6. Where to read further

- [`spec.md`](./spec.md) — feature spec and clarifications
- [`plan.md`](./plan.md) — milestones M1–M3 and constitution gates
- [`research.md`](./research.md) — every implementation decision (R-014.1
  through R-014.11)
- [`data-model.md`](./data-model.md) — in-memory entities, FR-001
  state enum, `RunSummary` additive fields
- [`contracts/cli-contract.md`](./contracts/cli-contract.md) — exact
  CLI flag, exit code, and stdout shape contracts
- `docs/stage1-vendor-identity/paddle-gpu-preflight.md` (lands during
  M1) — operator-facing FR-001 state guide and pinned wheel install
  command
