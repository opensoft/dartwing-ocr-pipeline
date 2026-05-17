# Implementation Plan: Pipeline Harness Integration

**Branch**: `012-pipeline-harness-integration` | **Date**: 2026-05-05 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/012-pipeline-harness-integration/spec.md`

## Summary

Add a harness-owned pipeline preparation step to the evaluator CLI. When requested, document and corpus evaluation commands will invoke the 011 top-level pipeline controller first, using stub-safe deterministic stage profiles by default and explicit runtime profiles when selected by the user. The evaluator remains responsible for scoring and reports; the pipeline remains responsible for stage execution, profile lifecycle, routing, and artifact generation.

The implementation will use the pipeline CLI as a subprocess rather than importing pipeline modules into the evaluator package. This preserves the existing harness/pipeline runtime boundary and keeps the import-barrier test meaningful.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: Python stdlib (`argparse`, `json`, `pathlib`, `subprocess`, `sys`, `tempfile`, `dataclasses`); existing `pydantic`/`jsonschema` evaluator dependencies remain unchanged
**Storage**: Filesystem-only JSON artifacts in per-document folders and corpus roots
**Testing**: `pytest` through the existing evaluator and integration test suites
**Target Platform**: Local Linux/WSL/devcontainer development environments that can run the repository CLI modules
**Project Type**: Python CLI/library package
**Performance Goals**: Stub-safe harness pipeline tests avoid live OCR/model startup; corpus preparation uses one warm pipeline invocation through `--documents-file` instead of spawning one pipeline process per document
**Constraints**: No artifact schema changes; no new required benchmark artifact; evaluator package must not import `dartwing_ocr.pipeline` or `dartwing_ocr.preprocessing`; default automated path must not require network, GPU, Ollama, PaddleOCR, or model weights
**Scale/Scope**: Stage 1 vendor-identity corpus, currently 20 per-document invoice folders with `source.pdf` and `expected.json`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. One Repo, Clear Runtime Boundaries**: PASS. The evaluator invokes the pipeline CLI as an external command and does not import pipeline modules; pipeline stage ownership remains unchanged.
- **II. Evidence-First, Schema-First Design**: PASS. The feature consumes the existing four canonical pipeline artifacts and existing evaluation outputs without schema changes.
- **III. Deterministic Control Over Model Output**: PASS. Routing and scoring remain deterministic code in their existing layers.
- **IV. Provenance and Review Safety**: PASS. The evaluator continues to judge `company_name.present`, `company_name.inferred`, and review flags from the final payload contract.
- **V. Benchmarkable and Reproducible Delivery**: PASS. The feature improves one-document and corpus reproducibility and surfaces existing warm-run timing metadata without making timing a release gate.
- **Stage 1 Scope Constraints**: PASS. The feature remains PDF/vendor-identity only and does not add remote cloud execution, line items, or latency gates.
- **OpenSpec Governance**: PASS. This work implements the already-documented `prd-test-harness.md` delivery order and the merged 011 controller boundary; it does not change artifact schemas, runtime ownership, or deterministic policy.

## Project Structure

### Documentation (this feature)

```text
specs/012-pipeline-harness-integration/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── evaluator-cli-contract.md
└── tasks.md
```

### Source Code (repository root)

```text
src/dartwing_ocr/evaluator/
├── cli.py
├── corpus.py
└── pipeline_invocation.py

tests/evaluator_tests/
├── test_cli.py
└── test_pipeline_invocation.py

tests/integration/
└── test_evaluator_pipeline_harness.py
```

**Structure Decision**: Keep the pipeline invocation adapter inside the evaluator package because it is harness behavior, but implement it only with subprocess calls to the public pipeline CLI. Extend `evaluator.corpus` only as needed to evaluate a caller-supplied subset after a continue-through-failures preparation run.

## Complexity Tracking

No constitution violations are introduced.
