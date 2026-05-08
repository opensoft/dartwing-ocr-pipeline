# Run-Summary Schema 0.1.3 (additive `phase_timings.warmup`)

**Feature**: 016-gpu-warmup-miopen-cache
**Lineage**: 0.1.0 (feature 014) → 0.1.1 (feature 014 patch) → 0.1.2 (feature 015) → **0.1.3 (this feature)**
**Decision source**: spec FR-006, FR-007, FR-008, FR-009; research.md R-016.8, R-016.9; /speckit.clarify Q2.

This contract describes the **only** addition this feature makes to the existing `kind: "run_summary"` stdout shape: one optional sub-key under `phase_timings`. All other 0.1.2 keys (`paddle_import`, `gpu_bind_probe`, `engine_init`, `rasterization`, `per_page_inference`, `artifact_write`, `total`, plus the legacy flat `stages.preprocess.*`) are unchanged in name, shape, and semantics.

## 1. Codebase-level version bump

```python
# src/ledgerlinc_ocr/pipeline/timing.py
SCHEMA_VERSION = "0.1.3"  # was "0.1.2"
```

Every run of the new binary emits `schema_version: "0.1.3"` regardless of warmup opt-in / outcome (R-016.9 / FR-008). The 0.1.3 schema is a strict superset of 0.1.2: adds one optional key. Consumers built against 0.1.2 continue to read 0.1.3 output without changes.

## 2. New optional key

**Path**: `per_document[*].phase_timings.warmup`
**Shape**: `{ "seconds": <float> }` — six-decimal-rounded; no other keys allowed.
**Type**: object with exactly one required field `seconds` (number).
**Presence**: optional. Absent in every 0.1.2 emission and in 0.1.3 emissions where warmup did not complete successfully.

