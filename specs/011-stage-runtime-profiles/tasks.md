---
description: "Implementation tasks for feature 011: Stage Runtime Profiles / Root Master Controller"
---

# Tasks: Stage Runtime Profiles / Root Master Controller (011)

**Input**: Design documents from `/specs/011-stage-runtime-profiles/`
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/cli-contract.md`, `quickstart.md`, `checklists/design.md`, `checklists/requirements.md`

**Tests**: Test tasks ARE included. The plan explicitly lists test files (`tests/pipeline_tests/`, `tests/contract_tests/`, `tests/integration/`) and the repo already runs a contract-test culture; coverage of foundational invariants (SC-005, SC-009) and the amended `002-cli-contract` surface is non-optional.

**Organization**: Tasks are grouped by user story (with priority) per FR-034 implementation sequencing: thin foundation -> warm `ppstructurev3@cpu` -> real defaults -> secondary lanes/stacks. Each story's checkpoint is independently testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks).
- **[Story]**: User-story label (US1...US6 from `spec.md`). Setup/Foundational/Polish tasks have no Story label.
- File paths are absolute relative to repo root (`/workspace/projects/ledgerlinc/ledgerlinc-model-ocr-pipeline-worktrees/011-stage-runtime-profiles/` is the worktree root).

## Path Conventions

Single-project Python package layout (per `plan.md` "Project Structure"):
- Source: `src/ledgerlinc_ocr/pipeline/` (extended); `src/ledgerlinc_ocr/{preprocessing,extract,router,assembler,validator}/` (reused unchanged as adapter targets).
- Tests: `tests/pipeline_tests/`, `tests/contract_tests/`, `tests/integration/`, `tests/unit/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Stand up empty module files so foundational tasks can land in parallel without colliding on file creation.

- [ ] T001 Create empty module files (module docstring + `from __future__ import annotations` only) at `src/ledgerlinc_ocr/pipeline/profiles.py`, `src/ledgerlinc_ocr/pipeline/slice_control.py`, `src/ledgerlinc_ocr/pipeline/corpus.py`, `src/ledgerlinc_ocr/pipeline/timing.py`, `src/ledgerlinc_ocr/pipeline/ollama_lanes.py`, `src/ledgerlinc_ocr/pipeline/failure_policy.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Implement the thin controller foundation per FR-034 step 1 (profile parsing/validation, `--start-at`/`--stop-after`, overwrite scoping, prerequisite-artifact validation, warm-registry primitives, run-summary builder, CLI flag plumbing). All user stories depend on this phase.

**WARNING**: No user story work can begin until this phase is complete (specifically until T011 lands the new CLI flags and T010 extends `Runner.run()` to consume `ResolvedRunPlan`).

### Foundational implementation

- [ ] T002 [P] Implement closed-set profile resolver, parsing grammar (`stub` | `<impl>@<lane>`), per-stage rejection rules, and `StackPreset` expansion table in `src/ledgerlinc_ocr/pipeline/profiles.py` (Spec FR-005/FR-006/FR-008/FR-004A; Research R-001/R-002/R-003; Data-model `StageProfile` and `StackPreset`)
- [ ] T003 [P] Implement `ExecutionSlice` dataclass with `start_at`/`stop_after` parsing, canonical stage tuple, prerequisite-artifact mapping (table from `contracts/cli-contract.md` Section"Prerequisite-artifact validation"), prerequisite-validation wrapper around `validate_artifact(...)`, and overwrite-scoping helper in `src/ledgerlinc_ocr/pipeline/slice_control.py` (Spec FR-004/FR-009/FR-010/FR-011; Research R-004/R-005/R-006)
- [ ] T004 [P] Implement `OllamaLaneEndpoints` with flag > env > default precedence for gpu/cpu/jetson lanes in `src/ledgerlinc_ocr/pipeline/ollama_lanes.py` (Spec FR-015/FR-016/FR-017/FR-018; Research R-012)
- [ ] T005 [P] Implement `FailurePolicy` parser with `continue` (warm-corpus default) and `fail-fast` modes in `src/ledgerlinc_ocr/pipeline/failure_policy.py` (Spec FR-028; Research R-008/R-010)
- [ ] T006 [P] Implement `StageTiming` capture (`time.monotonic_ns()` boundaries, per-stage phase keys, six-decimal float serialization) and `RunSummary` builder/serializer (`kind: "run_summary"`, `schema_version: "0.1.0"`, end-of-run JSON-Lines stdout) in `src/ledgerlinc_ocr/pipeline/timing.py` (Spec FR-027; Research R-009/R-015; Data-model `StageTiming` and `RunSummary`)
- [ ] T007 [P] Implement `parse_documents_file(path)` (UTF-8 read, blank/`#`-comment strip, paths-relative-to-file's-parent, empty-corpus rejection) and `WarmProfileRegistry` (per-process, stage-scoped, `get_or_initialize` with one-shot init, `close()` swallowing) in `src/ledgerlinc_ocr/pipeline/corpus.py` (Spec FR-023/FR-024/FR-025; Research R-007/R-011; Data-model `WarmProfileRegistry`)
- [ ] T008 Extend `CLIInvocation` dataclass and define `ResolvedRunPlan` (mode `cold_single_document` / `warm_corpus`, profiles map, slice, ollama_endpoints, failure_policy, stack_preset_name, documents tuple) in `src/ledgerlinc_ocr/pipeline/runner.py` (Data-model `ResolvedRunPlan`; Plan Section"Project Structure"; depends on T002-T007)
- [ ] T009 Implement profile->adapter registry binding `(stage, impl, lane)` tuples to adapter callables in `src/ledgerlinc_ocr/pipeline/stages.py`: keep all four stub callables; add stub-only entries for every supported `(stage, impl, lane)` triple from FR-006 with the live entries left as `DeferredImplementationError` placeholders (live wiring lands in US-specific phases) (Research R-014; Spec FR-012/FR-013; depends on T002)
- [ ] T010 Extend `Runner.run()` to accept a `ResolvedRunPlan`: respect the slice tuple, run prerequisite validation before any write when `start_at != preprocess`, scope overwrite guard to `slice.output_artifacts`, capture timing per stage, preserve the existing injected-stage-callable seam alongside the registry-driven path in `src/ledgerlinc_ocr/pipeline/runner.py` (Spec FR-009/FR-010/FR-011/FR-012; Research R-004/R-005/R-006/R-014; Data-model `DocumentRun`/`DocumentOutcome`; depends on T008, T009)
- [ ] T011 Extend the argparse parser in `src/ledgerlinc_ocr/pipeline/cli.py` to add `--preprocess-profile`, `--extract-profile`, `--routing-profile`, `--final-payload-profile`, `--stack-preset`, `--start-at`, `--stop-after`, `--documents-file`, `--on-failure`, `--ollama-cpu-url`, `--ollama-jetson-url`; wire mutual-exclusion checks for `--input` / `--document-folder` / `--documents-file` and the `--output-dir` / `--document-id` rejection in warm-corpus mode (Contract SectionArguments, Section"Mutual exclusion / ordering rules"; Spec FR-003/FR-004/FR-016/FR-017/FR-023; depends on T002-T007)

