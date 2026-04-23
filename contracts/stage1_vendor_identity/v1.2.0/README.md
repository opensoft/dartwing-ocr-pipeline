# contracts/stage1_vendor_identity/v1.2.0/

Machine-readable layer of the stage 1 vendor-identity contract set. v1.0.0 frozen 2026-04-12; v1.1.0 amended 2026-04-21 (adds `evidence_packet`); v1.2.0 amended 2026-04-23 (preprocess_output confidence permits `null` when the engine omits a score — see `AMENDMENTS.md`).

This directory is the *executable* representation consumed by `ledgerlinc_ocr.validator`. The *canonical* meaning of each artifact lives in the human-facing documentation layer:

- `docs/stage1-vendor-identity/schemas.md`
- `docs/stage1-vendor-identity/dataset-layout.md`
- `docs/stage1-vendor-identity/scoring.md`
- `docs/stage1-vendor-identity/architecture.md`
- `.specify/memory/constitution.md`

The two layers are updated together. When they disagree, the documentation layer is authoritative — but they should never be allowed to disagree outside an in-flight amendment.

## Files

| File | Kind | Purpose |
|------|------|---------|
| `contract_set.json` | metadata | Registers every schema, the closed `challenge_tags` vocabulary, and the active cross-artifact rules for this version. |
| `preprocess_output.schema.json` | JSON Schema 2020-12 | Page-level OCR + layout output of the preprocessing stage. |
| `edge_extraction_output.schema.json` | JSON Schema 2020-12 | Model-driven structured extraction with confidence + evidence; ensemble-ready by shape. |
| `routing_decision.schema.json` | JSON Schema 2020-12 | Deterministic accept/review decision with `consensus_summary`, `scores`, `checks`. |
| `final_structured_payload.schema.json` | JSON Schema 2020-12 | Clean downstream handoff; flattened `vendor_candidate`. |
| `expected.schema.json` | JSON Schema 2020-12 | Hand-labeled truth for one document. `additionalProperties: false` everywhere — no predictions, no confidence. |
| `evaluation_document.schema.json` | JSON Schema 2020-12 | Per-document comparison result. |
| `evaluation_run_summary.schema.json` | JSON Schema 2020-12 | Corpus-level aggregate. |
| `folder.schema.json` | JSON configuration | Describes the filesystem layout (folder name pattern, required files per difficulty, reserved generated filenames). **Not** a JSON Schema applied to a file. |

## Cross-artifact rules

The JSON Schema files enforce per-artifact rules. Rules that span multiple files — the company-name provenance triad and the evidence-reference integrity check — are implemented in `src/ledgerlinc_ocr/validator/cross_artifact.py`. `contract_set.json.cross_artifact_rules` names the active set.

## Amending this contract set

Do not mutate files in a shipped version directory. Follow the checklist in `../AMENDMENTS.md` to land a new version.

## Using this contract set

From repo root:

```bash
python -m ledgerlinc_ocr.validator show contract-set --version 1.0.0
python -m ledgerlinc_ocr.validator validate artifact <path> --contract <name>
python -m ledgerlinc_ocr.validator validate folder <path>
python -m ledgerlinc_ocr.validator validate corpus tests/stage1_vendor_identity
```
