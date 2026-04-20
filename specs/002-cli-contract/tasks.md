---
description: "Task list for feature 002-cli-contract — Stage 1 One-Document CLI Contract"
---

# Tasks: Stage 1 One-Document CLI Contract

**Input**: Design documents from `/specs/002-cli-contract/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (cli-contract.md, exit-codes.md, stdout-summary.md, stderr-failure-record.md), quickstart.md

**Tests**: Included — research R-010 explicitly scopes CLI-contract tests in `tests/pipeline_tests/` as the primary verification of the contract. Stubbable pipeline stages keep tests fast, deterministic, and Ollama-free.

**Organization**: Tasks are grouped by user story. US1 and US2 are both P1 and share the foundational surface; US2 adds corpus-loop / folder-input semantics on top of US1. US3 is P2 (diagnosability). US4 is P3 design-for-extensibility and is discharged via compatibility assertions, not new runtime behavior.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: `US1`, `US2`, `US3`, `US4` — mapped from spec.md priorities
- All paths absolute-from-repo-root: `/workspace/projects/ledgerlinc/ledgerlinc-model-ocr-pipeline-worktrees/002-cli-contract/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffold the `pipeline/` package alongside the existing `validator/`, register test and console-script hooks.

- [X] T001 Create empty package skeleton at `src/ledgerlinc_ocr/pipeline/` with `__init__.py` (exposes `__version__` string) and `__main__.py` (imports `cli.main` and calls `sys.exit(main())`).
- [X] T002 Create empty test package at `tests/pipeline_tests/__init__.py`.
- [X] T003 [P] Update `pyproject.toml`: add `tests/pipeline_tests` to `[tool.pytest.ini_options].testpaths`, and add `[project.scripts]` entry `ledgerlinc-pipeline = "ledgerlinc_ocr.pipeline.cli:main"` (per research R-011).
- [X] T004 [P] Confirm no new runtime dependencies are required (research R-005 rules out `python-magic`; research R-007 uses stdlib time). No files written for this task — the `pyproject.toml` diff from T003 is the durable record of the "no new dependencies" decision.
- [X] T004a [P] Create `tests/pipeline_tests/conftest.py` with three fixtures: `tmp_pdf_bytes` (returns a minimal byte sequence starting with `b"%PDF-1.4\n%%EOF"` that satisfies the magic-byte check), `tmp_document_folder` (creates `inv_NNN_easy/source.pdf` under `tmp_path` for a parameterisable NNN), and `tmp_corpus_root` (creates N document folders under `tmp_path` for the corpus-loop test). Used by every test task from T013 onward that needs PDF input — no external files, no real-corpus dependency.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The CLI-contract primitives every user story depends on — exit code enum, structured failure record, PDF magic check, path resolution, and the stubbable runner. These are pure functions / data classes with no story-specific behavior.

**⚠️ CRITICAL**: No user story phase can start until Phase 2 is green. Every US1–US3 task imports from these modules.

