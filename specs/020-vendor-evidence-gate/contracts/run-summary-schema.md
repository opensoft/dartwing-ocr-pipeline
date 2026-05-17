# Run-Summary Schema: Codebase-Level Bump 0.1.6 → 0.1.7

Feature 020 adds **four additive top-level fields** to the single `kind: "run_summary"` stdout line that `pipeline/timing.py` emits at run completion. `SCHEMA_VERSION` patches from `"0.1.6"` to `"0.1.7"`. No JSON Schema file is written; the bump is codebase-level only.

The four canonical stage 1 artifact schemas (`preprocess_output.schema.json`, `edge_extraction_output.schema.json`, `routing_decision.schema.json`, `final_structured_payload.schema.json`), the active `contract_set_version`, and the `pipeline_version` shape are **unchanged** (FR-020 / SC-007 / SC-010 / Constitution II).

---

## Schema-version bump

| Property | Before | After |
|---|---|---|
| Pinned constant in `pipeline/timing.py` | `SCHEMA_VERSION = "0.1.6"` | `SCHEMA_VERSION = "0.1.7"` |
| Emitted JSON value | `"schema_version": "0.1.6"` | `"schema_version": "0.1.7"` |
| Change type | n/a | Patch (additive only) |

Patch-level signals that no existing field's name, type, or default is changed (R-020.9). Consumers reading prior fields by name continue to work unchanged. Only consumers of the four new fields need to read the bumped version.

---

## Four additive top-level fields

The fields are emitted in this deterministic order, AFTER feature 019's `preprocess_strategy_id` and `ocr_only_fallback_count` and BEFORE any future additive field:

### 1. `evidence_gate_id`

| Property | Value |
|---|---|
| JSON path | `$.evidence_gate_id` |
| JSON type | `string` |
| Default | `"v1"` (closed vocabulary; size one at landing — see `evidence-gate-rule.md`) |
| Always emitted | Yes |
| Source FR / R | FR-010 / R-020.2 |
| Closed-vocabulary values at landing | `["v1"]` |

### 2. `evidence_gate_state_counts`

| Property | Value |
|---|---|
| JSON path | `$.evidence_gate_state_counts` |
| JSON type | `object` |
| Object shape | `{"sufficient": int, "borderline": int, "insufficient": int}` |
| Default | `{"sufficient": 0, "borderline": 0, "insufficient": 0}` |
| Always emitted | Yes (all three keys present even when all counters are zero — NOT sparse) |
| Source FR / R | FR-006 / FR-008 / R-020.10 |

### 3. `evidence_gate_documents`

| Property | Value |
|---|---|
| JSON path | `$.evidence_gate_documents` |
| JSON type | `array` of objects |
| Element shape | `{"document_id": string, "decision": string, "signals": object}` |
| Default | `[]` (empty array) |
| Always emitted | Yes |
| Source FR / R | FR-003 / FR-006 / R-020.10 / R-020.11 |
| Element ordering | Deterministic per `corpus_run.py` iteration (typically alphabetical by `document_id`) |

Per-element `signals` object shape:

```json
{
    "vendor_name_candidate_count": int,
    "header_band_token_density": int,
    "ocr_detection_confidence_mean": float,
    "business_suffix_present": bool,
    "tax_id_shaped_present": bool
}
```

Per-element `decision` value MUST be one of `"sufficient"`, `"borderline"`, `"insufficient"` (closed vocabulary, see `evidence-gate-rule.md`).

### 4. `evidence_gate_suppressed_fallback_count`

| Property | Value |
|---|---|
| JSON path | `$.evidence_gate_suppressed_fallback_count` |
| JSON type | `integer` |
| Default | `0` |
| Always emitted | Yes |
| Source FR / R | FR-007 / FR-008 / R-020.8 |
| Increment rule | Increments by exactly `1` per document where the FR-007 / R-020.8 suppression predicate returned `True` (i.e., the OCR-only-fast-lane fallback to PPStructureV3 was suppressed because the gate decision on the OCR-only candidate was `sufficient`). |

---

## Field-emission rules (always-emit pattern)

All four fields MUST be emitted on EVERY run of the new binary, including:
- `ppstructurev3@gpu` runs (with or without the opt-in)
- `ppstructurev3@cpu` runs (CPU profile)
- Stub-adapter runs
- Single-document runs via `python -m dartwing_ocr.preprocessing`
- Corpus runs via `python -m dartwing_ocr.pipeline`

Absence of any of these four fields on a run of the new binary is itself a regression signal (SC-003 / MI-16 / MI-17 in `module-invariants.md`).

