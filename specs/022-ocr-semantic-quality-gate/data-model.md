# Data Model: OCR Semantic Quality Gate

This document formalizes the 8 entities the feature 022 semantic quality gate manipulates, together with the regex constants, numeric constants, normalization specification, and row-anchoring algorithm. Every entity field is pinned by Clarifications Q1–Q44 recorded in `spec.md`; this document is the implementation-facing data sheet that code, JSON Schemas, and tests are written against. The gate is pure-Python, CPU-only, and dependency-additive-free: it uses stdlib (`unicodedata`, `re`, `json`, `decimal`, `pathlib`, `dataclasses`) plus existing `jsonschema>=4.22` and `pydantic>=2.7`. Module paths follow the layout pinned in `plan.md`.

---

## 1. Semantic Table Truth Sidecar (`semantic_table_truth.json`)

**Kind**: optional per-document authored truth file; JSON object on disk  
**Module (validator)**: `src/dartwing_ocr/validator/semantic_table_truth.py`  
**Schema**: `contracts/stage1_vendor_identity/v1.3.0/semantic_table_truth.schema.json`  
**Purpose**: carry the authored table/body row truth the semantic quality gate compares observed OCR against. Separate from `expected.json`, which retains its current vendor-identity-only shape and meaning (FR-006).

### Top-level field table

| Field | JSON type | Required | Constraints | Source |
|---|---|---|---|---|
| `document_id` | string | Yes | MUST match the containing per-document folder's basename exactly; MUST match safety pattern `^[A-Za-z0-9_-]{1,64}$` (canonical fixture pattern is a strict subset) | FR-003, Q27, security-clarify Q-SEC-2/B |
| `rows` | array | Yes | Non-empty; each item is a Semantic Table Row Truth (§2) | FR-002, Q27 |
| `schema_version` | string | No | e.g. `"1.3.0"`; when absent, the governed contract set is authoritative | Q27 |

`additionalProperties: false` at the top-level object. Row-level `additionalProperties: false` is enforced on each row item (§2).

### Validator error requirements (Q41)

- A `document_id`-mismatch error MUST name both the declared `document_id` value and the containing folder basename, e.g.: `"document_id 'inv_002_easy' does not match folder basename 'inv_001_hard'"`.
- A row-violation error MUST name the offending `row_id` (or the row-array index when `row_id` cannot be parsed), the specific failed field, and a one-line machine-readable reason, e.g.: `"row_id 'row-3': field 'unit_price' value '21.0' does not match ^\d+\.\d{2}$"`.

---

## 2. Semantic Table Row Truth (one row inside the sidecar)

**Kind**: JSON object; one element of the `rows` array in `semantic_table_truth.json`  
**Purpose**: the authored ground truth for one expected table/body row, used by all four check predicates.

### Field table

| Field | JSON type | Required | Constraints | Source |
|---|---|---|---|---|
| `row_id` | string | Yes | Non-empty; MUST be unique within the sidecar; MUST match safety pattern `^[A-Za-z0-9_-]{1,64}$` (rejects path-traversal, control characters, whitespace, runaway lengths) | Q11, FR-002, security-clarify Q-SEC-2/B |
| `required_row_text_tokens` | array of string | Yes | Non-empty array; each element a non-empty string; drives FR-011 binary row-text-coverage check | Q28, FR-002 |
| `quantity` | string | No | Optional; when present, becomes a required-content check (FR-009) | Q8, FR-002 |
| `description` | string | No | Optional; when present, becomes a required-content check (FR-009) | Q8, FR-002 |
| `unit_price` | string | No | When present, MUST match `^\d+\.\d{2}$`; authored without currency symbol, e.g. `"21.00"` | Q9, FR-002 |
| `amount` | string | No | When present, MUST match `^\d+\.\d{2}$`; authored without currency symbol, e.g. `"1234.56"` | Q9, FR-002 |

`additionalProperties: false`.

### Row-text optionality rule (Q8)