- [X] T005 [P] Write failing unit tests for `ExitCode` enum in `tests/pipeline_tests/test_exit_codes.py`: assert each of {SUCCESS=0, USAGE_ERROR=10, INPUT_NOT_FOUND=11, INVALID_PDF=12, OUTPUT_IN_USE=13, OUTPUT_PATH_NOT_USABLE=14, PROCESSING_FAILURE=20, SCHEMA_VALIDATION_FAILURE=30} exists with the exact numeric value, that the set is closed (no extra members), and that numeric values are unique (FR-021, FR-022, data-model §2).
- [X] T006 [P] Write failing unit tests for `pdf_check.is_pdf(path)` in `tests/pipeline_tests/test_pdf_check.py`: valid `%PDF-` prefix → True; 4-byte file → False; empty file → False; non-PDF bytes → False; non-existent path → raises `FileNotFoundError` (research R-005, FR-017).
- [X] T007 [P] Write failing unit tests for path resolution in `tests/pipeline_tests/test_path_resolution.py`: `--document-folder` sets destination to itself and resolves `source.pdf`; `--input` defaults destination to parent; `--output-dir` overrides both; `document_id` derivation from `inv_001_easy` → `inv_001`; folder name `inv_001_easy/` with trailing slash normalises identically; non-matching folder name without `--document-id` raises the "ambiguous document id" sentinel error (FR-002, FR-003, FR-004, research R-004).
- [X] T008 [US1] Implement `src/ledgerlinc_ocr/pipeline/exit_codes.py`: `ExitCode(IntEnum)` with the eight members from data-model §2; `StructuredFailureRecord` dataclass with fields `exit_code`, `exit_code_name`, `stage`, `message`, `artifacts_written` and an `as_json_line() -> str` method that serialises a single-line JSON object with no trailing newline (FR-023, stderr-failure-record.md).
- [X] T009 [US1] Implement `src/ledgerlinc_ocr/pipeline/pdf_check.py`: `is_pdf(path: Path) -> bool` reads first 5 bytes and returns True iff they equal `b"%PDF-"`. No external dependency (research R-005).
- [X] T010 [US1] Implement `src/ledgerlinc_ocr/pipeline/path_resolution.py`: pure functions `resolve_input_pdf(input, document_folder) -> Path`, `resolve_destination(input, document_folder, output_dir) -> Path`, `derive_document_id(dest_folder_name) -> str | None` using regex `^(inv_\d{3})_(easy|medium|hard|missing_name)$` (cli-contract.md §`--document-id` derivation). Functions accept and return absolute `Path` objects; no filesystem I/O beyond `.resolve()`.
- [X] T011 [US1] Implement `src/ledgerlinc_ocr/pipeline/runner.py`: `PipelineStage` literal type with members `arguments | input_validation | preprocess | extraction | routing | final_payload | schema_validation` (data-model §6); `Runner` class whose `__init__` accepts pluggable callables for `preprocess`, `extraction`, `routing`, `final_payload` (default callables wired in via T022 — this task defines the interface only); `run(invocation) -> tuple[ExitCode, artifacts_written]` orchestrates stages 3–6 writing to disk in order, then invokes stage 7 via the validator module (`ledgerlinc_ocr.validator.artifact.validate_artifact`); on any stage exception converts it to `PROCESSING_FAILURE` with the correct `stage` label; on any post-hoc validation failure returns `SCHEMA_VALIDATION_FAILURE` with `stage="schema_validation"`.
- [X] T012 [US1] Run the three Phase-2 test files from T005–T007 and confirm they now pass: `pytest tests/pipeline_tests/test_exit_codes.py tests/pipeline_tests/test_pdf_check.py tests/pipeline_tests/test_path_resolution.py -v`.

**Checkpoint**: CLI primitives green. User story phases may now proceed.

---

## Phase 3: User Story 1 — Pipeline Developer Runs One PDF End to End (Priority: P1) 🎯 MVP

**Goal**: A developer with one PDF can invoke the CLI, produce exactly four schema-valid artifacts in a known folder, and read exit code `0` and a JSON stdout summary. All five US1 acceptance scenarios from spec.md pass.

**Independent Test**: Hand a developer a PDF, the frozen contract docs (`cli-contract.md`, `stdout-summary.md`, `exit-codes.md`), and this CLI. They invoke `python -m ledgerlinc_ocr.pipeline run --input some.pdf --output-dir /tmp/out`. The folder contains exactly the four reserved filenames; every artifact validates against `contracts/stage1_vendor_identity/v1.0.0/`; stdout is one JSON line with `document_id`, `decision`, `manual_review_required`, `review_reason`, `artifacts`; exit code is `0`.

### Tests for User Story 1 (write first, confirm failing)

