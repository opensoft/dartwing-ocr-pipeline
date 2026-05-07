# Ollama ROCm Fix for WSL Ubuntu 24.04 on AMD gfx1151

Last updated: 2026-04-12T08:10:29-04:00

## Purpose

This document records the fix required to make Ollama use the AMD GPU through ROCm inside WSL on this workstation.

The issue was not a missing ROCm install. ROCm was already healthy in WSL and could see the GPU. The failure was specific to Ollama's deeper ROCm validation path, which filtered the GPU out before inference.

This writeup documents:

- the system context
- the exact failure mode
- the root cause
- the patch applied
- how Ollama was rebuilt and installed
- how GPU use was verified
- rollback and maintenance guidance

## Environment

- Host OS: Windows with WSL2
- Linux distro: Ubuntu 24.04.4 LTS
- GPU path in WSL: `/dev/dxg`
- ROCm version: 7.2.x
- GPU reported by ROCm: `AMD Radeon(TM) 8060S Graphics`
- GPU architecture: `gfx1151`
- Ollama base version installed: `0.20.5`

## Original Symptom

Ollama installed and started correctly, but model inference ran on CPU only.

Observed behavior:

- `rocminfo` reported the AMD GPU correctly.
- HIP and hipBLAS test programs completed successfully.
- `ollama serve` detected the AMD GPU and identified it as `gfx1151`.
- During startup, Ollama logged a GPU discovery failure and then filtered the GPU out.
- `ollama ps` showed `100% CPU` when a model was active.

Representative failure pattern from Ollama debug logging:

- GPU is discovered.
- Deep initialization validation runs.
- Validation does not finish before Ollama's timeout.
- Device is filtered out.
- Model is loaded with CPU inference.

## Why ROCm Itself Was Not the Problem

ROCm was already functional before patching Ollama.

The following checks succeeded:

- `rocminfo`
- `hipconfig --full`
- a small HIP device enumeration test
- a small hipBLAS initialization test

That narrowed the issue to Ollama's GPU selection logic rather than a broken ROCm stack.

## Root Cause

Ollama performs an additional "deep init validation" for ROCm devices before including them in the supported GPU list.

In this WSL configuration:

- the GPU is exposed through `/dev/dxg`
- HIP and hipBLAS initialize successfully
- but Ollama's deeper ggml ROCm preflight can hang long enough to exceed its timeout

When that happens, Ollama assumes the GPU is unsafe and removes it from the usable device list.

The relevant logic is in Ollama source:

- `/tmp/ollama-src/ml/device.go`
- `DeviceInfo.NeedsInitValidation()`

The patched function is at:

- `/tmp/ollama-src/ml/device.go:539`

## Patch Summary

Patch intent:

- keep ROCm validation behavior unchanged on normal Linux systems
- skip the extra deep validation step only for WSL ROCm devices exposed via `/dev/dxg`

Reasoning:

- this workstation already proved that HIP and hipBLAS load successfully
- the failing step was the extra Ollama preflight, not ROCm itself
- skipping that extra filter allows the ROCm runner to start and actually use the GPU

Applied logic:

1. if the device backend is not ROCm, leave behavior unchanged
2. if the device backend is ROCm on Linux and `/dev/dxg` exists, return `false` from `NeedsInitValidation()`
3. otherwise keep the original ROCm validation behavior

Patched code location:

- `/tmp/ollama-src/ml/device.go:539`

Patched block:

```go
func (d DeviceInfo) NeedsInitValidation() bool {
	// ROCm: rocblas will crash on unsupported devices.
	// CUDA: verify CC is supported by the version of the library
	if d.Library == "ROCm" {
		// WSL exposes AMD GPUs through /dev/dxg rather than the native amdgpu/kfd stack.
		// On gfx1151 systems the deeper ggml ROCm preflight can hang even though HIP and
		// hipBLAS initialize successfully, so avoid filtering the device out up front.
		if runtime.GOOS == "linux" {
			if _, err := os.Stat("/dev/dxg"); err == nil {
				return false
			}
		}
		return true
	}

	return d.Library == "CUDA"
}
```

## Build and Install Procedure

### 1. Install the standard Ollama binaries and ROCm userspace

```bash
sudo apt-get update
sudo apt-get install -y zstd golang-go

curl -L https://ollama.com/download/ollama-linux-amd64.tar.zst | sudo tar --zstd -x -C /usr
curl -L https://ollama.com/download/ollama-linux-amd64-rocm.tar.zst | sudo tar --zstd -x -C /usr
```

This installs:

- `/usr/bin/ollama`
- ROCm libraries under `/usr/lib/ollama/rocm`

### 2. Clone Ollama source

```bash
git clone --depth 1 https://github.com/ollama/ollama /tmp/ollama-src
```

### 3. Patch the source

Edit:

- `/tmp/ollama-src/ml/device.go`

### 4. Build a replacement binary

```bash
cd /tmp/ollama-src
go build -trimpath -o /tmp/ollama-patched .
```

### 5. Back up the original binary and install the patched one

```bash
sudo cp /usr/bin/ollama /usr/bin/ollama.orig-0.20.5
sudo install -m 0755 /tmp/ollama-patched /usr/bin/ollama
```

Resulting files on this workstation:

- active binary: `/usr/bin/ollama`
- backup of stock binary: `/usr/bin/ollama.orig-0.20.5`

## Verification Procedure

### A. Confirm ROCm sees the GPU

