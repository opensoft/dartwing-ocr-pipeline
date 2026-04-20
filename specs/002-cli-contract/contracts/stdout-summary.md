# Stdout Run Summary: Stage 1 Pipeline CLI

**Frozen**: 2026-04-20

---

## When emitted

Emitted as a single JSON-object line to stdout if and only if the CLI exits with code `0` (success).

## Shape

```json
{
  "document_id": "inv_001",
  "decision": "edge_accept",
  "manual_review_required": false,
  "review_reason": null,
  "artifacts": {
    "preprocess_output.json": "/abs/path/to/inv_001_easy/preprocess_output.json",
    "edge_extraction_output.json": "/abs/path/to/inv_001_easy/edge_extraction_output.json",
    "routing_decision.json": "/abs/path/to/inv_001_easy/routing_decision.json",
    "final_structured_payload.json": "/abs/path/to/inv_001_easy/final_structured_payload.json"
  }
}
```

## Field definitions

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `document_id` | `string` | Invocation | Same value stamped into all four artifacts (FR-028). |
| `decision` | `string` | `routing_decision.decision` | `"edge_accept"` or `"edge_review_required"`. Stage 1 vocabulary. |
| `manual_review_required` | `boolean` | `routing_decision.review_status.manual_review_required` | Mirrors the artifact. |
| `review_reason` | `string \| null` | `routing_decision.review_status.review_reason` | Mirrors the artifact. `null` when `manual_review_required` is `false`. |
| `artifacts` | `object` | Resolved paths | Keys are the four reserved filenames. Values are absolute paths. |

## Rules

- Single line, valid JSON, no trailing newline after the closing brace.
- Absolute paths are permitted in this output (FR-029 exempts stdout and stderr from the no-absolute-path rule).
- The `artifacts` object always contains exactly four keys — the four reserved pipeline artifact filenames.
- The harness can branch on `decision` and `manual_review_required` without re-reading the on-disk artifacts.