- [X] T013 [P] [US1] Contract test for argument parsing and subcommand dispatch in `tests/pipeline_tests/test_cli_arguments.py`: invoking with no subcommand exits `USAGE_ERROR` (10) and prints help to stderr; `run` with neither `--input` nor `--document-folder` exits `USAGE_ERROR`; `run` with both exits `USAGE_ERROR`; unknown argument exits `USAGE_ERROR`; `--log-level invalid` exits `USAGE_ERROR`; `--contract-set-version 99.9.9` (not installed) exits `USAGE_ERROR` with `stage="arguments"` and a message naming the missing version (cli-contract.md, FR-002, FR-006, FR-007, FR-019).
- [X] T013a [P] [US1] Contract test for Ollama-endpoint precedence in `tests/pipeline_tests/test_ollama_endpoint_precedence.py`: (a) no env var, no flag → `ollama_url == "http://localhost:11434"`; (b) `OLLAMA_BASE_URL=http://env-host:11434` in env, no flag → resolves to env value; (c) both env and `--ollama-url http://flag-host:11434` → flag wins; (d) invalid URL scheme (e.g. `not-a-url`) → accepted as opaque string (URL validation is Ollama's job, not the CLI's) (FR-032, research R-006).
- [X] T014 [P] [US1] Contract test for artifact placement in `tests/pipeline_tests/test_artifact_placement.py`: successful run against a valid PDF + existing dest folder produces exactly four files with the reserved names, no subfolders, no temp files, no prefix/suffix/timestamp; pre-existing non-reserved files in the folder (e.g., `expected.json`, `notes.md`) remain untouched (FR-010, FR-011, FR-012, FR-013).
- [X] T015 [P] [US1] Contract test for stdout summary shape in `tests/pipeline_tests/test_stdout_summary.py`: on success, stdout is exactly one line of valid JSON with keys `{document_id, decision, manual_review_required, review_reason, artifacts}`; `artifacts` has the four reserved-filename keys mapped to absolute paths; values match the on-disk `routing_decision.json` (FR-025, stdout-summary.md).
- [X] T016 [P] [US1] Contract test for input-validation exit codes in `tests/pipeline_tests/test_input_validation.py`: missing PDF → `INPUT_NOT_FOUND` (11) and no files written; non-PDF file (text file) → `INVALID_PDF` (12); missing destination folder → `INPUT_NOT_FOUND` (11); read-only destination folder → `OUTPUT_PATH_NOT_USABLE` (14); symlink resolving to a non-PDF → `INVALID_PDF` (12) (FR-016, FR-017, FR-018, edge cases).
- [X] T017 [P] [US1] Contract test for `--overwrite` guard in `tests/pipeline_tests/test_overwrite_guard.py`: pre-existing `preprocess_output.json` without `--overwrite` → `OUTPUT_IN_USE` (13) and file bytes unchanged; with `--overwrite` → success and file replaced; non-reserved files in folder never touched regardless of flag (FR-005, FR-013).
- [X] T018 [P] [US1] Contract test for post-hoc v1.0.0 schema validation in `tests/pipeline_tests/test_schema_validation.py`: if an injected stage callable writes a schema-invalid artifact, CLI exits `SCHEMA_VALIDATION_FAILURE` (30) with `stage="schema_validation"`; on a clean run, all four artifacts pass `validator.artifact.validate_artifact` (FR-020, FR-030, acceptance scenario 5).

### Implementation for User Story 1

