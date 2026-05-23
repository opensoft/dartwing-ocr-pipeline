## Why

The shipped stage 1 pipeline can accept vendor-identity evidence while table/body OCR is still confidently wrong. The previous as-built boundary amendment documented that gap; this change implements the first deterministic semantic/table OCR quality gate so future whole-invoice claims do not rely on Paddle OCR confidence alone.

## What Changes

- Add a deterministic semantic/table OCR quality gate for degraded invoice body/table rows.
- Add an evaluator-owned truth surface for table/body semantic checks without changing the vendor-identity meaning of `expected.json`.
- Add schema/report support so per-document and run-level evaluation can record semantic/table quality results separately from vendor-identity scores.
- Add tests and fixtures that prove high OCR confidence can still fail semantic/table quality.
- Keep vendor-identity-only acceptance valid: feature 019 fallback, feature 020 vendor-identity sufficiency, and feature 021 GPU MVP promotion are not rewritten in place.
- Define the handoff to Speckit feature `022-ocr-semantic-quality-gate` for implementation.

## Capabilities

### New Capabilities

- `ocr-semantic-quality-gate`: Defines deterministic table/body OCR quality evaluation, its fixture truth surface, evaluator reporting, and its interaction with existing vendor-identity-only gates.

### Modified Capabilities

- None. `openspec/specs/` does not contain archived capabilities for features 019, 020, 021, or the previous boundary amendment. This change introduces the implementation capability and may update repo docs/Speckit artifacts as part of the implementation tasks.

## Impact

- Code:
  - semantic-quality gate module under `src/dartwing_ocr/`
  - evaluator/harness integration
  - validator/schema loading where report or fixture contracts change
- Contracts and docs:
  - new or amended semantic table-truth fixture contract
  - evaluation output schemas and contract-set amendment notes if the report shape changes
  - `docs/stage1-vendor-identity/prd-ocr-semantic-quality-gate.md`
  - dataset, labeling, harness, scoring, and schema docs
- Tests:
  - unit tests for deterministic signals and verdicts
  - contract tests for any new fixture/report schema
  - evaluator tests proving degraded-body rows fail semantic quality despite high OCR confidence
- No new model runtime dependency, network call, or model-owned routing decision.
