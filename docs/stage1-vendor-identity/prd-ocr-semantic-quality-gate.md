# PRD: OCR Semantic Quality Gate

**Status**: ACTIVE — feature 022 landed via stacked PRs #44 → #46 → #47 → #49 → #50 against `contract_set_version` `1.3.0` (2026-05-23). This PRD now records what was built, not what was proposed. See `specs/022-ocr-semantic-quality-gate/spec.md` for the authoritative requirement set and `contracts/stage1_vendor_identity/AMENDMENTS.md#v130--2026-05-23` for the contract-bump narrative.

## Landed scope (2026-05-23)

The feature ships a deterministic, pure-CPU, harness-side semantic-table OCR quality gate. It evaluates four predicate-based checks in fixed order (no short-circuit) against an optional per-document `semantic_table_truth.json` sidecar and folds the verdict into the evaluator's existing artifacts as additive fields only. **No runtime pipeline code was modified** — Principle I and FR-028 guarantee, enforced by `tests/integration/test_features_019_021_unchanged.py`.

Key landed decisions (from the 44 Clarifications + 7 security-clarify questions):

- **Q14**: contract-set bumps 1.2.0 → 1.3.0 (additive; v1.2.0 frozen and read-accessible).
- **Q20 / MI-17 / FR-025**: `document_pass_fail.semantic_table_quality_passed` value domain is `{true, false, false, null}` for status `{passed, failed, unevaluable, not_applicable}`.
- **Q23 / MI-21 / SC-009**: canonical-pattern allowlist `^inv_\d{3}_(easy|medium|hard)$` partitions corpus folders into SCORED vs CALIBRATION. Calibration folders run the gate but do not feed scored aggregation.
- **Q26**: closed snake_case status enum `{passed, failed, unevaluable, not_applicable}`.
- **Q34**: stable-JSON serialization — sorted keys, UTF-8, LF, trailing newline, `Decimal` 6-dp `ROUND_HALF_EVEN`.
- **Q39 / MI-20**: aggregate counters in `semantic_table_quality_metrics` reflect scored folders only.
- **Q42 / MI-19**: `SemanticGateInvariantError` for invariant violations.
- **Q-SEC-2/B**: sidecar `document_id` and `row_id` constrained to `^[A-Za-z0-9_-]{1,64}$` (path-traversal / log-injection defense).
- **Q-SEC-7/B / FR-034**: air-gapped operation is a named requirement; the gate, validator, and evaluator make no network calls.

Phase 8 polish (T063-T070) also lands: AMENDMENTS.md v1.3.0 entry, schemas.md delta, this PRD promotion, v1.3.0/README.md update, CLAUDE.md verification, quickstart walkthrough, full pytest sweep, and the FR↔task↔test coverage matrix.

## Background (original problem statement)

The intended future Speckit feature name was:

- `022-ocr-semantic-quality-gate`

## Problem Statement

GPU calibration on a degraded invoice candidate showed that Paddle OCR can produce high detector confidence while reading table-body content incorrectly.

Observed behavior on the `inv_024_hard_degraded_body` candidate:

- the header was readable enough for vendor identity
- the table body was visibly degraded to a human reviewer
- Paddle OCR returned high confidence for many wrong row values
- quantities were omitted
- currency decimals were read as colons, such as `$21:00`
- several descriptions differed from labeled ground truth
- feature 019 FR-005 did not trigger fallback because token count and mean confidence stayed above threshold

This is not a defect in feature 020 or feature 021. Those features gate vendor identity and GPU promotion. It is a product gap for broader invoice understanding: OCR confidence is not semantic correctness.

## Future Goal

Specify and implement a deterministic quality gate that can flag table/body OCR outputs that are likely unusable even when OCR detector confidence is high.

A future gate should protect whole-invoice extraction work from accepting confidently wrong OCR and should give operators a clear reason to fall back, review, or route the document differently.

## Users and Stakeholders

Primary users:

- pipeline developers tuning OCR preprocessing
- evaluation owners expanding beyond vendor identity
- operators reviewing degraded invoice outputs

Stakeholders:

- Dartwing OCR/model pipeline engineering
- downstream accounting and AP workflow owners
- future line-item and totals extraction owners

## Candidate Future Scope

Candidate included scope for feature `022`:

- deterministic table/body quality signals computed from existing preprocessing output and, for evaluator runs, labeled truth
- fixture-driven evaluation using degraded table-body documents such as `inv_024_hard`
- row completeness checks for expected columns:
  - quantity
  - description
  - unit price
  - amount
- currency-shape checks that distinguish decimal money values from OCR punctuation errors such as `$21:00`
- column coverage and row-alignment checks for table-like OCR output
- a quality verdict that can be recorded in evaluator output or an existing operator-facing report surface
- an explicit interaction rule with feature 020 skip-fallback:
  - vendor-identity-only runs may still accept sufficient header evidence
  - whole-invoice or table-quality claims must not suppress fallback when the semantic/table quality gate fails