- [X] T019 [US1] Implement `src/ledgerlinc_ocr/pipeline/cli.py` argument parser: `argparse` with `run` subcommand; all arguments from `contracts/cli-contract.md` §Arguments (`--input`, `--document-folder`, `--output-dir`, `--document-id`, `--overwrite`, `--pipeline-version`, `--policy-version`, `--contract-set-version`, `--ollama-url`, `--log-level`, `--timeout`); mutual exclusion between `--input` and `--document-folder`; no subcommand → help + exit 10.
- [X] T020 [US1] Implement input validation block in `src/ledgerlinc_ocr/pipeline/cli.py`: resolve paths via `path_resolution.py`; check input PDF exists (→ `INPUT_NOT_FOUND`); check `pdf_check.is_pdf` (→ `INVALID_PDF`); check dest folder exists, is a directory, and is writable (→ `INPUT_NOT_FOUND` or `OUTPUT_PATH_NOT_USABLE`); check no reserved artifact filenames exist unless `--overwrite` (→ `OUTPUT_IN_USE`). All checks occur before any stage writes.
- [X] T021 [US1] Wire `Runner` into `cli.main(argv)`: construct `CLIInvocation` (data-model §1), instantiate `Runner` with default stub stages, call `runner.run(invocation)`, map the returned `(ExitCode, artifacts_written)` to process exit; on `SUCCESS` emit the stdout summary line built from the written `routing_decision.json`.
- [X] T022 [US1] Implement minimal schema-valid stub stage callables in `src/ledgerlinc_ocr/pipeline/runner.py` (or a `stages.py` sibling): each stub writes the minimum fields required by the v1.0.0 schema for its artifact, stamps `document_id`, `processed_at` (UTC ISO-8601), `contract_set_version`, and (where applicable) `pipeline_version`, `policy_version`; `routing_decision.decision = "edge_accept"` and `review_status.manual_review_required = false` for the happy path (FR-026, FR-028, FR-029). Defaults sourced per research R-012: `pipeline_version = ledgerlinc_ocr.__version__`, `policy_version = "stage1-baseline-v0"`.
- [X] T023 [US1] Confirm US1 tests green: `pytest tests/pipeline_tests/test_cli_arguments.py tests/pipeline_tests/test_artifact_placement.py tests/pipeline_tests/test_stdout_summary.py tests/pipeline_tests/test_input_validation.py tests/pipeline_tests/test_overwrite_guard.py tests/pipeline_tests/test_schema_validation.py -v`. Also run the existing `tests/contract_tests/` suite to confirm validator reuse did not regress any prior test.

**Checkpoint**: US1 fully functional; MVP deliverable complete. A developer can run one PDF end to end using only the spec and `--help` (SC-001).

---

## Phase 4: User Story 2 — External Test Harness Runs One Document of the Corpus (Priority: P1)

**Goal**: The harness can point the CLI at a per-document corpus folder (`inv_NNN_<difficulty>/source.pdf`) and trust that the four artifacts land alongside `expected.json` and `notes.md`, with `document_id` derived from the folder name and `review_status` fields mirroring between `routing_decision.json` and `final_structured_payload.json`. All six US2 acceptance scenarios pass.

**Independent Test**: Without reading pipeline source, a harness developer copies the loop from `quickstart.md §4`, runs it over the 20-document corpus at `tests/stage1_vendor_identity/`, and observes: every folder gains exactly the four reserved filenames, no stray files; `review_status.manual_review_required` and `review_status.review_reason` match between `routing_decision.json` and `final_structured_payload.json` for every document; folders tagged `missing_name` satisfy the company-name provenance triad.

### Tests for User Story 2 (write first, confirm failing)

- [X] T024 [P] [US2] Contract test for `--document-folder` path in `tests/pipeline_tests/test_document_folder_input.py`: folder containing `source.pdf` → success, all four artifacts written inside that folder; folder without `source.pdf` → `INPUT_NOT_FOUND` (11) and no artifacts (FR-002, acceptance scenario US2-1, US2-5).
- [X] T025 [P] [US2] Contract test for review-status mirroring in `tests/pipeline_tests/test_review_status_mirror.py`: load both `routing_decision.json` and `final_structured_payload.json` from the same run and assert `review_status.manual_review_required` and `review_status.review_reason` agree byte-for-byte (acceptance scenario US2-2).
- [X] T026 [P] [US2] Contract test for `missing_name` provenance triad in `tests/pipeline_tests/test_missing_name_triad.py`: inject a stub extraction stage that reports no explicit company name; assert `company_name.present = false`, `company_name.inferred = true`, `review_status.manual_review_required = true`, `review_status.review_reason = "company_name_inferred"`, and all four artifacts still validate against v1.0.0 (acceptance scenario US2-3, constitution "company-name provenance").
- [X] T027 [P] [US2] Contract test for corpus idempotency in `tests/pipeline_tests/test_corpus_idempotency.py`: run the CLI twice on the same folder with `--overwrite`; after both runs the folder contains exactly the four reserved pipeline filenames plus any pre-existing human files (`expected.json`, `notes.md`); no lockfiles, no `.tmp`, no backup files remain (FR-010, acceptance scenario US2-4, US2-6). Additionally assert SHA-256 of `source.pdf` is byte-identical before and after both runs (FR-015).
- [X] T028 [P] [US2] Contract test for `trace` bare-filename references AND whole-artifact absolute-path hygiene in `tests/pipeline_tests/test_trace_block.py`: (1) `final_structured_payload.trace` references the three sibling artifacts by bare filename only (no slashes, no absolute paths); folder can be moved to a new location and the trace block remains valid (FR-027). (2) For each of the four produced artifacts, recursively walk every string value and assert no value starts with `/`, `~`, or contains the tmp_path prefix — no persisted artifact may contain a host-specific absolute path (FR-029).

