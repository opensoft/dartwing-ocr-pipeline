# Schema Amendments: v1.2.0 → v1.3.0

This document records the verbatim schema delta governed by Clarifications Q14 (FR-031): a minor contract-set version bump from `1.2.0` to `1.3.0`, adding one new schema (`semantic_table_truth.schema.json`) and making additive amendments to three existing schemas (`evaluation_document.schema.json`, `evaluation_run_summary.schema.json`, `folder.schema.json`). All other v1.2.0 schemas are copied verbatim. The ready-to-copy `AMENDMENTS.md` entry appears at the end of this document.

---

## Schemas added

### `semantic_table_truth.schema.json` (NEW)

Full JSON Schema (Draft 2020-12) for the optional per-document sidecar file. Governs the shape of every `semantic_table_truth.json` authored under `tests/stage1_vendor_identity/` or `tests/stage1_semantic_quality/` (Q27, Q28, Q11, Q9, FR-002, FR-003, FR-004).

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://dartwing.internal/schemas/stage1/v1.3.0/semantic_table_truth.schema.json",
  "title": "SemanticTableTruth",
  "description": "Optional per-document authored table/body row truth for the semantic quality gate (feature 022). Separate from expected.json.",
  "type": "object",
  "required": ["document_id", "rows"],
  "additionalProperties": false,
  "properties": {
    "document_id": {
      "type": "string",
      "minLength": 1,
      "description": "Must match the per-document folder basename exactly (e.g. 'inv_001_hard'). Enforced at validator layer."
    },
    "schema_version": {
      "type": "string",
      "description": "Optional. When present, records the contract-set version (e.g. '1.3.0'). When absent the governed contract set remains authoritative.",
      "example": "1.3.0"
    },
    "rows": {
      "type": "array",
      "minItems": 1,
      "description": "Non-empty array of row truth entries. row_id uniqueness across the sidecar is enforced at validator layer (not by JSON Schema).",
      "items": { "$ref": "#/$defs/row" }
    }
  },
  "$defs": {
    "row": {
      "type": "object",
      "required": ["row_id", "required_row_text_tokens"],
      "additionalProperties": false,
      "properties": {
        "row_id": {
          "type": "string",
          "minLength": 1,
          "description": "Non-empty string, unique within the sidecar."
        },
        "required_row_text_tokens": {
          "type": "array",
          "minItems": 1,
          "description": "Non-empty array of non-empty strings. Each token drives the FR-011 binary row-text-coverage check.",
          "items": {
            "type": "string",
            "minLength": 1
          }
        },
        "quantity": {
          "type": "string",
          "description": "Optional. When present, becomes a required-content check for this row."
        },
        "description": {
          "type": "string",
          "description": "Optional. When present, becomes a required-content check for this row."
        },
        "unit_price": {
          "type": "string",
          "pattern": "^\\d+\\.\\d{2}$",
          "description": "Optional. Normalized decimal string without currency symbol (e.g. '21.00'). When present, drives both FR-009 missing-content and FR-010 currency-shape checks."
        },
        "amount": {
          "type": "string",
          "pattern": "^\\d+\\.\\d{2}$",
          "description": "Optional. Normalized decimal string without currency symbol (e.g. '420.00'). When present, drives both FR-009 missing-content and FR-010 currency-shape checks."
        }
      }
    }
  }
}
```

**Validator-layer supplements** (not expressible in JSON Schema alone):

- `document_id` MUST match the per-document folder basename (FR-003 / Q41).
- All `row_id` values MUST be unique within the `rows` array (Q11 / FR-004).
- `rows` MUST be non-empty; a sidecar with zero rows is rejected by the schema (`minItems: 1`).

---

## Schemas changed

### `evaluation_document.schema.json` — v1.2.0 → v1.3.0 delta

**BEFORE (v1.2.0)** — relevant subtree:

```json
{
  "properties": {
    "document_pass_fail": {
      "type": "object",
      "required": ["vendor_identity_passed"],
      "additionalProperties": false,
      "properties": {
        "vendor_identity_passed": {
          "type": ["boolean", "null"]
        }
      }
    }
  }
}
```

**AFTER (v1.3.0)** — same subtree with additive changes:

```json
{
  "properties": {
    "document_pass_fail": {
      "type": "object",
      "required": ["vendor_identity_passed"],
      "additionalProperties": false,
      "properties": {
        "vendor_identity_passed": {
          "type": ["boolean", "null"]
        },
        "semantic_table_quality_passed": {
          "type": ["boolean", "null"],
          "description": "true when semantic status is 'passed'; false when 'failed' or 'unevaluable'; null when 'not_applicable' (no sidecar). Always present on newly-written reports."
        }
      }
    },
    "semantic_table_quality": {
      "type": "object",
      "description": "Present when a sidecar was found OR when status is 'unevaluable'. Absent when status is 'not_applicable'.",
      "additionalProperties": false,
      "required": ["status", "failed_checks", "supporting_evidence"],
      "properties": {
        "status": {
          "type": "string",
          "enum": ["passed", "failed", "not_applicable", "unevaluable"]
        },
        "failed_checks": {
          "type": "array",
          "description": "Flat ordered array — source of truth. Items ordered by sidecar row declaration order then fixed category order (malformed-currency-shape, missing-required-content, row-text-coverage-gap, row-alignment-failure).",
          "items": {
            "type": "object",
            "required": ["category", "row_id"],
            "additionalProperties": false,
            "properties": {
              "category": {
                "type": "string",
                "enum": ["malformed-currency-shape", "missing-required-content", "row-text-coverage-gap", "row-alignment-failure"]
              },
              "row_id": { "type": "string", "minLength": 1 },
              "field": { "type": "string" },
              "expected": { "type": "string" },
              "observed": { "type": "string" },
              "predicate": { "type": "string" }
            }
          }
        },
        "row_reasons": {
          "type": "object",
          "description": "Per-row aggregation keyed by row_id, derived from failed_checks. Required when status == 'failed'.",
          "additionalProperties": {
            "type": "object",
            "required": ["categories", "reason"],
            "additionalProperties": false,
            "properties": {
              "categories": {
                "type": "array",
                "items": {
                  "type": "string",
                  "enum": ["malformed-currency-shape", "missing-required-content", "row-text-coverage-gap", "row-alignment-failure"]
                }
              },
              "reason": { "type": "string", "minLength": 1 }
            }
          }
        },
        "supporting_evidence": {
          "type": "object",
          "description": "Closed shape. Document-aggregate body-OCR stats.",
          "required": ["body_confidence_mean", "body_confidence_min", "body_line_count", "body_token_count", "header_band_excluded"],
          "additionalProperties": false,
          "properties": {
            "body_confidence_mean": { "type": "number" },
            "body_confidence_min": { "type": "number" },
            "body_line_count": { "type": "integer", "minimum": 0 },
            "body_token_count": { "type": "integer", "minimum": 0 },
            "header_band_excluded": { "type": "boolean" }
          }
        },
        "cause": {
          "type": "string",
          "enum": ["preprocess_output_missing", "preprocess_output_invalid_json", "preprocess_output_schema_invalid", "body_ocr_unreadable"],
          "description": "Required when status == 'unevaluable'. Absent otherwise."
        },
        "cause_detail": {
          "type": "string",
          "description": "Optional free-text diagnostic. Present only when status == 'unevaluable'."
        }
      }
    }
  }
}
```

The `vendor_identity_passed` property and all other v1.2.0 properties are unchanged. The two new properties (`semantic_table_quality_passed`, `semantic_table_quality`) are backward-compatible additions: a v1.2.0 `evaluation_document.json` that lacks them still validates against the v1.3.0 schema (FR-019 / SC-008).

---

### `evaluation_run_summary.schema.json` — v1.2.0 → v1.3.0 delta

**BEFORE (v1.2.0)** — top-level keys (abbreviated):

```json
{
  "properties": {
    "run_id": { "...": "..." },
    "documents_total": { "...": "..." },
    "vendor_identity_metrics": { "...": "..." }
    // ...existing keys...
  }
}
```

**AFTER (v1.3.0)** — additive top-level additions:

```json
{
  "properties": {
    // ...all v1.2.0 keys unchanged...
    "semantic_table_quality_metrics": {
      "type": "object",
      "description": "Top-level sibling key parallel to vendor-identity and feature-020 fields. Excludes calibration folders from aggregate counts.",
      "required": [
        "semantic_applicable_document_count",
        "semantic_not_applicable_document_count",
        "semantic_evaluable_document_count",
        "semantic_passed_document_count",
        "semantic_failed_document_count",
        "semantic_unevaluable_document_count",
        "semantic_table_quality_pass_rate",
        "semantic_failed_check_counts"
      ],
      "additionalProperties": false,
      "properties": {
        "semantic_applicable_document_count": { "type": "integer", "minimum": 0 },
        "semantic_not_applicable_document_count": { "type": "integer", "minimum": 0 },
        "semantic_evaluable_document_count": { "type": "integer", "minimum": 0 },
        "semantic_passed_document_count": { "type": "integer", "minimum": 0 },
        "semantic_failed_document_count": { "type": "integer", "minimum": 0 },
        "semantic_unevaluable_document_count": { "type": "integer", "minimum": 0 },
        "semantic_table_quality_pass_rate": {
          "type": ["number", "null"],
          "minimum": 0,
          "maximum": 1,
          "description": "passed / evaluable, rounded to 6 dp ROUND_HALF_EVEN. null when evaluable == 0."
        },
        "semantic_failed_check_counts": {
          "type": "object",
          "required": ["malformed-currency-shape", "missing-required-content", "row-text-coverage-gap", "row-alignment-failure"],
          "additionalProperties": false,
          "properties": {
            "malformed-currency-shape": { "type": "integer", "minimum": 0 },
            "missing-required-content": { "type": "integer", "minimum": 0 },
            "row-text-coverage-gap": { "type": "integer", "minimum": 0 },
            "row-alignment-failure": { "type": "integer", "minimum": 0 }
          }
        }
      }
    },
    "semantic_document_statuses": {
      "type": "array",
      "description": "Per-document semantic status entries for the run scope, sorted by deterministic run-document order. Includes calibration folders; those are excluded from aggregate counts.",
      "items": {
        "type": "object",
        "required": ["document_id", "semantic_table_quality_status", "semantic_table_quality_passed"],
        "additionalProperties": false,
        "properties": {
          "document_id": { "type": "string", "minLength": 1 },
          "semantic_table_quality_status": {
            "type": "string",
            "enum": ["passed", "failed", "not_applicable", "unevaluable"]
          },
          "semantic_table_quality_passed": { "type": ["boolean", "null"] }
        }
      }
    }
  }
}
```

Both `semantic_table_quality_metrics` and `semantic_document_statuses` are optional in the schema (backward-compat for v1.2.0 reports per FR-019 / SC-008). The writer MUST emit them on every newly-written run summary (FR-018).

---

### `folder.schema.json` — v1.2.0 → v1.3.0 delta

**BEFORE (v1.2.0):**

```json
{
  "properties": {
    "source.pdf": { "description": "Mandatory." },
    "expected.json": { "description": "Mandatory." },
    "preprocess_output.json": { "description": "Optional (written by pipeline)." }
  }
}
```

**AFTER (v1.3.0)** — one new optional entry:

```json
{
  "properties": {
    "source.pdf": { "description": "Mandatory." },
    "expected.json": { "description": "Mandatory." },
    "preprocess_output.json": { "description": "Optional (written by pipeline)." },
    "semantic_table_truth.json": {
      "description": "Optional. When present, the validator validates it against semantic_table_truth.schema.json and the gate evaluates semantic table quality for this document."
    }
  }
}
```

The mandatory artifacts (`source.pdf`, `expected.json`) are unchanged. Note: the synthetic US2 fixture at `tests/stage1_semantic_quality/inv_001_hard/` is exempt from the `source.pdf` mandatory requirement because it is a synthetic-fixture root, not a production corpus folder under `tests/stage1_vendor_identity/`.

---

## Schemas unchanged (copied verbatim from v1.2.0)

The following schemas are copied from `contracts/stage1_vendor_identity/v1.2.0/` into `v1.3.0/` with no modifications:

- `preprocess_output.schema.json`
- `edge_extraction_output.schema.json`
- `routing_decision.schema.json`
- `final_structured_payload.schema.json`
- `evidence_packet.schema.json`
- `expected.schema.json`

The `expected.schema.json` copy is especially significant: `expected.json` retains its current vendor-identity-only shape and meaning unchanged (FR-006 / MI-23). Table/body truth is never written into `expected.json`.

---

## `contract_set.json` delta

**BEFORE (v1.2.0):**

```json
{
  "contract_set_version": "1.2.0",
  "schemas": [
    "preprocess_output.schema.json",
    "edge_extraction_output.schema.json",
    "routing_decision.schema.json",
    "final_structured_payload.schema.json",
    "evidence_packet.schema.json",
    "expected.schema.json",
    "evaluation_document.schema.json",
    "evaluation_run_summary.schema.json",
    "folder.schema.json"
  ]
}
```

**AFTER (v1.3.0):**

```json
{
  "contract_set_version": "1.3.0",
  "schemas": [
    "preprocess_output.schema.json",
    "edge_extraction_output.schema.json",
    "routing_decision.schema.json",
    "final_structured_payload.schema.json",
    "evidence_packet.schema.json",
    "expected.schema.json",
    "evaluation_document.schema.json",
    "evaluation_run_summary.schema.json",
    "folder.schema.json",
    "semantic_table_truth.schema.json"
  ]
}
```

The only structural change is the addition of `"semantic_table_truth.schema.json"` to the `schemas` list and the version bump. All nine pre-existing schema entries are present and in the same order.

---

## Proposed AMENDMENTS.md entry

Copy the block below verbatim into `contracts/stage1_vendor_identity/AMENDMENTS.md` as the new entry for v1.3.0:

```markdown
## v1.3.0 — 2026-05-23

