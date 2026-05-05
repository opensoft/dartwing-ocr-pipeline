# Tasks: Harness Baseline Readiness

**Input**: Design documents from `/specs/013-harness-baseline-readiness/`  
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: Required by FR-009 and included before implementation tasks for each affected behavior.

**Organization**: Tasks are grouped by user story so each story can be implemented and validated independently.

## Phase 1: Setup (Shared Readiness)

**Purpose**: Confirm the starting failure modes and locate the exact surfaces that must change.

- [ ] T001 Inventory active `document_id` rule references in `docs/stage1-vendor-identity/`, `specs/006-corpus-labeling/`, `src/ledgerlinc_ocr/pipeline/path_resolution.py`, and `tests/`.
- [ ] T002 [P] Reproduce the committed-corpus document mismatch with evaluator `--run-pipeline` against a temporary copy of `tests/stage1_vendor_identity/inv_001_easy`.
- [ ] T003 [P] Reproduce the real-profile missing-dependency failure shape through the evaluator or pipeline CLI using `tests/stage1_vendor_identity/inv_001_easy`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish the single ID rule and avoid schema/runtime boundary drift before story work.

- [ ] T004 Identify all pipeline call sites that consume `derive_document_id()` in `src/ledgerlinc_ocr/pipeline/cli.py` and `src/ledgerlinc_ocr/pipeline/corpus_run.py`.
- [ ] T005 Ensure `src/ledgerlinc_ocr/pipeline/cli.py` and `src/ledgerlinc_ocr/pipeline/corpus_run.py` continue to use the shared path-resolution helper instead of local numeric-prefix parsing.
- [ ] T006 Confirm no artifact schema files under `contracts/` or `docs/stage1-vendor-identity/schemas.md` require a schema version change.

**Checkpoint**: The repository has one implementation source for deriving the stage 1 corpus `document_id`.

---

## Phase 3: User Story 1 - Evaluate A Committed Corpus Document Without Edits (Priority: P1) MVP

**Goal**: A developer can run the evaluator harness path on an unmodified committed corpus document without document-id mismatch.

**Independent Test**: Copy `tests/stage1_vendor_identity/inv_001_easy` unchanged, run evaluator document mode with `--run-pipeline --pipeline-overwrite`, and verify `evaluation_document.json` is produced.

### Tests for User Story 1

- [ ] T007 [P] [US1] Update path-resolution unit coverage in `tests/pipeline_tests/test_path_resolution.py` for `inv_001_easy -> inv_001_easy` and invalid folder rejection.
- [ ] T008 [P] [US1] Add evaluator document-mode smoke coverage in `tests/evaluator_tests/test_cli.py` using an unmodified copy of `tests/stage1_vendor_identity/inv_001_easy`.
- [ ] T009 [P] [US1] Add warm/corpus preparation coverage in `tests/integration/test_evaluator_pipeline_harness.py` proving committed folders keep full folder-name IDs.

### Implementation for User Story 1

- [ ] T010 [US1] Update `src/ledgerlinc_ocr/pipeline/path_resolution.py` tests and implementation so generated pipeline artifacts use full folder-name IDs.
- [ ] T011 [US1] Update any affected assertions in `tests/pipeline_tests/` and `tests/evaluator_tests/` that assumed numeric-prefix IDs for corpus folder runs.
- [ ] T012 [US1] Validate US1 with `PYTHONPATH=src python -m pytest tests/pipeline_tests/test_path_resolution.py tests/evaluator_tests/test_cli.py tests/integration/test_evaluator_pipeline_harness.py`.

**Checkpoint**: User Story 1 is complete and independently testable.

---

## Phase 4: User Story 2 - Preserve Corpus Contract Clarity (Priority: P2)

**Goal**: Docs, Speckit artifacts, tests, and code all define the same full folder-name `document_id` rule.

**Independent Test**: Review updated references and run ID-related tests; no active source defines numeric-prefix-only IDs for stage 1 corpus folders.

### Tests for User Story 2

- [ ] T013 [P] [US2] Add or update corpus labeling/validator assertions in `tests/contract_tests/test_folder_contract.py` so full folder-name labels are the expected contract.

### Implementation for User Story 2