Only `row_id` and `required_row_text_tokens` are mandatory in every row. Any PRESENT optional cell field (`quantity`, `description`, `unit_price`, `amount`) becomes a required-content check for that row — the gate evaluates it against the normalized body-OCR search string (FR-009). Approximate row-region anchors are explicitly NOT part of the first required row shape; they remain optional future metadata and MUST NOT be required by the validator (FR-002).

### Sidecar-level uniqueness (Q11)

`row_id` uniqueness across all rows in a sidecar is enforced at the validator layer. JSON Schema does not natively support array-uniqueness-by-key, so `semantic_table_truth.py` performs an additional uniqueness check after schema validation and raises a row-violation error naming the duplicate `row_id`.

---

## 3. Body OCR Evidence (derived from `preprocess_output.json`)

**Kind**: in-process derived data structure; not persisted  
**Module**: `src/dartwing_ocr/evaluator/semantic_quality_body_ocr.py`  
**Purpose**: the observed OCR lines the gate reads and searches, after excluding the page-1 header band.

### `BodyOcrEvidence` entity

| Field | Python type | Notes |
|---|---|---|
| `included_lines` | `list[BodyOcrLine]` | Every OCR line on every page, in `preprocess_output.json` serialization order (Q24), EXCLUDING the page-1 header-band region defined by `Y_THRESHOLD_FRACTION = 0.25` |
| `excluded_line_count` | `int` | Count of lines excluded by the header-band filter (page 1 only) |
| `normalized_search_string` | `str` | Single normalized concatenation of all included body-OCR lines: lines joined with a single ASCII space in Q24 serialization order, then the FR-009 normalization pipeline applied once (Q33) |
| `header_band_excluded` | `bool` | `True` iff at least one line was filtered by `Y_THRESHOLD_FRACTION` on page 1 |

### `BodyOcrLine` sub-entity

| Field | Python type | Notes |
|---|---|---|
| `raw_text` | `str` | The raw OCR line text from `preprocess_output.json` before any normalization |
| `detector_confidence` | `float` | Per-line detector confidence in `[0.0, 1.0]`; read from `preprocess_output.json` |
| `page_index` | `int` | 0-based page index |
| `line_index` | `int` | 0-based line index within the page's OCR output |
| `raw_tokens` | `list[str]` | Whitespace-split raw tokens from `raw_text`; used by currency-shape check (FR-010 / Q35) |

### Header-band exclusion rule (Q22)

The header-band region uses `Y_THRESHOLD_FRACTION = 0.25`, imported from `preprocessing.evidence_gate` (feature 020). The filter applies ONLY to page 1 (index 0); pages 2..N are fully included. The selection is lane-robust — it applies identically to OCR-only-lane and PPStructureV3 `preprocess_output.json` artifacts and MUST NOT depend on table-block detection (FR-007).

### Normalized search string construction (Q33)

All "found anywhere" checks (FR-009, FR-011, FR-012) operate against the single `normalized_search_string`. It is constructed once per document evaluation:
1. Collect every `included_line.raw_text` in Q24 serialization order.
2. Join the raw texts with a single ASCII space.
3. Apply the FR-009 normalization pipeline (§11) once to the joined string.

---

## 4. Failed Check

**Kind**: in-process data structure; serialized as an element of the `failed_checks` array in `semantic_table_quality`  
**Module**: `src/dartwing_ocr/evaluator/semantic_quality_checks.py` (produced); `src/dartwing_ocr/evaluator/semantic_quality_report.py` (serialized)  
**Source**: FR-015, Q18, Q29

### Field table

