# Claude Prompt: `/speckit.specify` for Feature 022

Use this prompt in Claude from the Dartwing OCR repo root.

Before running `/speckit.specify`, verify:

```bash
git status -sb
git branch --show-current
```

You must be on `main`, and any existing worktree changes must be intentional and preserved. Do not pre-create a Codex-prefixed branch. Let the Speckit `before_specify` hook create the canonical feature branch/worktree. After `/speckit.specify` creates the feature worktree, run follow-on Speckit commands from that generated worktree, not from `main`.

## Prompt To Send

```text
/speckit.specify

Create feature 022-ocr-semantic-quality-gate for the Dartwing OCR pipeline.

Use these source artifacts as the governing input:

- openspec/changes/add-ocr-semantic-quality-gate/proposal.md
- openspec/changes/add-ocr-semantic-quality-gate/design.md
- openspec/changes/add-ocr-semantic-quality-gate/specs/ocr-semantic-quality-gate/spec.md
- docs/stage1-vendor-identity/prd-ocr-semantic-quality-gate.md
- docs/stage1-vendor-identity/ocr-semantic-quality-observations.md
- openspec/changes/govern-ocr-semantic-quality-gap/specs/ocr-semantic-quality-boundary/spec.md

The OpenSpec capability spec is the source of truth for feature behavior. The prior `govern-ocr-semantic-quality-gap` change only documented the as-built limitation; this new feature is the implementation/refactor work that adds the semantic/table OCR quality gate.

Feature intent:

- Add deterministic semantic/table OCR quality evaluation for degraded invoice body/table rows.
- Add an optional authored `semantic_table_truth.json` sidecar for documents that have table/body truth.
- Keep `expected.json` as the vendor-identity truth file; do not overload it with table truth unless a later clarification explicitly changes that decision.
- Evaluate semantic table quality from `preprocess_output.json` plus `semantic_table_truth.json`.
- Do not use model judgment, network calls, or OCR confidence as proof of correctness.
- Record failed checks for missing required row content, malformed currency shape such as `$21:00` for `$21.00`, row text coverage gaps, and row-alignment failure evidence.
- Add evaluator/reporting surfaces that expose semantic table quality separately from existing vendor-identity metrics.
- Preserve current feature 019 OCR-only fallback behavior, feature 020 vendor-identity evidence-gate behavior, feature 021 GPU MVP promotion criteria, and `document_pass_fail.vendor_identity_passed`.
- When semantic truth is absent, report semantic table quality as not applicable rather than inferring a pass from vendor-identity metrics.
- When semantic truth is present and the gate fails, whole-invoice/table-quality claims must fail or require review even if vendor identity passes.
- Treat degraded-body samples as test/calibration fixtures first. Do not promote noncanonical folders such as `inv_024_hard_degraded_body` into scored corpus data unless the same feature includes the dataset, labeling, folder-contract, and evaluator contract amendments needed to validate them.

Important scope constraints:

- Stage 1 remains vendor-identity-first; this feature adds table/body quality evaluation, not line-item extraction.
- Do not rewrite features 019, 020, or 021 in place.
- Do not add a learned classifier, new model runtime, remote service, network call, or prompt-owned routing decision.
- Keep the gate deterministic and code-owned.
- Keep specs and code aligned: do not add active requirements that are not covered by the feature implementation tasks and tests.

Resolve or preserve as explicit clarification questions:

1. Should canonical degraded-body fixtures eventually live under `tests/stage1_vendor_identity/`, or should this feature introduce a separate semantic-quality corpus root?
2. What is the minimum `semantic_table_truth.json` row shape for the first gate: required values only, required values plus row text, or required values plus approximate row-region anchors?
3. Should runtime fallback/review integration remain out of scope for this feature and be deferred until evaluator-only evidence is stable?

Generate a Speckit feature spec that is suitable for `/speckit.clarify`, `/speckit.plan`, `/speckit.tasks`, and implementation. The spec must include testable functional requirements and success criteria for the sidecar truth contract, deterministic quality checks, evaluator report surface, vendor-identity non-regression, and corpus governance.
```
