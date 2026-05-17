# Data Model: DPI Reduction And Region-First Vendor Identity Preprocess

**Feature**: 018-dpi-region-first-preprocess
**Date**: 2026-05-10

This feature is preset-and-observability heavy: it adds two closed-vocabulary preset registries, three additive top-level `run_summary` fields, extends one existing exception (`UnknownPresetError.preset_axis: Literal[…]`), and reuses one existing exit code (`UNKNOWN_PRESET = 16`). There are no new persisted artifacts and no new exceptions or exit codes. The entities below describe the stable in-process and on-the-wire surfaces this feature introduces or extends.

## Entity: RasterProfile

A named, closed-vocabulary preset that resolves to a single integer DPI value used by the rasterizer. Lives in `src/dartwing_ocr/preprocessing/raster_profiles.py`. Entries in the registry are immutable across the process lifetime.

```python
@dataclass(frozen=True)
class RasterProfile:
    name: str    # closed vocabulary value (R-018.2)
    dpi: int     # rasterization DPI used by `rasterize_pdf(pdf_path, dpi=profile.dpi)`
```

| Field | Type | Source | Notes |
|---|---|---|---|
| name | `str` | one of `{"legacy", "reduced-v1", "cpu-default", "stub-default"}` | Closed vocabulary at landing time. Adding a new entry is a code change. |
| dpi | `int` | hard-coded per preset (R-018.2 / R-018.3) | `legacy.dpi` reads from `preprocessing/version.py:DPI` (300) so it stays pinned to whatever feature 014 originally set; `reduced-v1.dpi = 200` per R-018.3; CPU/stub identity presets carry `dpi = 300` (irrelevant for stub; matches CPU lane's existing behavior). |

**Registry invariants**:

- `RASTER_PROFILES["legacy"].dpi` is exactly `preprocessing.version.DPI` at module-load time. If `version.DPI` ever changes, `legacy` follows it (single source of truth).
- `RASTER_PROFILES["reduced-v1"].dpi == 200` (per R-018.3).
- `RASTER_PROFILES["cpu-default"].dpi == 300` and `RASTER_PROFILES["stub-default"].dpi == 300`. The CPU rasterizer is NOT preset-driven — it retains its existing `DPI = 300` constant. Identity presets exist for the run_summary identifier surface, not to mutate the CPU rasterizer (FR-015 / R-018.2).
- The registry is exhaustive at landing — registry keys equal the closed `raster_profile_id` vocabulary 1:1.

## Entity: RegionStrategy

A named, closed-vocabulary preset that owns the page-targeting decision and the FR-007 fallback trigger check. Lives in `src/dartwing_ocr/preprocessing/region_strategies.py`. Entries in the registry are immutable across the process lifetime.

```python
@dataclass(frozen=True)
class RegionStrategy:
    name: str
    page_targeting: Callable[[PdfDocument, int], Optional[BBox]]
    trigger_fired: Callable[[list[Block]], bool]
```

| Field | Type | Source | Notes |
|---|---|---|---|
| name | `str` | one of `{"full-page", "header-first-v1", "cpu-default", "stub-default"}` | Closed vocabulary at landing. |
| page_targeting | `Callable[[PdfDocument, int], Optional[BBox]]` | hard-coded per preset (R-018.5) | Returns a `BBox` (in PDF point coordinates) for pages to be targeted, or `None` for "process whole page" (full-page strategies) or "skip and emit empty page record" (header-first on pages 2..N). |
| trigger_fired | `Callable[[list[Block]], bool]` | hard-coded per preset (R-018.7) | Returns `True` iff the FR-007 fallback should fire on this document. For `full-page`, `cpu-default`, `stub-default` strategies, returns `False` always (these strategies have no fallback). For `header-first-v1`, returns `not "".join(b.text for b in targeted_blocks).strip()` per Clarifications Q3. |

**Registry invariants**:

- `REGION_STRATEGIES["full-page"].page_targeting` returns `None` for every page (the orchestrator treats `None` as "process whole page").
- `REGION_STRATEGIES["full-page"].trigger_fired` returns `False` always.
- `REGION_STRATEGIES["header-first-v1"].page_targeting(pdf_doc, page_index)` returns a BBox covering the top 30% of page 1's height when `page_index == 0`, and `None` for `page_index > 0` (R-018.5; the orchestrator interprets the latter as "skip and emit empty page record" for the `header-first-v1` strategy specifically).
- `REGION_STRATEGIES["header-first-v1"].trigger_fired` implements the Clarifications Q3 check verbatim.
- `REGION_STRATEGIES["cpu-default"]` and `["stub-default"]` are aliases of `full-page` semantics — page_targeting returns `None` always, trigger_fired returns `False` always; their distinct `name` values exist purely to populate the run_summary identifier surface (FR-011).
- The registry is exhaustive at landing — registry keys equal the closed `region_strategy_id` vocabulary 1:1.

## Entity: BBox (in PDF point coordinates)

Internal value object used by `RegionStrategy.page_targeting`'s return type and by the rasterizer's `rasterize_page_band`. Distinct from the `bbox` field in `preprocess_output.json` (which is in pixel coordinates after rasterization).

```python
@dataclass(frozen=True)
class BBox:
    x0_pt: float
    y0_pt: float
    x1_pt: float
    y1_pt: float
```

PDF coordinate convention: origin at top-left, y increases downward (matches `pypdfium2`'s convention). Conversion to pixel coordinates: `x_px = x_pt * dpi / 72.0`, `y_px = y_pt * dpi / 72.0`. The rasterizer applies this conversion when cropping; the orchestrator applies the inverse offset when translating PaddleOCR's crop-relative pixel bboxes back to full-page pixel bboxes (R-018.15).

## Entity: PreprocessAxesResolution

Internal value object, never serialized. Carries the resolved axes from CLI parse to the rasterizer / orchestrator and to `RunSummary` build. Sibling of feature 017's `PresetResolution`.

```python
@dataclass(frozen=True)
class PreprocessAxesResolution:
    raster_profile: RasterProfile
    region_strategy: RegionStrategy
```

**Validation rules**:

- Both fields are non-None — preset resolution always returns a value or raises `UnknownPresetError` (R-018.12). There is no "missing" state.
- The resolution is computed once at CLI parse time and read at (a) rasterization to use `raster_profile.dpi`; (b) per-page orchestration in `preprocessing/pipeline.py` to consult `region_strategy.page_targeting`; (c) post-page-1-predict to invoke `region_strategy.trigger_fired`; (d) run_summary build time to write the `raster_profile_id` / `region_strategy_id` strings.

## Entity: UnknownPresetError (extended additively from feature 017)

Existing exception class in `src/dartwing_ocr/preprocessing/errors.py` (introduced by feature 017). This feature **widens its `preset_axis: Literal[…]` field additively** — no new exception class, no new caller signature, no new exit code.

```python
# Before feature 018:
class UnknownPresetError(ValueError):
    exit_code = EXIT_UNKNOWN_PRESET  # = 16
    def __init__(
        self,
        message: str,
        *,
        preset_axis: Literal["module_set", "det_rec_variant"],
        preset_value: str,
        valid_values: tuple[str, ...],
    ) -> None: ...

# After feature 018 (only the Literal[…] widens — additive):
class UnknownPresetError(ValueError):
    exit_code = EXIT_UNKNOWN_PRESET  # = 16, unchanged
    def __init__(
        self,
        message: str,
        *,
        preset_axis: Literal[
            "module_set", "det_rec_variant",       # feature 017
            "raster_profile", "region_strategy",   # feature 018 (this feature)
        ],
        preset_value: str,
        valid_values: tuple[str, ...],
    ) -> None: ...
```

**Cause-class taxonomy** (extends feature 017's table additively):

| Routed via `preset_axis` | When raised | Source feature |
|---|---|---|
| `module_set` | `resolve_module_set(name)` called with a `name` not in `MODULE_SET_PRESETS` | feature 017 |
| `det_rec_variant` | `resolve_det_rec_variant(name)` called with a `name` not in `DET_REC_VARIANTS` | feature 017 |
| `raster_profile` | `resolve_raster_profile(name)` called with a `name` not in `RASTER_PROFILES` | feature 018 |
| `region_strategy` | `resolve_region_strategy(name)` called with a `name` not in `REGION_STRATEGIES` | feature 018 |

The CLI boundary already catches `UnknownPresetError` (per feature 017's `preprocessing/cli.py` and `pipeline/cli.py`), prints `error: unknown <preset_axis>: <preset_value!r> — valid values are: <comma-separated valid_values>` to stderr, and exits with code 16 (R-018.12). No caller change is required for this feature.

**Stability stance**: `preset_axis` is now a closed four-element string literal type at the type level. Adding a fifth axis is a future feature-level decision, not an implementation choice. `valid_values` is informational (shape contract); its content evolves as the registries grow, but its tuple type is stable.

## Entity: RunSummary additive top-level fields

Extends `pipeline/timing.py::RunSummary` additively with three new top-level fields. Field declaration order and emission order are stable for diff readability.

| Field | Type | Default | Notes |
|---|---|---|---|
| `raster_profile_id` | `str` | `CPU_DEFAULT_RASTER_PROFILE = "cpu-default"` | Always emitted (FR-008 / FR-011). On `ppstructurev3@gpu` runs without the flag, value is `"legacy"`. On stub-adapter runs, value is `"stub-default"`. |
| `region_strategy_id` | `str` | `CPU_DEFAULT_REGION_STRATEGY = "cpu-default"` | Always emitted (FR-008 / FR-011). On `ppstructurev3@gpu` runs without the flag, value is `"full-page"`. On stub-adapter runs, value is `"stub-default"`. |
| `region_strategy_fallback_count` | `int` | `0` | Always emitted (FR-009 / Clarifications Q4). For `region_strategy_id != "header-first-v1"`, value is always `0`. For `header-first-v1` runs, value is the count of documents in this run that triggered the FR-007 fallback exactly once each (R-018.8). |

Existing 0.1.4 keys (`schema_version`, `paddle_import`, `gpu_bind_probe`, `engine_init`, `warmup`, `rasterization`, `per_page_inference`, `artifact_write`, `total`, `module_set_id`, `det_rec_variant_id`, `ppstructure_modules_invoked`) are unchanged in name, type, or order. The patch bump 0.1.4 → 0.1.5 reflects the additive top-level surface (R-018.14).

**Identifier-string constants** (declared in `preprocessing/identifiers.py`):

| Constant | Value | Used by |
|---|---|---|
| `LEGACY_RASTER_PROFILE` | `"legacy"` | `RASTER_PROFILES` registry; `preprocessing/cli.py` and `pipeline/cli.py` GPU-default-when-flag-unset selection |
| `CPU_DEFAULT_RASTER_PROFILE` | `"cpu-default"` | `RunSummary.raster_profile_id` default; `RASTER_PROFILES` registry |
| `STUB_DEFAULT_RASTER_PROFILE` | `"stub-default"` | stub adapter run_summary; `RASTER_PROFILES` registry |
| `LEGACY_REGION_STRATEGY` | `"full-page"` | `REGION_STRATEGIES` registry; `preprocessing/cli.py` and `pipeline/cli.py` GPU-default-when-flag-unset selection |
| `CPU_DEFAULT_REGION_STRATEGY` | `"cpu-default"` | `RunSummary.region_strategy_id` default; `REGION_STRATEGIES` registry |
| `STUB_DEFAULT_REGION_STRATEGY` | `"stub-default"` | stub adapter run_summary; `REGION_STRATEGIES` registry |

## Entity: Empty page record (in `preprocess_output.json.pages[i]` for skipped pages)

Not a Python entity — a JSON shape produced by the `header-first-v1` orchestrator for `i > 0`. Fits inside the existing `preprocess_output.json` per-page schema (no schema change — verified at /speckit.clarify Q2 time).

```json
{
  "page_number": <i + 1>,
  "width":  <int(round(width_pt  * resolved_dpi / 72.0))>,
  "height": <int(round(height_pt * resolved_dpi / 72.0))>,
  "rotation_detected": <0 | 90 | 180 | 270 from PDF /Rotate, 0 if absent>,
  "blocks": [],
  "raw_ocr_lines": []
}
```

`width_pt` / `height_pt` are read from `pypdfium2`'s `page.get_size()` without rasterization. `rotation_detected` reads from the page's `/Rotate` (PDF metadata) via `pypdfium2`; absence is `0`. `resolved_dpi` is the active `RasterProfile.dpi` (so a `reduced-v1 × header-first-v1` run produces page-2 geometry consistent with page 1's actual rasterization — see R-018.6 rationale).

## Entity: Per-document fallback event (transient; aggregated into `region_strategy_fallback_count`)

Not serialized. The orchestrator in `preprocessing/pipeline.py` maintains a per-run accumulator that increments by exactly 1 for every document on which `RegionStrategy.trigger_fired` returned `True`. The accumulator's final value lands in `RunSummary.region_strategy_fallback_count` (R-018.8).

| Property | Value |
|---|---|
| Granularity | per-document (one increment per document, regardless of how many pages were involved) |
| Lifetime | live for the duration of one run; not persisted between runs |
| Emission | aggregated into `RunSummary.region_strategy_fallback_count` at run-summary build time |

Per-document attribution (which documents fell back) is **independently recoverable** from `preprocess_output.json.pages[]` shape per Clarifications Q4: a fallen-back document has `pages.length == page_count` with all pages populated (because the full-page strategy ran), while a clean `header-first-v1` multi-page document has page 1 populated and pages 2..N as empty records. Operators investigating "which docs fell back?" do not need a per-document fallback marker on `run_summary` — the `pages[]` shape gives them the answer.
