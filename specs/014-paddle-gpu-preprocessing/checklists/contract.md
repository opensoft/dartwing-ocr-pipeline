# Contract Additivity & Schema Discipline Checklist: Workstation Paddle GPU Preprocessing Validation

**Purpose**: Validate that contract-additivity requirements (no schema changes, additive `run_summary`, parseable `pipeline_version`) are complete, clear, and consistent before implementation
**Created**: 2026-05-06
**Feature**: [spec.md](../spec.md)
**Domain**: FR-015 / FR-025 schema invariants, `run_summary` schema 0.1.0→0.1.1 additive bump, `pipeline_version` parser contract, `kind: "preflight_readout"` JSON shape policy

> Each item below tests the **requirements**, not the implementation.
> The feature deliberately surfaces new identity through string-level
> additions to existing free-form fields rather than schema changes;
> every place this happens has a contract-quality question.

## Requirement Completeness

- [x] CHK001 - Are the four stage-1 artifact schemas (`preprocess_output`, `edge_extraction_output`, `routing_decision`, `final_structured_payload`) explicitly listed as out-of-scope for change? [PASS, Spec §FR-025 + §Out Of Scope] — FR-025 forbids changes to all four schemas; Out Of Scope reaffirms.
- [x] CHK002 - Is the canonical artifact filename set (e.g., `preprocess_output.json`) enumerated as the closed set FR-013 forbids extending? [PASS, Spec §FR-013] — FR-013 names `preprocess_output.json` as the canonical preprocessing artifact and forbids additional canonical preprocessing filenames.
- [x] CHK003 - Is the `pipeline_version` parser contract defined (regex, expected segments, ordering)? [Resolved, Research R-014.2 §Normative regex] — Research now provides a normative `re.compile` pattern with named capture groups for paddleocr_version, weights_hash7, dpi, and lane_segment.
- [x] CHK004 - Are the rules for parsing `pipeline_version` from older artifacts (no lane segment) defined for the migration period? [Resolved, Data-model §LaneSegment + Research R-014.2 §Backward-compatible parser default + Contracts §1.pipeline_version parsing] — Pre-feature strings parse as `("cpu", None)`; documented in three places.
- [x] CHK005 - Is the `kind: "preflight_readout"` JSON object's amendment policy specified (frozen contract or evolvable)? [PASS, Spec §Key Entities + Contracts §1] — Spec states the readout shape "may evolve without an amendment"; contracts document `schema_version: "0.1.0"` as evolvable.

## Requirement Clarity

- [x] CHK006 - Is "additive" formally defined for `run_summary` schema 0.1.0→0.1.1 (additive = new optional keys only, no field-type changes, no removals)? [Resolved, Research R-014.6 §Formal definition of "additive"] — R-014.6 now contains a four-clause normative definition of "additive".
- [x] CHK007 - Is "no schema field added/removed/repurposed" (FR-015) defined precisely enough to decide whether attaching new semantics to a free-form string (the lane segment in `pipeline_version`) counts as repurposing? [Resolved, Spec §FR-015 + §Clarifications 2026-05-06] — FR-015 now defines "schema" / "schema field" as the JSON-Schema-validated field shape only; free-form string content addition is explicitly permitted.
- [x] CHK008 - Are the rules for when to bump `run_summary` `schema_version` (patch vs. minor vs. major) defined? [Resolved, Research R-014.6 §`schema_version` bump policy] — R-014.6 defines patch/minor/major bump triggers explicitly.
- [x] CHK009 - Is the relationship between `pipeline_version` (free-form string) and `contract_set_version` (1.2.0) clarified — do consumers gate on one, the other, or both? [Resolved, Contracts §1.pipeline_version parsing] — Contracts/cli-contract.md now states the two are orthogonal: `contract_set_version` governs schema validation; `pipeline_version` is a producer-behavior identity string.

## Requirement Consistency

- [x] CHK010 - Are FR-013 (canonical filename), FR-014 (schema validity), FR-015 (no field changes), and FR-025 (no schema change) collectively non-redundant and non-conflicting? [PASS, Spec §FR-013 / §FR-014 / §FR-015 / §FR-025] — Each FR covers a distinct surface (filename / schema validity / field semantics / hard boundary); they layer rather than overlap.
- [x] CHK011 - Does the `kind: "preflight_readout"` "may evolve without amendment" policy align with the `kind: "run_summary"` schema-versioning policy? [PASS, Spec §Key Entities + Research R-014.6] — Both are stdout-only, non-persisted, and use a `schema_version` field for evolution; readout is more permissive (may evolve without amendment) because it has no consumer outside this feature today.
- [x] CHK012 - Are the `LaneSegment` grammar reservation (`gpu<N>` open-ended) and the spec's "no multi-GPU in scope" stance consistent? [Resolved, Spec §Out Of Scope + Research R-014.8] — Out Of Scope now explicitly excludes multi-GPU device selection; R-014.8 reserves the grammar for future work without committing to it.

## Acceptance Criteria Quality

- [x] CHK013 - Can FR-014 ("validates against the active `preprocess_output.schema.json`") be objectively verified via the existing validator? [PASS, Plan §Contract Test Coverage point 1] — Existing `tests/contract_tests/` infrastructure under feature 001 validates all four schemas under contract_set 1.2.0.
- [x] CHK014 - Can the additive guarantee for `run_summary` 0.1.1 be verified by a contract test (e.g., a 0.1.0-shape parser must still parse 0.1.1 output)? [Resolved, Plan §Contract Test Coverage point 4] — Plan now requires `tests/integration/test_runsummary_gpu_timing_fields.py` to assert that a 0.1.0-shape parser parses 0.1.1 output without raising and without losing existing fields.

