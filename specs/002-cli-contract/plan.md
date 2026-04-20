# Implementation Plan: Stage 1 One-Document CLI Contract

**Branch**: `002-cli-contract` | **Date**: 2026-04-20 | **Spec**: [`specs/002-cli-contract/spec.md`](spec.md)
**Input**: Feature specification from `/specs/002-cli-contract/spec.md`

## Summary

Freeze the stage 1 one-document CLI contract: a single command that takes one PDF and a destination folder, writes exactly four JSON artifacts (`preprocess_output.json`, `edge_extraction_output.json`, `routing_decision.json`, `final_structured_payload.json`) into that folder, exits with a stable code from a documented vocabulary, emits a JSON summary to stdout on success and a structured failure record to stderr on failure. The CLI lives in the pipeline package alongside the existing validator and reuses the frozen v1.0.0 contract set for post-hoc schema validation. No model inference, no preprocessing logic, no extraction — only the command surface, argument parsing, path resolution, exit codes, and the orchestration skeleton that later pipeline stages will plug into.

## Technical Context

**Language/Version**: Python 3.12 (matches devcontainer and existing package)
**Primary Dependencies**: `jsonschema >=4.22` (already installed), `pydantic >=2.7` (already installed), `python-magic` or stdlib `struct` for PDF magic detection (see research.md)
**Storage**: Filesystem only — JSON artifacts on disk, no database
**Testing**: `pytest >=8.2` (already configured under `tests/contract_tests/`)
**Target Platform**: Linux (WSL2 / devcontainer), callable from host shell
**Project Type**: CLI (single-command pipeline entry point)
**Performance Goals**: N/A for contract layer; FR-038 explicitly defers latency SLA
**Constraints**: No network beyond configured Ollama endpoint; no cloud; no image inputs; PDF-only stage 1
**Scale/Scope**: One document per invocation; 20-document corpus exercised by external harness

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Gate | Status | Evidence |
|---|------|--------|----------|
| I | One repo, clear runtime boundaries | **PASS** | CLI lives in pipeline layer only (FR-031). Does not embed harness, evaluator, or labeling tooling. Host Ollama over HTTP for inference (FR-032). |
| II | Evidence-first, schema-first design | **PASS** | All four artifacts validated against frozen v1.0.0 contract set (FR-030). CLI adapts to contracts, not reverse. New fields require amendment (FR-026). |
| III | Deterministic control over model output | **PASS** | CLI does not implement consensus, routing policy, or spam gates — those are downstream pipeline stages. Exit codes and path resolution are deterministic code. |
| IV | Provenance and review safety | **PASS** | CLI stamps `document_id` consistently (FR-028). Provenance triad enforcement is downstream of CLI contract but validated post-hoc via v1.0.0 schemas. |
| V | Benchmarkable and reproducible delivery | **PASS** | CLI supports one-document execution (User Story 1) and corpus iteration (User Story 2). Deterministic output paths enable reproducible runs. |
| QG-1 | Pipeline/harness separation | **PASS** | FR-031 explicitly prohibits embedding harness. FR-013 forbids writing `evaluation_document.json`. |
| QG-2 | Output contract updates | **N/A** | CLI does not change artifact schemas; it writes them as-is from v1.0.0. |
| QG-3 | Architecture/runtime doc updates | **PASS** | Ollama endpoint config (FR-032) aligns with `ollama-runtime.md`. No new runtime introduced. |
| QG-4 | Verifiable local execution path | **PASS** | SC-001 requires developer can run one PDF within 10 minutes using only spec + `--help`. |
| QG-5 | Container/runtime distinction | **N/A** | CLI does not change container topology; runs inside existing devcontainer. |
| QG-6 | Evaluation against labeled truth | **N/A** | CLI does not implement evaluation. Harness consumes CLI output. |

No violations. Proceeding to Phase 0.

### Post-Design Re-Check

All gates remain **PASS** after Phase 1 design. Specific confirmations:

- **Gate I** (runtime boundaries): The pipeline module (`src/ledgerlinc_ocr/pipeline/`) is a sibling to `validator/`, not embedded in it. The runner stubs stages without collapsing harness or evaluator logic into the pipeline. Ollama is accessed over HTTP at a configurable URL.
- **Gate II** (schema-first): All four artifacts validated post-hoc against v1.0.0 schemas via the existing validator module. No new artifact fields introduced. Exit code 30 catches schema drift.
- **Gate III** (deterministic control): Exit codes, path resolution, and overwrite guards are deterministic code. No model output influences CLI behavior — the CLI is a shell around pluggable stages.
- **Gate V** (reproducible): Deterministic path resolution + stable exit codes + `--overwrite` flag enable reproducible corpus runs. The harness loop in `quickstart.md` demonstrates this.

## Project Structure

### Documentation (this feature)

```text
specs/002-cli-contract/
├── plan.md              # This file
├── research.md          # Phase 0: design decisions
├── data-model.md        # Phase 1: entities & relationships
├── quickstart.md        # Phase 1: post-ship usage guide
└── contracts/
    ├── cli-contract.md          # Frozen CLI argument surface
    ├── exit-codes.md            # Exit code vocabulary
    ├── stdout-summary.md        # Stdout JSON line schema (success)
    └── stderr-failure-record.md # Stderr JSON line schema (failure)
```

### Source Code (repository root)

```text
src/ledgerlinc_ocr/
├── __init__.py                          # Package root (existing)
├── pipeline/                            # NEW — pipeline CLI module
│   ├── __init__.py
│   ├── __main__.py                      # Entry: python -m ledgerlinc_ocr.pipeline
│   ├── cli.py                           # argparse CLI: argument parsing, dispatch
│   ├── exit_codes.py                    # Exit code enum + structured failure record
│   ├── path_resolution.py               # Deterministic input/output/document-id resolution
│   ├── runner.py                        # Orchestration skeleton: validate → stub stages → validate output
│   └── pdf_check.py                     # PDF magic byte verification (FR-017)
└── validator/                           # Existing — reused for post-hoc schema validation
    ├── __init__.py
    ├── __main__.py
    ├── cli.py
    ├── artifact.py
    ├── folder.py
    ├── corpus.py
    ├── cross_artifact.py
    ├── loader.py
    ├── report.py
    └── version.py

tests/
├── contract_tests/                      # Existing — validator tests
│   └── ... (15 existing test files)
└── pipeline_tests/                      # NEW — CLI contract tests
    ├── __init__.py
    ├── conftest.py                      # Fixtures: tmp dirs, sample PDFs, pre-written artifacts
    ├── test_cli_arguments.py            # Argument parsing, mutual exclusion, unknown args
    ├── test_path_resolution.py          # Destination folder, document-id derivation
    ├── test_exit_codes.py               # Each failure category → distinct code
    ├── test_input_validation.py         # Missing PDF, non-PDF, missing dest folder
    ├── test_overwrite_guard.py          # --overwrite behavior
    ├── test_stdout_summary.py           # Success JSON line shape
    ├── test_stderr_failure_record.py    # Failure JSON line shape
    └── test_artifact_placement.py       # Four files in correct folder, no strays
```

**Structure Decision**: The pipeline CLI lives at `src/ledgerlinc_ocr/pipeline/` — a sibling to the existing `validator/` module. Both share the `ledgerlinc_ocr` package namespace. The CLI is invoked via `python -m ledgerlinc_ocr.pipeline`. A `console_scripts` entry point (`ledgerlinc-pipeline`) will be added to `pyproject.toml` for convenience but the `python -m` form is the contract-stable surface the harness targets.

## Complexity Tracking

No constitution violations to justify — all gates pass.
