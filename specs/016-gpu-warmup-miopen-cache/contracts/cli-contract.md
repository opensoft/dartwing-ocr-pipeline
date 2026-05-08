# CLI Contract: GPU Warmup Opt-In Surface

**Feature**: 016-gpu-warmup-miopen-cache
**Applies to**: `python -m ledgerlinc_ocr.preprocessing` (single-doc) and `python -m ledgerlinc_ocr.pipeline` (warm-corpus mode)
**Decision source**: research.md R-016.1; spec FR-002, FR-010, /speckit.clarify Q1.

## 1. Activation surfaces

| Surface | Form | Default | Wins when both set |
|---|---|---|---|
| CLI flag | `--gpu-warmup` (boolean; no `=value`) | absent (off) | yes |
| Env var | `LEDGERLINC_GPU_WARMUP` | unset (off) | no |

**Env-var truthiness** (after `.strip().lower()`): `{"1", "true", "yes"}` ⇒ ON. Anything else (including `2`, `on`, `enabled`, empty string, unset) ⇒ OFF. Strict whitelist; ambiguous values are NOT errors — they are silently treated as OFF, matching how `LOG_LEVEL` parses unrecognized values.

## 2. Help text

`--gpu-warmup` MUST appear in `--help` next to `--preprocess-profile`, with text close to:

```
  --gpu-warmup          Run a one-time PPStructureV3 warmup pass after engine
                        construction so MIOpen/COMGR kernel-selection cost is
                        paid up front. Reported as phase_timings.warmup on the
                        first successful per-document run_summary entry.
                        Has no effect on ppstructurev3@cpu or stub adapters
                        (a stderr warning is emitted in those cases). Can also
                        be set via the LEDGERLINC_GPU_WARMUP=1 environment
                        variable; the CLI flag wins when both are present.
```

## 3. Behavior matrix

| Profile | Warmup opt-in | Behavior | Exit code | stderr |
|---|---|---|---|---|
| `ppstructurev3@gpu` | OFF | identical to feature 015 (no warmup, no `phase_timings.warmup`) | 0 (success) or 10–14 (preflight) or 1 (other) | unchanged |
| `ppstructurev3@gpu` | ON, warmup completes | warmup runs once; `phase_timings.warmup = {seconds: <float>}` on first successful per-doc entry | 0 (success) or 1 (per-doc failure) | unchanged on success; per-doc failures unchanged |
| `ppstructurev3@gpu` | ON, warmup fails | fail-fast; no documents timed; no run_summary emitted | **15** (new — see § 4) | `error: warmup failed: <cause-class>: <message>` |
| `ppstructurev3@cpu` (default) | OFF | identical to feature 015 (CPU run) | 0 or 1 | unchanged |
| `ppstructurev3@cpu` | ON | warn-and-proceed: warmup is no-op'd; run is otherwise identical to opt-in OFF | same as opt-in OFF | one extra line: `warning: --gpu-warmup ignored: active preprocess profile is 'ppstructurev3@cpu', not 'ppstructurev3@gpu'` |
| stub adapter | ON | warn-and-proceed: warmup is no-op'd | same as opt-in OFF | one extra line: `warning: --gpu-warmup ignored: active preprocess profile is '<stub-name>', not 'ppstructurev3@gpu'` |

**Warn-and-proceed text** is fixed (not localized) so test assertions can grep for it: the literal string `--gpu-warmup ignored:` MUST appear in the warning. Tests asserting the warning's presence (`test_warmup_cpu_no_op.py`, SC-007) match on `--gpu-warmup ignored:` rather than the full sentence so the wording can be tightened later without breaking tests.

## 4. Exit codes

This feature adds **one** new exit code, immediately after feature 014's preflight 10–14 range:

| Code | Meaning | Source |
|---|---|---|
| 0 | success | unchanged |
| 1 | generic processing failure | unchanged |
| 10 | preflight: `paddle_not_installed` | feature 014 |
| 11 | preflight: `paddle_cpu_only` | feature 014 |
| 12 | preflight: `gpu_not_exposed` | feature 014 |
| 13 | preflight: `gpu_exposed_paddle_cant_bind` | feature 014 |
| 14 | preflight: `ppstructurev3_init_failed` | feature 014 |
| **15** | **warmup pass failed** (this feature) | **`WarmupError`** raised after preflight succeeded — see R-016.6 |

Exit code 15 fires when `WarmupError` is caught at the runner / corpus_run boundary. Stderr line is `error: warmup failed: <cause-class>: <message>` (FR-007). No `run_summary` is emitted; no `preprocess_output.json` is written for any document that would have been timed after the failed warmup (SC-011).

## 5. Composition rules

- `--gpu-warmup` is **orthogonal** to `--preprocess-profile`: setting it never changes profile selection (Assumptions in spec).
- Setting `--gpu-warmup` with `--preprocess-profile=ppstructurev3@gpu`: warmup runs (the headline path).
- Setting `--gpu-warmup` with any other profile: warn-and-proceed (§ 3 row 5–6).
- Setting `LEDGERLINC_GPU_WARMUP=1` globally in a CI shell: safe — every CPU/stub job in the same shell hits the warn-and-proceed path; only `ppstructurev3@gpu` jobs activate warmup (this is the design ergonomic R-016.1 chose the env-var fallback for).

## 6. Stability

- `--gpu-warmup` flag name is part of this feature's public CLI surface; renaming it is a breaking change.
- The env-var name `LEDGERLINC_GPU_WARMUP` follows the existing `LEDGERLINC_*` convention (cf. `LEDGERLINC_OCR_LOG_LEVEL`).
- Exit code 15 is part of the same exit-code contract feature 014 established; reordering or removing it is a breaking change.
- Stderr warning literal `--gpu-warmup ignored:` is part of this contract for test stability; if the wording changes, the literal MUST be preserved.
