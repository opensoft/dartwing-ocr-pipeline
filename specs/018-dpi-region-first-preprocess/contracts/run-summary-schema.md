# Run-Summary Schema: DPI Reduction And Region-First Vendor Identity Preprocess

**Feature**: 018-dpi-region-first-preprocess
**Applies to**: `kind: "run_summary"` JSON object emitted on stdout by `python -m ledgerlinc_ocr.preprocessing` and `python -m ledgerlinc_ocr.pipeline`
**Decision source**: research.md R-018.8, R-018.14; spec FR-008, FR-009, FR-010, FR-011, FR-022; /speckit.clarify Q4.

## 1. Schema version

`RunSummary.SCHEMA_VERSION` patches **0.1.4 → 0.1.5** on this feature. The bump is codebase-level (in `pipeline/timing.py`); the `kind: "run_summary"` JSON object's top-level `schema_version` field reflects it on every run regardless of profile or preset selection.

| Version | Set by feature | Additive change |
|---|---|---|
| 0.1.0 | feature 011 | initial run_summary surface |
| 0.1.1 | feature 014 | added `paddle_import`, `gpu_bind_probe`, `engine_init`, `rasterization`, `per_page_inference`, `artifact_write`, `total` (phase_timings shape) |
| 0.1.2 | feature 015 | additional phase_timings refinements (single-engine guarantee infrastructure) |
| 0.1.3 | feature 016 | added `phase_timings.warmup` |
| 0.1.4 | feature 017 | added `module_set_id`, `det_rec_variant_id`, `ppstructure_modules_invoked` |
| **0.1.5** | **feature 018 (this feature)** | **added `raster_profile_id`, `region_strategy_id`, `region_strategy_fallback_count`** |

Every bump in this table is additive-only — no existing field has been renamed, removed, or retyped (FR-022).

## 2. Top-level field set after feature 018

Top-level fields on the `kind: "run_summary"` object (in deterministic emission order — append-only):

| Field | Type | Source feature | Default | Notes |
|---|---|---|---|---|
| `kind` | `str` | pre-014 | `"run_summary"` | discriminator |
| `schema_version` | `str` | pre-014 | `"0.1.5"` (this feature) | always emitted |
| `paddle_import` | `float` (seconds) | feature 014 | — | wall-clock |
| `gpu_bind_probe` | `float` (seconds) | feature 014 | — | wall-clock |
| `engine_init` | `float` (seconds) | feature 014 | — | wall-clock |
| `warmup` | `float` (seconds) | feature 016 | — | wall-clock; `0.0` if `--gpu-warmup` not set |
| `rasterization` | `float` (seconds) | feature 014 | — | wall-clock; combined cost on fallen-back documents per R-018.10 |
| `per_page_inference` | `float` (seconds) | feature 014 | — | wall-clock; combined cost on fallen-back documents per R-018.10 |
| `artifact_write` | `float` (seconds) | feature 014 | — | wall-clock |
| `total` | `float` (seconds) | feature 014 | — | wall-clock |
| `module_set_id` | `str` | feature 017 | `"cpu-default"` | always emitted |
| `det_rec_variant_id` | `str` | feature 017 | `"cpu-default"` | always emitted |
| `ppstructure_modules_invoked` | `list[str]` | feature 017 | `[]` | always emitted; values from `AUDIT_SUB_MODULE_VOCABULARY` |
| **`raster_profile_id`** | **`str`** | **feature 018** | `"cpu-default"` | always emitted (FR-008 / FR-011) |
| **`region_strategy_id`** | **`str`** | **feature 018** | `"cpu-default"` | always emitted (FR-008 / FR-011) |
| **`region_strategy_fallback_count`** | **`int`** | **feature 018** | `0` | always emitted (FR-009 / Clarifications Q4) |

Per FR-010 / FR-022, no existing field is renamed, removed, or retyped by this feature.

## 3. New field semantics

### `raster_profile_id: str`

The active rasterization-DPI preset name for this run. Values at landing:

| Value | When emitted |
|---|---|
| `"legacy"` | `ppstructurev3@gpu` runs without `--raster-profile` set (or with `--raster-profile=legacy`) |
| `"reduced-v1"` | `ppstructurev3@gpu` runs with `--raster-profile=reduced-v1` set |
| `"cpu-default"` | `ppstructurev3@cpu` runs (any value of `--raster-profile`; flag warn-and-proceed-ignored per FR-014) |
| `"stub-default"` | stub-adapter runs (any value of `--raster-profile`) |

**Stability**: human-readable string, lowercase, ASCII, no whitespace. The set of valid values is the closed `RASTER_PROFILES.keys()` — adding a future preset is a code change.

### `region_strategy_id: str`

The active region-strategy preset name for this run. Values at landing:

| Value | When emitted |
|---|---|
| `"full-page"` | `ppstructurev3@gpu` runs without `--region-strategy` set (or with `--region-strategy=full-page`) |
| `"header-first-v1"` | `ppstructurev3@gpu` runs with `--region-strategy=header-first-v1` set |
| `"cpu-default"` | `ppstructurev3@cpu` runs (any value of `--region-strategy`; flag warn-and-proceed-ignored per FR-014) |
| `"stub-default"` | stub-adapter runs (any value of `--region-strategy`) |

