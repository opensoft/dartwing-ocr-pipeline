# PRD: Stage 1 Test Harness

## Purpose

This PRD defines the product requirements for the stage 1 LedgerLinc OCR test harness.

This document is specifically about the harness that drives the pipeline, stores labeled invoice cases, evaluates outputs, and reports quality. It is not the PRD for the model pipeline itself.

## Product Boundary

This PRD covers:

- the stage 1 test corpus
- expected-truth storage
- per-document test folder layout
- pipeline invocation for evaluation
- output comparison
- scoring and reporting
- optional preservation of per-voter outputs when ensemble mode is enabled

This PRD does not cover:

- OCR or model extraction internals
- routing logic internals
- PDF preprocessing internals
- downstream accounting or CRM integrations

Those belong to `prd-model-pipeline.md`.

## Problem Statement

LedgerLinc needs a repeatable way to evaluate whether the stage 1 OCR/model pipeline actually works on real-world invoices.

Without a structured harness and labeled truth set, the team cannot distinguish plausible output from correct output, cannot measure regressions, and cannot compare prompt or pipeline changes with confidence.

## Stage 1 Goal

Build a repeatable test harness that:

- stores a curated PDF corpus
- stores expected truth per document
- runs the pipeline on those documents
- compares pipeline output to labeled truth
- produces per-field, per-document, and per-run metrics
- remains compatible with both single-voter and future three-voter pipeline runs

## Users and Stakeholders

Primary users:

- internal developers iterating on the pipeline
- internal reviewers validating extraction quality

Stakeholders:

- LedgerLinc engineering
- operations stakeholders who need confidence before adoption
- future QA or evaluation owners

## Stage 1 Scope

Included:

- a 20-document real-world PDF corpus
- per-document folders
- labeled expected truth per document
- notes for human reviewers
- pipeline invocation for one or many documents
- evaluator outputs
- run summary reporting

Explicitly out of scope:

- UI test management
- cloud benchmark infrastructure
- formal ML experiment tracking systems
- production monitoring
- latency benchmarking as a stage 1 requirement

## Dataset Requirements

The stage 1 corpus must contain 20 PDF invoices:

- 5 easy
- 5 medium
- 5 hard
- 5 missing company name

Each document must have its own folder.

Required per-document files:

- `source.pdf`
- `expected.json`
- `notes.md`

Generated per-document artifacts:

- `preprocess_output.json`
- `edge_extraction_output.json`
- `routing_decision.json`
- `final_structured_payload.json`
- `evaluation_document.json`

Optional future artifacts:

- per-voter raw outputs
- consensus-specific artifacts

## Labeling Requirements

Each `expected.json` must contain:

- `document_id`
- `difficulty`
- `challenge_tags`
- `expected_review`
- `expected_vendor_candidate`
- optional notes

The expected truth must represent the labeled answer the system is judged against. It must not include predicted values, confidence values, or evaluation outcomes.

## Evaluation Requirements

The harness must:

1. run the pipeline against one document or the full corpus
2. compare `final_structured_payload.json` against `expected.json`
3. score fields individually
4. score documents overall
5. produce run-level summaries

When ensemble mode is enabled, the harness should also be able to preserve per-voter outputs for debugging and analysis.

The evaluator must score at minimum:

- company name value
- company name present flag
- company name inferred flag
- decomposed address fields
- typed tax IDs
- website
- phone
- email
- manual review required
- review reason

## Scoring Requirements

The harness must support:

- normalized field comparison
- weighted document scoring
- hard pass/fail gates for vendor identity and review routing
- difficulty-bucket summaries
- field-type summaries

When ensemble mode is enabled, the harness should also support:

- agreement metrics
- disagreement metrics
- per-field consensus analysis

The current scoring baseline is documented in `scoring.md`.

## Reporting Requirements

The harness must emit:

- `evaluation_document.json` per document
- `evaluation_run_summary.json` for the entire run

Run reporting must include at minimum:

- overall weighted field accuracy
- overall document pass rate
- vendor identity pass rate
- review routing pass rate
- breakdown by difficulty
- breakdown by field type

