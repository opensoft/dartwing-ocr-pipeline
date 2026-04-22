# Quickstart: Evidence Packet Assembly

**Feature**: 004-evidence-packet-assembly
**Audience**: developers running the devcontainer who want to exercise the
slice end-to-end and inspect the generated packet.

## Prerequisites

1. The 003 preprocessing slice has run at least once and produced a
   `preprocess_output.json` in a per-document folder — for example
   `tests/stage1_vendor_identity/inv_001_easy/`. If you don't have one yet:

   ```bash
   ledgerlinc-preprocess tests/stage1_vendor_identity/inv_001_easy
   ```

2. The `ledgerlinc-ocr` package is installed in editable mode inside the
   devcontainer:

   ```bash
   python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
   ```

   The new `ledgerlinc-evidence-packet` console script is wired by this slice's
   `pyproject.toml` entry and becomes available on `PATH` after install.

## Default run (in-memory, no on-disk changes)

```bash
ledgerlinc-evidence-packet tests/stage1_vendor_identity/inv_001_easy
```

Expected:

- stdout: one compact JSON line, `status: "ok"`, `persisted: false`.
- The folder is unchanged — the four existing artifacts (`preprocess_output.json`, `edge_extraction_output.json` if present, `routing_decision.json` if present, `final_structured_payload.json` if present, `expected.json`) are byte-identical before and after. No `evidence_packet.json` is written.
- Exit code: `0`.

## Debug run (persists `evidence_packet.json`)

```bash
ledgerlinc-evidence-packet -v tests/stage1_vendor_identity/inv_001_easy
```

Expected:

- stderr: debug log lines describing input validation, regex-hit counts by field, output validation, and the persist path.
- stdout: one compact JSON line, `status: "ok"`, `persisted: true`.
- `tests/stage1_vendor_identity/inv_001_easy/evidence_packet.json` exists and validates against `contracts/stage1_vendor_identity/v1.1.0/evidence_packet.schema.json`.
- Exit code: `0`.

Re-run the same command. Diff the two on-disk results:

```bash
diff <(cat evidence_packet.json) <(ledgerlinc-evidence-packet -v ... && cat evidence_packet.json)
```

Output: empty — the files are byte-identical (SC-002).

## Library invocation

```python
from pathlib import Path
from ledgerlinc_ocr.evidence_packet import assemble_from_folder

packet = assemble_from_folder(Path("tests/stage1_vendor_identity/inv_001_easy"))

print(packet["contract_set_version"])          # "1.1.0"
print(packet["document_id"])                   # "inv_001"
print(len(packet["candidate_vendor_signals"]["emails"]))

# Every regex hit carries full source-reference fields
for hit in packet["candidate_vendor_signals"]["emails"]:
    print(
        hit["value"],
        hit["page_index"],
        hit["block_index"],
        hit["line_index"],
        hit["provenance"],   # "unverified" in stage 1
    )
```

If you already have the `preprocess_output` loaded (e.g. from 005's voter):

```python
import json
from ledgerlinc_ocr.evidence_packet import assemble_from_preprocess

with open("preprocess_output.json") as f:
    preprocess_output = json.load(f)

packet = assemble_from_preprocess(preprocess_output)   # no disk I/O
```

## Inspecting the Trijunction slots

```bash
ledgerlinc-evidence-packet -v tests/stage1_vendor_identity/inv_001_easy
jq '.ingestion_sources' tests/stage1_vendor_identity/inv_001_easy/evidence_packet.json
```

Expected in stage 1:

```json
{
  "paddleocr_vl": { "enabled": true, "status": "success", "payload": { "kind": "structural" } },
  "falcon_ocr": { "enabled": false, "status": "not_implemented", "payload": null },
  "falcon_perception": { "enabled": false, "status": "not_implemented", "payload": null }
}
```

All three slots are always present. Future slices populate `falcon_ocr` and
`falcon_perception` without changing the packet shape.

## Failure modes to try

- **Missing input**: delete `preprocess_output.json` and re-run — exit code `2`, stdout `status: "error", kind: "input_missing"`.
- **Invalid input**: truncate `preprocess_output.json` to break the schema — exit code `3`, `kind: "input_invalid"`.
- **Read-only folder + verbose**: `chmod -w` the folder and re-run with `-v` — exit code `5`, `kind: "persistence_failed"`. The in-memory packet is still valid; the failure is specifically about writing.

## Validation commands (after the amendment ships)

Once `contracts/stage1_vendor_identity/v1.1.0/` is in place:

```bash
# Validate the persisted packet against its schema
python -m ledgerlinc_ocr.validator validate artifact \
  --schema contracts/stage1_vendor_identity/v1.1.0/evidence_packet.schema.json \
  tests/stage1_vendor_identity/inv_001_easy/evidence_packet.json

# Validate the folder against the amended folder contract
python -m ledgerlinc_ocr.validator validate folder \
  tests/stage1_vendor_identity/inv_001_easy
```

Both commands should exit 0 whether or not `evidence_packet.json` is present
(the file is an optional reserved generated filename in v1.1.0).

## Where to go next

- Inspect `data-model.md` for the authoritative packet shape and invariants.
- Inspect `contracts/cli-contract.md` for exit-code semantics and library API.
- Inspect `research.md` Decisions 2 and 4 for the reverse-mapping rationale
  behind `line_index`.
