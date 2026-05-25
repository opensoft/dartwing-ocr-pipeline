---
description: "Task list for feature 023 GPU MVP Demo Hardening"
---

# Tasks: GPU MVP Demo Hardening

**Input**: Design documents from `/specs/023-gpu-mvp-demo-hardening/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/cli-contract.md, contracts/demo-report-schema.md, contracts/readiness-vocabulary.md, quickstart.md, checklists/triage-2026-05-24.md, checklists/plan-coverage.md, checklists/remediation-plan-2026-05-25.md

**Tests**: SC-008 mandates CPU-isolated pytest coverage of the CLI flow, exit-code table, readiness failure classes, and report shape with stubbed Paddle/Ollama dependencies. Test tasks are therefore IN SCOPE for every user story and follow the TDD pattern (tests written first, fail, then implementation makes them pass).

**Organization**: Tasks are grouped by user story (US1 P1, US2 P2, US3 P2, US4 P3) so each story can be implemented and tested independently. The MVP is US1 alone.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Setup / Foundational / Polish phases: no story label
- File paths are absolute under the worktree root

## Path Conventions

- Source code: `src/dartwing_ocr/gpu_demo/` (new package; sibling of `extract/`, `router/`, `assembler/`, `preprocessing/`)
- Tests: `tests/integration/gpu_demo/` (new directory, follows feature 005/008/009/020/022 lineage)
- Fixtures: `tests/integration/gpu_demo/fixtures/`
- Docs: `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md` (extend in place per Q15)
- No new contracts under `contracts/stage1_vendor_identity/v1.3.0/` (FR-014: no contract-set bump)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the package skeleton, test directory layout, and (optional) console-script entry. No new pinned dependencies — all needed runtime deps are already in `pyproject.toml`.

- [X] T001 Create `src/dartwing_ocr/gpu_demo/` package directory with empty `__init__.py`
- [X] T002 Create `src/dartwing_ocr/gpu_demo/__main__.py` shim that calls `cli.main()` so `python -m dartwing_ocr.gpu_demo` works (delegates to `cli.py` to be created in Phase 2)
- [X] T003 [P] Create `tests/integration/gpu_demo/` directory with empty `__init__.py` and `conftest.py` skeleton (no fixtures yet; populated in Phase 2)
- [X] T004 [P] Create `tests/integration/gpu_demo/fixtures/` directory with placeholder `.gitkeep` (individual fixture folders are authored in Phase 2 / per-story)
- [X] T005 [P] Add the optional `dartwing-gpu-demo` console-script entry to `pyproject.toml` `[project.scripts]` pointing at `dartwing_ocr.gpu_demo.cli:main`
- [X] T006 [P] Register `gpu` pytest marker in `pyproject.toml` `[tool.pytest.ini_options]` markers list (the marker is referenced by R-023.5 for workstation-only tests; CPU CI uses `-m "not gpu"`)

**Checkpoint**: Package skeleton importable; pytest can collect `tests/integration/gpu_demo/` (no tests yet); `dartwing-gpu-demo` console-script resolves but errors with "Phase 2 incomplete" — that is fine.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that EVERY user story depends on — closed enums, the `DemoRunReport` dataclass with stable serialization, the readiness `Protocol`, CLI argparse skeleton, exit-code table, voter-config loader, run-id helper, stderr severity helper. All four user stories build on this.

**⚠️ CRITICAL**: No US1–US4 implementation may begin until this phase is complete.

### Closed enums and exit codes

- [X] T007 [P] Create `src/dartwing_ocr/gpu_demo/exit_codes.py` defining `ExitCode` IntEnum with the closed table from FR-021 (`SUCCESS=0`, `READINESS_FAILED=1`, `INVALID_INPUT=2`, `PIPELINE_RUNTIME_TIMEOUT=3`, `PIPELINE_RUNTIME_ERROR=4`, `ARTIFACT_SCHEMA_VALIDATION_FAILED=5`) per `contracts/cli-contract.md` §"Exit codes"
- [X] T008 [P] Create `src/dartwing_ocr/gpu_demo/enums.py` defining the closed `Literal` types `RuntimeOutcome`, `StalledPhase`, `QualityStatus`, `FailureKind`, `ReadinessCheckName`, `ReadinessCheckStatus`, `ProbeResult`, `QualityStatusSource` per `data-model.md` §4 and `contracts/demo-report-schema.md`

### Report dataclass + stable serialization

- [X] T009 [P] Create `src/dartwing_ocr/gpu_demo/report.py` defining `DemoRunReport`, `ReadinessSummary`, `ReadinessCheck`, `CheckDiagnostic`, `PhaseTimings`, `CPUFallbackDetection` `pydantic.dataclasses.dataclass` types per `data-model.md` §1–§5
- [X] T010 [P] Add `src/dartwing_ocr/gpu_demo/serialization.py` implementing `to_json_line(report: DemoRunReport) -> str` per R-023.12 (`sort_keys=False`, `ensure_ascii=False`, `separators=(",", ":")`, single line, newline-terminated, UTF-8) and the float-rounding helper `round_wall_clock(value: float) -> float` returning `round(value, 3)` per R-023.21
- [X] T011 [P] Add `src/dartwing_ocr/gpu_demo/version.py` exposing `get_pipeline_version() -> str` via `importlib.metadata.version("dartwing-ocr")` with `"unknown"` fallback per R-023.2

### Readiness base + voter config + helpers

- [X] T012 [P] Create `src/dartwing_ocr/gpu_demo/readiness/__init__.py` and `src/dartwing_ocr/gpu_demo/readiness/base.py` defining the `ReadinessCheck` `Protocol` (one method `run(context: ReadinessContext) -> ReadinessResult`) plus `ReadinessContext` and `ReadinessResult` dataclasses
- [X] T013 [P] Create `src/dartwing_ocr/gpu_demo/voter_config_loader.py` exposing `load_voter_config(path: Path | None) -> VoterConfigReference` honoring `--voter-config` override → feature 005/021 auto-discovery. On error, raises one of `VoterConfigUnreadable`, `VoterConfigMalformed`, `VoterConfigMissingModel` (all three are caught by the orchestrator and mapped to exit 2 per FR-005). On success with a multi-voter config, returns a `VoterConfigReference` whose `extra_voters_ignored: list[str]` field lists the names of voters past the first; the orchestrator reads this field and emits a single stderr `WARN:[run_id] voter config has multiple voters; demo uses the first (model: <name>)` per data-model.md §6 single-voter precondition. No sentinel exception is raised for the multi-voter case.
- [X] T014 [P] Create `src/dartwing_ocr/gpu_demo/run_id.py` exposing `new_run_id() -> str` (UUID4 lowercase 36 chars) and `prefix_for(run_id: str) -> str` returning `run_id[0:8]` per R-023.6
- [X] T015 [P] Create `src/dartwing_ocr/gpu_demo/log.py` exposing `info(run_id, msg)`, `warn(run_id, msg)`, `error(run_id, msg)` that write `INFO:[<8hex>] <msg>\n`, `WARN:[<8hex>] <msg>\n`, `ERROR:[<8hex>] <msg>\n` to `sys.stderr` (line-buffered) per R-023.7 and `contracts/cli-contract.md` §"stdout / stderr discipline"

### CLI argparse + main entry

- [X] T016 Create `src/dartwing_ocr/gpu_demo/cli.py` implementing `main()` and `build_parser()` exposing the closed 5-flag set (`--check-only`, `--document-folder`, `--voter-config`, `--preset`, `--with-evaluator`) plus `--help` and `--version` per `contracts/cli-contract.md` §"Closed flag set". `main()` returns the exit code (does not call `sys.exit` directly, to keep it testable). Depends on T002, T007, T009, T010, T011, T013, T014, T015.

### Quality-status derivation + path canonicalization helpers

- [X] T017 [P] Create `src/dartwing_ocr/gpu_demo/quality_status.py` exposing `derive_quality_status(gate_state: str, manual_review_required: bool, evaluator_result: EvaluatorVerdict | None) -> tuple[QualityStatus, QualityStatusSource]` implementing the R-023.20 truth-table and the "evaluator can downgrade but not upgrade" rule
- [X] T018 [P] Create `src/dartwing_ocr/gpu_demo/folder_canonicalize.py` exposing `canonicalize_document_folder(path: Path) -> Path` and `safe_eager_delete(folder: Path, basenames: tuple[str, ...]) -> None` enforcing FR-017 (symlink-resolved folder, basename-only deletes, exit-2-on-any-failure, symlink-escape guard)

### Foundational contract test (skeleton smoke)

- [X] T019 [P] Create `tests/integration/gpu_demo/test_cli_smoke.py` with two trivial assertions: `python -m dartwing_ocr.gpu_demo --help` exits 0 and `--version` prints a version string. Marks the package as importable end-to-end. Depends on T001, T002, T011, T016.

**Checkpoint**: All shared infrastructure ready. The CLI parses flags but does not yet run readiness checks or the pipeline. All four user stories can now begin in parallel.

---

## Phase 3: User Story 1 - Canonical one-command GPU MVP demo (Priority: P1) 🎯 MVP

**Goal (US1):** Operator runs `python -m dartwing_ocr.gpu_demo` (no flags) against the canonical fixture, all 8 readiness checks pass, the four canonical stage 1 artifacts are produced and schema-valid within 600 s, and the `DemoRunReport` JSON line shows `runtime_outcome: "success"` + `quality_status: "pass"`.

**Independent Test (US1):** With host Ollama running and the configured extraction model GPU-placed, run the bare command against `tests/stage1_vendor_identity/inv_001_easy/`. Confirm exit 0, the four artifacts on disk, schema-valid, within 600 s.

### Tests for User Story 1 (TDD — write first, fail, then implement)

- [X] T020 [P] [US1] Create CPU-isolated fixture `tests/integration/gpu_demo/fixtures/ok/` with `source.pdf` symlinked to `tests/stage1_vendor_identity/inv_001_easy/source.pdf` per R-023.18, plus a minimal valid `voter_config.yaml` (single voter, model name `qwen2.5-vl:7b`)
- [X] T021 [P] [US1] Author Paddle ROCm preflight stub fixture in `tests/integration/gpu_demo/conftest.py` (`paddle_preflight_stub` monkeypatch fixture returning a fake `PreflightResult(device="rocm_gpu")`)
- [X] T022 [P] [US1] Author host Ollama HTTP stub fixture in `tests/integration/gpu_demo/conftest.py` (`ollama_http_stub` using `httpx.MockTransport`; responds to `/api/version` with `0.4.5` and `/api/ps` with a fully-GPU-placed entry for the configured model)
- [X] T023 [P] [US1] Write `tests/integration/gpu_demo/test_cli_flow.py::test_happy_path` asserting exit 0, four artifacts present, `runtime_outcome: "success"`, `quality_status: "pass"`, all 8 readiness checks `"pass"`, schema_version `"0.1.0"`, `phase_timings` populated with 4 non-null floats. Test MUST initially fail.
- [X] T024 [P] [US1] Write `tests/integration/gpu_demo/test_report_shape.py::test_success_outcome` asserting the 17 top-level keys are present with the success-outcome values from `contracts/demo-report-schema.md` outcome matrix. Test MUST initially fail.

### Implementation for User Story 1

#### Readiness check modules (6 pre-pipeline + 2 runtime-monitor entries)

- [X] T025 [P] [US1] Implement `src/dartwing_ocr/gpu_demo/readiness/interpreter.py` (check 1: compares `os.path.realpath(sys.executable)` against the expected `.venv-paddle-rocm` prefix; returns a `ReadinessResult` with `name="interpreter/venv"`)
- [X] T026 [P] [US1] Implement `src/dartwing_ocr/gpu_demo/readiness/paddle_preflight.py` (check 2: composes feature 014's preflight entry point; under pytest, monkeypatched by the `paddle_preflight_stub` fixture)
- [X] T027 [P] [US1] Implement `src/dartwing_ocr/gpu_demo/readiness/ollama_reach.py` (check 3: `httpx.get(OLLAMA_BASE_URL + "/api/ps", timeout=2.0)`; captures the response body for re-use by checks 5 and 6)
- [X] T028 [P] [US1] Implement `src/dartwing_ocr/gpu_demo/readiness/ollama_version.py` (check 4: `httpx.get(OLLAMA_BASE_URL + "/api/version")`; compares via `packaging.version.Version` against `Version("0.4.0")` per R-023.10)
- [X] T029 [P] [US1] Implement `src/dartwing_ocr/gpu_demo/readiness/ollama_placement.py` (check 5: re-uses the `/api/ps` body cached by check 3; asserts model entry exists AND `size_vram > 0` AND `size_vram == size` per FR-005)
- [X] T030 [P] [US1] Implement `src/dartwing_ocr/gpu_demo/readiness/ollama_ctx_len.py` (check 6: reads `int(os.environ.get("OLLAMA_CONTEXT_LENGTH", "2048"))`; compares against `/api/ps.context_length` when exposed; soft-pass + WARN when not exposed per R-023.14 fallback)
- [X] T031 [P] [US1] Implement `src/dartwing_ocr/gpu_demo/readiness/schema_validation.py` (check 7: composes `dartwing_ocr.validator` against the 4 canonical artifacts post-pipeline; aggregates ALL failing artifacts into the `observed` list per CHK052/remediation)
- [X] T032 [P] [US1] Implement `src/dartwing_ocr/gpu_demo/readiness/runtime_timeout.py` (check 8: SIGALRM-driven monitor that records elapsed wall-clock; raises `TimeoutError` mapped to `runtime_outcome: "timeout"` if 600 s elapses during any phase)

#### Readiness runner (fixed-order execution + skip-on-fail)

- [X] T033 [US1] Implement `src/dartwing_ocr/gpu_demo/readiness/runner.py` executing the 8 checks in the FR-016 fixed order (interpreter/venv → paddle-rocm-preflight → ollama-reachability → ollama-version → ollama-model-gpu-placement → ollama-context-length → artifact-schema-validation → pipeline-runtime-timeout) with skip-on-upstream-fail per FR-026; returns a `ReadinessSummary`. Depends on T012 + T025–T032.

#### Orchestrator (eager-delete + phase invocations + report assembly)

- [X] T034 [US1] Implement `src/dartwing_ocr/gpu_demo/orchestrator.py` **skeleton** driving the lifecycle from `data-model.md` §8: (1) argparse → CLIArgs, (2) voter-config load (raises → exit 2), (3) canonicalize document-folder (raises → exit 2), (3a) **verify `source.pdf` exists inside the canonicalized folder** (raises `SourcePDFMissing` → exit 2 per FR-027, before readiness runs) — this gate applies to every run mode except `--check-only`, (4) call readiness runner for checks 1–6, (5) eager-delete the 4 canonical artifacts in the canonicalized folder via T018's helper, (6) **pluggable `PipelineComposer` Protocol** invocation per R-023.1 — the default in-process composer raises `PipelineUnavailable` as a placeholder; the real feature 003/005/008/009 wiring is filed as T034a — with `signal.alarm(600)` set around the pipeline, capturing each phase's wall-clock into `PhaseTimings` per FR-025, (7) post-pipeline checks 7–8, (8) post-run CPU-fallback interrogation (R-023.15 placeholder for US4), (9) assemble `DemoRunReport`, (10) emit JSON line + exit per `ExitCode`. Depends on T007–T018, T033. (The concrete `SourcePDFMissing` raise / mapping is filed as T043 in US2 because its failing-path test lives there; the orchestrator skeleton in this task wires the call site at step (3a).)
- [ ] T034a [US1] Wire the default `PipelineComposer` (`src/dartwing_ocr/gpu_demo/orchestrator.py:_DefaultPipelineComposer`) to features 003/005/008/009's in-process Python entry points (R-023.1). Each phase method imports its sub-module lazily, invokes the per-feature pipeline-runner function with the canonicalized document folder + preset + voter config, captures wall-clock timing for `PhaseTimings`, and translates sub-module exceptions per the R-023.3 mapping table to the appropriate `runtime_outcome` value. Depends on T034 + (sub-module API inspection per `research.md` R-023.1). Workstation manual GPU smoke (T073) is the validation path; CPU tests use the stub composer from the conftest.

#### Wire up `cli.py` entry to orchestrator

- [X] T035 [US1] Update `src/dartwing_ocr/gpu_demo/cli.py::main()` to instantiate the orchestrator with parsed args and return its exit code. Depends on T016, T034.

**Checkpoint US1:** Running `python -m dartwing_ocr.gpu_demo` against the canonical fixture (with stubbed Paddle + Ollama under CPU pytest) completes the full pipeline path and emits a success `DemoRunReport`. `test_happy_path` and `test_success_outcome` from T023/T024 now pass.

---

## Phase 4: User Story 2 - Fail-fast GPU readiness preflight (Priority: P2)

**Goal (US2):** Operator runs `python -m dartwing_ocr.gpu_demo --check-only` and gets a clear nonzero exit within 10 seconds when any of the 6 infrastructure readiness classes is broken, with the failing check named.

**Independent Test (US2):** Break each prerequisite in isolation (wrong venv, Ollama down, model unloaded, partial CPU placement, voter-config absent, OLLAMA_CONTEXT_LENGTH too small). Run `--check-only`. Confirm exit 1 within 10 s, `failing_check_name` matches the broken prerequisite, no pipeline artifacts written.

### Tests for User Story 2

- [X] T036 [P] [US2] Create fixture folders `tests/integration/gpu_demo/fixtures/missing_source_pdf/` and `tests/integration/gpu_demo/fixtures/malformed_voter_config/` per R-023.18 (each populated with the minimal content for its negative-path test)
- [X] T037 [P] [US2] Write `tests/integration/gpu_demo/test_check_only.py::test_check_only_pass` asserting `--check-only` with all stubs passing exits 0, emits the stable-shape `DemoRunReport` with `runtime_outcome: null`, `phase_timings.* = null`, `artifact_paths = null`, `document_folder = null`, checks 7–8 status `"skipped"`. Test MUST initially fail.
- [X] T038 [P] [US2] Write `tests/integration/gpu_demo/test_check_only.py::test_check_only_within_10s` asserting `--check-only` wall-clock < 10 s with warm fixtures (SC-007)
- [X] T039 [P] [US2] Write `tests/integration/gpu_demo/test_readiness_order.py::test_skip_on_upstream_fail` parameterized across each of checks 1–6 failing; asserts checks before the failing one are `"pass"`, the failing check is `"fail"`, and ALL checks after are `"skipped"`; `failing_check_name` is the first failing check
- [X] T040 [P] [US2] Write `tests/integration/gpu_demo/test_readiness_failures.py` with one parameterized test per failure class (interpreter/venv wrong, paddle preflight CPU-mode, ollama-reach connection error, ollama-version < 0.4.0 + missing size_vram, ollama-placement partial CPU, ollama-context-length below minimum); each asserts exit 1, `runtime_outcome: null`, `failure_kind: "readiness-failed"`, `failing_check_name` matches the broken class, and the per-check diagnostic shape (`checked`/`observed`/`expected`/`remediation`) per R-023.11
- [X] T041 [P] [US2] Write `tests/integration/gpu_demo/test_exit_codes.py` parameterized across the closed 0–5 table (FR-021); asserts exit code matches each (`runtime_outcome`, `failure_kind`) combination

### Implementation for User Story 2

- [X] T042 [US2] Implement `--check-only` branch in `src/dartwing_ocr/gpu_demo/orchestrator.py`: when the flag is set, skip eager-delete, skip pipeline phases, skip post-run interrogation, mark checks 7–8 as `"skipped"` with `elapsed_seconds=0.0`, set the runtime/quality/timing/artifact fields to null per FR-025a, emit the stable-shape report. Includes the INFO log line "ignoring --document-folder / --preset / --with-evaluator under --check-only" when those flags were also set. Depends on T034.
- [X] T043 [US2] Implement missing-`source.pdf` validation in `src/dartwing_ocr/gpu_demo/orchestrator.py` (raise `SourcePDFMissing` mapped to exit 2 per FR-027). Depends on T034.
- [X] T044 [US2] Implement closed-vocabulary diagnostic objects in each readiness module (T025–T030) so failing checks emit the full `CheckDiagnostic` shape (closed `checked`/`observed`/`expected`/`remediation` keys per R-023.11). Each module adds its own `remediation` text per `contracts/readiness-vocabulary.md`. Depends on T025–T030. *(Satisfied during US1 — the T025/T026/T027/T028/T029/T030/T031 readiness modules already emit full `CheckDiagnostic` shapes; verified by post-MVP analyze IMP4.)*

**Checkpoint US2:** `--check-only` runs every infrastructure readiness check, exits 1 on any failure with the failing check identified, completes in ≤10 s warm. `test_check_only_*`, `test_skip_on_upstream_fail`, `test_readiness_failures`, `test_exit_codes` all pass.

---

## Phase 5: User Story 3 - Specific readiness diagnostics (Priority: P2)

**Goal (US3):** Every failure class is reported with a closed-key diagnostic (`checked`/`observed`/`expected`/`remediation`) on both stdout JSON and stderr text. Timeout outcomes identify the stalled phase. Multi-artifact validation failures aggregate all failing artifacts.

**Independent Test (US3):** Force each of the named failure classes deterministically; confirm the stderr severity-prefixed line names the failing check and reproduces the diagnostic from the JSON report verbatim (same `observed`/`expected`/`remediation` content).

### Tests for User Story 3

- [X] T045 [P] [US3] Write `tests/integration/gpu_demo/test_diagnostics.py::test_stderr_mirrors_json_diagnostic` asserting that for each readiness failure class, the stderr `ERROR:[<8hex>]` line and the `readiness.checks[<name>].diagnostic` JSON object surface the same `observed`/`expected`/`remediation` content
- [X] T046 [P] [US3] Write `tests/integration/gpu_demo/test_runtime_outcomes.py::test_timeout_sets_stalled_phase` parameterized across the four phases; injects a 700 s sleep into each phase; asserts `runtime_outcome: "timeout"`, `stalled_phase` matches the injected phase, exit code 3, partial new artifacts remain on disk
- [X] T047 [P] [US3] Write `tests/integration/gpu_demo/test_runtime_outcomes.py::test_failed_at_phase` parameterized across the four `failed_at_<phase>` values; injects a sub-module exception per phase; asserts the matching `runtime_outcome` value and exit code 4
- [X] T048 [P] [US3] Write `tests/integration/gpu_demo/test_schema_validation.py::test_multi_artifact_failure` corrupting two of the four post-pipeline artifacts; asserts check 7's `observed` is a list of two `{path, error}` objects in canonical order per CHK052/remediation
- [X] T049 [P] [US3] Write `tests/integration/gpu_demo/test_check_only.py::test_check_only_does_not_check_source_pdf` asserting `--check-only` passes even when the per-doc folder is missing `source.pdf` per FR-018 + CHK037/remediation

### Implementation for User Story 3

- [X] T050 [US3] Implement the stalled-phase capture mechanism in `src/dartwing_ocr/gpu_demo/orchestrator.py`: wrap each phase call in a `current_phase` context manager; the SIGALRM handler reads `current_phase` and populates `stalled_phase` in the report. Depends on T034.
- [X] T051 [US3] Implement multi-artifact aggregation in `src/dartwing_ocr/gpu_demo/readiness/schema_validation.py`: iterate all 4 artifacts, collect every failure into a list of `{path, error}` objects in canonical order; emit list as `observed`. Depends on T031.
- [X] T052 [US3] Implement the `CheckDiagnostic` → stderr-line projection in `src/dartwing_ocr/gpu_demo/log.py` (or a new `diagnostics.py`): `format_diagnostic_line(check_name, diagnostic) -> str` returning `"readiness check '{name}' failed — observed {observed!r}, expected {expected!r}. Remediation: {remediation}"`. The orchestrator calls this once per failing check, emitting via `log.error(run_id, line)`. Depends on T015, T044.

**Checkpoint US3:** Every failure class produces a structured diagnostic in both JSON and stderr; timeout reports the stalled phase; multi-artifact failures aggregate. `test_stderr_mirrors_json_diagnostic`, `test_timeout_sets_stalled_phase`, `test_failed_at_phase`, `test_multi_artifact_failure`, `test_check_only_does_not_check_source_pdf` all pass.

---

## Phase 6: User Story 4 - Runtime success separated from extraction quality (Priority: P3)

**Goal (US4):** `runtime_outcome` (pipeline ran successfully) is reported separately from `quality_status` (extraction quality from gate + manual_review_required, optionally augmented by `--with-evaluator`). CPU fallback detected post-run flips a `success` to `failed_at_extraction` with `failure_kind: "cpu-fallback-detected"`.

**Independent Test (US4):** Use a fixture where extraction reliably produces `manual_review_required: true`; confirm `runtime_outcome: "success"` AND `quality_status: "review_required"`. Separately, force a CPU fallback mid-run; confirm the post-run probe rewrites the outcome to `failed_at_extraction`.

### Tests for User Story 4

- [X] T053 [P] [US4] Create fixtures `tests/integration/gpu_demo/fixtures/weak_quality/`, `with_evaluator_no_sidecar/`, `with_evaluator_with_sidecar/` per R-023.18 (each with synthetic stage 1 artifacts that drive the corresponding `quality_status` path)
- [X] T054 [P] [US4] Write `tests/integration/gpu_demo/test_quality_status.py` parameterized across the R-023.20 truth-table (6 rows × evidence-gate state × manual_review_required → quality_status). Each row asserts the right `quality_status` AND `quality_status_source: "gate"`
- [X] T055 [P] [US4] Write `tests/integration/gpu_demo/test_with_evaluator.py::test_warn_and_skip_no_sidecar` asserting `--with-evaluator` against `with_evaluator_no_sidecar/` produces a stderr `WARN:` line, `quality_status_source: "gate"` per CHK061/remediation, exit code unchanged from a no-flag run
- [X] T056 [P] [US4] Write `tests/integration/gpu_demo/test_with_evaluator.py::test_evaluator_downgrades_pass_to_weak` asserting that when the evaluator (subprocess-mocked) reports `semantic_table_quality_passed: false` against a `quality_status: "pass"` baseline, the final `quality_status` becomes `"weak"` AND `quality_status_source: "evaluator"` per R-023.20
- [X] T057 [P] [US4] Write `tests/integration/gpu_demo/test_with_evaluator.py::test_evaluator_subprocess_failure` asserting that when the evaluator subprocess exits non-zero, a `WARN:` line is emitted, `quality_status_source` stays `"gate"`, demo exit code is unchanged per R-023.13 expanded clause
- [X] T058 [P] [US4] Write `tests/integration/gpu_demo/test_cpu_fallback.py::test_post_run_probe_detects_ollama_fallback` mocking the post-run `/api/ps` to return `size_vram == 0`; asserts the outcome is rewritten to `runtime_outcome: "failed_at_extraction"`, `failure_kind: "cpu-fallback-detected"`, exit 4
- [X] T059 [P] [US4] Write `tests/integration/gpu_demo/test_cpu_fallback.py::test_post_run_probe_unreachable` mocking the post-run Ollama probe to time out (2 s budget per R-023.15); asserts `cpu_fallback_detection.ollama_post_run: "unreachable"`, `failure_kind: "post-run-interrogation-unreachable"`, exit code per the original pipeline outcome

### Implementation for User Story 4

- [X] T060 [US4] Implement `src/dartwing_ocr/gpu_demo/quality_derivation.py` (uses T017's `derive_quality_status`) reading the evidence-gate state from the `run_summary` JSON line that feature 014/020 preprocessing returns in-process to the orchestrator — specifically `run_summary["evidence_gate_documents"][<document_id>]["state"]` per feature 020's RunSummary.SCHEMA_VERSION 0.1.7 additive fields — and `manual_review_required` from `final_structured_payload.json` (feature 009 output). The orchestrator captures the preprocessing run_summary at T034 and threads it into this module's `derive(...)` entry point. Returns `(QualityStatus, QualityStatusSource)`. Depends on T017, T034.
- [X] T061 [US4] Implement `--with-evaluator` subprocess invocation in `src/dartwing_ocr/gpu_demo/evaluator_subprocess.py`: runs `python -m dartwing_ocr.evaluator …` with a 60 s wall-clock budget per R-023.13 expanded clause; reads `evaluation_document.json` from the per-doc folder; returns an `EvaluatorVerdict` or `None` (on warn-and-skip / failure). Depends on T013, T015.
- [X] T062 [US4] Implement post-run device interrogation in `src/dartwing_ocr/gpu_demo/cpu_fallback.py`: two probes (Ollama `/api/ps` re-query, Paddle device re-invocation) with 2 s per-probe + 5 s aggregate timeout per R-023.15; returns a `CPUFallbackDetection` dataclass; orchestrator uses its result to rewrite `runtime_outcome` and set `failure_kind` as needed (CHK058 + SC-004 enforcement). Depends on T026, T027, T034.
- [X] T063 [US4] Wire `--with-evaluator` flag handling into `src/dartwing_ocr/gpu_demo/orchestrator.py`: after pipeline success, if `--with-evaluator` is set AND the sidecar exists, invoke T061; combine evaluator verdict with T060's gate-derived result via T017's "downgrade-only" rule; emit warn-and-skip stderr line when sidecar is missing. Depends on T034, T060, T061.
- [X] T064 [US4] Wire post-run CPU-fallback detection into `src/dartwing_ocr/gpu_demo/orchestrator.py` after every pipeline run (success or failure); when a fallback is detected, rewrite `runtime_outcome` from `success` to `failed_at_extraction` and set `failure_kind: "cpu-fallback-detected"` per R-023.15. Depends on T034, T062.

**Checkpoint US4:** `runtime_outcome` and `quality_status` are now two distinct fields; `--with-evaluator` augments quality (downgrade-only) when a sidecar is present and warn-and-skips otherwise; post-run interrogation enforces SC-004. All US4 tests pass.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Cross-story refinements, fixture for the symlink-escape guard, the runbook deliverable, and the final byte-stability + 3-run smoke procedure.

### Path-canonicalization + eager-delete safety

- [X] T065 [P] Create fixture `tests/integration/gpu_demo/fixtures/symlink_escape/` per R-023.18 (folder with a `preprocess_output.json` symlink that resolves outside the folder)
- [X] T066 [P] Write `tests/integration/gpu_demo/test_eager_delete.py::test_symlink_escape_aborts_exit_2` asserting the symlink-escape fixture causes exit 2 before any phase runs
- [X] T067 [P] Write `tests/integration/gpu_demo/test_eager_delete.py::test_partial_delete_failure_aborts_exit_2` mocking one of the four delete operations to raise `PermissionError`; asserts exit 2 before any phase runs
- [X] T068 [P] Write `tests/integration/gpu_demo/test_eager_delete.py::test_idempotent_on_missing_files` asserting eager-delete succeeds when one of the four canonical artifacts does not yet exist (idempotent per FR-017 + CHK007 cluster)
- [X] T069 [P] Write `tests/integration/gpu_demo/test_eager_delete.py::test_preserves_non_canonical_files` asserting `source.pdf`, `expected.json`, `notes.md`, `semantic_table_truth.json`, debug PNGs, and a prior `evaluation_document.json` are ALL preserved across a run (SC-010)

### Float precision + byte stability

- [X] T070 [P] Write `tests/integration/gpu_demo/test_float_precision.py` asserting all wall-clock fields in `DemoRunReport` (every `elapsed_seconds`, `phase_timings.*`, `total_runtime_seconds`) serialize to ≤3 decimal places (R-023.21)

### Multi-voter handling

- [X] T071 [P] Write `tests/integration/gpu_demo/test_voter_config.py::test_multi_voter_warns_and_uses_first` asserting that a voter config with two voters produces a `WARN:` stderr line and the demo proceeds with the first voter's model per R-023 §6 single-voter precondition

### Multi-Ollama disambiguation (Edge Case)

- [X] T071a [P] Write `tests/integration/gpu_demo/test_ollama_base_url.py::test_demo_ignores_other_ollama_urls` mounting a competing `httpx.MockTransport` on a non-`OLLAMA_BASE_URL` URL with deliberately-wrong responses (e.g., version 0.1.0, model not loaded); asserts the demo never probes the competing URL and uses only the canonical `OLLAMA_BASE_URL` per R-023.14 + spec.md Edge Case "Multiple Ollama instances are running"

### Runbook deliverable

- [X] T072 Append the three new sections plus the colleague-dry-run appendix to `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md` per R-023.17: **§ Canonical Demo Command** (the bare command, the 5 flags, defaults, worked examples), **§ Readiness Failure Recovery Matrix** (one row per FR-016 closed-vocabulary check listing diagnostic shape + remediation), **§ Three-Run Stability Smoke Procedure (SC-006)** (operator pre-conditions, three successive runs, byte-comparison rule for the three deterministic artifacts, the operator sign-off block), and **§ Appendix: Colleague Dry-Run Sign-Off** (audit walkthrough 2026-05-25 Q11 — a colleague unfamiliar with the demo follows the runbook end-to-end, records gaps inline, and signs a dated line; no new SC). Also consolidate the prerequisites (Paddle venv, host Ollama startup script, OLLAMA_CONTEXT_LENGTH, 30 s cold-cache informal `--check-only` target, minimum Ollama version) into a single visible block at the top.

### Workstation-only smoke test (workstation gate; not CI)

- [ ] T073 [P] Write `tests/integration/gpu_demo/test_workstation_smoke.py::test_three_run_stability` marked `@pytest.mark.gpu` running the demo three times against the canonical fixture without stubs, comparing `runtime_outcome` + `quality_status` + the three deterministic artifact byte-contents across the three runs per SC-006. This test is workstation-only; CPU CI skips it via `pytest -m "not gpu"` (R-023.5).

### Documentation cross-references

- [X] T074 [P] Update `CLAUDE.md` (project-local) under `## Recent Changes` with a one-paragraph entry for feature 023 referencing `python -m dartwing_ocr.gpu_demo`, the runbook section, and SC-006 sign-off

