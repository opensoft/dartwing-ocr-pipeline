# Tasks: Workstation Paddle GPU Preprocessing Validation

**Input**: Design documents from `/specs/014-paddle-gpu-preprocessing/`
**Prerequisites**: `plan.md`, `spec.md` (US1 P1, US2 P2, US3 P3), `research.md` (R-014.1–R-014.11), `data-model.md`, `contracts/cli-contract.md`, `quickstart.md`

**Tests**: REQUIRED. FR-018, FR-019, FR-020 mandate a test surface, and `plan.md` §Contract Test Coverage names five contract guarantees that each need a corresponding test.

**Organization**: Tasks are grouped by user story so each story can be implemented and verified independently. Foundational tasks (Phase 2) gate every user story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story (US1 / US2 / US3); Setup / Foundational / Polish phases have no story label
- **[gpu]**: Test requires the `gpu` pytest marker (skipped on CI defaults per FR-019)
- File paths are absolute relative to the repo root: `/workspace/projects/ledgerlinc/ledgerlinc-model-ocr-pipeline-worktrees/014-paddle-gpu-preprocessing/`

## Path Conventions

Single-project layout (matches features 010 and 011): `src/ledgerlinc_ocr/`, `tests/`, `docs/stage1-vendor-identity/`. No new top-level package needed.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Cross-cutting touch-ups that are not blocking but are cheap to land first.