### Implementation for User Story 2

- [X] T029 [US2] Extend `src/ledgerlinc_ocr/pipeline/path_resolution.py` to handle the `--document-folder` path: when the folder resolves but `source.pdf` is absent, return a specific sentinel that `cli.py` maps to `INPUT_NOT_FOUND` with `message="Document folder missing source.pdf: {path}"`. (Distinguish from "dest folder missing" to keep error messages actionable.)
- [X] T030 [US2] Extend the stub `routing` and `final_payload` stages in `src/ledgerlinc_ocr/pipeline/runner.py` (or `stages.py`): both read `edge_extraction_output.json` from disk, propagate `review_status.manual_review_required` and `review_status.review_reason` identically into both artifacts, and write `trace` as `{"preprocess": "preprocess_output.json", "extraction": "edge_extraction_output.json", "routing": "routing_decision.json"}` — bare filenames only.
- [X] T031 [US2] Implement the company-name provenance branch in the stub `routing` stage: if `edge_extraction_output.company_name.present == false` and `company_name.inferred == true`, set `review_status.manual_review_required = true`, `review_status.review_reason = "company_name_inferred"`, `decision = "edge_review_required"`. This logic is deterministic code, not model output (constitution §III, FR mapping).
- [X] T032 [US2] Confirm US2 tests green, then smoke-check by invoking `cli.main(argv)` against the `tmp_document_folder` fixture from T004a (not the real corpus): assert exit 0, four artifacts written into the tmp folder, stdout summary parseable.

**Checkpoint**: US1 + US2 both work. Harness integration can proceed without pipeline code changes.

---

## Phase 5: User Story 3 — Operator Diagnoses a Failed Run (Priority: P2)

**Goal**: Every failure category in FR-021 produces a distinct exit code and a well-formed structured stderr failure record naming the stage and listing any partial artifacts. An operator can diagnose a failure using only exit code + one JSON line on stderr.

**Independent Test**: For each failure category (missing PDF / corrupt PDF / schema-invalid output / read-only destination / simulated Ollama-unreachable at extraction), run the CLI and confirm: the exit code matches the documented category; stderr's last line is a single JSON object validating against `stderr-failure-record.md`; `artifacts_written` accurately lists files on disk; partial artifacts remain on disk for inspection.

### Tests for User Story 3 (write first, confirm failing)