| Field | JSON type | Required | Constraints | Source |
|---|---|---|---|---|
| `category` | string | Yes | Closed kebab-case enum: `malformed-currency-shape` \| `missing-required-content` \| `row-text-coverage-gap` \| `row-alignment-failure` | Q18, Q26, FR-015 |
| `row_id` | string | Yes | Matches the `row_id` of the sidecar row this failure applies to | FR-015 |
| `field` | string \| null | Yes | The cell name (`quantity`, `description`, `unit_price`, `amount`) for cell-level checks; `null` when not applicable (e.g. row-text-coverage-gap targeting a token, row-alignment-failure) | FR-015 |
| `expected` | string | Yes | The sidecar value or required token against which the check was applied | FR-015 |
| `observed` | string \| null | Yes | The raw OCR token found (possibly failing the regex), or `null` when absent | FR-015 |
| `predicate` | string | Yes | Short identifier of the check predicate applied, e.g. `"normalized_substring_containment"`, `"money_regex"`, `"required_token_presence"`, `"anchored_span_ordering"` | FR-015 |
| `position_index` | int | Yes | 0-based position of this record within the `failed_checks` array; matches the FR-015 ordering rule: sidecar row declaration order (outer), then check-category order (inner): `malformed-currency-shape` → `missing-required-content` → `row-text-coverage-gap` → `row-alignment-failure` | Q29, FR-015 |

### Ordering rule (Q17, FR-015)

The gate evaluates all four check categories for every sidecar row without short-circuiting. Failed checks are collected in this fixed order:
1. Outer loop: sidecar row declaration order (row index 0, 1, 2, ...).
2. Inner order: `malformed-currency-shape`, then `missing-required-content`, then `row-text-coverage-gap`, then `row-alignment-failure`.

The flat `failed_checks` array is the source of truth (Q29). A row may appear multiple times in `failed_checks` when multiple categories fail for that row.

---

## 5. Row Reason (per-row aggregation derived from `failed_checks`)

**Kind**: in-process data structure; serialized as the value of a `row_id`-keyed entry inside the `row_reasons` **object** in `semantic_table_quality`  
**Module**: `src/dartwing_ocr/evaluator/semantic_quality_report.py`  
**Source**: Q29, FR-017

### Container shape

`row_reasons` is a JSON **object** keyed by `row_id` (matching the `row_id` declared on the sidecar row), where each value is the per-row aggregation record described below. It is NOT an array; the `row_id` is the property key, never a field inside the value. This shape matches `contracts/evaluator-output-contract.md` Example B and `contracts/schema-amendments.md` `evaluation_document.schema.json` `row_reasons.additionalProperties` definition.

### Per-row record field table

| Field | JSON type | Required | Constraints | Source |
|---|---|---|---|---|
| `categories` | array of string | Yes | Non-empty array of unique kebab-case enum values — the distinct `category` values from `failed_checks` entries for this `row_id`, in the fixed Q17 check-category order (`malformed-currency-shape`, `missing-required-content`, `row-text-coverage-gap`, `row-alignment-failure`). | Q29 |
| `reason` | string | Yes | Short one-line human-readable summary, e.g. `"unit_price token '$21:00' fails canonical money regex (colon-for-decimal)"`. | Q29 |