### FR ↔ task ↔ test traceability matrix

- [X] T074a [P] Author `specs/023-gpu-mvp-demo-hardening/coverage-fr-task-test.md` per audit walkthrough 2026-05-25 Q8, mirroring feature 022's `coverage-fr-task-test.md`. One row per FR / SC mapping to (a) the implementation task IDs that satisfy it, and (b) the test task IDs that exercise it. Regenerated as part of Phase 7 polish so it reflects the as-merged state.

### Final validation

- [X] T075 Run the full CPU pytest suite for this feature (`pytest tests/integration/gpu_demo/ -m "not gpu"`) and confirm: (a) ≤ 60 s wall-clock total per R-023.16, (b) all tests pass, (c) zero `xfail` results, (d) every CHK### test ID surfaced in `checklists/plan-coverage.md` §B/§C/§D is covered by at least one test function

**Checkpoint Polish:** All cross-story safety tests pass; the runbook is operator-ready; the workstation manual GPU smoke gate (SC-006/T073) is documented and can be invoked manually. Feature is ready for `/speckit.implement` if any tasks remain unchecked, or for review and merge if all pass.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup, T001–T006)**: No dependencies — can start immediately
- **Phase 2 (Foundational, T007–T019)**: Depends on Phase 1 completion — BLOCKS all user stories
- **Phase 3 (US1, T020–T035)**: Depends on Phase 2 completion
- **Phase 4 (US2, T036–T044)**: Depends on Phase 2 completion (does NOT depend on US1 implementation — independent test path)
- **Phase 5 (US3, T045–T052)**: Depends on US1 readiness modules (T025–T032) + orchestrator (T034) — most US3 tasks are *enhancements* to those modules
- **Phase 6 (US4, T053–T064)**: Depends on US1 orchestrator (T034) + US3 stalled-phase capture (T050)
- **Phase 7 (Polish, T065–T075)**: Depends on US1–US4 implementation

