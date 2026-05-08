# Data Model: GPU Warmup And MIOpen Cache Stabilization

**Feature**: 016-gpu-warmup-miopen-cache
**Date**: 2026-05-08

This feature is observability-and-side-effect heavy: it adds a single new in-process function call, one new exception, one additive run_summary key, and a small set of OS env-var defaults. There are no new persisted artifacts. The entities below describe the stable in-process and on-disk surfaces this feature introduces or extends.

## Entity: WarmupPass

A single, deterministic PPStructureV3 inference invocation whose only purpose is to populate MIOpen kernel-selection caches and COMGR compilation caches. Conceptual entity — has no persistent representation; manifests at runtime as one `engine.predict(np_img)` call inside `preprocessing/warmup.run_warmup()`.

| Field | Type | Source | Notes |
|---|---|---|---|
| engine | `paddleocr.PPStructureV3` | reference handed in by caller (the singleton from `preprocessing/ocr._ENGINE`) | MUST be the already-adopted engine (FR-003); never constructs a second engine |
| fixture_path | `pathlib.Path` | default = `tests/stage1_vendor_identity/inv_001_easy/source.pdf` (R-016.2) | Optional override for tests; `run_warmup` raises `WarmupError` (cause class `FixtureLoadError`) if unreadable |
| fixture_sha256 | `str` (64 hex chars) | computed once at module import | Diagnostic only — never appears in `run_summary` (R-016.8) |
| invocation_count | `int` | module-level `_WARMUP_RAN` flag, derived | MUST equal 1 for the lifetime of the process when warmup is opt-in (FR-001 / FR-004); subsequent calls return cached `WarmupResult` |
| timing_clock | `time.perf_counter` | hard-coded in `run_warmup` | Monotonic; six-decimal-rounded at serialization (FR-006) |

**Invariants**:
- `invocation_count <= 1` per process.
- The engine's PPStructureV3 *constructor* is never called by `run_warmup` (preserves feature 015 SC-001 / FR-001).
- The clock used is `time.perf_counter()` (monotonic-ish, highest resolution); converted to seconds via `round(elapsed, 6)` at serialization.

## Entity: WarmupResult

Frozen dataclass returned by `run_warmup()`. Internal — never serialized into any artifact directly. Two of its fields cross into the run_summary surface (`seconds` becomes `phase_timings.warmup.seconds`); the others are diagnostic.

```python
@dataclass(frozen=True)
class WarmupResult:
    seconds: float            # six-decimal-rounded perf_counter delta around engine.predict(...)
    fixture_sha256: str       # sha256 of the loaded fixture image bytes (diagnostic)
    fixture_path: pathlib.Path  # the resolved path used (diagnostic)
```

**Validation rules**:
- `seconds > 0.0` always (clock-jitter-anomaly handling: if `perf_counter` returns `<= 0`, raise `WarmupError` cause `ClockAnomaly`).
- `fixture_sha256` is the sha256 of the rasterized PIL image bytes, not of the source PDF (so a future PDF-loader change that produces the same pixels still hashes identically).

## Entity: WarmupError

New exception class in `src/ledgerlinc_ocr/preprocessing/errors.py`. Mirrors the `EngineInitError` shape used by feature 010/014.

```python
class WarmupError(RuntimeError):
    def __init__(self, message: str, *, cause_class: str, cause_module: str) -> None:
        super().__init__(message)
        self.cause_class = cause_class
        self.cause_module = cause_module
```

**Cause-class taxonomy** (the values that flow through the `cause_class` attribute and into the stderr `warmup failed: <cause-class>: <message>` line per FR-007):

| `cause_class` | When raised |
|---|---|
| `FixtureLoadError` | The default warmup fixture (R-016.2) cannot be loaded — missing file, IO error, pypdfium2 error, PIL error |
| `ClockAnomaly` | `time.perf_counter()` returns a non-positive elapsed value |
| `MIOpenError` | The underlying `engine.predict` raised an exception whose module name starts with `MIOpen` or `comgr` |
| `PaddleError` | The underlying `engine.predict` raised any other paddle/paddleocr/paddlex exception |
| `UnknownError` | Anything else — preserves the original exception's `type(exc).__module__` for triage |

