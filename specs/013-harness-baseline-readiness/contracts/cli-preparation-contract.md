# Contract: Evaluator Pipeline Preparation

## Document Preparation

Command shape:

```bash
python -m ledgerlinc_ocr.evaluator document <document-folder> \
  --run-pipeline \
  --pipeline-overwrite
```

Expected behavior:

- The evaluator invokes `python -m ledgerlinc_ocr.pipeline run --document-folder <document-folder>` as a subprocess.
- When no live stack or per-stage profile is requested, the evaluator passes stub profiles for all stages.
- The pipeline derives `document_id` from the full document folder basename.
- A committed folder copy such as `inv_001_easy` produces generated artifacts and `evaluation_document.json` with `document_id == "inv_001_easy"`.
- A mismatch between generated final payload and `expected.json` remains a hard evaluation error.

## Corpus Preparation

Command shape:

```bash
python -m ledgerlinc_ocr.evaluator corpus <corpus-root> \
  --run-pipeline \
  --pipeline-overwrite
```

Expected behavior:

- The evaluator writes a temporary documents file and invokes `python -m ledgerlinc_ocr.pipeline run --documents-file <file>` as a subprocess.
- Every committed corpus folder keeps the full folder-name `document_id` through pipeline preparation and evaluation.
- Per-document preparation failures are summarized through the existing pipeline run summary shape.

## Real Profile Missing Dependency Failure

Command shape:

```bash
python -m ledgerlinc_ocr.evaluator document <document-folder> \
  --run-pipeline \
  --pipeline-overwrite \
  --stack-preset full-workstation
```

Expected behavior when a selected live-stage dependency is missing:

- The command exits non-zero.
- stderr or the formatted preparation error names the missing dependency and affected stage/profile.
- The output must not include a Python traceback for the expected missing-dependency path.
- Stub-safe preparation remains unaffected.