## Scenario Coverage

- [x] CHK015 - Is consumer behavior defined when an artifact's `pipeline_version` is missing the lane segment (older artifact, or pre-feature artifact)? [Resolved, Data-model §LaneSegment + Contracts §1.pipeline_version parsing] — Pre-feature strings parse as `("cpu", None)` per the backward-compatible default.
- [x] CHK016 - Is consumer behavior defined when an artifact's `pipeline_version` carries an unrecognized lane segment (e.g., `.npu0` written by a future feature)? [Resolved, Data-model §LaneSegment + Research R-014.2 §Forward-compatible parser tolerance] — Unrecognized segments parse as `("unknown", None)` and MUST NOT raise; consumers should warn-and-continue.
- [x] CHK017 - Is consumer behavior defined when `run_summary.schema_version` is `0.1.0` but the producer wrote `0.1.1`-only fields? [PASS, Research R-014.6 §Consumer tolerance contract] — Consumers MUST ignore unknown keys regardless of `schema_version`; producers are obligated to bump `schema_version` when adding fields. The hypothetical mismatch is a producer bug, not an undefined consumer scenario.

## Edge Case Coverage

- [x] CHK018 - Is the contract for `run_summary` consumers' tolerance of unknown keys specified normatively, or only described as "consumers ignore unknown keys" in research? [Resolved, Research R-014.6 §Consumer tolerance contract + Contracts §1.run_summary consumer tolerance] — "MUST ignore unknown keys" is now normative in both research and the CLI contract.
- [x] CHK019 - Are the rules for what triggers a `pipeline_version` change defined (engine SHA bump, lane segment change, paddleocr version change) and is the lane-segment trigger compatible with FR-017's CPU byte-stability? [Resolved, Research R-014.2 §Legitimate triggers + Spec §SC-006] — R-014.2 enumerates a closed list of five triggers; the lane segment is a one-time intentional bump and SC-006 byte-identity is verified post-feature.
- [x] CHK020 - Is the boundary defined between "evolving the freeform `kind: "preflight_readout"` JSON" and "introducing a new persisted artifact" (FR-022 forbids the second)? [PASS, Spec §Key Entities + §FR-004 + §FR-022] — Preflight writes nothing per FR-004; the readout is transient stdout; FR-022 forbids persisted artifacts. Evolving stdout JSON does not introduce a persisted artifact.

## Non-Functional Requirements

- [x] CHK021 - Are the contract-test requirements documented (a contract test must exist that asserts schema unchanged, lane-segment grammar, run_summary additivity)? [Resolved, Plan §Contract Test Coverage] — Plan now enumerates five contract guarantees with named test files: schema unchanged, lane-segment grammar, CPU byte-stability, run_summary additivity, fail-fast 100%.
- [x] CHK022 - Is the documentation update obligation specified for any future `run_summary` schema bump (where do consumers find the changelog)? [Resolved, Research R-014.6 §Documentation update obligation] — Future bumps are documented in the relevant feature's `research.md` and `contracts/cli-contract.md`; no separate top-level CHANGELOG.

## Dependencies & Assumptions

- [x] CHK023 - Is the assumption that `pipeline_version` is treated as opaque by every existing consumer documented or verified? [Resolved, Plan §Existing feature-011 run_summary shape + Plan §Backward compatibility + Contracts §1.pipeline_version parsing] — Documented as an assumption; the lane-segment trigger preserves prefix-matching consumers' invariants.
- [x] CHK024 - Is the dependency on the existing feature-011 `run_summary` shape pinned (which fields exist today and must keep working)? [Resolved, Plan §Existing feature-011 run_summary shape] — Plan now pins the existing keys: `kind`, `schema_version: 0.1.0`, `stack_preset`, `resolved_profiles`, `execution_slice`, `on_failure`, `documents_total`, `documents_succeeded`, `documents_failed`, `profile_initialization_seconds`, `per_document[]` substructure.

## Ambiguities & Conflicts

- [x] CHK025 - Does FR-016's "by encoding them as additional segments in the existing `pipeline_version` string" conflict with FR-025's "MUST NOT change any stage 1 artifact schema" if a strict reader interprets schema to include field-content semantics? [Resolved, Spec §FR-015 / §Clarifications 2026-05-06] — FR-015 now defines "schema" / "schema field" as the JSON-Schema-validated field shape only; adding parseable structure to a free-form string field (`pipeline_version`) is explicitly a content addition, not a schema change. The conflict is resolved by definition.
- [x] CHK026 - Is "schema-valid" (FR-014) interpreted to allow arbitrary string content in `pipeline_version`, or does it require a documented format? [PASS, Spec §FR-015 + Research R-014.2] — FR-015 (post-resolution) clarifies "schema-valid" = JSON-Schema-validated; `pipeline_version` schema is `{"type":"string","minLength":1}` so any non-empty string passes. R-014.2 documents the format consumers should *parse*; the format is a parser convention, not a schema constraint.

## Notes

- This checklist tests requirement quality, not implementation behavior.
- Items marked `[Resolved]` had a wording-only gap patched in spec/plan/research/data-model/contracts during the 2026-05-06 checklist-resolution pass.
- Items marked `[PASS]` were already satisfied by existing artifacts at the time of evaluation.