**Type**: Minor (additive only; backward-compatible)

**Summary**:

- **New schema**: `semantic_table_truth.schema.json` — optional per-document sidecar for authored table/body row truth, consumed by the feature-022 semantic quality gate. Top-level shape: `{document_id, rows[], schema_version?}`. Row shape: `{row_id (required, non-empty, unique), required_row_text_tokens (required, non-empty array of non-empty strings), quantity?, description?, unit_price?, amount?}`. `unit_price`/`amount` are normalized decimal strings without currency symbol (pattern `^\d+\.\d{2}$`). `document_id`-to-folder-basename matching and `row_id` uniqueness are enforced at validator layer (not in JSON Schema).
- **`evaluation_document.schema.json`** (additive): new optional `document_pass_fail.semantic_table_quality_passed` field (`boolean | null`); new optional `semantic_table_quality` object with closed shape (`status`, `failed_checks`, `row_reasons`, `supporting_evidence`, optional `cause`/`cause_detail`). Pre-v1.3.0 reports without these fields remain schema-valid (backward-compat per FR-019).
- **`evaluation_run_summary.schema.json`** (additive): new optional top-level `semantic_table_quality_metrics` namespace (8 fields including nullable pass rate and per-category failed-check counts); new optional `semantic_document_statuses` array (per-document `document_id`, `semantic_table_quality_status`, `semantic_table_quality_passed` entries). Pre-v1.3.0 reports without these keys remain schema-valid.
- **`folder.schema.json`** (additive): `semantic_table_truth.json` listed as an optional per-document folder artifact alongside the unchanged mandatory `source.pdf` and `expected.json`.
- **All other schemas** (`preprocess_output`, `edge_extraction_output`, `routing_decision`, `final_structured_payload`, `evidence_packet`, `expected`) are copied unchanged from v1.2.0.

**Justification**: Speckit Clarifications Q14 / spec FR-031 (feature 022-ocr-semantic-quality-gate). The minor bump is required because the governed contract set gains one new schema; the existing schema changes are strictly additive (new optional fields only). No breaking change is introduced.

**Spec link**: `specs/022-ocr-semantic-quality-gate/spec.md` — Clarifications Q14 (FR-031).

**Validator**: Run `python -m dartwing_ocr.validator show contract-set` after bumping `contract_versions.py::CURRENT_CONTRACT_SET_VERSION` to `"1.3.0"` to confirm the new schema is registered.
```
