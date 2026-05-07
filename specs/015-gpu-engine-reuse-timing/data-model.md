# Phase 1 Data Model: GPU Engine Reuse And Phase Timing

This document captures the entities and module-level invariants that change in this feature. The spec's stage 1 artifact contracts (`preprocess_output.json` etc.) are **unchanged** (FR-010); the entities below are pipeline-internal run-metadata and runtime-engine state.

## Entities

### GPU Readiness Result (`PreflightReadout`)

Process-scoped, cached outcome of "is Paddle GPU usable on this host for this profile."

| Field | Type | Notes |
|---|---|---|
| `state` | `PreflightState` enum | One of the six FR-001 states; unchanged. |
| `evidence.interpreter_path` | str | Existing. |
| `evidence.interpreter_version` | str | Existing. |
| `evidence.venv_path` | str \| None | Existing. |
| `evidence.paddle_version` | str \| None | Existing. |
| `evidence.paddleocr_version` | str \| None | Existing. |
| `evidence.paddle_compiled_with_cuda` | bool \| None | Existing. |
| `evidence.paddle_compiled_with_rocm` | bool \| None | Existing. |
| `evidence.visible_device_count` | int \| None | Existing. |
| `evidence.selected_device` | str \| None | Existing (e.g., `"gpu:0"`). |
| `evidence.runtime_device_exposure` | dict[str, bool] | Existing six-key dict. |
| `evidence.paddle_import_seconds` | float \| None | **NEW (R-015.2)**. Seconds spent in `import paddle` during step 2. None when classify exited before step 2. |
| `evidence.gpu_bind_probe_seconds` | float \| None | **NEW (R-015.2)**. Seconds spent in step 5 (`paddle.device.set_device("gpu:0") + to_tensor probe`). None when classify exited before step 5 or the probe failed before timing was captured. |
| `evidence.ppstructurev3_init_seconds` | float \| None | Existing. Now mirrors the value persisted into `phase_timings.engine_init` on the first per-document run_summary entry. |
| `evidence.ppstructurev3_init_error` | str \| None | Existing. |
| `evidence.ppstructurev3_init_skipped_reason` | str \| None | Existing. |
| `recommendation` | str | Existing. |

**State transitions**: unchanged from feature 014 — six FR-001 states with the existing classify() ladder. Adding the two timing fields does not change state semantics.

**Cache**: `_LAST_READOUT` (process-scoped, set by `_make_readout`). Unchanged behavior; `ensure_gpu_ready()` continues to short-circuit on cached `PPSTRUCTUREV3_INIT_SUCCEEDED`.

### Reusable PPStructureV3 Engine (`ocr._ENGINE`)

Process-scoped singleton; constructed at most once per process per FR-001 / SC-001.

| Slot | Type | Notes |
|---|---|---|
| `ocr._ENGINE` | `paddleocr.PPStructureV3` \| None | Existing module-level singleton. |
| `ocr._ENGINE_DEVICE` | str \| None | Existing. Set on first construction; locks the device. CF4 single-device-per-process guard unchanged. |

**Invariant CF4 (single-device-per-process, preserved from feature 014)**: Once `_ENGINE_DEVICE` is set, any `_get_engine(device=other)` call where `other != _ENGINE_DEVICE` MUST raise `RuntimeError`.

**New invariant CF5 (engine reuse across preflight + runtime)**: After `classify(attempt_ppstructurev3_init=True)` succeeds with `state = PPSTRUCTUREV3_INIT_SUCCEEDED`, `ocr._ENGINE` MUST be the engine instance that was constructed in classify step 6 (not `None`, not a different instance), and `ocr._ENGINE_DEVICE` MUST equal `"gpu:0"`. Subsequent `ocr._get_engine(device="gpu:0")` calls MUST return that same instance (verifiable by `id(...)` in tests).

**New helper `ocr._adopt_engine(engine, device)`**: tiny one-way cross-module setter used by `preflight.classify()` to populate `_ENGINE` / `_ENGINE_DEVICE` and set `_PADDLE_SEEDED = True`. Avoids preflight reaching into ocr's globals directly. Never imported by any other module; not part of the public API.

### Phase timing record (per per-document run_summary entry)

This is the central new entity. Carried inside the existing `kind: "run_summary"` stdout line on each `per_document[*]` element. Schema source of truth: `pipeline/timing.py` `RunSummary` dataclass + `build_per_document_success` / `build_per_document_failure`.

#### Top-level shape (additive on per_document entries)

```json
{
  "document_id": "inv_001_easy",
  "folder": "tests/stage1_vendor_identity/inv_001_easy",
  "status": "success",
  "stages": { "preprocess": { "total_seconds": 102.7, "gpu_init_seconds": 41.2, "gpu_inference_seconds": 18.5 } },

  "phase_timings": {
    "paddle_import":   { "seconds": 1.42 },
    "gpu_bind_probe":  { "seconds": 0.04 },
    "engine_init":     { "seconds": 41.21 },
    "rasterization":   { "seconds": 1.13 },
    "artifact_write":  { "seconds": 0.05 },
    "total":           { "seconds": 102.71 }
  },
  "per_page_inference": [
    { "page": 1, "seconds": 8.43 },
    { "page": 2, "seconds": 7.91 }
  ]
}
```

