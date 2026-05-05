# CLI Contract: Evaluator Pipeline Preparation

**Feature**: `012-pipeline-harness-integration`  
**Date**: 2026-05-05  
**Status**: additive amendment to the 007 evaluator CLI contract

This contract adds optional pipeline preparation flags to the existing evaluator CLI. Existing evaluator commands without these flags keep their current behavior, stdout shape, output files, and exit codes.

## Document Evaluation

```bash
python -m ledgerlinc_ocr.evaluator evaluate document <folder> \
  [--run-pipeline] \
  [--pipeline-overwrite] \
  [--stack-preset NAME] \
  [--preprocess-profile VALUE] \
  [--extract-profile VALUE] \
  [--routing-profile VALUE] \
  [--final-payload-profile VALUE] \
  [--start-at STAGE] \
  [--stop-after STAGE] \
  [--ollama-url URL] \
  [--ollama-cpu-url URL] \
  [--ollama-jetson-url URL] \
  [--timeout SECONDS] \
  [existing evaluator flags]
```

When `--run-pipeline` is absent, behavior is unchanged.

When `--run-pipeline` is present:

- The evaluator invokes the public pipeline controller before evaluating.
- The input selector passed to the pipeline is `--document-folder <folder>`.
- `--contract-set-version` is passed through to the pipeline.
- `--pipeline-overwrite` maps to pipeline `--overwrite`.
- If no stack preset and no per-stage profile flags are present, the evaluator passes all four stage profiles as `stub`.
- If a stack preset or any per-stage profile flag is present, the evaluator passes the user selections through and lets the pipeline default unspecified stages.
- A non-zero pipeline subprocess exit prevents evaluation and the evaluator exits with hard-error code `3`.

## Corpus Evaluation

```bash
python -m ledgerlinc_ocr.evaluator evaluate corpus <root> \
  [--run-pipeline] \
  [--pipeline-overwrite] \
  [--pipeline-on-failure continue|fail-fast] \
  [--stack-preset NAME] \
  [--preprocess-profile VALUE] \
  [--extract-profile VALUE] \
  [--routing-profile VALUE] \
  [--final-payload-profile VALUE] \
  [--start-at STAGE] \
  [--stop-after STAGE] \
  [--ollama-url URL] \
  [--ollama-cpu-url URL] \
  [--ollama-jetson-url URL] \
  [--timeout SECONDS] \
  [existing evaluator flags]
```

When `--run-pipeline` is absent, behavior is unchanged.

When `--run-pipeline` is present:

- The evaluator discovers document folders using the same corpus folder rules used by aggregation.
- The evaluator writes a temporary documents file and invokes the pipeline once with `--documents-file`.
- `--pipeline-on-failure` maps to pipeline `--on-failure` and defaults to `continue`.
- In fail-fast mode, any non-zero pipeline exit prevents evaluation and the evaluator exits with hard-error code `3`.
- In continue mode, the evaluator parses the pipeline run summary and evaluates only successfully prepared document folders.
- If continue mode prepares zero documents, evaluation does not run and the evaluator exits with hard-error code `3`.
- The normal `evaluation_run_summary.json` and Markdown report still summarize evaluated documents only.
- Preparation failures and warm timing metadata are reported to stderr for the operator; they are not inserted into `evaluation_run_summary.json`.

## Exit Codes

- `0`: pipeline preparation and evaluation completed. Document pass/fail gates are represented in evaluation output, not by process exit.
- `2`: evaluator argument usage error.
- `3`: hard preparation or evaluation error.

The pipeline subprocess may use its own internal exit-code taxonomy, but the evaluator CLI maps preparation failure to the existing evaluator hard-error code `3`.

## Backward Compatibility

- Existing evaluator CLI arguments remain valid.
- Existing stdout behavior remains unchanged when `--run-pipeline` is absent.
- `--run-pipeline` document mode still honors `--json` and `--text` after preparation succeeds.
- Corpus stdout remains the Markdown evaluation report; preparation diagnostics go to stderr.
- The evaluator package must not import pipeline or preprocessing modules.
