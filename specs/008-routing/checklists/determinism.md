# Determinism Checklist: Deterministic Routing (Stage 1)

**Purpose**: Release-gate validation that the spec specifies byte-identical,
repeatable routing output with the rigor needed for evaluation stability.
Every item validates the **requirements**, not the implementation.
**Created**: 2026-04-21
**Feature**: [spec.md](../spec.md)
**Depth**: Release gate
**Audience**: Reviewer (PR + evaluation owner)

## Byte-Identical Guarantee

- [x] CHK001 Does the spec state byte-identical reruns as a hard requirement (not just "stable" or "consistent")? [Clarity, Spec §FR-021 §SC-004]
- [x] CHK002 Is the exemption for `processed_at` enumerated explicitly (rather than left implicit)? [Clarity, Spec §FR-021 §US1 AC#6 §SC-004]
- [x] CHK003 Is there a success criterion that quantifies determinism across reruns (two consecutive invocations)? [Measurability, Spec §SC-004]
- [x] CHK004 Does byte-identity cover `decision`, `review_status`, `checks`, `scores`, `reasons` contents, AND the artifact's ordering? [Completeness, Spec §FR-021 §US1 AC#6]

## Inputs Held Constant

- [x] CHK005 Are the inputs that must be held constant for byte-identity enumerated (input JSON contents, `pipeline_version`, `policy_version`)? [Completeness, Spec §FR-021 §SC-004]
- [x] CHK006 Is `processed_at` explicitly the *only* field exempt from byte-identity? [Clarity, Spec §FR-021 §US1 AC#6]
- [x] CHK007 Is the rule "confidence values MUST NOT enter any numeric computation the router emits" stated? [Clarity, Spec §FR-018 §Clarifications]

## Score Formula Determinism

- [x] CHK008 Are all five score formulas pinned with exact rules rather than described qualitatively ("a weighted aggregate")? [Clarity, Spec §FR-017 §Clarifications]
- [x] CHK009 Is `company_name_score`'s binary rule (`1.0` iff explicit + evidenced, else `0.0`) stated? [Clarity, Spec §FR-017]
- [x] CHK010 Is `address_score`'s denominator pinned to a specific integer (5 components) and the component set named? [Clarity, Spec §FR-017]
- [x] CHK011 Is `tax_id_score`'s denominator pinned to 4 and the slot set named (`ein`, `state_tax_id`, `vat_id`, `other_tax_id`)? [Clarity, Spec §FR-017]
- [x] CHK012 Is `contact_score`'s denominator pinned to 3 and the field set named (`website`, `phone`, `email`)? [Clarity, Spec §FR-017]
- [x] CHK013 Is `overall_vendor_identity_score`'s aggregation rule pinned (equal-weight arithmetic mean of the four per-category scores)? [Clarity, Spec §FR-017]
- [x] CHK014 Is "grounded" defined with one canonical rule (non-null `value` AND non-empty `evidence`) that all score formulas share? [Consistency, Spec §FR-017 §Clarifications]

## `reasons` Array Ordering

- [x] CHK015 Is the `reasons` array order pinned to the FR-015 priority order (missing-name → spam-gate → secondary-identifier deficit → upstream-failure), not left to implementation order? [Clarity, Spec §FR-015 §Clarifications]
- [x] CHK016 Is the ordering of affirmative entries (for `edge_accept`) fixed, not arbitrary? [Clarity, Spec §FR-015 §FR-016]
- [x] CHK017 Is the ordering of informational entries (upstream-partial, contract-violation) fixed? [Clarity, Spec §FR-015]
- [x] CHK018 Is the rule "same input → same reasons array byte-for-byte across reruns" stated? [Completeness, Spec §FR-021 §SC-004]

## `checks` and Output Key Order

- [x] CHK019 Does the spec indicate that the `checks` block uses the schema's `required` key order, not an implementation-dependent order? [Consistency, Spec §FR-002]
- [x] CHK020 Is the rule "two runs produce byte-identical `checks` content and ordering" stated? [Completeness, Spec §FR-021]
- [x] CHK021 Is the rule "two runs produce byte-identical `scores` content and ordering" stated? [Completeness, Spec §FR-021]

## Processed-At Exception

- [x] CHK022 Is `processed_at`'s format described with enough precision to constrain it (e.g., ISO-8601 date-time) rather than left open-ended? [Clarity, Spec §FR-021 §US1 AC#2]
- [x] CHK023 Is the rule "`processed_at` variance is allowed across reruns; all other variance is forbidden" stated? [Clarity, Spec §FR-021 §US1 AC#6]

## Policy and Pipeline Version Stability

- [x] CHK024 Is `policy_version` required to be identical across reruns when the rule set is unchanged? [Consistency, Spec §FR-005 §FR-021]
- [x] CHK025 Is `pipeline_version` required to be identical across reruns for the same build? [Consistency, Spec §FR-005 §FR-021]
- [x] CHK026 Does the spec state that byte-identity holds under repeated invocation of the default `--pipeline-version` and `--policy-version` values? [Completeness, Spec §FR-021]

## Reconstructibility (Determinism's Reviewer-Facing Face)

- [x] CHK027 Does the spec require that every decision be reconstructible from the artifact alone (no external state, no logs)? [Completeness, Spec §SC-005 §SC-009 §US5 AC#6]
- [x] CHK028 Does the spec require that the `reasons` array name every rule that fired (not just the highest-priority one)? [Completeness, Spec §FR-015 §US1 AC#5]