The `cause_module` field captures `type(original_exc).__module__` verbatim, so operators triaging a stderr `warmup failed: MIOpenError: <message>` line have a path back to the originating module.

**Stability stance**: the cause-class taxonomy above is a **closed set** for stage 1 — the five values (`FixtureLoadError`, `ClockAnomaly`, `MIOpenError`, `PaddleError`, `UnknownError`) are part of the public contract. Tests, monitoring, and downstream consumers MAY assert that `WarmupError.cause_class` is always one of these five strings. `UnknownError` is the explicit catch-all for any exception whose module does not match the routing rules of `MIOpenError` (module prefix `MIOpen*` or `comgr*`) or `PaddleError` (paddle/paddleocr/paddlex modules); adding a sixth class would be a feature-level decision, not an implementation choice. If a future feature needs more granularity (e.g., separating `MIOpenKernelDBError` from `MIOpenAllocationError`), it MUST extend this taxonomy via spec amendment with a corresponding `schema_version` patch bump in `pipeline/timing.py`.

## Entity: `phase_timings.warmup` (run_summary additive key)

The single observable surface added to the existing `kind: "run_summary"` stdout shape (feature 011 / 014 / 015 lineage).

**Shape**: `{ "seconds": <float> }`. No other keys. Six-decimal-rounded.

**Location**: under `phase_timings` on the **first per-document `run_summary` entry whose `status == "success"`** (the same entry feature 015 attaches `paddle_import` / `gpu_bind_probe` / `engine_init` to, per feature 015 FR-015). Never on a failure entry. Never on the second-or-later per-document entry.

**Presence rules** (FR-007 / SC-002 / SC-005):

| Condition | `phase_timings.warmup` |
|---|---|
| Warmup opt-in absent | absent |
| Warmup opt-in set, profile is not `ppstructurev3@gpu` (CPU/stub) | absent |
| Warmup opt-in set, profile is `ppstructurev3@gpu`, warmup completed successfully | present on first successful per-doc entry |
| Warmup opt-in set, profile is `ppstructurev3@gpu`, warmup raised `WarmupError` | absent (process exited non-zero before any document was timed; no run_summary emitted) |
| Warmup opt-in set, warmup succeeded, but every per-doc inference failed | absent (per FR-006: attached to "first per-document entry whose `status == "success"`"; no such entry exists) |

**Excluded from**: `phase_timings.total`, `phase_timings.rasterization`, `phase_timings.per_page_inference[*].seconds`, `phase_timings.artifact_write` (FR-007 / SC-004). Excluded from legacy flat keys `stages.preprocess.{total_seconds, gpu_init_seconds, gpu_inference_seconds}` (FR-009).

## Entity: `RunSummary.SCHEMA_VERSION` (codebase-level bump)

Codebase-level transition driven by this feature: `"0.1.2"` → `"0.1.3"`. Set in `src/ledgerlinc_ocr/pipeline/timing.py` (the single source of truth). Every run of the new binary emits `schema_version: "0.1.3"` regardless of whether warmup ran (R-016.9 / FR-008 / /speckit.clarify Q2). The 0.1.3 schema is a strict superset of 0.1.2: it adds the optional `warmup` key under `phase_timings`. Existing 0.1.2 keys (`paddle_import`, `gpu_bind_probe`, `engine_init`, `rasterization`, `per_page_inference`, `artifact_write`, `total`) MUST NOT be renamed, removed, or have their type changed (FR-008).

## Entity: MIOpen / COMGR cache state (on-disk side effect)

Two operator-clearable directories. Not owned by the pipeline; this feature configures them and reads their effect through `phase_timings.warmup.seconds` magnitude.

