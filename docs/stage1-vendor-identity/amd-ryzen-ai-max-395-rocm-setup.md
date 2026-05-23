# AMD Ryzen AI Max+ 395 ROCm Setup

This runbook brings up a second AMD Ryzen AI Max+ 395 workstation for the
Dartwing stage 1 GPU MVP path:

- Paddle / PPStructureV3 preprocessing on ROCm
- host Ollama extraction on ROCm
- the feature 021 readiness gates
- a one-document GPU smoke run

It is written for machines similar to the current workstation: Ryzen AI
Max+ 395 / Radeon 8060S class hardware, Python 3.12, Ubuntu 24.04, and the
stage 1 demo profile using `ppstructurev3@gpu` plus `ollama@gpu`.

## Supported Shapes

Use one of these host shapes:

| Host shape | Status | Notes |
|------------|--------|-------|
| Native Ubuntu 24.04 on Ryzen AI Max+ 395 | Preferred | Matches AMD's current Ryzen APU ROCm install path. Use `/dev/kfd` and `/dev/dri` for native containers. |
| Windows + WSL Ubuntu 24.04 with ROCDXG | Supported for this workstation class | Matches the current development workstation. GPU serving must run on the WSL host, not inside Docker Desktop. |
| Docker Desktop container on WSL | Not a GPU validation path | The container may serve HTTP, but AMD ROCm GPU exposure through Docker Desktop on WSL is not reliable for this repo. |

If this machine is native Linux, follow the native Linux section first. If
it is Windows with WSL, follow the WSL section first.

## 1. Confirm The Hardware And OS

On the target machine:

```bash
uname -a
lsb_release -a 2>/dev/null || cat /etc/os-release
lspci | rg -i 'vga|display|amd|radeon' || true
```

After ROCm is installed, the binding check is:

```bash
rocminfo | rg 'Marketing Name|Name:|gfx'
```

Expected Ryzen AI Max+ 395 class signals are:

- architecture: `gfx1151`
- marketing name similar to `Radeon 8060S Graphics`, `Radeon 8050S Graphics`,
  or another Strix Halo / Ryzen AI Max GPU label

`rocm-smi` is useful on native Linux. On WSL it can report driver/module
errors even when ROCm compute is healthy, so do not use `rocm-smi` as the
deciding gate on WSL.

## 2A. Native Ubuntu 24.04 ROCm Install

Follow AMD's current "Install Ryzen Software for Linux with ROCm" guide for
the exact package version for the day you provision the machine. At the time
this runbook was written, AMD's ROCm 7.2.1 Ryzen matrix lists Ubuntu 24.04.4
and Ryzen AI Max+ 395 / `gfx1151` as supported.

The native Linux shape is:

```bash
sudo apt update
sudo apt install -y linux-oem-24.04
sudo reboot
```

After reboot:

```bash
uname -r
sudo apt update
wget https://repo.radeon.com/amdgpu-install/7.2.1/ubuntu/noble/amdgpu-install_7.2.1.70201-1_all.deb
sudo apt install ./amdgpu-install_7.2.1.70201-1_all.deb
sudo amdgpu-install -y --usecase=rocm --no-dkms
sudo usermod -a -G render,video "$LOGNAME"
sudo reboot
```

Then verify:

```bash
groups
rocminfo | rg 'Marketing Name|Name:|gfx1151|gfx1150'
```

If the target has large unified memory, also inspect AMD's `amd-ttm` guidance
for shared-memory sizing. The default can be too conservative for large local
LLMs.

## 2B. Windows + WSL ROCm Install

Use this path when the machine is a Windows workstation running Ubuntu under
WSL2.

1. Install the current AMD Adrenalin driver for WSL2 that AMD's ROCm Ryzen
   WSL guide points to.
2. Install Ubuntu 24.04 under WSL2.
3. Follow AMD's ROCDXG quickstart from the `ROCm/librocdxg` repo.
4. Install ROCm userspace in the WSL distro.