- [ ] T014 [US2] Update `docs/stage1-vendor-identity/dataset-layout.md`, `docs/stage1-vendor-identity/labeling-guide.md`, and any relevant `docs/stage1-vendor-identity/schemas.md` examples to consistently describe the full folder-name ID rule without changing schemas.
- [ ] T015 [US2] Update conflicting active Speckit artifacts in `specs/006-corpus-labeling/spec.md` and `specs/006-corpus-labeling/data-model.md` to remove numeric-prefix-only guidance.
- [ ] T016 [US2] Validate US2 with targeted `rg` checks plus `PYTHONPATH=src python -m pytest tests/contract_tests/test_folder_contract.py tests/pipeline_tests/test_path_resolution.py`.

**Checkpoint**: User Story 2 is complete and independently testable.

---

## Phase 5: User Story 3 - Fail Clearly When Real Runtime Dependencies Are Missing (Priority: P3)

**Goal**: A real `full-workstation` preparation attempt reports a concise missing-dependency preparation failure instead of a Python traceback.

**Independent Test**: In an environment missing a selected live preprocessing dependency, run real-profile preparation and verify a non-zero, operator-facing message with no raw traceback.

### Tests for User Story 3

- [ ] T017 [P] [US3] Add runner coverage in `tests/pipeline_tests/test_stage_failure_labels.py` for a live adapter factory raising `ModuleNotFoundError`.
- [ ] T018 [P] [US3] Add evaluator coverage in `tests/evaluator_tests/test_cli.py` proving missing-dependency preparation errors omit raw tracebacks.

### Implementation for User Story 3

- [ ] T019 [US3] Update `src/ledgerlinc_ocr/pipeline/runner.py` so stage callable resolution errors are converted to `RunResult` failures with the correct stage and exit code.
- [ ] T020 [US3] Add concise missing-dependency/profile formatting in `src/ledgerlinc_ocr/pipeline/runner.py` while preserving stub-safe imports.
- [ ] T021 [US3] Verify `src/ledgerlinc_ocr/evaluator/pipeline_invocation.py` surfaces the structured pipeline failure without new traceback handling changes.
- [ ] T022 [US3] Validate US3 with `PYTHONPATH=src python -m pytest tests/pipeline_tests/test_stage_failure_labels.py tests/evaluator_tests/test_cli.py`.

**Checkpoint**: User Story 3 is complete and independently testable.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation across the feature contract.

- [ ] T023 Run the quickstart document smoke from `specs/013-harness-baseline-readiness/quickstart.md` in `py-bench`.
- [ ] T024 Run `PYTHONPATH=src python -m pytest tests/pipeline_tests/test_path_resolution.py tests/pipeline_tests/test_stage_failure_labels.py tests/evaluator_tests/test_cli.py tests/integration/test_evaluator_pipeline_harness.py` in `py-bench`.
- [ ] T025 Verify no JSON schema files under `contracts/` or `docs/stage1-vendor-identity/schemas.md` were modified and generated artifacts retain existing filenames.
- [ ] T026 Review `specs/013-harness-baseline-readiness/spec.md`, `plan.md`, `tasks.md`, and checklists for consistency before PR creation.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup completion and blocks user story implementation.
- **User Story 1 (Phase 3)**: Depends on Foundational and is the MVP.
- **User Story 2 (Phase 4)**: Depends on Foundational and may proceed after US1 tests identify exact documentation/test expectations.
- **User Story 3 (Phase 5)**: Depends on Foundational and can proceed independently of US2.
- **Polish (Phase 6)**: Depends on selected user stories being complete.

### User Story Dependencies

- **US1**: Required first because it restores the merged harness-controller baseline path.
- **US2**: Depends on the selected ID rule from US1/Foundation but not on runtime dependency work.
- **US3**: Independent of ID derivation after Foundation; can be worked in parallel with US2.

### Parallel Opportunities

- T002 and T003 can run in parallel after T001.
- T007, T008, and T009 can be drafted in parallel because they target different test surfaces.
- T013 can run in parallel with US1 implementation once the ID rule is confirmed.
- T017 and T018 can run in parallel because they cover runner and evaluator/CLI behavior separately.

## Parallel Example: User Story 3

```text
Task: "Add runner coverage in tests/pipeline_tests/test_stage_failure_labels.py for a live adapter factory raising ModuleNotFoundError."
Task: "Add evaluator or CLI coverage in tests/evaluator_tests/test_cli.py or tests/integration/test_evaluator_pipeline_harness.py proving missing-dependency preparation errors omit raw tracebacks."
```

## Implementation Strategy

1. Complete Setup and Foundational tasks.
2. Deliver US1 first and validate the committed-document smoke.
3. Deliver US2 documentation/spec consistency.
4. Deliver US3 missing-dependency failure handling.
5. Run quickstart and targeted py-bench tests.