| Directory | Set via env var | What lives there | When operator clears |
|---|---|---|---|
| `~/.cache/miopen` | `MIOPEN_USER_DB_PATH` (R-016.5) | MIOpen kernel database + find-mode tuning artifacts | After ROCm version bump; when investigating cold-vs-warm regression; when `phase_timings.warmup.seconds` looks suspicious |
| `~/.cache/comgr` | `MIOPEN_CUSTOM_CACHE_DIR` (R-016.5) | HIP/ROCm compiler (COMGR) cache | Same triggers as above |

**Cold cache** = both directories absent or empty (or populated under an incompatible ROCm/driver/PPStructureV3 configuration). **Warm cache** = both directories populated by a prior compatible run. Detection in production code MUST be via `phase_timings.warmup.seconds` magnitude (per Definitions in spec.md), NOT via filesystem inspection — this avoids race conditions and keeps the cache an opaque OS-level surface.

## Entity: Default env-var configuration shipped by this feature

Applied by `preprocessing/warmup.run_warmup()` at the start of execution, only when the GPU warmup path is taken (not on CPU/stub per FR-011), and only when the operator has not already set the variable (operator override wins per R-016.4 / R-016.5).

| Env var | Default | FR-016 disposition | Purpose |
|---|---|---|---|
| `MIOPEN_FIND_MODE` | `2` | addressed by default config | Fast find (R-016.4) |
| `MIOPEN_USER_DB_PATH` | `${HOME}/.cache/miopen` | addressed by default config | Suppress "user db path undetermined" workspace warning |
| `MIOPEN_CUSTOM_CACHE_DIR` | `${HOME}/.cache/miopen` | addressed by default config | Suppress "custom cache dir not set" workspace warning |
| `MIOPEN_LOG_LEVEL` | `2` | addressed by default config | Errors + warnings only (quiets per-kernel info traces) |

The full "addressed by default config" + "residual / known diagnostic" split (per /speckit.clarify Q3 hybrid policy) is finalized at landing time via the workstation verification run and recorded in `docs/stage1-vendor-identity/gpu-warmup-and-cache.md` (the US4 / FR-017 deliverable).

## Entity: Activation-surface state machine

The opt-in surface decision made in R-016.1, expressed as a two-input → three-state truth table that the CLI parser implements. Inputs are `--gpu-warmup` (CLI flag) and `LEDGERLINC_GPU_WARMUP` (env var). CLI wins over env per R-016.1.

| `--gpu-warmup` flag | `LEDGERLINC_GPU_WARMUP` env | Active profile | Behavior |
|---|---|---|---|
| absent | unset / empty / `0` / `false` / `no` | any | warmup opt-in OFF |
| absent | `1` / `true` / `yes` (case-insensitive) | `ppstructurev3@gpu` | warmup opt-in ON; warmup runs |
| absent | `1` / `true` / `yes` | `ppstructurev3@cpu` or stub | warmup opt-in ON, no-op'd; stderr warn-and-proceed line emitted (FR-010) |
| present | (ignored — CLI wins) | `ppstructurev3@gpu` | warmup opt-in ON; warmup runs |
| present | (ignored) | `ppstructurev3@cpu` or stub | warmup opt-in ON, no-op'd; stderr warn-and-proceed line emitted (FR-010) |

The env-var truthiness parser is case-insensitive and rejects ambiguous values (e.g., `LEDGERLINC_GPU_WARMUP=2` is treated as unset, not as "very on"). Strict whitelist: `{"1", "true", "yes"}` after `.strip().lower()`.

## Out-of-scope entities (intentionally not modeled)

- **Multi-pass warmup** — FR-001 / FR-004 cap it at exactly one pass.
- **Per-stage-shape warmup** — single canonical fixture per R-016.2 covers stage 1; multi-shape is a follow-up feature.
- **Persisted warmup-result artifact** — explicitly forbidden by FR-019 unless `/speckit.plan` produces evidence the run_summary is insufficient. This research did not produce such evidence.
- **Programmatic cold/warm cache detection in production code** — Definitions section of spec rules this out: detection is via `phase_timings.warmup.seconds` magnitude, not via filesystem inspection.
