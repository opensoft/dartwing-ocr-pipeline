# Ollama Runtime Options

This document records how the repo supports Ollama during stage 1 and what has been verified on the current workstation.

## Supported Runtime Paths

The repo now supports two Ollama runtime paths:

- host Ollama in Ubuntu 24.04 WSL
- optional Docker infrastructure container

The host path remains the default because it is the only path that has been verified to use the AMD GPU on this workstation.

## Default Behavior

The pipeline container defaults to:

- `OLLAMA_BASE_URL=http://host.docker.internal:11434`

That allows the lightweight pipeline container to call a host-level Ollama service without bundling model serving into the dev container.

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

1. Start Ollama on the host.
2. Keep the default `OLLAMA_BASE_URL`.
3. Run the pipeline container unchanged.

No compose override is needed for this path.

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

## Extractor timeout + no-retry convention

The stage 1 extractor calls host Ollama via a single `httpx` request per
invocation and never retries. Retries are considered an orchestrator concern
and live outside this pipeline.

- **Transport**: `httpx` only. `requests` is forbidden under `src/ledgerlinc_ocr/extract/` (enforced structurally — see `tests/unit/extract/test_no_downstream_imports.py`).
- **Timeout**: pinned per voter config (`ollama.timeout_seconds`, `ollama.connect_timeout_seconds`). Default profile for `gemma-edge.yaml` lives in `src/ledgerlinc_ocr/extract/voters/configs/gemma-edge.yaml`.
- **No retries**: any `ConnectError`, `ConnectTimeout`, `ReadTimeout`, or other `TransportError` surfaces as `OllamaUnreachable` → exit code 3. `model not found` payloads surface as `OllamaModelUnavailable` → exit code 4. See `specs/005-single-voter-extraction/research.md §R-001` (httpx, no retries) and `§R-002` (timeout).

Rationale: deterministic failure shape is more valuable than opportunistic retry masking. Downstream orchestration (or a human operator) is free to rerun the extractor; the pipeline itself never papers over transport instability.
