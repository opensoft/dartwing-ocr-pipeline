# Evaluator Output Contract: Newly-Written Semantic Quality Fields

This document records the exact shape of every semantic-quality field written by the v1.3.0 evaluator on `evaluation_document.json` and `evaluation_run_summary.json`. All fields described here are additive. No existing field — including `document_pass_fail.vendor_identity_passed`, any feature-020 run-summary key, or any field introduced by features 007/014–021 — is renamed, removed, or retyped. All examples use the synthetic US2 fixture (`tests/stage1_semantic_quality/inv_001_hard/`) as the reference document.

---

## `evaluation_document.json` extensions

### `document_pass_fail.semantic_table_quality_passed`

**Type**: `boolean | null`

**Always present** on newly-written `evaluation_document.json` artifacts (Q20, FR-017). The field is a sibling of the unchanged `vendor_identity_passed`.

**Value mapping** — determined exclusively by the semantic status; no other input affects it:

| Semantic status | Field value |
|----------------|-------------|
| `"passed"` | `true` |
| `"failed"` | `false` |
| `"unevaluable"` | `false` |
| `"not_applicable"` | `null` |

A document with a failing semantic verdict but a passing vendor-identity verdict MUST have this field set to `false`; the two verdicts are independent (FR-025 / SC-004). A document with no sidecar MUST have this field set to `null` — the evaluator MUST NOT infer a semantic pass from vendor-identity metrics (FR-025 / SC-005).

---

### `semantic_table_quality` object

**Present when**: the sidecar is found for the document, OR when `status == "unevaluable"` (sidecar present but inputs unreadable).

**Absent when**: `status == "not_applicable"` (no sidecar). In the not_applicable case `document_pass_fail.semantic_table_quality_passed` is `null` and the `semantic_table_quality` key is omitted.

**Closed shape** — `additionalProperties: false` (Q29, Q30, Q31, Q37, FR-017):

```
{
  "status":           string (closed enum: "passed" | "failed" | "not_applicable" | "unevaluable"),
  "failed_checks":    array  (source of truth — see below),
  "row_reasons":      object (per-row derived aggregation — required when status=="failed"),
  "supporting_evidence": object (closed shape — always present when sidecar was evaluated),
  "cause":            string (closed enum — required when status=="unevaluable"),
  "cause_detail":     string (optional free-text — present only when status=="unevaluable")
}
```

**`failed_checks`** is the flat ordered array and the single source of truth for all recorded failures. Each entry has: `category` (one of the four kebab-case labels), `row_id`, `field` (the sidecar field that was checked), `expected` (normalized or raw expected value), `observed` (normalized absence finding or raw observed token), and `predicate` (description of the check rule applied). Items are ordered by sidecar row declaration order as the outer loop, then by fixed check-category order within each row: `malformed-currency-shape` → `missing-required-content` → `row-text-coverage-gap` → `row-alignment-failure` (Q17). No short-circuiting: all four applicable checks are evaluated for every row.

**`row_reasons`** is a per-row aggregation derived from `failed_checks`, keyed by `row_id`. Each value carries `categories` (the set of failed-category labels for that row, in fixed order) and `reason` (a short human-readable summary). Present and non-empty only when `status == "failed"`.

**`supporting_evidence`** is the pinned closed shape (Q37):

```json
{
  "body_confidence_mean": <float, 6 dp>,
  "body_confidence_min":  <float, 6 dp>,
  "body_line_count":      <integer>,
  "body_token_count":     <integer>,
  "header_band_excluded": <boolean>
}
```

Computed across all body-OCR lines that survived the page-1 header-band exclusion filter. `header_band_excluded` is `true` if at least one header-band line was filtered out.

---

### Full inline examples

#### Example A — status `"passed"` (sidecar present, no failed checks)

```json
{
  "document_id": "inv_002_easy",
  "document_pass_fail": {
    "vendor_identity_passed": true,
    "semantic_table_quality_passed": true
  },
  "semantic_table_quality": {
    "status": "passed",
    "failed_checks": [],
    "supporting_evidence": {
      "body_confidence_mean": 0.971234,
      "body_confidence_min":  0.943100,
      "body_line_count":      24,
      "body_token_count":     187,
      "header_band_excluded": true
    }
  }
}
```

#### Example B — status `"failed"` (synthetic US2 fixture reference)