### Foundational unit tests

- [ ] T012 [P] Unit tests for the profile resolver (every accepted FR-006 value, every rejection case from R-002 including `stub@cpu`, `stub@gpu`, `ppstructurev3@gpu`, `edge-ocr@cpu`, `rules@gpu`, `ensemble@cloud`, unknown impls; preset expansion for all three presets; per-stage override semantics) in `tests/pipeline_tests/test_profile_resolver.py` (covers SC-005 partially; design.md CHK009-CHK012; depends on T002)
- [ ] T013 [P] Unit tests for slice control (every contiguous slice combination; default bounds; `start_at > stop_after` rejection; prerequisite tabulation per start stage; overwrite-scoping positive and negative cases) in `tests/pipeline_tests/test_slice_control.py` (covers Spec FR-009/FR-010/FR-011; design.md CHK013-CHK014; depends on T003)
- [ ] T014 [P] Unit tests for Ollama lane URL resolution (flag > env > default precedence on each of gpu/cpu/jetson; default values match Research R-012 table) in `tests/pipeline_tests/test_ollama_lanes.py` (depends on T004)
- [ ] T015 [P] Unit tests for failure policy parser (case-insensitive parse of `continue`/`fail-fast`; warm-corpus default is `continue`; cold-mode no-op behavior) in `tests/pipeline_tests/test_failure_policy.py` (depends on T005)
- [ ] T016 [P] Unit tests for timing capture and run-summary serializer (monotonic_ns; six-decimal float rounding; phase-key vocabulary per stage; `kind` and `schema_version` fields present; missing phase keys handled per Research R-009/R-015) in `tests/pipeline_tests/test_timing_and_summary.py` (depends on T006)
- [ ] T017 [P] Unit tests for documents-file parsing (UTF-8 input, blank-line strip, `#`-comment strip, relative-to-parent resolution, duplicate preservation, empty-corpus rejection) and `WarmProfileRegistry` (one-shot init invariant, per-process scope, `close()` runs unconditionally) in `tests/pipeline_tests/test_corpus_internals.py` (covers SC-009 invariant at unit level; design.md CHK031-CHK032; depends on T007)

**Checkpoint**: Foundation ready -- profile/slice/lane/policy/timing/corpus primitives are implemented and unit-tested; the runner can consume a `ResolvedRunPlan`; the CLI parser accepts the new flags. User-story phases can now begin.

---

