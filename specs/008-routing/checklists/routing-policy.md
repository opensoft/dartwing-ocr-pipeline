# Routing-Policy Checklist: Deterministic Routing (Stage 1)

**Purpose**: Release-gate validation that the spec pins the routing rule set,
canonical vocabulary, priority semantics, and policy-version lifecycle with
the rigor needed to tell two rule sets apart across runs. Every item
validates the **requirements**, not the implementation.
**Created**: 2026-04-21
**Feature**: [spec.md](../spec.md)
**Depth**: Release gate
**Audience**: Reviewer (PR + policy owner + evaluator owner)

## `policy_version` Lifecycle

- [x] CHK001 Is `policy_version` required to be a non-empty string and pinned as an identifier of the rule set applied? [Clarity, Spec §FR-005 §US1 AC#2]
- [x] CHK002 Is `policy_version` kept orthogonal to `pipeline_version` (one identifies rules, the other identifies build)? [Consistency, Spec §FR-005 §Key Entities]
- [x] CHK003 Are the exact trigger conditions for a `policy_version` bump enumerated (rule addition, rule removal, threshold change, canonical reason-string change, spam-gate threshold change)? [Completeness, Spec §FR-005 §SC-010 §US4 AC#3]
- [x] CHK004 Is the rule "zero routing rule changes ship without a corresponding `policy_version` change" stated as a success criterion? [Measurability, Spec §SC-010]
- [x] CHK005 Does the spec describe how mid-corpus policy changes are reconciled (each artifact records the policy in effect; older artifacts are not retroactively re-routed)? [Completeness, Spec §Edge Cases]
- [x] CHK006 Is the specific initial `policy_version` string left to plan/research rather than hard-coded in the spec (and is that deferral explicit)? [Gap — deferred to plan; Spec §FR-005]

## Missing-Name Invariant (Principle IV)

- [x] CHK007 Is the constitutional invariant wired directly into the spec as a hard rule (`company_name.inferred == true` OR `company_name.present == false` → `edge_review_required` + `"company_name_inferred"`)? [Clarity, Spec §FR-008 §US2 AC#1 AC#2]
- [x] CHK008 Is the canonical reason string `"company_name_inferred"` pinned with "zero variants" language (not `"name_inferred"` or `"vendor_name_inferred"`)? [Clarity, Spec §FR-008 §US2 AC#1]
- [x] CHK009 Is the rule "secondary-identifier strength does NOT override the missing-name gate" stated explicitly? [Clarity, Spec §US2 AC#4 §Edge Cases]
- [x] CHK010 Is the rule "the router NEVER accepts a document whose company name is inferred or missing" stated? [Clarity, Spec §US2 AC#5]
- [x] CHK011 Is the cross-feature coordination with the evaluator (007 US4) called out explicitly, pinning the reason string as load-bearing? [Traceability, Spec §US2 §Assumptions §SC-008]

## Priority Order for `review_reason`

- [x] CHK012 Is the four-level priority order pinned (1 missing-name → 2 spam-gate → 3 secondary-identifier deficit → 4 upstream-failure)? [Clarity, Spec §FR-015 §Key Entities]
- [x] CHK013 Is the rule "highest-priority firing rule supplies `review_reason`; all firing rules appear in `reasons`" stated? [Completeness, Spec §FR-015 §US3 AC#6 §US4 AC#4]
- [x] CHK014 Is priority conflict behavior illustrated with at least one multi-rule case (e.g., spam-gate AND missing-name both fire)? [Coverage, Spec §US4 AC#4 §US3 AC#6]

## Canonical Forcing-Rule Vocabulary

- [x] CHK015 Are all four forcing-rule canonical strings named and pinned (`"company_name_inferred"`, `"post_extraction_spam_gate_failed"`, `"secondary_identifiers_insufficient"`, `"upstream_extraction_failed"`)? [Completeness, Spec §FR-015 §Key Entities]
- [x] CHK016 Is the rule "forcing-rule strings are part of `policy_version`; renaming requires a bump" stated? [Clarity, Spec §FR-005 §SC-010]
- [x] CHK017 Is each forcing-rule trigger condition precisely specified (e.g., spam-gate fires when every structural field is null)? [Clarity, Spec §FR-008 §FR-013 §FR-014 §FR-020]

## Affirmative & Informational Vocabulary

- [x] CHK018 Does the spec require `edge_accept` decisions to carry at least one affirmative `reasons` entry (not silent)? [Clarity, Spec §FR-016 §US1 AC#5]
- [x] CHK019 Does the spec require affirmative reasons to name the affirmative conditions met (e.g., "secondary identifier floor met with address + email")? [Clarity, Spec §FR-016]
- [x] CHK020 Are the affirmative string set and informational string set pinned at spec level, or explicitly deferred to plan/policy? [Gap, Spec §FR-016]
- [x] CHK021 Does the spec require every `edge_accept` document to carry `company_name_present == true AND company_name_inferred == false` in `checks`? [Clarity, Spec §US2 AC#5]

## Secondary-Identifier Floor

- [x] CHK022 Is the floor threshold pinned (`>= 2` of the secondary-identifier slots)? [Clarity, Spec §FR-014 §US3]
- [x] CHK023 Is the set of slots counted toward the floor enumerated (`address_has_minimum_components`, `at_least_one_tax_id_present`, `website_or_email_present`, and phone-grounded as an independent slot)? [Completeness, Spec §FR-014 §US3 AC#3]
- [x] CHK024 Is `address_has_minimum_components` definition pinned (`city AND state AND postal_code` all grounded)? [Clarity, Spec §FR-010 §US3 AC#4 §Edge Cases]
- [x] CHK025 Is the rule "unevidenced tax IDs do not count" stated (grounded = non-null value AND non-empty evidence)? [Clarity, Spec §FR-011 §US3 AC#5]
- [x] CHK026 Is the rule "website and email count together as one slot, not two" stated? [Clarity, Spec §FR-012 §Edge Cases]
- [x] CHK027 Is the rule "multiple tax IDs populated still count as one floor slot, not multiple" stated? [Clarity, Spec §Edge Cases]
- [x] CHK028 Is the phone-grounded slot's independence from `website_or_email_present` called out? [Clarity, Spec §FR-014 §Edge Cases]

## Post-Extraction Spam Gate

- [x] CHK029 Is the spam-gate trigger condition pinned (every structural field null simultaneously)? [Completeness, Spec §FR-013 §US4 AC#1]
- [x] CHK030 Is the rule "spam-gate threshold change bumps `policy_version`" stated? [Clarity, Spec §FR-013 §US4 AC#3 §SC-010]
- [x] CHK031 Does the spec state that the pre-extraction spam gate (Falcon OCR) is not yet wired up and that the post-extraction gate is the only stage 1 spam defense? [Completeness, Spec §Assumptions §US4]

## Rule Separation from Model Confidence

- [x] CHK032 Is the rule "confidence is a signal, not a primary gate on any decision or check" stated? [Clarity, Spec §FR-018 §Clarifications]
- [x] CHK033 Is the rule "confidence MUST NOT affect scores or decisions" stated after the 2026-04-21 clarification? [Consistency, Spec §FR-017 §FR-018 §Clarifications]
- [x] CHK034 Is provenance (`present`/`inferred`) + grounding (evidence arrays) stated as the sole input to gates? [Clarity, Spec §FR-009 §FR-018]

## Rule/Check Boundary

- [x] CHK035 Does the spec state that `checks.company_name_present` and `checks.company_name_inferred` are direct copies from the input, not re-derived? [Clarity, Spec §FR-009]
- [x] CHK036 Does the spec state that routing does NOT re-verify evidence against `preprocess_output.json` and trusts the extractor's reconciliation (FR-010, FR-011 in the extractor)? [Clarity, Spec §Edge Cases]
- [x] CHK037 Does the spec state that realistic-value selection (e.g., a company name that looks like "INVOICE") is not routing's job? [Clarity, Spec §Edge Cases]

## `POLICY_VERSION` Bump Gate (PR-review, not runtime)

This section is the process home for FR-005 / SC-010. The gate is enforced by
reviewers, not by a runtime check or a CI lint — see spec FR-005 for the
authoritative language ("PR-review gate, not a runtime check"). Adding a CI
rule later would require a separate spec or amendment.

- [x] CHK038 Is the rule-layer module list that triggers a required bump enumerated: `src/ledgerlinc_ocr/router/rules.py`, `src/ledgerlinc_ocr/router/checks.py`, `src/ledgerlinc_ocr/router/reasons.py`, `src/ledgerlinc_ocr/router/version.py`, and any canonical reason-string constants? [Completeness, Spec §FR-005]
- [x] CHK039 Is the reviewer's responsibility stated: any PR touching those modules without a corresponding `version.POLICY_VERSION` edit MUST be rejected at review as a quality-gate failure, not a style nit? [Clarity, Spec §FR-005 §SC-010]
- [x] CHK040 Does the spec explicitly label SC-010 as a PR-review gate rather than a runtime check, so reviewers know the enforcement point? [Traceability, Spec §FR-005 §SC-010]
