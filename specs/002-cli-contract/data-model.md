# Data Model: Stage 1 One-Document CLI Contract

**Feature**: `002-cli-contract`
**Date**: 2026-04-20

---

## Entities

### 1. CLIInvocation

Represents one execution of the pipeline CLI. Not persisted as its own artifact; its observable outputs are the four artifacts, the exit code, the stdout summary, and the stderr failure record.

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `input_pdf` | `Path` | `--input` or `--document-folder` + `source.pdf` | Resolved to absolute; read-only. |
| `destination_folder` | `Path` | `--output-dir` or derived | Must exist and be writable. Never created implicitly. |
| `document_id` | `str` | `--document-id` or derived from folder name | Pattern: `^inv_\d{3}$` for corpus folders; freeform when explicit. |
| `overwrite` | `bool` | `--overwrite` flag | Default `false`. Controls whether existing artifacts are replaced. |
| `pipeline_version` | `str` | `--pipeline-version` or package default | Semver string stamped into artifacts. |
| `policy_version` | `str` | `--policy-version` or default | Stamped into `routing_decision` only. |
| `contract_set_version` | `str` | `--contract-set-version` or installed default | Must match an installed contract set. Validated at argument time. |
| `ollama_url` | `str` | `--ollama-url` or `OLLAMA_BASE_URL` env or `http://localhost:11434` | Passed to extraction stage. |
| `log_level` | `str` | `--log-level` | One of `error`, `warning`, `info`, `debug`. Default `warning`. |
| `timeout` | `int` | `--timeout` | Seconds. Default 300. |

**Validation rules**:
- `--input` and `--document-folder` are mutually exclusive (FR-002).
- `--contract-set-version`, if provided, must name an installed version (FR-006).
- `--log-level` must be one of the four valid values (FR-007).
- Unknown arguments are rejected (FR-019).

---

### 2. ExitCode

An enum mapping the stable category names to numeric values. Frozen at stage 1.

| Code | Name | Layer | Description |
|------|------|-------|-------------|
| 0 | `SUCCESS` | — | All four artifacts produced and validated. |
| 10 | `USAGE_ERROR` | arguments | Bad, missing, or conflicting arguments. |
| 11 | `INPUT_NOT_FOUND` | input | PDF missing, folder missing `source.pdf`, dest folder missing. |
| 12 | `INVALID_PDF` | input | Content is not a PDF (magic byte check). |
| 13 | `OUTPUT_IN_USE` | input | Reserved artifact filenames already present without `--overwrite`. |
| 14 | `OUTPUT_PATH_NOT_USABLE` | input | Destination not writable or not a directory. |
| 20 | `PROCESSING_FAILURE` | processing | A pipeline stage raised a failure. |
| 30 | `SCHEMA_VALIDATION_FAILURE` | post-processing | A produced artifact fails v1.0.0 schema validation. |

**Rules**: No two categories share a numeric code (FR-022). Numeric values are stable through stage 1 (FR-021).

---

### 3. StdoutRunSummary

A single JSON-object line emitted to stdout on exit code `0` (FR-025).

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `document_id` | `str` | From invocation | Same as stamped in artifacts. |
| `decision` | `str` | From `routing_decision.decision` | `"edge_accept"` or `"edge_review_required"`. |
| `manual_review_required` | `bool` | From `routing_decision.review_status` | Mirrors the artifact. |
| `review_reason` | `str \| null` | From `routing_decision.review_status` | Mirrors the artifact. |
| `artifacts` | `object` | Resolved paths | Maps each of the four reserved filenames to its absolute path on disk. |

**Rules**: Emitted only on success. Single line, no trailing newline in the JSON. Absolute paths are acceptable here (FR-029 exempts stdout).

---

### 4. StructuredFailureRecord

A single JSON-object line emitted to stderr on any non-zero exit (FR-023).

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `exit_code` | `int` | From `ExitCode` | Numeric value. |
| `exit_code_name` | `str` | From `ExitCode` | Category name (e.g., `"INPUT_NOT_FOUND"`). |
| `stage` | `str` | Pipeline stage | One of: `arguments`, `input_validation`, `preprocess`, `extraction`, `routing`, `final_payload`, `schema_validation`. |
| `message` | `str` | Generated | Human-readable description. |
| `artifacts_written` | `list[str]` | Observed | Absolute paths of artifacts already on disk. May be empty. |

