## Context

Features 019, 020, and 021 are shipped Speckit features. They established the OCR-only fast lane, the deterministic vendor-identity evidence gate, and the GPU MVP promotion path. After those features landed, calibration against a degraded invoice body showed that Paddle OCR can report high confidence for table-body text that is materially wrong.

The current stage 1 MVP is still vendor-identity-only. The new finding affects a product boundary and a future evaluator direction, not the already-shipped runtime behavior. Because it changes how the team interprets shipped feature claims, it belongs in OpenSpec before additional Speckit work.

## Goals / Non-Goals

**Goals:**

- Record the post-shipment semantic OCR quality gap under OpenSpec governance.
- Amend the shipped feature docs to clarify that feature 019 confidence, feature 020 vendor-identity sufficiency, and feature 021 GPU promotion do not certify table/body correctness.
- Add a draft PRD seed and observation note that can inform a future Speckit feature, `022-ocr-semantic-quality-gate`, without making that future behavior active now.
- Preserve the stage 1 MVP boundary while making the future product gap explicit.

**Non-Goals:**

- No runtime code change.
- No new CLI flag, environment variable, dependency, or model behavior.
- No change to canonical stage 1 artifact schemas or contract-set versions.
- No committed corpus baseline regeneration.
- No immediate promotion of the degraded-body candidate into the canonical corpus.
- No rewrite of shipped feature 019, 020, or 021 implementation behavior.

## Decisions

### Decision 1: Govern this as a post-shipment OpenSpec amendment

The shipped Speckit artifacts are amended under a new OpenSpec change instead of treating the docs edits as an ad hoc patch.

Alternatives considered:

- Edit shipped Speckit docs directly only: rejected because the finding affects product interpretation across shipped features.
- Reopen feature 021: rejected because 021 is a validation/promotion slice and must not absorb new product behavior.

### Decision 2: Add a new as-built boundary capability

The OpenSpec capability is `ocr-semantic-quality-boundary`. It captures the current shipped boundary rather than pretending archived Speckit features are native OpenSpec capabilities or making the future semantic-quality gate active before implementation.

Alternatives considered:

- Create modified OpenSpec capabilities for 019/020/021: rejected because `openspec/specs/` currently has no archived capabilities for those shipped Speckit features.
- Create only a PRD with no capability spec: rejected because OpenSpec needs a testable requirement surface for the as-built boundary.

### Decision 3: Keep the current docs edits documentation-only

The amendment adds docs/spec clarity and a non-active future-feature seed. It does not change runtime behavior, schemas, or corpus baselines.

Alternatives considered:

- Change feature 019 FR-005 thresholds now: rejected because the finding is about semantic correctness, not sparse/low-confidence detection.
- Block feature 020 skip-fallback on table-body quality now: rejected because feature 020 is vendor-identity scoped and a table-quality gate has not been specified or implemented.
- Add the degraded candidate as canonical corpus immediately: rejected because the folder name and table-truth contract need normal dataset governance first.

## Risks / Trade-offs

- The amendment may look like a product deferral instead of a fix -> Mitigation: the PRD seed names `022-ocr-semantic-quality-gate` while clearly stating it is not an active contract until the future feature is specified and implemented.
- Operators may confuse vendor-identity sufficiency with whole-invoice quality -> Mitigation: feature 020 and 021 specs explicitly state the boundary.
- The degraded fixture may enter the corpus incorrectly -> Mitigation: dataset and labeling docs state that degraded table-body candidates remain `hard` and require the normal amendment flow before table truth becomes scored data.
- Future table-quality work could overfit to one synthetic/degraded sample -> Mitigation: the PRD defines signal classes and open questions rather than hardcoding a single fixture as the whole solution.

## Migration Plan

1. Keep the OpenSpec change active while the docs/spec amendments are reviewed.
2. Land the documentation-only amendment with no runtime/schema/corpus baseline change.
3. Use the PRD seed to open a separate OpenSpec/Speckit feature when the team is ready to implement semantic/table OCR quality checks.
4. Archive this OpenSpec change only after the documentation amendment is merged and the follow-up path is acknowledged.

Rollback is documentation-only: revert the OpenSpec change and the associated docs/spec amendments. No runtime migration is required.

## Open Questions

- Should `022-ocr-semantic-quality-gate` store table/body truth in `expected.json`, a new optional fixture file, or evaluator-only data?
- Should semantic/table quality affect runtime fallback decisions, or only harness/evaluator verdicts?
- What minimum fixture set is needed before semantic table quality can influence whole-invoice claims?