Each field is emitted regardless of whether the gate actually evaluated any documents on the run. A run that processed zero documents (e.g., a stub-adapter run with no input list) emits:

```json
{
    "kind": "run_summary",
    "schema_version": "0.1.7",
    "...": "(feature 014-019 fields unchanged)",
    "evidence_gate_id": "v1",
    "evidence_gate_state_counts": {"sufficient": 0, "borderline": 0, "insufficient": 0},
    "evidence_gate_documents": [],
    "evidence_gate_suppressed_fallback_count": 0
}
```

---

## Order of keys in `RunSummary.to_dict()`

The emitted JSON key order is deterministic. The authoritative source is `pipeline/timing.py::RunSummary.to_dict()`; this section documents the order so a reader can verify by inspection. After feature 020 lands, the full ordered emission is:

```
kind, schema_version, stack_preset, resolved_profiles, execution_slice, on_failure,
documents_total, documents_succeeded, documents_failed,
profile_initialization_seconds, per_document,
preprocess_lane,
module_set_id, det_rec_variant_id, ppstructure_modules_invoked,
raster_profile_id, region_strategy_id, region_strategy_fallback_count,
preprocess_strategy_id, ocr_only_fallback_count,
evidence_gate_id, evidence_gate_state_counts, evidence_gate_documents, evidence_gate_suppressed_fallback_count
```

The four new feature-020 fields are appended at the end; no pre-020 field is renamed, removed, or repositioned. Per-document records (inside `per_document`) and `phase_timings` continue to follow the feature-015 / feature-016 ordering rules established in those features' contracts.

---

## Cross-feature compatibility

Field renames / removals / retypes by this feature: **none** (FR-011 / FR-022 / MI-19).

The following features' surfaces are preserved byte-for-byte on a no-opt-in run:
- Feature 014: `preprocess_profile`, `phase_timings.*`.
- Feature 015: single-engine-construction guarantee surface in `phase_timings`.
- Feature 016: `phase_timings.warmup`, `--gpu-warmup` opt-in semantics.
- Feature 017: `module_set_id`, `det_rec_variant_id`, `ppstructure_modules_invoked`.
- Feature 018: `raster_profile_id`, `region_strategy_id`, `region_strategy_fallback_count`.
- Feature 019: `preprocess_strategy_id`, `ocr_only_fallback_count`.

`test_run_summary_schema_0_1_7.py` reads a captured pre-feature-020 `run_summary` and asserts every key is still present in the post-bump emission with the same type and (where applicable) default-zero value.

---

## Forbidden surface changes

- Adding gate-related fields inside any of the four canonical stage 1 artifacts (`preprocess_output`, `edge_extraction_output`, `routing_decision`, `final_structured_payload`) is forbidden.
- Adding `phase_timings.evidence_gate` or any nested `phase_timings` key for gate timing is out of scope; the gate is cheap pure-Python work and is not separately timed in this feature.
- Emitting per-document gate records on a separate stdout `kind:` line (e.g., `kind: "evidence_gate_document"`) is forbidden — Clarifications Q3 explicitly chose shape (a) single-line over shape (b) per-document lines.
- Writing a sidecar JSON artifact for per-document gate data is forbidden — Clarifications Q3 explicitly rejected this, and FR-021 confirms no new persisted artifact.

---

## Verification

CPU-safe tests in `tests/pipeline_tests/`:

1. `test_run_summary_schema_0_1_7.py` — asserts the bump from `"0.1.6"` to `"0.1.7"` and the presence of all four new fields on stub-adapter and CPU runs.
2. `test_evidence_gate_runsummary_aggregation.py` (synthetic RunSummary level) + `test_evidence_gate_pipeline_integration.py` (real on-disk wiring) — together assert that `evidence_gate_state_counts[s]` equals `count(evidence_gate_documents | .decision == s)` for each closed-vocabulary state.
3. `test_legacy_byte_identity_evidence_gate.py` (CPU variant) — **lands on stacked PR #39 (US6)**, NOT on PR #38. Asserts feature 014–019 surface bytes are unchanged on a no-opt-in run. The byte-identity contract is enforced on PR #38 by `test_run_summary_schema_0_1_7.py::test_features_014_to_019_keys_byte_identical_to_baseline`, which value-parity-compares every pre-020 key against the captured `tests/fixtures/feature_020_baseline/run_summary_pre_020.json` baseline.

GPU-marked tests (deferrable per R-020.15):

4. `test_evidence_gate_skip_fallback.py @gpu` — asserts `evidence_gate_suppressed_fallback_count` increment on the `sufficient` path.
5. `test_evidence_gate_skip_fallback_borderline.py @gpu` — asserts the counter does NOT increment on the `borderline` path.
