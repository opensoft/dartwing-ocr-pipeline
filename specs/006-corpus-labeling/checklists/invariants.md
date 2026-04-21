# Labeling Invariants Requirements Quality Checklist

**Purpose**: Pre-release gate. Validate that requirements governing the constitution-bound labeling invariants — missing-name provenance (FR-007, FR-008), `document_id` / `difficulty` agreement (FR-005), null-vs-empty-string (FR-009), schema closure and no-prediction-data (FR-010), verbatim labeling (FR-018) — are complete, measurable, and internally consistent. These are the invariants most likely to silently bias every downstream evaluation, so the *requirements* need to be as hard to misread as possible.
**Created**: 2026-04-20
**Feature**: [spec.md](../spec.md)
**Depth**: Deep (every invariant-bearing FR, SC, edge case, and schema coupling cross-checked).

**T074 post-ship tick-through (2026-04-21)**: The labeling guide resolves some items (e.g., header-vs-footer name handling in §8). Remaining open items are spec-level edge-case gaps — combined-edge-cases (explicit name + logo + remit differ), multi-language invoices, whitespace/control-character name handling — that are outside the current corpus (all 20 docs are English and single-form). Deferred to a future spec clarification round when such fixtures are added.

## Requirement Completeness

- [x] CHK001 Are all three components of the missing-name triad (`company_name.present`, `company_name.inferred`, `expected_review.manual_review_required`) stated together in one place, or scattered across FRs? [Completeness, Spec §FR-008]
- [x] CHK002 Is `expected_review.review_reason == "company_name_inferred"` stated as a literal frozen string that cannot vary? [Clarity, Spec §FR-008]
- [x] CHK003 Are requirements stated for what `company_name.value` contains on a missing-name doc when no inference is defensible (null only, or empty-string allowed)? [Completeness, Spec §FR-008, §FR-009]
- [x] CHK004 Does the spec enumerate every optional field where `null`-not-`""` applies, or only give examples? [Completeness, Spec §FR-009]
- [x] CHK005 Are requirements defined for the `country` field when the document has no explicit country-of-origin mark? [Gap, Spec §FR-009]
- [ ] CHK006 Is "verbatim from the source document" (FR-018) defined precisely enough to decide whether to preserve or strip OCR artifacts, trailing whitespace, unicode variants? [Clarity, Spec §FR-018]
- [ ] CHK007 Are requirements stated for which normalizations happen at label time vs. scoring time, as a complete list (not just "per scoring.md")? [Completeness, Spec §FR-018]
- [x] CHK008 Does the spec enumerate every piece of prediction-side data that is forbidden in `expected.json` (FR-010), or is the list illustrative? [Completeness, Spec §FR-010]
- [ ] CHK009 Are requirements defined for the `notes` key (inside `expected.json`) — what content is allowed, what is not? [Gap, Schema]
- [x] CHK010 Does the spec state that `document_id` and `difficulty` in `expected.json` must match the folder name byte-for-byte (casing, underscores)? [Clarity, Spec §FR-005]
- [x] CHK011 Is "no keys outside the schema" (FR-010) backed by a specific `additionalProperties: false` contract reference? [Traceability, Spec §FR-010, Contract]
- [x] CHK012 Are requirements stated for `tax_ids.*` when an invoice has a tax ID whose type is ambiguous (e.g., could be EIN or other)? [Gap, Spec §Edge Cases]

## Requirement Clarity

- [x] CHK013 Is "explicit company name" defined precisely enough to distinguish it from logo-text, footer-only, and address-only cases? [Clarity, Spec §FR-007, §Edge Cases]
- [x] CHK014 Is the "faint-but-present name = `hard`, not `missing_name`" rule stated in a form a labeler cannot rationalize around? [Clarity, Spec §Edge Cases]
- [x] CHK015 Is "not renamed to a parent entity" in US2 Scenario 2 testable or discretionary? [Clarity, Spec §US2]
- [ ] CHK016 Is "normalized for legibility only" enumerated (which normalizations qualify) or open-ended? [Ambiguity, Spec §US2]
- [ ] CHK017 Is "label as it appears on the document" (FR-018) unambiguous when the name appears differently in the header versus the footer? [Ambiguity, Spec §FR-018]
- [x] CHK018 Is the DBA rule ("Acme Widgets Inc. dba AcmeWerx") clear on which string to record and whether both go into `value`? [Clarity, Spec §Edge Cases]
- [x] CHK019 Is "address component fields follow the same null-for-missing rule per-field" (US2 Scenario 4) unambiguous when `street_2` is absent but `street_1` is present? [Clarity, Spec §US2]
- [x] CHK020 Is the company-name logo rule ("present=true, inferred=false, logo_only tag") consistent with "company name only appears in a logo, not as text"? [Clarity, Spec §Edge Cases]

