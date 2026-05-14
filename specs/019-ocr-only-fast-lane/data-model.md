# Data Model: OCR-Only Fast Lane For Vendor Identity

**Feature**: 019-ocr-only-fast-lane
**Date**: 2026-05-11
**Status**: Phase 1 — entity shapes and relationships. Decisions referenced from `research.md`.

This document defines the entities and value types introduced or extended by feature 019. It is normative for the data shape; implementation details (file paths, function signatures) live in `plan.md`.

## PreprocessStrategy

A named, closed-vocabulary preset that fixes which preprocessing pipeline the `ppstructurev3@gpu` profile runs.

**Module**: `src/dartwing_ocr/preprocessing/preprocess_strategies.py`

**Fields** (all immutable per instance):

| Field | Type | Notes |
|---|---|---|
| `name` | `str` | Closed-vocabulary identifier; one of `{"ppstructurev3", "ocr-only-v1", "cpu-default", "stub-default"}` (R-019.2). Equals the `preprocess_strategy_id` value emitted on `run_summary` when this strategy is active. |
| `kind` | `Literal["ppstructurev3", "ocr-only", "identity"]` | Dispatch discriminator used by `preprocessing/pipeline.py`. `"ppstructurev3"` ⇒ existing layout-aware path; `"ocr-only"` ⇒ new OCR-only path; `"identity"` ⇒ CPU/stub-default identity (no GPU effect; just a label for `run_summary`). |
| `token_threshold` | `int \| None` | The R-019.5 token-count threshold; only populated for `kind = "ocr-only"`. Currently 8 for `ocr-only-v1`. `None` for `ppstructurev3` and identity strategies. |
| `confidence_threshold` | `float \| None` | The R-019.6 detector-confidence-mean threshold; only populated for `kind = "ocr-only"`. Currently 0.60 for `ocr-only-v1`. `None` for `ppstructurev3` and identity strategies. |
| `confidence_aggregator` | `Literal["mean"] \| None` | The R-019.6 aggregation function name; only populated for `kind = "ocr-only"`. Currently `"mean"` for `ocr-only-v1`. `None` for `ppstructurev3` and identity strategies. Closed-vocabulary at landing — adding a new aggregator (e.g., `"weighted_mean"`) is a future feature decision. |

**Registry**: `PREPROCESS_STRATEGIES: Mapping[str, PreprocessStrategy]` — a read-only dict keyed by `name`. Closed at landing to exactly four entries (R-019.2).

**Resolver**: `resolve_preprocess_strategy(name: str) -> PreprocessStrategy` raises `UnknownPresetError(preset_axis="preprocess_strategy", preset_value=name, valid_values=tuple(PREPROCESS_STRATEGIES.keys()))` on any name not in the registry (R-019.12 / exit code 16).

**State transitions**: none. `PreprocessStrategy` is a value object; instances are immutable; equality is by `name`.

## OcrOnlyEligibilityRule

The FR-005 deterministic combined two-threshold eligibility / sufficiency check, applied per-document after OCR-only preprocessing completes.

**Module**: `src/dartwing_ocr/preprocessing/ocr_only.py`

**Inputs** (all derived from preprocessing-pass outputs alone — FR-006 / R-019.5..R-019.7):

| Field | Type | Source |
|---|---|---|
| `lines` | `list[OcrOnlyLine]` | Output of `run_ocr_only_page` aggregated across all targeted pages for the document. Each `OcrOnlyLine` carries `bbox`, `text`, `detector_confidence: float`. |
| `token_threshold` | `int` | From `PreprocessStrategy.token_threshold`. |
| `confidence_threshold` | `float` | From `PreprocessStrategy.confidence_threshold`. |
| `confidence_aggregator` | `Literal["mean"]` | From `PreprocessStrategy.confidence_aggregator`. |

**Output**: `EligibilityVerdict` — a closed enum-like value:

| Value | Meaning |
|---|---|
| `SUFFICIENT` | Both thresholds hold; the OCR-only output is accepted as the final `preprocess_output.json` for this document. |
| `INSUFFICIENT` | At least one threshold trips (or zero boxes detected per R-019.7); the OCR-only partial output is discarded and the document falls back to `ppstructurev3` on the same engine instance (R-019.10). |

**Decision rule** (R-019.5 / R-019.6 / R-019.7, AND-semantics):

```text
if len(lines) == 0:
    return INSUFFICIENT                               # R-019.7 zero-detection short-circuit
token_count = sum(len(line.text.split()) for line in lines)
mean_confidence = sum(line.detector_confidence for line in lines) / len(lines)
if token_count >= token_threshold and mean_confidence >= confidence_threshold:
    return SUFFICIENT
return INSUFFICIENT
```

