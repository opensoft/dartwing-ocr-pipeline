# Feature Specification: Workstation Paddle GPU Preprocessing Validation

**Feature Branch**: `014-paddle-gpu-preprocessing`
**Created**: 2026-05-05
**Status**: Draft
**Input**: User description: "Workstation Paddle GPU preprocessing validation for stage 1. The feature must start with a GPU preflight that can clearly distinguish missing Paddle, CPU-only Paddle, missing GPU device exposure, GPU visible but unusable by Paddle, and PPStructureV3 GPU initialization failure/success. Only if preflight is meaningful should the spec allow adding an explicit opt-in `ppstructurev3@gpu` preprocessing profile. Preserve `ppstructurev3@cpu` as the default. No silent CPU fallback when GPU is selected. No schema changes. No committed baseline regeneration unless determinism is proven and explicitly accepted."

## Overview

Stage 1 preprocessing today runs PPStructureV3 (PaddleOCR 3.5) on CPU only. The
workstation has an AMD/ROCm GPU that is already used by host Ollama for
extraction, but it is unproven for Paddle. The harness loop is uncomfortably
slow because every preprocessing run is CPU-bound, and the team does not yet
know whether a usable Paddle GPU runtime exists in the bench/devcontainer
environment at all.

This feature delivers a disciplined GPU validation path. It begins with a
diagnostic preflight that produces a clear, actionable readout regardless of
outcome, and only adds an opt-in `ppstructurev3@gpu` preprocessing profile if
preflight proves Paddle GPU + PPStructureV3 GPU initialization actually work
in the intended environment. The CPU profile remains the default and unchanged.

## Clarifications

### Session 2026-05-06

- Q: Where is the GPU profile/device identity recorded so SC-005 can be verified from the artifact? → A: Encode profile + device only in `pipeline_version`; no other artifact change.
- Q: When the pipeline runs with `--preprocess-profile ppstructurev3@gpu`, how does it gate on GPU prerequisites before the first artifact write? → A: Pipeline calls the same checker module inline every GPU run; no cache; reuses FR-001 state vocabulary verbatim.
- Q: When the GPU profile is selected for a multi-document harness run and one document's GPU inference fails mid-run, what happens to the rest of the run? → A: Abort the whole harness run on the first per-document GPU failure; remaining documents not processed.
- Q: What format must the FR-001 preflight readout produce? → A: Human-readable text plus one trailing JSON line on stdout (mirrors feature 011 `run_summary` style).
- Q: How is warm CPU vs. warm GPU timing evidence (FR-022, US3) surfaced? → A: Add timing fields to the existing feature-011 `run_summary` stdout JSON; no persisted artifact.
- Wording resolution (post-checklist, no behavior change): "Ollama GPU state" in FR-005 is narrowed to *Ollama-process-specific* signals. Observing shared host indicators (`/dev/kfd`, `/dev/dri`, `HIP_VISIBLE_DEVICES`, `ROCM_PATH`, `CUDA_VISIBLE_DEVICES`) is GPU-runtime exposure evidence under FR-002, not Ollama state, and is permitted. Reason: resolves checklist conflicts CHK028 (failure-handling.md) / CHK029 (diagnostics.md).
- Wording resolution (post-checklist, no behavior change): "schema" / "schema field" in FR-015 and FR-025 means the JSON-Schema-validated field shape under `contracts/stage1_vendor_identity/v1.2.0/`, not the free-form string content of fields whose schema is `{"type":"string","minLength":1}`. Adding a parseable lane segment to `pipeline_version` is therefore a content addition, not a schema change. Reason: resolves checklist conflict CHK025 (contract.md).

## User Scenarios & Testing *(mandatory)*

### User Story 1 — GPU readiness preflight (Priority: P1)

A pipeline developer needs a single documented command they can run inside the
bench environment that tells them, in plain language, whether Paddle GPU is
usable for PPStructureV3 preprocessing on this workstation, and if not, what
specifically is missing. The readout must be useful even when the answer is
"no GPU available" — that is itself a first-class outcome the team will use to
decide whether to invest further.