Explicitly out of scope for this draft seed and the current as-built amendment:

- changing feature 020's vendor-identity evidence gate in place
- changing feature 021's GPU promotion posture in place
- requiring line-item extraction to ship before the current MVP demo
- replacing Paddle confidence with a learned classifier
- adding a new product runtime dependency unless the Speckit plan proves one is necessary
- regenerating committed corpus baselines outside the dataset amendment flow

## Candidate Requirements For Feature 022

The following candidate requirements are not active for the shipped code. They should be reviewed, revised, and made testable in the separate `022-ocr-semantic-quality-gate` OpenSpec/Speckit work before implementation.

### Semantic Quality Signals

1. Feature `022` should treat OCR confidence as an observation, not as proof of correctness.
2. Feature `022` should detect missing required table-column content when the expected fixture declares those columns.
3. Feature `022` should detect malformed money values when the expected fixture contains normalized currency and OCR output substitutes punctuation that changes the value shape, such as colon for decimal point.
4. Feature `022` should detect row-alignment gaps where values from a row are missing, shifted, or split in a way that prevents deterministic row reconstruction.
5. Feature `022` should preserve low-confidence OCR as one signal, but low confidence should not be the only trigger.
6. Feature `022` should record enough evidence for an operator to understand whether failure was caused by missing cells, malformed currency, row alignment, or text mismatch.

### Fixture And Evaluation Requirements

1. A degraded-body fixture should be promoted through the normal corpus process as `inv_024_hard` or the next available `inv_NNN_hard` folder.
2. The fixture must pass the labeling-guide pre-inclusion screening before it becomes canonical corpus data.
3. The fixture's `expected.json` could remain vendor-identity-only while table/body truth is held in a separate evaluator extension, if the active contract set is still vendor-identity-only.
4. If table/body truth becomes part of the committed corpus contract, the schema and labeling guide would need to be amended in the same feature.
5. The future evaluator should show that the degraded-body fixture has high OCR confidence but fails the semantic/table quality gate.

### Interaction With Existing Gates

1. Feature 019 FR-005 remains a lightweight OCR-only sufficiency check based on token count and mean detector confidence. This feature does not rewrite that trigger retroactively.
2. Feature 020 remains a vendor-identity gate over page-1 header-band evidence. It does not certify body rows, line items, totals, or table structure.
3. Feature 021 remains a GPU validation and promotion slice. It does not broaden product behavior into table quality.
4. If a future run claims whole-invoice OCR quality, feature `022` should decide whether skip-fallback is blocked or separately reviewed when the semantic/table quality gate fails.
5. When a run is explicitly vendor-identity-only, a table/body quality failure could be reported as out-of-scope informational evidence rather than blocking vendor-identity acceptance.

## Success Criteria

1. A fixture with readable header vendor identity but degraded table body fails the semantic/table quality gate even if mean OCR confidence is high.
2. The failure reason identifies at least one concrete issue from missing quantities, malformed currency, row alignment, or text mismatch.
3. Existing vendor-identity-only acceptance remains unchanged unless the operator selects a whole-invoice/table-quality mode.
4. The feature introduces no new canonical artifact schema changes unless the Speckit plan explicitly approves a contract amendment.
5. The evaluator can report the semantic/table gate result in a way that a reviewer can reproduce from recorded OCR output and labeled truth.

## Open Decisions For Speckit

1. Should table/body truth live in `expected.json`, a new optional fixture file, or evaluator-only data?
2. Should the gate run only inside the harness/evaluator, or should it also affect runtime fallback decisions?
3. What is the minimal column set for stage 1 table-quality fixtures: quantity, description, unit price, amount, or a broader invoice row model?
4. Should malformed currency be a hard fail for table-quality, or one weighted signal inside an aggregate verdict?
5. What operator-facing surface records the verdict without adding noise to vendor-identity-only runs?

## Speckit Specify Seed

Use this prompt when opening the follow-up feature:

```text
Create feature 022-ocr-semantic-quality-gate. The feature addresses a GPU calibration finding where a degraded invoice body produced high Paddle OCR confidence but incorrect table rows. Stage 1 vendor identity remains the MVP boundary; do not rewrite feature 019/020/021 behavior in place. Add deterministic semantic/table OCR quality checks that can flag missing quantities, malformed currency such as colon-for-decimal, row-alignment gaps, and table-body text mismatches. The gate must treat OCR confidence as a signal, not proof of correctness. It must preserve vendor-identity-only acceptance when the header is sufficient, but any future whole-invoice/table-quality claim must fail or require fallback/review when the table-quality gate fails. Define the fixture and evaluator contract for a degraded-body hard document, preferably inv_024_hard or the next available hard fixture after labeling-guide screening. Avoid new runtime dependencies and avoid canonical artifact schema changes unless the plan explicitly approves a contract amendment.
```
