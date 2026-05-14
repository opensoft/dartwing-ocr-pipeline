# GPU Warmup and MIOpen / COMGR Cache

**Audience**: workstation operators running `ppstructurev3@gpu` with the `--gpu-warmup` opt-in.
**Scope**: covers the five US4 Independent Test items per spec.md SC-009 — cache locations, clearance procedure, `MIOPEN_FIND_MODE` rationale, workspace-warning meaning + operator guidance, and how to read `phase_timings.warmup` as cold-vs-warm signal.
**Feature**: 016-gpu-warmup-miopen-cache. See `specs/016-gpu-warmup-miopen-cache/spec.md` for the contract; `specs/016-gpu-warmup-miopen-cache/quickstart.md` for the end-to-end verification walkthrough.

---

## TL;DR

When you set `--gpu-warmup` (or `DARTWING_GPU_WARMUP=1`) on a `ppstructurev3@gpu` run, the pipeline runs one PPStructureV3 inference against `tests/stage1_vendor_identity/inv_001_easy/source.pdf` BEFORE the first timed document, populating MIOpen's kernel-selection database (`~/.cache/miopen`) and COMGR's HIP shader cache (`~/.cache/comgr`). The duration is reported as `phase_timings.warmup = {seconds: <float>}` on the first successful per-document `run_summary` entry — separate from `phase_timings.total` so per-document numbers reflect steady-state OCR cost.

If you re-run on the same workstation without clearing the caches, `phase_timings.warmup.seconds` should be **at least 2× smaller** (per SC-003) — that's the cold-vs-warm signal.

**Installed-distribution note**: the warmup fixture default resolves relative to the repo's `tests/` tree, which is not shipped as package data. If you run an installed distribution (the `tests/` tree is not on disk), set `DARTWING_WARMUP_FIXTURE_PATH=/absolute/path/to/source.pdf` to point at any local PDF (any single-page invoice will do — the fixture is used purely to drive PPStructureV3's kernel-selection path; it is not part of the per-document OCR output). Without this override, `--gpu-warmup` will fail-fast with `WarmupError(cause_class="FixtureLoadError")` and exit 15.

---

## 1. Cache locations

The pipeline interacts with two on-disk OS caches during a warmup-enabled GPU run:

| Directory | What lives there | How its location is controlled |
|---|---|---|
| `~/.cache/miopen` | MIOpen kernel database, find-mode tuning artifacts | Pipeline sets both `MIOPEN_USER_DB_PATH` and `MIOPEN_CUSTOM_CACHE_DIR` to this path inside `preprocessing/warmup.py::_apply_env_defaults` (operator override wins). |
| `~/.cache/comgr` | HIP / ROCm compiler (COMGR) cache (compiled shader binaries) | **Filesystem-default location used by the AMD COMGR library — not controlled by any pipeline-set env var.** Operators who need a non-default path must use whatever knob the local ROCm/COMGR build exposes (typically `XDG_CACHE_HOME` or distribution-specific configuration). |

Both directories are managed by AMD ROCm libraries — the pipeline does not write into them directly. They are populated as a side effect when MIOpen or COMGR runs (during warmup or per-document inference).

## 2. How to clear them deliberately

```bash
# Cold-cache reset (for verification, ROCm version bumps, or
# investigating a suspected cache-state regression):
rm -rf ~/.cache/miopen ~/.cache/comgr
```

After clearing, the next `--gpu-warmup` run will pay full kernel-selection cost (the "cold" run). Sequential runs after that should hit the warm cache.

**When to clear**:
- After a ROCm version bump (cached kernels may not match the new runtime).
- After a `paddleocr` / `paddlepaddle-dcu` package version bump.
- When investigating a `phase_timings.warmup.seconds` value that looks unexpectedly high or low.
- Before running the cold-vs-warm verification per `quickstart.md` §1.

**Clear `~/.cache/comgr` only**:

```bash
rm -rf ~/.cache/comgr
# MIOpen kernel-selection DB stays warm; COMGR re-compiles shaders.
```

This is useful for the US2 acceptance scenario #3 (verifying that `phase_timings.warmup.seconds` rises measurably from a fully-warm baseline when COMGR alone is cleared).

## 3. `MIOPEN_FIND_MODE` rationale

The pipeline ships **`MIOPEN_FIND_MODE=2`** (Fast find) as the default for warmup-enabled GPU runs, set inside `preprocessing/warmup.py::_apply_env_defaults` only if the variable is not already set (operator override wins per FR-015 / R-016.4).

Mode comparison:

| Mode | Name | What it does | Why we don't use it |
|---|---|---|---|
| 1 | Full search | Exhaustive kernel benchmarking on every cache miss | Far too slow for inline warmup — minutes per cold run |
| **2** | **Fast (default)** | **Heuristic + cached lookup; falls back to fast benchmark on miss** | **Used as default — fast warmup, accurate enough** |
| 3 | Hybrid | Mix of fast + full | Marginal benefit over mode 2 for this stage 1 workload |
| 4 | Cache-only | No kernel search; errors on miss | Fails on first cold run AND any post-driver-update run |

The default value of `2` is appropriate for production-style GPU runs. Operators may override (e.g., temporarily set mode 1 to populate a richer kernel database for benchmarking) — the pipeline preserves operator-set values.

If workstation evidence at landing time shows that mode 2 is materially worse than another mode for this gfx1151 + V3 workload, the FR-015 amendment hook applies: update `research.md` R-016.4 + spec FR-015 + this doc before merge.

## 4. Workspace-warning meaning + operator guidance

The pipeline applies a **hybrid policy** for MIOpen/COMGR runtime warnings per FR-016 (clarified in /speckit.clarify Q3):

### 4a. Warnings addressed by default config

The pipeline ships these env-var defaults (set only when each is unset — operator override wins). Each suppresses a specific class of MIOpen/COMGR runtime workspace warning by giving the runtime a deterministic configuration to use:

| Env var | Default | Suppresses |
|---|---|---|
| `MIOPEN_FIND_MODE` | `2` | "find_mode_db not initialized" runtime info |
| `MIOPEN_USER_DB_PATH` | `${HOME}/.cache/miopen` | "MIOpen could not determine user db path" |
| `MIOPEN_CUSTOM_CACHE_DIR` | `${HOME}/.cache/miopen` | "custom cache dir not set" |
| `MIOPEN_LOG_LEVEL` | `2` | High-volume per-kernel info traces (errors + warnings only) |

These four env vars are applied by `preprocessing/warmup.py` only on the GPU branch (FR-011 / I-6 — never on CPU/stub paths). If you have set any of them yourself before invoking the pipeline, your value is preserved.

### 4b. Residual / known runtime diagnostics

The following warnings are inherent to the AMD ROCm + MIOpen + COMGR runtime and may still appear on stderr during a warmup-enabled run. They are **not** errors — they are diagnostics. **Do not act on them unless the run also fails or `phase_timings.warmup.seconds` looks wrong.** This list will be refined at workstation-verification landing time per `quickstart.md` Appendix B / T026.

(*This list is filled in at workstation verification time; until T026 lands, treat the absence of entries here as "no observed residuals on the verification host" rather than as a contract that there are none.*)

| Warning text | Meaning | Operator action |
|---|---|---|
| _(filled by T026 / quickstart.md Appendix B)_ | _(filled at landing)_ | _(filled at landing)_ |

If you observe a warning that looks like a real failure — for example, MIOpen reporting that the kernel database is corrupt, or COMGR reporting that it cannot write its cache — see § 6 (Recovery) below.

## 5. How to read `phase_timings.warmup` as a cold-vs-warm signal

Every warmup-enabled `ppstructurev3@gpu` run that completes successfully emits a `phase_timings.warmup` entry on the first per-document `run_summary` entry whose `status == "success"`:

```jsonc
{
  "kind": "run_summary",
  "schema_version": "0.1.3",
  "per_document": [
    {
      "document_id": "inv_001_easy",
      "status": "success",
      "phase_timings": {
        "paddle_import":     {"seconds": 0.04},      // ← feature 015
        "gpu_bind_probe":    {"seconds": 0.02},      // ← feature 015
        "engine_init":       {"seconds": 1.5},       // ← feature 015
        "warmup":            {"seconds": <VALUE>},   // ← feature 016 — read THIS
        "rasterization":     {"seconds": 0.1},
        "artifact_write":    {"seconds": 0.05},
        "total":             {"seconds": 0.45}       // ← does NOT include warmup
      },
      "per_page_inference": [{"page": 1, "seconds": 0.3}]
    }
  ]
}
```

### Interpretation

| `phase_timings.warmup.seconds` | Likely cache state | Notes |
|---|---|---|
| **High** (e.g., > 5 s on this gfx1151 workload) | Cold cache | MIOpen ran full kernel selection, COMGR compiled shaders. Expected on first run after `rm -rf ~/.cache/miopen ~/.cache/comgr` or after a ROCm version bump. |
| **Low** (significantly below the cold value, typically < cold/2 per SC-003) | Warm cache | Cache hits served the warmup pass. Expected on second-or-later runs. |
| **Mid-range** (e.g., comgr cleared but miopen warm) | Mixed | After `rm -rf ~/.cache/comgr` only. COMGR recompiles shaders; MIOpen kernel-selection is cached. |
| **Suspiciously low cold value** (e.g., < 1 s on first run after full clear) | Possible MIOpen/COMGR misconfiguration | Caches may not actually be writing. Check the env vars in § 4a are set as expected. |
| **`warmup` key absent** | Warmup did not run | Either the opt-in was not set, the active profile was not `ppstructurev3@gpu`, or warmup failed (look for `error: warmup failed:` on stderr — see § 6). |