**Rounding precision (explicit)**: `seconds` MUST be rounded to **exactly six decimal places** via `round(elapsed_perf_counter_seconds, 6)`. This matches the rounding convention used for every other scalar `phase_timings.*.seconds` entry across feature 014 / 015 / 016 (six decimals = microsecond precision; matches `pipeline/timing.py`'s existing `_ns_to_seconds` helper). Values with more than six decimals on the wire are a schema violation; values with fewer (e.g., `0.5` instead of `0.500000`) are acceptable JSON since trailing zeros are not preserved by `json.dumps`. The contract is the rounding *operation*, not the wire string format.

## 3. Presence rules (formal)

For a per-document run_summary entry `e`:

```
e.phase_timings.warmup exists  ⇔
    schema_version == "0.1.3"
    AND warmup opt-in was set for the run
    AND active preprocess profile == "ppstructurev3@gpu"
    AND run_warmup() returned a WarmupResult successfully
    AND e.status == "success"
    AND e is the first per-document entry whose status == "success"
```

Negation cases (warmup absent):

| Case | Reason |
|---|---|
| schema_version is 0.1.2 or older | feature not yet shipped |
| Warmup opt-in not set | FR-002 (off by default) |
| Profile is `ppstructurev3@cpu` or stub | FR-010 warn-and-proceed |
| `run_warmup` raised `WarmupError` | FR-007 / SC-011 — process exited with code 15; no run_summary emitted at all |
| `e.status == "failure"` | feature 015 FR-015 / FR-016 — one-time GPU phases land on a successful entry only |
| `e` is the second-or-later successful entry | FR-006 — attached to first successful entry only (FR-004 = once per process) |

## 4. Co-location with feature 015 keys

`phase_timings.warmup` is attached by the SAME `attach_one_time_gpu_phases(...)` helper that attaches `paddle_import` / `gpu_bind_probe` / `engine_init` (R-016.8). Therefore, when `phase_timings.warmup` is present on entry `e`, those three feature-015 keys are also present on the same entry (modulo their own absence rules — e.g., if preflight was already past `paddle_import` because paddle was preloaded by a previous in-process operation, that key may itself be absent per feature 015 FR-016). The four "first-doc one-time GPU phases" therefore form a coherent set, all colocated on the first successful per-doc entry.

## 5. Validation snippet

The minimal schema fragment a 0.1.3 per-document run_summary entry MUST satisfy:

```jsonc
"type": "object",
"additionalProperties": false,
"properties": {
  "phase_timings": {
    "type": "object",
    "additionalProperties": false,
    "properties": {
      "paddle_import":  {"$ref": "#/$defs/seconds_record"},  // optional
      "gpu_bind_probe": {"$ref": "#/$defs/seconds_record"},  // optional
      "engine_init":    {"$ref": "#/$defs/seconds_record"},  // optional
      "warmup":         {"$ref": "#/$defs/seconds_record"},  // optional, NEW in 0.1.3
      "rasterization":  {"$ref": "#/$defs/seconds_record"},  // optional
      "artifact_write": {"$ref": "#/$defs/seconds_record"},  // optional
      "total":          {"$ref": "#/$defs/seconds_record"}   // optional (always present in practice)
    }
  },
  "per_page_inference": {
    "type": "array",
    "items": {"$ref": "#/$defs/page_record"}  // optional sibling field
  }
},
"$defs": {
  "seconds_record": {
    "type": "object",
    "additionalProperties": false,
    "required": ["seconds"],
    "properties": { "seconds": {"type": "number", "minimum": 0} }
  },
  "page_record": {
    "type": "object",
    "additionalProperties": false,
    "required": ["page", "seconds"],
    "properties": {
      "page": {"type": "integer", "minimum": 1},
      "seconds": {"type": "number", "minimum": 0}
    }
  }
}
```

Note: the run_summary stdout line is not stored under `contracts/stage1_vendor_identity/`; it is run-level pipeline observability metadata (Constitution II / Quality Gate #2 inapplicability per plan.md). The fragment above is the contract this feature commits to but is enforced by `tests/pipeline_tests/test_run_summary_schema_0_1_3.py`, not by the stage 1 contract validator.

## 6. Backwards-compatibility guarantees

- Consumers parsing 0.1.2 must continue to parse 0.1.3 output: `phase_timings.warmup` is OPTIONAL and ADDITIVE.
- Consumers MUST NOT reject a run_summary as malformed if `phase_timings.warmup` is present. The lineage of additive 0.1.x bumps means consumers built for any 0.1.x version should ignore unknown optional keys (this is the long-standing additive-only rule from feature 014 FR-014, restated by feature 015 FR-014).
- Existing 0.1.2 fields (legacy flat `stages.preprocess.{total_seconds, gpu_init_seconds, gpu_inference_seconds}` and structured `phase_timings.{paddle_import, gpu_bind_probe, engine_init, rasterization, artifact_write, total}` plus sibling `per_page_inference`) are unchanged in name and shape.
- Legacy flat `gpu_init_seconds` continues to mean `paddle_import + gpu_bind_probe + engine_init` only — warmup time is NEVER folded in (FR-009).
- **Negative assertion (FR-009 explicit)**: warmup time MUST NOT inflate `stages.preprocess.gpu_init_seconds`, `stages.preprocess.gpu_inference_seconds`, or `stages.preprocess.total_seconds`. The legacy flat-key emission for a warmup-enabled run MUST be byte-identical to the same run without the warmup opt-in. This pins the contract for legacy 0.1.1 consumers — they continue to read identical numbers regardless of warmup state.

## 7. What this contract does NOT change

- `preprocess_output.json` shape: unchanged (FR-018 / SC-008).
- `edge_extraction_output.json`, `routing_decision.json`, `final_structured_payload.json` shapes: unchanged.
- `pipeline_version` suffix: still `.gpu0` for GPU runs, `.cpu0` for CPU runs (FR-020).
- The `kind: "run_summary"` top-level fields (`stack_preset`, `resolved_profiles`, `execution_slice`, `on_failure`, `documents_total`, `documents_succeeded`, `documents_failed`, `profile_initialization_seconds`, `per_document`, `preprocess_lane`): unchanged.
- The `contract_set_version` for stage 1 artifacts (`1.2.0`): unchanged. This feature does not amend `contracts/stage1_vendor_identity/AMENDMENTS.md` (FR-019 — no new persisted artifact, no stage 1 contract change).
