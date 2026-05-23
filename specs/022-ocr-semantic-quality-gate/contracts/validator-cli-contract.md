# Validator CLI Contract: Sidecar and Corpus Validation

This document records the `python -m dartwing_ocr.validator` subcommand surface for the v1.3.0 sidecar contract. Feature 022 extends the existing validator CLI with one new subcommand (`validate semantic-truth`) and modifies the behavior of `validate folder` and `validate corpus` to incorporate the optional sidecar. No new top-level CLI entry point is introduced; the gate runs automatically inside the existing evaluator when a sidecar is present (Q13 / FR-007). All exit codes described below are additive and do not replace any code defined by prior features.

---

## `validate folder <folder-path>`

### Behavior changes from v1.2.0

When `semantic_table_truth.json` is **absent**, behavior is identical to v1.2.0: mandatory artifacts (`source.pdf`, `expected.json`) are validated per the existing contract. No new requirement is imposed on folders without a sidecar (FR-005).

When `semantic_table_truth.json` is **present**, the following additional checks run (FR-003, FR-004):

1. The sidecar is loaded and validated against `contracts/stage1_vendor_identity/v1.3.0/semantic_table_truth.schema.json`.
2. The declared `document_id` is compared against the folder basename. A mismatch is a validation error (Q41): the error message MUST name both the declared value and the folder basename (see "Error message content" below).
3. All `row_id` values in the `rows` array are checked for uniqueness. A non-unique `row_id` is a validation error.
4. Every row is validated against the row-truth contract. A row violation is an error (Q41): the error message MUST name the offending `row_id` (or the row-array index when `row_id` is absent or cannot be parsed), the specific failed field, and a one-line machine-readable reason.

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | Folder valid (sidecar accepted when present, or absent with no new requirement). |
| 1 | Mandatory artifact missing or schema-invalid (unchanged from v1.2.0). |
| 3 | Sidecar present but `document_id` mismatch. |
| 4 | Sidecar present but row-violation (row_id non-unique, row fails contract). |
| 5 | Sidecar present but fails JSON Schema validation (top-level shape invalid). |

Exit codes 3, 4, 5 are new for v1.3.0. Exit codes 1 and 2 (argparse usage error) are unchanged.

---

## `validate semantic-truth <folder-path>` (NEW)

Validates only the `semantic_table_truth.json` sidecar in the specified folder. Designed for fixture authoring workflows where the author wants to verify the sidecar in isolation before running a full pipeline or evaluator pass (FR-003, FR-004, Q41).

### Steps performed

1. Checks that `<folder-path>/semantic_table_truth.json` exists. Exits 4 (missing sidecar) if absent.
2. Parses the file as JSON. Exits 5 (invalid JSON / schema error) if not valid JSON.
3. Validates the parsed object against `semantic_table_truth.schema.json`. Exits 5 if schema-invalid.
4. Compares `document_id` against the folder basename (the last path component of `<folder-path>`). Exits 3 with a named-mismatch error if they differ.
5. Checks `row_id` uniqueness across all rows. Exits 4 with a named-violation error if any duplicate is found.
6. Checks each row against the row-truth contract. Exits 4 with a named-violation error for the first failing row encountered (validator does not short-circuit across rows — all rows are checked, all violations are reported).
7. Reports accepted on stdout and exits 0.

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | Sidecar accepted. All checks pass. |
| 1 | Internal validator error (unexpected exception). |
| 2 | Argparse usage error (e.g. missing folder-path argument). |
| 3 | `document_id` mismatch: declared value does not match folder basename. |
| 4 | Row violation: missing sidecar, empty `rows`, non-unique `row_id`, or row fails row-truth contract. |
| 5 | JSON parse error or top-level schema validation failure. |

### Example invocation

```bash
python -m dartwing_ocr.validator validate semantic-truth \
    tests/stage1_semantic_quality/inv_001_hard/
# Exit 0: semantic_table_truth.json accepted for document 'inv_001_hard'.
```

```bash
python -m dartwing_ocr.validator validate semantic-truth \
    tests/stage1_vendor_identity/inv_005_easy/
# Exit 4: missing sidecar — no semantic_table_truth.json in
# 'tests/stage1_vendor_identity/inv_005_easy/'.
```

---

## `validate corpus <corpus-root>`

### Behavior changes from v1.2.0