## Phase 3: User Story 2 - Run Any Contiguous Pipeline Slice With Explicit Stage Profiles (Priority: P1)

**Goal**: With `--start-at` / `--stop-after` and explicit stage profiles, callers can execute any contiguous slice (`preprocess`-only, `extract`-only, ..., full pipeline), reusing already-written upstream artifacts as prerequisites.

**Independent Test**: On a folder with a valid `preprocess_output.json`, run `python -m ledgerlinc_ocr.pipeline run --document-folder <folder> --start-at extract --stop-after extract --extract-profile stub --overwrite`. Verify only `edge_extraction_output.json` is rewritten, preprocessing is treated as prerequisite (not re-run), and missing/invalid prerequisites fail before any downstream write.

### Implementation for User Story 2

- [ ] T018 [US2] Wire CLI args -> profile resolver -> `ResolvedRunPlan` -> `Runner.run()` end-to-end in `src/ledgerlinc_ocr/pipeline/cli.py`: argument validation order is (parse -> stack-preset expand -> per-stage override -> slice resolve -> prerequisite validate -> overwrite check -> dispatch); single shared usage-error code path emits the `002` `StructuredFailureRecord` with the new `arguments` / `prerequisite_validation` stages (Contract Section"Output behavior"; depends on T010, T011)

### Tests for User Story 2

- [ ] T019 [P] [US2] Integration test: `--start-at extract --stop-after extract` against a folder with a valid `preprocess_output.json` rewrites only `edge_extraction_output.json` and leaves the other three artifacts byte-identical, in `tests/integration/test_slice_extract_only.py` (Spec User Story 2 Acceptance Scenario 1; depends on T018)
- [ ] T020 [P] [US2] Integration test: `--start-at routing --stop-after final_payload` against a folder with valid upstream artifacts writes only routing + final payload, leaves preprocess and extract artifacts untouched, in `tests/integration/test_slice_late_stages.py` (Spec User Story 2 Acceptance Scenario 2; depends on T018)
- [ ] T021 [P] [US2] Integration test: `--preprocess-profile stub --extract-profile stub` with a slice covering both stages produces a real (non-stub) extract artifact when extract is replaced by a non-stub stub-injected callable, demonstrating mixed stub-upstream + live-downstream composition in `tests/integration/test_slice_mixed_stub_live.py` (Spec User Story 2 Acceptance Scenario 3; depends on T018)
- [ ] T022 [P] [US2] Integration test: `--start-at routing` with `edge_extraction_output.json` missing exits `2` (`INPUT_NOT_FOUND`) before any write and stderr names the unmet prerequisite; same start with a malformed `edge_extraction_output.json` exits `4` (`SCHEMA_VALIDATION_FAILURE`) in `tests/integration/test_slice_missing_prereq.py` (Spec User Story 2 Acceptance Scenario 4 + Edge Cases bullet 1; design.md CHK013/CHK057; depends on T018)
- [ ] T023 [P] [US2] Integration test: `--stop-after preprocess` with downstream artifact files already on disk (no `--overwrite`) succeeds when the slice excludes those files (overwrite scoping is positive); without `--overwrite` and the slice's own output already present, fails with `OUTPUT_IN_USE` (overwrite scoping is negative) in `tests/integration/test_slice_overwrite_scoping.py` (Spec User Story 2 Acceptance Scenario 5; design.md CHK014; depends on T018)

**Checkpoint**: User Story 2 fully functional -- callers can execute any contiguous slice independently. SC-003 partially demonstrated (every valid slice executes when prerequisites present and fails-before-write when missing).

---

## Phase 4: User Story 4 - Preserve Contract-Test Seams While Expanding The CLI Surface (Priority: P1)

**Goal**: Existing contract and unit tests can continue to drive the runner with all-stub execution and no network dependency, either through injected stage callables or explicit `stub` profiles, even as the CLI grows.

**Independent Test**: Run the existing CLI-contract test suite under the new CLI; assert no Ollama / no Paddle imports or socket calls; assert the injected-callable seam still routes around the new resolver.

### Implementation for User Story 4

- [ ] T024 [US4] Confirm `Runner.__init__` continues to accept per-stage `StageCallable` injections; add an explicit branch in `Runner.run()` so injected callables short-circuit the profile registry while still honoring slice + prerequisite + overwrite + timing in `src/ledgerlinc_ocr/pipeline/runner.py` (Spec FR-012; design.md CHK024; depends on T010)

### Tests for User Story 4

