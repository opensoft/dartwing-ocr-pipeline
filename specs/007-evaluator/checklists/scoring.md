# Scoring Rubric Requirements Checklist: Evaluator & Reporting

**Purpose**: Validate that every scoring, normalization, partial-match, weighting, and pass-gate requirement in the spec is complete, unambiguous, consistent with `docs/stage1-vendor-identity/scoring.md`, and objectively verifiable. This is a "unit test for English" — it audits the requirements, not the implementation.
**Created**: 2026-04-21
**Feature**: [spec.md](../spec.md)
**Audience**: pre-PR reviewer (standard depth)

## Fields To Score — Completeness

- [x] CHK001 Does the spec enumerate exactly the 18 scored fields from `scoring.md` §Fields To Score, with dotted naming? [Completeness, Spec §FR-004]
- [x] CHK002 Is the canonical iteration order of `field_results` keys pinned to match `scoring.md`, not left to implementation choice? [Clarity, Spec §FR-004 / research.md §11]
- [x] CHK003 Are the three company-name sub-fields (`value`, `present`, `inferred`) each explicitly listed as separately scored, rather than collapsed into one? [Clarity, Spec §FR-004]
- [x] CHK004 Are all four tax-ID sub-fields (`ein`, `state_tax_id`, `vat_id`, `other_tax_id`) listed as individually scored? [Completeness, Spec §FR-004]

## Result Labels — Clarity & Consistency