**Why this priority**: Without trustworthy preflight, every later step is
guesswork. Paddle GPU on AMD/ROCm WSL is unproven; Ollama GPU success on the
same machine does not imply Paddle GPU success. Landing preflight as the
first slice protects later work from being built on a silent-CPU illusion and
gives the team a clean stopping point if the runtime is not viable.

**Independent Test**: Run the preflight command in the bench environment and
confirm it produces a structured readout that names the Python interpreter,
the Paddle/PaddleOCR versions, GPU build capability, visible device count,
selected device, container/runtime device exposure, and PPStructureV3 GPU
initialization result. The readout must distinguish each of the failure modes
listed in FR-001 from a successful PPStructureV3 GPU init. Delivers value
even if the final state is "Paddle is CPU-only on this machine" because the
team can act on that fact (install path, container exposure, hardware swap,
or pause).

**Acceptance Scenarios**:

1. **Given** a bench environment where Paddle is not installed, **When** a
   developer runs the preflight command, **Then** the readout reports
   "Paddle/PaddleOCR not installed" and recommends the next remediation step
   (install or enter the correct environment).
2. **Given** a bench environment where Paddle is installed but compiled
   CPU-only, **When** preflight runs, **Then** the readout reports
   "Paddle installed but CPU-only" with the Paddle version and a pointer to
   the documented supported install path.
3. **Given** a bench environment where Paddle has a GPU build but the
   container does not expose the workstation GPU device, **When** preflight
   runs, **Then** the readout reports "GPU device not exposed to runtime"
   and identifies the missing device file or environment variable rather
   than blaming Paddle.
4. **Given** the GPU device is exposed but Paddle cannot bind to it (ROCm
   mismatch, wrong wheel, missing library), **When** preflight runs,
   **Then** the readout reports "GPU device exposed but unusable by Paddle"
   and includes the Paddle-reported error so a developer can act on it.
5. **Given** Paddle reports GPU is usable but PPStructureV3 cannot
   initialize on the GPU device, **When** preflight runs, **Then** the
   readout reports "PPStructureV3 GPU initialization failed" with the
   captured error and does not pretend the GPU profile is ready.
6. **Given** Paddle GPU is usable and PPStructureV3 initializes on the GPU
   device, **When** preflight runs, **Then** the readout reports
   "PPStructureV3 GPU initialization succeeded" with the device string and
   the captured initialization time, and indicates that the opt-in GPU
   profile is safe to enable.

---

### User Story 2 — Opt-in `ppstructurev3@gpu` preprocessing profile (Priority: P2)

Once preflight passes for a developer's environment, that developer (and the
harness) can explicitly select `ppstructurev3@gpu` as the preprocessing
profile for a stage 1 run. Selecting the GPU profile must run the same
PPStructureV3 stack on the GPU device, must produce the canonical
`preprocess_output.json` artifact validated against the active schema, must
make the selected profile/device visible in run metadata, and must fail fast
with a named missing prerequisite if any GPU requirement is not satisfied.
Selecting the CPU profile (or omitting the flag) must continue to behave
exactly as today.

**Why this priority**: This is the user-facing capability that justifies the
feature. It is gated on P1 because a profile that cannot honor its name is
worse than no profile — it would either silently fall back to CPU or
intermittently fail in confusing ways. Once preflight is meaningful, this
slice gives the harness and developers a real GPU path.

**Independent Test**: With preflight passing, run the existing pipeline
command for a single document folder using `--preprocess-profile
ppstructurev3@gpu` (start-at and stop-after constrained to the preprocess
stage). Verify (a) the run produces `preprocess_output.json` that validates
against the active schema, (b) `pipeline_version` or run metadata identifies
the GPU profile and device, (c) `document_text` is non-empty for a known
text-bearing test invoice, (d) the same command with GPU prerequisites
intentionally absent fails fast and writes no artifact, (e) the existing
`ppstructurev3@cpu` behavior is unchanged when the new flag is not passed.

**Acceptance Scenarios**:

1. **Given** preflight has passed in the current environment, **When** a
   developer runs preprocessing on a known-good test invoice with
   `--preprocess-profile ppstructurev3@gpu`, **Then** the run produces a
   `preprocess_output.json` that validates against the active
   `preprocess_output.schema.json` and contains non-empty `document_text`
   and at least three layout blocks for `inv_001_easy`.
