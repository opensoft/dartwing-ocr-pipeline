# Exit Code Vocabulary: Stage 1 Pipeline CLI

**Frozen**: 2026-04-20
**Governance**: Changes require an amendment in `contracts/stage1_vendor_identity/AMENDMENTS.md`.

---

## Exit codes

| Code | Name | Layer | Description |
|------|------|-------|-------------|
| 0 | `SUCCESS` | — | All four artifacts produced and validated against v1.0.0. |
| 10 | `USAGE_ERROR` | `arguments` | Bad, missing, or conflicting arguments. Includes: both `--input` and `--document-folder`, unknown arguments, invalid `--log-level`, `--contract-set-version` naming a non-installed version, `document_id` not derivable and `--document-id` not provided. |
| 11 | `INPUT_NOT_FOUND` | `input_validation` | Resolved input PDF path does not exist, or `--document-folder` does not contain `source.pdf`, or destination folder does not exist. |
| 12 | `INVALID_PDF` | `input_validation` | Input file exists but is not a PDF (magic byte check: first 5 bytes are not `%PDF-`). |
| 13 | `OUTPUT_IN_USE` | `input_validation` | One or more reserved artifact filenames already exist in the destination folder and `--overwrite` was not passed. |
| 14 | `OUTPUT_PATH_NOT_USABLE` | `input_validation` | Destination path is not a directory or is not writable. |
| 20 | `PROCESSING_FAILURE` | `preprocess` / `extraction` / `routing` / `final_payload` | A pipeline processing stage failed. The `stage` field in the stderr failure record identifies which one. Includes: Ollama unreachable, model error, timeout exceeded, unexpected exception. |
| 30 | `SCHEMA_VALIDATION_FAILURE` | `schema_validation` | All four artifacts were produced but at least one fails validation against the v1.0.0 contract set. The stderr failure record names the offending artifact and field path. |

## Guarantees

- **Distinctness**: No two categories share the same numeric code. An operator reading only the exit code can distinguish every layer.
- **Stability**: Numeric values do not change through stage 1. New categories may be added via amendment; existing values are never reassigned.
- **Completeness**: Every non-zero exit produces a structured failure record on stderr (see `stderr-failure-record.md`). The `exit_code_name` in that record matches the `Name` column above.

## Grouping rationale

- **10–14**: Input and argument layer. Problems the caller can fix without changing the pipeline.
- **20–29**: Processing layer. Problems inside a pipeline stage (model, OCR, logic).
- **30–39**: Post-processing validation layer. Artifacts were produced but do not conform.