```json
{
  "document_id": "inv_001_hard",
  "document_pass_fail": {
    "vendor_identity_passed": true,
    "semantic_table_quality_passed": false
  },
  "semantic_table_quality": {
    "status": "failed",
    "failed_checks": [
      {
        "category":  "malformed-currency-shape",
        "row_id":    "row-3",
        "field":     "unit_price",
        "expected":  "21.00",
        "observed":  "$21:00",
        "predicate": "raw token must match ^\\$?\\d{1,3}(,\\d{3})*\\.\\d{2}$"
      },
      {
        "category":  "missing-required-content",
        "row_id":    "row-5",
        "field":     "quantity",
        "expected":  "4",
        "observed":  "not found in normalized body-OCR search string",
        "predicate": "normalized exact containment in body-OCR search string"
      },
      {
        "category":  "row-text-coverage-gap",
        "row_id":    "row-7",
        "field":     "required_row_text_tokens",
        "expected":  "Annual Maintenance Contract",
        "observed":  "token 'Maintenance' absent from normalized body-OCR",
        "predicate": "every required_row_text_token present as normalized substring"
      }
    ],
    "row_reasons": {
      "row-3": {
        "categories": ["malformed-currency-shape"],
        "reason": "unit_price token '$21:00' fails canonical money regex (colon-for-decimal)"
      },
      "row-5": {
        "categories": ["missing-required-content"],
        "reason": "quantity '4' not found in normalized body-OCR search string"
      },
      "row-7": {
        "categories": ["row-text-coverage-gap"],
        "reason": "required token 'Maintenance' absent from normalized body-OCR"
      }
    },
    "supporting_evidence": {
      "body_confidence_mean": 0.970812,
      "body_confidence_min":  0.940100,
      "body_line_count":      32,
      "body_token_count":     241,
      "header_band_excluded": true
    }
  }
}
```

#### Example C — status `"unevaluable"` (preprocess_output.json missing)

```json
{
  "document_id": "inv_006_medium",
  "document_pass_fail": {
    "vendor_identity_passed": null,
    "semantic_table_quality_passed": false
  },
  "semantic_table_quality": {
    "status": "unevaluable",
    "failed_checks": [],
    "supporting_evidence": {
      "body_confidence_mean": 0.0,
      "body_confidence_min":  0.0,
      "body_line_count":      0,
      "body_token_count":     0,
      "header_band_excluded": false
    },
    "cause": "preprocess_output_missing",
    "cause_detail": "No preprocess_output.json found at tests/stage1_semantic_quality/inv_006_medium/preprocess_output.json"
  }
}
```

#### Example D — status `"not_applicable"` (no sidecar present)

```json
{
  "document_id": "inv_007_easy",
  "document_pass_fail": {
    "vendor_identity_passed": true,
    "semantic_table_quality_passed": null
  }
}
```

The `semantic_table_quality` key is absent when `status == "not_applicable"`.

---

## `evaluation_run_summary.json` extensions

### `semantic_table_quality_metrics` top-level sibling key

**Location**: top-level sibling in `evaluation_run_summary.json`, parallel to existing vendor-identity and feature-020 fields (Q36, FR-018).

**Always present** on newly-written run summaries (FR-018). Excludes calibration folders from aggregate counts and pass-rate computation (Q39 / MI-20).

**Full field enumeration** (Q19):

| Field | Type | Description |
|-------|------|-------------|
| `semantic_applicable_document_count` | `integer` | Count of scored corpus folders that have a sidecar (excludes calibration folders). |
| `semantic_not_applicable_document_count` | `integer` | Count of scored corpus folders without a sidecar. |
| `semantic_evaluable_document_count` | `integer` | Count of scored folders where status is `"passed"` or `"failed"` (i.e., the gate ran and produced a usable verdict). |
| `semantic_passed_document_count` | `integer` | Count of scored folders with status `"passed"`. |
| `semantic_failed_document_count` | `integer` | Count of scored folders with status `"failed"`. |
| `semantic_unevaluable_document_count` | `integer` | Count of scored folders where sidecar was present but inputs were unreadable. |
| `semantic_table_quality_pass_rate` | `number \| null` | `semantic_passed_document_count / semantic_evaluable_document_count`, rounded to 6 decimal places using `ROUND_HALF_EVEN`. `null` when `semantic_evaluable_document_count == 0` (prevents division by zero). |
| `semantic_failed_check_counts` | `object` | Integer counts per category across all scored folders: `malformed-currency-shape`, `missing-required-content`, `row-text-coverage-gap`, `row-alignment-failure`. All four keys always present (not sparse), defaulting to `0`. |

**Sample JSON** (mixed corpus: 1 scored folder with sidecar + 19 scored folders without):

```json
{
  "semantic_table_quality_metrics": {
    "semantic_applicable_document_count": 1,
    "semantic_not_applicable_document_count": 19,
    "semantic_evaluable_document_count": 1,
    "semantic_passed_document_count": 0,
    "semantic_failed_document_count": 1,
    "semantic_unevaluable_document_count": 0,
    "semantic_table_quality_pass_rate": 0.0,
    "semantic_failed_check_counts": {
      "malformed-currency-shape": 1,
      "missing-required-content": 1,
      "row-text-coverage-gap": 1,
      "row-alignment-failure": 0
    }
  }
}
```

