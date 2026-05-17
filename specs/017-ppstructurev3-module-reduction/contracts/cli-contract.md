# CLI Contract: PPStructureV3 Module And Det/Rec Variant Opt-In Surface

**Feature**: 017-ppstructurev3-module-reduction
**Applies to**: `python -m dartwing_ocr.preprocessing` (single-doc) and `python -m dartwing_ocr.pipeline` (warm-corpus mode)
**Decision source**: research.md R-017.1, R-017.2, R-017.4, R-017.5, R-017.9, R-017.12; spec FR-002, FR-006, FR-008, FR-010, FR-013; /speckit.clarify Q2, Q4.

## 1. Activation surfaces

| Surface | Form | Default | Wins when both set |
|---|---|---|---|
| CLI flag — module set | `--module-set <id>` | unset (active profile's default identifier) | yes |
| Env var — module set | `DARTWING_MODULE_SET=<id>` | unset (off) | no |
| CLI flag — det/rec variant | `--det-rec-variant <id>` | unset (active profile's default identifier) | yes |
| Env var — det/rec variant | `DARTWING_DET_REC_VARIANT=<id>` | unset (off) | no |

**Env-var resolution**: `DARTWING_MODULE_SET` and `DARTWING_DET_REC_VARIANT` are read at CLI parse time, after argv parsing. The env var's literal value is passed to `resolve_module_set` / `resolve_det_rec_variant`; an unknown value raises `UnknownPresetError` (exit code 16) the same way an unknown CLI value does. There is no truthiness coercion — the env var carries an identifier name, not a boolean.

**Orthogonality**: both flags are orthogonal to `--preprocess-profile` and `--gpu-warmup`. An operator may combine `--preprocess-profile=ppstructurev3@gpu --gpu-warmup --module-set=reduced-v1 --det-rec-variant=ppocrv5-mobile` in a single invocation; the order on argv does not matter.

## 2. Help text

`--module-set` and `--det-rec-variant` MUST appear in `--help` next to `--preprocess-profile` and `--gpu-warmup`, with text close to:

```
  --module-set ID       Select a named PPStructureV3 module-set preset for the
                        ppstructurev3@gpu lane. Valid values: legacy, reduced-v1.
                        Default on GPU: legacy. Default on CPU/stub: cpu-default
                        / stub-default (the flag is ignored on non-GPU profiles
                        with a stderr warning). Can also be set via the
                        DARTWING_MODULE_SET environment variable; the CLI flag
                        wins when both are present.

  --det-rec-variant ID  Select a named detection/recognition model variant for
                        the ppstructurev3@gpu lane. Valid values: legacy,
                        ppocrv5-mobile, ppocrv4-mobile. Default on GPU: legacy.
                        Default on CPU/stub: cpu-default / stub-default. Same
                        warn-and-proceed behavior on non-GPU profiles. Can also
                        be set via the DARTWING_DET_REC_VARIANT environment
                        variable; the CLI flag wins when both are present.
```

## 3. Behavior matrix

| Profile | `--module-set` | `--det-rec-variant` | Behavior | Exit code | stderr |
|---|---|---|---|---|---|
| `ppstructurev3@gpu` | unset | unset | identical to feature 016 with both identifiers `= "legacy"` on `run_summary` | 0 / 1 / 10–15 | unchanged |
| `ppstructurev3@gpu` | `legacy` | `legacy` | identical to "both unset" | 0 / 1 / 10–15 | unchanged |
| `ppstructurev3@gpu` | `reduced-v1` | unset | reduced module set; `ppstructure_modules_invoked` shrinks; `module_set_id="reduced-v1"`, `det_rec_variant_id="legacy"` | 0 / 1 / 10–15 | unchanged on success |
| `ppstructurev3@gpu` | unset | `ppocrv5-mobile` | lighter det/rec; per-page inference faster; `module_set_id="legacy"`, `det_rec_variant_id="ppocrv5-mobile"`; audit list unchanged from `legacy` | 0 / 1 / 10–15 | unchanged on success |
| `ppstructurev3@gpu` | `reduced-v1` | `ppocrv5-mobile` | both axes reduced; identifier values reflect both | 0 / 1 / 10–15 | unchanged on success |
| `ppstructurev3@gpu` | any value | any value | unknown identifier on either axis | **16** | `error: unknown <preset_axis>: <preset_value!r> — valid values are: <…>` |
| `ppstructurev3@gpu` | unknown | known | fail-fast on `module_set` axis | **16** | as above |
| `ppstructurev3@gpu` | known | unknown | fail-fast on `det_rec_variant` axis | **16** | as above |
| `ppstructurev3@cpu` (default) | unset | unset | identical to feature 016 CPU run; both identifiers `= "cpu-default"` on `run_summary` | 0 / 1 | unchanged |
| `ppstructurev3@cpu` | any known value | unset | warn-and-proceed: flag has no effect; identifiers are `"cpu-default"` / `"cpu-default"` | same as no-flag CPU run | one extra line: `warning: --module-set ignored: active preprocess profile is 'ppstructurev3@cpu', not 'ppstructurev3@gpu'` |
| `ppstructurev3@cpu` | unset | any known value | warn-and-proceed (det/rec axis); identical structure to module-set warn line | same as no-flag CPU run | one extra line: `warning: --det-rec-variant ignored: active preprocess profile is 'ppstructurev3@cpu', not 'ppstructurev3@gpu'` |
| `ppstructurev3@cpu` | any known | any known | warn-and-proceed (both axes); two extra stderr lines | same as no-flag CPU run | two extra lines (one per ignored flag) |
| `ppstructurev3@cpu` | unknown | unknown / either / both | unknown-preset fail-fast — the unknown-value check runs BEFORE the cross-profile warn check | **16** | `error: unknown <preset_axis>: …` (no `--module-set ignored:` warning is emitted on this path; fail-fast wins over warn-and-proceed when both apply) |
| stub adapter | any | any | warn-and-proceed: `module_set_id="stub-default"`, `det_rec_variant_id="stub-default"`; same stderr structure as CPU path | same as no-flag stub run | up to two extra `… ignored:` lines |

**Warn-and-proceed text** is fixed (not localized) so test assertions can grep for it: the literal strings `--module-set ignored:` and `--det-rec-variant ignored:` MUST appear in the corresponding warning lines. Tests asserting the warning's presence (`test_presets_cpu_warn_and_proceed.py`, SC-004) match on those substrings rather than the full sentence so the wording can be tightened later without breaking tests.

**Fail-fast vs warn-and-proceed precedence**: when both apply (CPU profile AND unknown identifier value), fail-fast wins — the unknown-value check is performed at CLI parse time, before any cross-profile warn evaluation. Operators get exit code 16 and the unknown-value stderr line, never the cross-profile warning, on this path.

## 4. Exit codes

This feature adds **one** new exit code, immediately after feature 016's `WARMUP_FAILED = 15`:

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
| **16** | **unknown preset value selected** (this feature) | **`UnknownPresetError`** raised in `preprocessing/presets.py` — see R-017.9 |

Exit code 16 fires when either `resolve_module_set(name)` or `resolve_det_rec_variant(name)` is called with an unknown name at CLI parse time. The check runs BEFORE any Paddle / preflight import, so the failure cost is <100 ms. Stderr line is `error: unknown <preset_axis>: <preset_value!r> — valid values are: <comma-separated valid_values>` (R-017.9). No `run_summary` is emitted; no `preprocess_output.json` is written.

## 5. Argv parse-order invariants

- The unknown-value check (R-017.12) runs at the same boundary `argparse.ArgumentParser.parse_args(...)` returns to the CLI's main function — before any `import paddle` / `import paddleocr` and before the preflight is invoked.
- The cross-profile warn-and-proceed check (FR-013) runs after the active `--preprocess-profile` is known but before any engine is constructed; it depends on the resolved profile value, so it cannot run before argv parse.
- The orthogonality with `--gpu-warmup` is enforced: combining `--gpu-warmup` with `--module-set=reduced-v1 --det-rec-variant=ppocrv5-mobile` on `ppstructurev3@gpu` causes the warmup pass to run on the new preset's engine — i.e., the engine constructed with `use_table_recognition=False` and the lighter det/rec models. The warmup fixture (R-016.2) is unchanged; only the engine that processes it differs.