**Determinism**: The rule depends only on `lines` (preprocessing-pass output) and the constants on the active `PreprocessStrategy`. No model output downstream of OCR participates (FR-006). Two runs with the same input produce the same verdict (SC-012).

## OcrOnlyLine

A single detected and recognized text line from PaddleOCR's pure-OCR pass. Internal value type used by `OcrOnlyEligibilityRule` and the block-clustering step (R-019.8). Not persisted to disk — exists only in-memory during the per-document orchestration.

**Module**: `src/dartwing_ocr/preprocessing/ocr_only.py`

**Fields**:

| Field | Type | Notes |
|---|---|---|
| `bbox` | `BBox` (xmin, ymin, xmax, ymax in image coordinates) | Same coordinate system as the existing `Block.bbox` in the schema. |
| `text` | `str` | Recognized text for this line. |
| `detector_confidence` | `float` | PaddleOCR text-detector confidence for the bbox (range [0.0, 1.0]). |

## OcrOnlyPagePredict

Aggregate predict result for one page on the OCR-only path. Returned by `run_ocr_only_page(engine, page_image)`. Internal — not persisted.

| Field | Type | Notes |
|---|---|---|
| `lines` | `list[OcrOnlyLine]` | All detected lines on this page. |
| `page_number` | `int` | 1-indexed page number (matches the existing `preprocess_output.json` per-page schema). |
| `page_width` | `int` | Image width in pixels (matches `pages[].width`). |
| `page_height` | `int` | Image height in pixels (matches `pages[].height`). |

## Block-Clustering Output

The deterministic Y-axis line clustering rule (R-019.8) takes a `list[OcrOnlyLine]` for a single page and produces a `list[Block]` matching the existing `preprocess_output.json` schema's per-page `blocks[]` shape.

**Algorithm** (R-019.8):

```text
def cluster_lines_into_blocks(lines: list[OcrOnlyLine]) -> list[Block]:
    if not lines:
        return []
    # Compute per-line vertical center
    centers = [(line, (line.bbox.ymin + line.bbox.ymax) / 2) for line in lines]
    # Sort by vertical center
    centers.sort(key=lambda lc: lc[1])
    # Compute median line height
    heights = sorted(line.bbox.ymax - line.bbox.ymin for line in lines)
    H = heights[len(heights) // 2]
    # Floor-clamp to MIN_LINE_HEIGHT_PX=1 so a degenerate all-zero-height
    # input cannot collapse the threshold to 0 and force every line into
    # its own block. Well-formed boxes always have H >= 1, so the clamp
    # is a no-op on healthy input.
    proximity_threshold = 1.5 * max(MIN_LINE_HEIGHT_PX, H)
    # Greedy clustering
    blocks: list[list[OcrOnlyLine]] = []
    current: list[OcrOnlyLine] = [centers[0][0]]
    last_cy: float = centers[0][1]
    for line, cy in centers[1:]:
        if cy - last_cy <= proximity_threshold:
            current.append(line)
        else:
            blocks.append(current)
            current = [line]
        last_cy = cy
    blocks.append(current)
    # Build Block objects
    return [_build_block(cluster, reading_order=i+1) for i, cluster in enumerate(blocks)]
```

**`Block` field assignments for OCR-only**:

| Field | Value |
|---|---|
| `block_id` | `block_id(page_number, reading_order)` from `preprocessing/identifiers.py` (unchanged helper). |
| `block_type` | `"text"` (R-019.8 — OCR-only always emits `"text"` since layout classification is not run). |
| `bbox` | Per-axis min/max envelope of the cluster's line bboxes. |
| `text` | The cluster's line `text` values joined with `"\n"`. |
| Other fields | Whatever the existing schema requires; OCR-only's predict result populates them from the cluster (e.g., `confidence` ⇒ mean of line detector confidences). |

## RunSummary additive fields

Feature 019 adds two top-level fields to the existing `RunSummary` dataclass (R-019.14 SCHEMA_VERSION bump 0.1.5 → 0.1.6).

**Module**: `src/dartwing_ocr/pipeline/timing.py`

**New fields**:

| Field | Type | Default | Notes |
|---|---|---|---|
| `preprocess_strategy_id` | `str` | `CPU_DEFAULT_PREPROCESS_STRATEGY` (`"cpu-default"`) | Always emitted (FR-008 / FR-010). Value drawn from the closed vocabulary in R-019.2. |
| `ocr_only_fallback_count` | `int` | `0` | Always emitted (FR-007). Incremented by 1 per document that triggered the FR-005 fallback during this run; remains `0` on `ppstructurev3` runs, CPU runs, and stub-adapter runs. |