For the older WSL package path, AMD's Radeon WSL guide uses:

```bash
sudo apt update
wget https://repo.radeon.com/amdgpu-install/7.2/ubuntu/noble/amdgpu-install_7.2.70200-1_all.deb
sudo apt install ./amdgpu-install_7.2.70200-1_all.deb
sudo amdgpu-install -y --usecase=wsl,rocm --no-dkms
```

On current Ryzen WSL guidance, ROCDXG is the important layer: WSL compute goes
through `/dev/dxg`, and the Windows display driver remains the real driver.

Verify:

```bash
test -e /dev/dxg && echo "WSL GPU device present"
rocminfo | rg 'Marketing Name|Name:|gfx'
```

If ROCm installs into a versioned directory other than `/opt/rocm-7.2.0`,
record it:

```bash
ls -d /opt/rocm* 2>/dev/null
```

Use that directory as `ROCM_ROOT` in the later commands.

## 3. Install System Tools

Install the basic host tools used by this repo's readiness scripts:

```bash
sudo apt update
sudo apt install -y \
  build-essential \
  cmake \
  curl \
  git \
  jq \
  pkg-config \
  python3.12 \
  python3.12-venv \
  python3.12-dev \
  ripgrep \
  zstd
```

Install mikefarah `yq` v4 on the host path. The Ollama readiness helper uses
`yq` to resolve the active voter config.

```bash
mkdir -p "$HOME/.local/bin"
curl -fsSL https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 \
  -o "$HOME/.local/bin/yq"
chmod +x "$HOME/.local/bin/yq"
export PATH="$HOME/.local/bin:$PATH"
yq --version
```

Persist the path if needed:

```bash
printf '\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$HOME/.bashrc"
```

If `opensoft/model-paddle` release assets require GitHub authentication on the
new machine, install and authenticate GitHub CLI before the Paddle wheel step:

```bash
if command -v gh >/dev/null; then
  gh auth status || gh auth login
else
  echo "Install GitHub CLI before downloading private release assets."
fi
```

## 4. Clone The Repo

Use the repo checkout on the target machine:

```bash
git clone git@github.com:opensoft/dartwing-ocr-pipeline.git
cd dartwing-ocr-pipeline
git status -sb
```

If SSH is not configured, use the HTTPS URL that matches the GitHub remote.

## 5. Create The ROCm Paddle Venv

Keep ROCm Paddle isolated from the normal CPU `.venv`.

```bash
python3.12 -m venv .venv-paddle-rocm
.venv-paddle-rocm/bin/pip install -U pip setuptools wheel
.venv-paddle-rocm/bin/pip install -e ".[dev]" --no-deps
.venv-paddle-rocm/bin/pip install paddleocr==3.5.0 "paddlex[ocr]==3.5.1"
.venv-paddle-rocm/bin/pip uninstall -y paddlepaddle
```

Install the ROCm/DCU Paddle wheel that matches this host and Python 3.12. The
wheel is produced and published from `opensoft/model-paddle`; the pipeline
repo consumes the wheel but does not build it.

Current tested wheel for this workstation class:

- release: `paddle-v3.3.1-rocm7.2-gfx1151-py312`
- asset: `paddlepaddle_dcu-3.3.0.dev20260319-cp312-cp312-linux_x86_64.whl`

If a newer `model-paddle` release supersedes that asset, use the newer
release but keep the same constraints: Python 3.12, ROCm 7.2 class runtime,
and `gfx1151`.

```bash
mkdir -p /tmp/paddle-rocm
gh release download paddle-v3.3.1-rocm7.2-gfx1151-py312 \
  -R opensoft/model-paddle \
  -p 'paddlepaddle_dcu-*.whl' \
  -p SHA256SUMS \
  -D /tmp/paddle-rocm

cd /tmp/paddle-rocm
sha256sum -c SHA256SUMS --ignore-missing
cd -

.venv-paddle-rocm/bin/pip install \
  /tmp/paddle-rocm/paddlepaddle_dcu-3.3.0.dev20260319-cp312-cp312-linux_x86_64.whl
```