`phase_timings.total` is the per-document inference time and does NOT include warmup duration (FR-007 / SC-004). Reading per-document latency from `total` is therefore "steady-state OCR cost only" — the whole reason warmup exists.

The legacy flat keys `stages.preprocess.{total_seconds, gpu_init_seconds, gpu_inference_seconds}` from feature 014 also exclude warmup time (FR-009). If you're reading both legacy and structured emissions, you cannot accidentally double-count warmup.

## 6. Recovery: what to do when warmup keeps failing

If a warmup-enabled run exits with `15` and stderr `error: warmup failed: <cause-class>: <message>`, the cause class indicates triage steps:

| `cause_class` | What it means | First thing to try |
|---|---|---|
| `FixtureLoadError` | Couldn't load `tests/stage1_vendor_identity/inv_001_easy/source.pdf` | Verify the fixture exists at the expected path; re-clone the corpus if missing |
| `ClockAnomaly` | `time.perf_counter()` returned a non-positive elapsed value | Almost never seen in practice; check clock skew / virtualization timing |
| `MIOpenError` | The underlying exception's module starts with `MIOpen` or `comgr` | Likely a kernel-DB corruption or cache-write failure. Try: `rm -rf ~/.cache/miopen ~/.cache/comgr` and retry once |
| `PaddleError` | The underlying exception's module starts with `paddle*` (paddleocr / paddlex / paddlepaddle) | Likely a model-weight issue or paddle-internal failure. Re-check that `paddlepaddle-dcu` is installed (`pip show paddlepaddle-dcu`) and run the preflight (`python -m dartwing_ocr.preprocessing.preflight`) |
| `UnknownError` | Anything else (catch-all per data-model.md §WarmupError) | Capture stderr + the `cause_module` field; if reproducible, file an issue with the underlying exception class |

**Cache state after `WarmupError`**: the on-disk caches at `~/.cache/miopen` and `~/.cache/comgr` may be **partially populated** by MIOpen/COMGR before the underlying exception was raised. The pipeline does NOT attempt to clean up or roll back. If the failure looks cache-related (e.g., `MIOpenError` referencing a kernel-DB read), clearing both caches and retrying once is a reasonable first step. If the failure persists, do NOT keep retrying with cleared caches — investigate the cause class first.

**Do not silent-fall-back**: the pipeline never silently downgrades a failed warmup-enabled run to a no-warmup run (FR-007 / SC-011). If you want to proceed without warmup after a failure, re-invoke the pipeline without `--gpu-warmup` (and without `DARTWING_GPU_WARMUP=1`).

## 7. Activation surface (CLI flag + env var)

Per `contracts/cli-contract.md` §1, the warmup opt-in has two equivalent activation surfaces:

| Surface | Form | Default | Wins when both set |
|---|---|---|---|
| CLI flag | `--gpu-warmup` (boolean; no `=value`) | absent (off) | yes |
| Env var | `DARTWING_GPU_WARMUP` | unset (off) | no |

**Truthy env values** (after `.strip().lower()`): `{"1", "true", "yes"}` only. Anything else (including `2`, `on`, `enabled`, `off`, empty) is silently treated as off — NOT an error. This whitelist is intentional: it keeps shared CI env vars from accidentally activating warmup on unrelated stages.

**On non-GPU profiles**: setting the opt-in via either surface emits a single stderr line containing the literal `--gpu-warmup ignored:` and proceeds with the run as if the opt-in were not set (FR-010 / SC-007 / /speckit.clarify Q1). No MIOpen env vars are set; no `~/.cache/miopen` access; no `preprocessing.warmup` module imported.

## 8. Related documentation

- [`paddle-gpu-preflight.md`](paddle-gpu-preflight.md) — feature 014 GPU preflight and exit codes 10–14
- [`ollama-runtime.md`](ollama-runtime.md) — host vs container Ollama; complementary GPU concerns
- `specs/016-gpu-warmup-miopen-cache/spec.md` — full feature spec
- `specs/016-gpu-warmup-miopen-cache/quickstart.md` — end-to-end verification walkthrough (cold-cache run, warm-cache run, comgr-only-cleared run, CPU/stub no-op, failure-injection)
- `specs/016-gpu-warmup-miopen-cache/contracts/cli-contract.md` — exit codes, stderr contracts, activation surfaces
- `specs/016-gpu-warmup-miopen-cache/contracts/run-summary-schema.md` — `phase_timings.warmup` shape and presence rules
- `specs/016-gpu-warmup-miopen-cache/data-model.md` — `WarmupError` cause-class taxonomy and activation truth table