- [ ] T025 [P] [US4] Integration test: a contract test that injects four stub `StageCallable`s into `Runner` runs end-to-end without hitting the profile resolver and with no live module imports, in `tests/pipeline_tests/test_injected_callable_seam.py` (Spec User Story 4 Acceptance Scenario 1; depends on T024)
- [ ] T026 [P] [US4] Contract test using `pytest-socket` to disable network: a CLI-driven run with `--preprocess-profile stub --extract-profile stub --routing-profile stub --final-payload-profile stub` succeeds with zero socket calls, in `tests/contract_tests/test_cli_contract_011_amendment.py` (Spec User Story 4 Acceptance Scenario 2; SC-006; depends on T011, T018)
- [ ] T027 [P] [US4] Contract test: `python -m ledgerlinc_ocr.pipeline run --help` lists every new flag (`--preprocess-profile`, `--extract-profile`, `--routing-profile`, `--final-payload-profile`, `--stack-preset`, `--start-at`, `--stop-after`, `--documents-file`, `--on-failure`, `--ollama-cpu-url`, `--ollama-jetson-url`) and preserves every flag from the frozen `002-cli-contract`, in `tests/contract_tests/test_cli_contract_011_amendment.py` (Spec User Story 4 Acceptance Scenario 3; design.md CHK008; depends on T011)
- [ ] T028 [P] [US4] Update `tests/contract_tests/test_cli_contract.py` (or extend the file matching the existing 002 contract test) to cover the amended argument set: amended `--overwrite` semantics, mutual exclusion of `--input`/`--document-folder`/`--documents-file`, rejection of `--output-dir` and `--document-id` in warm-corpus mode (Contract Section"Mutual exclusion / ordering rules"; depends on T011)

**Checkpoint**: User Story 4 fully functional -- stub-only network-free contract tests continue to pass; the injected-callable seam still works; the amended CLI surface is documented through tests.

---

## Phase 5: User Story 6 - Run Corpus Live Stages Through Warm Profile Instances (Priority: P1)

**Goal**: Harness operators can run the 20-document corpus through `python -m ledgerlinc_ocr.pipeline run --documents-file <path> --preprocess-profile ppstructurev3@cpu`, initializing PPStructureV3 exactly once per process and reusing the warmed instance for every document, with per-document failure context and a single end-of-run `kind: "run_summary"` JSON line on stdout.

**Independent Test**: Stage 3+ valid per-document folders, write their paths to a `documents.txt`, run the warm-corpus invocation. Verify (a) `profile_initialization_seconds.preprocess` appears exactly once in the run summary regardless of N (SC-009); (b) every document folder contains its full set of four canonical artifacts; (c) cold one-document runs remain available and visibly distinct from warm corpus timing.

### Implementation for User Story 6

- [ ] T029 [US6] Implement `CorpusRun.execute(registry)` in `src/ledgerlinc_ocr/pipeline/corpus.py`: iterate documents, build per-document `DocumentRun`s, call `Runner.run(plan)` against the warm registry, emit per-document `002`-shaped success records on stdout / `StructuredFailureRecord` on stderr, honor `FailurePolicy.mode`, call `registry.close()` unconditionally, then emit the run summary (Spec FR-023/FR-026/FR-028; Research R-008/R-009/R-011; Data-model `CorpusRun`; depends on T007, T010)
- [ ] T030 [US6] Wire `--documents-file` -> `parse_documents_file` -> `CorpusRun.execute` in `src/ledgerlinc_ocr/pipeline/cli.py`; preserve cold single-document codepath unchanged when `--input`/`--document-folder` is supplied (Contract Section"Output behavior"; depends on T011, T018, T029)
- [ ] T031 [US6] Implement live `("preprocess", "ppstructurev3", "cpu")` adapter in `src/ledgerlinc_ocr/pipeline/stages.py`: `initialize()` constructs `PPStructureV3` once via the existing `ledgerlinc_ocr.preprocessing.pipeline` entry point; `process(folder)` runs preprocessing using the warmed instance; instrument timing phase keys `rasterize`/`infer`/`write` (Spec FR-024; Research R-014; depends on T009)
- [ ] T032 [US6] Wire run-summary emission to be the **last** stdout line in warm-corpus mode and **never** emitted in cold single-document mode in `src/ledgerlinc_ocr/pipeline/cli.py` (Contract Section"Output behavior"; Research R-009/R-010; design.md CHK022; depends on T011, T029)

### Tests for User Story 6