- [ ] T001 Add a one-paragraph cross-reference in `docs/stage1-vendor-identity/ollama-runtime.md` pointing to the new `paddle-gpu-preflight.md` (created in T015) so the existing runtime doc surfaces the Paddle GPU diagnostic alongside the Ollama lanes. File: `docs/stage1-vendor-identity/ollama-runtime.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared classifier module, version-string extension, engine factory device parameter, and pytest gpu marker. Every user story depends on at least one of these.

**⚠️ CRITICAL**: No US1 / US2 / US3 work begins until Phase 2 completes.

- [ ] T002 [P] Create `src/ledgerlinc_ocr/preprocessing/preflight.py` and define `PreflightState(str, Enum)` with the six FR-001 states (`PADDLE_NOT_INSTALLED`, `PADDLE_CPU_ONLY`, `GPU_NOT_EXPOSED`, `GPU_EXPOSED_PADDLE_CANT_BIND`, `PPSTRUCTUREV3_INIT_FAILED`, `PPSTRUCTUREV3_INIT_SUCCEEDED`) per Research R-014.3 and Spec FR-001. File: `src/ledgerlinc_ocr/preprocessing/preflight.py`

- [ ] T003 Add the frozen `PreflightEvidence` dataclass with the 13 fields specified in Data-model §PreflightEvidence (interpreter_path, interpreter_version, venv_path, paddle_version, paddleocr_version, paddle_compiled_with_cuda, paddle_compiled_with_rocm, visible_device_count, selected_device, runtime_device_exposure, ppstructurev3_init_seconds, ppstructurev3_init_error, ppstructurev3_init_skipped_reason). File: `src/ledgerlinc_ocr/preprocessing/preflight.py`

- [ ] T004 Add the frozen `PreflightReadout` dataclass plus `to_text()` and `to_json_dict()` serializers per Research R-014.5 and Data-model §PreflightReadout. The `to_json_dict()` payload must shape `{kind:"preflight_readout", schema_version:"0.1.0", state, evidence, recommendation}` (compact JSON, separators `(",", ":")`, `ensure_ascii=False`). File: `src/ledgerlinc_ocr/preprocessing/preflight.py`

- [ ] T005 Implement the `classify(*, attempt_ppstructurev3_init=True) -> PreflightReadout` function applying the Research R-014.7 step ordering: (1) install probe via `importlib.metadata.version`, (2) `import paddle`, (3) `is_compiled_with_cuda/rocm`, (4) `device.cuda.device_count`, (5) tensor-bind probe, (6) `PPStructureV3(device="gpu:0", ...)` construction. Capture `runtime_device_exposure` per Research R-014.10 (`/dev/dri`, `/dev/kfd`, `HIP_VISIBLE_DEVICES`, `CUDA_VISIBLE_DEVICES`, `ROCM_PATH`, `running_in_container`). Implement the edge-case behavior block from R-014.7 (introspection raise → `PADDLE_CPU_ONLY`; bind-probe synchronous, no timeout; device-index trust; version-mismatch surfaces as init failure; no exception-class taxonomy). File: `src/ledgerlinc_ocr/preprocessing/preflight.py`

- [ ] T006 [P] Extend `build_pipeline_version(...)` in `src/ledgerlinc_ocr/preprocessing/version.py` to accept a `lane_segment: str` parameter and append it as the trailing dot-segment per Research R-014.2 grammar (`.cpu` | `.gpu<N>`). The CPU default (called from existing CPU code path) MUST pass `lane_segment="cpu"` so post-feature CPU runs emit `.cpu` consistently. File: `src/ledgerlinc_ocr/preprocessing/version.py`

- [ ] T007 Add the pure helper `parse_lane_segment(pipeline_version: str) -> tuple[str, Optional[int]]` to the same `version.py` per Data-model §LaneSegment normative behavior: `("cpu", None)` for `.cpu` strings, `("gpu", N)` for `.gpu<N>`, `("cpu", None)` for pre-feature strings (no trailing lane segment), `("unknown", None)` for unrecognized segments without raising, `ValueError` for malformed strings. File: `src/ledgerlinc_ocr/preprocessing/version.py`

- [ ] T008 [P] Extend `_get_engine()` in `src/ledgerlinc_ocr/preprocessing/ocr.py` to accept a `device: str` parameter (default `"cpu"`) and forward it to `PPStructureV3(device=device, ...)`. Preserve the existing `cpu_threads=1, enable_mkldnn=False` settings on the CPU path (FR-017). The `EngineInitError` mapping in `_classify_engine_init_exception` is unchanged. File: `src/ledgerlinc_ocr/preprocessing/ocr.py`

- [ ] T009 Register the `gpu` pytest marker and the session-scoped preflight classifier fixture in `tests/conftest.py` per Research R-014.9. Add `pytest_configure(config)` to call `config.addinivalue_line("markers", "gpu: requires Paddle GPU readiness per FR-001 (state ppstructurev3_init_succeeded)")`. Add a session-scoped fixture that calls `classify(attempt_ppstructurev3_init=True)` once and caches the result. Add `pytest_collection_modifyitems(items)` that walks collected items and skips `gpu`-marked items with a reason of the form `f"skipped: state={state.value}; {recommendation}"` when state ≠ `PPSTRUCTUREV3_INIT_SUCCEEDED`. File: `tests/conftest.py`

**Checkpoint**: Foundation ready — US1 / US2 / US3 implementation can now begin.

---

## Phase 3: User Story 1 — GPU readiness preflight (Priority: P1) 🎯 MVP

**Goal**: Deliver a single discoverable preflight command that classifies the bench environment into one of the six FR-001 states with an actionable recommendation, even when the answer is "Paddle is CPU-only on this machine".

**Independent Test**: Run `python -m ledgerlinc_ocr.preprocessing.preflight` in the bench environment. The dual readout (human text + trailing JSON line) names the FR-001 state, exposes every FR-002 evidence field, and the exit code matches the Contracts §1 table for that state. Verifiable end-to-end against US1 acceptance scenarios 1–6 in `spec.md`.

### Tests for User Story 1

> Write these tests alongside the implementation tasks (TDD-style); every test must fail before its sibling implementation lands and pass once it does.

- [ ] T010 [P] [US1] Implement `tests/unit/test_preflight_classifier.py` as a table-driven classification test: for each of the six FR-001 states, mock `paddle` and the runtime-device-exposure helpers to produce the entry conditions, then assert `classify(...).state` equals the expected enum member and that the evidence-validation rules from Data-model §PreflightEvidence hold. Verifies FR-001, R-014.7, R-014.10. File: `tests/unit/test_preflight_classifier.py`

- [ ] T011 [P] [US1] Implement `tests/unit/test_preflight_cli_dual_format.py` to assert: (a) stdout text section matches the ordered template in Contracts §1.Stdout shape, (b) exactly one trailing JSON line parses as `{"kind":"preflight_readout","schema_version":"0.1.0", ...}`, (c) `--quiet` suppresses the text section but keeps the JSON line, (d) `--no-init` sets `ppstructurev3_init_skipped_reason="caller_disabled_init_attempt"` and skips the construction, (e) exit codes match the Contracts §1 table (0/10/11/12/13/14 for the six states; 1 for argparse error; 2 for classifier internal). File: `tests/unit/test_preflight_cli_dual_format.py`

- [ ] T012 [P] [US1] Implement `tests/unit/test_pipeline_version_lane_segment.py` covering: (a) round-trip for CPU lane (`build_pipeline_version(lane_segment="cpu")` → `parse_lane_segment(...)` returns `("cpu", None)`), (b) round-trip for GPU lane(s) `gpu0`, `gpu1`, `gpu7`, (c) backward-compatible default — pre-feature strings (no trailing lane segment) parse as `("cpu", None)`, (d) forward-compatible tolerance — unrecognized segments (e.g. `.npu0`, `.jetson1`) parse as `("unknown", None)` without raising, (e) malformed strings raise `ValueError`. Also assert the regex from Research R-014.2 matches every post-feature output of `build_pipeline_version`. Verifies SC-005, R-014.2. File: `tests/unit/test_pipeline_version_lane_segment.py`

- [ ] T013 [P] [US1] Implement `tests/unit/test_preflight_edge_cases.py` covering Spec §Edge Cases bullets and Research R-014.7 edge-case behavior: network-restricted shell (`--no-init`), `paddle.is_compiled_with_*` raising → conservative `PADDLE_CPU_ONLY`, missing paddle/paddleocr packages, `paddlepaddle`/`paddleocr` version mismatch surfacing as `PPSTRUCTUREV3_INIT_FAILED`, venv vs system interpreter divergence reported via `interpreter_path` and `venv_path`. Verifies FR-005, FR-006, R-014.7. File: `tests/unit/test_preflight_edge_cases.py`

### Implementation for User Story 1

- [ ] T014 [P] [US1] Create `src/ledgerlinc_ocr/preprocessing/preflight_cli.py` with an `argparse.ArgumentParser` exposing `--no-init` and `--quiet` flags per Contracts §1. The `main(argv: list[str] | None = None) -> int` entry point calls `classify(attempt_ppstructurev3_init=not args.no_init)`, formats the readout per Contracts §1.Stdout shape, prints text section (unless `--quiet`) followed by exactly one trailing JSON line via `json.dumps(readout.to_json_dict(), separators=(",", ":"), ensure_ascii=False)`, and returns the exit-code mapping from Contracts §1.Exit codes (0/10/11/12/13/14; 2 for an unhandled internal error). File: `src/ledgerlinc_ocr/preprocessing/preflight_cli.py`

- [ ] T015 [US1] Add `src/ledgerlinc_ocr/preprocessing/__main__.py` that imports `preflight_cli.main` and dispatches when the module is run as `python -m ledgerlinc_ocr.preprocessing.preflight`. Confirm the existing `preprocessing/cli.py` console-script entry (`ledgerlinc-preprocess`) is untouched. File: `src/ledgerlinc_ocr/preprocessing/__main__.py`

- [ ] T016 [P] [US1] Author `docs/stage1-vendor-identity/paddle-gpu-preflight.md` per Research R-014.11: per-state remediation, supported native-Linux ROCm install path with the pinned `paddlepaddle-gpu` install command, unsupported paths (WSL Docker, raw Conda) and the readout shape to expect there, CI default behavior (gpu-marked tests skipped, traceable to FR-001 state), and how to opt in locally. Cross-references Spec §FR-005 (Ollama state distinction), FR-024 (additive install path), and `quickstart.md`. File: `docs/stage1-vendor-identity/paddle-gpu-preflight.md`

**Checkpoint**: Preflight CLI works end-to-end. US1 acceptance scenarios 1–6 are testable. M1 milestone gate complete.

---

## Phase 4: User Story 2 — Opt-in `ppstructurev3@gpu` preprocessing profile (Priority: P2)

**Goal**: Once preflight passes, a developer (or the harness) can select `--preprocess-profile ppstructurev3@gpu`. The pipeline runs PPStructureV3 on `gpu:0`, fails fast with a named missing prerequisite when preflight cannot pass, fails per-document on inference errors with a multi-doc abort, and identifies the GPU run via the `pipeline_version` lane segment.

**Independent Test**: With preflight passing, `ledgerlinc-preprocess --input tests/stage1_vendor_identity/inv_001_easy/source.pdf --document-id inv_001_easy --preprocess-profile ppstructurev3@gpu --start-at preprocess --stop-after preprocess` produces a schema-valid `preprocess_output.json` whose `pipeline_version` ends with `.gpu0` and whose `document_text` is non-empty with ≥3 layout blocks. With prerequisites absent, the same command fails before any artifact write with an error naming both the profile and the FR-001 state. The CPU profile (no flag) behaves byte-identically to before this feature except for the added `.cpu` lane segment in `pipeline_version`.

### Tests for User Story 2

- [ ] T017 [P] [US2] Extend the existing `tests/pipeline_tests/test_profiles_vocabulary.py` with assertions that (a) `parse_profile("preprocess", "ppstructurev3@gpu")` returns a valid `StageProfile` with `lane="gpu"`, (b) `parse_profile("preprocess", "stub@gpu")` raises `ProfileValidationError`, (c) `parse_profile("preprocess", "ppstructurev3@cpu")` continues to behave as before. Verifies FR-007, FR-008, FR-011. File: `tests/pipeline_tests/test_profiles_vocabulary.py`

- [ ] T018 [P] [US2] Implement `tests/integration/test_pipeline_gpu_gate_failfast.py` as a parameterized test that, for each of the five FR-001 fail states, monkeypatches `ledgerlinc_ocr.preprocessing.preflight.classify` to return that state and runs `ledgerlinc-preprocess` with `--preprocess-profile ppstructurev3@gpu`. Asserts: (a) no `preprocess_output.json` written for any document in the run, (b) stderr contains `error: --preprocess-profile=ppstructurev3@gpu: <state-value>; <recommendation>`, (c) exit code matches the Contracts §1 table (10/11/12/13/14). Verifies FR-009, SC-003, plan.md §Contract Test Coverage point 5. File: `tests/integration/test_pipeline_gpu_gate_failfast.py`

- [ ] T019 [P] [US2] [gpu] Implement `tests/integration/test_pipeline_gpu_e2e.py` as the gpu-marked end-to-end integration test on `tests/stage1_vendor_identity/inv_001_easy/source.pdf`: run preprocessing with `--preprocess-profile ppstructurev3@gpu`, assert (a) `preprocess_output.json` is written and validates against `contracts/stage1_vendor_identity/v1.2.0/preprocess_output.schema.json` via the existing validator, (b) `pipeline_version` ends with `.gpu0`, (c) `document_text` is non-empty, (d) at least 3 layout blocks across all pages. Skipped on default CI per FR-019; runs only when preflight passes. Verifies FR-020, SC-004. File: `tests/integration/test_pipeline_gpu_e2e.py`

### Implementation for User Story 2

- [ ] T020 [P] [US2] Add `("preprocess", "ppstructurev3", "gpu")` to `SUPPORTED_PROFILES` in `src/ledgerlinc_ocr/pipeline/profiles.py`. Confirm `PPSTRUCTUREV3_GPU = "ppstructurev3@gpu"` constant is defined alongside the existing `PPSTRUCTUREV3_CPU`. Do not change `DEFAULT_PROFILES` or any `STACK_PRESETS` (preserves FR-008). Verifies FR-007, FR-011. File: `src/ledgerlinc_ocr/pipeline/profiles.py`

- [ ] T021 [US2] Plumb the resolved preprocess lane through `src/ledgerlinc_ocr/preprocessing/pipeline.py`: when the resolved profile is `ppstructurev3@gpu`, (a) call `classify(attempt_ppstructurev3_init=True)` once per process before the first artifact write per Clarification Q2, (b) on `state ≠ PPSTRUCTUREV3_INIT_SUCCEEDED` raise a structured `GpuPrerequisiteError` carrying the state and recommendation, (c) when the gate passes, call `_get_engine(device="gpu:0")` (or the device the classifier reports), and (d) thread `lane_segment="gpu0"` into every `build_pipeline_version(...)` call. The CPU path continues to thread `lane_segment="cpu"` so post-feature CPU output uniformly carries `.cpu`. Verifies FR-009, FR-016. File: `src/ledgerlinc_ocr/preprocessing/pipeline.py`

- [ ] T022 [US2] Update `src/ledgerlinc_ocr/preprocessing/cli.py` to catch `GpuPrerequisiteError` and exit with the matching code from the Contracts §1 table after writing the FR-009 stderr message `error: --preprocess-profile=ppstructurev3@gpu: <state-value>; <recommendation>`. Confirm the existing single-doc command exposes `--preprocess-profile` (it should already from feature 011 plumbing); if not, route the flag through to the resolver. File: `src/ledgerlinc_ocr/preprocessing/cli.py`

- [ ] T023 [US2] Wire the GPU lane through the warm-corpus runner in `src/ledgerlinc_ocr/pipeline/runner.py`: when the resolved preprocess profile is `ppstructurev3@gpu`, the runner invokes the same shared classifier once before the first document and short-circuits on a non-success state with no artifact writes. The classifier result is cached in-process for the rest of the run (Q2: no cache across processes; one classify per process). Verifies FR-009. File: `src/ledgerlinc_ocr/pipeline/runner.py`

- [ ] T024 [US2] Implement the abort-on-first-GPU-failure override in `src/ledgerlinc_ocr/pipeline/corpus_run.py` per Research R-014.4: when a per-document GPU inference call raises after the gate has passed, (a) record a per-document failure record with `gpu_lane_forced_abort: true`, (b) abort the warm-corpus run regardless of the user's `--on-failure` value (preserving the user's requested mode in `run_summary.on_failure` for transparency), (c) still emit the partial `kind:"run_summary"` JSON line on stdout per existing feature-011 conventions, (d) exit with the existing feature-011 stage-failure exit code. No silent CPU fallback. Verifies FR-010, Clarification Q3. File: `src/ledgerlinc_ocr/pipeline/corpus_run.py`

**Checkpoint**: GPU profile works end-to-end on a passing preflight environment; fails fast otherwise; CPU profile remains the default and is byte-stable. US2 acceptance scenarios 1–6 testable. M2 milestone gate complete.

---

## Phase 5: User Story 3 — CPU-vs-GPU timing evidence (Priority: P3)

**Goal**: With both lanes working, the warm-corpus runner emits additive timing fields (`preprocess_lane`, `gpu_init_seconds`, `gpu_inference_seconds`) on the existing `kind:"run_summary"` stdout JSON so a developer can compare warm CPU vs. warm GPU on the same input without parsing committed baselines.

**Independent Test**: Run the warm corpus twice on the same documents file, once with the CPU profile and once with `--preprocess-profile ppstructurev3@gpu`, capture stdout. The CPU run's last line shows `preprocess_lane:"cpu"` and no `gpu_*_seconds` keys. The GPU run's last line shows `preprocess_lane:"gpu0"`, `gpu_init_seconds` on the first per-document entry only, and `gpu_inference_seconds` on every successful per-document entry. A 0.1.0-shape parser parses the 0.1.1 output without raising. Verifiable against US3 acceptance scenarios 1–4.

### Tests for User Story 3

- [ ] T025 [P] [US3] [gpu] Implement `tests/integration/test_runsummary_gpu_timing_fields.py` covering US3 acceptance scenarios 1, 2, 3: run warm-corpus preprocessing once with CPU lane and once with GPU lane on a small fixture set, capture stdout, parse the trailing `kind:"run_summary"` line, and assert the fields per the contract in `contracts/cli-contract.md` §3 (`preprocess_lane`, additive `gpu_init_seconds` on first doc only, `gpu_inference_seconds` on every successful GPU doc, `gpu_lane_forced_abort:true` flag absent on success). Verifies FR-022, R-014.6. File: `tests/integration/test_runsummary_gpu_timing_fields.py`

- [ ] T026 [P] [US3] Implement `tests/contract_tests/test_runsummary_additive_contract.py`: simulate a feature-011 0.1.0-shape parser (one that knows only the pre-feature key set) and run it against a sample 0.1.1 `RunSummary.to_json_dict()` output produced by this feature. Assert the parser does not raise, returns all pre-feature fields with their original types, and silently ignores the new keys (`preprocess_lane`, `gpu_init_seconds`, `gpu_inference_seconds`, `gpu_lane_forced_abort`). Verifies plan.md §Contract Test Coverage point 4 and Research R-014.6 consumer tolerance. File: `tests/contract_tests/test_runsummary_additive_contract.py`

### Implementation for User Story 3

- [ ] T027 [US3] Extend `RunSummary` in `src/ledgerlinc_ocr/pipeline/timing.py`: bump `SCHEMA_VERSION` from `"0.1.0"` to `"0.1.1"`; add `preprocess_lane: str` (always present after this feature); update `to_dict()` to emit the new key. Do NOT remove or rename any existing fields. Verifies R-014.6 additive definition. File: `src/ledgerlinc_ocr/pipeline/timing.py`

- [ ] T028 [US3] In the same `timing.py`, extend `StageTiming.to_seconds_map()` so it includes `gpu_init_seconds` and `gpu_inference_seconds` keys when the corresponding nanosecond entries are present in `phases_ns`. Phase keys absent when not measured (R-009 absence policy preserved). File: `src/ledgerlinc_ocr/pipeline/timing.py`

- [ ] T029 [US3] In `src/ledgerlinc_ocr/pipeline/corpus_run.py`, populate `RunSummary.preprocess_lane` from the resolved preprocess profile (`"cpu"` or `"gpu<N>"`) once the resolver runs. Capture `gpu_init_seconds` exactly once per process — record it on the first successful per-document `StageTiming` entry by adding a phase named `gpu_init` whose duration is the `ppstructurev3_init_seconds` reported by the cached `PreflightReadout`. Verifies FR-022, R-014.6. File: `src/ledgerlinc_ocr/pipeline/corpus_run.py`

- [ ] T030 [US3] In `src/ledgerlinc_ocr/preprocessing/pipeline.py`, instrument the per-document GPU predict call to capture `gpu_inference_seconds` via `time.monotonic_ns()` deltas around the `_get_engine().predict(...)` invocation when the lane is GPU. Pass the timing into the per-document `StageTiming` so the warm-corpus runner aggregates it into the run summary. Do not capture this phase on the CPU lane. File: `src/ledgerlinc_ocr/preprocessing/pipeline.py`

**Checkpoint**: Timing evidence visible on stdout, additive contract preserved, no new persisted artifact. US3 acceptance scenarios 1–4 testable. M3 milestone gate complete.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Regression guards and final docs hygiene. No new feature behavior here.

- [ ] T031 [P] Implement `tests/pipeline_tests/test_pipeline_version_cpu_byte_stable.py` per plan.md §Contract Test Coverage point 3: with CPU profile (default) and a fixed input (`tests/stage1_vendor_identity/inv_001_easy/source.pdf`), run preprocessing twice and assert `hashlib.sha256(open(preprocess_output.json,"rb").read()).hexdigest()` is identical between the two runs. The test runs only after T006/T021 land (post-feature CPU output, including the `.cpu` lane segment, is the byte-stability baseline per the SC-006 wording resolution). Verifies FR-017, SC-006. File: `tests/pipeline_tests/test_pipeline_version_cpu_byte_stable.py`

- [ ] T032 [P] Confirm the existing `tests/contract_tests/` infrastructure under feature 001 still validates all four stage-1 artifact schemas under `contract_set_version` 1.2.0 with no edits — this is plan.md §Contract Test Coverage point 1. If any existing contract test newly fails because of this feature, that is a regression and the offending production change must be rolled back. No new file expected; validation only. File: `tests/contract_tests/` (existing infrastructure)

- [ ] T033 [P] Manually verify the four-step quickstart walkthrough in `specs/014-paddle-gpu-preprocessing/quickstart.md` (§1 preflight states, §2 GPU run, §3 CPU-vs-GPU timing comparison, §4 CPU byte-stability sha256 check) on the bench workstation. This is a documented manual smoke test; capture the output as evidence in the PR description. File: `specs/014-paddle-gpu-preprocessing/quickstart.md` (no edit; verification step)

---

## Dependencies & Story Completion Order

```text
Setup (T001) ──────────────────────────────────┐
                                                ▼
