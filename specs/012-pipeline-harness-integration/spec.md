# Feature Specification: Pipeline Harness Integration

**Feature Branch**: `012-pipeline-harness-integration`  
**Created**: 2026-05-05  
**Status**: Draft  
**Input**: User description: "Build the stage 1 harness-controller integration so the evaluation harness can invoke the merged top-level pipeline controller for one document and corpus runs before evaluating outputs. The harness must support explicit stage profiles and stack presets, default to stub-safe deterministic profiles for tests unless real profiles are requested, preserve the four canonical pipeline artifacts and existing evaluator contracts, evaluate per-document and corpus outputs, and capture available warm-run timing metadata from the pipeline run summary without adding new schema artifacts or moving benchmark ownership into the pipeline."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run And Evaluate One Document (Priority: P1)

An internal developer can point the stage 1 harness at one labeled invoice folder, ask it to run the pipeline first, and receive the normal document evaluation output without manually chaining separate commands.

**Why this priority**: One-document harness invocation is the smallest useful vertical slice and is the fastest way to debug a specific invoice regression.

**Independent Test**: Can be fully tested with a single corpus document folder that contains `source.pdf` and `expected.json`; the run produces the four canonical pipeline artifacts and then writes `evaluation_document.json`.

**Acceptance Scenarios**:

1. **Given** a labeled document folder with `source.pdf` and `expected.json`, **When** the harness is run with pipeline invocation enabled, **Then** it produces `preprocess_output.json`, `edge_extraction_output.json`, `routing_decision.json`, `final_structured_payload.json`, and `evaluation_document.json` in the document folder.
2. **Given** a document folder whose pipeline run fails before a final payload is available, **When** the harness is run with pipeline invocation enabled, **Then** the harness reports a hard evaluation-preparation failure and does not publish a misleading document score.

---

### User Story 2 - Run And Evaluate A Corpus (Priority: P2)

An internal developer can point the harness at the stage 1 corpus, ask it to run the pipeline across the corpus, and receive the existing run summary report for all discovered documents.

**Why this priority**: Corpus-level invocation is needed to measure regressions and make pipeline quality visible after the 011 controller merge.

**Independent Test**: Can be tested with a small multi-document corpus using deterministic profiles; the run produces or refreshes document evaluations and writes the normal corpus summary artifacts.

**Acceptance Scenarios**:

1. **Given** a corpus root containing multiple labeled document folders, **When** the harness is run with pipeline invocation enabled for the corpus, **Then** every selected folder is processed through the pipeline before aggregation and the run writes `evaluation_run_summary.json`.
2. **Given** one document in the corpus cannot be processed by the pipeline, **When** the harness is configured to continue through failures, **Then** the run summary identifies the failed document and still evaluates documents whose required artifacts are present.

---

### User Story 3 - Select Runtime Profiles For Harness Runs (Priority: P3)

An internal developer can choose the pipeline stack or per-stage profiles used by the harness run while keeping deterministic stub-safe defaults available for tests.

**Why this priority**: The harness must compare real profile choices over time, but automated tests must remain fast and must not require live OCR or model endpoints.

**Independent Test**: Can be tested by running the same document with explicit deterministic profiles and by verifying unsupported profile combinations fail before evaluation begins.

**Acceptance Scenarios**:

1. **Given** no real runtime stack is requested, **When** automated harness tests invoke the pipeline path, **Then** deterministic stage profiles are used and no live OCR, model runtime, network, or GPU dependency is required.
2. **Given** an explicit supported stack preset or per-stage profile set, **When** the harness invokes the pipeline, **Then** the selected profiles are passed through and are visible in the generated pipeline artifacts or run metadata.
3. **Given** an unsupported profile or stack combination, **When** the harness is run, **Then** the command fails before writing evaluation outputs for that selection.

---

### User Story 4 - Surface Warm Corpus Timing (Priority: P4)

An internal developer can see available warm-run timing metadata from corpus pipeline execution alongside the evaluation workflow, so the team can compare whether the 011 warm path speeds up repeated test runs.

**Why this priority**: Timing visibility is useful immediately after 011, but it must remain secondary to correctness scoring and must not create a new benchmark artifact contract.

**Independent Test**: Can be tested with a corpus pipeline run that emits run-level timing metadata; the harness records or reports the available metadata without changing the evaluation schema.

**Acceptance Scenarios**:

1. **Given** the pipeline emits warm-run metadata during corpus processing, **When** the harness completes evaluation, **Then** the user can identify one-time initialization time separately from per-document processing time using the preserved pipeline run metadata.
2. **Given** the pipeline does not emit warm-run metadata for a selected run, **When** the harness completes evaluation, **Then** the evaluation still succeeds and clearly omits timing comparison rather than fabricating benchmark data.

### Edge Cases