- [ ] T033 [P] [US6] Integration test: warm corpus with all-stub profiles over 3 folders, no Paddle/Ollama imports, run summary reports `documents_total: 3`, `documents_succeeded: 3`, `profile_initialization_seconds: {}` in `tests/integration/test_warm_corpus_stub_profiles.py` (Quickstart Section3b; depends on T030)
- [ ] T034 [P] [US6] Integration test (Paddle-gated; skip if `paddleocr` import fails): warm corpus with `--preprocess-profile ppstructurev3@cpu` over 3 folders, assert `len(run_summary["profile_initialization_seconds"]) == 1`, assert each per-document `stages.preprocess.total_seconds` is well below the initialization cost, assert all four canonical artifacts validate against the installed contract set in `tests/integration/test_warm_corpus_ppstructurev3_cpu.py` (Spec User Story 6 Acceptance Scenarios 1-2 + 4; SC-009 + SC-010; Quickstart Section3c + Section6; design.md CHK026/CHK036/CHK048; depends on T031, T030)
- [ ] T035 [P] [US6] Integration test: warm corpus with default `--on-failure continue`, mix of valid folders and one folder whose `source.pdf` is malformed; run reports 3 successes + 1 failure, each per-document failure record names the failed stage/profile and exits with the highest-severity per-document code in `tests/integration/test_warm_corpus_continue.py` (Spec User Story 6 Acceptance Scenario 3; Research R-008; depends on T030)
- [ ] T036 [P] [US6] Integration test: warm corpus with `--on-failure fail-fast` aborts after the first bad document and skipped documents do not appear in `per_document` in `tests/integration/test_warm_corpus_fail_fast.py` (Research R-008; design.md CHK023; depends on T030)
- [ ] T037 [P] [US6] Integration test: cold single-document mode (`--document-folder`) still emits exactly the existing `002-cli-contract` success line on stdout with no `kind` field and no run summary in `tests/integration/test_cold_single_document_preserved.py` (Spec User Story 6 Acceptance Scenario 5; SC-011; Research R-010; depends on T030)
- [ ] T038 [P] [US6] Integration test: warm corpus with a deterministic-only slice (`--start-at routing --stop-after final_payload --routing-profile stub --final-payload-profile stub`) does not initialize any live preprocessing profile -- `profile_initialization_seconds` stays empty in `tests/integration/test_warm_corpus_deterministic_slice.py` (Spec Edge Cases warm-corpus deterministic-only-stages bullet; design.md CHK054; depends on T030)

**Checkpoint**: User Story 6 fully functional -- harness can run the warm corpus path; SC-009 and SC-010 demonstrated; cold path preserved.

---

## Phase 6: User Story 1 - Run The Top-Level Pipeline Through Real Default Profiles (Priority: P2)

**Goal**: With no stage-profile overrides, `python -m ledgerlinc_ocr.pipeline run --document-folder <folder>` executes the full stage-1 slice through real implementations (`ppstructurev3@cpu`, `ollama@gpu`, `rules@cpu`, `assembler@cpu`), preserving the `002-cli-contract` artifact filenames, schemas, and stdout/stderr record shapes.

**Independent Test**: Run the top-level CLI with no flags on `inv_001_easy`. Verify all four artifacts come from non-stub implementations and validate against the installed contract set; verify stdout success line still matches the frozen `002` shape.

### Implementation for User Story 1

- [ ] T039 [US1] Implement live `("extract", "ollama", "gpu")` adapter binding to `ledgerlinc_ocr.extract.pipeline` (or current entry point) with the resolved GPU URL from `OllamaLaneEndpoints.gpu_url`, instrumenting timing phase keys `infer`/`write`, in `src/ledgerlinc_ocr/pipeline/stages.py` (Research R-014; depends on T009, T004)
- [ ] T040 [US1] Implement live `("routing", "rules", "cpu")` adapter binding to `ledgerlinc_ocr.router.pipeline.route` with timing phase keys `compute`/`write`, in `src/ledgerlinc_ocr/pipeline/stages.py` (depends on T009)
- [ ] T041 [US1] Implement live `("final_payload", "assembler", "cpu")` adapter binding to `ledgerlinc_ocr.assembler.pipeline.assemble` with timing phase keys `compute`/`write`, in `src/ledgerlinc_ocr/pipeline/stages.py` (depends on T009)
- [ ] T042 [US1] Verify the default-profile resolution path: when no `--*-profile` flag and no `--stack-preset` are supplied, the resolver yields `ppstructurev3@cpu`/`ollama@gpu`/`rules@cpu`/`assembler@cpu`; ensure the adapter registry routes each default to the live adapter (T031, T039, T040, T041) rather than the stub callable, in `src/ledgerlinc_ocr/pipeline/cli.py` and `src/ledgerlinc_ocr/pipeline/stages.py` (Spec FR-007/FR-013; depends on T031, T039, T040, T041)

### Tests for User Story 1

- [ ] T043 [P] [US1] Integration test (Ollama + Paddle gated; skipped if either dependency missing): `python -m ledgerlinc_ocr.pipeline run --document-folder tests/stage1_vendor_identity/inv_001_easy --overwrite` produces all four artifacts under non-stub implementations and the `model_runtime`/`vote_metadata` blocks reflect a real Ollama call rather than a stub identifier, in `tests/integration/test_default_real_run.py` (Spec User Story 1 Acceptance Scenarios 1 + 4; depends on T042)
- [ ] T044 [P] [US1] Integration test: artifact filenames, on-disk locations, and JSON Schemas of all four artifacts produced under default real run match the contract set v1.2.0 unchanged from a baseline `002`-shape run, in `tests/integration/test_default_real_artifacts_contract.py` (Spec User Story 1 Acceptance Scenario 2; SC-002; depends on T042)
- [ ] T045 [P] [US1] Contract test: stdout success summary and stderr structured-failure record under default real run match the frozen `002-cli-contract` shapes byte-for-byte (no `kind` field, identical key set), in `tests/contract_tests/test_default_real_record_shapes.py` (Spec User Story 1 Acceptance Scenario 3; FR-002; Research R-010; depends on T042)

