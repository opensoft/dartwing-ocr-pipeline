# dartwing-ocr-pipeline

Step 2 of the Dartwing AP Clerk Agent: OCR + Field Extraction + Structuring.

## Stage 1 — Contracts & Validator

Stage 1 freezes the JSON contracts for the seven persisted artifacts and the per-document folder layout, and ships a Python validator that enforces them. See `specs/001-freeze-schemas-folder-contracts/quickstart.md` for the full walkthrough.

Quick commands from a fresh checkout:

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m dartwing_ocr.validator show contract-set
.venv/bin/python -m dartwing_ocr.validator validate artifact <path> --contract <name>
.venv/bin/python -m dartwing_ocr.validator validate folder <folder>
.venv/bin/python -m dartwing_ocr.validator validate corpus tests/stage1_vendor_identity
.venv/bin/pytest tests/contract_tests/
```

Machine-readable contracts live at `contracts/stage1_vendor_identity/v1.0.0/`. The human-readable documentation layer lives at `docs/stage1-vendor-identity/`. Amendments go through `contracts/stage1_vendor_identity/AMENDMENTS.md`.

## Prototype (pre-stage-1)

The legacy prototype script still exists for reference — treat it as scaffolding, not as the pipeline.

```bash
python step2_ocr_ensemble.py --input test_invoices/your_invoice.pdf
