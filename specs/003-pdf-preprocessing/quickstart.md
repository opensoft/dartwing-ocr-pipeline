# Quickstart: PDF Preprocessing (Stage 1)

Run the stage 1 preprocessing slice against a single invoice PDF and produce a
schema-valid `preprocess_output.json` next to it.

## Prerequisites

- A working devcontainer (see `.devcontainer/docker-compose.yml`; the
  `pipeline-dev` service is enough — no Ollama, no GPU needed for
  preprocessing).
- Python 3.12.
- A per-document folder under `tests/stage1_vendor_identity/inv_XXX_<difficulty>/`
  that contains `source.pdf`.

## One-time setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
# The preprocessing slice adds these runtime deps to pyproject.toml:
#   pypdfium2, paddleocr, paddlepaddle (CPU), Pillow, numpy
# They install automatically via the editable install once the tasks land.
```

## Run preprocessing on one document

```bash
python -m ledgerlinc_ocr.preprocessing \
    --document-folder tests/stage1_vendor_identity/inv_001_easy
```

Expected result:

- Exit code `0`.
- Stdout: `{"status": "ok", "document_id": "inv_001_easy", "artifact": "<abs path>", "warnings": 0}`
- `tests/stage1_vendor_identity/inv_001_easy/preprocess_output.json` exists
  and validates against the frozen v1.0.0 contract.

## Verify the artifact

Run the existing contract validator:

```bash
python -m ledgerlinc_ocr.validator validate artifact preprocess_output \
    tests/stage1_vendor_identity/inv_001_easy/preprocess_output.json
```

Expected: `OK` (or the validator's success equivalent), zero errors.

## Check determinism

```bash
python -m ledgerlinc_ocr.preprocessing --document-folder tests/stage1_vendor_identity/inv_001_easy
cp tests/stage1_vendor_identity/inv_001_easy/preprocess_output.json /tmp/run1.json
python -m ledgerlinc_ocr.preprocessing --document-folder tests/stage1_vendor_identity/inv_001_easy
diff /tmp/run1.json tests/stage1_vendor_identity/inv_001_easy/preprocess_output.json
```

Expected: empty diff (SC-002).

## Inspecting a debug run

```bash
python -m ledgerlinc_ocr.preprocessing \
    --document-folder tests/stage1_vendor_identity/inv_001_easy \
    --write-page-images
ls tests/stage1_vendor_identity/inv_001_easy/page_*.png
```

The `page_*.png` files are debug-only (FR-007) — they are not part of the
contract and are not consumed by any downstream slice.

## Failure modes you should see

Each of these is covered by integration tests under
`tests/integration/preprocessing/`.

| Input                                              | Exit | Artifact? | Stderr hint                         |
|----------------------------------------------------|------|-----------|-------------------------------------|
| Folder exists, `source.pdf` missing                | `2`  | no        | `source.pdf not found in <folder>`  |
| Encrypted / password-protected PDF                 | `2`  | no        | `encrypted PDF — decryption out of scope` |
| Truncated / malformed PDF                          | `2`  | no        | `could not open PDF: <reason>`      |
| Non-PDF file renamed `source.pdf`                  | `2`  | no        | `not a PDF (bad magic bytes)`       |
| PDF with one blank / unreadable page among others  | `0`  | yes       | warning in artifact naming the page |

## Common troubleshooting

- **PaddleOCR first-run model download**: on the first invocation, PaddleOCR
  pulls its model weights. This is a one-time cost; subsequent runs use the
  cached weights under `~/.paddlex/`.
- **Schema-validation failure (exit 3)**: this means the assembled artifact
  did not match `preprocess_output.schema.json`. Do not edit the schema —
  that is frozen v1.0.0. Fix the pipeline code to match the contract. See
  `contracts/stage1_vendor_identity/AMENDMENTS.md` for the schema-change path,
  which is explicitly out of scope for this slice.
- **Non-deterministic diffs on rerun**: check that `use_mp=False` and
  `cpu_threads=1` are still set in the PaddleOCR wrapper (research.md
  Decision 2). Multiprocessing reorders pages and breaks SC-002.
