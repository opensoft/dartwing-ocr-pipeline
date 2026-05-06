# Harness Boundary Requirements Checklist

**Purpose**: Validate requirement quality for harness-controller boundary, corpus preparation, profile selection, and timing metadata before implementation  
**Created**: 2026-05-05  
**Feature**: [spec.md](../spec.md)  
**Focus**: Requirement completeness, boundary clarity, failure semantics, and measurable acceptance criteria  
**Audience**: PR reviewer

**Checklist disposition cleanup (2026-05-06)**: This checklist was used as a pre-implementation boundary review for 012 and left visually unchecked after 012/013 landed. The shipped implementation satisfied these checks through the harness/controller work and baseline-readiness follow-up; boxes are ticked to remove stale open-state signal.

## Requirement Completeness

- [x] CHK001 Are the document-preparation requirements complete for required inputs, generated pipeline artifacts, and generated evaluation output? [Completeness, Spec §User Story 1, Spec §FR-001..FR-004]
- [x] CHK002 Are corpus-preparation requirements complete for document discovery, warm pipeline invocation, aggregation, and summary output? [Completeness, Spec §User Story 2, Spec §FR-002, Spec §FR-011..FR-012]
- [x] CHK003 Are profile-selection requirements complete for stub defaults, stack presets, per-stage overrides, and unsupported combinations? [Completeness, Spec §User Story 3, Spec §FR-005..FR-009]
- [x] CHK004 Are warm timing metadata requirements complete enough to distinguish available timing from benchmark artifacts? [Completeness, Spec §User Story 4, Spec §FR-013..FR-015]

## Requirement Clarity

- [x] CHK005 Is "stub-safe deterministic profiles" defined clearly enough to avoid accidental live OCR, model runtime, network, or GPU dependencies? [Clarity, Spec §FR-005, Plan §Technical Context]
- [x] CHK006 Is the precedence between stack presets and explicit per-stage profiles unambiguous? [Clarity, Spec §FR-008]
- [x] CHK007 Is the distinction between pipeline preparation failure and evaluation comparison failure explicitly defined? [Clarity, Spec §FR-018]
- [x] CHK008 Is the behavior for missing, partial, or absent warm timing metadata unambiguous? [Clarity, Spec §User Story 4, Spec §FR-014]

## Requirement Consistency

- [x] CHK009 Are the spec, plan, and CLI contract consistent that the evaluator owns scoring while the pipeline owns stage execution and profile lifecycle? [Consistency, Spec §FR-016..FR-017, Plan §Constitution Check, Contract §Backward Compatibility]
- [x] CHK010 Are the spec and research consistent that continue-through-failures must avoid scoring unprepared documents? [Consistency, Spec §FR-010..FR-012, Research §Decision 4]
- [x] CHK011 Are artifact filename requirements consistent with the existing four pipeline artifacts and two evaluation outputs? [Consistency, Spec §FR-003..FR-004, Contract §Document Evaluation]
- [x] CHK012 Are stdout/stderr expectations consistent between existing evaluator behavior and new preparation diagnostics? [Consistency, Contract §Corpus Evaluation, Contract §Backward Compatibility]

## Acceptance Criteria Quality

- [x] CHK013 Can each success criterion be objectively verified without live OCR or model runtime dependencies? [Measurability, Spec §SC-001..SC-007]
- [x] CHK014 Are corpus result counts specified clearly enough to measure prepared, evaluated, skipped, and failed documents? [Measurability, Spec §SC-006, Contract §Corpus Evaluation]
- [x] CHK015 Are preparation failure outcomes measurable without changing `evaluation_run_summary.json`? [Measurability, Research §Decision 4, Contract §Corpus Evaluation]

## Scenario Coverage

- [x] CHK016 Are primary document and corpus flows independently specified and testable? [Coverage, Spec §User Story 1, Spec §User Story 2]
- [x] CHK017 Are alternate flows for explicit real-runtime selection covered without weakening default test determinism? [Coverage, Spec §User Story 3]
- [x] CHK018 Are recovery or continuation flows for partial corpus preparation failures addressed? [Coverage, Spec §User Story 2, Research §Decision 4]
- [x] CHK019 Are no-metadata and partial-metadata timing scenarios covered? [Coverage, Spec §User Story 4]

## Edge Case Coverage

- [x] CHK020 Are missing input files and missing generated artifacts addressed in requirements? [Edge Case, Spec §Edge Cases]
- [x] CHK021 Are existing artifacts without overwrite permission addressed in requirements? [Edge Case, Spec §Edge Cases, Spec §FR-019]
- [x] CHK022 Are invalid folders inside a corpus addressed without requiring evaluation schema changes? [Edge Case, Spec §Edge Cases, Research §Decision 4]
- [x] CHK023 Are unsupported local runtime endpoints and unavailable real profiles addressed as preparation failures rather than evaluation failures? [Edge Case, Spec §Edge Cases, Spec §FR-018]

## Dependencies & Assumptions

- [x] CHK024 Are dependencies on the merged 011 top-level pipeline controller explicit and bounded? [Dependency, Spec §Assumptions, Plan §Summary]
- [x] CHK025 Are assumptions about stage 1 corpus layout and existing evaluator comparison inputs documented? [Assumption, Spec §Assumptions]
- [x] CHK026 Are exclusions for new schemas, benchmark artifacts, and moved runtime ownership stated consistently? [Assumption, Spec §FR-015..FR-017, Plan §Constitution Check]
