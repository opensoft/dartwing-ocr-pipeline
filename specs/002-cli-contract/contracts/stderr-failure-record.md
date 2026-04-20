# Stderr Failure Record: Stage 1 Pipeline CLI

**Frozen**: 2026-04-20

---

## When emitted

Emitted as a single JSON-object line to stderr on any non-zero exit code. Log messages (controlled by `--log-level`) may precede this line on stderr; the failure record is always the last line.

## Shape

```json
{
  "exit_code": 20,
  "exit_code_name": "PROCESSING_FAILURE",
  "stage": "extraction",
  "message": "Ollama endpoint unreachable at http://localhost:11434",
  "artifacts_written": [
    "/abs/path/to/inv_001_easy/preprocess_output.json"
  ]
}
```

## Field definitions

| Field | Type | Description |
|-------|------|-------------|
| `exit_code` | `integer` | Numeric exit code from the vocabulary (see `exit-codes.md`). |
| `exit_code_name` | `string` | Category name matching the exit code vocabulary. One of: `USAGE_ERROR`, `INPUT_NOT_FOUND`, `INVALID_PDF`, `OUTPUT_IN_USE`, `OUTPUT_PATH_NOT_USABLE`, `PROCESSING_FAILURE`, `SCHEMA_VALIDATION_FAILURE`. |
| `stage` | `string` | Pipeline stage where the failure occurred. One of: `arguments`, `input_validation`, `preprocess`, `extraction`, `routing`, `final_payload`, `schema_validation`. |
| `message` | `string` | Human-readable description. May mention the Ollama endpoint, the failing artifact, or the missing input. Must not embed stack traces or implementation-internal module paths. |
| `artifacts_written` | `array of string` | Absolute paths of artifact files already written to disk when the failure occurred. Empty array if no artifacts were written. |

## Rules

- Single line, valid JSON, no trailing newline after the closing brace.
- Always emitted on non-zero exit, including `USAGE_ERROR` (where `artifacts_written` is always `[]` and `stage` is `"arguments"`).
- Absolute paths are permitted (FR-029 exempts stderr).
- `artifacts_written` lists only the four reserved pipeline artifact filenames that were successfully written before the failure. It does not include temporary files.
- On `SCHEMA_VALIDATION_FAILURE`, `message` should name the offending artifact and the failing field path so the operator knows which artifact to inspect.
- Partial artifacts remain on disk for debugging (FR-024). The harness can use `artifacts_written` to clean up if it chooses.
- When an exception occurs outside an identifiable processing stage (memory exhaustion, OS-level signal, unknown import error), `stage` MUST be set to the last successfully-entered stage. If no stage has been entered yet, use `"input_validation"`. This rule keeps `stage` values drawn from the closed stage vocabulary even for ambiguous failures.

## Schema validation failure example

```json
{
  "exit_code": 30,
  "exit_code_name": "SCHEMA_VALIDATION_FAILURE",
  "stage": "schema_validation",
  "message": "edge_extraction_output.json: required property 'vote_metadata' is missing at path $",
  "artifacts_written": [
    "/abs/path/to/inv_001_easy/preprocess_output.json",
    "/abs/path/to/inv_001_easy/edge_extraction_output.json",
    "/abs/path/to/inv_001_easy/routing_decision.json",
    "/abs/path/to/inv_001_easy/final_structured_payload.json"
  ]
}
```
