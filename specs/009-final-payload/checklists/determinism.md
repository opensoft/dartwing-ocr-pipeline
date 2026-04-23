# Determinism Checklist: Final Structured Payload Assembly (Stage 1)

**Purpose**: Release-gate validation that the spec's determinism and reproducibility
requirements are written clearly enough to be objectively verified, with no ambiguity that
would allow two builds to drift apart on the same inputs.
**Created**: 2026-04-21
**Feature**: [spec.md](../spec.md)
**Depth**: Release gate
**Audience**: Reviewer (PR + contract owner)

## Byte-Identical Re-runs

- [X] CHK001 Is "byte-identical output across re-runs, except `processed_at`" stated as a top-level invariant with an explicit list of fields it covers? [Completeness, Spec §FR-022, SC-004]
- [X] CHK002 Is `processed_at` explicitly named as the single permitted source of drift between re-runs on the same inputs? [Clarity, Spec §FR-022, US1 AS-4]
- [X] CHK003 Are the scopes where determinism must hold enumerated (vendor_candidate values + confidences, review_status, quality_summary, trace)? [Completeness, Spec §FR-022, US1 AS-4]
- [X] CHK004 Is the determinism guarantee qualified with "identical assembler build" so that a `pipeline_version` bump is not considered a determinism violation? [Clarity, Spec §FR-022, Edge Case §8]

## Policy Version & `pipeline_version`

- [X] CHK005 Is the exact format of `pipeline_version` (`"009-final-payload@<semver>"`) pinned, so two builds emitting the same format can be compared? [Clarity, Spec §FR-007, Clarifications Q2]
- [X] CHK006 Is the mapping between a policy change (formula or ordering) and a required semver bump explicitly stated? [Completeness, Spec §SC-008, Clarifications Q2]
- [X] CHK007 Are "formula change" and "ordering change" defined precisely enough that a reviewer can tell whether a given diff requires a bump? [Clarity, Spec §SC-008]
- [X] CHK008 Is the relationship between `contract_set_version` (frozen) and the semver segment of `pipeline_version` (bumpable) spelled out so they aren't confused? [Consistency, Spec §FR-007 §FR-002]

## `overall_vendor_confidence` Reproducibility

- [X] CHK009 Is the `overall_vendor_confidence` formula specified completely enough to yield the same value across implementations (inputs, weights, aggregation shape, clipping)? [Measurability, Spec §FR-019, Clarifications Q5]
- [X] CHK010 Is the handling of the empty-secondaries case (`mean` defaulting to `0.0`, not `NaN` or error) explicitly specified? [Coverage, Spec §FR-019, US4 AS-6]
- [X] CHK011 Is the rule for which extractor confidences feed the "address" secondary term (mean of `city`, `state`, `postal_code`) fully specified in the spec rather than deferred to the plan? [Completeness, Spec §FR-019]
- [X] CHK012 Does the spec tag the formula with its policy version (`0.1.0`) so any future change lands at a nameable generation? [Traceability, Spec §FR-019, Clarifications Q5]

## `secondary_identifiers_found` Reproducibility

- [X] CHK013 Is the inclusion rule for each identifier (value non-null AND non-empty evidence) specified uniformly across all eight enum values? [Consistency, Spec §FR-020]
- [X] CHK014 Is the `"address"` inclusion rule (city + state + postal_code all grounded) tied to the same definition routing uses (008 FR-010's `address_has_minimum_components`)? [Consistency, Spec §FR-020]
- [X] CHK015 Is the output ordering pinned to the schema enum's declared order (not "any deterministic order") with absent items skipped? [Clarity, Spec §FR-020, Clarifications Q3, US4 AS-5]
- [X] CHK016 Is the empty-array case (`[]` vs. omitted) explicitly specified for the all-null extraction scenario? [Coverage, Spec §US4 AS-6]

## Key Ordering & Serialization

- [X] CHK017 Is the requirement that all top-level keys be present and non-empty stated (no silent omission of optional keys, since the schema has none optional)? [Completeness, Spec §US1 AS-3]
- [X] CHK018 Does the spec assert that two assembler runs on the same inputs with the same build produce outputs that can be compared byte-for-byte (implying a stable serialization convention)? [Measurability, Spec §FR-022, SC-004]

## Performance as a Determinism Adjacent Target

- [X] CHK019 Is the 200 ms wall-clock target framed as an internal performance goal rather than a release gate, so a slower-but-correct build still satisfies determinism requirements? [Clarity, Spec §SC-001]
- [X] CHK020 Is the 100% schema-validation-on-valid-inputs claim across all 20 corpus documents scoped and measurable? [Measurability, Spec §SC-001]
