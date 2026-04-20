# Research: Stage 1 One-Document CLI Contract

**Feature**: `002-cli-contract`
**Date**: 2026-04-20

---

## R-001: CLI Entry Point Name and Invocation Form

**Decision**: `python -m ledgerlinc_ocr.pipeline` is the contract-stable invocation. A `console_scripts` entry `ledgerlinc-pipeline` is added as a convenience alias.

**Rationale**: The existing validator uses `python -m ledgerlinc_ocr.validator` and has no `console_scripts` entry. Adding a `console_scripts` entry for the pipeline CLI improves developer ergonomics (`ledgerlinc-pipeline run ...` vs. `python -m ledgerlinc_ocr.pipeline run ...`), but the `python -m` form is the one the harness targets because it works without installation into PATH and matches the validator precedent. The contract documents both; the harness examples use the `python -m` form.

**Alternatives considered**:
- `python -m ledgerlinc_ocr run` (top-level `__main__.py`): Rejected — collapses pipeline and validator into one dispatch layer; the spec says these are separate concerns.
- `ledgerlinc-ocr pipeline run`: Rejected — overloads the package name as a multi-command CLI; premature for stage 1.

---

## R-002: Module Layout Within the Package

**Decision**: `src/ledgerlinc_ocr/pipeline/` as a sibling package to `validator/`.

**Rationale**: The validator is at `src/ledgerlinc_ocr/validator/` with its own `__main__.py` and `cli.py`. The pipeline follows the same pattern. Both are under the `ledgerlinc_ocr` namespace but are independently invocable. The pipeline can import from the validator (e.g., `loader.load_contract_set`, `artifact.validate_artifact`) for post-hoc schema validation without circular dependencies.

**Alternatives considered**:
- `src/ledgerlinc_ocr/cli.py` (flat file): Rejected — too many responsibilities for one file (argument parsing, path resolution, exit codes, orchestration, PDF check).
- `src/ledgerlinc_pipeline/` (separate top-level package): Rejected — adds a second package to `pyproject.toml` and breaks the single-namespace convention.

---

## R-003: Exit Code Numeric Values

**Decision**: Use a contiguous set starting above the validator's range (0–3), mapped to the spec's seven categories:

| Code | Name | Spec Category |
|------|------|---------------|
| 0 | `SUCCESS` | Success |
| 10 | `USAGE_ERROR` | usage error |
| 11 | `INPUT_NOT_FOUND` | input not found |
| 12 | `INVALID_PDF` | invalid PDF |
| 13 | `OUTPUT_IN_USE` | output in use |
| 14 | `OUTPUT_PATH_NOT_USABLE` | output path not usable |
| 20 | `PROCESSING_FAILURE` | processing failure |
| 30 | `SCHEMA_VALIDATION_FAILURE` | schema validation failure |

**Rationale**: Grouping by tens separates concern layers: 10s = input/argument layer, 20s = processing layer, 30s = post-processing validation layer. Code `0` is universal success. This leaves room for future subcategories (e.g., 21 for extraction-specific failure) without reassigning existing codes. The validator uses 0–3 so there is no collision.

**Alternatives considered**:
- Sequential 1–7: Rejected — no semantic grouping, harder to remember.
- BSD sysexits (64–78): Rejected — the categories don't map cleanly to sysexits and the harness needs pipeline-specific semantics, not POSIX generics.

---

## R-004: Document ID Derivation Logic

**Decision**: Extract `document_id` from the destination folder name by matching `^(inv_\d{3})_(easy|medium|hard|missing_name)$` and capturing group 1. If the folder name does not match, require `--document-id` or exit with `USAGE_ERROR`.

**Rationale**: The folder contract (`folder.schema.json`) defines `document_id_pattern: "^inv_\\d{3}$"` and `folder_name_pattern: "^inv_\\d{3}_(easy|medium|hard|missing_name)$"`. The derivation is a direct extraction from the folder contract's own patterns. The spec (FR-004) says "derived deterministically from the destination folder name using the documented corpus convention; if derivation is ambiguous, the CLI MUST exit with a usage error."

**Alternatives considered**:
- Derive from `source.pdf` filename: Rejected — the spec ties identity to the destination folder, not the input file.
- Always require `--document-id`: Rejected — spec says it's optional with automatic derivation for corpus folders.

---

## R-005: PDF Content Detection (File Magic)

**Decision**: Check the first 5 bytes of the file for `%PDF-` (bytes `25 50 44 46 2D`). This is the PDF file signature per ISO 32000-1.

**Rationale**: FR-017 requires content inspection, not extension checking. The PDF magic bytes are universally reliable and require no external dependency. The `python-magic` library (libmagic wrapper) would add a C dependency to the devcontainer for no additional accuracy — PDF magic is a fixed 5-byte prefix. Stdlib `struct` or raw `bytes` comparison is sufficient.

**Alternatives considered**:
- `python-magic` (libmagic): Rejected — adds a system dependency (`libmagic1`) for a check that is a 5-byte comparison. Overkill for stage 1.
- File extension check only: Rejected — explicitly forbidden by FR-017.
- `PyPDF2` / `pypdf` header parsing: Rejected — adds a dependency just for validation; the 5-byte check is sufficient to distinguish "not a PDF" from "corrupt PDF" (the latter would surface as a processing failure downstream).

---

## R-006: OLLAMA_BASE_URL Default Value

**Decision**: Default to `http://localhost:11434`. The CLI reads `OLLAMA_BASE_URL` from the environment; if unset, uses this default. An optional `--ollama-url` flag overrides both.

