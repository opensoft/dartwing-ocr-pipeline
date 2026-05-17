# Implementation Plan: Harness Baseline Readiness

**Branch**: `013-harness-baseline-readiness` | **Date**: 2026-05-05 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `/specs/013-harness-baseline-readiness/spec.md`

## Summary

Make the merged evaluator-to-pipeline harness path usable against committed stage 1 corpus folders before adding benchmark helpers. The implementation will make the full corpus folder name (for example `inv_001_easy`) the single authoritative `document_id`, update conflicting documentation/tests, add smoke coverage for evaluator `--run-pipeline` on an unchanged committed document, and convert live-profile dependency import failures into operator-facing preparation failures.

## Technical Context

**Language/Version**: Python 3.12  
**Primary Dependencies**: Python stdlib, `pytest`, existing `jsonschema` validation stack; no new runtime dependency  
**Storage**: Filesystem JSON artifacts only  
**Testing**: `pytest` unit/integration slices plus py-bench CLI smoke checks  
**Target Platform**: Local Linux/WSL development and `py-bench` container validation  
**Project Type**: Python CLI/library pipeline plus evaluator harness  
**Performance Goals**: No new benchmark timing goal; deterministic stub-safe smoke should complete in seconds and avoid live OCR/model initialization  
**Constraints**: Preserve all artifact schemas and filenames; keep evaluator/pipeline boundary as subprocess CLI; stub-safe preparation must not import optional OCR/model dependencies; real-profile failures must not expose raw tracebacks  
**Scale/Scope**: Stage 1 committed corpus under `tests/stage1_vendor_identity/`, one-document smoke plus corpus-compatible ID derivation

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. One Repo, Clear Runtime Boundaries**: PASS. The evaluator continues to invoke `dartwing_ocr.pipeline` through the public CLI subprocess path. The pipeline owns preparation and stage failures; the harness owns evaluation/reporting.
- **II. Evidence-First, Schema-First Design**: PASS. No artifact shape or schema version changes are planned.
- **III. Deterministic Control Over Model Output**: PASS. The feature does not move routing, confidence, or review policy into model output.
- **IV. Provenance and Review Safety**: PASS. Vendor identity provenance semantics are untouched.
- **V. Benchmarkable and Reproducible Delivery**: PASS. The feature restores reproducible evaluation against committed `expected.json` truth files.
- **Quality Gates**: PASS. Evaluation changes preserve comparison against human-labeled truth files; runtime changes will be verified through a concrete local execution path and documented where guidance currently conflicts.

No constitution violations require complexity tracking.

## Project Structure

### Documentation (this feature)

```text
specs/013-harness-baseline-readiness/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── cli-preparation-contract.md
├── checklists/
│   ├── requirements.md
│   └── baseline-readiness.md
└── tasks.md
```

### Source Code (repository root)

```text
src/dartwing_ocr/
├── evaluator/
│   └── pipeline_invocation.py       # harness subprocess boundary and preparation error formatting
├── pipeline/
│   ├── cli.py                       # document-folder CLI derivation path
│   ├── corpus_run.py                # warm corpus document-id derivation/failure labels
│   ├── path_resolution.py           # authoritative folder-name document_id derivation
│   ├── runner.py                    # stage resolution/runtime failure conversion
│   └── stages.py                    # live adapter factory registration/import boundary
└── validator/
    └── folder.py                    # corpus folder/expected.json contract guidance if needed

docs/stage1-vendor-identity/
├── dataset-layout.md
├── labeling-guide.md
└── schemas.md

specs/006-corpus-labeling/
├── spec.md
└── data-model.md

tests/
├── evaluator_tests/test_cli.py
├── integration/test_evaluator_pipeline_harness.py
└── pipeline_tests/
    ├── test_path_resolution.py
    └── test_stage_failure_labels.py
```

**Structure Decision**: Keep the implementation inside the existing pipeline/evaluator packages. Add tests where the behavior already has coverage boundaries instead of creating a new test framework or benchmark harness.

## Phase 0 Research

See [research.md](./research.md).

## Phase 1 Design

See [data-model.md](./data-model.md), [contracts/cli-preparation-contract.md](./contracts/cli-preparation-contract.md), and [quickstart.md](./quickstart.md).

## Post-Design Constitution Check

- **Runtime boundary remains separated**: PASS. Evaluator subprocess invocation is preserved.
- **Schema-first contract remains stable**: PASS. No JSON schema files or artifact filenames change.
- **Deterministic control remains in code**: PASS. The ID rule and missing-dependency classification are deterministic code paths.
- **Reproducible delivery improves**: PASS. The plan adds a committed-corpus smoke and keeps real runtime dependency installation out of this feature.

## Complexity Tracking

No constitution violations or extra architectural complexity.
