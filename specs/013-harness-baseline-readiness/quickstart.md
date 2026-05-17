# Quickstart: Harness Baseline Readiness

Run from the 013 worktree with `PYTHONPATH=src`.

## Stub-Safe Committed Document Smoke

```bash
tmpdir="$(mktemp -d)"
cp -a tests/stage1_vendor_identity/inv_001_easy "$tmpdir/"
PYTHONPATH=src python -m dartwing_ocr.evaluator document \
  "$tmpdir/inv_001_easy" \
  --run-pipeline \
  --pipeline-overwrite
```

Expected:

- Exit code `0`.
- `$tmpdir/inv_001_easy/evaluation_document.json` exists.
- Generated `final_structured_payload.json` and committed `expected.json` both use `document_id` `inv_001_easy`.

## Stub-Safe Corpus Smoke

```bash
tmpdir="$(mktemp -d)"
mkdir -p "$tmpdir/corpus"
cp -a tests/stage1_vendor_identity/inv_001_easy "$tmpdir/corpus/"
cp -a tests/stage1_vendor_identity/inv_002_easy "$tmpdir/corpus/"
PYTHONPATH=src python -m dartwing_ocr.evaluator corpus \
  "$tmpdir/corpus" \
  --run-pipeline \
  --pipeline-overwrite
```

Expected:

- Exit code `0`.
- No document-id mismatch errors.
- The run summary reports both documents prepared and evaluated.

## Real Profile Dependency Failure Shape

```bash
tmpdir="$(mktemp -d)"
cp -a tests/stage1_vendor_identity/inv_001_easy "$tmpdir/"
PYTHONPATH=src python -m dartwing_ocr.evaluator document \
  "$tmpdir/inv_001_easy" \
  --run-pipeline \
  --pipeline-overwrite \
  --stack-preset full-workstation
```

Expected in an environment missing OCR dependencies such as `PIL`:

- Non-zero exit code.
- Error text names the missing dependency and selected stage/profile.
- No Python traceback is printed.