When ensemble mode is enabled, run reporting should also be able to include:

- unanimous rate
- 2-of-3 majority rate
- split-decision rate

## Success Criteria

The stage 1 harness is successful when:

1. a developer can run the harness on a single document or the full suite
2. the harness produces stable machine-readable evaluation output
3. the harness makes regressions visible at both field and document level
4. missing-name documents are evaluated correctly as review-required cases

## Acceptance Criteria

The test harness is acceptable for stage 1 when:

1. the 20-document corpus structure exists
2. each document folder can hold source, truth, outputs, and notes
3. the harness can invoke the pipeline for one document
4. the harness can evaluate one document against expected truth
5. the harness can aggregate results across all test documents
6. the harness can report field-level and overall quality

## Runtime Boundary

For stage 1, the harness is expected to run from the development bench environment and call the repo pipeline code plus host Ollama.

The harness is not itself the model runtime.

## Dependency Map

### Hard Dependencies

These items block downstream harness work:

1. `expected.json` contract
   - required before real labeling can proceed consistently
2. `final_structured_payload` contract
   - required before evaluator logic can be finalized
3. pipeline invocation contract
   - required before one-document or full-run orchestration
4. scoring rules
   - required before document pass/fail and run summaries
5. `evaluation_document.json` contract
   - required before run-level aggregation

### Orthogonal Or Low-Coupled Work

These can progress largely independently once the truth schema is stable:

- source PDF collection
- per-document notes writing
- challenge-tag curation
- benchmark reporting for CPU versus GPU lanes
- future ensemble-specific reporting extensions

## Recommended Delivery Order

The recommended implementation order for the harness is:

1. freeze `expected.json` and per-document folder conventions
2. create the corpus root and document folder templates
3. implement one-document pipeline invocation
4. implement `evaluation_document.json`
5. implement `evaluation_run_summary.json`
6. add full-suite orchestration
7. add rerun-only-failed and benchmark comparison helpers

This order keeps the harness grounded in stable truth and a working pipeline boundary before adding bulk-run features.

## Parallelizable Work

After the truth schema and pipeline invocation contract are stable, the following work can happen in parallel:

### Workstream A: Corpus And Labeling

- create the 20 per-document folders
- add `source.pdf`
- add `expected.json`
- add `notes.md`

This can proceed independently from most pipeline internals once the truth schema is frozen.

### Workstream B: One-Document Runner

- invoke the pipeline CLI
- capture generated artifacts
- store outputs back into the document folder

This depends on the pipeline entry point but not on full-suite orchestration.

### Workstream C: Evaluation And Reporting

- implement per-field comparison
- implement document pass/fail
- implement run summaries

This depends on stable output contracts, but not on the entire corpus being labeled first.

### Workstream D: Benchmark And Comparison Support

- compare host GPU versus container CPU runs
- capture run metadata
- summarize relative runtime behavior

This can start once the one-document runner and evaluation output format exist.

## Assumptions

The following assumptions are currently baked into this draft:

- test inputs are PDFs only
- the corpus is stored in per-document folders for human review
- expected truth is hand-labeled
- latency is not a stage 1 pass criterion
- the evaluator compares against `final_structured_payload.json`
- the long-term pipeline architecture will include multiple model voters and deterministic consensus

## Risks

1. Label quality may become the bottleneck if expected truth is inconsistent.
2. Too much scoring complexity too early may slow pipeline iteration.
3. Missing-name cases may require tighter labeling guidance than straightforward explicit-name cases.
4. Real-world invoices may expose additional difficulty categories not captured in the initial 20-document set.

## Open Questions

1. Should the harness support incremental re-runs of only failed documents in stage 1?
2. Should challenge tags be constrained to a fixed vocabulary in code, or just documented and reviewed manually at first?
3. Should run summaries include confidence calibration analysis in stage 1, or should that remain a secondary report?
4. When the three-vote ensemble is enabled, should the harness persist all raw voter outputs by default or only on failure?
