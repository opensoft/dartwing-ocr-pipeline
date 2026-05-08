# Feature Specification: GPU Engine Reuse And Phase Timing

**Feature Branch**: `015-gpu-engine-reuse-timing`
**Created**: 2026-05-07
**Status**: Draft
**Input**: User description: "Optimize the proven `ppstructurev3@gpu` preprocessing path by removing duplicated startup work and adding phase timing to explain remaining latency. The current GPU path performs heavy PPStructureV3 initialization during preflight and then again at runtime; one GPU process must construct PPStructureV3 no more than once while preserving fail-fast GPU prerequisite behavior, the single-device-per-process guard, and never silently falling back to CPU."

## Clarifications

### Session 2026-05-07

- Q: Where do phase timings surface in run output? → A: Emit additive phase timings only in the existing `kind: "run_summary"` stdout line, per document. Do not add timing fields to `preprocess_output.json` and do not introduce a new stdout `kind`.
- Q: Does this feature implement an explicit MIOpen/COMGR warmup pass? → A: No. Warmup remains a reserved timing phase only — feature 015 does not add a synthetic warmup pass; the warmup timing is omitted unless another code path actually performs warmup.
- Q: What is the JSON shape of phase timing entries? → A: A structured `phase_timings` object whose scalar phases are records of the form `{seconds: <float>}` keyed by phase name; per-page inference is a `per_page_inference` array of `{page: <int 1-based>, seconds: <float>}` records (page numbering matches `preprocess_output.json`). Durations are measured from a monotonic clock (`time.perf_counter()`) and reported as JSON-number seconds.
- Q: What is the fail-fast upper bound for GPU-prereq failure (SC-007)? → A: ≤ 10 seconds wall-clock from process start to the failure being reported.
- Q: How are phase timings emitted for documents that fail mid-processing? → A: A failed document still appears as an entry in the per-document `run_summary` array, carrying whatever `phase_timings` completed before the failure (e.g. `rasterization` set, `per_page_inference` partial up to the failed page) plus an explicit failure status field. Phases that did not run are omitted, not zeroed.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Single GPU run constructs PPStructureV3 once (Priority: P1)

A pipeline engineer runs preprocessing for one document on the workstation GPU profile. Today that run takes about 103 seconds for `inv_001_easy/source.pdf` because PPStructureV3 is built once during the GPU preflight and then a second time when the runtime engine is constructed. The engineer needs the GPU path to construct PPStructureV3 at most once per process so the obvious duplicated-startup cost is gone before any further latency work begins.

**Why this priority**: Removing the duplicated initialization is the single biggest win available without touching OCR model variants, DPI, or region strategy (all explicitly out of scope for this feature). It is also a prerequisite for trustworthy phase-timing measurements — measuring duplicated work produces misleading numbers.

**Independent Test**: A cold single-document GPU preprocess run is fully testable on its own: invoke the existing `ppstructurev3@gpu` profile against `inv_001_easy/source.pdf`, assert that PPStructureV3 was constructed exactly once during the process, and confirm the resulting `preprocess_output.json` is still schema-valid with `pipeline_version` ending in `.gpu0`.

**Acceptance Scenarios**:

1. **Given** a fresh process selecting `ppstructurev3@gpu` and `inv_001_easy/source.pdf`, **When** preprocessing completes successfully, **Then** PPStructureV3 has been constructed exactly once during that process.
2. **Given** the same single-document run, **When** preprocessing completes, **Then** `preprocess_output.json` validates against the active stage 1 contract set, `pipeline_version` ends in `.gpu0`, `document_text` is non-empty, and at least three layout blocks are present.
3. **Given** GPU prerequisites are not satisfied (no ROCm device visible, Paddle cannot bind to GPU, etc.), **When** the engineer selects `ppstructurev3@gpu`, **Then** the run fails fast with a clear reason and does not silently fall back to CPU.

---

### User Story 2 - Warm corpus run reuses one engine across documents (Priority: P1)

A harness operator runs `ppstructurev3@gpu` over a small corpus (at least two documents) in one process. They expect the warm path to mirror the warm CPU profile's intent: the GPU readiness checks and PPStructureV3 engine construction happen once, and every subsequent document only pays inference and artifact-write cost.