**Rationale**: `http://localhost:11434` is Ollama's standard default port and works on the host workstation where the native ROCm Ollama runs. The devcontainer's `docker-compose.yml` sets `OLLAMA_BASE_URL=http://host.docker.internal:11434` as an environment variable, so container runs already override the default. The CLI does not need to detect which environment it is in — the environment variable handles it.

**Alternatives considered**:
- Default to `http://host.docker.internal:11434`: Rejected — only works inside Docker; breaks on host.
- No default (require explicit config): Rejected — FR-032 says "with a documented default."

---

## R-007: Processing Timeout

**Decision**: Accept an optional `--timeout` argument (integer seconds). Default: `300` (5 minutes). If the pipeline stages exceed this wall-clock time, the CLI exits with `PROCESSING_FAILURE` at the stage that was running.

**Rationale**: FR-038 says a timeout "MAY be implemented for robustness" but "MUST NOT be positioned as a quality or SLA control" and "MUST NOT be required to tune for the 20-document corpus." A 5-minute default is generous for one invoice against a local Ollama endpoint. The harness can override with `--timeout 600` if needed. The timeout is not a release gate — it is a safety net against hung model calls.

**Alternatives considered**:
- No timeout: Rejected — a hung Ollama call would block the harness indefinitely with no feedback.
- Per-stage timeouts: Rejected — premature; FR-038 says no SLA knobs at stage 1. A single overall timeout is simpler and sufficient.

---

## R-008: Argument That Is Not in the Spec — `--ollama-url`

**Decision**: Include `--ollama-url` as an optional argument that overrides `OLLAMA_BASE_URL`. It is part of the frozen argument set.

**Rationale**: FR-032 says "a CLI flag MAY be provided as an override but MUST NOT be the only way to configure the endpoint." The environment variable is the primary path; the flag is a convenience for one-off runs (`--ollama-url http://other-host:11434`). Including it in the frozen set now avoids a contract amendment later.

**Alternatives considered**:
- Omit entirely (env-var only): Viable but less ergonomic for developers testing against different Ollama instances.
- `--ollama-base-url` (longer name): Rejected — verbosity adds nothing; `--ollama-url` is clear enough.

---

## R-009: Subcommand vs. Bare Command

**Decision**: Use a subcommand: `python -m ledgerlinc_ocr.pipeline run [ARGS]`. The `run` subcommand processes one document. The top-level command without a subcommand prints help.

**Rationale**: The validator already uses subcommands (`validate artifact`, `validate folder`, `show contract-set`). Using `run` as a subcommand keeps the CLI extensible (e.g., future `python -m ledgerlinc_ocr.pipeline info` to dump installed contract versions) without changing the primary invocation. The spec's forward-compatibility requirement (FR-035) is served by having `run` own the argument surface so new subcommands don't collide.

**Alternatives considered**:
- No subcommand (bare `python -m ledgerlinc_ocr.pipeline --input ...`): Viable but closes the extensibility path. Adding a second mode later would require a breaking change or ambiguous argument parsing.

---

## R-010: Test Strategy for the CLI Contract

**Decision**: Tests live in `tests/pipeline_tests/`. They test the CLI's external contract — argument parsing, path resolution, exit codes, stdout/stderr shapes, artifact placement — by invoking `cli.main(argv)` in-process (same pattern as `tests/contract_tests/test_cli_artifact.py`). No model inference is needed: the orchestration runner accepts pluggable stage callables, and tests inject stubs that write pre-canned artifacts.

**Rationale**: The CLI contract is the deliverable, not model inference. Tests must verify the contract holds regardless of what the pipeline stages do internally. Stubbing stages at the runner level keeps tests fast, deterministic, and free of Ollama. The existing validator tests provide the pattern: they invoke `main(argv)` and check exit codes and output.

**Alternatives considered**:
- Subprocess tests (`subprocess.run`): Rejected — slower, harder to capture stderr/stdout, and the validator tests already prove the in-process pattern works.
- End-to-end with live Ollama: Out of scope for this feature — that is integration testing for the preprocessing/extraction features.

---

## R-011: `pyproject.toml` Test Configuration

**Decision**: Add `tests/pipeline_tests` to `testpaths` alongside the existing `tests/contract_tests`. Add a `console_scripts` entry `ledgerlinc-pipeline = "ledgerlinc_ocr.pipeline.cli:main"`.

**Rationale**: `pytest` is already configured with `testpaths = ["tests/contract_tests"]`. Adding the new directory lets `pytest` discover both test suites. The console script provides the convenience alias without changing the `python -m` contract.

**Alternatives considered**:
- Separate pytest config for pipeline tests: Rejected — one `pytest` invocation should run all tests.

---

## R-012: Default Values for `pipeline_version` and `policy_version`

**Decision**: `pipeline_version` defaults to `ledgerlinc_ocr.__version__` (the package version from `pyproject.toml`). `policy_version` defaults to the string `"stage1-baseline-v0"` during stage 1; it becomes a meaningful semver when real routing policy lands.

**Rationale**: Package version is the natural source for pipeline identity — it already tracks build-level changes and is the value a harness operator can correlate with a git SHA. A policy version only makes sense once there is a routing policy to version; using a stable placeholder string preserves the artifact schema slot without overpromising semantics the pipeline does not yet encode.

**Alternatives considered**:
- Hardcoded `"0.0.0"` for both: Rejected — discards the package-version signal that is already available and conveys nothing to the operator.
- Omit `policy_version` until real routing is implemented: Rejected — the v1.0.0 schema requires the field, so omitting it would produce schema-invalid artifacts.
- Separate semver for policy from day one (e.g. `"0.1.0"`): Rejected — semver on a stub conveys false precision; the placeholder string makes "this is a baseline, not a real policy" legible.
