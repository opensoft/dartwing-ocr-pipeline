# Feature Specification: Stage Runtime Profiles / Root Master Controller

**Feature Branch**: `011-stage-runtime-profiles`
**Created**: 2026-04-22
**Updated**: 2026-05-04
**Status**: Draft
**Input**: User description: "Make feature 011 the root/master controller for the stage 1 pipeline. The controller's purpose is to enable faster harness testing - it is not the harness itself. It owns stage-profile resolution, execution slicing, prerequisite validation, overwrite scoping, stage lifecycle, warm profile reuse, and per-run timing metadata that the harness consumes. The harness still owns corpus selection, repeated benchmark runs, scoring, evaluation, and report generation. Preserve the top-level commands `python -m ledgerlinc_ocr.pipeline run` and `ledgerlinc-pipeline run`. Add per-stage profile flags `--preprocess-profile`, `--extract-profile`, `--routing-profile`, `--final-payload-profile`, and execution-slice flags `--start-at` and `--stop-after` over `preprocess`, `extract`, `routing`, `final_payload`. Profile grammar is `stub` or `<implementation>@<lane>`. Default full-run profiles are `ppstructurev3@cpu`, `ollama@gpu`, `rules@cpu`, `assembler@cpu`. Stage 1 supported profiles include preprocess `stub` / `ppstructurev3@cpu` / `edge-ocr@jetson`; extract `stub` / `ollama@gpu` / `ollama@cpu` / `ollama@jetson` / `ensemble@workstation`; routing `stub` / `rules@cpu`; final payload `stub` / `assembler@cpu`. `edge-ocr@jetson`, `ollama@jetson`, `ensemble@workstation`, `cloud-workstation`, and `edge-fast` are supported contract targets, but their implementation must be sequenced after the warm `ppstructurev3@cpu` slice. Implementation priority is: (1) thin controller foundation - profile parsing, profile validation, `--start-at`/`--stop-after`, overwrite scoping, prerequisite-artifact validation; (2) warm `ppstructurev3@cpu` preprocessing for corpus/harness use, initializing once per process and processing multiple document folders through the warmed instance, preserving standard per-folder artifacts and exposing timing metadata that separates one-time initialization from per-document rasterization, page inference, artifact writing, and total time; (3) keep explicit `stub` profiles and injected stage callables working for deterministic network-free contract tests; (4) only after that expand into full real defaults and secondary runtime lanes. No artifact schema changes. No new persisted benchmark artifact. No remote cloud-provider calls or credentials. No separate repository for edge OCR. A normal per-document folder still has exactly one canonical set of the four stage artifacts."

## Controller Scope And Boundary With The Harness

This feature is the **root/master controller** for stage 1 - the orchestration layer that the harness drives. The controller's value is making real and mixed stub/live runs reproducible and fast enough for harness-driven testing without changing artifact contracts.

The controller owns:

- stage-profile resolution (per-stage profile flags and the `--stack-preset` convenience expansion)
- execution slicing (`--start-at` / `--stop-after`) and prerequisite-artifact validation
- overwrite scoping limited to the selected execution slice
- stage lifecycle, including warm profile initialization and reuse across documents
- per-run timing metadata that separates one-time profile initialization from per-document rasterization, prediction/inference, artifact writing, and total time

The controller does **not** own:

- corpus selection or expected-truth labeling
- repeated benchmark loops, scoring, evaluation, or report generation
- new persisted benchmark artifacts
- remote cloud-provider integration or credentialed cloud fallback
- a second repository for the edge OCR scanner

The harness consumes the controller's run timing metadata and per-document failure context to produce its corpus reports.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run The Top-Level Pipeline Through Real Default Profiles (Priority: P2)

A harness or pipeline developer wants the existing top-level `python -m ledgerlinc_ocr.pipeline run` entrypoint to execute the real stage-1 pipeline by default, instead of the current all-stub runner. They should not have to change the command shape just to move from contract-only stub runs to real preprocessing, model extraction, routing, and final payload assembly.

**Why this priority**: This is the eventual goal of the controller, but it lands after the thin foundation, the warm `ppstructurev3@cpu` corpus path, and the preserved stub seams. Wiring real defaults too early would block the faster-testing slices that this feature exists to enable.