- The document folder is missing `source.pdf`, `expected.json`, or one of the four pipeline artifacts needed for evaluation.
- Existing canonical pipeline artifacts are present and the user has not allowed overwrite.
- A corpus contains folders that are not valid document folders.
- Pipeline invocation succeeds for some corpus documents and fails for others.
- The user requests both a stack preset and explicit per-stage overrides.
- The user requests real runtime profiles in an environment that lacks the needed local runtime endpoint.
- Warm-run timing metadata is absent, partial, or emitted only for failed documents.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The harness MUST provide a user-visible option to run the stage 1 pipeline before evaluating a single document folder.
- **FR-002**: The harness MUST provide a user-visible option to run the stage 1 pipeline before evaluating a corpus root.
- **FR-003**: The harness MUST preserve the existing evaluation outputs and their filenames: `evaluation_document.json` for each document and `evaluation_run_summary.json` for corpus runs.
- **FR-004**: The harness MUST preserve the four canonical pipeline artifact filenames in each selected document folder.
- **FR-005**: The harness MUST support deterministic, stub-safe pipeline execution for automated tests when no real runtime stack is requested.
- **FR-006**: The harness MUST allow callers to select a supported stack preset for pipeline execution.
- **FR-007**: The harness MUST allow callers to select supported per-stage profiles for pipeline execution.
- **FR-008**: Explicit per-stage profile selections MUST take precedence over stack preset defaults where the underlying pipeline contract supports that precedence.
- **FR-009**: The harness MUST fail before evaluation when pipeline profile validation fails.
- **FR-010**: The harness MUST fail before publishing evaluation results for a document when the required pipeline artifact set is missing after a requested pipeline run.
- **FR-011**: Corpus pipeline invocation MUST support a continue-through-failures mode that evaluates documents whose required artifacts are present and reports documents that could not be prepared.
- **FR-012**: Corpus pipeline invocation MUST support a fail-fast mode that stops the run when a selected document cannot be prepared for evaluation.
- **FR-013**: The harness MUST surface available pipeline run metadata that separates warm initialization time from per-document processing time when the pipeline provides it.
- **FR-014**: The harness MUST NOT invent timing values or benchmark results when the pipeline does not provide them.
- **FR-015**: The harness MUST NOT add a new required evaluation schema artifact for timing metadata in this feature.
- **FR-016**: The harness MUST keep scoring, pass/fail decisions, aggregation, and report ownership in the evaluator/harness layer.
- **FR-017**: The harness MUST NOT move OCR, model extraction, routing, final payload assembly, or profile lifecycle ownership out of the pipeline layer.
- **FR-018**: The harness MUST produce clear operator-facing errors that distinguish pipeline invocation failures from evaluation comparison failures.
- **FR-019**: The harness MUST support refreshing generated artifacts for a document or corpus when requested by the user.
- **FR-020**: The harness MUST remain compatible with single-voter stage 1 outputs and future ensemble-ready metadata already allowed by the artifact contracts.

### Key Entities *(include if feature involves data)*

- **Document Folder**: A per-invoice folder containing `source.pdf`, `expected.json`, generated pipeline artifacts, and generated evaluation output.
- **Harness Pipeline Run Request**: The user's selected scope, overwrite preference, failure policy, stack preset, per-stage profiles, and runtime endpoint choices for preparing documents before evaluation.
- **Pipeline Artifact Set**: The four canonical JSON files produced by the stage 1 pipeline and consumed by the evaluator.
- **Document Evaluation**: The existing per-document comparison result written as `evaluation_document.json`.
- **Corpus Evaluation Summary**: The existing aggregate report written as `evaluation_run_summary.json`.
- **Pipeline Timing Metadata**: Optional metadata emitted by the pipeline for warm corpus execution and document processing phases.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can run one labeled document through pipeline preparation and evaluation with a single harness command.
- **SC-002**: A developer can run a corpus through pipeline preparation and evaluation with a single harness command.
- **SC-003**: Automated tests for the harness pipeline path complete without live OCR, model runtime, network, or GPU dependencies.
- **SC-004**: A failed pipeline preparation step prevents a misleading evaluation score for that document every time.
- **SC-005**: Existing evaluator commands without pipeline invocation continue to behave as before.
- **SC-006**: Corpus output identifies the number of documents prepared, evaluated, skipped, and failed.
- **SC-007**: When warm-run timing metadata is available, the user can distinguish one-time initialization time from per-document processing time without opening individual stage logs.

## Assumptions

- The 011 top-level pipeline controller is the authoritative pipeline entrypoint for this feature.
- The evaluator continues to compare `final_structured_payload.json` against `expected.json`.
- Deterministic test runs use stub-compatible profiles unless the user explicitly requests real runtime profiles.
- The stage 1 corpus keeps the existing per-document folder layout.
- Timing visibility is informational in this feature and is not a stage 1 pass/fail quality gate.
- Side-by-side profile benchmarking remains a harness responsibility, but formal benchmark comparison helpers are outside this feature unless already supported by existing pipeline metadata.