2. **Given** preflight has passed, **When** a developer runs the GPU
   profile, **Then** the selected profile and device are visible through
   `pipeline_version` and/or run metadata so a downstream consumer can tell
   the artifact came from the GPU profile rather than the CPU profile.
3. **Given** preflight cannot pass in the current environment (any FR-001
   failure mode), **When** a developer runs the pipeline with
   `--preprocess-profile ppstructurev3@gpu`, **Then** the run fails before
   any artifact is written and the error names the selected profile and
   the specific missing GPU prerequisite.
4. **Given** the GPU profile has been added, **When** a developer runs the
   pipeline without the new flag, **Then** preprocessing runs
   `ppstructurev3@cpu` exactly as it did before this feature, including the
   `enable_mkldnn=False`, `cpu_threads=1`, and determinism behavior.
5. **Given** the GPU profile is selected, **When** GPU initialization
   succeeds but a per-document inference call fails on the GPU, **Then**
   the run fails for that document instead of silently falling back to
   CPU, and the failure is attributable to the GPU profile in the run
   output.
6. **Given** the GPU profile is selected, **When** the developer combines
   it with `--start-at preprocess --stop-after preprocess`, **Then** the
   slice runs end-to-end the same way the CPU profile does for the same
   slice flags, with no new artifact files outside the canonical layout.

---

### User Story 3 — CPU-vs-GPU timing evidence and harness readiness (Priority: P3)

Once the GPU profile works, a developer can compare warm CPU and GPU
preprocessing on the same document or small corpus sample, see the timing
difference, and know whether the GPU profile is materially faster than the
warm CPU profile. The harness must be able to request the GPU profile through
the existing pipeline-profile interface, and the timing evidence must be
captured without introducing a new mandatory persisted benchmark artifact.
This evidence is the input for a later, separate decision about whether the
GPU profile should ever become the default, and whether GPU output is
deterministic enough to regenerate committed baselines.

**Why this priority**: Speed and repeatability are the reasons the feature
exists at all, but they only become measurable after the diagnostic and the
profile are in place. Promotion decisions belong to a future feature; this
slice's job is to make those decisions defensible, not to make them.

**Independent Test**: With the GPU profile working on at least one document,
run warm CPU and warm GPU preprocessing on the same document and capture (a)
one-time profile initialization time, (b) per-document preprocessing time,
(c) schema validity for both outputs, (d) basic quality signals (block count
range, non-empty `document_text`). Verify the harness can request the GPU
profile through the existing pipeline-profile mechanism. Verify no new
required, committed benchmark artifact has been introduced.

**Acceptance Scenarios**:

1. **Given** the GPU profile works on at least one stage 1 invoice, **When**
   a developer runs warm CPU and warm GPU preprocessing on the same
   document, **Then** the run records initialization time and per-document
   preprocessing time for both profiles in a way the developer can read
   without parsing committed baselines.
2. **Given** the harness already supports stage profile selection, **When**
   the GPU profile is enabled, **Then** the harness can request it through
   the existing pipeline-profile interface without changes to corpus
   layout, artifact filenames, or harness output schemas.
3. **Given** GPU and CPU outputs differ on the same input, **When** the
   developer compares them, **Then** the difference is recorded and the
   feature does not regenerate committed `preprocess_output.json`
   baselines from GPU output unless byte-level determinism has been
   demonstrated and explicitly accepted in a follow-up decision.
4. **Given** the timing evidence has been captured, **When** the team
   decides whether to make the GPU profile a default, **Then** the
   evidence is sufficient to answer that question (warm-vs-warm timing,
   schema validity, basic quality, repeatability observation) without
   needing to re-run preflight.

---

### Edge Cases

- A developer runs the preflight command in an environment where the
  `py-bench` venv's interpreter differs from the system Python. The readout
  must report the exact interpreter actually executing the preflight, not a
  guess.
- A developer runs the preflight command from inside a container that has
  Paddle but does not have the workstation GPU device file mapped. The
  readout must distinguish "Paddle CPU-only build" from "GPU build, device
  not exposed" so the developer fixes container configuration rather than
  reinstalling Paddle.