**Position**: Emitted after feature 018's three additive fields in `RunSummary.to_dict()` output (append-only emission order — feature 017's fields, then feature 018's, then this feature's).

**Existing fields**: Untouched (FR-009 / FR-022). The complete post-019 top-level field set is enumerated in `contracts/run-summary-schema.md` §2.

## Identifier-string constants

**Module**: `src/dartwing_ocr/preprocessing/identifiers.py`

| Constant | Value | Used by |
|---|---|---|
| `LEGACY_PREPROCESS_STRATEGY` | `"ppstructurev3"` | GPU-lane no-flag default (R-019.4); also the closed-vocabulary value for the existing layout-aware strategy. |
| `OCR_ONLY_V1_PREPROCESS_STRATEGY` | `"ocr-only-v1"` | The OCR-only candidate preset name. Constant exposed for code reference (e.g., in tests). |
| `CPU_DEFAULT_PREPROCESS_STRATEGY` | `"cpu-default"` | Default value of `RunSummary.preprocess_strategy_id` on CPU profile. |
| `STUB_DEFAULT_PREPROCESS_STRATEGY` | `"stub-default"` | Value of `RunSummary.preprocess_strategy_id` on stub-adapter runs. |

All four are top-level module constants, added additively. Existing feature 017 / 018 identifier strings are unchanged.

## UnknownPresetError extension

**Module**: `src/dartwing_ocr/preprocessing/errors.py`

**Change**: The existing `UnknownPresetError.preset_axis: Literal[…]` is widened additively (R-019.12):

```python
# Before (post-018):
preset_axis: Literal[
    "module_set", "det_rec_variant",     # feature 017
    "raster_profile", "region_strategy", # feature 018
]

# After (post-019):
preset_axis: Literal[
    "module_set", "det_rec_variant",     # feature 017
    "raster_profile", "region_strategy", # feature 018
    "preprocess_strategy",                # feature 019 (R-019.12)
]
```

No new exception class. `exit_code = EXIT_UNKNOWN_PRESET = 16` is unchanged. The stderr message format `error: unknown <preset_axis>: <preset_value!r> — valid values are: <…>` is identical across all 5 axes.

## Relationships

```text
PreprocessStrategy (closed registry of 4)
       │
       │ (resolved at preflight time per --preprocess-strategy flag or env var)
       ▼
PreprocessLane (the run's resolved (lane, raster_profile, region_strategy, preprocess_strategy) tuple)
       │
       │ (for each document, dispatch by PreprocessStrategy.kind)
       ▼
       ├── kind="ppstructurev3" → existing PPStructureV3 path (unchanged from feature 018)
       │
       └── kind="ocr-only"      → preprocessing/ocr_only.py:
                                      run_ocr_only_page(...)
                                      → list[OcrOnlyLine]
                                      cluster_lines_into_blocks(...)
                                      → list[Block]   (schema-valid blocks[])
                                      check_eligibility(...)
                                      → EligibilityVerdict
                                          ├── SUFFICIENT   → emit OCR-only preprocess_output.json
                                          │
                                          └── INSUFFICIENT → fall back to PPStructureV3 path
                                                              (same active region_strategy_id per R-019.11)
                                                              (increment RunSummary.ocr_only_fallback_count by 1)
```

## Invariants

The complete invariant set is in `contracts/module-invariants.md`. Highlights:

- **I-019.1** Closed-vocabulary enforcement: only the 4 values in R-019.2 are valid for `preprocess_strategy_id`. Unknown values raise `UnknownPresetError` → exit 16.
- **I-019.2** Dual-singleton engine: PPStructureV3 and PaddleOCR (OCR-only) are each constructed at most once per process, independently. An OCR-only-only run never constructs PPStructureV3 (FR-022 explicit exception).
- **I-019.3** Combined-trigger AND-semantics: sufficiency requires BOTH `token_count >= threshold` AND `mean_confidence >= threshold`. Zero detections short-circuits to INSUFFICIENT.
- **I-019.4** Per-document fallback granularity: `ocr_only_fallback_count` is incremented by 1 per document; never by 1 per page, never by 1 per threshold trip.
- **I-019.5** Region-strategy orthogonality preservation: on OCR-only fallback, the active `region_strategy_id` is preserved; the `ppstructurev3` fallback runs on the same targeted region. Feature 018's `region_strategy_fallback_count` axis fallback is independent and may still fire.
- **I-019.6** OCR-only block_type pinning: blocks produced by OCR-only line clustering always have `block_type = "text"` (R-019.8).
- **I-019.7** Schema-version always-emit: `RunSummary.SCHEMA_VERSION = "0.1.6"` appears on every run of the new binary regardless of profile or preset selection (FR-010).
