# Phase 1 Data Model: Vendor-Identity Evidence Gate

This document specifies the entities, types, validation rules, and state transitions added by feature 020. All entities live in-process; nothing is persisted to a new file (FR-021). The four canonical stage 1 artifact schemas are unchanged.

---

## 1. Gate preset surface (closed vocabulary)

**Module**: `preprocessing/evidence_gate.py`
**Kind**: module-level constants + `decide_for_gate(gate_id, signals)` dispatch function (a flatter form than the original 1-element registry — see B post-review reconciliation).
**Purpose**: Identify the active gate-rule body for a run; future iterations add additional dispatch branches.

The preset surface comprises:

| Symbol | Type | Notes |
|---|---|---|
| `EVIDENCE_GATE_ID_V1` | `str` constant | Value `"v1"`. The only valid `evidence_gate_id` at landing. |
| `EVIDENCE_GATE_ID_DEFAULT` | `str` constant | Currently identical to `EVIDENCE_GATE_ID_V1`. |
| `Y_THRESHOLD_FRACTION` | `Final[float]` | Page-1 header-band coordinate scope, in fraction of page height. Value: `0.25` (R-020.5). |
| `DENSITY_THRESHOLD` | `Final[int]` | Threshold for `header_band_token_density` (R-020.6). Value: `8`. |
| `CONFIDENCE_THRESHOLD` | `Final[float]` | Threshold for `ocr_detection_confidence_mean` (R-020.6). Value: `0.70`. |
| `decide_for_gate(gate_id, signals)` | `(str, FiveSignalSet) -> GateDecision` | Dispatch hook. At landing only `"v1"` is accepted; any other id raises `KeyError`. Future presets (`"v2"`, `"v3"`, ...) land additive branches here per R-020.2. |
| `evaluate_evidence_gate(preprocess_output, gate_id="v1")` | `(dict, str) -> EvidenceGateResult` | Top-level entry point: compute signals + dispatch + bundle result. |

**Validation**:
- `gate_id` MUST be `"v1"`; `evaluate_evidence_gate` and `decide_for_gate` raise `KeyError` otherwise.
- `Y_THRESHOLD_FRACTION` satisfies `0.0 < y_threshold_fraction < 1.0`.
- `DENSITY_THRESHOLD` is `>= 0`.
- `CONFIDENCE_THRESHOLD` satisfies `0.0 <= confidence_threshold <= 1.0`.
- The decision function is pure: same input ⇒ same output across reruns and hosts (FR-001 / SC-001).

**v1 dispatch sketch**:
```python
def decide_for_gate(gate_id: str, signals: FiveSignalSet) -> GateDecision:
    if gate_id != EVIDENCE_GATE_ID_V1:
        raise KeyError(f"unknown evidence gate id: {gate_id!r}")
    return _v1_decide(signals)
```

**Rationale for the flatter shape** (B post-review reconciliation): the original plan called for an `EvidenceGate` dataclass + `EVIDENCE_GATES = {"v1": EvidenceGate(...)}` registry. With registry size exactly one at landing, the dataclass + Callable indirection was scaffolding for a v2 that has no spec yet — YAGNI per the project constitution. The collapsed form preserves the R-020.2 extension contract (additive code change to land v2) without the dataclass overhead.

**State transitions**: None. Module-level constants are immutable; the dispatch function is stateless.

---

## 2. `FiveSignalSet`

**Module**: `preprocessing/evidence_gate.py`
**Kind**: frozen dataclass (or `pydantic.BaseModel` with `frozen=True`)
**Purpose**: Carry the five computed signal values for one document (R-020.3).

| Field | Type | Range | Notes |
|---|---|---|---|
| `vendor_name_candidate_count` | `int` | `>= 0` | Count of vendor-name-candidate tokens in the page-1 header band. |
| `header_band_token_density` | `int` | `>= 0` | Total non-whitespace tokens in the page-1 header band. |
| `ocr_detection_confidence_mean` | `float` | `0.0 <= x <= 1.0` | Arithmetic mean of `confidence` across detection boxes in the band; `0.0` when band is empty. |
| `business_suffix_present` | `bool` | — | `True` iff any band token matches `BUSINESS_SUFFIX_RE` (R-020.4). |
| `tax_id_shaped_present` | `bool` | — | `True` iff any band token matches `TAX_ID_EIN_RE` OR `TAX_ID_VAT_RE` (R-020.4). |