- Paddle reports a GPU build, device count > 0, and `gpu_available()` true,
  but PPStructureV3 throws on construction because of a runtime library
  mismatch. The readout must surface that as PPStructureV3 init failure, not
  as a Paddle GPU success.
- A developer accidentally requests `--preprocess-profile ppstructurev3@gpu`
  on a pure CPU machine that has never had GPU support. The pipeline must
  fail before writing any artifact and must name `ppstructurev3@gpu` as the
  selected profile in the failure message.
- A second developer tries to use `stub@gpu`. The profile vocabulary must
  reject this exactly as it does today; stubs remain lane-less.
- The CPU profile run produces byte-identical output before and after this
  feature lands. Any change to CPU determinism is a regression, not an
  acceptable side effect.
- A developer runs preflight in a network-restricted shell where Paddle
  cannot download model weights. Preflight must still report Paddle install
  state, build capability, and GPU device exposure even if it cannot
  exercise PPStructureV3 GPU initialization, and must clearly label the
  PPStructureV3 step as "not exercised" rather than "failed".
- The GPU profile is selected and PPStructureV3 initializes on the GPU but
  ROCm runs out of memory mid-document. The failure must be reported as a
  per-document GPU failure rather than a hidden CPU re-run, and in a
  multi-document harness run that failure must abort the rest of the run
  rather than continuing with subsequent documents.
- A developer runs the GPU profile and then the CPU profile in the same
  per-document folder. The canonical `preprocess_output.json` must reflect
  whichever profile ran last; there must not be two canonical preprocessing
  artifacts in the same folder at the same time.
- The opt-in GPU profile is added, but a future patch upgrades Paddle and
  changes its device-binding behavior. The preflight readout and the
  fail-fast error path must still produce actionable diagnostics under the
  new Paddle behavior, not silently degrade.

## Requirements *(mandatory)*

### Functional Requirements

#### Preflight Diagnostic

- **FR-001**: The system MUST provide a single documented preflight command
  whose output distinguishes, at minimum, all of the following states:
  (a) Paddle/PaddleOCR not installed; (b) Paddle installed but CPU-only;
  (c) GPU device not exposed to the runtime; (d) GPU device exposed but
  unusable by Paddle; (e) Paddle GPU usable but PPStructureV3 GPU
  initialization fails; (f) PPStructureV3 GPU initialization succeeds.
- **FR-002**: The preflight readout MUST identify the exact Python
  interpreter and environment path executing the preflight (interpreter
  path, interpreter version, and venv path when distinct from the system
  interpreter), the installed Paddle and PaddleOCR versions, the Paddle
  GPU build flags (both `is_compiled_with_cuda` and
  `is_compiled_with_rocm`), the visible device count, the selected
  device, and whether the runtime exposes the required GPU device files
  or environment variables (`/dev/kfd`, `/dev/dri`,
  `HIP_VISIBLE_DEVICES`, `ROCM_PATH`, `CUDA_VISIBLE_DEVICES`,
  containerization indicators). The operational expansion of this list
  is documented in `specs/014-paddle-gpu-preprocessing/data-model.md`
  (`PreflightEvidence`); FR-002 is satisfied as long as the readout
  surfaces every field defined there.
- **FR-003**: The preflight readout MUST be self-contained enough that a
  developer can decide the next action (install dependencies, change
  container device exposure, change runtime, or stop) without reading
  source code. Each FR-001 fail-state recommendation MUST (a) name a
  specific remediation action (e.g. an install command, a container
  configuration change, or a runtime switch), (b) reference
  `docs/stage1-vendor-identity/paddle-gpu-preflight.md` (or its
  successor) so a developer can navigate to the canonical guide
  without prior knowledge of the docs tree, and (c) fit on one line
  ("plain language" per US1: avoid jargon, name the issue once, state
  the next user action). The success-state recommendation MUST confirm
  that the GPU profile is safe to enable and name the device string.
  The readout MUST be emitted in a dual form on stdout:
  (a) a human-readable text section that names the FR-001 state, the
  evidence captured under FR-002, and the recommended next remediation
  step, followed by (b) exactly one trailing JSON object on its own line
  that exposes the same FR-001 state and the FR-002 evidence fields in a
  machine-parseable shape. This mirrors the `kind: "run_summary"` stdout
  convention from feature 011 so tests, CI, and the FR-019 skip-gate can
  parse the JSON line without scraping the human text. The exact JSON
  shape is not a frozen contract artifact (per the "Preflight readout"
  Key Entity) and may evolve without an amendment.
