# Quickstart: Stage 1 One-Document Pipeline CLI

**Feature**: `002-cli-contract`
**Audience**: Pipeline developers, test harness developers, operators.

This quickstart shows what you can do once the CLI contract feature has shipped. All paths are relative to the repo root.

---

## 1. Install

Inside the devcontainer (or any Python 3.12 environment):

```bash
pip install -e .
```

This installs `ledgerlinc_ocr` with both the validator and the pipeline CLI.

## 2. Run one PDF (developer path)

```bash
# Create a destination folder
mkdir -p /tmp/inv_001_easy

# Copy your test PDF
cp tests/stage1_vendor_identity/inv_001_easy/source.pdf /tmp/inv_001_easy/

# Run the pipeline
python -m ledgerlinc_ocr.pipeline run \
    --document-folder /tmp/inv_001_easy
```

On success (exit 0), stdout prints a single JSON line:

```json
{"document_id":"inv_001","decision":"edge_accept","manual_review_required":false,"review_reason":null,"artifacts":{"preprocess_output.json":"/tmp/inv_001_easy/preprocess_output.json","edge_extraction_output.json":"/tmp/inv_001_easy/edge_extraction_output.json","routing_decision.json":"/tmp/inv_001_easy/routing_decision.json","final_structured_payload.json":"/tmp/inv_001_easy/final_structured_payload.json"}}
```

Inspect the folder — exactly four JSON files alongside `source.pdf`:

```bash
ls /tmp/inv_001_easy/
# edge_extraction_output.json  final_structured_payload.json
# preprocess_output.json       routing_decision.json
# source.pdf
```

## 3. Run with --input (ad-hoc path)

```bash
mkdir -p /tmp/my_output
python -m ledgerlinc_ocr.pipeline run \
    --input ~/invoices/acme-invoice.pdf \
    --output-dir /tmp/my_output \
    --document-id acme_001
```

When using `--input`, `--document-id` is required if the output folder name does not match the corpus naming convention.

## 4. Harness integration (corpus loop)

```bash
CORPUS=tests/stage1_vendor_identity

for folder in "$CORPUS"/inv_*; do
    python -m ledgerlinc_ocr.pipeline run \
        --document-folder "$folder" \
        --overwrite \
        2>/dev/null
done
```

Each invocation writes four artifacts into the document folder. The harness reads them alongside `expected.json` for evaluation.

## 5. Diagnose a failure

On failure, the CLI prints a structured JSON line to stderr:

```bash
python -m ledgerlinc_ocr.pipeline run \
    --document-folder /tmp/nonexistent 2>&1 >/dev/null | jq .
```

```json
{
  "exit_code": 11,
  "exit_code_name": "INPUT_NOT_FOUND",
  "stage": "input_validation",
  "message": "Destination folder does not exist: /tmp/nonexistent",
  "artifacts_written": []
}
```

The exit code tells you the failure category; the `stage` field tells you where it happened.

## 6. Check exit codes programmatically

```bash
python -m ledgerlinc_ocr.pipeline run \
    --document-folder tests/stage1_vendor_identity/inv_001_easy \
    --overwrite
rc=$?

case $rc in
  0)  echo "Success" ;;
  10) echo "Usage error — check arguments" ;;
  11) echo "Input not found" ;;
  12) echo "Not a valid PDF" ;;
  13) echo "Artifacts exist — pass --overwrite" ;;
  14) echo "Output path not usable" ;;
  20) echo "Processing failure — check stderr" ;;
  30) echo "Schema validation failure — check stderr" ;;
  *)  echo "Unknown exit code: $rc" ;;
esac
```

## 7. Override the Ollama endpoint

```bash
# Via environment variable (preferred for harness/CI)
OLLAMA_BASE_URL=http://192.168.1.100:11434 \
    python -m ledgerlinc_ocr.pipeline run --document-folder /tmp/inv_001_easy

# Via CLI flag (one-off override)
python -m ledgerlinc_ocr.pipeline run \
    --document-folder /tmp/inv_001_easy \
    --ollama-url http://192.168.1.100:11434
```

## 8. Validate produced artifacts with the validator

After a pipeline run, use the existing validator to independently confirm schema compliance:

```bash
python -m ledgerlinc_ocr.validator validate folder /tmp/inv_001_easy --json
```

The pipeline CLI already performs post-hoc validation internally (exit code 30 on failure), but the validator is available as an independent check.

## 9. Run the test suite

```bash
pytest tests/pipeline_tests/ -v
```

Or run all tests (validator + pipeline):

```bash
pytest -v
```

## 10. What this feature does NOT give you

- **No real preprocessing**: Stage 3 (preprocess) writes stub artifacts. Real PaddleOCR/Falcon integration is a downstream feature.
- **No real extraction**: Stage 4 (extraction) writes stub artifacts. Real Qwen/Gemma/Phi-4 integration is a downstream feature.
- **No real routing logic**: Stage 5 (routing) writes stub artifacts. Real deterministic routing is a downstream feature.
- **No multi-document orchestration**: The CLI processes one document. The harness owns the loop.
- **No evaluation**: `evaluation_document.json` is produced by the harness, not by this CLI.