**Validation**:
- All five fields MUST be present (no `None` / `null`).
- Numeric fields MUST be finite (no `NaN`, no `Infinity`).
- `ocr_detection_confidence_mean` MUST be in `[0.0, 1.0]` inclusive.

**State transitions**: None. `FiveSignalSet` is immutable once constructed by `evaluate_evidence_gate(...)`.

**JSON serialization** (when emitted inside `evidence_gate_documents.signals`):
```json
{
    "vendor_name_candidate_count": 3,
    "header_band_token_density": 14,
    "ocr_detection_confidence_mean": 0.84,
    "business_suffix_present": true,
    "tax_id_shaped_present": false
}
```
Field order is deterministic and matches the dataclass field order.

---

## 3. `EvidenceGateResult`

**Module**: `preprocessing/evidence_gate.py`
**Kind**: frozen dataclass (or `pydantic.BaseModel` with `frozen=True`)
**Purpose**: Carry the gate evaluation output for one document — the signal values + the decision.

| Field | Type | Notes |
|---|---|---|
| `signals` | `FiveSignalSet` | The five recorded signal values. |
| `decision` | `Literal["sufficient", "borderline", "insufficient"]` | The decision drawn from the gate's decision table over `signals`. |
| `evidence_gate_id` | `str` | The active gate-rule identifier (R-020.2). For v1 always `"v1"`. |

**Validation**:
- `decision` MUST be one of the three values in the closed-vocabulary.
- `decision` MUST equal `decide_for_gate(evidence_gate_id, signals)` (SC-002 / SC-012 — re-derivability constraint).

**State transitions**: None.

**JSON serialization** (inside `evidence_gate_documents` array elements, with `document_id` added by the caller):
```json
{
    "document_id": "inv_001_easy",
    "decision": "sufficient",
    "signals": { "...": "..." }
}
```
The `evidence_gate_id` is not repeated per-document — it appears once on the top-level `run_summary` field.

---

## 4. `EvidenceGateDocumentRecord` (per-document run_summary entry)

**Module**: `preprocessing/evidence_gate.py` (alias) / used by `pipeline/timing.py`'s `RunSummary`
**Kind**: TypedDict or dataclass; serialized as JSON object
**Purpose**: One element of the top-level `evidence_gate_documents` array on `run_summary`.

| Field | Type | Notes |
|---|---|---|
| `document_id` | `str` | Per-document folder name relative to the corpus root (R-020.11). Examples: `"inv_001_easy"`, `"inv_002_easy"`. |
| `decision` | `Literal["sufficient", "borderline", "insufficient"]` | The gate decision over the document's FINAL `preprocess_output.json` (R-020.7). |
| `signals` | `FiveSignalSet` (serialized as nested object) | The five signal values used to compute `decision`. |

**Validation**:
- `document_id` MUST be a non-empty string.
- `decision` MUST be in the closed-vocabulary `{"sufficient", "borderline", "insufficient"}`.
- `signals` MUST satisfy the `FiveSignalSet` validation rules.
- The triple `(document_id, decision, signals)` MUST be re-derivable: applying the documented v1 decision table to `signals` MUST yield `decision` exactly (SC-002 / SC-012).

**Ordering invariant**: The `evidence_gate_documents` array is ordered by per-document iteration order in `corpus_run.py` (typically alphabetical by `document_id`). Two runs over the same corpus with the same configuration produce arrays in identical order with identical contents.

---

## 5. `RunSummary` additive fields (extends feature 019's RunSummary)

**Module**: `pipeline/timing.py`
**Kind**: dataclass extension; codebase-level `SCHEMA_VERSION` bump 0.1.6 → 0.1.7
**Purpose**: Carry the four new top-level fields on every emitted `kind: "run_summary"` stdout line.

