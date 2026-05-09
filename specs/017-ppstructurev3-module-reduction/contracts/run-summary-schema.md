# Run-Summary Schema 0.1.4 (additive `module_set_id` / `det_rec_variant_id` / `ppstructure_modules_invoked`)

**Feature**: 017-ppstructurev3-module-reduction
**Lineage**: 0.1.0 (feature 014) → 0.1.1 (feature 014 patch) → 0.1.2 (feature 015) → 0.1.3 (feature 016) → **0.1.4 (this feature)**
**Decision source**: spec FR-008, FR-009, FR-010, SC-003; research.md R-017.5, R-017.7, R-017.8; data-model.md (the three additive fields); /speckit.clarify Q2, Q3.

This contract describes the **only** addition this feature makes to the existing `kind: "run_summary"` stdout shape: three optional-but-always-emitted top-level fields. All other 0.1.3 fields (`schema_version`, `kind`, `stack_preset`, `resolved_profiles`, `execution_slice`, `on_failure`, `documents_total`, `documents_succeeded`, `documents_failed`, `profile_initialization_seconds`, `per_document` including all `phase_timings.*` keys with feature 016's `warmup`, `preprocess_lane`) are unchanged in name, shape, and semantics.

## 1. Codebase-level version bump

```python
# src/ledgerlinc_ocr/pipeline/timing.py
SCHEMA_VERSION = "0.1.4"  # was "0.1.3"
```

Every run of the new binary emits `schema_version: "0.1.4"` regardless of preset selection (R-017.8 / FR-008 / FR-010). The 0.1.4 schema is a strict superset of 0.1.3: adds three top-level always-emitted fields. Consumers built against 0.1.3 continue to read 0.1.4 output without changes.

## 2. New top-level fields

### 2.1 `module_set_id`

**Path**: `module_set_id` (top level on run_summary)
**Shape**: `<string>` — one of the closed-vocabulary values from R-017.2.
**Type**: string (required on every run of the new binary).
**Closed vocabulary at landing** (`{"legacy", "reduced-v1", "cpu-default", "stub-default"}`).

### 2.2 `det_rec_variant_id`

**Path**: `det_rec_variant_id` (top level on run_summary)
**Shape**: `<string>` — one of the closed-vocabulary values from R-017.4.
**Type**: string (required on every run of the new binary).
**Closed vocabulary at landing** (`{"legacy", "ppocrv5-mobile", "ppocrv4-mobile", "cpu-default", "stub-default"}`).

### 2.3 `ppstructure_modules_invoked`

**Path**: `ppstructure_modules_invoked` (top level on run_summary)
**Shape**: array of strings — subset of `AUDIT_SUB_MODULE_VOCABULARY = ("layout_detection", "table_recognition", "ocr_det", "ocr_rec")` (R-017.7).
**Type**: list (required on every run of the new binary).
**Determinism**: list elements MUST be sorted lexicographically. Empty list on `ppstructurev3@cpu` and stub adapter runs (no audit performed on non-GPU lanes per R-017.7).

## 3. Emission order on the run_summary line

The three new fields land in `RunSummary.to_dict()`'s emission order between the existing `preprocess_lane` (feature 014 T027 — last existing top-level field) and the run_summary's terminating brace:

```jsonc
{
  "kind": "run_summary",
  "schema_version": "0.1.4",
  "stack_preset": "...",
  "resolved_profiles": {...},
  "execution_slice": {...},
  "on_failure": "...",
  "documents_total": <int>,
  "documents_succeeded": <int>,
  "documents_failed": <int>,
  "profile_initialization_seconds": {...},
  "per_document": [...],
  "preprocess_lane": "cpu" | "gpu0" | ...,
  "module_set_id": "cpu-default" | "stub-default" | "legacy" | "reduced-v1",
  "det_rec_variant_id": "cpu-default" | "stub-default" | "legacy" | "ppocrv5-mobile" | "ppocrv4-mobile",
  "ppstructure_modules_invoked": ["layout_detection", "ocr_det", "ocr_rec"]
}
```

Stable insertion order keeps the run_summary line deterministic, which makes it easier to grep / diff across runs.

## 4. Presence rules (formal)

For a run_summary line `r` emitted by a binary with `SCHEMA_VERSION = "0.1.4"`:

```
r.module_set_id              is present  (always — required field)
r.det_rec_variant_id         is present  (always — required field)
r.ppstructure_modules_invoked is present  (always — required field; may be empty list)
```

Absence of any of the three fields on a 0.1.4-binary run_summary line is a regression (FR-010: "absence of either field is itself a regression signal"; extended here to include `ppstructure_modules_invoked` per /speckit.clarify Q3).

If the run exits before `RunSummary.to_dict()` is called (preflight failure, warmup failure, unknown-preset failure, etc.), no run_summary line is emitted at all — the no-emission case preserves feature 014/015/016 fail-fast surfaces and is NOT considered a regression.

## 5. Co-location with existing run-summary fields

The three new fields are top-level peers of `preprocess_lane` (feature 014 T027), `documents_total` (feature 014), and `schema_version` (feature 014). They are NOT nested under `phase_timings.*` (which is per-document and lives inside `per_document[*]`) and are NOT nested under any new wrapper object. The flat-top-level placement matches the additive-only pattern from features 014/015/016.

When `phase_timings.warmup` is present on `per_document[0]` (warmup ran successfully — feature 016), the three new top-level fields are also present on the same run_summary line; the four observability surfaces (warmup timing, module-set identifier, det/rec variant identifier, audit list) form a coherent set that operators can grep together.

## 6. Validation snippet

The minimal schema fragment a 0.1.4 run_summary line MUST satisfy:

```jsonc
{
  "type": "object",
  "required": [
    "kind", "schema_version", "module_set_id", "det_rec_variant_id",
    "ppstructure_modules_invoked"
    /* plus all existing required fields from 0.1.3 */
  ],
  "properties": {
    "schema_version":              { "const": "0.1.4" },
    "module_set_id":               { "type": "string", "enum": ["legacy", "reduced-v1", "cpu-default", "stub-default"] },
    "det_rec_variant_id":          { "type": "string", "enum": ["legacy", "ppocrv5-mobile", "ppocrv4-mobile", "cpu-default", "stub-default"] },
    "ppstructure_modules_invoked": {
      "type": "array",
      "items": { "type": "string", "enum": ["layout_detection", "table_recognition", "ocr_det", "ocr_rec"] },
      "uniqueItems": true
    }
  }
}
```

The contract is asserted by `tests/pipeline/test_run_summary_schema_0_1_4.py` on every CPU and stub run; the GPU-marked verification asserts the same contract under the live GPU configurations (deferred per FR-024 if workstation GPU is unavailable).

## 7. Stability stance

The three field names, their JSON types, their emission position, the closed vocabularies of `module_set_id` / `det_rec_variant_id`, and the closed `AUDIT_SUB_MODULE_VOCABULARY` for `ppstructure_modules_invoked` items are part of the public 0.1.4 contract. Tests, monitoring, and downstream consumers MAY assert all three are always present and that their values fall within the closed vocabularies. Adding a new value to any of the three closed vocabularies (e.g., `reduced-v2`, `ppocrv5-server-quantized`, a new sub-module name) is a future-feature decision and triggers a `SCHEMA_VERSION` patch bump (0.1.4 → 0.1.5 etc.) under the same additive-only convention.
