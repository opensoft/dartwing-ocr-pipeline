# CLI Contract: `--evidence-gate-skip-fallback`

> **Implementation status**: This contract describes the **US4 opt-in surface**, which lands on stacked PR #40, not on the MVP PR #38. PR #38 has no parser entry for `--evidence-gate-skip-fallback` and no resolver for `DARTWING_EVIDENCE_GATE_SKIP_FALLBACK`. Running the commands documented here against PR #38's tip exits with `argparse: unknown argument`. The contract is documented here on the MVP branch so US4's stacked PR can implement against a frozen, reviewed CLI contract rather than negotiating it during implementation.

Feature 020 adds one boolean opt-in flag to both `python -m dartwing_ocr.preprocessing` and `python -m dartwing_ocr.pipeline`. No new value-bearing preset axis is introduced at landing because the `evidence_gate_id` closed-vocabulary has size one (`"v1"` only — see R-020.2 / `evidence-gate-rule.md`). No new exit code is introduced.

---

## Flag and environment variable

| Surface | Name | Type | Default | Notes |
|---|---|---|---|---|
| CLI flag | `--evidence-gate-skip-fallback` | boolean (presence) | `False` (absent) | Activates shape (b) skip-fallback (R-020.7 / R-020.8). |
| Env-var fallback | `DARTWING_EVIDENCE_GATE_SKIP_FALLBACK` | string | unset / `""` (falsy) | Truthy values: `"1"`, `"true"`, `"yes"`, `"on"` (case-insensitive). Falsy values: `"0"`, `"false"`, `"no"`, `"off"`, `""`, unset. |

### Precedence (R-020.1)

When both the CLI flag and env var resolve to definite values, **CLI wins**. Specifically, `resolve_evidence_gate_skip_fallback(cli_value, env)` returns:
- `True` if CLI flag is present (regardless of env-var value).
- `False` if CLI flag is absent AND env var is unset OR set to a falsy value.
- `True` if CLI flag is absent AND env var is set to a truthy value.

Empty-string env = unset. Any other env-var value rejects with the same error path the existing `_PRESET_ENV_VAR` helpers use (`ValueError` ⇒ argparse → exit code 2 from the existing CLI infrastructure).

---

## Activation matrix

| Profile | Preprocess strategy | Flag/env | Behavior |
|---|---|---|---|
| `ppstructurev3@gpu` | `ppstructurev3` | OFF | Default; no suppression. Gate runs on the final `preprocess_output.json` and emits all four `run_summary` fields. |
| `ppstructurev3@gpu` | `ppstructurev3` | ON | Flag has no effect (no OCR-only candidate to suppress); no warn fires (R-020.12). `evidence_gate_suppressed_fallback_count` stays `0`. Gate runs and emits its four fields normally. |
| `ppstructurev3@gpu` | `ocr-only-v1` | OFF | Feature 019 fallback runs unchanged. Gate runs on final output. `evidence_gate_suppressed_fallback_count = 0`. |
| `ppstructurev3@gpu` | `ocr-only-v1` | ON | Shape (b) engaged. Gate evaluates candidate; if `sufficient` AND FR-005 trigger fires, fallback suppressed and `evidence_gate_suppressed_fallback_count += 1`; otherwise feature 019's fallback runs unchanged. |
| `ppstructurev3@cpu` | n/a (CPU profile) | OFF | Default CPU run; gate runs on CPU and emits four fields with `evidence_gate_suppressed_fallback_count = 0`. |
| `ppstructurev3@cpu` | n/a (CPU profile) | ON | Warn-and-proceed: one stderr line `--evidence-gate-skip-fallback ignored: active profile is not ppstructurev3@gpu`. Gate still runs on CPU; four fields emitted; `evidence_gate_suppressed_fallback_count = 0`. Same exit code as OFF. |
| stub-adapter | n/a | OFF | Stub run; gate emits defaults (`evidence_gate_id = "v1"`, empty state counts, empty documents array, `evidence_gate_suppressed_fallback_count = 0`). |
| stub-adapter | n/a | ON | Warn-and-proceed (same as CPU); same emit behavior as stub OFF. |

---

## Orthogonality with existing CLI surface