**Why this priority**: Engine reuse across the corpus is the warm-path equivalent of US1 and is the configuration the harness will actually use day-to-day. Without it, the per-document cost of a corpus sweep stays dominated by repeated initialization, defeating the point of a "fast harness workflow."

**Independent Test**: A corpus-mode GPU run can be tested independently of US1's single-document path by invoking the warm profile over at least two known-good documents and asserting that GPU init/warmup phases are reported only for the first document while inference and artifact-write phases are reported for each subsequent successful document.

**Acceptance Scenarios**:

1. **Given** at least two documents queued for `ppstructurev3@gpu` in one process, **When** the corpus run completes, **Then** PPStructureV3 has been constructed exactly once across the entire run.
2. **Given** the same corpus run, **When** examining the run output, **Then** GPU readiness, GPU bind probe, engine initialization, and any optional warmup phases are reported for the first document only, while per-page inference and artifact-write phases are reported for every successfully processed document.
3. **Given** a corpus run where one document fails inference mid-stream, **When** the run continues to the next document, **Then** the engine is not rebuilt and subsequent documents still skip init/warmup phases.

---

### User Story 3 - Phase timing explains remaining latency (Priority: P1)

A pipeline engineer needs to know which phase of the GPU path dominates the current ~2-minute single-document run so the team can target the next optimization. They look at the run output and expect to see distinct timings for each major phase, not a single opaque "preprocess took 103s" number.

**Why this priority**: Without observability, even after engine reuse lands, the remaining latency is a black box. The whole point of this feature is to make the next round of latency work data-driven. Phase timing therefore ships in the same feature as the deduplication, not later.

**Independent Test**: A single GPU run is sufficient to test phase-timing surfacing: run preprocessing once and confirm the output exposes a timing entry for each listed phase, and that the slowest phase can be identified from the output alone.

**Acceptance Scenarios**:

1. **Given** any successful `ppstructurev3@gpu` run, **When** the engineer inspects the run output, **Then** distinct timings are surfaced for: Paddle import / first availability check, GPU bind probe, PPStructureV3 engine initialization, optional MIOpen/COMGR warmup (only when performed), PDF rasterization, per-page PPStructureV3 inference (one timing per page), artifact construction/write, and total preprocess time.
2. **Given** a warm corpus run, **When** the engineer inspects per-document timing, **Then** the first document's output distinguishes one-time GPU init/warmup costs from steady-state inference, and subsequent documents report only steady-state phases.
3. **Given** any single GPU run's phase timing, **When** the engineer reads the output, **Then** they can identify the slowest phase without rerunning the pipeline.
4. **Given** any preprocessing run, **When** phase timing is emitted, **Then** it appears as additive fields inside the existing final `kind: "run_summary"` stdout line per FR-014 — no fields are added to `preprocess_output.json`, no new stdout `kind` is introduced, and no new persisted benchmark artifact is required.

---

### User Story 4 - CPU and stub paths pay no GPU cost (Priority: P2)

An engineer running the default `ppstructurev3@cpu` profile, or a stub adapter in CI, must not pay any GPU preflight, GPU bind probe, or GPU-specific timing overhead. This protects CI runs that have no GPU hardware and the default workstation experience.

**Why this priority**: Important but lower than the GPU stories because CPU/stub behavior already works today; the risk here is regression. P2 reflects "preserve, don't break."

**Independent Test**: Run the default CPU profile and the existing stub-adapter tests with no GPU available; the suite must pass and the run output must contain no GPU phase timings or GPU readiness probe results.

**Acceptance Scenarios**:

1. **Given** `ppstructurev3@cpu` (the default profile) selected on a host without GPU, **When** preprocessing runs, **Then** no GPU preflight, GPU bind probe, or GPU-specific phase timing is executed or reported.
2. **Given** the existing CPU profile and stub adapter test suites, **When** they run on a host without GPU, **Then** they pass without modification.
3. **Given** the test suite is run on a host without GPU, **When** GPU-dependent tests are encountered, **Then** they are marked or skipped rather than failing.

---

### Edge Cases

