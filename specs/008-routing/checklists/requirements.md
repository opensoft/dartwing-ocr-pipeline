# Specification Quality Checklist: Deterministic Routing (Stage 1 Vendor-Identity)

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-04-21
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- References to frozen contract artifacts (`routing_decision.schema.json`, `edge_extraction_output.schema.json`, `contract_set_version = "1.0.0"`) and the pinned canonical reason strings (`"company_name_inferred"`, `"post_extraction_spam_gate_failed"`, `"secondary_identifiers_insufficient"`, `"upstream_extraction_failed"`) are product-surface anchors, not implementation choices. The router exists to conform to those contracts and to produce exactly those reason strings; naming them is intentional and load-bearing — in particular, `"company_name_inferred"` is coordinated with the evaluator (007-evaluator US4).
- The `policy_version` field is treated as part of the product surface: every rule, threshold, or canonical string change triggers a policy bump. This is stricter than implementation-level versioning and is intentional, because `policy_version` is what lets a reviewer tell routing decisions apart across rule evolutions.
- FR-014 and FR-017 intentionally leave the specific phone-grounded counting convention and the overall-score weighting formula to the plan phase. These are thresholds / formulas rather than behavioral rules; pinning them at spec level would lock the implementation to numbers that are better owned by `policy_version` in code.
- The `"upstream_extraction_failed"` canonical reason is introduced by this spec to give the router a way to propagate upstream failures cleanly; it is not defined elsewhere but is pinned here as part of the stage 1 routing policy.
- SC-008 ties this feature's correctness to the evaluator's `review_routing_passed` rate on the missing-name corpus subset. This is a cross-feature quality claim, but the missing-name rule (FR-008) is the only routing rule necessary to satisfy it, so the claim remains testable against routing alone given hand-labeled missing-name fixtures.
- Items marked incomplete require spec updates before `/speckit.clarify` or `/speckit.plan`.
