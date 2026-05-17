# Module Invariants: OCR-Only Fast Lane For Vendor Identity

**Feature**: 019-ocr-only-fast-lane
**Date**: 2026-05-11
**Status**: Phase 1 — normative invariants enforced at code level.

These invariants govern the new modules (`preprocessing/preprocess_strategies.py`, `preprocessing/preprocess_strategy_optin.py`, `preprocessing/ocr_only.py`) and the edits to existing modules. Each invariant has a numbered ID for traceability from `tasks.md`, the checklists, and code comments.

## I-019.1 — Closed-vocabulary enforcement

Only the four values in `R-019.2` (`"ppstructurev3"`, `"ocr-only-v1"`, `"cpu-default"`, `"stub-default"`) are valid for emitted `preprocess_strategy_id` values. On the user-facing CLI/env surface, only `"ppstructurev3"` and `"ocr-only-v1"` are accepted operator inputs; passing any other value via `--preprocess-strategy` or `DARTWING_PREPROCESS_STRATEGY` MUST raise `UnknownPresetError(preset_axis="preprocess_strategy", ...)` → exit code 16. The registry `PREPROCESS_STRATEGIES` is frozen at module-load time; runtime mutation is forbidden.

Adding a future preset (e.g., `ocr-only-v2` with tuned thresholds) is a code change plus a new `preprocess_strategy_id` value — not a runtime knob and not a config-file override.

## I-019.2 — Dual-singleton engine construction

Two singleton engines coexist in the same process:
- `preprocessing/ocr.py:_ENGINE` — PPStructureV3 (existing, feature 015 FR-001).
- `preprocessing/ocr_only.py:_OCR_ENGINE` — PaddleOCR (new, this feature).

Each engine is constructed **at most once per process** **when invoked**:
- An `ocr-only-v1` run with zero fallbacks constructs only `_OCR_ENGINE`; `_ENGINE` remains `None`.
- An `ocr-only-v1` run with ≥1 fallback constructs both engines (each exactly once).
- A `ppstructurev3` run constructs only `_ENGINE`; `_OCR_ENGINE` remains `None`.

Both engines bind to the same `gpu:0` device when GPU is selected. The single-device-per-process guard (feature 015 FR-006) applies per-engine: each engine's `_*_DEVICE` is recorded on first construction and `RuntimeError` is raised on any subsequent request for a different device.

This invariant is the explicit FR-022 exception (spec): *"When `preprocess_strategy_id = ocr-only-v1`, the PPStructureV3 engine MAY remain unconstructed for the run — the 015 FR-001 'exactly once per process' guarantee applies *to* PPStructureV3 *when* it is invoked, not as a requirement to invoke it."*

## I-019.3 — FR-005 combined-trigger AND-semantics

The eligibility check in `preprocessing/ocr_only.py:check_eligibility` MUST evaluate:

```python
if len(lines) == 0:
    return INSUFFICIENT
token_count = sum(len(line.text.split()) for line in lines)
mean_confidence = sum(line.detector_confidence for line in lines) / len(lines)
return SUFFICIENT if (token_count >= token_threshold) and (mean_confidence >= confidence_threshold) else INSUFFICIENT
```

The AND-semantics is non-negotiable per Clarifications Session 2026-05-11 Q2 (rationale documented in `spec.md`). OR-semantics or a weighted-sum is forbidden. Zero-detection short-circuits to INSUFFICIENT per R-019.7 (an explicit branch, not an accidental NaN-comparison side effect).

`token_threshold` and `confidence_threshold` are read from the active `PreprocessStrategy` (immutable per process). They MUST NOT be settable via env var, CLI flag, or runtime config.

## I-019.4 — Per-document fallback granularity

The `RunSummary.ocr_only_fallback_count` field MUST be incremented **by exactly 1 per document** whose OCR-only eligibility check returned INSUFFICIENT. It MUST NOT be incremented per page, per threshold trip, or per re-attempt. A document that falls back has `+1` regardless of how many pages it has; a document whose OCR-only attempt succeeded has `+0`; a `ppstructurev3` run (no OCR-only attempts) leaves the counter at `0`.

The counter is always emitted on every run of the new binary regardless of profile or strategy selection (FR-007 / FR-010); the default `0` is meaningful — absence is itself a regression signal.

## I-019.5 — Region-strategy orthogonality preservation on fallback

When OCR-only's eligibility check returns INSUFFICIENT for a document and the fallback to `ppstructurev3` fires, the fallback MUST preserve the active `region_strategy_id`:

- If `region_strategy_id = full-page` is active → `ppstructurev3` fallback runs on the full page (the existing behavior).
- If `region_strategy_id = header-first-v1` is active → `ppstructurev3` fallback runs on the same header band on page 1 (pages 2..N remain empty records per feature 018 Q2).

