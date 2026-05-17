# CLI Contract: OCR-Only Fast Lane For Vendor Identity

**Feature**: 019-ocr-only-fast-lane
**Applies to**: `python -m dartwing_ocr.preprocessing` and `python -m dartwing_ocr.pipeline`
**Decision source**: research.md R-019.1, R-019.12; spec FR-001, FR-004, FR-013, FR-014.

## 1. Flag surface

This feature adds one new CLI flag and one new env-var fallback, mirroring features 014 / 016 / 017 / 018 exactly.

| Flag | Env-var fallback | Argument type | Default (no flag, no env var) |
|---|---|---|---|
| `--preprocess-strategy <id>` | `DARTWING_PREPROCESS_STRATEGY` | `str` (one of the user-selectable values) | Lane-dependent default (see §2) |

**Precedence** (R-019.1): CLI flag wins when both are set. Env-var literal value is passed verbatim — no `.strip()`, no case normalization. Empty-string env-value counts as unset (matches feature 016 / 017 / 018).

**Help text placement**: appears in the `--help` output next to feature 018's `--raster-profile` / `--region-strategy` and feature 017's `--module-set` / `--det-rec-variant`. Help string names the two user-selectable values, `ppstructurev3` and `ocr-only-v1`, and separately notes that `cpu-default` / `stub-default` are internal identity values emitted on non-GPU profiles rather than accepted operator inputs.

## 2. Resolved default by lane

| Active lane | `--preprocess-strategy` set? | Resolved `RunSummary.preprocess_strategy_id` |
|---|---|---|
| `ppstructurev3@gpu` | No (flag/env both unset) | `"ppstructurev3"` (LEGACY_PREPROCESS_STRATEGY per R-019.4) |
| `ppstructurev3@gpu` | Yes, valid value (`"ppstructurev3"` or `"ocr-only-v1"`) | the CLI/env value verbatim |
| `ppstructurev3@gpu` | Yes, unknown value | (raises `UnknownPresetError` → exit 16; see §4) |
| `ppstructurev3@cpu` | Any (set or unset) | `"cpu-default"` (CPU_DEFAULT_PREPROCESS_STRATEGY); warn-and-proceed if set (§3) |
| Stub adapter | Any (set or unset) | `"stub-default"` (STUB_DEFAULT_PREPROCESS_STRATEGY); warn-and-proceed if set (§3) |

## 3. Warn-and-proceed on wrong profile (FR-013)

When `--preprocess-strategy` (or its env-var equivalent) is set on a profile other than `ppstructurev3@gpu` (i.e., on `ppstructurev3@cpu` or any stub adapter), the CLI MUST:

1. Emit exactly one stderr line containing the literal substring `--preprocess-strategy ignored:` followed by the active profile name.
   - Example: `warning: --preprocess-strategy ignored: active preprocess profile is 'ppstructurev3@cpu', not 'ppstructurev3@gpu'`