**Independent Test**: Invoke `python -m ledgerlinc_ocr.pipeline run --document-folder <folder>` with no stage-profile overrides on a valid per-document folder. Verify that all four stage artifacts are produced through non-stub implementations, with the same filenames and artifact schemas already defined for stage 1.

**Acceptance Scenarios**:

1. **Given** a valid per-document folder containing `source.pdf`, **When** the top-level pipeline CLI runs with no stage-profile overrides, **Then** it executes the full stage-1 slice from preprocessing through final payload using named non-stub default profiles rather than stub defaults.
2. **Given** a successful default run, **When** the four output artifacts are inspected, **Then** their filenames, on-disk locations, and schema contracts are unchanged from the documented stage-1 contract.
3. **Given** a successful default run, **When** the stdout summary and stderr failure formats are inspected, **Then** they preserve the existing `002-cli-contract` shapes; this feature changes stage-selection behavior, not the success/failure record formats.
4. **Given** a run where the caller does not specify any stage profile flags, **When** the effective execution profile is resolved, **Then** the default profiles are `ppstructurev3@cpu` for preprocessing, `ollama@gpu` for extraction, `rules@cpu` for routing, and `assembler@cpu` for final payload.

---

### User Story 2 - Run Any Contiguous Pipeline Slice With Explicit Stage Profiles (Priority: P1)

A developer needs to test one part of the pipeline in isolation, or run a mixed stub/live composition while developing downstream slices. They need to select the implementation profile for each of the four stages and also choose where the run should start and stop, so the runner can reuse already-written upstream artifacts instead of always recomputing the whole pipeline.

**Why this priority**: This is the thin controller foundation that every later slice depends on (profile parsing, profile validation, `--start-at`/`--stop-after`, overwrite scoping, and prerequisite-artifact validation). Without slice control, the only way to test one stage is to bypass the top-level runner entirely.

**Independent Test**: On a folder with a valid `preprocess_output.json`, run `python -m ledgerlinc_ocr.pipeline run --document-folder <folder> --start-at extract --stop-after extract --extract-profile ollama@gpu`. Verify that only `edge_extraction_output.json` is rewritten, that preprocessing is treated as a prerequisite rather than re-run, and that the selected extraction profile is honored.

**Acceptance Scenarios**:

1. **Given** a folder with a valid `preprocess_output.json` already present, **When** the caller runs `--start-at extract --stop-after extract`, **Then** the runner treats preprocessing as satisfied input and executes only the extraction stage.
2. **Given** a folder with valid upstream artifacts through `edge_extraction_output.json`, **When** the caller runs `--start-at routing --stop-after final_payload`, **Then** the runner executes only routing and final payload assembly and leaves `preprocess_output.json` and `edge_extraction_output.json` untouched.
3. **Given** a caller who wants a mixed run, **When** they specify `--preprocess-profile stub` together with a non-stub extraction profile and an execution slice that includes both stages, **Then** the runner uses the schema-valid stub preprocess artifact as the upstream input to the real extraction stage.
4. **Given** a caller selects a start stage whose prerequisite artifact is missing or schema-invalid, **When** the run begins, **Then** the CLI fails before writing any downstream artifact and names the unmet prerequisite.
5. **Given** a caller executes only a subset of stages, **When** overwrite guards are evaluated, **Then** only artifact files in the selected execution slice are considered outputs-in-use; untouched upstream prerequisites do not trigger overwrite errors.

---

### User Story 3 - Compare Workstation And Jetson Lanes For Supported Live Stages (Priority: P3)

A developer or harness operator wants to compare performance across live runtime lanes without changing the pipeline entrypoint. They need the same stage profile syntax to express workstation CPU/GPU lanes and the Jetson Nano Super edge GPU lane where the underlying implementation supports them, while unsupported combinations fail clearly before the run starts.

**Why this priority**: The contract surface for these lanes (`ollama@cpu`, `ollama@jetson`, `edge-ocr@jetson`, `ensemble@workstation`) is part of this feature so profile validation can reject unsupported combinations from day one, but their *implementation* is sequenced after the warm `ppstructurev3@cpu` slice. Lane comparisons are not part of the first faster-testing increment.

**Independent Test**: Run the same extraction-only slice against the same folder with `--extract-profile ollama@gpu`, `--extract-profile ollama@cpu`, and `--extract-profile ollama@jetson`. Verify that all runs preserve the same artifact contract while resolving different runtime lanes, and that invalid lane combinations such as `rules@gpu` are rejected before any artifact writes.