The flag composes orthogonally with every CLI option features 014–019 added. Setting `--evidence-gate-skip-fallback` does NOT change the resolution of:
- `--preprocess-profile` (feature 014)
- `--gpu-warmup` (feature 016)
- `--module-set` (feature 017)
- `--det-rec-variant` (feature 017)
- `--raster-profile` (feature 018)
- `--region-strategy` (feature 018)
- `--preprocess-strategy` (feature 019)

It also does NOT introduce a new value-bearing preset axis at landing (R-020.2): there is no `--evidence-gate <id>` flag, no `DARTWING_EVIDENCE_GATE` env var, no `evidence_gate` enum value in `UnknownPresetError.preset_axis`. Future presets (`v2`, `v3`, ...) will land their own selection flag at that time.

---

## Help text (informative)

Excerpt from `preprocessing/cli.py --help`:

```
  --evidence-gate-skip-fallback
                        Opt-in: when set, suppresses feature 019's OCR-only-to-PPStructureV3 fallback
                        on per-document basis IF the evidence gate decision over the OCR-only candidate
                        is "sufficient" AND the feature 019 FR-005 trigger would otherwise fire.
                        Off by default. Requires `--preprocess-profile=ppstructurev3@gpu` AND
                        `--preprocess-strategy=ocr-only-v1` to have effect; on other profile/strategy
                        combinations the flag is honored but is a no-op. On non-GPU profiles, a
                        stderr warning is emitted (`--evidence-gate-skip-fallback ignored:`) and the
                        run proceeds unchanged. Env-var fallback:
                        DARTWING_EVIDENCE_GATE_SKIP_FALLBACK (truthy values: 1/true/yes/on).
                        See specs/020-vendor-evidence-gate/contracts/evidence-gate-rule.md for the
                        v1 decision table.
```

---

## Exit codes

This feature introduces **no new exit codes**. All existing exit codes from feature 014–019 are preserved (including `UNKNOWN_PRESET = 16` from feature 017, which is not extended because there is no new preset axis to validate).

The CLI's existing handling applies:
- `0` — successful run.
- `1` — generic CLI error (uncaught runtime failure).
- `2` — argparse usage error. Two paths fall here:
  - Malformed flag usage (e.g., `--evidence-gate-skip-fallback=yes` — the flag is boolean, no value accepted).
  - Invalid `DARTWING_EVIDENCE_GATE_SKIP_FALLBACK` env-var value: the existing `_PRESET_ENV_VAR` helper raises `ValueError`, argparse catches it in its `type=` conversion path and calls `parser.error()` which exits 2. This is the same behavior the precedence section above documents.
- Other codes (3, 4, 5, ... 16, ...) — unchanged from prior features.

---

## Verification

CPU-safe checks that MUST pass in CI:

1. `python -m dartwing_ocr.preprocessing --help 2>&1 | grep -F -- "--evidence-gate-skip-fallback"` → exit 0.
2. `python -m dartwing_ocr.preprocessing ... --evidence-gate-skip-fallback --preprocess-profile ppstructurev3@cpu 2>&1 | grep -F -- "--evidence-gate-skip-fallback ignored:"` → exit 0.
3. `DARTWING_EVIDENCE_GATE_SKIP_FALLBACK=1 python -m dartwing_ocr.preprocessing ... --preprocess-profile ppstructurev3@cpu 2>&1 | grep -F -- "--evidence-gate-skip-fallback ignored:"` → exit 0 (env-var fallback fires the same warn).
4. `DARTWING_EVIDENCE_GATE_SKIP_FALLBACK="" python -m dartwing_ocr.preprocessing ... --preprocess-profile ppstructurev3@cpu 2>&1` does NOT emit the warn (empty string = unset per R-020.1).
5. Two runs with identical configuration produce byte-identical `run_summary` values for `evidence_gate_id`, `evidence_gate_state_counts`, `evidence_gate_documents`, and `evidence_gate_suppressed_fallback_count`.

GPU-safe checks (deferrable per R-020.15):

6. `python -m dartwing_ocr.preprocessing ... --evidence-gate-skip-fallback --preprocess-profile ppstructurev3@gpu --preprocess-strategy ocr-only-v1` on a `sufficient`-eligible fixture: `evidence_gate_suppressed_fallback_count >= 1` AND `ocr_only_fallback_count == 0` for that document.
7. Same command on a `borderline`-eligible fixture: `evidence_gate_suppressed_fallback_count == 0` AND `ocr_only_fallback_count == 1` for that document.
