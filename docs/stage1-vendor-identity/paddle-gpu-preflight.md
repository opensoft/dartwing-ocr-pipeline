# Paddle GPU Preflight (Workstation)

This document is the operator-facing reference for the workstation Paddle
GPU preprocessing lane (`ppstructurev3@gpu`). It explains the six FR-001
preflight states surfaced by `python -m dartwing_ocr.preprocessing.preflight`,
the supported native Linux ROCm install path, the unsupported runtime
shapes, the CI default behavior, and the verified offline-operation knobs
for network-restricted shells. The CPU lane (`ppstructurev3@cpu`) remains
the default and is unaffected; this doc only covers the workstation GPU
diagnostic path. Cross-references at the bottom point at the canonical
spec sections (FR-005, FR-024) and the feature 014 quickstart.

## How To Run Preflight

The preflight tool ships in-tree as a module CLI. There is no
`[project.scripts]` console entry; `python -m ...` is the only invocation
form (per `specs/014-paddle-gpu-preprocessing/contracts/cli-contract.md`
§1).

Install the package once into a venv (the lightweight CPU-only base):

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

Then run the preflight:

```bash
.venv/bin/python -m dartwing_ocr.preprocessing.preflight
```

Two flags are available:

| Flag        | Effect |
|-------------|--------|
| `--no-init` | Skip the PPStructureV3 GPU construction step (step 6 of R-014.7). Steps 1-5 (install probe, paddle import, build flag introspection, device count, tensor bind probe) still run. Use this in network-restricted shells where Paddle's first-run weight download cannot reach `paddlepaddle.bj.bcebos.com`. |
| `--quiet`   | Suppress the human-readable text section. Stdout is exactly the trailing JSON line. Useful when piping into a JSON parser or shell test. |

Stdout always ends with one JSON line of the shape
`{"kind":"preflight_readout","schema_version":"0.1.0","state":"<state>","evidence":{...},"recommendation":"..."}`.
The state value is the lowercase form of one of the six FR-001 states
listed below.

Exit codes (per CLI contract §1):

| Exit | Meaning |
|------|---------|
| `0`  | `ppstructurev3_init_succeeded` |
| `1`  | argparse / CLI usage error |
| `2`  | Internal classifier error (no FR-001 state could be produced) |
| `10` | `paddle_not_installed` |
| `11` | `paddle_cpu_only` |
| `12` | `gpu_not_exposed` |
| `13` | `gpu_exposed_paddle_cant_bind` |
| `14` | `ppstructurev3_init_failed` |

Preflight never writes a pipeline artifact; the only allowed disk write is
the preexisting first-run PaddleOCR weight download into
`~/.paddlex/official_models/`, suppressed by `--no-init`.

## The Six FR-001 States

Each of the six states below corresponds to one FR-001 outcome. For
fail states the recommendation follows the FR-003 three-part rule:
(a) a specific remediation action, (b) a back-reference to this doc,
and (c) one plain-language line that names the issue once and states
the next user action.

### `paddle_not_installed`

The preflight could not import `paddle`, or
`importlib.metadata.version("paddlepaddle")` raised
`PackageNotFoundError`.

- (a) **Remediation**: install the lightweight CPU base (or, on a
  workstation, the GPU wheel below) into the active venv:
  `.venv/bin/pip install -e ".[dev]"`.
- (b) **Doc reference**: see the *Supported Install Path* and
  *Unsupported Paths* sections of this doc
  (`docs/stage1-vendor-identity/paddle-gpu-preflight.md`).
- (c) **Plain language**: Paddle is not installed in this interpreter;
  install it or activate the venv that has it.

### `paddle_cpu_only`

`paddle` imported, but both `paddle.is_compiled_with_cuda()` and
`paddle.is_compiled_with_rocm()` returned False. The installed wheel is
the CPU build.

- (a) **Remediation**: uninstall the CPU wheel and install the
  workstation ROCm wheel from the *Supported Install Path* below
  (`pip uninstall paddlepaddle && pip install paddlepaddle-gpu ...`).
- (b) **Doc reference**: see *Supported Install Path* in this doc.
- (c) **Plain language**: this Paddle wheel has no GPU build; replace
  it with a ROCm-enabled wheel.

### `gpu_not_exposed`