**Acceptance Scenarios**:

1. **Given** a caller specifies `--extract-profile ollama@gpu`, **When** the extraction stage runs, **Then** it resolves the configured GPU extraction lane rather than the CPU lane.
2. **Given** a caller specifies `--extract-profile ollama@cpu`, **When** the extraction stage runs, **Then** it resolves the configured CPU extraction lane rather than the GPU lane.
3. **Given** a caller specifies `--preprocess-profile edge-ocr@jetson`, **When** the preprocessing stage runs on the edge target, **Then** it uses the Jetson GPU lane for the lightweight Paddle OCR scanner and fails fast rather than silently falling back to CPU OCR.
4. **Given** a caller specifies `--extract-profile ollama@jetson`, **When** the extraction stage runs on the edge target, **Then** it resolves the Jetson-local Gemma 4 E2B lane and fails fast rather than silently falling back to CPU model inference.
5. **Given** a caller specifies an unsupported lane/profile combination such as `--routing-profile rules@gpu`, **When** arguments are validated, **Then** the CLI exits with a usage error before any artifact is written.
6. **Given** two runs differ only by lane selection for a supported stage, **When** the resulting artifacts are inspected, **Then** filenames, locations, and schema contracts are identical; only runtime path and performance characteristics are allowed to differ.

---

### User Story 4 - Preserve Contract-Test Seams While Expanding The CLI Surface (Priority: P1)

A pipeline developer still needs the same fast, deterministic stub seams that made `002-cli-contract` testable without network or model dependencies. This feature must preserve that ability even though the CLI surface grows and live profiles are added.

**Why this priority**: Stub profiles and injected stage callables are the only way to keep contract and unit tests fast and network-free while the controller foundation and warm preprocessing slice are landing. If expanding the runner makes contract tests depend on Ollama or Paddle, the repository loses a major quality gate before the real defaults are even wired up.

**Independent Test**: Run the existing CLI-contract test suite with explicit stub profile flags or injected stage callables. Verify that tests remain Ollama-free and deterministic while the top-level runner supports real profiles for normal runs.

**Acceptance Scenarios**:

1. **Given** a contract or unit test that injects stub stage callables directly into the runner, **When** it executes, **Then** the runner still accepts those callables and does not force the real implementations.
2. **Given** a CLI-driven test run that passes explicit stub stage profiles for all executed stages, **When** the pipeline runs, **Then** no external model or OCR runtime is required.
3. **Given** the CLI argument set expands to support stage profiles and slice selection, **When** contract docs are updated, **Then** the amended surface is documented as a successor to the frozen `002` interface rather than an undocumented behavior drift.

---

### User Story 5 - Test Cloud-Class Stack On Workstation GPUs (Priority: P3)

A developer wants to test the future cloud solution on local workstation GPU
cards before any provider-managed cloud deployment or fallback exists. They need
a named stack and profile value that run the larger voter set locally while
preserving the same stage artifacts, deterministic routing policy, and harness
comparison path.

**Why this priority**: `cloud-workstation` is part of the controller's supported contract surface so profile validation, stack-preset expansion, and metadata are correct from day one, but its implementation lands after the warm `ppstructurev3@cpu` slice. The project needs cloud-solution evidence before adding remote infrastructure, but not before the faster-testing slice is unblocked.

**Independent Test**: Run the same document once with `full-workstation` and
once with `cloud-workstation`. Verify both runs emit the same four canonical
artifact filenames under separate run namespaces, that `cloud-workstation`
records the selected voter set in metadata, and that no remote cloud-provider
credentials or APIs are required.

**Acceptance Scenarios**:

1. **Given** a caller selects the `cloud-workstation` stack, **When** the run is
   resolved, **Then** preprocessing uses full-structure evidence and extraction
   uses `ensemble@workstation` on local workstation model endpoints.
2. **Given** the `cloud-workstation` stack runs, **When** artifacts are written,
   **Then** filenames and schema contracts match the standard stage-1 artifacts,
   and runtime metadata distinguishes the result from `full-workstation` and
   `edge-fast`.
3. **Given** any required local workstation model endpoint is missing, **When**
   validation runs, **Then** the CLI fails before artifact writes and names the
   missing endpoint/profile.