- [X] T033 [P] [US3] Contract test for stderr failure record shape in `tests/pipeline_tests/test_stderr_failure_record.py`: for every non-zero exit (USAGE_ERROR through SCHEMA_VALIDATION_FAILURE), stderr's last line is a single-line JSON object with exactly the keys `{exit_code, exit_code_name, stage, message, artifacts_written}`; `exit_code_name` is drawn from the closed vocabulary; `stage` is drawn from the closed stage vocabulary (FR-023, stderr-failure-record.md).
- [X] T034 [P] [US3] Contract test for partial-artifact preservation in `tests/pipeline_tests/test_partial_artifacts.py`: inject an extraction-stage stub that raises after `preprocess_output.json` is written; assert exit `PROCESSING_FAILURE` (20), `stage="extraction"`, `artifacts_written=["<abs>/preprocess_output.json"]`, and the file still exists on disk after CLI exit (FR-024).
- [X] T035 [P] [US3] Contract test for each processing-stage failure labelling in `tests/pipeline_tests/test_stage_failure_labels.py`: inject a stub that fails at each of preprocess / extraction / routing / final_payload in turn; assert `stage` field in the stderr record matches and `artifacts_written` length grows appropriately (0, 1, 2, 3).
- [X] T036 [P] [US3] Contract test for Ollama-unreachable simulation in `tests/pipeline_tests/test_ollama_unreachable.py`: inject an extraction stub that raises `ConnectionError("cannot reach http://localhost:11434")`; assert `PROCESSING_FAILURE` (20), `stage="extraction"`, `message` mentions the Ollama endpoint URL and does not contain stack-trace lines or internal module paths (edge case: "Host Ollama is unreachable").

### Implementation for User Story 3

- [X] T037 [US3] Implement stderr emission in `src/ledgerlinc_ocr/pipeline/cli.py`: in all non-zero exit paths, construct a `StructuredFailureRecord` with the correct `stage` and `exit_code_name`, serialise via `as_json_line()`, write to stderr as the last line before process exit. Log messages (if any) from `--log-level` must precede this line, never follow it.
- [X] T038 [US3] Implement processing-stage exception handling in `src/ledgerlinc_ocr/pipeline/runner.py`: wrap each of preprocess / extraction / routing / final_payload calls in a try/except that captures the exception, records `stage` as the current stage name, records the accumulating `artifacts_written` list (populated after each successful stage write), and returns a failure tuple `(PROCESSING_FAILURE, artifacts_written, stage, message)` to `cli.py`. The exception's `str()` seeds `message`; stack traces must not leak (stderr-failure-record.md "Must not embed stack traces").
- [X] T039 [US3] Implement schema-validation-failure message in `src/ledgerlinc_ocr/pipeline/runner.py` stage 7: on failure, set `message` to `"{artifact_filename}: {field_path}: {validator_error}"` format so operators can pin the offending artifact and field (stderr-failure-record.md §"Schema validation failure example").
- [X] T040 [US3] Confirm US3 tests green. Cross-check: `python -m ledgerlinc_ocr.pipeline run` (no subcommand) exits 10 and emits a `USAGE_ERROR` failure record with `stage="arguments"` and `artifacts_written=[]`.

**Checkpoint**: Failure diagnosability contract complete. SC-009 passes — every FR-021 category is distinguishable from exit code + one stderr JSON line alone.

---

## Phase 6: User Story 4 — Future Component Plugs In Without Changing the Surface (Priority: P3)

**Goal**: Freeze the surface so later ensemble/voter/service work does not break today's harness invocation. This is asserted via compatibility tests against the frozen contract docs plus a runtime reservation check.

**Independent Test**: Re-run the test suite after this phase. The required-argument set, reserved filenames, destination-folder rules, exit-code vocabulary, and stdout summary shape are all machine-pinned against the contract docs. Attempting to write a reserved-but-off-limits name (`consensus_output.json`, `votes/`) from the pipeline fails the test.

### Tests for User Story 4

- [X] T041 [P] [US4] Contract test for frozen argument set in `tests/pipeline_tests/test_frozen_argument_set.py`: parse `specs/002-cli-contract/contracts/cli-contract.md` (or a derived constant) and assert the live `argparse` parser exposes exactly that set of arguments — no more, no less (FR-009, FR-035, SC-006).
- [X] T042 [P] [US4] Contract test for off-limits name reservation in `tests/pipeline_tests/test_off_limits_names.py`: pre-create `consensus_output.json` and a `votes/` subdirectory in the destination folder; assert the CLI succeeds, does not touch either, and still writes the four reserved artifacts (FR-014, acceptance scenario US4-2).
- [X] T043 [P] [US4] Contract test for path-resolution purity in `tests/pipeline_tests/test_path_resolution_purity.py`: every function in `path_resolution.py` is a pure function of its arguments (no `os.environ`, no `time.now`, no filesystem mutation); tested by patching env and filesystem mocks and asserting outputs are identical across calls (FR-035, acceptance scenario US4-3).

