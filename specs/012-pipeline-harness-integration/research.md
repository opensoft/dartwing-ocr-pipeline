# Research: Pipeline Harness Integration

## Decision 1: Invoke Pipeline As A Subprocess

**Decision**: The evaluator will invoke `python -m dartwing_ocr.pipeline run` with `subprocess.run` rather than importing pipeline modules.

**Rationale**: The existing evaluator contract and import-barrier test enforce harness/pipeline separation. A subprocess call keeps the boundary explicit while still exercising the public pipeline controller exactly as an operator would.

**Alternatives considered**:

- Import `dartwing_ocr.pipeline.cli.main` in process: rejected because it violates the current evaluator import barrier and weakens runtime separation.
- Duplicate stage orchestration in the harness: rejected because the pipeline owns stage execution and profile lifecycle.

## Decision 2: Default Harness Pipeline Runs Use All-Stub Profiles

**Decision**: When a user enables pipeline preparation but does not provide a stack preset or any per-stage profile, the harness passes `stub` for all four stage profiles.

**Rationale**: The pipeline controller defaults to real full-workstation profiles after 011. That is correct for operator runs but unsuitable for evaluator unit and integration tests, which must not require OCR/model runtime dependencies. Explicit stack presets or per-stage profile flags opt into non-stub behavior.

**Alternatives considered**:

- Use pipeline defaults in every harness run: rejected because automated tests would require live OCR/model dependencies.
- Add a new pipeline stack preset for harness tests: rejected because all-stub profile selection already exists and does not require a pipeline contract amendment.

## Decision 3: Corpus Preparation Uses The Warm `--documents-file` Pipeline Mode

**Decision**: Corpus preparation writes a temporary documents file containing selected document folders and invokes the pipeline once with `--documents-file`.

**Rationale**: 011 introduced warm corpus execution specifically to avoid initializing expensive profiles once per document. The harness should use that path directly rather than spawning one pipeline process per folder.

**Alternatives considered**:

- Invoke the single-document pipeline command per folder: rejected because it would bypass the warm profile lifecycle and recreate the slow testing loop 011 was designed to avoid.
- Add a new evaluator-side warm worker: rejected because profile lifecycle belongs to the pipeline.

## Decision 4: Continue-Through-Failures Evaluates Only Prepared Documents

**Decision**: When corpus preparation is run with continue-through-failures, the harness parses the pipeline run summary and evaluates only documents that reported successful preparation. Failed documents are reported to the operator but are not scored.

**Rationale**: The current evaluation schema is for scored documents, not preparation failures. Scoring a document without a valid final payload would be misleading, and adding a new required evaluation artifact is out of scope.

**Alternatives considered**:

- Abort the entire corpus on any preparation failure: rejected because the spec requires a continue mode.
- Insert failed preparation records into `evaluation_run_summary.json`: rejected because it would change the evaluation schema.
- Write a new persistent preparation summary artifact: rejected for this feature because timing and preparation metadata should remain informational and pipeline-owned unless a later contract adds a harness report.

## Decision 5: Preparation Metadata Is Operator-Facing, Not A New Schema

**Decision**: The harness will surface parsed pipeline preparation counts and warm timing metadata through CLI output paths that do not mutate the evaluation schemas.

**Rationale**: The pipeline already emits a run-summary JSON line for warm corpus runs. The harness can parse it for control flow and report the key counts to the operator without creating another persisted contract.

**Alternatives considered**:

- Persist a harness-specific benchmark JSON artifact: rejected because the feature explicitly excludes new schema artifacts and benchmark ownership changes.
- Ignore warm timing metadata: rejected because the feature goal includes visibility into the 011 speedup surface.

## Decision 6: Evaluation Subset Support Stays Internal

**Decision**: `evaluate_corpus` may accept an internal optional folder subset so the CLI can aggregate only successfully prepared documents after a continue-mode pipeline run. The public CLI default remains unchanged.

**Rationale**: Existing users of `evaluate_corpus(root)` must still discover all valid document folders. The harness pipeline path needs a precise subset after preparation failures.

**Alternatives considered**:

- Copy successful documents into a temporary corpus root: rejected because it is slower and risks confusing artifact paths.
- Add a user-facing evaluator corpus include-file contract now: rejected because it is not needed for the MVP and would expand the CLI surface beyond the requested harness integration.