Paddle has a GPU build (`is_compiled_with_cuda` or
`is_compiled_with_rocm` is True), but `paddle.device.cuda.device_count()`
returned `0`. Cross-checked against the runtime device exposure flags
(`/dev/kfd`, `/dev/dri`, `HIP_VISIBLE_DEVICES`, `ROCM_PATH`,
`CUDA_VISIBLE_DEVICES`, `running_in_container`) per R-014.10, the
recommendation names the missing device file or environment variable.

- (a) **Remediation**: expose the GPU device to the runtime. Inside a
  container, map `/dev/kfd` and `/dev/dri` and set the appropriate ROCm
  environment variables; or run the preflight on the host instead of in
  a container.
- (b) **Doc reference**: see *Unsupported Paths* in this doc for the
  WSL Docker Desktop and raw Conda readouts; see
  [`ollama-runtime.md`](./ollama-runtime.md) §*Production Container Path*
  for the verified `/dev/kfd` + `/dev/dri` exposure pattern on native
  Linux ROCm.
- (c) **Plain language**: no GPU device is visible to this process;
  fix container exposure or run on the host.

### `gpu_exposed_paddle_cant_bind`

The device count was non-zero, but the bind probe
(`paddle.device.set_device("gpu:0")` plus a tiny tensor allocation)
raised. Common causes are a wrong ROCm version, a wrong wheel, or a
missing runtime library. The classifier captures `str(exc)` verbatim
into `evidence.ppstructurev3_init_error` (the field is reused for the
bind probe at this stage).

- (a) **Remediation**: install a `paddlepaddle-gpu` wheel whose ROCm
  version matches the host's ROCm runtime, per the *Supported Install
  Path* below; verify `/opt/rocm` and `ROCM_PATH` line up.
- (b) **Doc reference**: see *Supported Install Path* in this doc.
- (c) **Plain language**: Paddle cannot bind to the visible GPU; the
  wheel and the host ROCm version are mismatched.

### `ppstructurev3_init_failed`

Paddle reported GPU as usable, but constructing
`PPStructureV3(device="gpu:0", ...)` raised. The captured exception text
goes into `ppstructurev3_init_error`. This is the highest-fidelity
GPU-readiness signal short of running on a real document; the
pipeline's inline gate trusts this state without re-running the
construction.

- (a) **Remediation**: read `ppstructurev3_init_error` in the readout,
  reconcile the underlying issue (typically a PaddleOCR / paddlepaddle
  version skew or a missing PaddleX dependency), and rerun preflight.
  If the failure is missing model weights in a network-restricted
  shell, see *Offline-Operation Knobs* below.
- (b) **Doc reference**: see *Offline-Operation Knobs* and
  *Supported Install Path* in this doc.
- (c) **Plain language**: PPStructureV3 will not initialize on the GPU;
  the captured error names the underlying cause.

### `ppstructurev3_init_succeeded`

`paddle` imported, GPU build available, device visible, bind probe
passed, and `PPStructureV3(device="gpu:0", ...)` constructed. The GPU
lane is safe to enable. The selected device string is `gpu:0`. The
recommendation confirms the GPU profile is ready and names the device
string verbatim, e.g. `GPU lane is ready. You can now run
--preprocess-profile=ppstructurev3@gpu (device gpu:0).`

## Supported Install Path

The supported workstation runtime is a **native Linux ROCm host** with a
ROCm-enabled Paddle build that matches the host's ROCm runtime. This is
the only Paddle GPU runtime path the team has agreed to support for
stage 1 preprocessing.