**Checkpoint**: User Story 1 fully functional -- full real defaults run end-to-end. SC-001 + SC-002 demonstrated.

---

## Phase 7: User Story 3 - Compare Workstation And Jetson Lanes For Supported Live Stages (Priority: P3)

**Goal**: Same stage-profile syntax expresses workstation CPU/GPU and Jetson lanes for stages where the implementation supports them; unsupported combinations fail clearly before the run starts; live Jetson adapters are recognized but their implementation is sequenced after this slice (FR-035, R-014).

**Independent Test**: Run the same extraction-only slice with `--extract-profile ollama@gpu` and `--extract-profile ollama@cpu`; verify both produce the same artifact contracts but different runtime metadata. Verify `--extract-profile ollama@jetson` is recognized but fails fast at adapter dispatch with a deferred-implementation message.

### Implementation for User Story 3

- [ ] T046 [US3] Implement live `("extract", "ollama", "cpu")` adapter binding to the same extract entry point as US1 but with `OllamaLaneEndpoints.cpu_url`, in `src/ledgerlinc_ocr/pipeline/stages.py` (Spec FR-015/FR-016; Research R-012; depends on T039)
- [ ] T047 [US3] Wire profile-validation acceptance for `("preprocess", "edge-ocr", "jetson")` and `("extract", "ollama", "jetson")` in the registry: argument validation accepts these values, but adapter dispatch raises `DeferredImplementationError` with stage `prerequisite_validation` and a message naming FR-034 step 4 as the implementation slice (Spec FR-035; Research R-013/R-014; depends on T009)

### Tests for User Story 3

- [ ] T048 [P] [US3] Integration test (Ollama-gated): extract-only slice on the same folder with `--extract-profile ollama@gpu` and then with `--extract-profile ollama@cpu` produces `edge_extraction_output.json` with identical schema-relevant keys but distinct lane-URL evidence in metadata, in `tests/integration/test_lane_comparison.py` (Spec User Story 3 Acceptance Scenarios 1-2 + 6; SC-004; depends on T046)
- [ ] T049 [P] [US3] Integration test: `--extract-profile ollama@jetson` with all other flags valid exits `10` before any write with a stderr stage of `prerequisite_validation` and a message naming `ollama@jetson` and FR-034 step 4, in `tests/integration/test_jetson_recognition_only.py` (Spec User Story 3 Acceptance Scenarios 3-4; FR-035; Research R-014; depends on T047)
- [ ] T050 [P] [US3] Unit test (extends T012): every unsupported `<impl>@<lane>` combination from spec Edge Cases (`stub@gpu`, `stub@cpu`, `ppstructurev3@gpu`, `edge-ocr@cpu`, `rules@gpu`, `ensemble@cloud`, unknown impls) is rejected at argument validation with `USAGE_ERROR` and stage `arguments`, in `tests/pipeline_tests/test_invalid_lane_rejection.py` (Spec User Story 3 Acceptance Scenario 5; SC-005; design.md CHK010; depends on T002)

**Checkpoint**: User Story 3 fully functional for the supported lanes covered by this slice (gpu/cpu); jetson recognition-only verified.

---

## Phase 8: User Story 5 - Test Cloud-Class Stack On Workstation GPUs (Priority: P3)

**Goal**: `--stack-preset cloud-workstation` and `--extract-profile ensemble@workstation` are accepted by argument validation, expand correctly, and metadata records the originating preset, but live execution of `ensemble@workstation` is deferred to FR-034 step 4 with a deterministic fail-fast (R-013). No remote cloud-provider calls or credential handling.

**Independent Test**: Run with `--stack-preset cloud-workstation`. Verify argument validation accepts the preset, the registry dispatch fails fast with a named missing-endpoint error before any artifact write, and the run summary records `stack_preset: "cloud-workstation"` and `resolved_profiles.extract: "ensemble@workstation"` (when the run summary is emitted before the fail-fast) or that the failure record carries the same metadata.

### Implementation for User Story 5