Feature 018's region-strategy-side fallback (region-first → full-page when the targeted region's `blocks[].text` concat is empty) is INDEPENDENT and MAY still fire on the fallen-back document — in which case both `ocr_only_fallback_count` and `region_strategy_fallback_count` are incremented by 1 for that document. The two axes' fallback counters are emitted independently.

The implementation MUST NOT silently switch `region_strategy_id` to `full-page` on OCR-only fallback. Each axis's fallback decision is independent (FR-026).

## I-019.6 — OCR-only block_type pinning

Blocks produced by `preprocessing/ocr_only.py:cluster_lines_into_blocks` MUST have `block_type = "text"`. OCR-only does not run layout classification (FR-002), so it MUST NOT emit `"title"`, `"table"`, `"figure"`, `"header"`, or `"footer"` block types.

The `blocks[]` shape (required keys, coordinate origin / units, page-index ordering rules, `pages.length == page_count` invariant) is identical to a `ppstructurev3` run on the same fixture (FR-003).

## I-019.7 — SCHEMA_VERSION always-emit and additive-only

`RunSummary.SCHEMA_VERSION = "0.1.6"` MUST appear on every run of the new binary regardless of profile or preset selection (FR-010). The bump from `0.1.5` is patch-level and additive-only — no existing field is renamed, removed, or retyped (FR-009 / FR-022). The complete post-019 top-level field set is in `contracts/run-summary-schema.md` §2.

A future field rename would require a minor or major bump and a contracts/AMENDMENTS update. A patch bump signals additive-only changes.

## I-019.8 — Deterministic block clustering (R-019.8)

The Y-axis line-clustering rule in `cluster_lines_into_blocks` MUST be deterministic with respect to its input. Specifically:

1. Lines are sorted by vertical center `cy = (bbox.ymin + bbox.ymax) / 2` ascending. Tie-breaking: stable sort (Python's default).
2. The median line height `H` is computed from the sorted-heights list using integer index `len // 2` (Python's "lower median" — deterministic across platforms).
3. The proximity threshold is `1.5 * max(MIN_LINE_HEIGHT_PX, H)`, where `MIN_LINE_HEIGHT_PX = 1`. The floor clamp keeps a degenerate all-zero-height input (every bbox has `ymin == ymax`) from collapsing the threshold to zero and splitting every line into its own block. Well-formed PaddleOCR boxes always have `H >= 1`, so the clamp is a no-op on healthy input.
4. Greedy clustering: a line joins the current cluster iff its `cy` is within `proximity_threshold` of the previous line's `cy`; otherwise a new cluster starts.

Within each cluster the lines are joined with `"\n"` to form the block's `text`. The block's `bbox` is the per-axis min/max envelope. Reading order within a page is determined by cluster order (top-to-bottom).

Two runs with the same `list[OcrOnlyLine]` input MUST produce byte-identical `blocks[]` output.

## I-019.9 — Confidence aggregation determinism (R-019.6)

The detector-confidence aggregator MUST be the **arithmetic mean** across all detected boxes in the targeted region:

```python
mean_confidence = sum(line.detector_confidence for line in lines) / len(lines)
```

No weighted mean, no median, no max/min. Division by zero is impossible because the R-019.7 zero-detection short-circuit returns INSUFFICIENT before this expression is evaluated.

The mean is computed once per document, not per page; per-page detector confidences are aggregated into the document-level mean across all targeted pages.

## I-019.10 — CPU/stub no-import discipline

`preprocessing/preprocess_strategies.py`, `preprocessing/preprocess_strategy_optin.py`, and `preprocessing/ocr_only.py` (at module-load time) MUST NOT import `paddleocr`, `paddle`, or any other Paddle-family package. Paddle imports happen lazily inside `ocr_only._get_ocr_engine(...)` on the first GPU predict.

This mirrors the existing pattern in `preprocessing/raster_profiles.py` / `preprocessing/region_strategies.py` / `preprocessing/ocr.py` and satisfies FR-014 (CPU-host suites must run without Paddle GPU).

## I-019.11 — `phase_timings` shape preservation (FR-022 carry-forward)

The eight existing `phase_timings.*` keys (`paddle_import`, `gpu_bind_probe`, `engine_init`, `rasterization`, `per_page_inference`, `artifact_write`, `total`, `warmup`) MUST NOT be renamed, removed, or retyped by this feature. Their definitions stay identical to feature 016's contract.

On the OCR-only path, `phase_timings.per_page_inference` reflects PaddleOCR det+rec time only. On a fallback document, `phase_timings.per_page_inference` and `phase_timings.rasterization` reflect **combined wall-clock cost** (OCR-only attempt + PPStructureV3 fallback) per R-019.15. No new `phase_timings.*` key is introduced.

## I-019.12 — `UnknownPresetError` literal widening discipline (R-019.12)

The `preset_axis: Literal[…]` widening from 4 to 5 values is additive. No CLI catch site is modified (existing uniform routing in `preprocessing/cli.py` and `pipeline/cli.py` catches `UnknownPresetError` and exits with `error.exit_code`). The stderr message format `error: unknown <preset_axis>: <preset_value!r> — valid values are: <…>` is identical across all 5 axes.

Tests under `tests/unit/preprocessing/test_unknown_preset_value.py` cover all 5 axes uniformly.

## I-019.13 — Identifier-emission additivity (FR-009 / FR-022)

This feature MUST NOT rename, remove, or retype any existing `run_summary` field, including:
- Feature 011's base fields (`kind`, `schema_version`, etc.).
- Feature 014's `phase_timings.*` shape (8 keys).
- Feature 016's `phase_timings.warmup`.
- Feature 017's `module_set_id`, `det_rec_variant_id`, `ppstructure_modules_invoked`.
- Feature 018's `raster_profile_id`, `region_strategy_id`, `region_strategy_fallback_count`.

Only the two new top-level fields (`preprocess_strategy_id`, `ocr_only_fallback_count`) are added. The `SCHEMA_VERSION` patch bump 0.1.5 → 0.1.6 reflects exactly these two additions.

## I-019.14 — `--preprocess-strategy ignored:` marker stability

The warn-and-proceed stderr line emitted by `preprocess_strategy_optin.preprocess_strategy_warn_message(active_profile)` MUST contain the literal substring `--preprocess-strategy ignored:`. Tests grep for this substring so the surrounding wording can be tightened later without breaking them. The wording outside the marker MAY change; the marker MUST NOT.

This mirrors feature 016's `--gpu-warmup ignored:`, feature 017's `--module-set ignored:` / `--det-rec-variant ignored:`, and feature 018's `--raster-profile ignored:` / `--region-strategy ignored:` markers.

## I-019.15 — No new persisted artifact (FR-021)

This feature MUST NOT introduce a new persisted artifact at landing. Benchmark numbers and quality-gate evidence land in this feature's `quickstart.md` Appendix A and `research.md` Appendix B respectively — both Markdown documents under `specs/019-ocr-only-fast-lane/`, not under `contracts/` and not under `tests/stage1_vendor_identity/`. The FR-021 escape hatch (data-model.md + research.md + AMENDMENTS update) is reserved for a future amendment if `/speckit.plan` evidence later shows `run_summary` + harness/evaluator outputs are insufficient.

## I-019.16 — Warmup binds the strategy-implied engine only (R-019.16 / Clarifications Q3)

`preprocessing/warmup.py` (and its callers in `preflight.py` / `preflight_cli.py`) MUST bind exactly one engine at warmup time, determined by the resolved `preprocess_strategy_id`:

- `preprocess_strategy_id == "ppstructurev3"` ⇒ warmup invokes `ocr._get_engine(...)` (PPStructureV3). `_OCR_ENGINE` (from `ocr_only.py`) remains `None` after warmup. (Existing feature 016 behavior on this branch — unchanged.)
- `preprocess_strategy_id == "ocr-only-v1"` ⇒ warmup invokes `ocr_only._get_ocr_engine(...)` (PaddleOCR). `_ENGINE` (from `ocr.py`) remains `None` after warmup.
- `preprocess_strategy_id ∈ {"cpu-default", "stub-default"}` ⇒ warmup is profile-defined (the CPU/stub warn-and-proceed path nulls the strategy flag before warmup is reached; this invariant does not constrain that case).

Forbidden:
- Warming both engines on `ocr-only-v1`. The unconstructed engine MUST remain `None`.
- Warming PPStructureV3 on `ocr-only-v1` (would violate FR-002 by invoking layout pre-emptively).
- Skipping warmup entirely on `ocr-only-v1` (would regress feature 016's warmup benefits on the OCR-only path).

`phase_timings.warmup` measures the single warmed engine's warmup cost only (PaddleOCR on `ocr-only-v1`; PPStructureV3 on `ppstructurev3`). On a fallback document, the PPStructureV3 cold-start cost (construction + first-predict) is included in that document's `phase_timings.per_page_inference` and `phase_timings.rasterization` per I-019.11 / R-019.15 — never folded back into `phase_timings.warmup`. Warmup pass mechanics (cache, env-default, fixture loader, clock-anomaly check, exit code 15 on failure) are unchanged from feature 016.