```bash
rocminfo | rg 'Marketing Name|gfx1151'
hipconfig --full
```

Expected signals:

- `AMD Radeon(TM) 8060S Graphics`
- `gfx1151`

### B. Start Ollama with the required ROCm runtime environment

```bash
scripts/start-host-ollama-rocm-wsl.sh
```

Do not use plain `ollama serve` for this workstation. The patched binary is
still required, but the current ROCm 7.2 / ROCDXG path also requires the host
HSA runtime to be preloaded ahead of Ollama's bundled ROCm libraries:

```bash
HSA_ENABLE_DXG_DETECTION=1
HSA_ENABLE_SDMA=0
ROCM_PATH=/opt/rocm-7.2.0
HIP_PATH=/opt/rocm-7.2.0
LD_PRELOAD=/opt/rocm-7.2.0/lib/libhsa-runtime64.so.1
LD_LIBRARY_PATH=/opt/rocm-7.2.0/lib
```

Without this environment, the runner can offload layers to `ROCm0` and then
hang during model load after the ROCDXG warning:

```text
librocdxg.so: undefined symbol: hsa_signal_store_screlease
```

Expected signals after the patch and startup environment:

- inference compute reports `library=ROCm`
- compute target is `gfx1151`
- `ollama ps` reports `100% GPU` for an active model

### C. Run a model

```bash
/usr/bin/ollama run llama3.2:1b "Respond with the single word: hello"
```

The most reliable confirmation came from the server logs during model load. The patched system logged that layers were assigned to `ROCm0` and that all model layers were offloaded to GPU.

Observed GPU-offload pattern:

- `layer 0 assigned to device ROCm0`
- repeated layer assignments to `ROCm0`
- `offloading 16 repeating layers to GPU`
- `offloading output layer to GPU`
- `offloaded 17/17 layers to GPU`

### D. Inspect the live runner process

The runner process provided direct proof that ROCm was active.

Process shape:

```bash
ps -ef | rg 'ollama serve|ollama runner'
```

Useful live checks:

```bash
rg 'libamdhip64|libhsa-runtime64|libhipblas|libhipblaslt|librocblas|librocdxg' /proc/<runner-pid>/maps
ls -l /proc/<runner-pid>/fd
```

Expected signals:

- mapped ROCm userspace libraries from `/usr/lib/ollama/rocm`
- `/opt/rocm-7.2.0/lib/librocdxg.so`
- open file descriptors to `/dev/dxg`

On this workstation, the live runner showed:

- `libamdhip64.so`
- `libhsa-runtime64.so`
- `libhipblas.so`
- `libhipblaslt.so`
- `librocblas.so`
- `librocdxg.so`
- open descriptors to `/dev/dxg`

That is strong evidence that the runner was executing on ROCm rather than CPU only.

## Notes on `ollama ps`

`ollama ps` is still useful, but it can be easy to miss active placement if the request is very short and the model unloads quickly.

If needed, keep the model resident longer by using a slower prompt or API `keep_alive` so that `ollama ps` has time to show the processor assignment.

## Known Caveat

During GPU load, one warning appeared from `librocdxg.so`:

```text
undefined symbol: hsa_signal_store_screlease
```

This warning is only benign when the required startup environment above is in
place. Without the `LD_PRELOAD` of `/opt/rocm-7.2.0/lib/libhsa-runtime64.so.1`,
the runner can hang at load progress around `0.18` after offloading layers to
`ROCm0`.

This warning should be treated as a compatibility concern to watch, but it did not block GPU inference in this setup.

## Rollback

To revert to the stock Ollama binary:

```bash
sudo cp /usr/bin/ollama.orig-0.20.5 /usr/bin/ollama
```

Then restart the server:

```bash
pkill -f '/usr/bin/ollama serve'
scripts/start-host-ollama-rocm-wsl.sh
```

Expected rollback result:

- Ollama returns to stock behavior
- the original ROCm timeout/filtering behavior may reappear

## Recommended Long-Term Follow-Up

This patch is appropriate as a workstation fix, but it should not remain an undocumented one-off binary replacement.

Recommended next steps:

1. rebuild from a pinned Ollama commit instead of a temporary `/tmp` clone
2. store the patch as a maintained diff or forked branch
3. retest when upgrading Ollama
4. check whether upstream Ollama fixes WSL ROCm deep validation for `gfx1151`
5. check whether future ROCm releases remove the need for this WSL-specific bypass

## Quick Reference

### Active files

- patched source: `/tmp/ollama-src/ml/device.go`
- active binary: `/usr/bin/ollama`
- stock backup: `/usr/bin/ollama.orig-0.20.5`
- startup script: `scripts/start-host-ollama-rocm-wsl.sh`

### Key commands

```bash
rocminfo | rg 'Marketing Name|gfx1151'
scripts/start-host-ollama-rocm-wsl.sh
/usr/bin/ollama run llama3.2:1b "Respond with the single word: hello"
ollama ps
ps -ef | rg 'ollama serve|ollama runner'
rg 'libamdhip64|libhsa-runtime64|libhipblas|libhipblaslt|librocblas|librocdxg' /proc/<runner-pid>/maps
ls -l /proc/<runner-pid>/fd
```

## Outcome

After patching and rebuilding Ollama, the AMD GPU became usable for inference in WSL Ubuntu 24.04 on this `gfx1151` system.

The decisive outcome was that Ollama's runner loaded ROCm libraries, opened `/dev/dxg`, and offloaded all model layers to `ROCm0`.