- [ ] T051 [US5] Wire profile-validation acceptance for `("extract", "ensemble", "workstation")` and adapter dispatch with deferred-implementation fail-fast carrying the message: `"ensemble@workstation requires voter endpoints; configuration is delivered in the secondary-lane slice (FR-034 step 4) -- set the explicit per-stage profile or --stack-preset to a supported workstation preset"`, in `src/ledgerlinc_ocr/pipeline/stages.py` (Spec FR-022A; Research R-013; design.md CHK040-CHK042; depends on T009)
- [ ] T052 [US5] Confirm `--stack-preset cloud-workstation` expansion in the resolver yields the preset table from FR-004A (preprocess `ppstructurev3@cpu`, extract `ensemble@workstation`, routing `rules@cpu`, final payload `assembler@cpu`); verify the `stack_preset` name is recorded verbatim in run-summary metadata regardless of per-stage overrides, in `src/ledgerlinc_ocr/pipeline/profiles.py` (Research R-003; design.md CHK011; depends on T002, T006)

### Tests for User Story 5

- [ ] T053 [P] [US5] Unit test for stack-preset expansion (table from FR-004A) and override semantics (per-stage flags win; preset name still recorded), in `tests/pipeline_tests/test_stack_preset_expansion.py` (covers all three presets; design.md CHK011-CHK012; depends on T052)
- [ ] T054 [P] [US5] Integration test: `--stack-preset cloud-workstation` exits `10` with stderr stage `prerequisite_validation` and a message naming `ensemble@workstation` and FR-034 step 4; no artifacts are written, in `tests/integration/test_ensemble_workstation_deferral.py` (Spec User Story 5 Acceptance Scenarios 1 + 3; design.md CHK040-CHK041; depends on T051)
- [ ] T055 [P] [US5] Integration test: cloud-provider-style env vars (`AWS_ACCESS_KEY_ID`, `OPENAI_API_KEY`, etc.) present in the environment do not change behavior; the fail-fast message is identical with and without them; pytest-socket asserts no egress, in `tests/integration/test_cloud_workstation_no_creds.py` (Spec User Story 5 Acceptance Scenario 4; FR-021; design.md CHK043; depends on T051)
- [ ] T056 [P] [US5] Contract test: a successful `cloud-workstation` slice (one that excludes the extract stage, e.g., `--stack-preset cloud-workstation --start-at routing`) emits a run summary whose `stack_preset == "cloud-workstation"` and whose `resolved_profiles.extract == "ensemble@workstation"` even though the deferred adapter was never dispatched, in `tests/contract_tests/test_run_summary_stack_metadata.py` (Spec User Story 5 Acceptance Scenario 2; SC-008; design.md CHK049; depends on T052)

**Checkpoint**: User Story 5 fully functional within this slice's scope -- contract surface for `cloud-workstation` is honored, ensemble@workstation deferral is enforced, metadata carries the preset name. Live ensemble execution remains deferred to FR-034 step 4 by design.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Constitution Q-Gate 3 documentation updates, regression sweep against earlier slices, and resolution of any unresolved design-checklist items before merge.

- [ ] T057 [P] Update `docs/stage1-vendor-identity/architecture.md` to describe the controller layer's responsibilities (FR-033), the warm-corpus path (FR-023/FR-024/FR-025/FR-027), and the `--documents-file` invocation surface; cross-link to `specs/011-stage-runtime-profiles/contracts/cli-contract.md` (Q-Gate 3; design.md CHK068)
- [ ] T058 [P] Update `docs/stage1-vendor-identity/ollama-runtime.md` to document the three Ollama lane URL flags (`--ollama-url`/`--ollama-cpu-url`/`--ollama-jetson-url`), env-var precedence, default values from R-012, and the WSL CPU container vs. native ROCm GPU vs. Jetson edge distinctions (Q-Gate 3; Research R-012; design.md CHK027)
- [ ] T059 [P] Add a forward reference at the top of `specs/002-cli-contract/contracts/cli-contract.md` noting that `specs/011-stage-runtime-profiles/contracts/cli-contract.md` v1.1.0 is the active successor (preserve `002` as the frozen baseline for tests that pin v1.0.0)
- [ ] T060 [P] Confirm `CLAUDE.md` "Active Technologies" and "Recent Changes" entries for 011 are accurate after `update-agent-context.sh claude` ran during /speckit.plan; correct any drift introduced by linter changes
- [ ] T061 Walk through `specs/011-stage-runtime-profiles/checklists/design.md` (CHK001-CHK068) and resolve every unchecked item by either (a) editing the corresponding artifact or (b) recording the deferral in `research.md` with rationale; check the box only after the underlying gap is closed
- [ ] T062 Run the full pytest suite from repo root (`.venv/bin/pytest tests/contract_tests/ tests/pipeline_tests/ tests/integration/ tests/unit/ tests/evaluator_tests/`) and confirm zero regressions in 001-010 suites; document any flake-vs-real distinction inline if a test is genuinely environment-dependent
- [ ] T063 Walk through every numbered scenario in `specs/011-stage-runtime-profiles/quickstart.md` (sections 1-7) end-to-end as smoke tests on a real workstation; record the timing of section 3c's PPStructureV3 init in `specs/010-pp-structurev3-preprocessing/research.md` "Baseline timings" if it is materially different from the 010 baseline (design.md CHK068)
- [ ] T064 Update `specs/011-stage-runtime-profiles/checklists/requirements.md` Notes section with a one-line entry confirming `/speckit.tasks` produced this `tasks.md` and that the design-quality checklist (`design.md`) was generated alongside