| New top-level field | Type | Default | Notes |
|---|---|---|---|
| `evidence_gate_id` | `str` | `EVIDENCE_GATE_ID_DEFAULT` (= `"v1"`) | Active gate-rule identifier; always present (R-020.2 / FR-010). |
| `evidence_gate_state_counts` | `dict[str, int]` | `{"sufficient": 0, "borderline": 0, "insufficient": 0}` | Aggregate count of per-document decisions across the run; always present with default-zero counters for all three states (R-020.10 / FR-006 / FR-008). |
| `evidence_gate_documents` | `list[EvidenceGateDocumentRecord]` | `[]` | One record per document the gate evaluated on the run; always present (default empty when no documents reached the gate); ordered per `corpus_run.py` iteration (R-020.11). |
| `evidence_gate_suppressed_fallback_count` | `int` | `0` | Count of documents where shape (b) suppression actually fired on this run (R-020.8 / FR-007 / FR-008). |

**Always-emit invariant**: All four fields MUST appear on every run of the new binary, including default `ppstructurev3@cpu` runs, stub-adapter runs, and `ppstructurev3@gpu` runs without the opt-in (FR-008 / FR-010 / SC-003).

**Order invariant**: Emitted in `RunSummary.to_dict()` AFTER feature 019's fields and BEFORE any future additive fields. Existing keys (paddle_import, gpu_bind_probe, engine_init, warmup, rasterization, per_page_inference, artifact_write, total, module_set_id, det_rec_variant_id, ppstructure_modules_invoked, raster_profile_id, region_strategy_id, region_strategy_fallback_count, preprocess_strategy_id, ocr_only_fallback_count) MUST NOT be renamed, removed, or retyped (FR-011 / FR-022).

**JSON example** (full `run_summary` after the bump):
```json
{
    "kind": "run_summary",
    "schema_version": "0.1.7",
    "phase_timings": { "...": "..." },
    "module_set_id": "minimal-text-only",
    "det_rec_variant_id": "lightweight-v1",
    "ppstructure_modules_invoked": ["text_detection", "text_recognition"],
    "raster_profile_id": "150dpi-v1",
    "region_strategy_id": "header-first-v1",
    "region_strategy_fallback_count": 0,
    "preprocess_strategy_id": "ocr-only-v1",
    "ocr_only_fallback_count": 0,
    "evidence_gate_id": "v1",
    "evidence_gate_state_counts": {"sufficient": 3, "borderline": 1, "insufficient": 1},
    "evidence_gate_documents": [
        {
            "document_id": "inv_001_easy",
            "decision": "sufficient",
            "signals": {
                "vendor_name_candidate_count": 3,
                "header_band_token_density": 14,
                "ocr_detection_confidence_mean": 0.84,
                "business_suffix_present": true,
                "tax_id_shaped_present": false
            }
        }
    ],
    "evidence_gate_suppressed_fallback_count": 1
}
```

---

## 6. Module-level regex constants (R-020.4)

**Module**: `preprocessing/evidence_gate.py`
**Kind**: compiled `re.Pattern` constants at module load time

| Name | Pattern | Flags | Matches |
|---|---|---|---|
| `BUSINESS_SUFFIX_RE` | `r"(?i)\b(LLC\|Incorporated\|Inc\|Limited\|Ltd\|GmbH\|S\.A\.S\.\|S\.A\.\|Corporation\|Corp\|Co\.)(?!\w)"` | `re.IGNORECASE` via `(?i)` flag in pattern | Common business-entity suffixes (English, French, Spanish, German); case-insensitive. Trailing `(?!\w)` (vs. `\b`) lets `.`-suffixed forms match at end-of-string; longer alternatives listed before their prefixes. |
| `TAX_ID_EIN_RE` | `r"\b\d{2}-\d{7}\b"` | none | US EIN canonical shape `XX-XXXXXXX`. |
| `TAX_ID_VAT_RE` | `r"\b[A-Z]{2}(?=[A-Z0-9]{2,12}\b)[A-Z0-9]*\d[A-Z0-9]*\b"` | none | EU-style VAT shape: 2-letter country prefix + 2..12 alphanumerics with **at least one digit**. The digit requirement rejects all-letter invoice header words (`INVOICE`, `PAYMENT`, `NUMBER`, `BALANCE`, ...) that the prior `[A-Z]{2}[A-Z0-9]{2,12}` pattern falsely matched. |