4. **Given** remote cloud credentials are present in the environment, **When**
   `cloud-workstation` runs, **Then** this feature does not use them; remote
   provider integration remains a separate future change.

---

### User Story 6 - Run Corpus Live Stages Through Warm Profile Instances (Priority: P1)

A harness operator needs to run the 20-document corpus without paying the
Paddle/PaddleX import and PPStructureV3 model-construction cost once per
document. They need a corpus or worker execution shape that initializes the
selected live preprocessing profile once, processes many document folders
through that warmed profile, and still preserves per-document artifact
isolation and failure reporting.

**Why this priority**: This is the first concrete enabler the controller exists to deliver - a warm `ppstructurev3@cpu` corpus path that makes harness-driven testing tractable. Corpus tests currently take hours because the live preprocessing stack is rebuilt for each document. Runtime profiles are not useful for harness-driven validation unless the selected live profile can stay warm across many documents.

**Independent Test**: Stage at least three valid per-document folders and run
the warm corpus execution path with `ppstructurev3@cpu`. Verify that the selected
preprocessing profile is initialized once for the process, that all selected
folders receive their normal stage artifacts, that a run summary reports one
profile initialization plus per-document timings, and that the same command can
be invoked with stub profiles without loading live OCR/model dependencies.

**Acceptance Scenarios**:

1. **Given** a corpus run selects `ppstructurev3@cpu`, **When** the run starts,
   **Then** the runner initializes the PPStructureV3 preprocessing profile once
   for the process before processing the first document.
2. **Given** the warmed preprocessing profile is initialized, **When** multiple
   document folders are processed, **Then** each document uses that same warmed
   profile instance rather than launching a fresh preprocessing process.
3. **Given** one document fails during a warm corpus run, **When** failure policy
   is not fail-fast, **Then** the run records the document failure with
   stage/profile context and continues with remaining documents.
4. **Given** a warm corpus run completes, **When** the run summary is inspected,
   **Then** it separates one-time profile initialization time from per-document
   rasterization, prediction, artifact-write, and total times.
5. **Given** a developer needs cold single-document debugging, **When** they run
   the normal one-document command, **Then** that cold path remains available and
   is clearly distinct from production-style warm corpus timing.

### Edge Cases

- A caller specifies `--start-at routing` but `edge_extraction_output.json` is missing, malformed, or schema-invalid.
- A caller specifies `--stop-after preprocess` while downstream artifact files already exist in the folder; only the selected output slice should matter for overwrite checks.
- A caller specifies `stub@gpu` or `stub@cpu`; stub is lane-less and such combinations are invalid.
- A caller specifies an unknown implementation name for a stage, such as `--extract-profile gemma`.
- A caller specifies `ppstructurev3@gpu`; the full-structure PPStructureV3 profile is CPU-only in this feature.
- A caller specifies `edge-ocr@cpu`; the edge OCR profile is Jetson GPU-only and must not provide a heavy CPU fallback path.
- A caller selects `ollama@cpu` but no CPU lane endpoint is configured or reachable.
- A caller selects `ollama@jetson` but no Jetson-local extraction endpoint is configured or reachable.
- A caller selects `ensemble@workstation` but one or more required local
  workstation voter endpoints are missing or not GPU-capable.
- A caller expects `cloud-workstation` to call an external cloud provider; this
  stack is explicitly local workstation validation only.
- A warm corpus run selects only deterministic downstream stages such as
  routing and final payload; no live preprocessing profile should be
  initialized.
- A warm corpus run receives a mix of valid and invalid document folders; valid
  folders should proceed according to the selected failure policy, and invalid
  folders should be reported with their own stage/profile context.
- A caller explicitly requests cold-per-document benchmarking; that mode must be
  visibly marked as cold timing and must not be used as the default live corpus
  path.
