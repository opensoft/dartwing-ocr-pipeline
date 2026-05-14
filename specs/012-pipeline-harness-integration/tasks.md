# Tasks: Pipeline Harness Integration

**Input**: Design documents from `/specs/012-pipeline-harness-integration/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included because the feature changes user-visible CLI behavior and must preserve deterministic stub-safe harness runs.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add the harness-side invocation seam without changing evaluator behavior yet.

- [X] T001 Create the subprocess pipeline invocation module in `src/dartwing_ocr/evaluator/pipeline_invocation.py`
- [X] T002 [P] Add focused unit tests for command construction and run-summary parsing in `tests/evaluator_tests/test_pipeline_invocation.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Wire shared CLI arguments and corpus subset support needed by all user stories.

- [X] T003 Add shared evaluator CLI pipeline-preparation arguments in `src/dartwing_ocr/evaluator/cli.py`
- [X] T004 Extend `evaluate_corpus` with an internal optional document-folder subset in `src/dartwing_ocr/evaluator/corpus.py`
- [X] T005 [P] Preserve the evaluator import barrier coverage in `tests/evaluator_tests/test_import_barrier.py`

**Checkpoint**: Foundation ready - user story implementation can begin.

---

## Phase 3: User Story 1 - Run And Evaluate One Document (Priority: P1) MVP

**Goal**: One evaluator command can prepare one document through the pipeline and then evaluate it.

**Independent Test**: Run the evaluator document command with `--run-pipeline --pipeline-overwrite` on a temporary labeled document folder and verify pipeline artifacts plus `evaluation_document.json` are written.

### Tests for User Story 1

- [X] T006 [P] [US1] Add document pipeline-preparation CLI integration test in `tests/evaluator_tests/test_cli.py`
- [X] T007 [P] [US1] Add document preparation failure test in `tests/evaluator_tests/test_pipeline_invocation.py`

### Implementation for User Story 1

- [X] T008 [US1] Invoke the pipeline before document evaluation when `--run-pipeline` is set in `src/dartwing_ocr/evaluator/cli.py`
- [X] T009 [US1] Map pipeline preparation failures to evaluator hard-error code `3` with clear stderr messages in `src/dartwing_ocr/evaluator/cli.py`

**Checkpoint**: User Story 1 is independently functional.

---

## Phase 4: User Story 2 - Run And Evaluate A Corpus (Priority: P2)

**Goal**: One evaluator command can prepare a corpus through the warm pipeline path and then aggregate evaluation results.

**Independent Test**: Run the evaluator corpus command with `--run-pipeline --pipeline-overwrite --refresh` on a small temporary corpus and verify all documents are prepared and `evaluation_run_summary.json` is written.

### Tests for User Story 2

- [X] T010 [P] [US2] Add corpus warm preparation integration test in `tests/integration/test_evaluator_pipeline_harness.py`
- [X] T011 [P] [US2] Add continue-through-failures corpus test in `tests/evaluator_tests/test_pipeline_invocation.py`

### Implementation for User Story 2

- [X] T012 [US2] Discover corpus folders and invoke warm pipeline preparation through a temporary documents file in `src/dartwing_ocr/evaluator/cli.py`
- [X] T013 [US2] Evaluate only successfully prepared folders after continue-mode preparation in `src/dartwing_ocr/evaluator/corpus.py`
- [X] T014 [US2] Report preparation counts and failures to stderr without changing corpus Markdown stdout in `src/dartwing_ocr/evaluator/cli.py`

**Checkpoint**: User Stories 1 and 2 are independently functional.

---

## Phase 5: User Story 3 - Select Runtime Profiles For Harness Runs (Priority: P3)

**Goal**: The harness supports explicit stack presets and per-stage profiles while defaulting to deterministic stubs for tests.

**Independent Test**: Verify command construction defaults to all-stub profiles only when no real profile selection is provided, and preserves explicit stack/profile selections when present.

### Tests for User Story 3

- [X] T015 [P] [US3] Add stub-default command construction tests in `tests/evaluator_tests/test_pipeline_invocation.py`
- [X] T016 [P] [US3] Add explicit stack/profile passthrough tests in `tests/evaluator_tests/test_pipeline_invocation.py`

### Implementation for User Story 3

- [X] T017 [US3] Implement stub-safe default profile selection in `src/dartwing_ocr/evaluator/pipeline_invocation.py`
- [X] T018 [US3] Implement stack preset, per-stage profile, slice, endpoint, timeout, and overwrite passthrough in `src/dartwing_ocr/evaluator/pipeline_invocation.py`

**Checkpoint**: User Stories 1, 2, and 3 are functional.

---

## Phase 6: User Story 4 - Surface Warm Corpus Timing (Priority: P4)

**Goal**: Corpus preparation exposes available 011 warm-run metadata without adding new schema artifacts.

**Independent Test**: Run a corpus preparation that emits a `kind: run_summary` line and verify stderr includes preparation counts and available initialization timing.

### Tests for User Story 4

- [X] T019 [P] [US4] Add warm metadata parsing tests in `tests/evaluator_tests/test_pipeline_invocation.py`
- [X] T020 [P] [US4] Add CLI stderr metadata test in `tests/integration/test_evaluator_pipeline_harness.py`

### Implementation for User Story 4

- [X] T021 [US4] Parse warm run summary metadata in `src/dartwing_ocr/evaluator/pipeline_invocation.py`
- [X] T022 [US4] Print preparation metadata to stderr from corpus CLI handling in `src/dartwing_ocr/evaluator/cli.py`

**Checkpoint**: All user stories are functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation and validation.

- [X] T023 [P] Update 012 quickstart if implementation flags differ in `specs/012-pipeline-harness-integration/quickstart.md`
- [X] T024 Run focused evaluator and integration tests for 012
- [X] T025 Commit implementation and test changes for 012

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on setup and blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on foundational work; MVP.
- **User Story 2 (Phase 4)**: Depends on foundational work; can reuse the invocation module from US1.
- **User Story 3 (Phase 5)**: Depends on foundational work; can be tested mostly through command construction.
- **User Story 4 (Phase 6)**: Depends on corpus run-summary parsing from US2.
- **Polish (Phase 7)**: Depends on selected story scope.

### Parallel Opportunities

- T002 can run in parallel with T001 once the intended module path is agreed.
- T005 can run in parallel with T003 and T004 because it verifies source-level imports.
- US1 tests T006 and T007 can be written in parallel.
- US2 tests T010 and T011 can be written in parallel.
- US3 tests T015 and T016 can be written in parallel.
- US4 tests T019 and T020 can be written in parallel.

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Complete User Story 1.
3. Validate one-document preparation and evaluation with stub-safe profiles.

### Incremental Delivery

1. Add corpus warm preparation and subset aggregation.
2. Add runtime profile passthrough.
3. Add warm timing metadata reporting.
4. Run focused tests and commit.