**Validation invariants**:
- All three patterns MUST compile at module load (a regex compilation error is a developer error, not a runtime error).
- Patterns MUST be applied only to whitespace-tokenized strings drawn from `preprocess_output.json` block/box text fields after NFKC Unicode normalization.
- Matching is whole-token; `\b` (or `(?!\w)`) boundaries ensure substring matches inside larger words do not count.

---

## 7. Module-level numeric constants (R-020.5 / R-020.6)

**Module**: `preprocessing/evidence_gate.py`

| Constant | Type | Value | Source | Used by |
|---|---|---|---|---|
| `Y_THRESHOLD_FRACTION` | `float` | `0.25` | R-020.5 | Page-1 header-band coordinate filter |
| `DENSITY_THRESHOLD` | `int` | `8` | R-020.6 | `header_band_token_density >= threshold` |
| `CONFIDENCE_THRESHOLD` | `float` | `0.70` | R-020.6 | `ocr_detection_confidence_mean >= threshold` |

All three constants are module-level frozen constants; they are NOT operator-tunable. A future preset (`v2`) would land via an additive `_v2_decide` function + a new `decide_for_gate` branch with its own thresholds (referenced from new module-level constants), not by mutating these.

---

## 8. Stop-word set for vendor-name-candidate (R-020.3)

**Module**: `preprocessing/evidence_gate.py`
**Kind**: `frozenset[str]` constant at module load

```python
VENDOR_NAME_STOP_WORDS: Final[frozenset[str]] = frozenset({
    "INVOICE", "BILL", "TAX", "DATE", "PAGE", "NUMBER",
    "TOTAL", "AMOUNT", "DUE", "PAYMENT", "FROM", "TO",
})
```

Used by `vendor_name_candidate_count` computation to exclude common invoice header tokens that ARE uppercase / title-case but are not vendor names. Case-folded comparison.

---

## 9. CPU/stub identity values for `evidence_gate_id` (R-020.2)

**Decision**: Feature 020 emits `evidence_gate_id = "v1"` uniformly on CPU profiles, stub adapter runs, and GPU runs at landing. There is no `cpu-default` or `stub-default` identity value for the gate because the gate computation IS the same across profiles — it is a pure read over `preprocess_output.json` content (FR-014).

Contrast with feature 019's `preprocess_strategy_id` which uses `cpu-default` / `stub-default` identity values: feature 019's strategy is a GPU-runtime construct (which actual preprocessing engine to use), so non-GPU profiles need an identity value. Feature 020's gate is a CPU-safe pure-function construct, so no identity value is needed.

---

## 10. State transitions and side effects

The evidence gate is **stateless** at module level. There are no in-process mutable globals. Each call to `evaluate_evidence_gate(preprocess_output_dict, *, gate_id="v1")` is a pure function: same input ⇒ same output across reruns and hosts (SC-001).

Side effects under feature 020:
- `preprocessing/pipeline.py`: when the suppression predicate (R-020.8) returns `True`, the OCR-only candidate `preprocess_output.json` is kept as the document's final preprocessing output INSTEAD of triggering feature 019's PPStructureV3 fallback. This side effect is operator-visible via `evidence_gate_suppressed_fallback_count` on `run_summary`.
- `pipeline/timing.py`: `RunSummary.SCHEMA_VERSION` is bumped from `"0.1.6"` to `"0.1.7"` and four new top-level fields are emitted on every run.
- `preprocessing/cli.py` / `pipeline/cli.py`: a new boolean opt-in flag `--evidence-gate-skip-fallback` is accepted; when set on a non-GPU profile, a stderr warn line is emitted and the run proceeds unchanged (R-020.12).

No state is persisted across runs (FR-021 / no new artifact). All state lives in the in-process `RunSummary` instance and is emitted on the single `kind: "run_summary"` stdout line at run completion.