- A caller mixes a stub upstream stage with a live downstream stage; downstream behavior must be defined in terms of schema-valid upstream artifacts rather than assumptions about artifact richness.
- A caller runs `--start-at final_payload --stop-after final_payload`; the runner must treat `routing_decision.json` as the required input artifact and avoid touching earlier stage outputs.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The top-level entrypoint remains `python -m ledgerlinc_ocr.pipeline run` (and the equivalent `ledgerlinc-pipeline run`). This feature does not replace the top-level command with stage-specific subcommands.
- **FR-002**: This feature amends the frozen `002-cli-contract` surface by adding stage-profile and execution-slice flags while preserving the existing top-level command name, four artifact filenames, artifact schemas, stdout success summary shape, and stderr failure-record shape.
- **FR-003**: The CLI MUST add one optional profile flag for each stage: `--preprocess-profile`, `--extract-profile`, `--routing-profile`, and `--final-payload-profile`.
- **FR-004**: The CLI MUST add two optional execution-slice flags: `--start-at` and `--stop-after`. Their allowed values are `preprocess`, `extract`, `routing`, and `final_payload`. Both bounds are inclusive. The default slice is `preprocess` through `final_payload`.
- **FR-004A**: The CLI SHOULD add an optional `--stack-preset` convenience flag. Allowed values are `full-workstation`, `cloud-workstation`, and `edge-fast`. A preset expands to concrete stage profiles, and the resolved stage-profile values remain the source of truth for execution and metadata.
- **FR-005**: Stage-profile values MUST use named implementation profiles, not a generic `real` keyword. The accepted value grammar is either `stub` or `<implementation>@<lane>`.
- **FR-006**: The stage-1 supported profile set is:
  - preprocess: `stub`, `ppstructurev3@cpu`, `edge-ocr@jetson`
  - extract: `stub`, `ollama@gpu`, `ollama@cpu`, `ollama@jetson`, `ensemble@workstation`
  - routing: `stub`, `rules@cpu`
  - final payload: `stub`, `assembler@cpu`
- **FR-007**: The default profile set, used when no stage-profile flags are supplied, MUST be:
  - `ppstructurev3@cpu` for preprocessing
  - `ollama@gpu` for extraction
  - `rules@cpu` for routing
  - `assembler@cpu` for final payload
