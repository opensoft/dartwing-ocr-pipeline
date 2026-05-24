# contracts/stage1_vendor_identity/v1.3.0/

Machine-readable layer of the stage 1 vendor-identity contract set. v1.0.0 frozen 2026-04-12; v1.1.0 amended 2026-04-21 (adds `evidence_packet`); v1.2.0 amended 2026-04-23 (preprocess_output and mirrored evidence-packet structural confidence fields permit `null` when the engine omits or cannot provide a schema-valid score); v1.3.0 amended 2026-05-23 (adds the optional per-document `semantic_table_truth.json` sidecar contract and additive semantic-quality fields on the two evaluation report schemas, per feature 022 — see `../AMENDMENTS.md` and `specs/022-ocr-semantic-quality-gate/contracts/schema-amendments.md`).

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
| `evaluation_document.schema.json` | JSON Schema 2020-12 | Per-document comparison result. **v1.3.0 delta**: additive `semantic_table_quality` object and `document_pass_fail.semantic_table_quality_passed` field. |
| `evaluation_run_summary.schema.json` | JSON Schema 2020-12 | Corpus-level aggregate. **v1.3.0 delta**: additive `semantic_table_quality_metrics` namespace (six per-status document counts, a nullable `semantic_table_quality_pass_rate` formatted as 6-dp `ROUND_HALF_EVEN`, and a nested `semantic_failed_check_counts` object with four per-category counters) and `semantic_document_statuses` array. |
| `folder.schema.json` | JSON configuration | Describes the filesystem layout (folder name pattern, required files per difficulty, reserved generated filenames). **Not** a JSON Schema applied to a file. **v1.3.0 delta**: `semantic_table_truth.json` appended to `reserved_generated_filenames`. |
| `semantic_table_truth.schema.json` | JSON Schema 2020-12 | **NEW in v1.3.0** — optional per-document truth sidecar for the semantic-table quality gate. `document_id` and `row_id` constrained to `^[A-Za-z0-9_-]{1,64}$` (Q-SEC-2/B). |

## Cross-artifact rules

The JSON Schema files enforce per-artifact rules. Rules that span multiple files — the company-name provenance triad and the evidence-reference integrity check — are implemented in `src/ledgerlinc_ocr/validator/cross_artifact.py`. `contract_set.json.cross_artifact_rules` names the active set.

## Amending this contract set

Do not mutate files in a shipped version directory. Follow the checklist in `../AMENDMENTS.md` to land a new version.

For the v1.3.0 amendment narrative — what changed, why, and what stayed byte-identical from v1.2.0 — see [`../AMENDMENTS.md#v130--2026-05-23`](../AMENDMENTS.md#v130--2026-05-23).

## Using this contract set

From repo root:

```bash
python -m ledgerlinc_ocr.validator show contract-set --version 1.0.0
python -m ledgerlinc_ocr.validator validate artifact <path> --contract <name>
python -m ledgerlinc_ocr.validator validate folder <path>
python -m ledgerlinc_ocr.validator validate corpus tests/stage1_vendor_identity
```