2. Perform no preprocessing-strategy change (the active profile's default strategy runs unchanged).
3. Proceed with the run normally.
4. Exit with the same status it would have produced without the flag.

This mirrors feature 016's `--gpu-warmup`, feature 017's `--module-set` / `--det-rec-variant`, and feature 018's `--raster-profile` / `--region-strategy` warn-and-proceed pattern exactly. The grep-able marker `--preprocess-strategy ignored:` lets tests assert the warning is emitted without coupling to the exact wording.

## 4. Exit codes

This feature introduces **no new exit code**. It reuses the existing taxonomy from features 016 / 017 / 018:

| Exit code | Constant | Reused from | When emitted (this feature) |
|---|---|---|---|
| 0 | `EXIT_OK` | feature 014 | normal completion (including completion with warn-and-proceed) |
| 1 | `EXIT_UNEXPECTED` | feature 014 | unexpected exception (existing behavior unchanged) |
| 2 | `EXIT_INPUT_REJECTED` | feature 014 | non-PDF / encrypted / malformed / zero-page PDF (unchanged) |
| 3 | `EXIT_INTERNAL_ERROR` | feature 014 | engine init / artifact validation failures (unchanged) |
| 10–14 | preflight codes | feature 014 | unchanged |
| 15 | `EXIT_WARMUP_FAILED` | feature 016 | unchanged |
| **16** | `EXIT_UNKNOWN_PRESET` | feature 017 | **this feature: extended to fire on `--preprocess-strategy ocr-only-v99` (unknown value on the new axis)** |

The `UnknownPresetError.preset_axis` literal is widened from 4 values (post-018) to 5 values by adding `"preprocess_strategy"` (R-019.12 / `data-model.md` §UnknownPresetError). No new exception class. No new exit code. The stderr message format is identical across all 5 axes: `error: unknown <preset_axis>: <preset_value!r> — valid values are: <comma-separated valid_values>`. For the `preprocess_strategy` axis, that list is the two user-selectable values only: `ppstructurev3, ocr-only-v1`.

## 5. Behavior matrix

The full behavior matrix for `--preprocess-strategy` across all three flag-state × profile combinations:

| Profile | `--preprocess-strategy` value | `preprocess_strategy_id` emitted | Engine constructed | `ocr_only_fallback_count` default | Exit code |
|---|---|---|---|---|---|
| `ppstructurev3@gpu` | unset | `"ppstructurev3"` | PPStructureV3 (existing path) | 0 | 0 / error |
| `ppstructurev3@gpu` | `"ppstructurev3"` (explicit) | `"ppstructurev3"` | PPStructureV3 (existing path) | 0 | 0 / error |
| `ppstructurev3@gpu` | `"ocr-only-v1"` | `"ocr-only-v1"` | PaddleOCR (new path); + PPStructureV3 if any document falls back | per-doc fallback count | 0 / error |
| `ppstructurev3@gpu` | unknown (e.g., `"ocr-only-v99"`) | none (no run_summary) | none | n/a | **16** |
| `ppstructurev3@cpu` | any (including unset) | `"cpu-default"` | (CPU path unchanged) | 0 | 0 / error (warn if flag set) |
| Stub adapter | any (including unset) | `"stub-default"` | (stub path unchanged) | 0 | 0 / error (warn if flag set) |

## 6. Activation orthogonality with prior features

`--preprocess-strategy` composes orthogonally with the existing CLI flags from features 014 / 016 / 017 / 018:

| Flag | Source feature | Orthogonality with `--preprocess-strategy` |
|---|---|---|
| `--preprocess-profile <name>` | feature 014 | unchanged. Selects the lane (`ppstructurev3@cpu` / `ppstructurev3@gpu` / stub); `--preprocess-strategy` only takes effect on `ppstructurev3@gpu` (other profiles trigger warn-and-proceed per §3). |
| `--gpu-warmup` | feature 016 | Resolved per Clarifications Session 2026-05-11 Q3 / R-019.16. The warmup pass exercises **only the engine implied by the selected `preprocess_strategy_id`**. On `--preprocess-strategy=ocr-only-v1` (or env-var equivalent) the warmup binds the OCR-only PaddleOCR engine (`_OCR_ENGINE`); PPStructureV3 (`_ENGINE`) remains unconstructed at warmup. On `--preprocess-strategy=ppstructurev3` (or unset / default) the warmup binds PPStructureV3 (existing behavior). Warmup credit is not transferred across engines — fallback documents on an `ocr-only-v1` warmup run pay the PPStructureV3 cold-start cost on their own `phase_timings.per_page_inference` / `phase_timings.rasterization` budgets per R-019.15. Warmup pass mechanics (cache, env-default, fixture loader, clock-anomaly check, exit code 15 on failure) are unchanged. |
| `--module-set <name>` | feature 017 | independent. On `ocr-only-v1`, the module-set selection is moot (PPStructureV3 is not invoked unless fallback fires). `module_set_id` on `run_summary` reflects the selected value regardless. |
| `--det-rec-variant <name>` | feature 017 | active. OCR-only uses the same det/rec variant the operator selects (FR-027 — `ocr-only-v1` reuses feature 017's `det_rec_variant_id` text-det / text-rec variants; no new variant). |
| `--raster-profile <id>` | feature 018 | active. OCR-only uses the active rasterization DPI. `raster_profile_id` on `run_summary` reflects the selected value regardless. |
| `--region-strategy <id>` | feature 018 | **fully orthogonal — see R-019.11 and `module-invariants.md` I-019.5**. OCR-only respects the active region strategy for the targeted region; on fallback, the `ppstructurev3` path also respects the active region strategy. Both fallback counters (`ocr_only_fallback_count` and `region_strategy_fallback_count`) may fire independently on the same document. |

## 7. Backward compatibility

A run that sets none of the new flags or env vars MUST produce a `run_summary` line that differs from a pre-019 run **only** in:
- `schema_version`: `"0.1.5"` → `"0.1.6"` (R-019.14)
- New top-level fields: `preprocess_strategy_id`, `ocr_only_fallback_count`

The corresponding `preprocess_output.json` on the default `(legacy, full-page, ppstructurev3)` GPU configuration is byte-identical to `main` (FR-019 / SC-007 / SC-008).

## 8. Test coverage on the CPU lane

Per FR-024 / FR-023 / SC-006, the default test suite (CPU-only host, no Paddle GPU, no ROCm) MUST cover:
- The §3 warn-and-proceed path for `--preprocess-strategy` set on `ppstructurev3@cpu` and on stub adapters.
- The §4 unknown-preset exit-16 path for `--preprocess-strategy ocr-only-v99` (and other unknown values).
- The §7 backward-compatibility property (CPU-default `preprocess_strategy_id = "cpu-default"`, `ocr_only_fallback_count = 0`).

GPU-marked tests (`@pytest.mark.gpu`) cover the §2 GPU-lane resolution, the OCR-only inference path, the fallback path, and the FR-015 benchmark. These MAY be deferred per FR-025 if workstation GPU is unavailable at merge.