- **FR-008**: Unsupported profile values and unsupported implementation/lane combinations MUST be rejected during argument validation, before any stage writes occur. Examples include `stub@cpu`, `ppstructurev3@gpu`, `edge-ocr@cpu`, `rules@gpu`, `ensemble@cloud`, and unknown implementation names.
- **FR-009**: The runner MUST execute only the contiguous stage slice defined by `--start-at` and `--stop-after`. Stages before `--start-at` are treated as prerequisites and are not re-run. Stages after `--stop-after` are not run.
- **FR-010**: For any run whose `--start-at` is later than `preprocess`, the runner MUST require the prerequisite upstream artifact(s) for the selected start stage to already exist in the destination folder and to validate against the current contract set before downstream execution begins.
- **FR-011**: The overwrite guard MUST scope only to artifacts that belong to the selected execution slice. Files that are purely prerequisites for the slice MUST NOT be treated as outputs-in-use.
- **FR-012**: The runner MUST continue to support injected stage callables for tests and programmatic callers. Real default profiles cannot remove the existing stub seam.
- **FR-013**: Full default runs through the top-level pipeline MUST use non-stub implementations for all four stage-1 artifacts. Stub execution becomes opt-in through explicit stage-profile flags or injected test callables.
- **FR-014**: Lane selection MUST change only runtime resolution, not output contract. Changing from `ollama@gpu` to `ollama@cpu` or `ollama@jetson` MUST NOT change artifact filenames, artifact schemas, or the required top-level success/failure record shapes. Changing from `ppstructurev3@cpu` to `edge-ocr@jetson` MAY change evidence richness, but MUST still preserve the `preprocess_output.json` schema and make the selected profile visible in metadata.
- **FR-015**: The extraction lane resolver MUST distinguish GPU and CPU Ollama lanes. The GPU lane continues to use the existing `--ollama-url` / `OLLAMA_BASE_URL` resolution path. The CPU lane MUST use a separate resolution path so the caller can benchmark CPU and GPU lanes without changing the command form.
- **FR-016**: The CLI MUST add `--ollama-cpu-url` as the explicit CPU extraction lane override. Its precedence MUST be `--ollama-cpu-url` flag > `OLLAMA_CPU_BASE_URL` environment variable > documented stage-1 CPU lane default.
- **FR-017**: The CLI MUST add `--ollama-jetson-url` as the explicit Jetson extraction lane override. Its precedence MUST be `--ollama-jetson-url` flag > `OLLAMA_JETSON_BASE_URL` environment variable > documented Jetson-local default.
- **FR-018**: Lane selectors are stage-specific. In stage 1, full-structure preprocessing exposes `ppstructurev3@cpu`, edge preprocessing exposes `edge-ocr@jetson`, extraction exposes `ollama@gpu`, `ollama@cpu`, `ollama@jetson`, and `ensemble@workstation`, and routing/final payload expose only deterministic `@cpu` code paths. Unsupported lane claims MUST fail fast rather than silently degrading to another lane.
- **FR-019**: The `edge-fast` stack target is Jetson Nano Super class hardware. Its OCR and model inference work MUST run on the Jetson GPU lane; CPU-only OCR or CPU-only model inference is not an acceptable fallback for that stack.
- **FR-020**: The `edge-ocr@jetson` profile MUST attempt the lightweight Paddle OCR scanner first. If profile-owned quality gates fail, it MAY fall back to a larger Paddle OCR/layout scanner only when that fallback also runs on the Jetson GPU lane and the fallback is recorded in profile metadata. If a Jetson GPU fallback is unavailable, the run MUST return a review/escalation signal rather than running the heavy OCR stack on CPU.
- **FR-021**: The `cloud-workstation` stack target is local workstation GPU hardware. It MUST run cloud-class voter behavior on local workstation model endpoints and MUST NOT call external cloud-provider APIs or require provider credentials.
- **FR-022**: The `cloud-workstation` stack MUST use full-structure evidence initially and `ensemble@workstation` for extraction. The selected voter set, model runtimes, and stack name MUST be visible in artifact metadata or run metadata so evaluator reports can separate it from `full-workstation` and `edge-fast`.
- **FR-023**: The runner MUST support a warm corpus or worker execution mode for live stage profiles. In that mode, the selected live preprocessing profile MUST be initialized once per process and reused across all selected document folders in the run.
- **FR-024**: Warm execution MUST apply at minimum to live preprocessing profiles, including `ppstructurev3@cpu` and future `edge-ocr@jetson`. The design MAY later reuse the same lifecycle for live extraction profiles, but this feature's hard performance requirement is to avoid rebuilding the preprocessing stack once per document.
- **FR-025**: The one-document command remains a supported cold debugging path. Corpus or harness-driven live preprocessing runs MUST use warm execution by default and MUST NOT shell out to a fresh live preprocessing process per document unless the caller explicitly requests cold-per-document benchmarking.
- **FR-026**: Warm corpus execution MUST preserve per-document artifact isolation. Each document folder still receives only the standard selected-run artifacts, and no stage artifact schema or filename changes are allowed.
- **FR-027**: Warm corpus execution MUST report a run summary that separates one-time live profile initialization timing from per-document timings for rasterization, prediction/inference, artifact writing, and total document processing. This timing summary is run metadata, not a new persisted stage artifact.
- **FR-028**: Warm corpus execution MUST support per-document failure reporting. A failure in one document MUST identify the failed stage/profile and MUST NOT corrupt artifacts for other documents. The runner MAY support a fail-fast option, but continue-through-failures MUST be available for corpus diagnostics.
- **FR-029**: This feature MUST NOT change the persisted artifact schemas. `preprocess_output.json`, `edge_extraction_output.json`, `routing_decision.json`, and `final_structured_payload.json` remain the same contract-defined files.
- **FR-030**: This feature MUST NOT add a new benchmark artifact or move benchmark ownership from the harness into the pipeline. The harness remains responsible for multi-run timing capture and reporting; the pipeline exposes enough per-run timing detail for the harness to consume.
- **FR-031**: The runner MUST surface enough stage/profile context in human-readable error messages that an operator can tell which stage failed and which profile had been selected, without requiring code inspection.
- **FR-032**: The contract amendment for this feature MUST update the documented CLI argument set, quickstart examples, and test expectations that currently enforce the `002` frozen argument list.
- **FR-033**: The controller's responsibilities are scoped to stage-profile resolution, execution slicing, prerequisite-artifact validation, overwrite scoping, stage lifecycle (including warm profile initialization and reuse), and per-run timing metadata that the harness consumes. The controller MUST NOT take ownership of corpus selection, repeated benchmark loops, scoring, evaluation, or report generation; those remain harness responsibilities.
- **FR-034**: Implementation sequencing MUST land the controller in this order, and slices later in the order MUST NOT block slices earlier in the order:
  1. Thin controller foundation: profile parsing, profile validation, `--start-at` / `--stop-after`, overwrite scoping, prerequisite-artifact validation, with explicit `stub` profiles and injected stage callables preserved.
  2. Warm `ppstructurev3@cpu` preprocessing for corpus and harness use, including warm initialization, multi-folder processing through the warmed instance, preserved per-folder artifacts, and per-run timing metadata that separates one-time initialization from per-document rasterization, page inference, artifact writing, and total time.
  3. Wiring of full default real runs to `ppstructurev3@cpu`, `ollama@gpu`, `rules@cpu`, and `assembler@cpu`.
  4. Secondary lanes and stacks: `ollama@cpu`, `ollama@jetson`, `edge-ocr@jetson`, `ensemble@workstation`, `cloud-workstation`, and `edge-fast`.