`row_reasons` is derived from `failed_checks` and is REQUIRED only when `status == failed`. Within the object, entries are emitted in sidecar row declaration order (the `stable_json` writer's sort_keys then re-sorts the JSON keys alphabetically per Q34 — this is acceptable because the per-row aggregation is order-insensitive once each entry is a self-contained `{categories, reason}` record). A `row_id` appears in `row_reasons` at most once (it aggregates all failed categories for that row). `failed_checks` (not `row_reasons`) is the source of truth for individual failure records (Q29).

---

## 6. Supporting Evidence (closed shape on `semantic_table_quality`)

**Kind**: JSON object; nested inside the `semantic_table_quality` object  
**Module**: `src/dartwing_ocr/evaluator/semantic_quality_report.py`  
**Source**: Q30, Q37, FR-013, FR-017

### Field table

| Field | JSON type | Required | Constraints | Source |
|---|---|---|---|---|
| `body_confidence_mean` | number | Yes | Arithmetic mean of `detector_confidence` across all included body lines; `0.0` when no included lines; 6-decimal-place precision (Q34 ROUND_HALF_EVEN) | Q30, Q37 |
| `body_confidence_min` | number | Yes | Minimum `detector_confidence` across included body lines; `0.0` when no included lines; 6-dp | Q30, Q37 |
| `body_line_count` | integer | Yes | Count of lines in `included_lines` (≥0) | Q30, Q37 |
| `body_token_count` | integer | Yes | Total count of raw tokens across all included body lines (≥0) | Q30, Q37 |
| `header_band_excluded` | boolean | Yes | `true` iff at least one line was filtered by `Y_THRESHOLD_FRACTION` on page 1 | Q30, Q37 |

**Confidence scope rule**: confidence values are computed ONLY across included body lines — never across header-band lines. OCR confidence is recorded only here as document-aggregate supporting evidence and MUST NOT appear per-row or per-failed-check (FR-013, Q30).

**Always-emit rule**: `supporting_evidence` is required when `status ∈ {passed, failed, unevaluable}`. It MAY be omitted when `status == not_applicable` (no sidecar, no preprocess input read). The body counts remain meaningful for `unevaluable` when partial reading occurred before the failure.

---

## 7. Semantic Quality Verdict (the `semantic_table_quality` object on `evaluation_document.json`)

**Kind**: JSON object written into `evaluation_document.json` per processed document  
**Module (builder)**: `src/dartwing_ocr/evaluator/semantic_quality_report.py`  
**Module (writer)**: `src/dartwing_ocr/evaluator/document.py` (the existing per-document evaluator writer, extended in T051)  
**Source**: FR-016, FR-017, Q26, Q29, Q30, Q31, Q37

### Field table

| Field | JSON type | Required | Constraints | Source |
|---|---|---|---|---|
| `status` | string | Yes | Closed snake_case enum: `passed` \| `failed` \| `not_applicable` \| `unevaluable`; verbatim literal values (Q26) | FR-016, Q26 |
| `failed_checks` | array | Conditional | Required (always present) when `status ∈ {passed, failed, unevaluable}` — MUST be non-empty when `status == failed`, MUST be an empty array `[]` when `status == passed` or `status == unevaluable`; omitted only when `status == not_applicable` (because the whole `semantic_table_quality` object is omitted). Items are Failed Check records (§4). | FR-015, Q29, F5-resolution |
| `row_reasons` | object | Conditional | Required when `status == failed`; **object keyed by `row_id`** (NOT an array) where each value is the §5 per-row record `{categories, reason}`; omitted otherwise | Q29, FR-017, F1-resolution |
| `supporting_evidence` | object | Conditional | Required when `status ∈ {passed, failed, unevaluable}`; closed shape (§6); MAY be omitted when `status == not_applicable` | Q30, Q37, FR-017 |
| `cause` | string | Conditional | Required when `status == unevaluable`; closed enum: `preprocess_output_missing` \| `preprocess_output_invalid_json` \| `preprocess_output_schema_invalid` \| `body_ocr_unreadable` | Q31, FR-017 |
| `cause_detail` | string | No | Optional free-text detail when `status == unevaluable` | Q31, FR-017 |

`additionalProperties: false`.

### State transitions (verdict derivation)

| Condition | Resulting `status` |
|---|---|
| No `semantic_table_truth.json` present | `not_applicable` |
| Sidecar present + `preprocess_output.json` missing or unparseable | `unevaluable` |
| Sidecar present + `preprocess_output.json` readable + ≥1 failed check recorded | `failed` |
| Sidecar present + `preprocess_output.json` readable + 0 failed checks recorded | `passed` |

**Gate-time invariant violations** (Q42): a sidecar that passes the validator but triggers an internal gate invariant violation (e.g. anchor returns an inconsistent span, aggregation produces an unknown status) MUST raise `SemanticGateInvariantError` from `evaluator/exceptions.py`. The run fails hard; `status` is NOT recorded as `unevaluable` (which is reserved for unreadable INPUT files), and the document is excluded from `semantic_table_quality_metrics` aggregation.

### `document_pass_fail.semantic_table_quality_passed` (Q20, FR-025)

A sibling of the unchanged `document_pass_fail.vendor_identity_passed`. Value domain:

| `status` | `semantic_table_quality_passed` |
|---|---|
| `passed` | `true` |
| `failed` | `false` |
| `unevaluable` | `false` |
| `not_applicable` | `null` |

The evaluator MUST NOT infer a semantic pass from vendor-identity metrics (FR-025, SC-005).

---

## 8. Semantic Quality Metrics (top-level `semantic_table_quality_metrics` namespace on `evaluation_run_summary.json`)

**Kind**: JSON object written into `evaluation_run_summary.json` as a top-level sibling key  
**Module**: `src/dartwing_ocr/evaluator/semantic_quality_metrics.py`  
**Source**: FR-018, Q19, Q36, Q39

### `semantic_table_quality_metrics` field table

| Field | JSON type | Constraints | Source |
|---|---|---|---|
| `semantic_applicable_document_count` | integer | ≥0; count of scored corpus documents processed that have a sidecar | Q19, FR-018 |
| `semantic_not_applicable_document_count` | integer | ≥0; count of scored corpus documents processed without a sidecar | Q19, FR-018 |
| `semantic_evaluable_document_count` | integer | ≥0; equals `semantic_passed_document_count + semantic_failed_document_count` | Q19, FR-018 |
| `semantic_passed_document_count` | integer | ≥0 | Q19, FR-018 |
| `semantic_failed_document_count` | integer | ≥0 | Q19, FR-018 |
| `semantic_unevaluable_document_count` | integer | ≥0 | Q19, FR-018 |
| `semantic_table_quality_pass_rate` | number \| null | `passed / evaluable` in `[0.0, 1.0]`; 6-dp ROUND_HALF_EVEN; `null` when `semantic_evaluable_document_count == 0` | Q19, FR-018 |
| `semantic_failed_check_counts` | object | Keys: `malformed-currency-shape`, `missing-required-content`, `row-text-coverage-gap`, `row-alignment-failure`; each value an integer ≥0 | Q19, FR-018 |

### Per-document status entries

Emitted under the **top-level sibling key `semantic_document_statuses`** in `evaluation_run_summary.json`, parallel to `semantic_table_quality_metrics` (NOT nested inside it). The value is a JSON array of per-document entries. Pinned by `contracts/evaluator-output-contract.md` §`semantic_document_statuses` and `contracts/schema-amendments.md` §`evaluation_run_summary.schema.json`. Each entry:

| Field | JSON type | Constraints | Source |
|---|---|---|---|
| `document_id` | string | Non-empty | Q19, FR-018 |
| `semantic_table_quality_status` | string | One of the four Q26 snake_case enum values | Q19, Q26, FR-018 |
| `semantic_table_quality_passed` | boolean \| null | Q20 value domain | Q20, FR-018 |

Entries are sorted by deterministic run-document order (the evaluator's canonical document iteration order for the run).

### Calibration folder exclusion rule (Q39)

Folders whose basename does NOT match `CANONICAL_FOLDER_PATTERN` (§9) are calibration/test-fixture material. The gate still runs on them when a sidecar is present and emits a per-document `semantic_table_quality` object and a per-document status entry. However, calibration folders MUST be EXCLUDED from all `semantic_table_quality_metrics` aggregate counts and from the pass-rate calculation (Q39, SC-009).

---

## 9. Regex constants

Pin these as module-level compiled `re.Pattern` constants at module load time. A compilation error is a developer error, not a runtime error.

| Name | Module | Pattern | Purpose | Source |
|---|---|---|---|---|
| `CANONICAL_MONEY_REGEX` | `evaluator/semantic_quality_currency.py` | `r"^\$?\d{1,3}(,\d{3})*\.\d{2}$"` | Anchored canonical money regex. Applied to the RAW observed OCR token before FR-009 punctuation stripping (Q16). Accepts `$21.00`, `21.00`, `$1,234.56`; rejects `$21:00`, `$22:`, `21.0`, `$1234.00` (missing comma grouping is accepted — only colon-for-decimal and truncated-cents are the targeted defects). | Q10, FR-010 |
| `EXPECTED_CELL_DECIMAL_REGEX` | `validator/semantic_table_truth.py` | `r"^\d+\.\d{2}$"` | Validates sidecar-author `unit_price`/`amount` fields at validation time. Rejects symbol-prefixed or malformed authored values. | Q9, FR-002 |
| `CANONICAL_FOLDER_PATTERN` | `validator/corpus_pattern.py` | `r"^inv_\d{3}_(easy\|medium\|hard)$"` | Canonical scored-corpus folder allowlist. Shared by `validate corpus` subcommand and `semantic_quality_metrics.py` calibration exclusion logic. Default-exclude: any non-matching name is calibration/test-fixture material. | Q23, FR-027 |
| `IDENTIFIER_SAFETY_REGEX` | `validator/semantic_table_truth.py` | `r"^[A-Za-z0-9_-]{1,64}$"` | Safety pattern applied to `document_id` and `row_id` in the sidecar (per security-clarify Q-SEC-2/B / FR-002 / FR-003). Alphanumeric + dash/underscore, ≤64 chars. Rejects path-traversal sequences, control characters, whitespace, punctuation-heavy PII-style labels, and runaway lengths. Canonical `CANONICAL_FOLDER_PATTERN` is a strict subset, so existing fixture names pass unchanged. | security-clarify Q-SEC-2/B, FR-002, FR-003 |

---

## 10. Numeric constants

| Constant | Module | Type | Value | Purpose | Source |
|---|---|---|---|---|---|
| `Y_THRESHOLD_FRACTION` | `preprocessing/evidence_gate.py` (feature 020, imported) | `float` | `0.25` | Page-1 header-band top-fraction exclusion. Imported by `evaluator/semantic_quality_body_ocr.py` as `EVIDENCE_GATE_Y_THRESHOLD_FRACTION`. | Q22, R-020.5 |
| `SUPPORTING_EVIDENCE_FLOAT_PRECISION` | `evaluator/semantic_quality_report.py` | `int` | `6` | Decimal places for `body_confidence_mean`, `body_confidence_min`, and `semantic_table_quality_pass_rate`; ROUND_HALF_EVEN via `decimal.Decimal`. | Q34, FR-014 |
| `SEMANTIC_QUALITY_GATE_VERSION` | `evaluator/semantic_quality.py` | `str` | `"v1"` | Public string constant identifying the gate version; exposed alongside the gate module's public API. | plan.md |

---

## 11. Normalization pipeline (FR-009 / Q5 / Q32)

Applied identically to BOTH sides of every "found anywhere" comparison (sidecar value and body-OCR search string). The order is fixed; do not reorder steps.

```python
import unicodedata
import re

def normalize(text: str) -> str:
    # Step 1: Unicode NFKC normalization (Q5, Q32)
    text = unicodedata.normalize("NFKC", text)
    # Step 2: Case-folding (Q5) — Python casefold() handles Turkish I, German ß, etc.
    text = text.casefold()
    # Step 3: Whitespace collapse — every Unicode whitespace run → single ASCII space (Q5)
    text = re.sub(r"\s+", " ", text, flags=re.UNICODE)
    # Step 4: Punctuation strip — drop all code points whose Unicode general category
    #         starts with "P" (Pc, Pd, Pe, Pf, Pi, Po, Ps) after NFKC (Q32)
    text = "".join(ch for ch in text if not unicodedata.category(ch).startswith("P"))
    return text.strip()
```

**Module**: `src/dartwing_ocr/evaluator/semantic_quality_normalize.py`  
**Idempotence invariant**: `normalize(normalize(x)) == normalize(x)` for all inputs.

**Currency-shape exception (Q16)**: FR-010 currency-shape checks operate on the RAW observed OCR token BEFORE this normalization pipeline. The normalize function is NOT applied to currency candidates being evaluated by `CANONICAL_MONEY_REGEX`.

**Exact containment semantics**:
- For a scalar cell value (`quantity`, `description`, `unit_price`, `amount`): `normalize(expected_value)` appears as a contiguous substring in `normalized_search_string`.
- For each token in `required_row_text_tokens`: `normalize(token)` appears as a substring in `normalized_search_string`.

---

## 12. Row anchoring algorithm (FR-012 / Q7 / Q24)

**Module**: `src/dartwing_ocr/evaluator/semantic_quality_anchor.py`

For each sidecar row, the anchor algorithm finds the contiguous span of body-OCR included-line indices that best represents the row's position in the document body.

### Algorithm

1. **Candidate generation**: For each possible contiguous span `(start_line_index, end_line_index)` over `BodyOcrEvidence.included_lines`, compute the count of the row's `required_row_text_tokens` whose `normalize(token)` appears in the normalized text of the span.
2. **Best-span selection**: Select the span that maximizes the matched-token count. "Best" means most `required_row_text_tokens` matched — NOT fuzzy edit distance (Q7).
3. **Tie-break rule (Q24)**: On ties (equal matched-token count), select the span with the earliest start in `preprocess_output.json` serialization order — the lowest `(page_index, line_index)` of the span's start line. No geometry computation, no coordinate tolerance.
4. **Further ties**: Break remaining ties by sidecar row declaration order (earlier row index in the sidecar takes priority) (Q7).
5. **Output**: `RowAnchor(row_id: str, start_line_index: int, end_line_index: int)` where the indices are positions into `BodyOcrEvidence.included_lines`.

### Use by downstream checks

- **FR-010 (currency-shape)**: raw tokens within the anchored span are the search space for digit-sequence matching (Q35).
- **FR-012 (row-alignment)**: the anchor span is used to verify required values appear in order and without incompatible splitting.

### Anchor failure

When no included body lines exist (empty `BodyOcrEvidence.included_lines`), the anchor span is `None`. All row checks that depend on an anchor span fall through to `missing-required-content` failures.

---

## 13. State transitions and side effects

A single document evaluation proceeds as follows:

1. **Sidecar absent** → `status = not_applicable`; no `semantic_table_quality` object written (or written with only `status`); `document_pass_fail.semantic_table_quality_passed = null`.
2. **Sidecar present + `preprocess_output.json` unreadable** → `status = unevaluable`; `cause` set to the appropriate closed-enum value; `document_pass_fail.semantic_table_quality_passed = false`.
3. **Sidecar present + `preprocess_output.json` readable** → build `BodyOcrEvidence`, anchor rows, evaluate all four check categories per row (no short-circuit), aggregate by any-fail rule → `status ∈ {passed, failed}`.
4. **Gate-time invariant violation** → raise `SemanticGateInvariantError`; run fails; document excluded from `semantic_table_quality_metrics`.

**Per-document file writes**:
- `evaluation_document.json` — always written; includes `document_pass_fail.semantic_table_quality_passed` (FR-017); includes `semantic_table_quality` object when sidecar present or status is `unevaluable`.

**Per-corpus-run file write**:
- `evaluation_run_summary.json` — written once per evaluator run by `semantic_quality_metrics.py`; includes `semantic_table_quality_metrics` as a top-level sibling key and the per-document semantic status entries (Q36, FR-018).

Both outputs are routed through `evaluator/stable_json.py`'s `dump_stable(obj, path)` (Q34): sorted keys at every nesting level, UTF-8 encoding, LF line endings, trailing newline at EOF, no trailing whitespace, 6-dp ROUND_HALF_EVEN floats emitted as JSON numbers.

**Invariants that hold across every run**:
- No model call, no network I/O (FR-008, FR-029).
- Existing vendor-identity fields on `evaluation_document.json` and `evaluation_run_summary.json` are byte-identical before and after the feature lands (SC-006, FR-020, FR-022).
- The `semantic_quality_metrics.py` aggregator is invoked exactly once per evaluator run.
- Calibration folders (non-matching `CANONICAL_FOLDER_PATTERN`) appear in per-document status entries but are excluded from all aggregate `semantic_table_quality_metrics` counts (Q39, SC-009).
