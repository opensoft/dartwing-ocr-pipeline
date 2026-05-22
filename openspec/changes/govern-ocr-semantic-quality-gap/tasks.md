## 1. OpenSpec Governance

- [x] 1.1 Create the `govern-ocr-semantic-quality-gap` OpenSpec change from the bench container where `openspec` is available.
- [x] 1.2 Add the proposal, design, and `ocr-semantic-quality-boundary` capability spec.
- [x] 1.3 Confirm the amendment is documentation-only: no runtime code, CLI behavior, dependencies, artifact schemas, or corpus baselines are changed.

## 2. Shipped Speckit Artifact Amendments

- [x] 2.1 Amend feature 019 research to record that token count and mean detector confidence are not semantic/table correctness proof.
- [x] 2.2 Amend feature 020 spec and quickstart to state that vendor-identity sufficiency does not certify table/body OCR and to defer semantic/table quality to feature 022.
- [x] 2.3 Amend feature 021 spec to record the degraded-body OCR confidence limitation as a post-GPU calibration observation without broadening GPU promotion scope.

## 3. Stage 1 Documentation Amendments

- [x] 3.1 Add `docs/stage1-vendor-identity/prd-ocr-semantic-quality-gate.md` as a non-active follow-up feature seed with candidate requirements and a Speckit specify seed.
- [x] 3.2 Add `docs/stage1-vendor-identity/ocr-semantic-quality-observations.md` with the `inv_024` calibration evidence and row-level comparison.
- [x] 3.3 Update stage 1 README, dataset layout, labeling guide, harness PRD, and scoring docs to preserve the vendor-identity MVP boundary while documenting the future semantic/table gate.

## 4. Validation

- [x] 4.1 Run `openspec status --change govern-ocr-semantic-quality-gap` from the bench container and confirm proposal, design, specs, and tasks are complete.
- [x] 4.2 Run `git diff --check` and whitespace checks for the new docs.
- [x] 4.3 Confirm user-provided degraded invoice samples remain unmodified and unpromoted to canonical corpus folders.