- [x] CHK005 Are the six result labels (`match`, `partial_match`, `mismatch`, `missing_prediction`, `unexpected_prediction`, `not_applicable`) each defined with a clear, non-overlapping trigger condition? [Clarity, Spec §FR-004]
- [x] CHK006 Is the "both sides null ⇒ `not_applicable`" rule stated consistently across User Stories, Edge Cases, and FRs? [Consistency, Spec §US1 AC#6 / §Edge Cases]
- [x] CHK007 Is the "expected non-null, actual null ⇒ `missing_prediction`" mapping stated without contradicting the "actual null on a nullable field" scenarios? [Consistency, Spec §US1 AC#4]
- [x] CHK008 Does the spec state explicitly that `not_applicable` fields are excluded from both the numerator and denominator of any accuracy computation? [Clarity, Spec §FR-007]

## Normalization Rules — Coverage & Measurability

- [x] CHK009 Does the spec cover every normalization rule enumerated in `scoring.md` §Normalization (company, street, state, postal, website, phone, email, tax IDs) without gaps? [Completeness, Spec §FR-005]
- [x] CHK010 Is each normalization rule stated in a way that can be turned into a deterministic function (no "where reasonable" that isn't bounded)? [Measurability, Spec §FR-005]
- [x] CHK011 Is the canonical set of US state abbreviations/expansions (50 + DC + territories) specified or delegated to a named reference? [Clarity, research.md §1 / Spec §FR-005]
- [x] CHK012 Is the website normalization pipeline (scheme, `www.`, trailing slash, query/fragment) ordered explicitly so two implementations would produce the same canonical form? [Clarity, Spec §FR-005 / research.md §3]
- [x] CHK013 Is phone normalization ("digits only") stated with enough precision that implementations agree on extension handling? [Clarity, Spec §FR-005 / research.md §2]
- [x] CHK014 Are tax-ID normalization obligations ("strip spaces and punctuation") consistent with the partial-match exclusion for tax IDs? [Consistency, Spec §FR-005 vs §FR-006]

## Partial-Match Policy — Boundary Definition

- [x] CHK015 Does the spec enumerate every permitted partial-match case from `scoring.md`, matching the rubric one-for-one? [Coverage, Spec §FR-006]
- [x] CHK016 Is the exclusion list for `partial_match` (booleans, `review_reason`, tax IDs) stated in the spec, not only implied by the rubric? [Completeness, Spec §FR-006]
- [x] CHK017 Is the ZIP-vs-ZIP+4 partial-match rule defined objectively (e.g., "5-digit prefix of 9-digit")? [Measurability, Spec §US3 AC#2 / research.md §4]
- [x] CHK018 Is the "imperfectly normalized street suffix ⇒ partial" rule bounded so two reviewers would classify the same fixture the same way? [Clarity / Ambiguity, Spec §US3 Independent Test]

## Weights & Document Score — Consistency with `scoring.md`

- [x] CHK019 Does the spec anchor field weights to `scoring.md` §Field Weights, not restate them with drift? [Consistency, Spec §FR-007 / Assumptions]
- [x] CHK020 Is the document-score formula `sum(result_value × weight) / sum(applicable_weights)` stated without drift from the rubric? [Consistency, Spec §FR-007]
- [x] CHK021 Are the `scoring.md` recommended result values (`match=1.0`, `partial_match=0.5`, others `0.0`) pinned by the spec as stage-1 defaults? [Clarity, Spec §Assumptions]
- [x] CHK022 Does the spec confirm the weights sum invariant (total=100) so adding or reweighting a field is a checked change? [Measurability / Gap, Spec §SC-010]

## `comparison_summary` Accounting — Post-Clarification Consistency

- [x] CHK023 Does the spec state explicitly that `matched_field_count` counts strict `match` only and excludes `partial_match`? [Clarity, Spec §Clarifications / §FR-011]
- [x] CHK024 Is the formula `field_accuracy = (matched + 0.5 × partial_count) / applicable` pinned in FR-011, with `partial_count` derivable from `field_results`? [Measurability, Spec §FR-011]
- [x] CHK025 Is the identity `applicable = matched + mismatched + missing_pred + unexpected_pred + partial_count` stated or derivable from FR-011 text? [Consistency, Spec §FR-011]

## Pass Gates — Coverage & Conjunction

- [x] CHK026 Is `vendor_identity_passed` defined as a conjunction of `company_name` match + at least 2 secondary identifiers matching, without allowing either to short-circuit? [Clarity, Spec §FR-008]
- [x] CHK027 Is the five-slot secondary-identifier set (address, any tax ID, website, phone, email) pinned, with the address-slot requirement (city + state + postal_code) resolved post-clarification? [Completeness, Spec §FR-008 / §Clarifications]
- [x] CHK028 Is the tax-ID slot rule ("at least one tax_ids sub-field is `match`; never partial") stated without ambiguity? [Clarity, Spec §FR-008 / §FR-006]
- [x] CHK029 Is `review_routing_passed` defined as the conjunction of `manual_review_required` match AND `review_reason` match? [Clarity, Spec §FR-009]
- [x] CHK030 Is `overall_passed` defined as the conjunction of both hard gates AND `document_score >= 0.85`, with no implicit short-circuit via threshold alone? [Consistency, Spec §FR-010 / §US3 AC#7]
- [x] CHK031 Is the 0.85 threshold epsilon behavior stated clearly enough that an auditor can verify "0.849999..." cases? [Clarity, Spec §Edge Cases / research.md §8]

## Missing-Name Invariants — Coverage & Traceability

- [x] CHK032 Are all four missing-name invariants enumerated (company_name.present=false, inferred=true, manual_review_required=true, review_reason="company_name_inferred")? [Completeness, Spec §FR-012]
- [x] CHK033 Does the spec state that matching the inferred value is NOT sufficient when any invariant is violated? [Clarity, Spec §US4 AC#2 / §FR-012]
- [x] CHK034 Are the missing-name invariants cross-referenced back to the constitution (§IV) so reviewers can trace "why" without re-litigating scope? [Traceability / Consistency, Spec §FR-012]
- [x] CHK035 Is the failing-case coverage for missing-name (one invariant violation at a time) required by the spec, not left to test-author judgment? [Completeness, Spec §US4 Independent Test]

## Out-of-Scope Boundaries — Gap Audit

- [x] CHK036 Is failure-category auto-classification (`ocr_miss`, `hallucinated_value`, etc.) explicitly excluded, with a pointer to where it lives? [Coverage, Spec §Assumptions]
- [x] CHK037 Is confidence-calibration analysis explicitly excluded in this feature, with traceability to `scoring.md`? [Coverage, Spec §Assumptions]
- [x] CHK038 Is ensemble-aware scoring (unanimous/majority/split) declared out of scope at the **field** level while still being emitted at the **run** level for single-voter? [Consistency, Spec §FR-016 / §FR-024]

## Notes

- Check items off as completed: `[x]`.
- `[Gap]` items flag requirements that would need to be written — not implementation to-dos.
- If a checklist item is answered with "no / the spec doesn't say", the fix is a spec edit, not a code edit.