## Requirement Consistency

- [x] CHK021 Do FR-007 (non-missing: present=true, inferred=false) and FR-008 (missing: present=false, inferred=true) leave the pair (present=true, inferred=true) legally unreachable in the corpus? [Consistency, Spec §FR-007, §FR-008]
- [x] CHK022 Is the constitution's Principle IV wording identical to the spec's FR-008 wording (no drift)? [Consistency, Spec §FR-008, Constitution §IV]
- [x] CHK023 Does "faint-but-present name is `hard`, not `missing_name`" (Edge Cases) align with FR-016 (`missing_company_name` only on missing-name docs)? [Consistency, Spec §Edge Cases, §FR-016]
- [x] CHK024 Does the `logo_only` rule (Edge Cases: present=true, inferred=false) align with FR-007 for non-missing docs? [Consistency, Spec §Edge Cases, §FR-007]
- [x] CHK025 Does the DBA rule (write as appears) align with FR-018 (verbatim)? [Consistency, Spec §Edge Cases, §FR-018]
- [x] CHK026 Does the null-vs-empty rule (FR-009) align with the schema's `type: ["string", "null"]` for every optional field? [Consistency, Spec §FR-009, Contract]
- [x] CHK027 Are `expected_review.review_reason` values restricted by the spec to known strings (`"company_name_inferred"` on missing), or does the schema allow any string? [Consistency, Spec §FR-008, Contract]

## Acceptance Criteria Quality

- [x] CHK028 Is SC-004 ("100% of missing-name docs satisfy invariants") verifiable by a single schema-plus-rules check? [Measurability, Spec §SC-004]
- [x] CHK029 Is SC-008 ("no predicted values / confidence / verdicts in expected.json") a schema-enforceable invariant (`additionalProperties: false`) or a governance-only guarantee? [Measurability, Spec §SC-008]
- [x] CHK030 Can "verbatim" be objectively measured against a source PDF? [Measurability, Spec §FR-018]
- [x] CHK031 Is "100% of 5 missing_name docs" countable directly from the difficulty distribution? [Measurability, Spec §SC-004]

## Scenario Coverage

- [ ] CHK032 Are requirements defined for a document with explicit name AND logo AND differing remit-to (combined edge cases)? [Coverage, Spec §Edge Cases]
- [x] CHK033 Are requirements defined for a rotated scan where the company name is visible but sideways? [Coverage, Spec §Edge Cases]
- [x] CHK034 Are requirements defined for international invoices with non-US states, VAT-only tax IDs, non-US postal codes? [Coverage, Spec §Edge Cases]
- [x] CHK035 Are requirements defined for a multi-page PDF where vendor identity differs between pages (vendor on page 1, processor on page 2)? [Coverage, Spec §Edge Cases]

## Edge Case Coverage

- [ ] CHK036 Does the spec address a document where the name is spelled two different ways in two places (header vs. footer)? [Coverage, Gap]
- [ ] CHK037 Are requirements defined for a document with explicit name in one language and logo in another? [Coverage, Gap]
- [ ] CHK038 Does the spec address numeric identifiers that could be construed as tax IDs but aren't labeled as such? [Coverage, Gap]
- [ ] CHK039 Are requirements defined for whitespace-only / control-character values in explicit name strings? [Coverage, Gap]

## Dependencies & Assumptions

- [x] CHK040 Is the dependency on `expected.schema.json` explicit in every invariant FR, or assumed? [Dependency, Spec §FR-004, §FR-010]
- [x] CHK041 Is the assumption "scoring.md defines the complete normalization set" validated or implicit? [Assumption, Spec §FR-018]
- [x] CHK042 Does the spec assume the contract-set version stays at `"1.0.0"` for the entire labeling exercise? [Assumption, Spec §Assumptions]

## Notes

- Check items off as completed: `[x]`.
- `[Gap]` = silent. `[Ambiguity]` = stated but underspecified. `[Conflict]` = two statements appear to disagree.
- These are constitution-bound invariants (Principle IV). Any `[Conflict]` or `[Ambiguity]` on items CHK021–CHK027 must be resolved before shipping the corpus.