- **FR-004**: The preflight command MUST NOT modify the pipeline's runtime
  behavior or write any pipeline artifact (`preprocess_output.json`,
  routing decisions, final payload, or evaluator output) as a side effect.
- **FR-005**: The preflight command MUST treat Ollama GPU success as
  unrelated to Paddle GPU readiness; it MUST NOT use *Ollama-process-specific*
  GPU state (whether the Ollama daemon is running, whether it is
  serving requests, whether it has bound the GPU) as evidence that
  Paddle GPU works. Observing shared host-level GPU runtime indicators
  — presence of `/dev/kfd` and `/dev/dri`, or environment variables
  such as `HIP_VISIBLE_DEVICES`, `ROCM_PATH`, and `CUDA_VISIBLE_DEVICES`
  — does NOT constitute "Ollama GPU state" for the purposes of this
  requirement; those indicate the host's overall GPU exposure and MAY
  be reported under FR-002. The classifier MUST still attempt its own
  Paddle device bind and PPStructureV3 GPU init to confirm Paddle GPU
  readiness; the host indicators alone never satisfy state (f).
- **FR-006**: The preflight command MUST be runnable in the same bench
  environment that runs the pipeline, with no requirement for
  workstation-only credentials, secrets, or external network calls beyond
  the existing first-run Paddle weight downloads.

#### Profile And CLI

- **FR-007**: The preprocessing profile vocabulary MAY add
  `ppstructurev3@gpu` as an explicit opt-in profile, only after FR-001
  preflight produces a meaningful pass/fail signal in the intended
  environment.
- **FR-008**: `ppstructurev3@cpu` MUST remain a valid preprocessing profile
  and MUST remain the default selection when no preprocessing profile flag
  is passed.
- **FR-009**: When a caller selects `ppstructurev3@gpu` and any GPU
  prerequisite is not satisfied, the pipeline MUST fail before writing any
  artifact, and the failure message MUST name both the selected profile
  and the specific missing GPU prerequisite (matching the FR-001 state
  vocabulary). The pipeline MUST gate on GPU prerequisites by invoking
  the same checker module that powers the FR-001 preflight readout,
  inline on every GPU pipeline invocation. There is no cached preflight
  result; the pipeline does not require that a separate preflight command
  has been run beforehand. The shared checker is the single source of
  truth for the FR-001 state vocabulary; the pipeline MUST NOT define a
  parallel set of GPU readiness states.
- **FR-010**: When `ppstructurev3@gpu` is selected and GPU initialization
  succeeds but a per-document GPU inference call fails, the pipeline MUST
  fail for that document. It MUST NOT silently fall back to CPU. In a
  multi-document harness run, the first per-document GPU inference
  failure MUST abort the entire run; remaining documents MUST NOT be
  processed and MUST NOT have artifacts written. The aborting failure
  MUST be attributable to the GPU profile and the offending document in
  the run output, matching the FR-001 state vocabulary where applicable
  (e.g. ROCm OOM, GPU runtime fault).
- **FR-011**: The stub profile MUST remain lane-less. `stub@gpu` MUST
  remain invalid.
- **FR-012**: The existing execution-slice flags (`--start-at`,
  `--stop-after`) MUST work with `ppstructurev3@gpu` exactly the way they
  work with `ppstructurev3@cpu`, with no changes to slice semantics.

#### Preprocessing Artifact Behavior

- **FR-013**: The GPU profile MUST produce the canonical artifact filename
  `preprocess_output.json` in the per-document folder, identical to the
  CPU profile. No additional canonical preprocessing artifact filenames
  may be introduced.
- **FR-014**: The GPU profile's `preprocess_output.json` MUST validate
  against the active `preprocess_output.schema.json` under
  `contract_set_version` 1.2.0 (or its successor at the time of
  implementation, without altering the schema in this feature).
