## Context

Feature 019 added an OCR-only fast lane with lightweight sufficiency signals. Feature 020 added a vendor-identity evidence gate over page-1 header-band signals. Feature 021 promoted the GPU MVP path for vendor identity. The completed `govern-ocr-semantic-quality-gap` amendment documents that none of those features certifies invoice body/table OCR correctness.

The next feature should implement the first deterministic semantic/table quality gate while preserving the stage 1 vendor-identity MVP boundary. The gate must live in code and tests at the same time as the active requirements, so the specs do not get ahead of implementation.

## Goals / Non-Goals

**Goals:**

- Implement deterministic table/body OCR quality evaluation for documents with semantic table truth.
- Keep the gate evidence-first: use `preprocess_output.json` and authored truth, not model judgment.
- Keep vendor-identity-only acceptance unchanged when no semantic table truth is present.
- Add a clear report surface so a reviewer can distinguish vendor-identity pass/fail from semantic table quality pass/fail.
- Add contract/schema/test coverage so the new requirements and code land together.

**Non-Goals:**

- Do not rewrite feature 019 FR-005 fallback semantics in place.
- Do not rewrite feature 020 vendor-identity sufficiency or skip-fallback semantics in place.
- Do not make line-item extraction a stage 1 MVP requirement.
- Do not add a learned classifier, new model runtime, network call, or prompt-owned routing decision.
- Do not mutate the existing 20-document vendor-identity baseline corpus without the explicit corpus amendment tasks in this change.

## Decisions

### Decision 1: First implementation is evaluator/harness-owned

The semantic gate runs during evaluation when a document has semantic table truth. It does not alter pipeline preprocessing, extraction, routing, or final payload generation at landing.

Rationale:

- Stage 1 does not yet produce line-item extraction outputs, so a runtime whole-invoice gate would have no stable downstream claim to protect.
- The discovered failure is measurable from `preprocess_output.json` plus labeled truth.
- Keeping the first implementation evaluator-owned avoids silently changing feature 019/020 runtime behavior while still making the quality gap testable.

Alternatives considered:

- Runtime fallback blocker in the pipeline: rejected for this slice because it would couple a new table-quality policy to vendor-identity skip-fallback before the table truth/report contract exists.
- Documentation-only follow-up: rejected because the previous OpenSpec change already handled as-built documentation; this change is for implementation.

### Decision 2: Add an optional authored `semantic_table_truth.json`

Table/body truth lives in a new optional per-document authored file, `semantic_table_truth.json`, rather than inside `expected.json`.

Rationale:

- `expected.json` remains the vendor-identity truth source.
- Table-body truth can evolve without overloading the vendor-identity shape.
- The folder contract can validate the sidecar only when present, preserving the current 20-document baseline.

Alternatives considered:

- Add table rows to `expected.json`: rejected because it would blur vendor identity and whole-invoice/table truth, and would force broad fixture churn.
- Evaluator-only hidden fixture data: rejected because reviewers need committed, validated truth data to reproduce verdicts.

### Decision 3: Add optional semantic quality fields to evaluation reports

`evaluation_document.json` gains an optional `semantic_table_quality` object. `evaluation_run_summary.json` gains optional aggregate semantic-quality metrics and per-document semantic status. The evaluator should emit those fields for newly generated reports, while schemas remain tolerant of existing v1.2 reports that do not contain them.

Rationale:

- Existing evaluation artifacts remain readable.
- New reports expose the semantic result without changing the meaning of `document_pass_fail.vendor_identity_passed`.
- Optional fields avoid forcing immediate regeneration of all committed baseline artifacts.

Alternatives considered:

- New persisted `semantic_quality_report.json`: rejected for the first implementation because it adds another artifact lifecycle when the existing evaluator report is the natural review surface.
- Reusing `field_results`: rejected because table/body quality is a gate over OCR evidence and row truth, not a final-payload vendor field comparison.

### Decision 4: Deterministic checks are explicit and explainable

The initial gate checks for missing required row values, malformed currency shape, row text coverage gaps, and row-alignment failure evidence. OCR confidence is recorded as supporting evidence only and cannot make a failing row pass.

Rationale:

- The calibration finding was high-confidence but wrong body OCR.
- Reviewers need concrete failure categories, not a single opaque score.
- The gate remains code-owned and reproducible.

Alternatives considered:

- Use OCR confidence thresholds alone: rejected because that is the failure mode being fixed.
- Use a model to judge row correctness: rejected by the deterministic-control principle.

### Decision 5: Whole-invoice claims fail independently from vendor identity

When semantic truth is present and the semantic gate fails, the document fails semantic/table quality. Vendor-identity-only pass/fail remains unchanged. Any future whole-invoice/table-quality claim must consult the semantic gate result; feature 020 vendor-identity sufficiency alone is not enough.

Rationale:

- A document can be acceptable for vendor identity and unacceptable for table quality.
- This preserves the current MVP while creating the quality surface needed for later line-item work.

## Risks / Trade-offs

- New truth sidecar may drift from the source PDF -> Mitigation: add validator checks for `document_id`, row shape, normalized currency, and row identifiers.
- Optional report fields could be ignored by older consumers -> Mitigation: document that whole-invoice/table-quality claims must read the semantic field when present.
- Row alignment is hard without full table structure -> Mitigation: start with deterministic row-value and text-coverage evidence, then leave richer table reconstruction to a later feature if needed.
- The feature could accidentally alter vendor-identity gates -> Mitigation: add non-regression tests proving vendor-identity pass/fail and feature 020 observability remain unchanged.

## Migration Plan

1. Promote this OpenSpec change into Speckit feature `022-ocr-semantic-quality-gate`.
2. Add the optional `semantic_table_truth.json` contract and validator support.
3. Add semantic quality module/tests.
4. Wire evaluator document/corpus reporting.
5. Add degraded-body fixtures under test fixtures first; promote canonical corpus folders only through explicit dataset tasks.
6. Update docs and PRD from draft seed to active feature PRD.

Rollback is additive: remove the optional semantic truth/report fields and semantic-quality evaluator wiring. Existing vendor-identity artifacts remain valid because the new report fields are optional and runtime pipeline behavior is not changed.

## Open Questions

- Should canonical degraded-body fixtures live under `tests/stage1_vendor_identity/` once promoted, or under a separate semantic-quality corpus root?
- What exact minimum row-truth shape is enough for the first gate: required values only, required values plus row text, or required values plus approximate row-region anchors?
- Should future runtime fallback/review integration be a later feature after evaluator-only evidence is stable?