- **Second device requested after engine bound**: A request to bind PPStructureV3 to a different device after it is already bound in the same process MUST fail with a clear error rather than silently rebinding, replacing the engine, or falling back to CPU.
- **GPU prerequisites missing**: ROCm runtime, Paddle GPU wheel, or `gpu:0` not visible — must fail fast (within the SC-007 ≤ 10 s budget) with a reason; must not auto-downgrade to `ppstructurev3@cpu`.
- **Engine construction succeeds but rasterization or inference later fails**: existing failure handling stays intact; the failed document still appears as an entry in the per-document `run_summary` array, carrying whatever `phase_timings` completed before the failure (phases not performed are omitted, not zeroed) plus an explicit failure status field; no partial `preprocess_output.json` is written if the existing path does not write one today.
- **Corpus document fails mid-run**: subsequent documents continue using the already-built engine; init/warmup are still not re-reported for them.
- **Optional warmup not performed**: if no MIOpen/COMGR warmup is executed for a given run, the warmup timing is omitted rather than reported as zero.
- **Per-page timing on multi-page documents**: each page of PPStructureV3 inference is reported separately so per-page variance is visible, while one-time costs remain in their own dedicated phases.

## Requirements *(mandatory)*

### Functional Requirements

**Engine reuse (deduplication of startup work)**

- **FR-001**: One `ppstructurev3@gpu` preprocessing process MUST construct PPStructureV3 no more than once.
- **FR-002**: GPU preflight MUST NOT redundantly construct PPStructureV3 alongside the runtime engine. Either preflight stops short of heavy construction and the runtime engine construction itself proves PPStructureV3 initialization, or preflight and runtime share one process-scoped engine.
- **FR-003**: GPU readiness state (Paddle availability, GPU bind result) MUST be cached for the lifetime of the process so subsequent readiness checks do not repeat the heavy probes.
- **FR-004**: Cold single-document `ppstructurev3@gpu` runs MUST go through the same reusable-engine path as warm runs.
- **FR-005**: Warm corpus `ppstructurev3@gpu` runs MUST reuse one PPStructureV3 engine across all documents in the same process.

**Safety, fail-fast, and profile boundaries**

- **FR-006**: The single-device-per-process guard MUST be preserved. After PPStructureV3 is bound to one device in a process, a request to bind another device MUST fail with a clear error.
- **FR-007**: When GPU prerequisites are missing or Paddle cannot bind to the requested GPU device, the run MUST fail fast (within the SC-007 ≤ 10 s budget) with a reason that identifies the missing prerequisite or bind failure.
- **FR-008**: After `ppstructurev3@gpu` is selected, the system MUST NOT silently fall back to CPU under any failure mode.
- **FR-009**: `ppstructurev3@cpu` MUST remain the default preprocessing profile; selecting GPU MUST remain explicit opt-in.
- **FR-010**: Canonical preprocessing artifact filenames and stage 1 JSON schemas MUST remain unchanged. `preprocess_output.json` produced by the optimized path MUST validate against the currently active stage 1 contract set.
- **FR-011**: Committed corpus baselines MUST NOT be regenerated by this feature.
- **FR-012**: OCR model variants, DPI, region strategy, and any OCR-only lane MUST NOT change in this feature; those are reserved for later features (017–019). Adding a synthetic MIOpen/COMGR warmup pass (a latency optimization) is also out of scope for feature 015 and reserved for a later feature.

**Phase timing (observability)**

- **FR-013**: Each preprocessing run MUST surface distinct phase timings for, at minimum:
  - Paddle import or first Paddle availability check
  - Paddle GPU bind probe
  - PPStructureV3 engine initialization
  - Optional MIOpen/COMGR warmup (reserved phase only — feature 015 does not introduce a synthetic warmup pass; surfaced only if some other code path actually performs warmup, otherwise omitted per FR-016)
  - PDF rasterization
  - Per-page PPStructureV3 inference (one entry per page)
  - Artifact construction/write
  - Total preprocess time — wall-clock from start to end of the preprocess stage for that document. On the first successfully processed document, `total` includes the one-time GPU phases (`paddle_import` + `gpu_bind_probe` + `engine_init` + optional `warmup`) plus the per-document phases. On subsequent documents, `total` includes only the per-document phases. `total` is therefore NOT the sum of the named phases on doc 1 (because some phases are per-process, not per-document).