- **FR-015**: The GPU profile MUST preserve the existing JSON field
  semantics: pages, blocks, raw OCR lines, tables, quality, ingestion
  sources, warnings, and document text. No schema fields may be added,
  removed, or repurposed in this feature. For this feature and for
  FR-025, "schema field" and "artifact schema" mean the
  JSON-Schema-validated field shape of the four stage 1 artifacts —
  field name, presence rule, JSON type, and any constraints expressed
  in `contracts/stage1_vendor_identity/v1.2.0/*.schema.json`. They do
  NOT cover the free-form string content of fields whose JSON Schema
  is `{"type": "string", "minLength": 1}` (notably `pipeline_version`).
  Adding parseable structure to such a free-form string (e.g. a
  trailing `.cpu` or `.gpu<N>` lane segment) is a content addition,
  not a schema change, and is permitted under FR-016 provided every
  artifact still validates against the unchanged JSON Schema and the
  parser contract is documented.
- **FR-016**: The GPU profile MUST make the selected profile and device
  visible to downstream consumers by encoding them as additional segments
  in the existing `pipeline_version` string of `preprocess_output.json`
  (e.g. an explicit `cpu` or `gpu<N>` segment alongside the existing
  semver/engine/dpi segments). No other artifact field, and no new schema
  field, may be used to carry this identity. A `preprocess_output.json`
  produced under `ppstructurev3@gpu` MUST be identifiable as such by
  parsing `pipeline_version` alone, without re-running the pipeline and
  without consulting harness stdout.
- **FR-017**: The CPU profile's existing determinism behavior
  (`enable_mkldnn=False`, `cpu_threads=1`, byte-stable output across
  repeat runs on the same input) MUST remain unchanged. Any byte-level
  diff on CPU output before and after this feature is a regression.

#### Test, Harness, And Documentation

- **FR-018**: Default automated tests MUST remain CPU/stub safe. CI
  defaults MUST NOT require GPU, ROCm device exposure, or Paddle GPU
  weight downloads beyond what already runs today.
- **FR-019**: GPU-dependent tests MUST be opt-in or correctly skipped when
  preflight prerequisites are absent, with a skip reason that points back
  to the preflight states from FR-001.
- **FR-020**: At least one GPU-gated integration test MUST exercise the
  GPU profile end-to-end on a real stage 1 document, asserting (a)
  successful GPU initialization, (b) `preprocess_output.json` written in
  the per-document folder, (c) artifact validates against the active
  schema, (d) the GPU profile/device is visible in
  `pipeline_version`/run metadata.
- **FR-021**: The harness MUST be able to request `ppstructurev3@gpu`
  through the existing pipeline-profile interface once the profile is
  enabled, without changes to corpus layout, artifact filenames, or
  harness output contracts.
- **FR-022**: The feature MUST capture warm CPU vs. warm GPU
  preprocessing timing for the same input. Timing capture MUST NOT
  require introducing a new mandatory committed benchmark artifact, a
  new persisted artifact filename, or any change to the four stage 1
  artifact schemas. Timing values (one-time profile initialization time
  and per-document preprocessing time) MUST be emitted as additive
  optional fields on the existing feature-011 `kind: "run_summary"`
  stdout JSON line, so a developer can capture them by tee-ing stdout
  without parsing committed baselines. Adding these fields MUST NOT
  break consumers of the existing `run_summary` shape.
- **FR-023**: The feature MUST update the relevant runtime/quickstart
  documentation so a developer reading docs alone can: run the preflight
  command, interpret each FR-001 readout state, choose between CPU and
  GPU profiles, and know which test outcomes constitute a skip versus a
  hard fail. If a separate GPU dependency install path or container
  device exposure change is introduced, it MUST be clearly documented as
  workstation/experimental and MUST leave the default CPU install path
  intact.
- **FR-024**: The feature MUST NOT make `requirements.txt` or
  `pyproject.toml` for the lightweight pipeline container depend on a
  workstation-specific GPU wheel that breaks CPU-only development. Any
  GPU-only install path MUST be additive and clearly named.

#### Hard Boundaries

