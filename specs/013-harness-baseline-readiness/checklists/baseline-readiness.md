# Baseline Readiness Checklist: Harness Baseline Readiness

**Purpose**: Validate that the 013 requirements are complete, unambiguous, and ready for implementation before task generation  
**Created**: 2026-05-05  
**Feature**: [spec.md](../spec.md)

**Note**: This checklist tests the written requirements, not the implementation.

## Requirement Completeness

- [x] CHK001 Are the authoritative `document_id` rule and examples specified for all relevant surfaces? [Completeness, Spec §Clarifications, Spec §FR-001, Spec §FR-002]
- [x] CHK002 Are the affected system boundaries identified without moving evaluator responsibilities into pipeline code or pipeline responsibilities into evaluator code? [Completeness, Spec §FR-006]
- [x] CHK003 Are both primary readiness outcomes covered: committed-corpus evaluation and real-runtime dependency failure shape? [Completeness, Spec §User Stories]
- [x] CHK004 Are schema and artifact filename preservation requirements explicitly stated? [Completeness, Spec §FR-005, Spec §SC-004]

## Requirement Clarity

- [x] CHK005 Is the phrase "full corpus folder name" defined with concrete examples? [Clarity, Spec §Clarifications, Spec §FR-002]
- [x] CHK006 Is stub-safe behavior distinguished from real-profile behavior with clear dependency expectations? [Clarity, Spec §FR-007, Spec §FR-008]
- [x] CHK007 Is the missing-dependency failure requirement specific enough to distinguish operator-facing errors from raw tracebacks? [Clarity, Spec §FR-007, Spec §SC-003]

## Requirement Consistency

- [x] CHK008 Are requirements consistent with the labeling guide rule that `expected.json.document_id` equals the folder name? [Consistency, Spec §FR-002]
- [x] CHK009 Are old conflicting numeric-prefix artifacts explicitly brought into scope for cleanup without rewriting unrelated feature history? [Consistency, Spec §FR-010, Spec §Assumptions]
- [x] CHK010 Are success criteria aligned with functional requirements and user-story independent tests? [Consistency, Spec §Success Criteria]

## Scenario And Edge Coverage

- [x] CHK011 Are document mode and corpus mode both represented in requirements or success criteria? [Coverage, Spec §FR-003, Spec §FR-004]
- [x] CHK012 Are mismatch, malformed folder-name, late-stage artifact, and dependency-location edge cases named? [Coverage, Spec §Edge Cases]
- [x] CHK013 Are acceptance criteria measurable without requiring heavy OCR/model runtime in PR checks? [Measurability, Spec §SC-001, Spec §SC-005]

## Dependencies And Assumptions

- [x] CHK014 Are environment setup responsibilities separated from feature implementation responsibilities? [Assumption, Spec §Assumptions]
- [x] CHK015 Is benchmark/rerun helper work explicitly deferred until baseline readiness is restored? [Dependency, Spec §Assumptions]
