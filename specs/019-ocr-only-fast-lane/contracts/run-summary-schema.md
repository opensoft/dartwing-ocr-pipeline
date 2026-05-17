# Run-Summary Schema: OCR-Only Fast Lane For Vendor Identity

**Feature**: 019-ocr-only-fast-lane
**Applies to**: `kind: "run_summary"` JSON object emitted on stdout by `python -m dartwing_ocr.preprocessing` and `python -m dartwing_ocr.pipeline`
**Decision source**: research.md R-019.14; spec FR-007, FR-008, FR-009, FR-010, FR-022; /speckit.clarify Session 2026-05-11.

## 1. Schema version

`RunSummary.SCHEMA_VERSION` patches **0.1.5 → 0.1.6** on this feature. The bump is codebase-level (in `pipeline/timing.py`); the `kind: "run_summary"` JSON object's top-level `schema_version` field reflects it on every run regardless of profile or preset selection.

| Version | Set by feature | Additive change |
|---|---|---|
| 0.1.0 | feature 011 | initial run_summary surface |
| 0.1.1 | feature 014 | added `paddle_import`, `gpu_bind_probe`, `engine_init`, `rasterization`, `per_page_inference`, `artifact_write`, `total` (phase_timings shape) |
| 0.1.2 | feature 015 | additional phase_timings refinements (single-engine guarantee infrastructure) |
| 0.1.3 | feature 016 | added `phase_timings.warmup` |
| 0.1.4 | feature 017 | added `module_set_id`, `det_rec_variant_id`, `ppstructure_modules_invoked` |
| 0.1.5 | feature 018 | added `raster_profile_id`, `region_strategy_id`, `region_strategy_fallback_count` |
| **0.1.6** | **feature 019 (this feature)** | **added `preprocess_strategy_id`, `ocr_only_fallback_count`** |

Every bump in this table is additive-only — no existing field has been renamed, removed, or retyped (FR-009 / FR-022).

## 2. Top-level field set after feature 019

Top-level fields on the `kind: "run_summary"` object (in deterministic emission order — append-only):

| Field | Type | Source feature | Default | Notes |
|---|---|---|---|---|
| `kind` | `str` | pre-014 | `"run_summary"` | discriminator |
| `schema_version` | `str` | pre-014 | `"0.1.6"` (this feature) | always emitted |
| `stack_preset` | `str \| null` | feature 011 | `null` | selected stack preset, if any |
| `resolved_profiles` | `object` | feature 011 | — | per-stage profile names |
| `execution_slice` | `object` | feature 011 | — | `start_at` / `stop_after` |
| `on_failure` | `str` | feature 011 | `"continue"` or `"fail-fast"` | warm-corpus policy |
| `documents_total` | `int` | feature 011 | — | run document count |
| `documents_succeeded` | `int` | feature 011 | — | success count |
| `documents_failed` | `int` | feature 011 | — | failure count |
| `profile_initialization_seconds` | `object` | feature 011 | `{}` | warm profile initialization timings |
| `per_document` | `list[object]` | feature 011+015 | `[]` | per-document status, legacy `stages`, optional `phase_timings`, optional `per_page_inference` |
| `preprocess_lane` | `str` | feature 014 | `"cpu"` | resolved preprocess lane |
| `module_set_id` | `str` | feature 017 | `"cpu-default"` | always emitted |
| `det_rec_variant_id` | `str` | feature 017 | `"cpu-default"` | always emitted |
| `ppstructure_modules_invoked` | `list[str]` | feature 017 | `[]` | always emitted; values from `AUDIT_SUB_MODULE_VOCABULARY` |
| `raster_profile_id` | `str` | feature 018 | `"cpu-default"` | always emitted (FR-008 / FR-011) |
| `region_strategy_id` | `str` | feature 018 | `"cpu-default"` | always emitted (FR-008 / FR-011) |
| `region_strategy_fallback_count` | `int` | feature 018 | `0` | always emitted (FR-009 / 018 Q4) |
| **`preprocess_strategy_id`** | **`str`** | **feature 019** | `"cpu-default"` | always emitted (FR-008 / FR-010) |
| **`ocr_only_fallback_count`** | **`int`** | **feature 019** | `0` | always emitted (FR-007 / Clarifications Q1) |

Per FR-009 / FR-022, no existing field is renamed, removed, or retyped by this feature.

## 3. New field semantics

### `preprocess_strategy_id: str`

The active preprocessing-strategy preset name for this run. Values at landing:

| Value | When emitted |
|---|---|
| `"ppstructurev3"` | `ppstructurev3@gpu` runs without `--preprocess-strategy` set (or with `--preprocess-strategy=ppstructurev3`) |
| `"ocr-only-v1"` | `ppstructurev3@gpu` runs with `--preprocess-strategy=ocr-only-v1` set |
| `"cpu-default"` | `ppstructurev3@cpu` runs (any value of `--preprocess-strategy`; flag warn-and-proceed-ignored per FR-013) |
| `"stub-default"` | stub-adapter runs (any value of `--preprocess-strategy`) |

**Stability**: human-readable string, lowercase, ASCII, no whitespace. The set of valid values is the closed `PREPROCESS_STRATEGIES.keys()` — adding a future preset is a code change plus a new identifier value (R-019.2 / FR-001). The value is stable across process restarts and across hosts (no host-specific tokens, no PIDs).