The wheel itself, plus the ROCm/CMake patches and source-build runbook
required to produce it for hosts with no matching public wheel (currently
the case for AMD `gfx1151` on Python 3.12 ROCm 7.x), live in the
[`opensoft/model-paddle`](https://github.com/opensoft/model-paddle) repo.
The pipeline does **not** ship a build script; this preflight only
detects the consumed distribution name (`paddlepaddle`,
`paddlepaddle-gpu`, or `paddlepaddle-dcu`).

Workstation install:

1. **Get a wheel.** Either download a published asset from a
   [`model-paddle` GitHub Release](https://github.com/opensoft/model-paddle/releases),
   or build one locally per `model-paddle`'s
   [`docs/source-build.md`](https://github.com/opensoft/model-paddle/blob/main/docs/source-build.md).
   Naming: a ROCm build emits `paddlepaddle-dcu` (because Paddle's
   `WITH_ROCM=ON` build renames the wheel); a CUDA build emits
   `paddlepaddle-gpu`. Both expose the normal `import paddle` module and
   `gpu:0` device string. Do **not** install a CUDA wheel on an AMD host
   — CUDA wheels do not make Paddle bind to an AMD ROCm device.

2. **Install into an isolated venv first** (do not replace the project
   `.venv` until verification passes):

   ```bash
   python3.12 -m venv .venv-paddle-rocm
   .venv-paddle-rocm/bin/pip install -U pip
   .venv-paddle-rocm/bin/pip install -e ".[dev]" --no-deps
   .venv-paddle-rocm/bin/pip install paddleocr==3.5.0 "paddlex[ocr]==3.5.1"
   .venv-paddle-rocm/bin/pip uninstall -y paddlepaddle
   # Either install from a model-paddle release asset URL …
   .venv-paddle-rocm/bin/pip install \
     https://github.com/opensoft/model-paddle/releases/download/<release-tag>/paddlepaddle_dcu-<version>-cp312-cp312-linux_x86_64.whl
   # … or install a locally-built wheel from model-paddle's wheelhouse:
   # .venv-paddle-rocm/bin/pip install ~/.cache/dartwing/paddle-rocm/wheelhouse/paddlepaddle_dcu-*.whl
   ```

3. **Verify the wheel binds.** Run `model-paddle`'s pipeline-agnostic
   probe (`scripts/verify-paddle-rocm-runtime.sh` in that repo) — it
   confirms ROCm compilation, device visibility, and a tensor on
   `gpu:0`. Then run **this** preflight from the same venv to confirm
   PPStructureV3 itself initializes:

   ```bash
   PYTHONPATH=src .venv-paddle-rocm/bin/python -m dartwing_ocr.preprocessing.preflight
   ```

This install path is **not** added to `requirements.txt` and **not**
added to `pyproject.toml` (per FR-024). The lightweight pipeline
container's CPU-only baseline must remain installable without any
GPU-only wheel. Operators who need GPU enable it manually, per host,
into an isolated venv first.

## Unsupported Paths

The following runtime shapes are not supported for `ppstructurev3@gpu`.
Preflight will still run and produce a useful readout, but the team has
not validated PPStructureV3 GPU initialization on these paths.

### WSL Docker Desktop

Running `ppstructurev3@gpu` from inside a Docker Desktop container on
Windows + WSL 2 with AMD ROCm is **unsupported**. The same constraint
documented in [`ollama-runtime.md`](./ollama-runtime.md) §*Why Local
Container GPU Is Still Not Working* applies here: Docker Desktop's
Windows GPU support is NVIDIA-focused and AMD's ROCm container guidance
assumes a native Linux Docker environment.

Expected preflight readout from inside a Docker Desktop container on
this workstation (depending on whether `paddlepaddle-gpu` was installed
inside the container):

- with the CPU wheel inside the container: `state: paddle_cpu_only`.
- with a ROCm wheel inside the container but no `/dev/kfd`:
  `state: gpu_not_exposed`,
  `runtime_device_exposure.dev_kfd_present: false`,
  `runtime_device_exposure.running_in_container: true`.
- with `/dev/kfd` mapped but ROCm cannot find a device:
  `state: gpu_exposed_paddle_cant_bind` with a HIP / ROCm error in
  `ppstructurev3_init_error`.

Run preflight on the WSL host (outside the container) to confirm the
host itself works, then move to a native Linux host for the supported
path.

### Raw Conda

A `paddlepaddle-gpu` install pulled into a Conda environment outside the
Dartwing venv is unsupported. The preflight readout will report
whichever interpreter `python -m dartwing_ocr.preprocessing.preflight`
runs under (`evidence.interpreter_path`); if it is the Conda interpreter
rather than `.venv/bin/python`, the readout will likely show
`paddle_not_installed` (Dartwing is not installed there) or
`paddle_cpu_only` (Conda's `paddlepaddle` channel typically ships a CPU
build). Activate the Dartwing venv and run the supported install path
above instead.

## CI Default Behavior

CI defaults run with no GPU. Tests carrying the `gpu` pytest marker are
**always skipped on CI** (per FR-018, FR-019). The skip mechanism is the
session-scoped fixture in `tests/conftest.py` that calls the same
classifier as the preflight CLI; the resulting `PreflightReadout.state`
drives the skip decision and the skip reason.

The skip-reason format names a specific FR-001 state and quotes the
recommendation string, so a CI log line for a skipped GPU test looks
like:

```text
SKIPPED [1] tests/integration/test_pipeline_gpu_e2e.py::test_gpu_lane_succeeds:
  state=paddle_cpu_only; Install a GPU-enabled paddlepaddle wheel; see
  docs/stage1-vendor-identity/paddle-gpu-preflight.md.
```

To opt into running GPU tests locally on a workstation that passes
preflight:

```bash
.venv/bin/pytest -m gpu
```

If preflight fails on the local workstation, every `gpu`-marked test is
skipped (never failed), with the skip reason traceable to the FR-001
state. This is the documented FR-019 behavior.

## Offline-Operation Knobs

In a fully air-gapped or network-restricted shell, PaddleOCR / PaddleX
cannot reach the BOS hoster
(`paddlepaddle.bj.bcebos.com` / `paddlex.bj.bcebos.com`) for first-run
model weight downloads. Two **verified** offline knobs let the pipeline
operate without that network hop:

1. **`PADDLE_PDX_MODEL_SOURCE` environment variable**. Per the official
   PaddleOCR FAQ at
   <https://www.paddleocr.ai/main/en/FAQ.html>, this variable points
   PaddleX at an alternative model source (mirror or local source).
   Set it before running preflight or the pipeline; it is consumed by
   PaddleX's model resolver, not by Dartwing directly.

2. **PaddleX `model_dir` parameter on each PPStructureV3 sub-module**.
   Per the official PaddleX PP-StructureV3 tutorial at
   <https://paddlepaddle.github.io/PaddleX/3.2/en/pipeline_usage/tutorials/ocr_pipelines/PP-StructureV3.html>,
   each sub-module of the pipeline (layout detector, OCR, table
   recognizer, etc.) accepts a `model_dir` argument that points at a
   pre-downloaded local directory of weights. Pre-download the weights
   on a connected machine, copy the directory to the air-gapped host,
   and pass each sub-module's `model_dir` to point at the local path.

These knobs are orthogonal to the preflight `--no-init` flag.
`--no-init` only suppresses **step 6** of the classifier (the
PPStructureV3 construction itself); it does not affect weight downloads
on its own. Use `--no-init` when you want a partial readout that
classifies up to `gpu_exposed_paddle_cant_bind` without attempting the
PPStructureV3 construction; use `PADDLE_PDX_MODEL_SOURCE` or `model_dir`
when you need PPStructureV3 to actually run offline.

> **Not a real knob**: `PADDLE_DOWNLOAD=0` is **not** part of the
> official PaddleX or PaddleOCR documentation. Earlier internal notes
> referenced it; that wording is incorrect and must not be propagated.
> Use the two verified knobs above instead.

## Cross-References

- Spec §FR-005 — Ollama-process-specific narrowing. Preflight observes
  shared host indicators (`/dev/kfd`, `/dev/dri`,
  `HIP_VISIBLE_DEVICES`, `ROCM_PATH`, `CUDA_VISIBLE_DEVICES`) as
  GPU-runtime exposure evidence under FR-002, but never observes
  Ollama-process-specific signals. Ollama GPU success on this host
  does not imply Paddle GPU readiness; only the classifier's own bind
  probe and PPStructureV3 construction can satisfy
  `ppstructurev3_init_succeeded`. See
  [`../../specs/014-paddle-gpu-preprocessing/spec.md`](../../specs/014-paddle-gpu-preprocessing/spec.md)
  §FR-005.
- Spec §FR-024 — Additive install path. The `paddlepaddle-gpu` wheel
  must NOT land in `requirements.txt` or `pyproject.toml`; the
  workstation install command above is the only documented path. See
  [`../../specs/014-paddle-gpu-preprocessing/spec.md`](../../specs/014-paddle-gpu-preprocessing/spec.md)
  §FR-024.
- Quickstart §0 (install) and §1 (preflight) — the developer-facing
  walkthrough mirrors this doc and references back here for the wheel
  install command and the FR-001 state interpretations. See
  [`../../specs/014-paddle-gpu-preprocessing/quickstart.md`](../../specs/014-paddle-gpu-preprocessing/quickstart.md).
- [`ollama-runtime.md`](./ollama-runtime.md) — already cross-references
  this doc and documents the production-style native Linux ROCm
  container path (`docker/compose.ollama-rocm-linux.yml`) that the
  *Supported Install Path* above relies on for `/dev/kfd` + `/dev/dri`
  exposure conventions.
