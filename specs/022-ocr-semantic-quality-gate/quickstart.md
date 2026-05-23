# Quickstart: OCR Semantic Quality Gate

Feature 022 adds a deterministic, evaluator/harness-owned semantic table quality gate for invoice body/table OCR. It is strictly evaluator-only: it does not alter pipeline preprocessing, extraction, routing, or final-payload behavior at landing (Clarifications Q3 / FR-033). The gate is triggered automatically inside the existing evaluator whenever a per-document folder contains a `semantic_table_truth.json` sidecar — the sidecar's presence is the opt-in, and no new CLI flag is introduced (Clarifications Q13). All paths below run on CPU; no GPU is required.

---

## Prerequisites

- Python 3.12 devcontainer (existing), or a host Python 3.12 environment.
- No GPU required. The semantic gate is a pure-Python, in-memory deterministic comparison; it has no Paddle, no model runtime, and no network dependency.
- Install the package from the worktree root:
  ```bash
  python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
  ```
- Confirm the contract set has been bumped to 1.3.0:
  ```bash
  python -m dartwing_ocr.validator show contract-set
  ```
  Expected output includes `contract_set_version = "1.3.0"`. If it shows `1.2.0`, the feature has not yet landed in the current installation.

---

## Path 1 — Author and validate a sidecar

A `semantic_table_truth.json` sidecar lives alongside `source.pdf` and `expected.json` in a per-document folder. Its top-level shape is `{document_id, rows[], schema_version?}` where `document_id` must match the folder basename.

**Example sidecar** for `tests/stage1_semantic_quality/inv_001_hard/semantic_table_truth.json`:

```json
{
  "document_id": "inv_001_hard",
  "schema_version": "1.3.0",
  "rows": [
    {
      "row_id": "row-1",
      "description": "Widget Assembly",
      "quantity": "5",
      "unit_price": "21.00",
      "amount": "105.00",
      "required_row_text_tokens": ["Widget", "Assembly", "5", "21.00", "105.00"]
    },
    {
      "row_id": "row-2",
      "description": "Shipping Surcharge",
      "amount": "12.50",
      "required_row_text_tokens": ["Shipping", "Surcharge", "12.50"]
    },
    {
      "row_id": "row-3",
      "description": "Consulting Services",
      "unit_price": "150.00",
      "amount": "300.00",
      "required_row_text_tokens": ["Consulting", "Services", "150.00", "300.00"]
    }
  ]
}
```

Key authoring rules (Clarifications Q2, Q8, Q9, Q11, Q27, Q28):

- `row_id` — non-empty string, unique within the sidecar. Mandatory.
- `required_row_text_tokens` — non-empty array of non-empty strings. Mandatory.
- `quantity`, `description`, `unit_price`, `amount` — optional. Every field that IS present becomes a required-content check for that row.
- `unit_price` and `amount` are normalized decimal strings without a currency symbol: `"21.00"`, not `"$21.00"` and not `21.0`.

**Validate the sidecar**:

```bash
python -m dartwing_ocr.validator validate semantic-truth \
    tests/stage1_semantic_quality/inv_001_hard/
```

Expected output on success (exit code 0):

```
OK  semantic_table_truth.json — inv_001_hard (3 rows)
```

**What a `document_id`-mismatch error looks like** (Clarifications Q41 — error names both the declared id and the folder basename):

```
ERROR  semantic_table_truth.json: document_id mismatch — declared "inv_002_medium", folder is "inv_001_hard"
```

**What a row-violation error looks like** (Clarifications Q41 — error names `row_id`, failed field, and one-line reason):

```
ERROR  semantic_table_truth.json: row "row-2" — field "unit_price": value "21.5" fails pattern ^\d+\.\d{2}$ (must be decimal string, e.g. "21.50")
```

---

## Path 2 — Run the gate on the synthetic US2 fixture

