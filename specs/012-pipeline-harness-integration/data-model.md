# Data Model: Pipeline Harness Integration

**Feature**: `012-pipeline-harness-integration`  
**Date**: 2026-05-05  
**Scope**: Harness-side request and outcome objects for preparing documents through the pipeline before evaluation. This feature does not add or change persisted artifact schemas.

## Entity: HarnessPipelineRequest

The user's request to prepare one document or a corpus through the pipeline before evaluation.

| Field | Type | Validation | Notes |
|---|---|---|---|
| `target` | enum: `document` / `corpus` | required | Matches evaluator subcommand target. |
| `path` | `Path` | existing folder/root must be valid for the evaluator target | Document folder or corpus root. |
| `contract_set_version` | string | must be accepted by existing evaluator/pipeline validators | Passed to both preparation and evaluation. |
| `overwrite` | bool | default false | Controls whether the pipeline may replace canonical stage artifacts. |
| `stack_preset` | string or null | validated by pipeline CLI | Explicit real-runtime selection. |
| `profiles` | mapping stage -> string or null | validated by pipeline CLI | Per-stage profile overrides. |
| `stub_default` | bool | derived | True when no preset or per-stage profile is supplied. |
| `on_failure` | enum: `continue` / `fail-fast` | corpus only | Passed to warm corpus pipeline mode. |
| `runtime_endpoints` | mapping lane -> URL or null | optional | Forwarded to pipeline CLI only when supplied. |
| `timeout` | int | positive | Forwarded to pipeline CLI. |

## Entity: PipelineCommand

The subprocess command assembled from a `HarnessPipelineRequest`.

| Field | Type | Validation | Notes |
|---|---|---|---|
| `argv` | tuple[str, ...] | starts with current Python executable and `-m ledgerlinc_ocr.pipeline run` | Never shell-expanded. |
| `documents_file` | `Path` or null | exists for corpus mode during command execution | Temporary file containing selected document folders. |
| `cwd` | `Path` or null | optional | Inherits current process working directory unless tests override. |

## Entity: PipelinePreparationOutcome

The parsed result of one pipeline preparation subprocess.

| Field | Type | Validation | Notes |
|---|---|---|---|
| `return_code` | int | subprocess return code | Non-zero may be acceptable only for corpus continue mode with successful documents. |
| `stdout` | string | captured | Preserved for diagnostics. |
| `stderr` | string | captured | Preserved for operator-facing failure details. |
| `run_summary` | dict or null | must be the final `kind: run_summary` JSON line in corpus mode when present | Contains warm timing metadata emitted by the pipeline. |
| `prepared_folders` | tuple[Path, ...] | successful document folders only | Used to evaluate a subset after continue-mode corpus preparation. |
| `failed_documents` | tuple[PreparedDocumentFailure, ...] | parsed from run summary where available | Operator-facing only in this feature. |

## Entity: PreparedDocumentFailure

One document that the pipeline could not prepare.

| Field | Type | Validation | Notes |
|---|---|---|---|
| `document_id` | string | best available identifier | From pipeline summary when available. |
| `folder` | string | raw folder token from pipeline summary | Informational. |
| `failed_stage` | string or null | from pipeline summary | Distinguishes preparation failure from evaluation failure. |
| `exit_code` | int or null | from pipeline summary | Informational. |
| `message` | string or null | from pipeline summary | Informational. |

## Entity: EvaluationSubset

The list of document folders passed into aggregation after corpus preparation.

| Field | Type | Validation | Notes |
|---|---|---|---|
| `root` | `Path` | corpus root | Output summaries still write at the root. |
| `folders` | tuple[Path, ...] | each folder must contain `expected.json` and `final_structured_payload.json` before evaluation | Defaults to normal corpus discovery when no subset is provided. |

## State Transitions

```text
requested
  -> command_built
  -> pipeline_completed
  -> preparation_validated
  -> evaluation_started
  -> evaluation_completed
```

Failure states:

- `command_failed`: subprocess returned non-zero and the request cannot continue.
- `preparation_partial`: corpus continue mode had failures but at least one document was prepared.
- `no_documents_prepared`: corpus continue mode produced no prepared documents.
- `evaluation_failed`: preparation completed but evaluator comparison raised a hard error.