- **FR-035**: `edge-ocr@jetson`, `ollama@jetson`, `ensemble@workstation`, `cloud-workstation`, and `edge-fast` are supported contract targets in this feature - profile validation, stack-preset expansion, and metadata MUST recognize them - but their live implementation MUST be sequenced after the warm `ppstructurev3@cpu` slice in FR-034.
- **FR-036**: This feature MUST NOT introduce a new persisted benchmark artifact, MUST NOT add remote cloud-provider calls or credential handling, MUST NOT split the edge OCR scanner into a separate repository, and MUST NOT permit more than one canonical set of the four stage artifacts to coexist in a single per-document folder for one selected run.

### Key Entities *(include if feature involves data)*

- **Stage Profile**: The resolved execution mode for one stage, expressed as either `stub` or `<implementation>@<lane>`. Examples: `ppstructurev3@cpu`, `edge-ocr@jetson`, `ollama@gpu`, `rules@cpu`.
- **Stack Preset**: A named convenience bundle that expands to concrete stage
  profiles. Stage 1 presets are `full-workstation`, `cloud-workstation`, and
  `edge-fast`.
- **Execution Slice**: The contiguous subset of stages the runner executes for one invocation, bounded by inclusive `--start-at` and `--stop-after` stage names.
- **Prerequisite Artifact**: An already-written upstream stage artifact required to begin a later execution slice. Example: `preprocess_output.json` is the prerequisite artifact for an extract-only run.
- **Warm Profile Instance**: A live stage implementation object that is initialized once within a process and reused for multiple document folders in the same corpus or worker run.
- **Warm Corpus Run**: A multi-document execution shape that processes a set of per-document folders while reusing any selected warm live stage instances and preserving normal per-document artifacts.
- **Cold Single-Document Run**: The normal one-document debugging shape where live profile initialization may happen for that one document. Cold timing is useful for diagnostics but is not representative of corpus or production-style throughput.
- **Run Timing Summary**: Non-artifact run metadata that separates one-time profile initialization time from per-document rasterization, prediction/inference, artifact-write, and total timings.
- **Lane**: The runtime path for a live stage profile. In stage 1 this matters for extraction (`gpu`, `cpu`, `jetson`, `workstation`) and for edge preprocessing (`jetson`), and is fixed to `cpu` for the deterministic in-process stages.
- **CPU Ollama Lane**: The CPU-only extraction runtime path used for performance comparison. It is configured separately from the default/GPU extraction lane.
- **Jetson Edge Lane**: The Jetson Nano Super class edge runtime path used by `edge-ocr@jetson` and `ollama@jetson`. Heavy OCR and model inference on this lane must use the Jetson GPU and must not silently degrade to CPU.
- **Cloud-Workstation Stack**: A local workstation GPU validation stack for the future cloud solution. It uses cloud-class voter configs and local model endpoints, not remote cloud-provider APIs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A harness can replace the current split preprocessing-plus-extraction invocation pattern with the top-level `python -m ledgerlinc_ocr.pipeline run` entrypoint for both full real runs and extraction-only slice runs, with no change to artifact filenames or folder layout.
- **SC-002**: Running the top-level pipeline with no stage-profile overrides on a valid corpus folder produces all four stage-1 artifacts through non-stub implementations 100% of the time on the supported workstation path, subject only to the live runtime dependencies of those implementations.
- **SC-003**: Every valid stage slice (`preprocess` only, `extract` only, `routing` only, `final_payload` only, and every contiguous multi-stage combination) can be executed independently when its prerequisites are present, and fails before any writes when prerequisites are missing.
- **SC-004**: Switching extraction between `ollama@gpu` and `ollama@cpu` requires only a stage-profile change and optional lane-URL override; no artifact schema, path, or filename changes are needed.
- **SC-005**: Invalid stage-profile values and unsupported lane combinations are rejected before any writes in 100% of tested cases.
- **SC-006**: Existing contract and unit tests can continue to exercise the pipeline with all-stub execution and no network dependency, either through injected callables or explicit stub stage profiles.
- **SC-007**: A harness can run the `edge-fast` stack with `edge-ocr@jetson` and `ollama@jetson` on the Jetson Nano Super target without changing artifact filenames or schemas, and the run metadata distinguishes it from the `full-workstation` stack.
- **SC-008**: A harness can run the `cloud-workstation` stack with `ppstructurev3@cpu` and `ensemble@workstation` on local workstation GPU hardware without changing artifact filenames or schemas, without provider credentials, and with run metadata that distinguishes it from `full-workstation` and `edge-fast`.
- **SC-009**: A warm corpus run over N document folders with `ppstructurev3@cpu` initializes the PPStructureV3 preprocessing profile exactly once per process, not N times, while producing schema-valid artifacts for every successfully processed document.
- **SC-010**: The warm corpus run summary reports one-time profile initialization timing and per-document rasterization, prediction/inference, artifact-write, and total timings for 100% of attempted documents.
- **SC-011**: Existing cold single-document commands remain available for debugging, but harness/corpus live preprocessing runs can execute without launching one fresh live preprocessing process per document.