### Within-Story Notes

- US1 is the MVP. Stopping after US1 yields a working demo (no `--check-only` flag, no `--with-evaluator`, but the bare command works).
- US2 is parallel-implementable with US1 if two developers split the work — US2 needs T034 (orchestrator) to exist as a hook, but otherwise its check-only branch (T042) is independent of the pipeline-running branch.
- US3 enhances diagnostics emitted by US1 readiness modules — implementations are mostly adding `CheckDiagnostic` payloads (T044 batches this into US2 tests but the logic lands in US3 polish).
- US4 is the most isolated — adds the quality-status derivation, evaluator subprocess, and CPU-fallback detection on top of US1's success path. No US1 changes required if US1 is built defensively (orchestrator already wires the `quality_status` field as `null` by default).

### Parallel Opportunities

- **Phase 1**: T003, T004, T005, T006 in parallel (different files / pyproject entries).
- **Phase 2**: T007–T015 are all `[P]` (different files, no inter-dependencies); T016 must wait for T002+T007+T009+T010+T011+T013+T014+T015; T017–T019 are independent of T016 and can run in parallel.
- **Phase 3 (US1)**: Tests T020–T024 in parallel; readiness modules T025–T032 in parallel; T033 (runner) depends on T012 + T025–T032; T034 (orchestrator) depends on all of Phase 2 + T033.
- **Phase 4 (US2)**: All tests T037–T041 in parallel; T036 (fixtures) in parallel.
- **Phase 5 (US3)**: All tests T045–T049 in parallel; implementations T050–T052 share the orchestrator file but otherwise can be authored back-to-back.
- **Phase 6 (US4)**: All tests T054–T059 in parallel; implementations T060/T061/T062 in parallel; T063+T064 serial (both touch orchestrator).
- **Phase 7**: T065 + T066–T069 in parallel; T070, T071, T073, T074 in parallel; T072 serial (single doc file); T075 is the final validation step.