- **FR-014**: Phase timing MUST be surfaced as additive fields inside the existing final `kind: "run_summary"` stdout line, organized per document. The line is emitted by the documents-file driver in warm-corpus mode and by the single-document CLI in single-document mode (with `documents_total: 1`); both emission sites MUST use the identical shape. Phase timing MUST NOT be added to `preprocess_output.json` (preserving FR-010), MUST NOT introduce a new stdout `kind`, and MUST NOT introduce a new persisted benchmark artifact. The "additive only" rule is concrete: existing keys MUST NOT be renamed, removed, or have their type changed; new keys are added under additionalProperties; the `schema_version` MUST be bumped one patch level (X.Y.Z → X.Y.(Z+1)) for any release that adds keys. Existing legacy flat keys (`stages.preprocess.{total_seconds, gpu_init_seconds, gpu_inference_seconds}`) introduced by feature 014 MUST be preserved in 0.1.2 for one schema version. Each per-document entry MUST contain a `phase_timings` object whose scalar phases are records of the form `{seconds: <float>}` keyed by phase name (e.g. `paddle_import`, `gpu_bind_probe`, `engine_init`, optional `warmup`, `rasterization`, `artifact_write`, `total`). Per-page PPStructureV3 inference timings MUST be emitted as a `per_page_inference` array of `{page: <int>, seconds: <float>}` records, where `page` is 1-based and matches the page numbering used in `preprocess_output.json`. Durations MUST be measured from a monotonic clock (e.g. `time.perf_counter()`) and reported as JSON-number seconds.
- **FR-015**: In any run output covering multiple documents, the GPU one-time phases (`paddle_import`, `gpu_bind_probe`, `engine_init`, optional `warmup`) MUST appear on the **first successfully processed per-document entry only** — i.e., the first per_document entry whose `status == "success"`. Subsequent successfully processed documents MUST report only steady-state per-document phases (`rasterization`, `artifact_write`, `total`, `per_page_inference`). If the first document fails (status `"failure"`), the GPU one-time phases attach to the next document whose status is `"success"`; failed documents never carry GPU one-time phases.
- **FR-016**: Optional phases (e.g. MIOpen/COMGR warmup) MUST be reported only when actually performed; absent phases MUST be omitted rather than reported as zero. For a document that fails mid-processing, its per-document `run_summary` entry MUST still be emitted, carrying whatever `phase_timings` completed before the failure plus an explicit failure status field; phases that did not run MUST be omitted, not zeroed.

**CPU/stub isolation and CI safety**

- **FR-017**: CPU and stub adapter paths MUST NOT execute GPU preflight, GPU bind probes, or GPU-specific timing instrumentation.
- **FR-018**: Existing CPU profile and stub adapter test suites MUST continue to pass without GPU hardware.
- **FR-019**: GPU-dependent tests MUST be marked or skipped so a default test run on a host without GPU does not produce false failures.

### Key Entities