The `stages` block is the **legacy** flat form (kept for back-compat per R-015.4); the `phase_timings` + `per_page_inference` blocks are the **new structured** form.

#### `phase_timings` keys (R-015.4)

> Canonical vocabulary is defined in `spec.md §FR-013`. The table below is derived from that list.

| Key | One-time | Per-document | When emitted |
|---|---|---|---|
| `paddle_import` | yes | — | First successful per_document entry only, GPU lane only. |
| `gpu_bind_probe` | yes | — | First successful per_document entry only, GPU lane only. |
| `engine_init` | yes | — | First successful per_document entry only, GPU lane only. |
| `warmup` | yes (optional) | — | **Reserved** (Q2 / FR-013): omitted in feature 015; key absent unless some other code path performs warmup. |
| `rasterization` | — | yes | Every per_document entry (success or failure) where rasterization started. |
| `artifact_write` | — | yes | Every successful per_document entry. Omitted on failure entries that aborted before artifact write. |
| `total` | — | yes | Every per_document entry (success or failure). Always emitted, since the outer measure_total context manager runs even on exception. |

CPU lane: only `rasterization`, `artifact_write`, `total` are present. The four GPU one-time keys MUST NOT appear on a CPU lane run (FR-017).

Failure entries (R-015.5): keys for phases that did not run are **omitted**, not zeroed. For example, a doc that fails inference on page 2 emits `rasterization`, `total`, and partial `per_page_inference` (one entry, page 1 — page 2 entry omitted because predict raised before timing was captured).

Each value is the literal object `{"seconds": <float>}` — durations are six-decimal-rounded `time.perf_counter()` deltas. The wrapper object (rather than a bare float) leaves room to add fields like `pages_processed` in a future feature without another schema bump.

#### `per_page_inference` shape (R-015.3)

JSON array of objects in document page order:

```json
[ { "page": 1, "seconds": 8.43 }, { "page": 2, "seconds": 7.91 } ]
```

- `page`: 1-based integer matching `preprocess_output.json` page numbering.
- `seconds`: float (six-decimal-rounded `time.perf_counter()` delta) for that page's `engine.predict(np_img)` call.
- Order: matches the document's natural page order (1, 2, 3, …). Skipped pages (e.g., a rasterization failure on a single page in a multi-page doc) do **not** create entries; the consumer can detect a gap by comparing to `preprocess_output.json`'s `pages[].page_number`.

CPU lane: array MUST be omitted entirely (FR-017) — CPU inference is reported under `total` only.

#### `RunSummary.SCHEMA_VERSION`

`"0.1.1"` → `"0.1.2"` (R-015.4). Patch bump because purely additive.

### Run summary (`RunSummary`)

| Field | Type | Notes |
|---|---|---|
| `kind` | const `"run_summary"` | Unchanged. |
| `schema_version` | str | `"0.1.2"` (was `"0.1.1"`). |
| `stack_preset` | str \| None | Unchanged. |
| `resolved_profiles` | dict[Stage, str] | Unchanged. |
| `execution_slice` | dict[str, str] | Unchanged. |
| `on_failure` | str | Unchanged. |
| `documents_total` | int | Unchanged; for single-doc CLI runs this is `1` (R-015.6). |
| `documents_succeeded` | int | Unchanged. |
| `documents_failed` | int | Unchanged. |
| `profile_initialization_seconds` | dict[Stage, float] | Unchanged. |
| `preprocess_lane` | str | Unchanged (`"cpu"` or `"gpu0"`). |
| `per_document` | list[dict] | Each element gains optional `phase_timings` and `per_page_inference` keys per the shapes above. |

## Module invariants (summary)

| ID | Statement | Asserted by |
|---|---|---|
| CF4 | `_ENGINE` is bound to one device per process; conflicting bind raises. | Existing `_get_engine` check. Tests in feature 014. |
| CF5 | After successful classify-with-init, `ocr._ENGINE is the preflight engine`. | New test `test_preflight_engine_persistence.py`. |
| Q3-shape | Each phase_timings value is `{"seconds": <float>}`. Per-page inference is `[{"page": <int>, "seconds": <float>}, …]` with 1-based pages. | New test `test_phase_timings_unit.py`. |
| Q5-failure | A failed-doc per_document entry carries partial `phase_timings` and (when applicable) partial `per_page_inference`. Phases not performed are omitted, not zeroed. | New test `test_failure_phase_timings.py`. |
| Q1/Q2 | No phase timings written to `preprocess_output.json`. No new stdout `kind`. No synthetic warmup pass. | Existing contract tests (preprocess_output.json schema unchanged) + new `test_run_summary_schema_0_1_2.py`. |
| Q4 / SC-007 | Process exits ≤ 10 s on GPU-prereq failure. | New regression test using `time.perf_counter` around CLI subprocess. |