---

## Parallel Example: Phase 2 (Foundational)

```bash
# Launch all parallel-marked Phase 2 tasks together (separate files, no cross-deps):
Task: T007 src/dartwing_ocr/gpu_demo/exit_codes.py
Task: T008 src/dartwing_ocr/gpu_demo/enums.py
Task: T009 src/dartwing_ocr/gpu_demo/report.py
Task: T010 src/dartwing_ocr/gpu_demo/serialization.py
Task: T011 src/dartwing_ocr/gpu_demo/version.py
Task: T012 src/dartwing_ocr/gpu_demo/readiness/base.py
Task: T013 src/dartwing_ocr/gpu_demo/voter_config_loader.py
Task: T014 src/dartwing_ocr/gpu_demo/run_id.py
Task: T015 src/dartwing_ocr/gpu_demo/log.py
# Then T016 (cli.py) — depends on the above
# Then T017, T018, T019 in parallel — independent of T016
```

## Parallel Example: Phase 3 (US1) — All 8 readiness checks

```bash
# After T033 (runner) skeleton and T020–T022 (fixtures + stubs) are in place,
# launch all 8 readiness check modules in parallel — each is a separate file:
Task: T025 src/dartwing_ocr/gpu_demo/readiness/interpreter.py
Task: T026 src/dartwing_ocr/gpu_demo/readiness/paddle_preflight.py
Task: T027 src/dartwing_ocr/gpu_demo/readiness/ollama_reach.py
Task: T028 src/dartwing_ocr/gpu_demo/readiness/ollama_version.py
Task: T029 src/dartwing_ocr/gpu_demo/readiness/ollama_placement.py
Task: T030 src/dartwing_ocr/gpu_demo/readiness/ollama_ctx_len.py
Task: T031 src/dartwing_ocr/gpu_demo/readiness/schema_validation.py
Task: T032 src/dartwing_ocr/gpu_demo/readiness/runtime_timeout.py
```