- **GPU readiness result**: Process-scoped, cached outcome of "is Paddle GPU usable on this host for this profile" — produced once per process, consumed by both preflight and runtime engine construction. Holds enough detail to explain a fail-fast decision.
- **Reusable PPStructureV3 engine**: Process-scoped engine constructed at most once per process. Bound to a single device. Reused across all documents in the process. Subject to the single-device-per-process guard.
- **Phase timing record**: Set of named phase timings emitted per document. Includes one-time phases (Paddle import, GPU bind probe, engine init, optional warmup) reported on the first document only, and per-document phases (rasterization, per-page inference, artifact write, total) reported for every successfully processed document. Carried as additive fields inside the existing final `kind: "run_summary"` stdout line from the documents-file driver under a `phase_timings` object plus a `per_page_inference` array; scalar phases shaped as `{seconds: <float>}`, per-page entries as `{page: <int 1-based>, seconds: <float>}`, durations from a monotonic clock; never added to `preprocess_output.json`; no new stdout `kind`; not persisted as a new artifact.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a single `ppstructurev3@gpu` preprocessing process, the count of PPStructureV3 constructions equals exactly 1 (verifiable from instrumentation, log evidence, or a counter assertion in test).
- **SC-002**: A warm `ppstructurev3@gpu` run over at least two documents in one process reports GPU readiness, GPU bind probe, engine initialization, and optional warmup phases for the first document only; for every subsequent successfully processed document, only per-document phases (rasterization, per-page inference, artifact write, total) appear.
- **SC-003**: A `ppstructurev3@gpu` preprocess run on `inv_001_easy/source.pdf` produces a `preprocess_output.json` that (a) validates against the active stage 1 contract set, (b) has `pipeline_version` ending in `.gpu0`, (c) has non-empty `document_text`, and (d) contains at least three layout blocks.
- **SC-004**: Every successful preprocessing run output contains all required phase timings listed in FR-013 (with optional warmup omitted when not performed and per-page inference reporting one entry per processed page).
- **SC-005**: From a single GPU run's phase-timing output, the slowest phase among the listed phases can be identified without rerunning the pipeline.
- **SC-006**: A `ppstructurev3@cpu` preprocessing run on the same document produces no GPU-readiness, GPU-bind, or GPU-specific phase entries in its run output.
- **SC-007**: A `ppstructurev3@gpu` run on a host where GPU prerequisites are missing or Paddle cannot bind to the requested device fails within 10 seconds (wall-clock, measured from OS exec of the CLI subprocess to the subprocess's first non-zero exit) with a reason that identifies the missing prerequisite or bind failure, and never produces a `preprocess_output.json` whose `pipeline_version` ends in `.gpu0` and never silently produces one ending in `.cpu0` either (FR-008).
- **SC-008**: The full default test suite (CPU profile and stub adapter) passes on a host without GPU; GPU-dependent tests are skipped or marked, not failed.

## Assumptions

- The current ~103 s single-document GPU run on `inv_001_easy/source.pdf` is the latency reference for "explain the remaining latency"; this feature commits to making latency observable and removing duplicated init, not to a specific numeric latency target.
- Existing run metadata / run summary surfaces accept additive phase-timing fields without requiring schema or contract-set changes.
- The active stage 1 contract set is the one currently pinned in the project (`contract_set_version = "1.2.0"` at the time of writing); the optimized GPU path is expected to keep producing artifacts that validate against whatever contract set is active when the feature lands.
- The workstation ROCm Paddle path used for verification is the host WSL `.venv-paddle-rocm` environment with `paddlepaddle-dcu` bound to `gpu:0`, as already proven in feature 014.
- Production CI continues to exercise CPU and stub paths only; GPU-dependent tests run on developer or workstation hosts where GPU prerequisites are met.
- The warm CPU profile's intent (one engine across all documents in a process) is the model to mirror for the warm GPU profile.
- Failure handling outside the explicit scope above (e.g. how a per-document inference failure is reported, how partial outputs are or are not written) is unchanged from current behavior.

## Definitions

- **One process / same process**: one OS process / one Python interpreter session — NOT "one CLI invocation." Tests instantiate the pipeline in-process across multiple `run()` calls, and that still counts as one process for FR-001 / FR-005 / SC-001 / SC-002 / FR-003 cache scope.
- **Construct PPStructureV3**: an invocation of the `paddleocr.PPStructureV3(...)` constructor. Subsequent `predict(...)` calls and `del` operations do NOT count as constructions. SC-001 / FR-001 are verified by counter assertion against the constructor (mock or instrumentation).
- **Phase timing precision**: phase timing values are reported in seconds as JSON numbers, six-decimal-rounded — derived from `time.perf_counter_ns()` deltas via `round(delta_ns / 1e9, 6)`. This precision rule is non-normative wording for the spec but normative for the implementation (see `research.md §R-015.4`).
- **FR-013 phase vocabulary as single source of truth**: `data-model.md`, `contracts/run-summary-schema.md`, and `research.md` enumerate the same phase keys derived from `FR-013`. If they ever drift, `spec.md §FR-013` is authoritative.
- **Preprocess profile terminology mapping**: the same logical preprocess profile is named differently at three layers, and all three are normative for their respective surfaces:

  | Surface | GPU form | CPU form | Where it lives |
  |---|---|---|---|
  | CLI slug (user-facing) | `ppstructurev3@gpu` | `ppstructurev3@cpu` | `--preprocess-profile=…` argument; `pipeline_version` ends in `.gpu0` / `.cpu0` |
  | Run summary lane (machine-facing) | `gpu0` | `cpu` | `run_summary.preprocess_lane` |
  | Paddle device (internal) | `gpu:0` | `cpu` | `PPStructureV3(device=…)` |

  When a future feature adds multi-GPU support, the mapping extends to `gpu1` / `gpu:1` etc.; the CLI slug form stays `ppstructurev3@gpu` (the `@gpu` suffix means "any GPU lane," with the specific device chosen by configuration).
