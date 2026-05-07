# Ollama Runtime Options

This document records how the repo supports Ollama during stage 1 and what has been verified on the current workstation.

> **See also**: [`paddle-gpu-preflight.md`](./paddle-gpu-preflight.md) — operator-facing diagnostic for the workstation Paddle GPU preprocessing lane (`ppstructurev3@gpu`). Ollama GPU success and Paddle GPU readiness are independent (per spec FR-005); the preflight tool is the documented way to determine whether Paddle can drive the GPU on this host. Run `python -m ledgerlinc_ocr.preprocessing.preflight` to classify the environment into one of six FR-001 states.

## Supported Runtime Paths

The repo now distinguishes local model runtime paths:

- host Ollama in Ubuntu 24.04 WSL
- optional Docker infrastructure container
- Jetson-local Ollama for the edge-fast stack
- workstation GPU model endpoints for `cloud-workstation` validation

The host path remains the default because it is the only path that has been verified to use the AMD GPU on this workstation.

## Default Behavior

The pipeline container defaults to:

- `OLLAMA_BASE_URL=http://${WSL_HOST_IP}:11434` when `WSL_HOST_IP` is resolved at start time (the normal path)
- `OLLAMA_BASE_URL=http://host.docker.internal:11434` as a fallback when `WSL_HOST_IP` is unset

That allows the lightweight pipeline container to call a host-level Ollama service without bundling model serving into the dev container.

### Why The WSL IP Path, Not `host.docker.internal`

`host.docker.internal` is a Docker Desktop alias pointing at Docker Desktop's private host-gateway network (typically `192.168.65.254`). WSL 2 Ubuntu's eth0 lives on a different virtual network (typically `172.25.x.y`). On this workstation the Docker Desktop host-gateway path does not reliably reach host Ollama, while routing from the devcontainer to the WSL distro's own IP does. Using the WSL IP directly avoids the fragile path.

### How `WSL_HOST_IP` Gets Populated

Two entry points resolve the current WSL distro IP before the compose stack starts:

- **VS Code Dev Containers.** `.devcontainer/devcontainer.json` declares an `initializeCommand` that writes `.devcontainer/.env` with `WSL_HOST_IP=$(hostname -I | awk '{print $1}')`. Docker Compose auto-loads that env file.
- **Manual `docker compose up`.** `scripts/devcontainer-up.sh` does the same thing, then invokes `docker compose`. Use this when starting the stack outside VS Code.

`.devcontainer/.env` is gitignored (machine-specific value). WSL eth0 addresses can drift across WSL reboots; re-running either entry point picks up the new IP automatically.

## Local WSL Container Path

The repo also defines an optional `ollama` service in:

- `.devcontainer/docker-compose.yml`

This service is intended for local infrastructure-style testing only. It is behind the Compose profile:

- `ollama`

The local WSL container now includes the best-effort runtime flags for AMD on WSL:

- `/dev/dxg` device mapping
- WSL DXCore library mounts
- ROCm HSA runtime mount
- `SYS_PTRACE`
- `seccomp=unconfined`
- `ipc: host`
- enlarged shared memory

These settings reflect AMD's WSL container guidance more closely than the initial placeholder configuration.

## Verified Findings On This Workstation

The following behavior has been verified locally:

- host WSL ROCm works
- host Ollama detects the AMD GPU
- host Ollama offloads model layers to ROCm
- the optional `ollama` Docker container starts and serves HTTP correctly
- the optional `ollama` Docker container does not detect a ROCm-capable device

The decisive test was a direct HIP probe:

- on the host: `hipGetDeviceCount` returned `count=1`
- in the container: `hipGetDeviceCount` returned `no ROCm-capable device is detected`

This means the failure is below Ollama itself. The container runtime cannot see a usable ROCm device in the current local setup.

## Why Local Container GPU Is Still Not Working

This workstation is using:

- WSL 2
- AMD ROCm via ROCDXG
- Docker Desktop as the Docker engine

Docker Desktop's documented Windows GPU support is NVIDIA-focused, while AMD's ROCm container guidance assumes a native Linux Docker environment. In practice, that leaves this local AMD-on-WSL Docker path unproven and currently non-functional for ROCm GPU inference.

So the current local state should be treated as:

- host Ollama = GPU-capable and usable
- Docker container = functionally running but CPU-only

## Jetson Edge Runtime Path

The `edge-fast` stack targets Jetson Nano Super class hardware. Its extraction
profile is `ollama@jetson` and its Gemma voter config is the smaller Gemma 4
E2B edge profile.

The Jetson lane is not the same as the optional CPU container lane:

- OCR and model inference must use the Jetson GPU path.
- CPU-only model inference is not an acceptable fallback for `ollama@jetson`.
- If the Jetson-local endpoint or GPU path is unavailable, the runner should
  fail fast or route the document to review/full-workstation processing rather
  than silently changing lanes.
- The proposed resolver is `--ollama-jetson-url` >
  `OLLAMA_JETSON_BASE_URL` > the documented Jetson-local default.

## Cloud-Workstation Runtime Path

The `cloud-workstation` stack is the local test path for the future cloud
solution. It runs cloud-class voters on workstation GPU hardware before the
project introduces a remote cloud provider path.

Rules for this lane:

- It is local workstation validation, not remote cloud execution.
- It must not require cloud-provider credentials or external provider APIs.
- Required model endpoints must be checked before artifact writes.
- Runtime metadata must identify the voter set and local workstation lane so
  evaluator reports do not mix these results with `full-workstation` or
  `edge-fast`.

## Production Container Path

For production-style deployment, the repo now includes a native Linux ROCm compose file:

- `docker/compose.ollama-rocm-linux.yml`

That file targets a standard Linux ROCm host and uses:

- `/dev/kfd`
- `/dev/dri`
- `seccomp=unconfined`
- `SYS_PTRACE`
- `ipc: host`
- shared memory sizing

This is the container path that should be used for cloud or real Linux GPU validation, not the WSL Docker Desktop path.

## ROCm Ownership

ROCm remains host-owned in every model:

- the kernel and device access belong to the host
- the container only receives access to those host GPU capabilities

This is true both for WSL and for a future Linux cloud host.

## How To Use The Host Runtime

1. Start Ollama on the WSL host with the repo startup script:

   ```bash
   scripts/start-host-ollama-rocm-wsl.sh
   ```

   Do not start this workstation's GPU lane with plain `ollama serve`.
   The `gfx1151` WSL ROCm path requires the host HSA runtime preload and
   SDMA workaround documented in `../ollama-rocm-wsl-gfx1151-fix.md`.

2. Keep the default `OLLAMA_BASE_URL` when the container can reach the WSL
   host directly. When Docker Desktop cannot route to the WSL IP directly,
   use the network-IP relay URL that resolves to host Ollama.
3. Run the pipeline container unchanged.

No compose override is needed for this path.

### Host Runtime Verification

After startup, verify GPU placement before treating a benchmark or pipeline
run as GPU-backed:

```bash
curl -fsS http://127.0.0.1:11434/api/generate \
  -H 'Content-Type: application/json' \
  -d '{"model":"llama3.2:1b","prompt":"Reply with OK only.","stream":false,"keep_alive":"5m","options":{"num_predict":2,"num_ctx":2048}}'

ollama ps
```

Expected `ollama ps` signal:

```text
PROCESSOR    100% GPU
```

When validating from `py-bench`, query the network-reachable URL, for example:

```bash
export OLLAMA_BASE_URL=http://192.168.1.131:11436
curl -fsS "$OLLAMA_BASE_URL/api/ps"
```

The `api/ps` response should report a non-zero `size_vram` for the loaded
model.

## How To Use The Local Container Runtime

1. Start the optional service with the `ollama` profile.
2. Set `OLLAMA_BASE_URL=http://ollama:11434`.
3. Treat this as a local integration path only.

At present, this path should be assumed CPU-only on this workstation until proven otherwise.

## How To Use The Production Linux ROCm Runtime

1. Provision a native Linux GPU host with AMD ROCm support.
2. Use `docker/compose.ollama-rocm-linux.yml`.
3. Validate GPU visibility on that Linux host before promoting the image.

## Recommendation

For stage 1 development:

- use host Ollama as the working GPU path
- keep the optional local container for API wiring and service topology
- validate the production Ollama container on a native Linux ROCm host, not Docker Desktop on Windows
- validate the `ollama@jetson` lane separately on the Jetson Nano Super target
  before treating edge-fast timings as production-representative
- validate `cloud-workstation` on the workstation GPU cards before planning
  remote cloud fallback or provider-managed deployment

## Extractor timeout + no-retry convention

The stage 1 extractor calls host Ollama via a single `httpx` request per
invocation and never retries. Retries are considered an orchestrator concern
and live outside this pipeline.

- **Transport**: `httpx` only. `requests` is forbidden under `src/ledgerlinc_ocr/extract/` (enforced structurally — see `tests/unit/extract/test_no_downstream_imports.py`).
- **Timeout**: pinned per voter config (`ollama.timeout_seconds`, `ollama.connect_timeout_seconds`). Default profile for `gemma-edge.yaml` lives in `src/ledgerlinc_ocr/extract/voters/configs/gemma-edge.yaml`.
- **No retries**: any `ConnectError`, `ConnectTimeout`, `ReadTimeout`, or other `TransportError` surfaces as `OllamaUnreachable` → exit code 3. `model not found` payloads surface as `OllamaModelUnavailable` → exit code 4. See `specs/005-single-voter-extraction/research.md §R-001` (httpx, no retries) and `§R-002` (timeout).

Rationale: deterministic failure shape is more valuable than opportunistic retry masking. Downstream orchestration (or a human operator) is free to rerun the extractor; the pipeline itself never papers over transport instability.

## Per-Lane Ollama URL Resolution (Feature 011)

The stage 1 controller distinguishes three Ollama runtime lanes for the
extract stage. Each lane has its own CLI flag, environment variable,
and documented default; resolution order is **flag > env > default**:

| Lane | Flag | Env Var | Default URL |
|---|---|---|---|
| `gpu` | `--ollama-url` | `OLLAMA_BASE_URL` | `http://localhost:11434` |
| `cpu` | `--ollama-cpu-url` | `OLLAMA_CPU_BASE_URL` | `http://localhost:11435` |
| `jetson` | `--ollama-jetson-url` | `OLLAMA_JETSON_BASE_URL` | `http://jetson.local:11434` |

The CPU default port `11435` matches the optional CPU container
convention (`docker compose --profile ollama up -d`). The Jetson default
is a placeholder; operators must override it on real hardware. WSL
caveats already documented above remain in effect -- only host Ollama
exposes the AMD GPU.

The controller selects a lane from the resolved extract profile
(`ollama@gpu` / `ollama@cpu` / `ollama@jetson`); changing lanes does
not change artifact filenames or schemas (FR-014). The `ollama@jetson`
lane is recognized at argument validation but its live execution is
deferred to FR-034 step 4. See
`specs/011-stage-runtime-profiles/contracts/cli-contract.md` for the
full CLI surface and
`specs/011-stage-runtime-profiles/research.md` R-012 for the lane
resolution rationale.