- **FR-025**: This feature MUST NOT change any stage 1 artifact schema, MUST
  NOT change any canonical artifact filename, MUST NOT introduce remote
  cloud execution or provider credentials, MUST NOT add the
  `edge-ocr@jetson` profile, MUST NOT add Jetson-local Paddle GPU
  support, MUST NOT replace `ppstructurev3@cpu` as the default profile,
  and MUST NOT regenerate any committed corpus baseline from GPU output
  unless determinism is proven and explicitly accepted in a follow-up
  decision.

### Key Entities

- **Preflight readout**: a structured diagnostic produced by the preflight
  command. Captures interpreter, Paddle/PaddleOCR versions, GPU build
  flag, visible device count, selected device, runtime device exposure,
  PPStructureV3 GPU initialization result, and a single classified state
  matching the FR-001 vocabulary. Not a persisted contract artifact; its
  shape may evolve without an amendment.
- **Preprocessing profile selection**: the resolved choice of
  `ppstructurev3@cpu`, `ppstructurev3@gpu`, or `stub`, surfaced into the
  pipeline run and into `pipeline_version` / run metadata for the
  resulting `preprocess_output.json`.
- **GPU prerequisites**: the named conditions that must hold before
  `ppstructurev3@gpu` can run for a single document — Paddle GPU build
  available, GPU device visible to the runtime, Paddle able to bind to
  the GPU device, PPStructureV3 able to initialize on that device. Each
  has a corresponding FR-001 failure-state name used in fail-fast error
  messages.
- **Timing evidence**: warm CPU vs. warm GPU preprocessing timing
  observations for the same input, including one-time profile
  initialization time and per-document preprocessing time. Surfaced in
  run output but not promoted into a committed benchmark contract.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can run one documented command in the bench
  environment and within five minutes wall-clock from a cold weights
  cache (i.e. first-run weight downloads under `~/.paddlex/`) know
  whether Paddle GPU is usable for PPStructureV3 on this workstation,
  with the result classified into one of the six FR-001 states.
  Subsequent invocations on the same machine, with weights already
  cached, MUST return in seconds rather than minutes.
- **SC-002**: For every FR-001 failure state, the preflight readout names
  the next remediation step (install path, container exposure, runtime
  switch, or hardware/runtime not viable) without requiring a developer
  to read pipeline source code.
- **SC-003**: When preflight does not pass, attempting to use the GPU
  profile fails before any artifact write in 100% of attempts, and the
  failure message names both the selected profile and the missing
  prerequisite.
- **SC-004**: When preflight passes, the GPU profile produces a
  schema-valid `preprocess_output.json` for the standard known-good test
  invoice (`inv_001_easy`) with non-empty `document_text` and at least
  three layout blocks.
- **SC-005**: The selected preprocessing profile and device are
  recoverable from `preprocess_output.json` by parsing `pipeline_version`
  alone, without re-running the pipeline and without consulting harness
  stdout.
- **SC-006**: The CPU profile produces byte-identical
  `preprocess_output.json` for a fixed input on repeat runs after this
  feature lands, where "byte-identical" means a per-byte SHA-256 match
  between two consecutive runs on the **same host environment**
  (interpreter, OS, Paddle wheel, PaddleOCR weights, lane segment) on
  the same input. The fixed input used for the in-tree regression
  guard is `tests/stage1_vendor_identity/inv_001_easy/source.pdf`. The
  guarantee applies to repeat-run determinism, not to cross-environment
  determinism (cross-host, cross-wheel, cross-OS byte-identity is
  explicitly out of scope). The `pipeline_version` lane-segment
  addition introduced by this feature is a one-time intentional bump
  applied uniformly to every CPU run after this feature lands; SC-006
  is verified against post-feature CPU output, not against pre-feature
  artifacts.
- **SC-007**: Default automated test runs (no GPU available) pass in the
  same time envelope as today, with GPU-gated tests skipped with a
  reason traceable to a specific FR-001 state.
- **SC-008**: When the GPU profile works, warm GPU per-document
  preprocessing time on the same stage 1 invoice is measurably lower than
  warm CPU per-document preprocessing time for the same invoice on the
  same workstation, in observed runs (the exact threshold is left to the
  promotion decision in a follow-up feature).
- **SC-009**: At the end of this feature, no committed corpus baseline
  has been regenerated from GPU output unless byte-level determinism
  has been demonstrated and accepted in a recorded decision, and the CPU
  profile remains the default for full top-level pipeline runs.