**Stability**: human-readable string, lowercase, ASCII, no whitespace. The set of valid values is the closed `REGION_STRATEGIES.keys()` — adding a future preset is a code change.

### `region_strategy_fallback_count: int`

The count of documents in this run that triggered the FR-007 fallback (per R-018.8). Per Clarifications Q4 / I-018.10:

- Granularity: per-document (one increment per document, regardless of how many pages would have been processed).
- Range: `[0, N]` where `N` is the number of documents processed in this run.
- Always emitted with default `0` on every run kind, including:
  - `region_strategy_id == "full-page"` (no fallback path active).
  - `region_strategy_id == "cpu-default"` or `"stub-default"` (no fallback path active).
  - `region_strategy_id == "header-first-v1"` runs where no document triggered the trigger (clean pass).
- Only `region_strategy_id == "header-first-v1"` runs can have a value `> 0`.

**Per-document attribution**: not encoded on `run_summary` — recoverable from `preprocess_output.json.pages[]` shape per Clarifications Q4 (a fallen-back document has `pages.length == page_count` with all pages populated; a clean `header-first-v1` multi-page document has `pages[0]` populated and `pages[1..N]` as empty records). Operators investigating "which docs fell back?" do not need an extra metadata field on `run_summary`.

## 4. Forbidden additions

This feature MUST NOT:

- Add a new field inside `phase_timings.*` (the eight existing keys are immutable in shape per FR-010 / FR-022).
- Add a new field inside `preprocess_output.json` for fallback bookkeeping (Clarifications Q4 explicitly forbids this — `region_strategy_fallback_count` lives only on `run_summary`).
- Rename, remove, or retype any field added by features 014 / 015 / 016 / 017 (`schema_version`, `paddle_import`, `gpu_bind_probe`, `engine_init`, `warmup`, `rasterization`, `per_page_inference`, `artifact_write`, `total`, `module_set_id`, `det_rec_variant_id`, `ppstructure_modules_invoked`).
- Add a new persisted artifact (FR-021 — escape hatch only with `/speckit.plan`-time evidence that `run_summary` + harness/evaluator outputs are insufficient; this feature concludes that they are sufficient per Assumptions §9 and the four-corner benchmark cells fitting cleanly into per-document `phase_timings.*` + the existing evaluator outputs).

## 5. Sample emission (CPU run with both flags ignored, post-feature-018)

```json
{
  "kind": "run_summary",
  "schema_version": "0.1.5",
  "paddle_import": 0.0,
  "gpu_bind_probe": 0.0,
  "engine_init": 0.85,
  "warmup": 0.0,
  "rasterization": 1.42,
  "per_page_inference": 7.31,
  "artifact_write": 0.05,
  "total": 9.63,
  "module_set_id": "cpu-default",
  "det_rec_variant_id": "cpu-default",
  "ppstructure_modules_invoked": [],
  "raster_profile_id": "cpu-default",
  "region_strategy_id": "cpu-default",
  "region_strategy_fallback_count": 0
}
```

## 6. Sample emission (GPU run with `--raster-profile=reduced-v1 --region-strategy=header-first-v1`, no fallback fired)

```json
{
  "kind": "run_summary",
  "schema_version": "0.1.5",
  "paddle_import": 4.10,
  "gpu_bind_probe": 0.32,
  "engine_init": 12.58,
  "warmup": 8.21,
  "rasterization": 0.41,
  "per_page_inference": 2.13,
  "artifact_write": 0.04,
  "total": 27.79,
  "module_set_id": "legacy",
  "det_rec_variant_id": "legacy",
  "ppstructure_modules_invoked": ["layout_detection", "ocr_det", "ocr_rec"],
  "raster_profile_id": "reduced-v1",
  "region_strategy_id": "header-first-v1",
  "region_strategy_fallback_count": 0
}
```

## 7. Sample emission (GPU corpus run on 5 docs, header-first triggered fallback on 1 doc)

```json
{
  "kind": "run_summary",
  "schema_version": "0.1.5",
  "paddle_import": 4.10,
  "gpu_bind_probe": 0.32,
  "engine_init": 12.58,
  "warmup": 8.21,
  "rasterization": 3.07,
  "per_page_inference": 12.76,
  "artifact_write": 0.21,
  "total": 41.25,
  "module_set_id": "legacy",
  "det_rec_variant_id": "legacy",
  "ppstructure_modules_invoked": ["layout_detection", "ocr_det", "ocr_rec"],
  "raster_profile_id": "reduced-v1",
  "region_strategy_id": "header-first-v1",
  "region_strategy_fallback_count": 1
}
```

In sample 7, `phase_timings.rasterization = 3.07` includes the combined wall-clock cost of the 1 document that fell back (page-1 header-band rasterization + full-page rasterization of all that document's pages) plus the 4 documents that did not fall back (page-1 header band only). Per R-018.10, this is the honest reading; readers comparing against `(reduced-v1, full-page)` on the same subset can attribute the difference to the fallback overhead via `region_strategy_fallback_count`.