### `ocr_only_fallback_count: int`

The count of documents in this run that triggered the FR-005 OCR-only → `ppstructurev3` fallback (per R-019.5 / R-019.6 / R-019.7 combined-trigger check). Per Clarifications Session 2026-05-11 Q1 (candidate-with-fallback) / Q2 (combined two-threshold trigger):

**Always emitted** on every run of the new binary regardless of profile or preset (FR-007):

| Configuration | `ocr_only_fallback_count` value |
|---|---|
| `ppstructurev3@gpu` + `--preprocess-strategy=ocr-only-v1`, no documents tripped the trigger | `0` |
| `ppstructurev3@gpu` + `--preprocess-strategy=ocr-only-v1`, K documents tripped the trigger | `K` (integer, ≥ 0, ≤ `documents_total`) |
| `ppstructurev3@gpu` + `--preprocess-strategy=ppstructurev3` (or unset / default) | `0` (no OCR-only attempts) |
| `ppstructurev3@cpu` runs | `0` (no OCR-only attempts) |
| stub-adapter runs | `0` (no OCR-only attempts) |

**Increment rule** (I-019.4): the counter is incremented by exactly 1 per document that triggered fallback. It is NOT incremented per page, per threshold trip, or per re-attempt. A multi-page document that falls back contributes `+1`, not `+pages`.

**Range invariant**: `0 <= ocr_only_fallback_count <= documents_total`. The counter cannot exceed the number of documents processed in this run.

**Coexistence with feature 018's `region_strategy_fallback_count`**: independent. Both counters MAY be non-zero on the same run if both axes' fallback triggers fire on different (or even the same) documents. The two counters together let operators distinguish "OCR-only ran clean but region-first sometimes fell back" (`ocr_only_fallback_count=0`, `region_strategy_fallback_count>0`) from "OCR-only fell back on K documents" (`ocr_only_fallback_count=K`).

## 4. Field ordering

The two new fields are emitted **after** feature 018's three additive fields in `RunSummary.to_dict()` output. Append-only emission order:

```text
... [feature 011 fields] ...
preprocess_lane                       (feature 014)
module_set_id                         (feature 017)
det_rec_variant_id                    (feature 017)
ppstructure_modules_invoked           (feature 017)
raster_profile_id                     (feature 018)
region_strategy_id                    (feature 018)
region_strategy_fallback_count        (feature 018)
preprocess_strategy_id                (feature 019 — NEW)
ocr_only_fallback_count               (feature 019 — NEW)
```

JSON consumers MUST NOT rely on key order (JSON objects are unordered), but the emission order is documented here for human readability of the stdout `run_summary` line and for diff stability across runs.

## 5. Default-value rationale

| Field | Default | Why |
|---|---|---|
| `preprocess_strategy_id` | `"cpu-default"` | Matches `CPU_DEFAULT_PREPROCESS_STRATEGY` constant (R-019.3). CPU is the default lane (FR-011). On stub-adapter runs the runtime swaps to `"stub-default"` post-construction. On GPU lane the runtime swaps to `"ppstructurev3"` (or the flag value) post-construction. |
| `ocr_only_fallback_count` | `0` | The natural default: no fallbacks have occurred. Always-emit-with-default-`0` matches feature 018's `region_strategy_fallback_count` pattern exactly so absence of the field on a run is a regression signal (FR-010 / FR-007). |

## 6. Verification

### Required CPU-safe test (test_run_summary_schema_0_1_6.py)

Per `plan.md` test plan: a stub-adapter run on the default test suite (no Paddle GPU) MUST emit a `run_summary` line where:
- `schema_version == "0.1.6"`
- `preprocess_strategy_id == "stub-default"`
- `ocr_only_fallback_count == 0`
- All feature 017/018 fields present and at their CPU/stub defaults.

### Required GPU-marked tests (deferred per FR-025)

- A `ppstructurev3@gpu` run with no `--preprocess-strategy` set emits `preprocess_strategy_id == "ppstructurev3"` and `ocr_only_fallback_count == 0`.
- A `ppstructurev3@gpu` run with `--preprocess-strategy=ocr-only-v1` on a vendor-identity-rich fixture (no fallback expected) emits `preprocess_strategy_id == "ocr-only-v1"` and `ocr_only_fallback_count == 0`.
- A `ppstructurev3@gpu` run with `--preprocess-strategy=ocr-only-v1` on a fixture chosen to trip the trigger emits `preprocess_strategy_id == "ocr-only-v1"` and `ocr_only_fallback_count == 1`.

## 7. Migration notes

- **Consumers of `run_summary`** (operators, dashboards, monitoring) MAY treat `preprocess_strategy_id` and `ocr_only_fallback_count` as optional during a brief migration window if they support pre-019 versions of the binary; from this feature's merge date onwards both fields are always present.
- **Downstream stages** (evidence packet 004, extractor 005, router 008, assembler 009, evaluator 007) do NOT consume `run_summary` — they consume the four canonical artifacts under `tests/stage1_vendor_identity/inv_*/`. No downstream change is required.
- **`evaluation_run_summary.json`** is unchanged. The evaluator's outputs remain on the existing v1.2.0 contract set (FR-020).
