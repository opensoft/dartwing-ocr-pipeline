# Feature Specification: Harness Baseline Readiness

**Feature Branch**: `013-harness-baseline-readiness`  
**Created**: 2026-05-05  
**Status**: Draft  
**Input**: User description: "Make the merged stage 1 harness-controller path ready to run against the committed corpus before adding benchmark helpers. Resolve the document_id mismatch between committed expected.json labels that use full folder names like inv_001_easy and the pipeline controller output that currently derives inv_001, update the authoritative docs/specs/code so one rule is enforced consistently, add a smoke test proving evaluator --run-pipeline works on an unmodified committed corpus document, and replace real full-workstation dependency tracebacks such as missing PIL with clear preflight/operator errors. Keep artifact schemas unchanged and preserve the evaluator/pipeline runtime boundary."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Evaluate A Committed Corpus Document Without Edits (Priority: P1)

A developer can run the merged evaluator harness path on a committed stage 1 corpus document without rewriting `expected.json` in a temporary copy.

**Why this priority**: Feature 012 is not useful for real corpus baselines until pipeline output `document_id` values match the committed truth labels.

**Independent Test**: Copy one committed corpus folder unchanged, run evaluator document mode with `--run-pipeline --pipeline-overwrite`, and verify `evaluation_document.json` is produced rather than a document-id mismatch error.

**Acceptance Scenarios**:

1. **Given** a committed corpus folder such as `inv_001_easy`, **When** the harness runs the pipeline before evaluation, **Then** the generated final payload and `expected.json` agree on the same `document_id`.
2. **Given** all stage 1 corpus folders, **When** a validation check compares folder names, expected labels, and pipeline-derived IDs, **Then** one documented rule is applied consistently across all folders.

---

### User Story 2 - Preserve Corpus Contract Clarity (Priority: P2)

A developer reading the docs, Speckit artifacts, and code can identify exactly whether stage 1 `document_id` means the full folder name or the numeric prefix.

**Why this priority**: The repository currently contains conflicting guidance: current labels and the labeling guide use full folder names, while older artifacts describe the numeric prefix.

**Independent Test**: Review the updated docs/spec references and run the relevant validator or unit tests; no two authoritative sources define incompatible `document_id` derivation rules.

**Acceptance Scenarios**:

1. **Given** the labeling guide, corpus specs, and pipeline path-resolution code, **When** a developer checks the `document_id` rule, **Then** each source describes the same value.
2. **Given** existing committed `expected.json` files, **When** the feature is complete, **Then** schema compatibility is preserved and no artifact schema version bump is required.

---

### User Story 3 - Fail Clearly When Real Runtime Dependencies Are Missing (Priority: P3)

A developer can attempt a real `full-workstation` harness run and receive an operator-facing preparation error instead of a Python traceback for missing local runtime dependencies.

**Why this priority**: The first full-workstation baseline attempt failed on missing `PIL` before OCR began. The harness should make runtime readiness actionable before benchmark work begins.

**Independent Test**: In an environment missing a required preprocessing dependency, run a real-profile harness preparation and verify the command returns a hard preparation failure with a concise missing-dependency message.

**Acceptance Scenarios**:

1. **Given** a real preprocessing profile is selected and a required local dependency is unavailable, **When** the harness invokes the pipeline, **Then** stderr names the missing dependency and the affected profile/stage without a raw traceback.
2. **Given** stub profiles are selected, **When** the harness runs, **Then** no real-runtime preflight dependency blocks the deterministic test path.

### Edge Cases

- A folder name does not match the stage 1 corpus pattern.
- A committed `expected.json` value disagrees with the selected `document_id` rule.
- A pipeline run starts from a later stage and reads existing prerequisite artifacts stamped with the older ID rule.
- Real runtime dependencies are absent in `py-bench` but present in the pipeline devcontainer or workstation environment.
- Missing dependencies occur in extraction rather than preprocessing.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The project MUST define one authoritative stage 1 corpus `document_id` rule across docs, specs, validator expectations, pipeline path resolution, and evaluator behavior.
- **FR-002**: The selected `document_id` rule MUST be compatible with the committed `tests/stage1_vendor_identity/*/expected.json` labels unless a deliberate migration updates all labels in the same feature.
- **FR-003**: The evaluator `--run-pipeline` document path MUST work on at least one unmodified committed corpus document in stub-safe mode.
- **FR-004**: The evaluator `--run-pipeline` corpus path MUST be able to prepare and evaluate committed corpus folders without document-id mismatch caused by controller-derived IDs.
- **FR-005**: The feature MUST preserve existing artifact schemas and filenames.
- **FR-006**: The feature MUST preserve the evaluator/pipeline runtime boundary; the evaluator still invokes the pipeline controller through the public CLI path.
- **FR-007**: Real-profile missing dependency failures MUST be reported as structured/operator-facing preparation failures rather than uncaught tracebacks.
- **FR-008**: Stub-safe pipeline preparation MUST NOT require real OCR, model runtime, network, GPU, or optional preprocessing dependencies.
- **FR-009**: Tests MUST cover both the fixed document-id rule and the real-runtime missing-dependency error path.
- **FR-010**: Documentation updates MUST identify any prior conflicting guidance and replace it with the selected rule.

### Key Entities *(include if feature involves data)*

- **Corpus Document ID**: The stable identifier shared by folder naming, `expected.json`, generated pipeline artifacts, and evaluation outputs.
- **Committed Corpus Folder**: A folder under `tests/stage1_vendor_identity/` containing `source.pdf`, `expected.json`, optional notes, and generated artifacts during temp-copy runs.
- **Runtime Dependency Preflight**: A pipeline-side check that reports missing dependencies for selected live profiles before emitting a raw traceback.
- **Harness Baseline Smoke**: A deterministic evaluator run against an unmodified corpus document using stub-safe pipeline profiles.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A stub-safe evaluator document run succeeds on an unmodified copy of `tests/stage1_vendor_identity/inv_001_easy`.
- **SC-002**: A stub-safe evaluator corpus run can complete preparation and evaluation for committed corpus folders without document-id mismatch.
- **SC-003**: A real `full-workstation` preparation attempt in an environment missing `PIL` or equivalent OCR dependencies reports a concise missing-dependency error and exits non-zero without a Python traceback.
- **SC-004**: No JSON artifact schema files are changed.
- **SC-005**: Relevant tests pass in `py-bench` without installing OCR/model dependencies.

## Assumptions

- The current committed corpus labels use full folder names as `document_id`; this feature should either preserve that rule or explicitly migrate all labels and docs.
- Benchmark/rerun helpers should wait until the committed corpus can run through the merged harness-controller path.
- Real OCR/model dependency installation is environment setup, not the responsibility of this feature.
- This feature may update old Speckit documentation when it conflicts with current corpus labeling, but it should not rewrite completed feature history beyond what is necessary to remove active ambiguity.