---

## Dependencies & Story Completion Order

```
                         T001 (Setup)
                              |
                  +-----------+-----------+
                  |                       |
              T002-T007                  T011 (CLI flags)
              [parallel]                  |
                  |                       |
                  +-----------+-----------+
                              |
                  T008 -> T009 -> T010 (runner consumes ResolvedRunPlan)
                              |
                              +--> T012-T017 (foundational unit tests, parallel)
                              |
                              v
                      US2 (T018-T023)        <-- P1, FR-034 step 1 verification
                              |
                              v
                      US4 (T024-T028)        <-- P1, stub-seam preservation
                              |
                              v
                      US6 (T029-T038)        <-- P1, FR-034 step 2 (warm ppstructurev3@cpu)
                              |
                              v
                      US1 (T039-T045)        <-- P2, FR-034 step 3 (real defaults)
                              |
                  +-----------+-----------+
                  |                       |
              US3 (T046-T050)         US5 (T051-T056)   <-- P3, FR-034 step 4 (recognition-only)
                              |
                              v
                      Polish (T057-T064)
```

**Story-level independence**:
- US2 and US4 share Phase 2's foundation but their tests (T019-T023, T025-T028) target disjoint files and can run in parallel within a story.
- US6 (warm corpus) depends on US2 + US4 only because US2/US4 verify the runner's slice/stub paths that US6 reuses; otherwise US6 has its own adapter (T031) and tests (T033-T038).
- US1 depends on US6 only via T031 (the ppstructurev3@cpu adapter is reused by both default real run and warm corpus). US1 adds three more live adapters (T039-T041) that US3/US5 do not need.
- US3 depends on US1's `ollama@gpu` adapter (T039) because `ollama@cpu` shares its entry point. US5 is independent of US3 -- both can run in parallel after US1 completes.
- Polish (Phase 9) depends on all user stories.

---

## Parallel Execution Opportunities

### Within Phase 2 (Foundational)

T002, T003, T004, T005, T006, T007 each touch a different new file -- launch all six in parallel. Their unit tests (T012, T013, T014, T015, T016, T017) similarly each touch a different test file -- launch in parallel after the matching implementation lands.

### Within US2 (Phase 3)

T019, T020, T021, T022, T023 each touch a different test file -- run in parallel after T018.

### Within US6 (Phase 5)

T033 through T038 each touch a different test file -- run in parallel after T030/T032.

### Within US1 (Phase 6)

T039, T040, T041 each touch the same `stages.py`; serialize them. T043, T044, T045 each touch a different test file -- run in parallel after T042.

### Within US5 (Phase 8) and Phase 9

US5's tests T053-T056 are file-disjoint -- run in parallel after T052. Polish T057, T058, T059, T060 each touch a different doc file -- run in parallel.

---

## Implementation Strategy

### MVP scope

The smallest deployable increment that makes the controller useful for harness-driven testing is **Phase 2 (Foundational) + US6 (warm `ppstructurev3@cpu` corpus)**. After T038, harness operators can drive multi-document warm runs with stub-only or `ppstructurev3@cpu` preprocessing and start seeing the SC-009 invariant in practice. US1's full real defaults (T039-T045) are a strict superset and land next.

### Incremental delivery

1. **Foundation only** (after T017): every contract/unit test passes; no behavior change to existing CLI consumers.
2. **+ US2** (after T023): callers can run any contiguous slice with explicit profiles; cold path users see no surface change.
3. **+ US4** (after T028): contract-test suite validated under the new CLI; `pytest-socket` enforces no-network in stub mode.
4. **+ US6** (after T038): warm-corpus harness path opens up; SC-009 demonstrable.
5. **+ US1** (after T045): default real-profile run end-to-end on the workstation; SC-001 + SC-002 demonstrated.
6. **+ US3** (after T050): `ollama@cpu` lane comparison enabled; jetson recognition-only verified.
7. **+ US5** (after T056): `cloud-workstation` contract surface complete; ensemble@workstation deferral enforced.
8. **+ Polish** (after T064): docs sync; full regression sweep; all design-checklist items resolved or deferred with rationale.

### Test sequencing inside each story

Within each user story, run tests against a placeholder/stub before wiring the live adapter, then re-run after the adapter lands. Both flows reuse the same test fixtures so the only diff is the profile flag.

### Format validation

Every task above strictly follows `- [ ] T### [P?] [Story?] Description with file path` (or repo-root-relative location for tasks that span multiple files).