## Assumptions

- This feature is the **root/master controller** for stage 1. Its purpose is to enable faster harness-driven testing; it is not the harness itself.
- The harness remains the owner of corpus selection, repeated benchmark loops, scoring, evaluation, JSONL logs, and run-summary reporting. The controller exposes only the execution controls and per-run timing metadata that those harness workflows consume.
- This feature is intentionally a CLI contract amendment to `002-cli-contract`; updating the argument set and its tests is in scope.
- Implementation is sequenced per FR-034: thin controller foundation, then warm `ppstructurev3@cpu` preprocessing for corpus/harness use, then real default profiles, then secondary lanes and stacks (`ollama@cpu`, `ollama@jetson`, `edge-ocr@jetson`, `ensemble@workstation`, `cloud-workstation`, `edge-fast`). Earlier slices ship without waiting on later ones.
- Stub profiles and injected stage callables remain a first-class seam through every slice, including after real defaults are wired up, so that contract and unit tests remain deterministic and network-free.
- The current stage-1 live implementation inventory is limited to real preprocessing, real single-voter extraction, deterministic routing code, and deterministic final-payload assembly. Remote cloud execution remains out of scope, but local cloud-class workstation validation is part of the runtime-profile contract surface and lands in the secondary-lane slice.
- The full-structure PPStructureV3 preprocessing profile remains CPU-only in stage 1. The lightweight edge preprocessing profile is a separate Jetson GPU lane and is not a CPU fallback for PPStructureV3.
- Warm corpus execution is required because cold per-document live preprocessing
  is known to rebuild expensive model stacks and is not representative of the
  intended corpus or production-style execution path.
- The stage-1 workstation continues to treat host Ollama as the GPU lane and the optional CPU container path as the CPU lane.
- The `cloud-workstation` lane is separate from the default `ollama@gpu` lane:
  it may use multiple local workstation model endpoints, but it still remains
  local validation rather than remote cloud execution.
- The edge target is Jetson Nano Super class hardware; exact JetPack, Paddle, and model-serving packaging choices remain implementation details for the edge profile. The edge OCR scanner stays in this repository under the same profile grammar; it is not split into a separate repository.
- Routing and final-payload assembly remain deterministic in-process code paths and therefore expose only `@cpu` profiles in stage 1.
- A normal per-document folder still contains exactly one canonical set of the four stage artifacts (`preprocess_output.json`, `edge_extraction_output.json`, `routing_decision.json`, `final_structured_payload.json`) for one selected run. Side-by-side profile comparisons are a harness-level concern handled via run namespaces, not a controller feature.
