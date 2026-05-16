# Quickstart: 009-final-payload

End-to-end walkthrough for running the assembler on one per-document folder in the devcontainer.

## 1. Install (one-time)

From the repo root:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

This makes `python -m dartwing_ocr.assembler` available. Once `pyproject.toml` is updated
(tasks phase) the `dartwing-assemble` console script will also be installed.

## 2. Stage a per-document folder

For a real corpus document (after 003-pdf-preprocessing + 005-single-voter-extraction +
008-routing have all run):

```text
tests/stage1_vendor_identity/inv_017_medium/
├── source.pdf
├── expected.json
├── preprocess_output.json       # from 003
├── edge_extraction_output.json  # from 005
└── routing_decision.json        # from 008
```

For a standalone assembler run (artifact-to-artifact, no upstream feature needed), use a
hand-crafted fixture folder with just the two JSONs:

```text
tests/fixtures/assembler/happy_grounded/
├── edge_extraction_output.json
└── routing_decision.json
```

The assembler only reads those two files. `source.pdf` and `preprocess_output.json` are
referenced by `trace` but not opened by this stage.

## 3. Run the assembler

```bash
python -m dartwing_ocr.assembler \
  --document-folder tests/fixtures/assembler/happy_grounded/
```

On success: exit `0`, no stdout, `final_structured_payload.json` written into the folder.

On failure: non-zero exit, one JSON line on stderr, no output file written. Example:

```bash
$ python -m dartwing_ocr.assembler \
    --document-folder tests/fixtures/assembler/document_id_mismatch/
{"status": "error", "kind": "document_id_mismatch", "message": "edge_extraction_output.json:document_id='inv_005' but routing_decision.json:document_id='inv_006'"}
$ echo $?
2
```

## 4. Inspect the output

```bash
cat tests/fixtures/assembler/happy_grounded/final_structured_payload.json
```

Expected top-level shape:

```json
{
  "contract_set_version": "1.0.0",
  "pipeline_version": "009-final-payload@0.1.0",
  "document_id": "...",
  "processed_at": "2026-04-21T10:30:00Z",
  "document_type": "invoice",
  "vendor_candidate": { "company_name": {...}, "address": {...}, "tax_ids": {...}, "website": {...}, "phone": {...}, "email": {...} },
  "review_status": { "manual_review_required": false, "review_reason": null },
  "quality_summary": { "overall_vendor_confidence": 0.8723, "explicit_name_found": true, "consensus_level": "single_voter_baseline", "secondary_identifiers_found": ["address", "ein", "email"] },
  "trace": { "source_file": "source.pdf", "preprocess_output_file": "preprocess_output.json", "edge_extraction_output_file": "edge_extraction_output.json", "routing_decision_file": "routing_decision.json" }
}
```

Key things to verify by eye:
- No `evidence` key anywhere (FR-014).
- `secondary_identifiers_found` items appear in schema enum order: `address, ein, state_tax_id, vat_id, other_tax_id, website, phone, email` (absent items skipped).
- `review_status` is byte-identical to `routing_decision.json:review_status`.

## 5. Validate against the frozen contract

```bash
python -m dartwing_ocr.validator validate artifact \
  --contract final_structured_payload \
  tests/fixtures/assembler/happy_grounded/final_structured_payload.json
```

Exit `0` means the assembler's output matches the frozen v1.0.0 schema.

## 6. Re-run to confirm determinism

```bash
cp tests/fixtures/assembler/happy_grounded/final_structured_payload.json /tmp/first.json
python -m dartwing_ocr.assembler --document-folder tests/fixtures/assembler/happy_grounded/
diff <(jq 'del(.processed_at)' /tmp/first.json) \
     <(jq 'del(.processed_at)' tests/fixtures/assembler/happy_grounded/final_structured_payload.json)
```

No diff = byte-identical output (FR-022, SC-004).

## 7. Run the test suite

```bash
.venv/bin/pytest tests/pipeline_tests/ tests/contract_tests/ tests/unit/
```

All US1–US6 acceptance scenarios are covered by `test_assembler_us*.py`. The seven fixtures
under `tests/fixtures/assembler/` back each scenario.

## 8. Performance note (SC-001)

A single `run(...)` against the `happy_grounded` fixture measures ~3 ms wall-clock on the
devcontainer (5-sample warm-cache median: ~3.0 ms; all samples < 5 ms). That is two orders of
magnitude below the SC-001 ceiling of 200 ms for a single per-document folder. The CLI adds
Python interpreter startup (~30–60 ms) on top of that, still well under budget.