---

## Implementation Strategy

### MVP First (US1 only)

1. Complete Phase 1: Setup (T001–T006) — ~1 hour
2. Complete Phase 2: Foundational (T007–T019) — ~1 day
3. Complete Phase 3: US1 (T020–T035) — ~2–3 days
4. **STOP and VALIDATE**: `pytest tests/integration/gpu_demo/test_cli_flow.py` should pass with stubs; manual workstation run should produce the four canonical artifacts.
5. Demo / sign off the MVP if ready.

### Incremental Delivery

- After MVP: add US2 (`--check-only`) → operators get a fast preflight (most operationally valuable next).
- Then US3 (specific diagnostics) → triage becomes self-service.
- Then US4 (quality separation + CPU fallback safety) → SC-004 + SC-005 satisfied.
- Then Phase 7 → SC-006 + SC-010 fully closed; workstation manual smoke gate documented.

### Parallel Team Strategy

If two developers:
- Dev A: Phase 1 + Phase 2 (T001–T019, ~2 days)
- Dev B (after Phase 2): US1 (T020–T035)
- Dev A (after Phase 2 + US1 in flight): US2 (T036–T044) — does not block on US1
- Both: converge on US3, US4, Polish

---

## Format validation

Every task above conforms to the required format:
- Checkbox `- [ ]` ✓
- Sequential Task ID `T###` ✓
- `[P]` marker only on parallelizable tasks (different files, no incomplete dependencies) ✓
- `[Story]` label on every US1/US2/US3/US4 task; absent on Setup, Foundational, and Polish tasks ✓
- Exact file path or directory in every description ✓