---

### Per-document semantic status entries

**Key**: `semantic_document_statuses` — top-level array in `evaluation_run_summary.json`.

**Sorted by**: deterministic run-document order (typically alphabetical by `document_id`, consistent with the evaluator's corpus iteration order).

**Includes**: every document processed in the run scope — scored corpus folders AND calibration folders with sidecars. Calibration folders appear here but are excluded from the `semantic_table_quality_metrics` aggregate counts (Q39).

**Per-entry shape**:

```json
{
  "document_id": "inv_001_hard",
  "semantic_table_quality_status": "failed",
  "semantic_table_quality_passed": false
}
```

**Full example** (3 scored + 1 calibration folder, mixed sidecar presence):

```json
{
  "semantic_document_statuses": [
    {
      "document_id": "inv_001_hard",
      "semantic_table_quality_status": "failed",
      "semantic_table_quality_passed": false
    },
    {
      "document_id": "inv_002_easy",
      "semantic_table_quality_status": "not_applicable",
      "semantic_table_quality_passed": null
    },
    {
      "document_id": "inv_003_medium",
      "semantic_table_quality_status": "passed",
      "semantic_table_quality_passed": true
    },
    {
      "document_id": "inv_024_hard_degraded_body",
      "semantic_table_quality_status": "failed",
      "semantic_table_quality_passed": false
    }
  ]
}
```

In this example, `inv_024_hard_degraded_body` appears in `semantic_document_statuses` but is excluded from all aggregate counters in `semantic_table_quality_metrics` because its basename does not match the canonical-pattern allowlist `^inv_\d{3}_(easy|medium|hard)$` (MI-20, MI-21, Q39).

---

## Stable JSON serialization

All newly-written semantic outputs use the following conventions, implemented in `stable_json.dump_stable` (Q34, FR-014, MI-16):

- **Key order**: sorted keys at every nesting level (including inside `row_reasons`, `supporting_evidence`, `semantic_failed_check_counts`, and every `failed_checks` entry).
- **Encoding**: UTF-8.
- **Line endings**: LF (Unix). No CRLF.
- **EOF**: exactly one trailing newline character. No trailing whitespace on any line.
- **Floats** (`body_confidence_mean`, `body_confidence_min`, `semantic_table_quality_pass_rate`): rounded to exactly 6 decimal places using `decimal.ROUND_HALF_EVEN`. Emitted as JSON numbers (e.g. `0.971234`), NOT as quoted strings (e.g. NOT `"0.971234"`). The schema type is `number` throughout.
- **Integers** (`body_line_count`, `body_token_count`, all `semantic_*_document_count` fields, all per-category failed-check counts): emitted as JSON integers (e.g. `24`, `0`), NOT as floats.
- **Booleans**: `true` / `false` (lowercase JSON literals).
- **Null**: `null` (lowercase JSON literal).

These conventions make two runs on identical inputs produce byte-identical output files, satisfying SC-007 / MI-2.

---

## Backward-compat readers (FR-019 / Q43)

### Pre-feature `evaluation_document.json`

A `evaluation_document.json` written before this feature landed (v1.2.0 era) will not contain `document_pass_fail.semantic_table_quality_passed` or the `semantic_table_quality` object. This artifact MUST:

- Validate against the v1.3.0 `evaluation_document.schema.json` without error (both new fields are optional in the schema).
- Be read by any code that checks `document_pass_fail.semantic_table_quality_passed` as though the absent field were `null` — semantically, "the semantic gate did not run on this document" (Q43).

No code path may raise an error on the mere absence of these fields in a pre-feature report. The writer contract (FR-018) requires them in newly-generated reports; the reader contract (FR-019) tolerates their absence in pre-feature reports.

### Pre-feature `evaluation_run_summary.json`

A `evaluation_run_summary.json` written before this feature landed will not contain `semantic_table_quality_metrics` or `semantic_document_statuses`. This artifact MUST:

- Validate against the v1.3.0 `evaluation_run_summary.schema.json` without error (both keys are optional in the schema, present only on newly-written reports).
- Be read without error by any aggregation or display code that expects the new namespace.

### Writer obligations

The backward-compat tolerance for readers is NOT a license for the new writer to omit fields. When the evaluator produces a new `evaluation_document.json` or `evaluation_run_summary.json` after this feature lands:

- `document_pass_fail.semantic_table_quality_passed` MUST always be present (FR-017).
- `semantic_table_quality_metrics` and `semantic_document_statuses` MUST always be present (FR-018).
- Absence of any of these fields in a newly-written report is a regression signal, not a valid backward-compat posture.