Foundational (T002→T003→T004→T005, T006→T007, T008, T009 depends on T005)
                                                │
                                                ▼
                    ┌───────────────────────────┼───────────────────────────┐
                    ▼                           ▼                           ▼
        US1 — Preflight CLI         US2 — GPU Profile           US3 — Timing Evidence
        (T010..T016)                (T017..T024)                (T025..T030)
                    │                           │                           │
                    └───────────────────────────┴───────────────────────────┘
                                                ▼
                                  Polish (T031..T033)
```

- US2 can start as soon as Foundational completes; it does **not** require US1's CLI/docs to land first because the runtime gate (T021/T023) imports the classifier from T005 directly.
- US3 depends on US2's runner plumbing (T023/T024) because the GPU timing fields are only populated when the GPU lane is in use end-to-end. US3 implementation tasks (T027/T028/T029/T030) can be developed in parallel with US2 implementation tasks but must integrate after US2 lands.
- The polish regression test T031 must run after T006 (post-feature CPU baseline) and ideally after T021 (CPU lane segment plumbed through pipeline.py). T032 can run any time. T033 runs last as the manual smoke test.

## Parallel Execution Examples

Within each phase, `[P]`-marked tasks touch distinct files and have no dependency on incomplete sibling tasks. Suggested parallel batches:

- **Foundational batch 1** (truly independent files): T002, T006, T008 (different files, no shared symbols at this stage). Launch T009 after T005 completes (conftest hook needs `classify`).
- **US1 tests in parallel**: T010, T011, T012, T013 (four independent test files; only their implementations T002–T009 / T014 need to land first).
- **US1 implementation in parallel**: T014 and T016 (CLI module + docs are independent; T015 depends on T014).
- **US2 tests in parallel**: T017, T018, T019 (three independent test files).
- **US2 implementation chained**: T020 [P] runs alongside the others; T021 → T022 → T023 → T024 is sequential because each touches a downstream caller of the previous.
- **US3 tests in parallel**: T025 and T026 are independent.
- **US3 implementation**: T027 → T028 (same file, sequential); T029 and T030 can run in parallel after T028 lands (different files, both consume the new `RunSummary` shape).
- **Polish in parallel**: T031, T032, T033 are all independent.

## Implementation Strategy

- **MVP = US1 only** (Phases 1–3). Even if Paddle GPU never passes preflight on this workstation, shipping the diagnostic + docs is a successful delivery per Spec §Assumptions and unblocks the team's runtime decision.
- **Increment 1 = US1 + US2** adds the GPU profile once preflight proves a usable Paddle GPU runtime in the bench environment.
- **Increment 2 = US1 + US2 + US3** adds the timing surface that justifies any future "promote GPU to default" decision in a follow-up feature (out of scope here).
- **CPU profile remains the default** through every increment (FR-008). Default CI never requires a GPU (FR-018, FR-019).
- **No schema changes, no committed-baseline regeneration, no `edge-ocr@jetson`** in any increment (FR-025).

## Format Validation

Every task above:

- Begins with `- [ ]` (markdown checkbox).
- Has a sequential `T###` ID.
- Carries `[P]` only when truly parallelizable, `[gpu]` only on tests requiring the gpu marker, and a `[US1] / [US2] / [US3]` story label inside user-story phases (Setup / Foundational / Polish carry no story label per the format rules).
- Names an exact absolute file path (or marks as a documented verification step where no file is edited).
- Cites the spec FR / SC / clarification / research ID being satisfied.