## Assumptions

- The preflight command lives in-tree (under the existing pipeline or
  preprocessing package, e.g. exposed through `python -m
  ledgerlinc_ocr.<...>` or an existing CLI entrypoint), rather than as a
  loose `scripts/` shell script. The exact location is a plan-level
  decision, but it MUST be discoverable from a single documented
  invocation per FR-006.
- The opt-in profile name is `ppstructurev3@gpu`, matching the existing
  `<implementation>@<lane>` profile grammar from
  `prd-stage-runtime-profiles.md`. A more explicit name such as
  `ppstructurev3@workstation-gpu` is not adopted in this feature unless
  preflight outcomes prove the shorter name would be ambiguous.
- The supported Paddle GPU runtime path is left to be determined by
  preflight outcomes. The feature does not assume a specific path (WSL
  Docker, WSL-native, or native Linux ROCm); whichever path preflight
  proves viable MUST be documented as the supported path.
- If preflight cannot pass on this workstation's hardware/runtime
  combination, the feature still ships the preflight tool and
  documentation. It does not enable a non-functional `ppstructurev3@gpu`
  adapter, and it does not change the CPU default. That outcome is
  considered a successful delivery of P1 and an explicit pause of P2/P3
  pending a follow-up decision.
- GPU determinism is assumed *not* to match CPU byte-stability by
  default. Any deviation from CPU output is recorded but does not justify
  regenerating committed baselines from GPU output in this feature; that
  is a separate, future decision.
- The harness pipeline-profile interface from feature 011 already
  supports per-stage profile selection. This feature reuses that surface
  rather than introducing a new harness contract.
- "Bench environment" in this spec refers to the environment used for
  pipeline development and validation today (the `py-bench` venv or its
  equivalent container). Any change required to expose the GPU device to
  that environment is in scope for documentation and configuration; any
  change to the lightweight pipeline container's CPU-only baseline is
  out of scope.
- The PaddleOCR/PaddleX model weight footprint already accepted under
  feature 010 remains acceptable. This feature does not introduce a new
  weight category; it may exercise the same weights on the GPU device.

## Dependencies

- Feature 010 (`010-pp-structurev3-preprocessing`) — provides the
  PPStructureV3 CPU profile and the active `preprocess_output.json`
  contract this feature must preserve unchanged.
- Feature 011 (`011-stage-runtime-profiles`) — provides the
  per-stage profile selection surface (`--preprocess-profile`,
  start/stop slice flags, warm preprocessing controller) that this
  feature extends with `ppstructurev3@gpu` as an opt-in value.
- The bench environment's GPU device exposure and Paddle install state.
  Both are inputs the preflight command observes; this feature owns
  documenting them, not provisioning a specific hardware/runtime
  combination.

## Out Of Scope

- Replacing `ppstructurev3@cpu` as the default preprocessing profile.
- Regenerating any committed corpus baseline from GPU output.
- Adding `edge-ocr@jetson`, Jetson-local Paddle GPU support, or any
  Jetson-class hardware target.
- Remote cloud execution, cloud-provider credentials, or
  provider-managed fallback paths.
- Schema changes to any of the four stage 1 artifacts.
- Side-by-side canonical `preprocess_output.json` artifacts in the same
  per-document folder (run-namespaced comparison output is allowed in
  the runtime-profile PRD but is not introduced by this feature).
- Embedding a model runtime into the pipeline container.
- Multi-GPU device selection (e.g. binding `gpu:1` or higher). The
  `LaneSegment` grammar reserves `gpu<N>` for `N ≥ 0` to keep future
  multi-GPU work non-breaking, but only `gpu0` is emitted by this
  feature.
- Non-x86-CUDA / non-ROCm GPU lanes (DCU, NPU, XPU, MetaX,
  Iluvatar). PaddleOCR's `device=` parameter accepts those strings,
  but this feature does not introduce profile vocabulary for them.
- Cross-environment determinism (byte-identity across hosts, wheels,
  or OS versions) for the CPU lane. SC-006 covers same-host repeat
  runs only.
- GPU-lane byte-level repeat-run determinism. Per the Assumptions
  section, GPU output is recorded but not asserted to be byte-stable
  across runs.
