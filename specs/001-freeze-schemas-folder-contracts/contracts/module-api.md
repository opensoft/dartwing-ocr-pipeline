# Validator Python Module API Contract

**Feature**: `001-freeze-schemas-folder-contracts`
**Import root**: `dartwing_ocr.validator`

Stage 1 harness code, pipeline smoke tests, and Python-level callers import the validator as a library. The CLI (`validator-cli.md`) is a thin wrapper over these entry points. This document freezes the public Python surface at contract-set version `1.0.0`.

## Public entry points

All names below are importable from `dartwing_ocr.validator` (re-exported via `__init__.py`). Nothing under `_*` or inside submodules other than the names listed here is part of the public contract.

### `load_contract_set(version: str | None = None) -> ContractSet`

Load a named contract-set version from `contracts/stage1_vendor_identity/`. If `version` is `None`, load the latest version available on disk. Raises `ContractSetNotFoundError` when the version directory is absent and `ContractSetCorruptError` when `contract_set.json` is malformed.

### `validate_artifact(path: str | Path, contract: ArtifactName | str, *, version: str | None = None) -> ValidationOutcome`

Validate a single on-disk JSON artifact. `contract` may be the enum or its string name. `version` defaults to the version stamped on the artifact; mismatches between `version` and the stamped value produce a `CONTRACT_SET_VERSION_INCOMPATIBLE` violation.

### `validate_folder(folder: str | Path, *, version: str | None = None) -> ValidationOutcome`

Validate a per-document folder against the folder contract plus any artifact files it contains.

### `validate_corpus(root: str | Path, *, version: str | None = None, fail_fast: bool = False) -> ValidationOutcome`

Validate an entire corpus root. Returns a single `ValidationOutcome` whose `sub_reports` list captures per-folder outcomes (in insertion order).

## Public data classes

All are Pydantic v2 models; fields and types match the structured-report JSON Schema (`report.schema.json`).

### `ArtifactName` (enum)

String enum with the seven values: `preprocess_output`, `edge_extraction_output`, `routing_decision`, `final_structured_payload`, `expected`, `evaluation_document`, `evaluation_run_summary`.

### `Severity` (enum)

String enum: `error`, `warning`.

### `Violation`

Immutable. Fields: `severity`, `target`, `field_path`, `violation_code`, `reason`, `expected`, `source_file`. Maps 1:1 to the `Violation` definition in `report.schema.json`.

### `ValidationOutcome`

Immutable. Fields: `report_version`, `contract_set_version_checked`, `target_summary`, `passed`, `violations`, `warnings`, `counts`, `sub_reports`. Serializes to the structured-report JSON Schema via `.model_dump(mode="json")`.

### `ContractSet`

Loaded-but-not-validated bundle describing the contract-set version in use.

- `version: str`
- `artifact_schemas: dict[ArtifactName, Path]`
- `folder_schema: Path`
- `challenge_tags: frozenset[str]`
- `cross_artifact_rules: tuple[str, ...]`

### Exceptions

- `ContractSetNotFoundError` — requested version directory is absent.
- `ContractSetCorruptError` — `contract_set.json` malformed or references missing schema files.
- `InvalidArtifactNameError` — string passed to `validate_artifact` is not one of the seven names.

Validation failures are not raised as exceptions; they are reported as `Violation` entries inside a `ValidationOutcome` with `passed=False`.

## Stability guarantees

- Function names, argument names, and argument order are frozen at contract-set `1.0.0`.
- `ValidationOutcome` and `Violation` field names and types are frozen.
- The enum values on `ArtifactName` and `Severity` are frozen.
- Additions to these public entry points MAY happen via the amendment path (minor version bump). Removals or renames require a major version bump.
