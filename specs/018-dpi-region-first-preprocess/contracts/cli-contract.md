# CLI Contract: Raster-Profile And Region-Strategy Opt-In Surface

**Feature**: 018-dpi-region-first-preprocess
**Applies to**: `python -m ledgerlinc_ocr.preprocessing` (single-doc) and `python -m ledgerlinc_ocr.pipeline` (warm-corpus mode)
**Decision source**: research.md R-018.1, R-018.2, R-018.4, R-018.7, R-018.12; spec FR-001, FR-004, FR-008, FR-009, FR-011, FR-014; /speckit.clarify Q1, Q2, Q3, Q4.

## 1. Activation surfaces

| Surface | Form | Default | Wins when both set |
|---|---|---|---|
| CLI flag — raster profile | `--raster-profile <id>` | unset (active profile's default identifier) | yes |
| Env var — raster profile | `LEDGERLINC_RASTER_PROFILE=<id>` | unset (off) | no |
| CLI flag — region strategy | `--region-strategy <id>` | unset (active profile's default identifier) | yes |
| Env var — region strategy | `LEDGERLINC_REGION_STRATEGY=<id>` | unset (off) | no |

**Env-var resolution**: `LEDGERLINC_RASTER_PROFILE` and `LEDGERLINC_REGION_STRATEGY` are read at CLI parse time, after argv parsing. The env-var value is passed verbatim to `resolve_raster_profile` / `resolve_region_strategy`; an unknown value raises `UnknownPresetError` (exit code 16) the same way an unknown CLI value does. There is no truthiness coercion — the env var carries an identifier name, not a boolean.

**Orthogonality**: both flags are orthogonal to `--preprocess-profile`, `--gpu-warmup`, `--module-set`, and `--det-rec-variant`. An operator may combine `--preprocess-profile=ppstructurev3@gpu --gpu-warmup --module-set=reduced-v1 --det-rec-variant=ppocrv5-mobile --raster-profile=reduced-v1 --region-strategy=header-first-v1` in a single invocation; argv order does not matter.

## 2. Help text

`--raster-profile` and `--region-strategy` MUST appear in `--help` next to feature 017's `--module-set` and `--det-rec-variant`, with text close to:

```
  --raster-profile ID   Select a named rasterization-DPI preset for the
                        ppstructurev3@gpu lane. Valid values: legacy, reduced-v1.
                        Default on GPU: legacy. Default on CPU/stub: cpu-default
                        / stub-default (the flag is ignored on non-GPU profiles
                        with a stderr warning). Can also be set via the
                        LEDGERLINC_RASTER_PROFILE environment variable; the CLI
                        flag wins when both are present.

  --region-strategy ID  Select a named page-area-targeting strategy for the
                        ppstructurev3@gpu lane. Valid values: full-page,
                        header-first-v1. Default on GPU: full-page. Default on
                        CPU/stub: cpu-default / stub-default. Same warn-and-
                        proceed behavior on non-GPU profiles. On a no-evidence
                        page-1 result, header-first-v1 falls back to full-page on
                        that document and increments
                        region_strategy_fallback_count on run_summary. Can also
                        be set via the LEDGERLINC_REGION_STRATEGY environment
                        variable; the CLI flag wins when both are present.
```

## 3. Behavior matrix

| Profile | `--raster-profile` | `--region-strategy` | Behavior | Exit code | stderr |
|---|---|---|---|---|---|
| `ppstructurev3@gpu` | unset | unset | identical to feature 017 with both new identifiers `= "legacy"` / `= "full-page"` on `run_summary`; `region_strategy_fallback_count = 0` | 0 / 1 / 10–16 | unchanged |
| `ppstructurev3@gpu` | `legacy` | `full-page` | identical to "both unset" | 0 / 1 / 10–16 | unchanged |
| `ppstructurev3@gpu` | `reduced-v1` | unset | reduced DPI (200); `phase_timings.rasterization` lower than legacy on the same fixture; `raster_profile_id="reduced-v1"`, `region_strategy_id="full-page"` | 0 / 1 / 10–16 | unchanged on success |
| `ppstructurev3@gpu` | unset | `header-first-v1` | page-1 header band only; pages 2..N empty records; `raster_profile_id="legacy"`, `region_strategy_id="header-first-v1"`; on no-evidence trigger, fallback fires (R-018.7), `region_strategy_fallback_count = 1` for this single-doc run | 0 / 1 / 10–16 | unchanged on success |
| `ppstructurev3@gpu` | `reduced-v1` | `header-first-v1` | both axes reduced; identifier values reflect both | 0 / 1 / 10–16 | unchanged on success |
| `ppstructurev3@gpu` | any value | any value | unknown identifier on either axis | **16** | `error: unknown <preset_axis>: <preset_value!r> — valid values are: <…>` |
| `ppstructurev3@gpu` | unknown | known | fail-fast on `raster_profile` axis | **16** | as above |
| `ppstructurev3@gpu` | known | unknown | fail-fast on `region_strategy` axis | **16** | as above |
| `ppstructurev3@cpu` (default) | unset | unset | identical to feature 017 CPU run; both new identifiers `= "cpu-default"` on `run_summary`; `region_strategy_fallback_count = 0` | 0 / 1 / 16 | unchanged |
| `ppstructurev3@cpu` | any known value | unset | warn-and-proceed: flag has no effect; identifiers are `"cpu-default"` / `"cpu-default"` | same as no-flag CPU run | one extra line: `warning: --raster-profile ignored: active preprocess profile is 'ppstructurev3@cpu', not 'ppstructurev3@gpu'` |
| `ppstructurev3@cpu` | unset | any known value | warn-and-proceed (region axis); identical structure to raster-profile warn line | same as no-flag CPU run | one extra line: `warning: --region-strategy ignored: active preprocess profile is 'ppstructurev3@cpu', not 'ppstructurev3@gpu'` |
| `ppstructurev3@cpu` | any known | any known | warn-and-proceed (both axes); two extra stderr lines | same as no-flag CPU run | two extra lines (one per ignored flag) |
| `ppstructurev3@cpu` | unknown | unknown / either / both | unknown-preset fail-fast — the unknown-value check runs BEFORE the cross-profile warn check | **16** | `error: unknown <preset_axis>: …` (no `--raster-profile ignored:` warning is emitted on this path; fail-fast wins over warn-and-proceed when both apply) |
| stub adapter | any | any | warn-and-proceed: `raster_profile_id="stub-default"`, `region_strategy_id="stub-default"`, `region_strategy_fallback_count = 0`; same stderr structure as CPU path | same as no-flag stub run | up to two extra `… ignored:` lines |

**Warn-and-proceed text** is fixed (not localized) so test assertions can grep for it: the literal strings `--raster-profile ignored:` and `--region-strategy ignored:` MUST appear in the corresponding warning lines. Tests asserting the warning's presence (`test_cpu_warn_and_proceed.py`, SC-005) match on those substrings rather than the full sentence so the wording can be tightened later without breaking tests.

**Fail-fast vs warn-and-proceed precedence**: when both apply (CPU profile AND unknown identifier value), fail-fast wins — the unknown-value check is performed at CLI parse time, before any cross-profile warn evaluation. Operators get exit code 16 and the unknown-value stderr line, never the cross-profile warning, on this path.

## 4. Exit codes

This feature adds **no new exit codes**. It reuses feature 017's `UNKNOWN_PRESET = 16` for unknown values on either of the two new axes (R-018.12). The full table is unchanged from feature 017:

| Code | Meaning | Source |
|---|---|---|
| 0 | success | unchanged |
| 1 | generic processing failure | unchanged |
| 10 | preflight: `paddle_not_installed` | feature 014 |
| 11 | preflight: `paddle_cpu_only` | feature 014 |
| 12 | preflight: `gpu_not_exposed` | feature 014 |
| 13 | preflight: `gpu_exposed_paddle_cant_bind` | feature 014 |
| 14 | preflight: `ppstructurev3_init_failed` | feature 014 |
| 15 | warmup pass failed | feature 016 |
| 16 | unknown preset value selected (any of `module_set` / `det_rec_variant` / `raster_profile` / `region_strategy`) | feature 017 (extended additively here) |

## 5. CLI parse order (feature-018 specific)

When both axes are set, parse order is deterministic:

1. argparse parses `--raster-profile` and `--region-strategy` (and their env-var fallbacks) into raw string values.
2. `resolve_raster_profile(raw_value)` runs first; on `UnknownPresetError`, exit 16 immediately with `preset_axis="raster_profile"`.
3. `resolve_region_strategy(raw_value)` runs second; on `UnknownPresetError`, exit 16 immediately with `preset_axis="region_strategy"`.
4. Cross-profile warn evaluation (FR-014) runs only if both axes resolved successfully — if either failed, no warn line is emitted (fail-fast wins).
5. Both resolved presets are passed into the `PreprocessAxesResolution` value object, which the rest of the pipeline consumes.

This order makes the stderr output for any single failing run unambiguous: at most one fail-fast line is printed; the line names which axis failed first.

## 6. Fallback observability on the single-doc CLI

For `python -m ledgerlinc_ocr.preprocessing --document-folder X --preprocess-profile=ppstructurev3@gpu --region-strategy=header-first-v1`:

- If the document does NOT trigger the fallback, the `kind: "run_summary"` line emits `region_strategy_fallback_count: 0`. The document's `preprocess_output.json` has page 1 populated and pages 2..N as empty records (Clarifications Q2).
- If the document DOES trigger the fallback, the `kind: "run_summary"` line emits `region_strategy_fallback_count: 1`. The document's `preprocess_output.json` has all pages populated (the full-page strategy's output replaces the partial region-first attempt). `phase_timings.rasterization` and the sibling `per_page_inference` entries reflect the combined wall-clock cost (R-018.10).

Operators can recover per-document attribution (which document fell back) from the `pages[]` shape per Clarifications Q4 — no extra metadata is needed on `run_summary` for that.