### Implementation for User Story 4

- [X] T044 [US4] No new runtime code expected beyond ensuring `path_resolution.py` stays pure (already true from T010). Adjust only if T043 reveals leakage. If any US4 test fails, fix the smallest surface change that preserves the frozen contract.

**Checkpoint**: SC-005, SC-006, SC-007 all demonstrable from the test suite alone.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Finalise quickstart verification, console-script wiring, and cross-artifact tests that span user stories.

- [X] T045 [P] Run `quickstart.md` §2 and §3 end to end against a PDF produced by the `tmp_pdf_bytes` fixture (T004a) written to a tmp folder. Confirm exit 0, four artifacts, stdout JSON parseable (SC-001).
- [X] T046 [P] Run `quickstart.md` §4 corpus loop over 20 folders produced by the `tmp_corpus_root` fixture (T004a). Confirm every folder contains exactly the four reserved pipeline filenames plus any pre-existing files, and `python -m ledgerlinc_ocr.validator validate corpus <tmp_root>` returns exit 0 (SC-004, SC-007).
- [X] T047 [P] Confirm the `ledgerlinc-pipeline` console-script entry works post-`pip install -e .`: `ledgerlinc-pipeline run --document-folder <tmp_folder> --overwrite` produces identical behavior to `python -m ledgerlinc_ocr.pipeline run ...` (research R-001).
- [X] T047a [P] Network-isolation smoke test in `tests/pipeline_tests/test_network_isolation.py`: monkeypatch `socket.socket.connect` to refuse any non-loopback (127.0.0.0/8) address; run the CLI against stub stages and assert exit 0 (FR-033). Loopback is allowed because local Ollama is reached via loopback during real runs (stubbed here, but the allow-list must permit it).
- [X] T048 Run the full test suite: `pytest -v`. Expect zero failures across both `tests/contract_tests/` and `tests/pipeline_tests/`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies; start immediately.
- **Phase 2 (Foundational)**: Depends on Phase 1. Blocks every user story.
- **Phase 3 (US1)**: Depends on Phase 2. Delivers MVP.
- **Phase 4 (US2)**: Depends on Phase 2; shares `cli.py` and `runner.py` with US1. In practice most US2 tasks integrate into the same modules US1 created, so US2 should ideally run **after** US1 even though both are P1.
- **Phase 5 (US3)**: Depends on Phase 2 and on US1's `cli.py` existing (for stderr emission wiring). Can be developed in parallel with US2 by a separate developer once `cli.py` has the argument-parsing skeleton from T019.
- **Phase 6 (US4)**: Depends on Phase 2, US1, and US2. US4 is assertion-only; no new runtime code expected.
- **Phase 7 (Polish)**: Depends on US1–US3 complete.

### User Story Dependencies

- **US1 (P1)**: First. Delivers the MVP surface.
- **US2 (P1)**: After US1 (shared modules). Deliberately sequenced despite equal priority.
- **US3 (P2)**: Can start in parallel with US2 once `cli.py` exists.
- **US4 (P3)**: After US1, US2, US3.

### Within Each User Story

- Tests (T013–T018 for US1, T024–T028 for US2, T033–T036 for US3, T041–T043 for US4) MUST be written and FAIL before implementation tasks in the same phase.
- Path-resolution + exit-code primitives (Phase 2) before `cli.py` orchestration (Phase 3).
- `cli.py` skeleton (T019) before `runner.py` wiring (T021).
- Stub stage callables (T022, T030, T031) before acceptance scenarios that depend on artifact contents.

### Parallel Opportunities

