# Stage 1 Vendor-Identity Corpus

This directory is the runtime corpus root for the stage 1 vendor-identity pipeline.

Each document lives in its own folder named `inv_<NNN>_<difficulty>/` where
`<difficulty>` is one of `easy`, `medium`, `hard`, `missing_name`.

## Labeling

See the authoritative documentation:

- `docs/stage1-vendor-identity/labeling-guide.md` — authoritative labeler-facing conventions for `expected.json` and `notes.md`, plus the PII/license screening checklist applied before any document enters the corpus.
- `docs/stage1-vendor-identity/dataset-layout.md` — folder contract, difficulty, challenge-tag vocabulary.
- `docs/stage1-vendor-identity/schemas.md` — `expected.json` shape.
- `contracts/stage1_vendor_identity/v1.0.0/expected.schema.json` — machine-readable contract the validator enforces.

## Validating

From repo root:

```bash
python -m dartwing_ocr.validator validate folder tests/stage1_vendor_identity/inv_001_easy
python -m dartwing_ocr.validator validate corpus tests/stage1_vendor_identity
```

## Required files per document

- `source.pdf` — unconditional.
- `expected.json` — unconditional; conforms to `expected.schema.json`.
- `notes.md` — hard requirement for `hard` and `missing_name`; soft (warning only) for `easy` and `medium`.

## Reserved filenames

The following are reserved for pipeline/evaluator output in each document folder:

- `preprocess_output.json`
- `edge_extraction_output.json`
- `routing_decision.json`
- `final_structured_payload.json`
- `evaluation_document.json`

Corpus root reserved file: `evaluation_run_summary.json`.

Reserved for a later ensemble mode (unused in stage 1): `votes/` subdirectory and `consensus_output.json`.
