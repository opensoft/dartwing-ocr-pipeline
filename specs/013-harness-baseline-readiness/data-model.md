# Data Model: Harness Baseline Readiness

## Corpus Document ID

- **Definition**: The stable identifier shared by folder naming, `expected.json`, generated pipeline artifacts, and evaluation outputs.
- **Format**: Full corpus folder name: `inv_<NNN>_<difficulty>`, where difficulty is `easy`, `medium`, `hard`, or `missing_name`.
- **Examples**: `inv_001_easy`, `inv_011_hard`, `inv_016_missing_name`.
- **Validation rules**:
  - Folder name must match the stage 1 corpus folder pattern.
  - `expected.json.document_id` must equal the folder name.
  - Pipeline-generated artifacts for document-folder runs must use the same value.
  - Evaluation fails hard when expected and final payload IDs differ.

## Committed Corpus Folder

- **Definition**: A per-document folder under `tests/stage1_vendor_identity/`.
- **Required files**: `source.pdf`, `expected.json`.
- **Optional files**: `notes.md`, generated artifacts during temporary-copy runs.
- **Relationship**: Owns one Corpus Document ID; the ID is derived from the folder basename, not from the numeric prefix alone.

## Runtime Dependency Preparation Failure

- **Definition**: A pipeline-side failure returned when a selected live stage profile cannot be prepared because an optional dependency is unavailable.
- **Fields surfaced to callers**:
  - `stage`: pipeline stage label such as `preprocess` or `extraction`.
  - `exit_code`: existing pipeline processing-failure or usage-error code.
  - `message`: concise missing-dependency/profile explanation.
- **Validation rules**:
  - Must not include a raw Python traceback in stderr for the expected missing-dependency path.
  - Must preserve stub profile behavior without requiring optional dependencies.

## Harness Baseline Smoke

- **Definition**: Deterministic evaluator invocation that runs pipeline preparation before evaluating a committed corpus document.
- **Inputs**: Unmodified copy of `tests/stage1_vendor_identity/inv_001_easy`, `--run-pipeline`, `--pipeline-overwrite`, and default stub-safe profiles.
- **Output**: `evaluation_document.json` plus generated pipeline artifacts whose `document_id` equals `inv_001_easy`.