If `gh` is not authenticated on the new machine, download the release asset
from `opensoft/model-paddle` in a browser or build the wheel locally from that
repo, then install the local `.whl` path with the same `pip install` command.

Do not add this wheel to `requirements.txt` or `pyproject.toml`. GPU
enablement is host-specific.

## 6. Export Runtime Environment

Set the ROCm runtime variables before running Paddle or Ollama on the WSL
host. If the machine installed a different ROCm directory, change `ROCM_ROOT`.

```bash
export PYTHONPATH=src
export ROCM_ROOT="${ROCM_ROOT:-/opt/rocm-7.2.0}"
export HSA_ENABLE_DXG_DETECTION=1
export HSA_ENABLE_SDMA=0
export ROCM_PATH="$ROCM_ROOT"
export HIP_PATH="$ROCM_ROOT"
export LD_PRELOAD="$ROCM_ROOT/lib/libhsa-runtime64.so.1"
export LD_LIBRARY_PATH="$ROCM_ROOT/lib:$ROCM_ROOT/lib/llvm/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export MIOPEN_FIND_MODE=2
export PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
```

On native Linux, keep `ROCM_ROOT`, `ROCM_PATH`, `HIP_PATH`,
`LD_LIBRARY_PATH`, `MIOPEN_FIND_MODE`, and
`PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK`. The WSL-only variables are
`HSA_ENABLE_DXG_DETECTION`, `HSA_ENABLE_SDMA`, and the HSA runtime
`LD_PRELOAD`; use them only if the native host actually needs them.

`MIOPEN_FIND_MODE=2` is important for this repo's smoke tests. Without it,
PPStructureV3 can spend a very long time inside exhaustive MIOpen convolution
algorithm search.

## 7. Run Paddle GPU Preflight

From the repo root:

```bash
PYTHONPATH=src .venv-paddle-rocm/bin/python -m dartwing_ocr.preprocessing.preflight
```

Pass condition:

```text
state: ppstructurev3_init_succeeded
selected_device: gpu:0
visible_device_count: 1
```

If this fails, do not run the demo yet. Fix the preflight state first. See
`paddle-gpu-preflight.md` for the six failure states and the remediation path.

## 8. Install And Start Host Ollama

Install Ollama on the host:

```bash
curl -L https://ollama.com/download/ollama-linux-amd64.tar.zst | sudo tar --zstd -x -C /usr
curl -L https://ollama.com/download/ollama-linux-amd64-rocm.tar.zst | sudo tar --zstd -x -C /usr
```

For WSL `gfx1151`, this repo expects host Ollama to be started with the
wrapper script:

```bash
ROCM_ROOT="${ROCM_ROOT:-/opt/rocm-7.2.0}" scripts/start-host-ollama-rocm-wsl.sh
```

Do not use plain `ollama serve` for the WSL GPU lane. The wrapper sets the
ROCm and ROCDXG environment that prevented CPU-only or hanging Ollama runs on
the current workstation.

On native Linux, you may use a normal service or `ollama serve`, but the
readiness gate below is still authoritative. If Ollama is CPU-only, the gate
will fail.

Load the demo extraction model:

```bash
OLLAMA_HOST=http://127.0.0.1:11434 ollama run gemma4:e4b ""
```

## 9. Run Ollama GPU Readiness

The readiness helper checks the same model selected by `ollama@gpu` via
`configs/voter/ollama-gpu.yaml`.

```bash
scripts/check-ollama-gpu-readiness.sh \
  --voter-config configs/voter/ollama-gpu.yaml \
  --base-url http://127.0.0.1:11434
```

Pass condition:

```json
{"status":"pass","model_name":"gemma4:e4b","size":13004151040,"size_vram":13004151040}
```

The exact `size` can change with model version. The important condition is:

```text
size_vram > 0 AND size_vram == size
```

If the model is not listed in `/api/ps`, load it again with `ollama run`. If
`size_vram` is zero or smaller than `size`, restart Ollama with the ROCm path
fixed before continuing.

## 10. Run A One-Document GPU Smoke

Pick one real test-corpus PDF and write it to a scratch docs file. Example:

```bash
mkdir -p /tmp/021-bench/smoke
find tests/stage1_vendor_identity -name '*.pdf' | sort | head -n 1 \
  > /tmp/021-bench/smoke/docs.txt
cat /tmp/021-bench/smoke/docs.txt
```

Run the GPU pipeline:

```bash
PYTHONPATH=src .venv-paddle-rocm/bin/python -m dartwing_ocr.pipeline run \
  --documents-file /tmp/021-bench/smoke/docs.txt \
  --preprocess-profile ppstructurev3@gpu \
  --preprocess-strategy ocr-only-v1 \
  --extract-profile ollama@gpu \
  --evidence-gate-skip-fallback
```

Expected result:

- command exits 0
- each document folder has the four stage 1 artifacts
- stdout ends with a `kind: "run_summary"` JSON line
- run summary identifies the GPU preprocessing and `ollama@gpu` extraction
  path

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `yq not found on PATH` | Host helper dependency missing | Install mikefarah `yq` and export `$HOME/.local/bin` on `PATH`. |
| `No module named dartwing_ocr` | Repo package not installed or `PYTHONPATH` missing | Run from repo root with `PYTHONPATH=src`, or reinstall `.venv-paddle-rocm/bin/pip install -e ".[dev]" --no-deps`. |
| `libomp.so` or LLVM runtime missing | ROCm LLVM lib path not visible | Include `$ROCM_ROOT/lib/llvm/lib` in `LD_LIBRARY_PATH`. |
| Paddle preflight reports CPU-only | Wrong Paddle wheel | Remove CPU `paddlepaddle`; install the ROCm/DCU `paddlepaddle_dcu` wheel for Python 3.12. |
| Paddle sees zero devices | GPU not exposed to this process | On native Linux verify `render,video` groups and `/dev/kfd`/`/dev/dri`; on WSL verify `/dev/dxg` and ROCDXG. |
| Pipeline appears stuck during first GPU document | MIOpen exhaustive algorithm search | Export `MIOPEN_FIND_MODE=2` before running. |
| `rocm-smi` says driver not initialized on WSL | WSL does not expose the native amdgpu driver stack | Use `rocminfo`, Paddle preflight, and Ollama `/api/ps` as the gates. |
| Ollama readiness exits 2 | Extraction model is not loaded | Run `OLLAMA_HOST=http://127.0.0.1:11434 ollama run gemma4:e4b ""`. |
| Ollama readiness exits 1 | Model is partially or fully on CPU | Restart Ollama with ROCm environment; on WSL use `scripts/start-host-ollama-rocm-wsl.sh`. |
| Docker container cannot see AMD GPU on WSL | Docker Desktop WSL ROCm path is not validated | Run GPU services on the WSL host, or move to native Linux ROCm containers. |

## References

- AMD ROCm Ryzen native Linux install and support matrix:
  <https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/install/installryz/native_linux/install-ryzen.html>
- AMD ROCm Ryzen native Linux compatibility:
  <https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/compatibility/compatibilityryz/native_linux/native_linux_compatibility.html>
- AMD ROCm Ryzen WSL / ROCDXG guide:
  <https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/install/installryz/wsl/howto_wsl.html>
- Existing Dartwing GPU preflight reference:
  `docs/stage1-vendor-identity/paddle-gpu-preflight.md`
- Existing Dartwing Ollama runtime reference:
  `docs/stage1-vendor-identity/ollama-runtime.md`
- Existing WSL `gfx1151` Ollama notes:
  `docs/ollama-rocm-wsl-gfx1151-fix.md`