The committed synthetic fixture at `tests/stage1_semantic_quality/inv_001_hard/` contains a hand-authored, schema-valid `preprocess_output.json` reproducing the degraded-body failure pattern — high mean OCR detector confidence (≈ 0.97, matching the `inv_024_hard_degraded_body` calibration evidence) but materially wrong table rows (colon-for-decimal currency shapes, mutated descriptions, missing quantities). No `source.pdf` is present; the fixture is deterministic and CPU-only (Clarifications Q25).

**Run the evaluator on the synthetic fixture**:

```bash
python -m dartwing_ocr.evaluator evaluate-document \
    tests/stage1_semantic_quality/inv_001_hard/
```

**Expected snippet from the resulting `evaluation_document.json`**:

```json
{
  "document_pass_fail": {
    "vendor_identity_passed": null,
    "semantic_table_quality_passed": false
  },
  "semantic_table_quality": {
    "status": "failed",
    "failed_checks": [
      {
        "category": "malformed-currency-shape",
        "row_id": "row-1",
        "field": "unit_price",
        "expected": "21.00",
        "observed_raw_token": "$21:00",
        "predicate": "canonical money regex ^\\$?\\d{1,3}(,\\d{3})*\\.\\d{2}$"
      },
      {
        "category": "missing-required-content",
        "row_id": "row-1",
        "field": "quantity",
        "expected_normalized": "5",
        "observed_normalized": null,
        "predicate": "normalized exact containment in body-OCR search string"
      }
    ],
    "row_reasons": {
      "row-1": {
        "categories": ["malformed-currency-shape", "missing-required-content"],
        "reason": "unit_price token '$21:00' fails canonical money regex; quantity '5' not found in body OCR"
      }
    },
    "supporting_evidence": {
      "body_confidence_mean": 0.970142,
      "body_confidence_min": 0.9412,
      "body_line_count": 24,
      "body_token_count": 112,
      "header_band_excluded": true
    }
  }
}
```

Key invariants to verify:

- `semantic_table_quality_passed` is `false` because status is `failed`.
- `supporting_evidence.body_confidence_mean ≈ 0.97` — high confidence does not make a failing row pass (FR-013).
- `failed_checks` is ordered: `malformed-currency-shape` before `missing-required-content` (Clarifications Q17).
- `row_reasons` is a per-row aggregation derived from `failed_checks`, not an independent source of truth (Clarifications Q29).
- **Float precision note** (per Copilot review on PR #44 2026-05-23): confidence values are rounded to 6 decimal places of *precision* using ROUND_HALF_EVEN, then emitted via Python's stdlib JSON encoder. Trailing zeros may be elided in the output (e.g. the Decimal value `0.941200` round-trips through `float` to JSON `0.9412`). The SC-007 byte-identical guarantee holds because the same input always produces the same Python float and therefore the same JSON repr.

**Verify SC-007 byte-identical reproducibility**:

```bash
python -m dartwing_ocr.evaluator evaluate-document \
    tests/stage1_semantic_quality/inv_001_hard/ > /tmp/run1.json

python -m dartwing_ocr.evaluator evaluate-document \
    tests/stage1_semantic_quality/inv_001_hard/ > /tmp/run2.json

sha256sum /tmp/run1.json /tmp/run2.json
```

Both hashes must be identical. Any divergence is a serialization bug.

---

## Path 3 — Run the evaluator over a mixed corpus

A typical corpus run spans both corpus roots: the stable 20-document vendor-identity baseline (no sidecars) and the semantic-quality corpus (sidecars present). Pass both roots to the evaluator:

```bash
python -m dartwing_ocr.evaluator evaluate-corpus \
    tests/stage1_vendor_identity/ \
    tests/stage1_semantic_quality/
```

The run summary is written to each corpus root. The `evaluation_run_summary.json` for the semantic-quality root includes a new top-level `semantic_table_quality_metrics` namespace (Clarifications Q36), a per-document semantic status table, and the unchanged vendor-identity fields.

**Expected snippet from `evaluation_run_summary.json`**:

```json
{
  "vendor_identity_pass_rate": 0.85,
  "evidence_gate_id": "v1",
  "evidence_gate_state_counts": {"sufficient": 18, "borderline": 2, "insufficient": 0},
  "semantic_table_quality_metrics": {
    "semantic_applicable_document_count": 1,
    "semantic_not_applicable_document_count": 0,
    "semantic_evaluable_document_count": 1,
    "semantic_passed_document_count": 0,
    "semantic_failed_document_count": 1,
    "semantic_unevaluable_document_count": 0,
    "semantic_table_quality_pass_rate": 0.000000,
    "semantic_failed_check_counts": {
      "malformed-currency-shape": 3,
      "missing-required-content": 5,
      "row-text-coverage-gap": 2,
      "row-alignment-failure": 1
    }
  },
  "semantic_table_quality_documents": [
    {
      "document_id": "inv_001_hard",
      "semantic_table_quality_status": "failed",
      "semantic_table_quality_passed": false
    }
  ]
}
```

Documents in `tests/stage1_vendor_identity/` have no sidecar; each appears in the per-document status table with `semantic_table_quality_status: "not_applicable"` and `semantic_table_quality_passed: null`. They are counted in `semantic_not_applicable_document_count` but excluded from `semantic_evaluable_document_count` and the pass rate (Clarifications Q19, Q20).

---

## Path 4 — Re-read a pre-feature `evaluation_document.json`

A report produced before feature 022 landed has no `semantic_table_quality` object and no `document_pass_fail.semantic_table_quality_passed` field. The v1.3.0 schema is read-tolerant of these absences (FR-019, Clarifications Q43).

**Validate a pre-feature artifact**:

```bash
python -m dartwing_ocr.validator validate artifact \
    path/to/legacy/evaluation_document.json
```

Expected output (exit code 0):

```
OK  evaluation_document.json — validated against v1.3.0 (read-schema; semantic_table_quality_passed absent: interpreted as null)
```

The absent `semantic_table_quality_passed` is treated as `null` semantically — meaning "the semantic gate did not run on this document at the time the report was written." The document is not penalized as a failure; it is not counted in semantic metrics at all. This preserves backward compatibility for any pre-feature corpus snapshot.

---

## Path 5 — Calibration folder handling

Noncanonical folder names — any name that does not fully match the pattern `^inv_\d{3}_(easy|medium|hard)$` — are treated as calibration material (Clarifications Q23). This includes `inv_024_hard_degraded_body` and any other folder with extra suffixes, different prefixes, or non-vocabulary difficulty strings.

**Validate a corpus containing a calibration folder**:

```bash
python -m dartwing_ocr.validator validate corpus \
    tests/stage1_semantic_quality/
```

The validator reports the calibration folder separately and excludes it from scored aggregation:

```
OK   inv_001_hard — scored corpus folder (3 rows in sidecar)
INFO inv_024_hard_degraded_body — calibration material (non-canonical name); per-doc artifacts validated, excluded from scored aggregation
```

Exit code 0. The calibration folder's per-document artifacts (`preprocess_output.json`, `semantic_table_truth.json` if present) are still validated for well-formedness; they are simply not counted as scored corpus.

**Calibration folder WITH a sidecar** — the gate still runs, but the result is excluded from aggregate counters (Clarifications Q39):

```bash
python -m dartwing_ocr.evaluator evaluate-corpus \
    tests/stage1_semantic_quality/
```

The resulting `evaluation_run_summary.json` per-document status table includes the calibration folder (so an operator can inspect its individual result), but the `semantic_table_quality_metrics` aggregate counters exclude it:

```json
{
  "semantic_table_quality_metrics": {
    "semantic_applicable_document_count": 1,
    "semantic_evaluable_document_count": 1,
    "semantic_failed_document_count": 1,
    "semantic_table_quality_pass_rate": 0.000000
  },
  "semantic_table_quality_documents": [
    {
      "document_id": "inv_001_hard",
      "semantic_table_quality_status": "failed",
      "semantic_table_quality_passed": false
    },
    {
      "document_id": "inv_024_hard_degraded_body",
      "semantic_table_quality_status": "failed",
      "semantic_table_quality_passed": false,
      "calibration_only": true
    }
  ]
}
```

`inv_024_hard_degraded_body` appears in the per-document list (with `calibration_only: true`) but is NOT counted in `semantic_applicable_document_count` or any aggregate metric.

---

## Path 6 — Triggering each `unevaluable` cause

When the sidecar is present but `preprocess_output.json` is missing or unreadable, the gate records `status: "unevaluable"` with a closed-enum `cause` (Clarifications Q31). In every `unevaluable` case, `document_pass_fail.semantic_table_quality_passed` is `false` (Clarifications Q20).

**Cause 1 — `preprocess_output_missing`**: sidecar present, `preprocess_output.json` deleted.

```bash
mv tests/stage1_semantic_quality/inv_001_hard/preprocess_output.json /tmp/backup.json
python -m dartwing_ocr.evaluator evaluate-document tests/stage1_semantic_quality/inv_001_hard/
```

```json
{
  "document_pass_fail": {"semantic_table_quality_passed": false},
  "semantic_table_quality": {
    "status": "unevaluable",
    "cause": "preprocess_output_missing",
    "cause_detail": "preprocess_output.json not found in tests/stage1_semantic_quality/inv_001_hard/"
  }
}
```

Restore: `mv /tmp/backup.json tests/stage1_semantic_quality/inv_001_hard/preprocess_output.json`

**Cause 2 — `preprocess_output_invalid_json`**: sidecar present, `preprocess_output.json` is truncated.

```bash
echo '{"pages": [' > tests/stage1_semantic_quality/inv_001_hard/preprocess_output.json
python -m dartwing_ocr.evaluator evaluate-document tests/stage1_semantic_quality/inv_001_hard/
```

```json
{
  "document_pass_fail": {"semantic_table_quality_passed": false},
  "semantic_table_quality": {
    "status": "unevaluable",
    "cause": "preprocess_output_invalid_json",
    "cause_detail": "JSONDecodeError at char 11: Expecting property name enclosed in double quotes"
  }
}
```

**Cause 3 — `preprocess_output_schema_invalid`**: sidecar present, `preprocess_output.json` is valid JSON but fails schema.

```bash
echo '{"not_a_valid_field": true}' > tests/stage1_semantic_quality/inv_001_hard/preprocess_output.json
python -m dartwing_ocr.evaluator evaluate-document tests/stage1_semantic_quality/inv_001_hard/
```

```json
{
  "document_pass_fail": {"semantic_table_quality_passed": false},
  "semantic_table_quality": {
    "status": "unevaluable",
    "cause": "preprocess_output_schema_invalid",
    "cause_detail": "'pages' is a required property"
  }
}
```

**Cause 4 — `body_ocr_unreadable`**: sidecar present, `preprocess_output.json` is schema-valid but contains no body-OCR lines (empty pages array or all lines filtered into the header band).

```json
{
  "document_pass_fail": {"semantic_table_quality_passed": false},
  "semantic_table_quality": {
    "status": "unevaluable",
    "cause": "body_ocr_unreadable",
    "cause_detail": "no body-OCR lines found after header-band exclusion (0 lines across 1 pages)"
  }
}
```

In all four cases: `semantic_table_quality_passed` is `false`, the `cause` is one of the four closed-enum values, and `cause_detail` is a human-readable free-text string (optional but recommended).

---

## Path 7 — Vendor-identity non-regression check (SC-006)

The 20-document vendor-identity baseline corpus (`tests/stage1_vendor_identity/`) has no sidecars. Running the evaluator over it after feature 022 lands must produce byte-identical vendor-identity results compared to a pre-feature run.

**Run the evaluator over the vendor-identity baseline**:

```bash
python -m dartwing_ocr.evaluator evaluate-corpus tests/stage1_vendor_identity/
```

Confirm that `evaluation_run_summary.json` contains `semantic_table_quality_metrics` with all counters at zero or null (no documents had sidecars), and that all existing vendor-identity fields are unchanged.

**Diff pre- and post-feature run summaries, excluding semantic fields**:

```bash
diff \
  <(jq -S . pre_feature/evaluation_run_summary.json | grep -v semantic_) \
  <(jq -S . post_feature/evaluation_run_summary.json | grep -v semantic_)
# no output — vendor-identity fields are byte-identical
```

If there is any diff output after excluding `semantic_` keys, that is a regression in vendor-identity behavior and must be investigated before the feature can land.

---

## Smoke tests

Run these after the feature lands to spot-check correctness. All are CPU-safe and require no GPU, no Paddle, and no Ollama:

```bash
# Contract schema: sidecar accept/reject shapes
pytest tests/contract_tests/test_semantic_table_truth_schema.py -v

# Unit: FR-009 / Q32 normalization pipeline (NFKC, casefold, whitespace, P-category stripping)
pytest tests/unit/evaluator/test_semantic_quality_normalize.py -v

# Unit: FR-010 / Q10 / Q35 currency-shape check (digit-sequence matching, canonical money regex)
pytest tests/unit/evaluator/test_semantic_quality_currency.py -v

# Integration: US2 synthetic fixture — status==failed, >=1 concrete check, byte-identical re-run
pytest tests/integration/test_us2_independent_test.py -v

# Integration: US4 vendor-identity non-regression — 20-doc baseline byte-identical before/after
pytest tests/integration/test_us4_non_regression.py -v

# Integration: US5 calibration handling — gate runs on noncanonical sidecar, excluded from aggregation
pytest tests/integration/test_us5_calibration_handling.py -v

# Validator CLI: validate the committed synthetic sidecar end-to-end
python -m dartwing_ocr.validator validate semantic-truth \
    tests/stage1_semantic_quality/inv_001_hard/
```

---

## Notes

- **No configurability.** The gate has no CLI flags, environment variables, config files, or tunable thresholds. This is intentional and explicit (Clarifications Q38). Behavior is fully fixed by the spec and Clarifications Q1–Q44.
- **No GPU dependency.** Every path above runs on CPU. The gate does not import Paddle, `paddlepaddle-dcu`, or any GPU-dependent library.
- **Check ordering is fixed.** For every sidecar row, the gate evaluates all four checks with no short-circuiting, in this order: `malformed-currency-shape`, `missing-required-content`, `row-text-coverage-gap`, `row-alignment-failure` (Clarifications Q17). A row may record more than one failed category.
- **Currency-shape check uses raw OCR tokens.** The canonical money regex `^\$?\d{1,3}(,\d{3})*\.\d{2}$` is applied to the raw observed OCR token text before FR-009 punctuation stripping. Normalization cannot erase a colon-for-decimal shape (Clarifications Q16).
- **Calibration folder promotion.** `inv_024_hard_degraded_body` and any other noncanonical folder name remain calibration-only until a dedicated corpus amendment change (with labeling-guide, folder-contract, truth-contract, and evaluator-contract updates) explicitly promotes it to scored corpus data (Clarifications Q21, US5).
- **PII screening.** The `labeling-guide.md` PII/license pre-inclusion screening applies equally to both corpus roots: `tests/stage1_vendor_identity/` and `tests/stage1_semantic_quality/`. The committed synthetic fixture carries no real PII by construction; any future committed fixture under `tests/stage1_semantic_quality/` must pass the same screening (Clarifications Q44).
- **Pre-feature reports remain valid.** A `evaluation_document.json` produced before this feature lacks `semantic_table_quality` and `document_pass_fail.semantic_table_quality_passed`. The v1.3.0 read-schema accepts it without error; the absent field is treated as `null` (Clarifications Q43, FR-019).
- **Gate-time invariant violations are hard errors**, not `unevaluable`. `unevaluable` is reserved for unreadable or missing input files. A sidecar that passes the validator but triggers an internal invariant during gate evaluation causes the run to fail and the document to be excluded from semantic metrics (Clarifications Q42).
- For sidecar authoring patterns, see `docs/stage1-vendor-identity/labeling-guide.md`.
