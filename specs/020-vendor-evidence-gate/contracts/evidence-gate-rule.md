# Evidence Gate Rule: `v1` decision table

This document is the authoritative specification of the `v1` evidence-gate rule body. An operator inspecting a recorded `run_summary` MUST be able to re-derive every `evidence_gate_documents[i].decision` value by applying this table to the recorded `signals` object (SC-002 / SC-012). The table itself is the contract.

---

## Closed-vocabulary preset registry

At landing the registry contains exactly one entry:

| `evidence_gate_id` | Rule body | Active? |
|---|---|---|
| `"v1"` | This document | Yes (the default and only entry at landing) |

Future presets `"v2"`, `"v3"`, ... are added via additive code change in `preprocessing/evidence_gate.py`. Adding a new preset requires:
1. A new `EvidenceGate` registry entry with its own decision-table body.
2. A new `contracts/evidence-gate-rule.md` section documenting the new body.
3. A new selection flag (`--evidence-gate <id>` + `LEDGERLINC_EVIDENCE_GATE` env var) at the CLI level (the registry has size two or more at that point, so selection is meaningful — see R-020.2).
4. An entry in the FR-005 / FR-007 closed-vocabulary documentation.

The closed-vocabulary semantics mean: an unknown `evidence_gate_id` value is a developer error, not a runtime preset-selection error. There is no `UnknownPresetError` extension because there is no CLI-time selection at landing (R-020.2).

---

## V1 decision table

The `v1` rule body is a deterministic function of the five-signal record `FiveSignalSet`:

```
sufficient   iff  has_name AND has_density AND has_confidence AND (has_suffix OR has_tax_id)
insufficient iff  NOT has_name AND NOT has_density AND NOT has_confidence AND NOT has_suffix AND NOT has_tax_id
borderline   otherwise  (residual)
```

Where:
- `has_name = signals.vendor_name_candidate_count >= 1`
- `has_density = signals.header_band_token_density >= 8` (constant `DENSITY_THRESHOLD = 8`, R-020.6)
- `has_confidence = signals.ocr_detection_confidence_mean >= 0.70` (constant `CONFIDENCE_THRESHOLD = 0.70`, R-020.6)
- `has_suffix = signals.business_suffix_present` (boolean from R-020.4 regex match)
- `has_tax_id = signals.tax_id_shaped_present` (boolean from R-020.4 regex match)

All comparisons are inclusive-on-the-high-side (`>=`). Threshold boundary values qualify as the positive level:
- `header_band_token_density == 8` ⇒ `has_density = True`.
- `ocr_detection_confidence_mean == 0.70` ⇒ `has_confidence = True`.
- `vendor_name_candidate_count == 1` ⇒ `has_name = True`.

---

## Decision table (canonical form)

The full truth table over the five boolean derivatives (`has_name`, `has_density`, `has_confidence`, `has_suffix`, `has_tax_id`) — 32 rows — is:

| has_name | has_density | has_confidence | has_suffix | has_tax_id | Decision |
|---|---|---|---|---|---|
| T | T | T | T | T | sufficient |
| T | T | T | T | F | sufficient |
| T | T | T | F | T | sufficient |
| T | T | T | F | F | borderline |
| T | T | F | T | T | borderline |
| T | T | F | T | F | borderline |
| T | T | F | F | T | borderline |
| T | T | F | F | F | borderline |
| T | F | T | T | T | borderline |
| T | F | T | T | F | borderline |
| T | F | T | F | T | borderline |
| T | F | T | F | F | borderline |
| T | F | F | T | T | borderline |
| T | F | F | T | F | borderline |
| T | F | F | F | T | borderline |
| T | F | F | F | F | borderline |
| F | T | T | T | T | borderline |
| F | T | T | T | F | borderline |
| F | T | T | F | T | borderline |
| F | T | T | F | F | borderline |
| F | T | F | T | T | borderline |
| F | T | F | T | F | borderline |
| F | T | F | F | T | borderline |
| F | T | F | F | F | borderline |
| F | F | T | T | T | borderline |
| F | F | T | T | F | borderline |
| F | F | T | F | T | borderline |
| F | F | T | F | F | borderline |
| F | F | F | T | T | borderline |
| F | F | F | T | F | borderline |
| F | F | F | F | T | borderline |
| F | F | F | F | F | insufficient |

3 rows fire `sufficient`, 1 row fires `insufficient`, 28 rows fire `borderline`.

---

## Re-derivation procedure (operator-facing)

Given a recorded `evidence_gate_documents[i]` element:

```json
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
```

To re-derive the decision:

1. Compute the five boolean derivatives:
   - `has_name = 3 >= 1` ⇒ `True`
   - `has_density = 14 >= 8` ⇒ `True`
   - `has_confidence = 0.84 >= 0.70` ⇒ `True`
   - `has_suffix = True`
   - `has_tax_id = False`
2. Evaluate `has_name AND has_density AND has_confidence AND (has_suffix OR has_tax_id)`:
   - `True AND True AND True AND (True OR False) = True AND True AND True AND True = True`
3. Since the `sufficient` condition is true, the decision is `sufficient`.
4. Verify: recorded `decision = "sufficient"`. Match ⇒ SC-012 holds for this document.

If the re-derived decision does NOT match the recorded decision, this is a determinism violation and is a regression (FR-001 / SC-002).

---

## Boundary cases

| Scenario | Derivatives | Decision |
|---|---|---|
| Single-token vendor name with all-caps and dense band | `has_name=True, has_density=True, has_confidence=True, has_suffix=False, has_tax_id=False` | `borderline` (no suffix/tax-id) |
| Vendor name + suffix but low confidence | `has_name=True, has_density=True, has_confidence=False (0.65), has_suffix=True, has_tax_id=False` | `borderline` (low confidence) |
| Sparse band but contains suffix | `has_name=False, has_density=False (5 tokens), has_confidence=True, has_suffix=True, has_tax_id=False` | `borderline` |
| Completely blank page | `has_name=False, has_density=False (0 tokens), has_confidence=False (0.0 default), has_suffix=False, has_tax_id=False` | `insufficient` |
| Header has all three: name, density, confidence, suffix | `has_name=True, has_density=True, has_confidence=True, has_suffix=True, has_tax_id=False` | `sufficient` |
| Header has name, density, confidence, AND tax-id (no suffix) | `has_name=True, has_density=True, has_confidence=True, has_suffix=False, has_tax_id=True` | `sufficient` |

---

## Re-derivability guarantee (FR-001 / FR-004 / SC-002 / SC-012)

The `EvidenceGate.evaluate(input_dict)` function MUST be defined such that, for any `FiveSignalSet` `s` and any `EvidenceGateResult` `r` produced by the evaluation:

```
r.decision == v1_decide(r.signals)
```

This is enforced by `test_evidence_gate_decision_unit.py` over a parameterized table of synthetic `FiveSignalSet` inputs covering all 32 truth-table rows above.

An operator who inspects `run_summary` on disk and applies this table to each `evidence_gate_documents[i].signals` MUST get the recorded `evidence_gate_documents[i].decision` value back exactly. There is no per-document state, per-run randomness, or model judgment in the loop (FR-027).

---

## Threshold rationale (R-020.6)

| Threshold | Value | Rationale |
|---|---|---|
| `DENSITY_THRESHOLD` | `8` | Empirical median of header-band token counts across the feature 017/018/019 benchmark subset. Excludes near-blank pages and title-only blocks. May be revised at the next preset (`v2`) after broader corpus calibration. |
| `CONFIDENCE_THRESHOLD` | `0.70` | Matches feature 019's R-019.6 FR-005 trigger threshold for the confidence-mean signal. Higher than the FR-005 fallback threshold (`0.60`) because `sufficient` is a stronger claim than "OCR is good enough to keep" — it asserts that the OCR-only output is good enough to vouch for vendor-identity sufficiency. |
| `Y_THRESHOLD_FRACTION` | `0.25` | Top-25% of page 1 by y-coordinate covers the typical invoice header block (per feature 018's header-first-v1 calibration). Dimension-invariant across US Letter / A4 / Legal page sizes. |
| Vendor-name candidate rule (token count `>= 2 chars`, starts uppercase or title-case or all-caps, not all-digit, not in stop-word set) | (see R-020.3) | Conservative heuristic that excludes common false positives (invoice number tokens like `12345`, header words like `INVOICE`, `BILL`) while accepting legitimate vendor-name tokens (`Acme`, `AcmeCorp`, `ACME`, `Acme-Corp.`, etc.). |

---

## Versioning policy

The `v1` decision table is frozen at landing. Any change to:
- the thresholds (`DENSITY_THRESHOLD`, `CONFIDENCE_THRESHOLD`, `Y_THRESHOLD_FRACTION`),
- the decision-table cells,
- the per-signal computation rules,
- the FR-001 closed signal set,

requires a new `evidence_gate_id` value (`"v2"`, `"v3"`, ...) — never a runtime knob. Operators reading the recorded `evidence_gate_id` on `run_summary` can always look up the corresponding contract document under `contracts/evidence-gate-rule.md` to re-derive the decision.

This policy mirrors feature 017's `module_set_id` versioning, feature 018's `raster_profile_id` / `region_strategy_id` versioning, and feature 019's `preprocess_strategy_id` versioning.