- **Phase 1**: T003 and T004 are parallel ([P]).
- **Phase 2**: T005, T006, T007 are parallel test files ([P]); T008, T009, T010 are parallel implementation files ([P]); T011 depends on T008–T010.
- **Phase 3**: All six test tasks T013–T018 are parallel ([P]). T019–T022 sequence on the same two files (`cli.py`, `runner.py`); T023 comes after.
- **Phase 4**: All five test tasks T024–T028 are parallel ([P]). T029–T031 touch overlapping files so run sequentially.
- **Phase 5**: All four test tasks T033–T036 are parallel ([P]). T037–T039 touch `cli.py` and `runner.py`; run sequentially.
- **Phase 6**: All three tests T041–T043 are parallel ([P]).
- **Phase 7**: T045–T047 are parallel ([P]).

---

## Parallel Example: User Story 1 Tests

```bash
# All six US1 contract-test files touch different files — run in parallel:
pytest tests/pipeline_tests/test_cli_arguments.py \
       tests/pipeline_tests/test_artifact_placement.py \
       tests/pipeline_tests/test_stdout_summary.py \
       tests/pipeline_tests/test_input_validation.py \
       tests/pipeline_tests/test_overwrite_guard.py \
       tests/pipeline_tests/test_schema_validation.py \
       -n auto -v
```

---

## Implementation Strategy

### MVP First (US1 only)

1. Complete Phase 1 (Setup — T001–T004).
2. Complete Phase 2 (Foundational — T005–T012).
3. Complete Phase 3 (US1 — T013–T023).
4. **STOP and VALIDATE**: A developer can run one PDF end to end using only the CLI contract and `--help`. Validates SC-001.

### Incremental Delivery

1. Phase 1 + Phase 2 → Foundation ready.
2. Add US1 → MVP: single PDF, exit-0 success path, stdout summary.
3. Add US2 → Harness can run the corpus loop against a per-document folder.
4. Add US3 → Operators can diagnose failures from exit code + one stderr line.
5. Add US4 → Surface frozen against future ensemble/voter/service work.
6. Polish phase ties together.

### Parallel Team Strategy

With three developers after Phase 2:

- Developer A: US1 (Phase 3) — owns `cli.py` shell and stub stages.
- Developer B: US2 (Phase 4) — starts once T019 (argparse skeleton) lands; owns stub routing / final-payload stages and trace block.
- Developer C: US3 (Phase 5) — starts once T019 lands; owns stderr record and per-stage exception handling.

US4 (Phase 6) and Polish (Phase 7) roll up at the end.

---

## Notes

- [P] = different files, no ordering dependency with previous [P] tasks in the same phase.
- Stage-3-through-6 implementations in this feature are **stubs that write minimal schema-valid artifacts**. Real preprocessing, extraction, routing, and payload-assembly are downstream features that replace the stubs without changing the CLI surface (design for FR-035 and SC-006).
- No network calls are made from tests. Ollama unreachability in US3 is simulated via an injected stub raising `ConnectionError`, not by actually reaching out to an endpoint.
- The validator module (`ledgerlinc_ocr.validator`) is reused in-process; do not fork schemas or re-implement validation.
- Every task that changes `cli.py` or `runner.py` must rerun the full `tests/pipeline_tests/` suite before marking complete; the contract-test suite is the single source of truth for "the CLI contract holds."
- Commit after each task or logical group. Stop at Phase 3's checkpoint to validate MVP independently.
- **Glossary**: "document folder" = the `--document-folder` INPUT argument target (must contain `source.pdf`). "destination folder" = the OUTPUT location where the four artifacts are written (resolved from `--output-dir`, or defaulted from `--document-folder` / `--input` parent). These may be the same physical folder (the corpus case) but the argument semantics differ. Prefer "destination folder" when discussing outputs.
- SIGINT / keyboard-interrupt handling is deferred beyond stage 1 (see `spec.md` §Edge Cases). The CLI relies on default Python signal behavior; forcing a structured failure record on signal is downstream scope.
