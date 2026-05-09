# Failure-Handling Checklist: PPStructureV3 Module And Model Reduction

**Purpose**: Validate that requirements covering warn-and-proceed, fail-fast, downstream-dependency conflict, blank-output regression, deferred-verification discipline, and instrumentation-failure modes are complete, clear, and consistent. This is a release-gate checklist.
**Created**: 2026-05-09
**Feature**: [spec.md](../spec.md)

## Warn-and-Proceed Discipline (switch on wrong profile)

- [x] CHK001 - Is the warn-and-proceed contract for the module-disable switch on `ppstructurev3@cpu` enumerated as four required behaviors (warn + no disable + proceed normally + same exit status)? [Completeness, Spec §FR-013, Edge Cases]
- [x] CHK002 - Is the warn-and-proceed contract for the model-variant switch on `ppstructurev3@cpu` stated identically to the module-disable switch's contract? [Consistency, Spec §FR-013, Edge Cases]
- [x] CHK003 - Is the stub adapter explicitly subject to the same warn-and-proceed contract as `ppstructurev3@cpu`? [Consistency, Spec §FR-013]
- [x] CHK004 - Is "clear stderr warning" specified concretely enough to be machine-grep-able (format, message keyword, marker line)? [Clarity, Spec §FR-013]
- [x] CHK005 - Is the prohibition on silent-ignore explicit and named alongside the prohibition on silent CPU fallback? [Completeness, Spec §FR-013]
- [x] CHK006 - Is the prohibition on rejection (refusing the run with a non-zero exit when the switch is set on CPU/stub) explicit and consistent with FR-013's "exits with the same status it would have produced without the switch"? [Consistency, Spec §FR-013]
- [x] CHK007 - Is "exits with the same status it would have produced without the switch" measurable across the six argv permutations (CPU/GPU/stub × switch-set/switch-unset)? [Measurability, Spec §FR-013, SC-004]
- [x] CHK008 - Is the relationship between FR-013 and feature 016 FR-010 (`--gpu-warmup` precedent) explicit so reviewers can verify consistency? [Traceability, Spec §FR-013]

## Fail-Fast Discipline (GPU bind / runtime failure)

- [x] CHK009 - Is the fail-fast contract when a selected configuration's model weights or runtime fail to bind on GPU explicit (no silent CPU fallback)? [Completeness, Spec §FR-007, Edge Cases]
- [x] CHK010 - Is "the exit reason MUST identify the configuration that failed" measurable (does the spec name the identifier values that must appear, e.g., `module_set_id`, `det_rec_variant_id`)? [Clarity, Spec §Edge Cases]
- [x] CHK011 - Is the relationship to feature 015 FR-008 ("no silent CPU fallback after `ppstructurev3@gpu` is selected") explicit? [Consistency, Spec §FR-007, FR-021]
- [x] CHK012 - Is the contract for an unknown / typo'd `module_set_id` value (e.g., `reduced-v99`) defined (fail fast vs. fall back to legacy vs. warn-and-proceed)? [Gap]
- [x] CHK013 - Is the contract for an unknown / typo'd `det_rec_variant_id` value defined? [Gap]
- [x] CHK014 - Is the contract for both switches set simultaneously to incompatible values (if any combinations exist) defined? [Gap]

## Module-Dependency Conflict (downstream needs a disabled module)

- [x] CHK015 - Is the priority rule explicit: when the reduced module set would remove a field a downstream stage depends on, the offending sub-module MUST stay enabled? [Clarity, Spec §FR-004, Edge Cases]
- [x] CHK016 - Is "downstream consumer depends on this sub-module" defined operationally (a mapping from PPStructureV3 sub-module to the `preprocess_output.json` fields it produces) or is the deferral to plan explicit? [Gap, Spec §FR-004]
- [x] CHK017 - Is the conflict-resolution outcome enumerated (sub-module re-enabled in the preset, OR `reduced-v1` rejected for that field's downstream-using deployment)? [Clarity, Spec §FR-004]

## Blank-Output Regression (reduced module set produces empty preprocess_output)

- [x] CHK018 - Is "reduced module set produces an empty/blank `preprocess_output.json`" defined as a regression of FR-003? [Completeness, Spec §Edge Cases]
- [x] CHK019 - Is "empty/blank" defined operationally — zero pages? zero blocks? a schema-required field missing? schema validates but downstream cannot use? [Clarity, Gap]
- [x] CHK020 - Is the rollback action explicit: the reduced configuration is rejected and the legacy module set is kept as the GPU default until the regression is resolved? [Clarity, Spec §Edge Cases]
- [x] CHK021 - Is the relationship between blank-output rejection (Edge Cases) and quality-gate failure (FR-015) consistent (both keep legacy default; neither flips it)? [Consistency]

## Lighter-Variant Side-Effect Containment

- [x] CHK022 - Is the prohibition on lighter variants changing per-document `phase_timings` shape stated identically to feature 015's keys + feature 016's `warmup`? [Consistency, Spec §Edge Cases]
- [x] CHK023 - Is the prohibition on lighter variants altering existing `run_summary` fields explicit (not just additive new fields)? [Consistency, Spec §FR-009]
- [x] CHK024 - Are network/download failure modes for lighter-variant weight downloads addressed, or explicitly deferred to plan? [Gap]
- [x] CHK025 - Are timeout / hang failure modes for benchmark runs on the GPU lane addressed, or explicitly deferred? [Gap]

## Operator Override (legacy stays selectable post-promotion)

- [x] CHK026 - Is the operator-override contract (override new GPU default back to the legacy default) explicit? [Completeness, Spec §Edge Cases, FR-017]
- [x] CHK027 - Is the override mechanism the same explicit configuration switch this feature introduces (not a separate flag) per FR-017? [Consistency, Spec §FR-017, Edge Cases]
- [x] CHK028 - Is "operator can still invoke the legacy configuration by explicit selection" measurable (a specific CLI-flag / env-var invocation can be tested)? [Measurability, Spec §FR-017]

## GPU-Verification Deferral Discipline (FR-024)

- [x] CHK029 - Is the GPU-verification-deferral contract (FR-024) explicit and bounded? [Completeness, Spec §FR-024]
- [x] CHK030 - Is the deferral set enumerated by FR-number (FR-001 audit, FR-005 benchmark, FR-008-related GPU `run_summary` checks, FR-015 promotion-gate verification)? [Coverage, Spec §FR-024]
- [x] CHK031 - Is the prohibition on "quietly skipping the deferred verification" explicit (deferral MUST be captured in tasks and quickstart)? [Completeness, Spec §FR-024]
- [x] CHK032 - Is the relationship to feature 016 FR-014 (deferral precedent) explicit? [Traceability, Spec §FR-024]

## Instrumentation Failure Modes (FR-001 audit)

- [x] CHK033 - Is the failure mode for the FR-001 audit itself defined (what happens if the live-path instrumentation cannot observe a sub-module invocation — fail fast? emit empty list? log warning?)? [Gap, Spec §FR-001]
- [x] CHK034 - Is the failure mode for `ppstructure_modules_invoked` emission when instrumentation throws specified (or explicitly bounded by the run's normal exit-code envelope)? [Gap]

## Coverage Discipline

- [x] CHK035 - Are the conditions under which the legacy default is preserved (gate fails on either metric, blank output, missing-field regression, missing GPU bind, FR-024 deferral) listed exhaustively in one place? [Coverage]
- [x] CHK036 - Is the warn-and-proceed path verifiable on the default (no-GPU) test suite per FR-023? [Coverage, Spec §FR-023, SC-005]