**Total tasks:** 77 (75 + T071a from the analyze-remediation pass + T074a from the audit-walkthrough Q8)
**Per-story counts:**
- Setup (Phase 1): 6 tasks
- Foundational (Phase 2): 13 tasks (T007–T019)
- US1 (Phase 3): 16 tasks (T020–T035) — MVP scope
- US2 (Phase 4): 9 tasks (T036–T044)
- US3 (Phase 5): 8 tasks (T045–T052)
- US4 (Phase 6): 12 tasks (T053–T064)
- Polish (Phase 7): 13 tasks (T065–T075 + T071a + T074a)

**Parallel opportunities:** ~38 tasks marked `[P]`. Phases 2, 3, 4, 6, 7 each have ≥4 parallel tasks; the longest single-file-serial chain is Phase 2 → T016 (cli.py) → T034 (orchestrator.py) → T035 (cli wire-up).

**Independent test criteria:**
- US1: bare `python -m dartwing_ocr.gpu_demo` against `inv_001_easy/` exits 0 with 4 schema-valid artifacts within 600 s.
- US2: `--check-only` exits 1 within 10 s for any of the 6 infrastructure-check failure classes, no pipeline artifacts written.
- US3: each named failure class emits a structured `CheckDiagnostic` on both stdout JSON and stderr text; timeouts identify the stalled phase; multi-artifact validation aggregates failures.
- US4: `runtime_outcome` and `quality_status` are distinct fields; `--with-evaluator` augments quality (downgrade-only); post-run interrogation rewrites silent-CPU-fallback success into `failed_at_extraction`.

**Suggested MVP scope:** US1 alone (Phases 1 + 2 + 3). Demo-able after T035; iterates from there.
