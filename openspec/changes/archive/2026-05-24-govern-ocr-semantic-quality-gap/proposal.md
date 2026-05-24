## Why

Features 019, 020, and 021 have already shipped the OCR-only fast lane, vendor-identity evidence gate, and GPU MVP promotion boundary. A post-landing GPU calibration fixture showed that Paddle OCR can return high confidence for table-body text that is visibly and materially wrong, so the shipped specs need a governed amendment that records the limitation without rewriting shipped behavior.

## What Changes

- Add an OpenSpec-governed capability that documents the as-built semantic OCR/table-quality boundary discovered after feature 021.
- Amend the shipped Speckit docs for features 019, 020, and 021 to state that OCR confidence and vendor-identity sufficiency do not certify invoice body/table correctness.
- Add a draft stage 1 follow-up PRD seed and observation note for a future Speckit feature, `022-ocr-semantic-quality-gate`; this seed is not an active implementation contract.
- Clarify dataset, labeling, harness, and scoring docs so degraded table-body fixtures remain `hard` vendor-identity cases until a future schema/evaluator amendment adds table-body truth.
- Preserve the current MVP boundary: no runtime behavior change, no artifact schema change, no corpus baseline regeneration, and no change to the feature 020/021 promotion decision.

## Capabilities

### New Capabilities

- `ocr-semantic-quality-boundary`: Defines the shipped product boundary and records that confidently wrong table/body OCR is not detected by the current vendor-identity MVP behavior.

### Modified Capabilities

- None. The repository does not currently have archived OpenSpec capabilities for shipped Speckit features 019, 020, or 021. Their shipped Speckit artifacts are amended as documentation under this change, and the new OpenSpec capability governs the forward path.

## Impact

- Documentation:
  - `docs/stage1-vendor-identity/prd-ocr-semantic-quality-gate.md`
  - `docs/stage1-vendor-identity/ocr-semantic-quality-observations.md`
  - `docs/stage1-vendor-identity/README.md`
  - `docs/stage1-vendor-identity/dataset-layout.md`
  - `docs/stage1-vendor-identity/labeling-guide.md`
  - `docs/stage1-vendor-identity/prd-test-harness.md`
  - `docs/stage1-vendor-identity/scoring.md`
- Shipped Speckit artifacts:
  - `specs/019-ocr-only-fast-lane/research.md`
  - `specs/020-vendor-evidence-gate/spec.md`
  - `specs/020-vendor-evidence-gate/quickstart.md`
  - `specs/021-gpu-mvp-promotion/spec.md`
- No code, runtime dependencies, CLI flags, canonical artifact schemas, or committed corpus baselines are changed by this OpenSpec amendment.