The corpus validator now applies the Q23 canonical-pattern allowlist to every subfolder it discovers. A folder is a **scored corpus folder** only when its basename fully matches `^inv_\d{3}_(easy|medium|hard)$`. Every non-matching name is a **calibration folder** and is handled differently (SC-009, FR-027).

**For scored corpus folders**: all mandatory artifact checks and, when present, sidecar validation run as described under `validate folder`. These folders contribute to scored corpus aggregation counts reported by the validator.

**For calibration folders** (non-matching basename, e.g. `inv_024_hard_degraded_body`): per-document artifact validation still runs (mandatory artifacts are checked), and when a sidecar is present it is validated. However, these folders are reported in a separate "calibration set" count and are NEVER included in scored corpus aggregation. The rule is default-exclude: an unrecognized folder name is never silently scored.

**Reporting**: the validator output reports both the scored set and the calibration set as separate counts:

```
Corpus root: tests/stage1_vendor_identity/
  Scored corpus folders:   20  (pattern: ^inv_\d{3}_(easy|medium|hard)$)
    Valid:                  20
    Invalid:                 0
  Calibration folders:      2
    Valid:                   2
    Invalid:                 0
  Sidecars present:          1  (in scored set)
  Sidecars accepted:         1
  Sidecars rejected:         0
```

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | All validated folders (scored + calibration) pass. |
| 1 | One or more scored-corpus mandatory-artifact failures. |
| 3 | One or more sidecar `document_id` mismatch errors (in any folder). |
| 4 | One or more sidecar row-violation errors (in any folder). |
| 5 | One or more sidecar JSON/schema validation failures (in any folder). |
| 6 | Corpus root directory not found. |

Multiple failure codes may apply; the exit code is the lowest non-zero code among all failures encountered.

---

## Error message content

The Q41 specification pins the following error message format requirements. Validators MUST produce messages that contain these elements exactly.

### `document_id` mismatch error

The error MUST name both the declared `document_id` and the containing folder basename. Exact required substrings:

- The declared value from the sidecar (e.g. `"inv_999_easy"`).
- The folder basename (e.g. `"inv_001_hard"`).

Example conforming message:

```
SemanticTruthValidationError: document_id mismatch —
  declared: 'inv_999_easy'
  folder:   'inv_001_hard'
  file:     tests/stage1_semantic_quality/inv_001_hard/semantic_table_truth.json
```

### Row violation error

The error MUST name the offending `row_id` (or the row-array index in brackets when `row_id` cannot be parsed), the specific failed field, and a one-line machine-readable reason.

Example conforming messages:

```
SemanticTruthValidationError: row violation —
  row_id:  'row-3'
  field:   'unit_price'
  reason:  value '$21.00' does not match pattern ^\d+\.\d{2}$ (currency symbol not permitted in sidecar)
```

```
SemanticTruthValidationError: row violation —
  row_id:  [1]  (row_id absent or not parseable)
  field:   'required_row_text_tokens'
  reason:  array is empty (minItems: 1 required)
```

```
SemanticTruthValidationError: row violation —
  row_id:  'row-2'
  field:   'row_id'
  reason:  duplicate row_id 'row-2' at index 3 (first seen at index 1)
```

### Notes on error robustness

- When multiple row violations exist, the validator MUST report all of them, not just the first.
- When `row_id` itself is absent (the row lacks the required field), use the array index in brackets as the identifier.
- Error messages are written to stderr; the exit code signals the class of error.

---

## Notes

No new CLI flag is introduced for the semantic gate itself. The gate runs automatically inside the existing evaluator on every folder that contains a `semantic_table_truth.json` sidecar; the sidecar's presence is the opt-in (Q13 / FR-007). No `--semantic-gate` flag, no `DARTWING_SEMANTIC_GATE` environment variable, and no new configuration file are part of this feature (Q38 / Out of Scope).

The `validate semantic-truth` subcommand is a convenience for fixture authors. It does not gate or trigger the semantic quality gate evaluation — that remains the evaluator's responsibility.

The canonical-pattern allowlist regex `^inv_\d{3}_(easy|medium|hard)$` is implemented as a module-level constant in `dartwing_ocr.validator.corpus_pattern` and is reused by both the validator CLI and the gate metrics aggregator (`semantic_quality_metrics.py`) to maintain a single source of truth for calibration-folder recognition (MI-21 / Q23 / SC-009).
