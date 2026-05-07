# Paddle ROCm Source Build

This document is the current workstation path for making
`ppstructurev3@gpu` real on the AMD ROCm WSL host.

## Current Status

Status as of 2026-05-06:

- A ROCm-enabled Paddle wheel has been built from Paddle `v3.3.1` source.
- The wheel is installed only in `.venv-paddle-rocm`; the project `.venv`
  remains unchanged.
- `scripts/verify-paddle-rocm-runtime.sh .venv-paddle-rocm/bin/python`
  succeeds with `state: paddle_rocm_bind_succeeded`,
  `compiled_with_rocm: true`, `device_count: 1`, and a tensor probe on
  `gpu:0`.
- Full LedgerLinc preflight succeeds with
  `state: ppstructurev3_init_succeeded` and selected device `gpu:0`.
- A temp one-document GPU preprocess pipeline run completed and wrote a
  schema-valid `preprocess_output.json` with
  `pipeline_version` ending in `.gpu0`, non-empty document text, 3 layout
  blocks, and 33 OCR lines.

Measured temp run:

```text
inv_001_easy/source.pdf
real 103.53s
pipeline_version stage1-preprocess-v0.2.0+paddleocr3.5.0.0000000.dpi300.gpu0
```

MIOpen emits workspace warnings during inference on this host. They did not
block output, but they are a performance signal: the current path is usable for
proof and development, not yet optimized for benchmark speed.

The workstation ROCm runtime itself is visible:

- ROCm path: `/opt/rocm-7.2.0`
- WSL GPU device: `/dev/dxg`
- GPU architecture: `gfx1151`
- GPU marketing name: `AMD Radeon(TM) 8060S Graphics`

The package issue is not CUDA versus ROCm naming. Paddle's Python GPU API
uses strings like `gpu:0`, but the build must be compiled with ROCm/HIP for
this AMD device. Installing a CUDA `paddlepaddle-gpu` wheel will not fix this
host.

## Why Source Build

For Paddle 3.3.x, the public Linux wheel table currently publishes CPU and
CUDA wheels. A public Linux x86_64 Python 3.12 ROCm/HIP wheel matching
PaddleOCR/PaddleX was not found.

The Paddle v3.3.1 source does contain a ROCm build switch:

- `WITH_ROCM=ON`
- `WITH_GPU=OFF`

`WITH_GPU` is the CUDA path and Paddle rejects enabling CUDA and ROCm together.
With `WITH_ROCM=ON`, Paddle names the Python wheel `paddlepaddle-dcu`.

The v3.3.1 ROCm CMake also assumes an older ROCm layout and hard-codes older
offload targets (`gfx906`, `gfx926`, `gfx928`, `gfx936`). The local build
wrapper patches those source-build assumptions for ROCm 7.x and `gfx1151`.

## Local Source Patches

The wrapper applies the workstation patches every time `prepare`, `configure`,
or `build` runs, so the external Paddle checkout can be refreshed without
losing the fixes.

Current patch set:

- Paddle ROCm CMake: supports ROCm 7.x flat include/library layout and derives
  HIP offload targets from `AMDGPU_TARGETS` instead of hard-coded Hygon/Instinct
  targets.
- Vendored `warpctc` and `warprnnt`: applies the same ROCm 7.x layout and
  `gfx1151` offload target handling to the external projects.
- Host-only Thrust guards: keeps ROCm Thrust system headers out of ordinary
  host C++ translation units in `paddle/phi/common/complex.h`,
  `paddle/phi/core/enforce.h`, and `paddle/fluid/platform/enforce.h`.
- ROCm component includes: rewrites older nested include paths for `hipblas`,
  `hiprand`, `rocblas`, `rocsparse`, `rocrand`, `rocsolver`, and `hipsolver`
  to the ROCm 7 flat headers.
- HIP 7 pointer attributes: uses the current `hipPointerAttribute_t.type`
  field.
- ROCm driver dynload: instantiates Paddle's declared HIP virtual-memory and
  graph dynamic-loader wrappers, including `hipMemCreate` and `hipMemRelease`.
- ROCm allocator headers: avoids CUDA driver allocator headers in the ROCm
  allocator facade path.
- hipBLAS complex scalars: uses `rocblas_float_complex` and
  `rocblas_double_complex` for host-side scalar construction.
- `values_vectors_functor.h`: keeps the Thrust device-vector implementation
  inside HIP translation units.
- Bundled Thrust shuffle shims: removes stale ROCm-internal includes/macros
  that no longer exist in ROCm 7.x.
- rocPRIM traits: defines traits for Paddle `float16` and `bfloat16` before
  argsort, top-k, and mode kernels use ROCm 7 `rocprim` primitives.
- Top-k wave64 fix: sizes the shared-memory `shared_max` array by rounded-up
  warp count so HIP wave64 builds do not instantiate a zero-length array when
  Paddle uses `BlockSize=32`.
- Build/runtime packaging fixes: include ROCm's LLVM runtime library path,
  set `SKIP_STUB_GEN=ON`, install the Python packaging dependencies needed by
  Paddle's wheel builder, and generate/copy
  `paddle.incubate.autograd.phi_ops_map` before packaging.

## Build Wheel

Run from the repository root on the WSL host, not from `py-bench`:

```bash
scripts/build-paddle-rocm-wheel.sh configure
```

If configure succeeds, build the wheel:

```bash
CMAKE_BUILD_PARALLEL_LEVEL=4 scripts/build-paddle-rocm-wheel.sh build
```

The build runs outside the repository by default:

```text
~/.cache/ledgerlinc/paddle-rocm/
```

The resulting wheel is copied to:

```text
~/.cache/ledgerlinc/paddle-rocm/wheelhouse/
```

The script intentionally does not modify the project `.venv`.

The successful local wheel currently lands at:

```text
~/.cache/ledgerlinc/paddle-rocm/wheelhouse/paddlepaddle_dcu-3.3.0.dev20260319-cp312-cp312-linux_x86_64.whl
```

## Build Variables

Common overrides:

| Variable | Default | Meaning |
|----------|---------|---------|
| `PADDLE_TAG` | `v3.3.1` | Paddle source tag to build. |
| `ROCM_PATH` | `/opt/rocm-7.2.0` | ROCm install root. |
| `AMDGPU_TARGETS` | `gfx1151` | HIP offload architecture list. |
| `PYTHON_BIN` | `python3.12` | Python ABI used for the wheel. |
| `PADDLE_HOST_CC` | `$ROCM_PATH/llvm/bin/amdclang` | Host C compiler. Required because ROCm headers can enter normal Paddle C++ translation units. |
| `PADDLE_HOST_CXX` | `$ROCM_PATH/llvm/bin/amdclang++` | Host C++ compiler. |
| `CMAKE_BUILD_PARALLEL_LEVEL` | half of `nproc`, minimum 2 | Build parallelism. |

Do not use the system GCC build directory for ROCm. GCC can configure the
top-level project, but normal Paddle C++ files may include ROCm `rocprim`
headers and fail on AMD GPU builtins. The wrapper defaults to a clean
`build-v3.3.1-rocm-amdclang` directory for this reason.

## Install Into An Isolated Test Venv

After a wheel exists, install it into a separate test venv:

```bash
python3.12 -m venv .venv-paddle-rocm
.venv-paddle-rocm/bin/pip install -U pip
.venv-paddle-rocm/bin/pip install -e ".[dev]" --no-deps
.venv-paddle-rocm/bin/pip install paddleocr==3.5.0 "paddlex[ocr]==3.5.1"
.venv-paddle-rocm/bin/pip uninstall -y paddlepaddle
.venv-paddle-rocm/bin/pip install ~/.cache/ledgerlinc/paddle-rocm/wheelhouse/paddlepaddle-dcu*.whl
.venv-paddle-rocm/bin/pip install "numpy>=1.24,<2.4" "Pillow>=10.4,<11" "pypdfium2>=4.30,<5"
```

Keep `.venv` unchanged until `.venv-paddle-rocm` passes the checks below.

## Verify Runtime Bind

```bash
scripts/verify-paddle-rocm-runtime.sh .venv-paddle-rocm/bin/python
```

Expected successful state:

```text
paddle_rocm_bind_succeeded
```

Then run the LedgerLinc preflight:

```bash
PYTHONPATH=src .venv-paddle-rocm/bin/python -m ledgerlinc_ocr.preprocessing.preflight --no-init
```

Only after `--no-init` succeeds should you run the full PPStructureV3 init:

```bash
PYTHONPATH=src .venv-paddle-rocm/bin/python -m ledgerlinc_ocr.preprocessing.preflight
```

## Run One GPU Pipeline Document

The pipeline adapter expects a per-document folder containing `source.pdf`.
For a temp proof run:

```bash
rm -rf /tmp/ledgerlinc-gpu-pipeline-doc
mkdir -p /tmp/ledgerlinc-gpu-pipeline-doc/inv_001_easy
cp tests/stage1_vendor_identity/inv_001_easy/source.pdf \
  /tmp/ledgerlinc-gpu-pipeline-doc/inv_001_easy/source.pdf

export ROCM_PATH=/opt/rocm-7.2.0
export HIP_PATH=/opt/rocm-7.2.0
export HSA_ENABLE_DXG_DETECTION=1
export HSA_ENABLE_SDMA=0
export MIOPEN_FIND_MODE=2
export PATH=/opt/rocm-7.2.0/bin:/opt/rocm-7.2.0/llvm/bin:$PATH
export LD_LIBRARY_PATH=/opt/rocm-7.2.0/lib:/opt/rocm-7.2.0/lib/llvm/lib:${LD_LIBRARY_PATH:-}
export LD_PRELOAD=/opt/rocm-7.2.0/lib/libhsa-runtime64.so.1${LD_PRELOAD:+:$LD_PRELOAD}

/usr/bin/time -p .venv-paddle-rocm/bin/python -m ledgerlinc_ocr.pipeline run \
  --document-folder /tmp/ledgerlinc-gpu-pipeline-doc/inv_001_easy \
  --preprocess-profile ppstructurev3@gpu \
  --start-at preprocess --stop-after preprocess \
  --overwrite
```

Verify the lane stamp and schema:

```bash
.venv-paddle-rocm/bin/python - <<'PY'
import json, re
p = "/tmp/ledgerlinc-gpu-pipeline-doc/inv_001_easy/preprocess_output.json"
data = json.load(open(p))
print(data["pipeline_version"])
assert re.search(r"\.gpu\d+$", data["pipeline_version"])
PY

PYTHONPATH=src .venv-paddle-rocm/bin/python -m ledgerlinc_ocr.validator \
  validate artifact \
  /tmp/ledgerlinc-gpu-pipeline-doc/inv_001_easy/preprocess_output.json \
  --contract preprocess_output \
  --contract-set-version 1.2.0
```

## Container Boundary

Do not use `py-bench` as proof of Paddle GPU readiness on this workstation.
The current WSL Docker Desktop path does not expose a native ROCm device stack
to the container. Build and first validation happen on the WSL host.

After the host can bind Paddle to `gpu:0`, the project can decide whether to
move this into a native Linux ROCm container. That is separate from the current
Docker Desktop `py-bench` setup.
