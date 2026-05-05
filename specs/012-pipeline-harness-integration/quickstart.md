# Quickstart: Pipeline Harness Integration

## One Document, Stub-Safe Preparation

```bash
python -m ledgerlinc_ocr.evaluator evaluate document \
  tests/stage1_vendor_identity/inv_001_easy \
  --run-pipeline \
  --pipeline-overwrite
```

This runs the pipeline with deterministic all-stub profiles, writes the four canonical pipeline artifacts, then writes `evaluation_document.json`.

## One Document, Explicit Real Stack

```bash
python -m ledgerlinc_ocr.evaluator evaluate document \
  tests/stage1_vendor_identity/inv_001_easy \
  --run-pipeline \
  --pipeline-overwrite \
  --stack-preset full-workstation \
  --ollama-url http://host.docker.internal:11434
```

This opts into the pipeline controller's `full-workstation` stack and then evaluates the produced final payload.

## Corpus, Warm Stub-Safe Preparation

```bash
python -m ledgerlinc_ocr.evaluator evaluate corpus \
  tests/stage1_vendor_identity \
  --run-pipeline \
  --pipeline-overwrite \
  --refresh
```

This discovers corpus folders, invokes the pipeline once in warm `--documents-file` mode using all-stub profiles, then refreshes document evaluations and writes the corpus summary.

## Corpus, Continue Through Preparation Failures

```bash
python -m ledgerlinc_ocr.evaluator evaluate corpus \
  tests/stage1_vendor_identity \
  --run-pipeline \
  --pipeline-overwrite \
  --pipeline-on-failure continue \
  --refresh
```

Documents successfully prepared by the pipeline are evaluated. Preparation failures are printed to stderr and are not scored.

## Corpus, Real Warm Profile

```bash
python -m ledgerlinc_ocr.evaluator evaluate corpus \
  tests/stage1_vendor_identity \
  --run-pipeline \
  --pipeline-overwrite \
  --stack-preset full-workstation \
  --ollama-url http://host.docker.internal:11434 \
  --refresh
```

When the selected pipeline stack emits warm-run timing metadata, the harness prints the available preparation counts and timing summary to stderr while preserving normal evaluation outputs.