**Rules**: Always emitted on non-zero exit (FR-023). `artifacts_written` lists partial outputs left for debugging (FR-024).

---

### 5. ReservedArtifactFilenames

The closed set of filenames the pipeline CLI is authorized to write. Frozen at v1.0.0.

| Filename | Written by | Notes |
|----------|-----------|-------|
| `preprocess_output.json` | Pipeline CLI | FR-010 |
| `edge_extraction_output.json` | Pipeline CLI | FR-010 |
| `routing_decision.json` | Pipeline CLI | FR-010 |
| `final_structured_payload.json` | Pipeline CLI | FR-010 |
| `evaluation_document.json` | Evaluator (harness) | Off-limits to CLI (FR-013) |
| `votes/` | Future ensemble | Off-limits to CLI (FR-014) |
| `consensus_output.json` | Future ensemble | Off-limits to CLI (FR-014) |

---

### 6. PipelineStage

The ordered set of stages the CLI orchestrates. Each stage is a pluggable callable.

| Order | Stage Name | Responsibility | Produces |
|-------|-----------|---------------|----------|
| 1 | `arguments` | Parse and validate CLI arguments | — |
| 2 | `input_validation` | Check PDF exists, is PDF, dest is usable, no conflicts | — |
| 3 | `preprocess` | PDF → raw OCR, layout, quality | `preprocess_output.json` |
| 4 | `extraction` | Evidence packet → structured fields | `edge_extraction_output.json` |
| 5 | `routing` | Deterministic decision from extraction | `routing_decision.json` |
| 6 | `final_payload` | Clean handoff payload + trace | `final_structured_payload.json` |
| 7 | `schema_validation` | Validate all four artifacts against v1.0.0 | — |

**Rules**: Stages 3–6 are stub implementations in this feature (they write pre-canned or minimal valid artifacts for contract testing). Real implementations are delivered by downstream features. Stage 7 reuses the existing validator module.

---

## Relationships

```
CLIInvocation
  ├── resolves → input_pdf (Path)
  ├── resolves → destination_folder (Path)
  ├── derives → document_id (from folder name or --document-id)
  ├── runs → PipelineStage[1..7] (ordered)
  │     ├── stages 3-6 each write one artifact into destination_folder
  │     └── stage 7 validates all four artifacts via validator module
  ├── on success → emits StdoutRunSummary (exit 0)
  └── on failure → emits StructuredFailureRecord (exit non-zero)

ExitCode
  ├── returned by CLIInvocation
  ├── embedded in StdoutRunSummary (implicitly: 0)
  └── embedded in StructuredFailureRecord (exit_code + exit_code_name)

ReservedArtifactFilenames
  ├── written by PipelineStage 3-6 (four pipeline artifacts)
  ├── checked by --overwrite guard (before processing)
  └── validated by PipelineStage 7 (post-hoc schema check)
```

## State Transitions

```
CLI Start
  │
  ├─ argument parsing fails → USAGE_ERROR (10)
  │
  ├─ input PDF not found → INPUT_NOT_FOUND (11)
  ├─ input not a PDF → INVALID_PDF (12)
  ├─ dest folder not usable → OUTPUT_PATH_NOT_USABLE (14)
  ├─ artifacts exist w/o --overwrite → OUTPUT_IN_USE (13)
  │
  ├─ preprocess fails → PROCESSING_FAILURE (20), artifacts_written=[]
  ��─ extraction fails → PROCESSING_FAILURE (20), artifacts_written=[preprocess_output.json]
  ├─ routing fails → PROCESSING_FAILURE (20), artifacts_written=[preprocess_output.json, edge_extraction_output.json]
  ├─ final_payload fails → PROCESSING_FAILURE (20), artifacts_written=[...3 files]
  │
  ├─ schema validation fails → SCHEMA_VALIDATION_FAILURE (30), artifacts_written=[...4 files]
  │
  └─ all pass → SUCCESS (0), emit StdoutRunSummary
```
