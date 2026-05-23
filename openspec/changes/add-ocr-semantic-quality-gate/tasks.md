## 1. OpenSpec Readiness

- [ ] 1.1 Review `proposal.md`, `design.md`, and `specs/ocr-semantic-quality-gate/spec.md` against `docs/stage1-vendor-identity/prd-ocr-semantic-quality-gate.md`.
- [ ] 1.2 Resolve the open corpus-placement decision: canonical `tests/stage1_vendor_identity/` fixture versus separate semantic-quality corpus root.
- [ ] 1.3 Resolve the first sidecar row-truth shape for `semantic_table_truth.json`.
- [ ] 1.4 Run `openspec validate add-ocr-semantic-quality-gate --strict`.

## 2. Speckit Handoff

- [ ] 2.1 From `main`, verify `git status -sb` has no unintended worktree changes before running Speckit.
- [ ] 2.2 Start exactly one Speckit feature for `022-ocr-semantic-quality-gate` from this OpenSpec change and the draft PRD seed.
- [ ] 2.3 Run Speckit clarify/plan/tasks from the generated `022-ocr-semantic-quality-gate` worktree, not from `main` or an unrelated worktree.
- [ ] 2.4 Promote `docs/stage1-vendor-identity/prd-ocr-semantic-quality-gate.md` from draft seed to active feature PRD inside the Speckit work.

## 3. Required Speckit Coverage

- [ ] 3.1 Ensure the Speckit tasks cover the optional `semantic_table_truth.json` contract, validator support, and folder-contract behavior.
- [ ] 3.2 Ensure the Speckit tasks cover deterministic semantic-quality checks for missing row content, malformed currency shape, row text coverage, and OCR-confidence-as-evidence-only.
- [ ] 3.3 Ensure the Speckit tasks cover evaluator document and corpus report fields without changing existing vendor-identity metric meaning.
- [ ] 3.4 Ensure the Speckit tasks cover regression tests proving feature 019, feature 020, and feature 021 behavior are not rewritten in place.
- [ ] 3.5 Ensure the Speckit tasks cover degraded-body fixtures as test fixtures first, with canonical corpus promotion only through the explicit dataset amendment tasks.

## 4. Validation And Closure

- [ ] 4.1 After Speckit implementation, run the unit, contract, evaluator, and corpus validation commands named by the Speckit quickstart.
- [ ] 4.2 Run `PYTHONPATH=src python -m dartwing_ocr.validator validate corpus tests/stage1_vendor_identity` after any contract/folder changes.
- [ ] 4.3 Confirm no noncanonical degraded-body sample folders are accidentally staged as scored corpus folders.
- [ ] 4.4 Archive this OpenSpec change only after the Speckit feature and its PR land.
