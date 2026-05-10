# Module Invariants: DPI Reduction And Region-First Vendor Identity Preprocess

**Feature**: 018-dpi-region-first-preprocess
**Applies to**: `preprocessing/raster_profiles.py`, `preprocessing/region_strategies.py`, `preprocessing/rasterize.py`, `preprocessing/pipeline.py`, `pipeline/timing.py`, `pipeline/corpus_run.py`, `pipeline/runner.py`
**Decision source**: research.md R-018.1 through R-018.16; spec FR-001, FR-002, FR-004, FR-006, FR-007, FR-008–FR-011, FR-014, FR-022; /speckit.clarify Q1–Q4.

## I-018.1: Closed-vocabulary preset axes (presets only — no runtime toggling)

The `--raster-profile` flag accepts only values in `RASTER_PROFILES.keys()`; the `--region-strategy` flag accepts only values in `REGION_STRATEGIES.keys()`. Free-form numeric DPI (`--dpi 175`) and free-form region coordinates (`--region-bbox 0,0,612,250`) are not accepted on the runtime path (FR-001 / FR-004). Adding a future preset is a code change to `preprocessing/raster_profiles.py` or `preprocessing/region_strategies.py` plus a new entry in the registry — not a runtime knob.

**Verification**: `test_raster_profiles_unit.py` and `test_region_strategies_unit.py` assert that `resolve_raster_profile("legacy" | "reduced-v1" | "cpu-default" | "stub-default")` succeed and `resolve_raster_profile(<any other string>)` raises `UnknownPresetError(preset_axis="raster_profile", ...)`. Same shape for `resolve_region_strategy`.

## I-018.2: GPU-only effects on both new axes

Both new axes have GPU-only behavioral effects. On `ppstructurev3@cpu` and stub-adapter runs:

- The CPU singleton in `preprocessing/ocr.py` continues to use `DPI = 300` from `preprocessing/version.py`, regardless of `--raster-profile` value.
- The CPU rasterizer in `preprocessing/rasterize.py` continues to use `DPI = 300`, regardless of `--raster-profile` value.
- The CPU lane processes every PDF page edge-to-edge, regardless of `--region-strategy` value (no header-band cropping, no page skipping).
- Setting either flag on CPU/stub triggers the FR-014 warn-and-proceed line (R-018.1).

**Verification**: `test_cpu_warn_and_proceed.py` (CPU-safe; no GPU required) asserts the CPU lane's `preprocess_output.json` is unchanged when `--raster-profile=reduced-v1` and/or `--region-strategy=header-first-v1` are set, and the corresponding warn line(s) appear on stderr.

## I-018.3: Single engine per process preserved (carry-forward of feature 015 FR-001)

The FR-007 fallback path (R-018.7 / R-018.9) MUST reuse the same PPStructureV3 engine instance constructed at preflight time. No second engine is constructed for the fallback predict. The orchestrator in `preprocessing/pipeline.py` passes the same `engine` reference to both the page-1 region-first predict and (on trigger) the full-page fallback predict.

**Verification**: `test_region_first_fallback.py @gpu` asserts via instrumentation that `PPStructureV3.__init__` is called exactly once per process even on a fixture chosen to force the fallback. (Deferred per FR-025 if no GPU available at landing.)

## I-018.4: Deterministic page targeting (FR-006)

`RegionStrategy.page_targeting(pdf_doc, page_index)` MUST be a pure function of (PDF page geometry, page index). It MUST NOT consult model output (extraction, classification, vendor-identity), wall-clock time, random seeds, or environment variables beyond the resolved preset name. Two calls of `page_targeting(same_pdf_doc, same_index)` MUST return the same `Optional[BBox]`.

**Verification**: `test_region_strategies_unit.py` (CPU-safe) constructs a synthetic PDF with known page sizes and asserts `header-first-v1.page_targeting(doc, 0)` returns the BBox `(0, 0, width_pt, 0.30 * height_pt)` and `header-first-v1.page_targeting(doc, i)` returns `None` for `i > 0`, on every call.

## I-018.5: Deterministic fallback trigger (FR-007 / Clarifications Q3)

`RegionStrategy.trigger_fired(blocks)` for `header-first-v1` MUST be exactly:

```python
return not "".join(b.text for b in blocks).strip()
```

The trigger MUST be re-derivable from the targeted blocks alone (no model output beyond what produced the blocks themselves; no external state). The trigger MUST NOT consult `raw_ocr_lines`, bounding-box presence, or block count.

**Verification**: `test_region_strategies_trigger.py` (CPU-safe) constructs synthetic block lists (empty, whitespace-only text, single non-whitespace block, mixed) and asserts the boundary cases per Clarifications Q3.

## I-018.6: Page-coverage invariant for `header-first-v1` (Clarifications Q2)

When `region_strategy_id == "header-first-v1"` and the FR-007 fallback did NOT fire on a document, the document's `preprocess_output.json` MUST satisfy:

- `len(pages) == page_count` (i.e., one entry per PDF page).
- `pages[0]` has populated `blocks: [...]` and `raw_ocr_lines: [...]` derived from the page-1 header band.
- `pages[i]` for `i > 0` has `blocks: []`, `raw_ocr_lines: []`, and valid geometry derived from `pdf_doc.get_page(i).get_size()` (R-018.6).

When the FR-007 fallback DID fire on a document, the document's `preprocess_output.json` MUST satisfy:

- `len(pages) == page_count`.
- Every `pages[i]` has populated `blocks` and `raw_ocr_lines` (because the full-page strategy produced the output).

These two shapes give the operator-facing per-document attribution rule from Clarifications Q4 ("fallen-back document has full-length populated `pages[]`; clean region-first multi-page document has page 1 populated and pages 2..N empty").

**Verification**: `test_region_first_pages_invariant.py @gpu` and `test_region_first_fallback.py @gpu` cover both shapes. (Both deferred per FR-025 if no GPU at landing.)

## I-018.7: Coordinate-system invariant (FR-002 / R-018.15)

For ANY `(raster_profile_id, region_strategy_id)` configuration, the `preprocess_output.json` field shape, coordinate origin, units, page index, and block index MUST be identical to a `(legacy, full-page)` run on the same fixture. Specifically:

- `pages[i].blocks[j].bbox` is in pixel coordinates, origin top-left of the full page (NOT crop-relative for `header-first-v1`).
- `pages[i].raw_ocr_lines[j].bbox` is in pixel coordinates, origin top-left of the full page.
- `pages[i].width` and `pages[i].height` reflect the resolved `RasterProfile.dpi` (so a `reduced-v1` run on a US-Letter PDF reports `width = round(612 * 200 / 72) = 1700` rather than `2550` from legacy 300 DPI — this is the only non-shape difference allowed).
- `pages[i].block_id` and `raw_ocr_lines[i].line_id` follow the existing `^p\\d+_b\\d+$` and `^p\\d+_l\\d+$` patterns (no preset-derived prefix).

Per R-018.15, integer pixel bbox values may differ by ±1 between `(legacy, full-page)` and `(reduced-v1, full-page)` on the same fixture (rasterization rounding floor). No other field differs in shape.

**Verification**: `test_legacy_byte_identity.py` (CPU-safe variant + optional `@gpu` variant) asserts `preprocess_output.json` byte-identity between a no-flag run and a `--raster-profile=legacy --region-strategy=full-page` explicit-default run. `test_coordinate_translation.py` (CPU-safe) covers the bbox translation arithmetic.

## I-018.8: `phase_timings.*` shape unchanged (FR-022 carry-forward)

This feature MUST NOT add, remove, rename, or retype any key in `phase_timings.*`. The eight existing keys (`paddle_import`, `gpu_bind_probe`, `engine_init`, `rasterization`, `per_page_inference`, `artifact_write`, `total`, `warmup`) are immutable in shape from features 015/016. The combined-cost rule from R-018.10 (fallen-back documents accumulate both region-first and full-page wall-clock time into the same `phase_timings.rasterization` / `phase_timings.per_page_inference` keys) does NOT change shape — it only changes content for documents that fell back.

**Verification**: `test_run_summary_schema_0_1_5.py` (CPU-safe) asserts the `phase_timings.*` key set is exactly the eight keys above on every run.

## I-018.9: `run_summary` always-emit invariant (FR-008 / FR-009 / FR-011)

The three new `run_summary` top-level fields (`raster_profile_id`, `region_strategy_id`, `region_strategy_fallback_count`) MUST be emitted on every run of the new binary, regardless of profile and regardless of whether the operator set the flags. Default values are `cpu-default` / `cpu-default` / `0` for the CPU singleton; `stub-default` / `stub-default` / `0` for the stub adapter; `legacy` / `full-page` / `0` for a no-flag GPU run. Absence of any of the three fields is a regression signal.

**Verification**: `test_run_summary_schema_0_1_5.py` (CPU-safe) asserts the three fields are present and have the correct default types on stub-adapter and CPU runs.

## I-018.10: `region_strategy_fallback_count` granularity invariant (R-018.8 / Clarifications Q4)

`region_strategy_fallback_count` is the count of **documents** in the run that triggered the FR-007 fallback exactly once each. It is NOT a page-granular count, NOT a corpus-percentage, and NOT a multi-trigger-per-document accumulator (the trigger fires at most once per document, by design — once it fires the document is reprocessed under the full-page strategy and the orchestrator moves on).

**Verification**: `test_region_first_fallback.py @gpu` asserts the counter increments by exactly 1 for a single document that triggered the fallback. (Deferred per FR-025 if no GPU at landing.)

## I-018.11: Single-source-of-truth for the `legacy` DPI (R-018.2)

`RASTER_PROFILES["legacy"].dpi` MUST be exactly `preprocessing.version.DPI` at module-load time. If `version.DPI` ever changes in a future feature, `legacy` follows it without code change in `raster_profiles.py`. There MUST NOT be a duplicate hard-coded `300` in `raster_profiles.py`.

**Verification**: `test_raster_profiles_unit.py` (CPU-safe) imports both `RASTER_PROFILES` and `version.DPI` and asserts equality. `reduced-v1.dpi == 200` is a separate assertion (its hard-coded value is the right behavior for `reduced-v1` per R-018.3).

## I-018.12: Carry-forward of feature 014 / 015 / 016 / 017 invariants (FR-022)

This feature does not change any of the following:
- Feature 014: `--preprocess-profile` flag, profile registry, exit codes 10–14.
- Feature 015: PPStructureV3 constructed exactly once per process; GPU readiness probed at most once per process; single-device-per-process guard; no silent CPU fallback after `ppstructurev3@gpu` is selected.
- Feature 016: `--gpu-warmup` flag, MIOpen/COMGR cache behavior, `phase_timings.warmup` semantics, `WARMUP_FAILED = 15` exit code, warn-and-proceed pattern for `--gpu-warmup` on CPU/stub.
- Feature 017: `--module-set` and `--det-rec-variant` flags; `module_set_id`, `det_rec_variant_id`, `ppstructure_modules_invoked` fields on `run_summary`; `UnknownPresetError` exception (this feature widens its `preset_axis: Literal[…]` additively per R-018.12 — NO existing caller change required).

**Verification**: `test_legacy_byte_identity.py` covers carry-forward of run-summary additive-only behavior (only the three new fields differ between feature 017's run-summary and feature 018's). The existing feature-014/015/016/017 test suites must continue to pass unchanged after this feature lands.
