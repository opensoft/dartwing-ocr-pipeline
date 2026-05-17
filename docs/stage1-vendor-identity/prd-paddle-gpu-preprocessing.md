# PRD: Workstation Paddle GPU Preprocessing

## Purpose

This PRD defines the product requirements for feature 014: proving whether the
stage 1 PPStructureV3 preprocessing profile can run on the workstation GPU and,
if it can, adding an explicit GPU preprocessing profile that the harness can use
for faster validation. It also captures the follow-on optimization roadmap now
that the ROCm path has been proven functional but too slow for routine harness
use.

The feature is intentionally staged as a runtime spike plus opt-in profile. It
does not replace the existing `ppstructurev3@cpu` path until the GPU path proves
that it is visible to the runtime, schema-compatible, sufficiently stable, and
measurably faster on the same corpus documents.

## Problem Statement

Feature 011 made the top-level pipeline warm enough to avoid rebuilding
PPStructureV3 once per document, but the full-structure preprocessing profile is
still CPU-only. That leaves the GPU unused for the slowest local pipeline stage.

The current local state is:

- `src/dartwing_ocr/preprocessing/ocr.py` constructs `PPStructureV3` with
  `device="cpu"`.
- The profile resolver rejects `ppstructurev3@gpu` because feature 011 scoped
  PPStructureV3 as CPU-only.
- The `py-bench` virtual environment has `paddle==3.3.1` and
  `paddleocr==3.5.0`, but the installed Paddle wheel is CPU-only
  (`compiled_cuda == False`, `cuda_count == 0`).
- The workstation GPU is an AMD/ROCm WSL device (`/dev/dxg`, `gfx1151`).
- The `dartwing-ollama` container maps `/dev/dxg` and selected ROCm/WSL
  libraries, but `py-bench` currently does not expose `/dev/dxg`.
- The existing warm PPStructure CPU integration test can run, but it is slow
  enough to make regular harness-driven validation uncomfortable.

The core unknown is not only code-level device selection. It is whether this
AMD/ROCm WSL environment has a compatible Paddle GPU runtime at all. If it
does not, the project still needs a clear preflight failure and documented
decision before spending time wiring a non-working profile.

Post-proof state:

- A ROCm-enabled `paddlepaddle-dcu` wheel can bind Paddle to `gpu:0` on the
  WSL host.
- PPStructureV3 GPU preflight can initialize successfully on `gpu:0`.
- A temp pipeline run over `inv_001_easy/source.pdf` produced a schema-valid
  `preprocess_output.json` with a `.gpu0` pipeline version.
- The measured temp run was about 103 seconds for one document, which is too
  slow for the intended faster harness workflow.
- The observed runtime includes duplicated PPStructureV3 initialization
  (preflight plus actual preprocessing), MIOpen/COMGR startup work, full
  PPStructureV3 model loading, 300 DPI rasterization, and the full
  layout/OCR/table stack.

## Goal

Add a disciplined GPU validation path for PPStructureV3 preprocessing:

- first, prove or disprove that Paddle GPU inference is available in the
  intended development runtime
- then, if available, add `ppstructurev3@gpu` as an explicit opt-in
  preprocessing profile
- preserve the canonical `preprocess_output.json` artifact contract
- prevent silent CPU fallback when a caller explicitly asks for GPU
- provide timing and quality evidence that decides whether GPU preprocessing
  should become part of the normal harness workflow

## Relationship To Existing Runtime Profiles

This PRD amends the stage-runtime profile roadmap without changing the existing
defaults immediately.

Current default remains:

- preprocess: `ppstructurev3@cpu`
- extract: `ollama@gpu`
- routing: `rules@cpu`
- final payload: `assembler@cpu`

Feature 014 may add:

- preprocess: `ppstructurev3@gpu`

`ppstructurev3@gpu` is a workstation full-structure profile. It is not the same
as `edge-ocr@jetson`.

- `ppstructurev3@gpu` means the same full PPStructureV3 layout/OCR/table stack
  as `ppstructurev3@cpu`, but executed on a workstation GPU if Paddle supports
  it.
- `edge-ocr@jetson` remains a later lightweight edge scanner profile for the
  Jetson Nano Super class target.

The GPU profile must not weaken the profile grammar or introduce a generic
`real` switch.

## Scope

Included:

- Add a GPU preflight path that reports, at minimum:
  - Python interpreter and environment path
  - Paddle version
  - Paddle GPU capability result
  - visible device count / selected device
  - whether the container exposes the required GPU device files
  - whether PPStructureV3 can initialize with a GPU device string
- Update the development runtime instructions for `py-bench` or the relevant
  bench container so GPU device exposure is explicit.
- Decide and document the supported Paddle GPU install path for this workstation
  environment. If no compatible AMD/ROCm WSL wheel exists, record that as a
  first-class outcome rather than hiding it behind skipped tests.
- Add `ppstructurev3@gpu` to the profile contract only after preflight has a
  meaningful pass/fail signal.
- Refactor preprocessing engine construction so the PPStructureV3 device is an
  explicit profile-owned setting rather than a hard-coded string.
- Ensure a selected GPU profile fails fast if the runtime cannot use GPU. It
  must not silently run the CPU profile.
- Add at least one GPU-gated integration test over a real stage 1 document that
  verifies:
  - the GPU profile can initialize
  - `preprocess_output.json` is written
  - the artifact validates against the active schema
  - run metadata or pipeline version makes the selected profile/device visible
- Capture timing metadata for CPU versus GPU preprocessing on the same document
  or small corpus copy.
- Capture enough timing detail to separate import, preflight, engine
  construction, warmup, rasterization, inference, and artifact writing.
- Update PRD/runtime docs and quickstart notes so developers know when a skip,
  fail-fast, or pass is expected.

Explicitly out of scope:

- Replacing `ppstructurev3@cpu` as the default preprocessing profile before
  repeatability and quality are proven.
- Regenerating committed corpus baselines from GPU output in this feature unless
  determinism is proven and explicitly accepted.
- Adding the `edge-ocr@jetson` lightweight scanner.
- Adding Jetson-local Paddle GPU support.
- Remote cloud execution, provider credentials, or cloud fallback behavior.
- Changing any stage 1 artifact schema or canonical artifact filename.
- Running two canonical `preprocess_output.json` artifacts side by side in the
  same committed document folder.
- Embedding model runtimes into the pipeline container. Paddle remains a
  pipeline dependency, not a served model runtime.

## Requirements

### Environment And Dependency Requirements

1. The feature MUST distinguish these states in preflight output:
   - Paddle/PaddleOCR not installed
   - Paddle installed but CPU-only
   - GPU device not exposed to the container
   - GPU device exposed but not usable by Paddle
   - Paddle GPU usable but PPStructureV3 GPU initialization fails
   - PPStructureV3 GPU initialization succeeds
2. The feature MUST NOT make the base `requirements.txt` depend on a
   workstation-specific GPU wheel that breaks CPU-only development.
3. If a separate GPU requirements file or install script is introduced, it MUST
   be clearly named as workstation/experimental and MUST leave the default CPU
   install path intact.
4. The feature MUST document whether the supported path is WSL Docker,
   WSL-native, or native Linux ROCm. If WSL Docker is not viable, that must be
   stated directly.
5. The GPU path MUST not rely on Ollama's ROCm workaround as proof that Paddle
   can use the same device. Ollama GPU success and Paddle GPU success are
   separate runtime facts.

### Profile And CLI Requirements

1. `ppstructurev3@gpu` MAY be added as a preprocessing profile only as an
   explicit opt-in value.
2. `ppstructurev3@cpu` MUST remain valid and MUST remain the default until a
   later decision changes it.
3. Selecting `--preprocess-profile ppstructurev3@gpu` MUST fail before artifact
   write if GPU prerequisites are not satisfied.
4. Failure output MUST name the selected profile and the missing GPU
   prerequisite.
5. Stub profiles MUST remain lane-less. `stub@gpu` remains invalid.
6. The existing execution-slice flags (`--start-at`, `--stop-after`) MUST work
   with the GPU profile the same way they work with the CPU profile.

### Preprocessing Requirements

1. The GPU profile MUST produce the same canonical artifact filename:
   `preprocess_output.json`.
2. The GPU profile MUST validate against the active
   `preprocess_output.schema.json`.
3. The GPU profile MUST preserve the existing JSON field semantics:
   pages, blocks, raw OCR lines, tables, quality, ingestion sources, warnings,
   and document text.
4. The GPU profile MUST make the selected profile/device visible through
   pipeline version, run metadata, or both.
5. The GPU profile MUST not silently fall back to CPU after initialization or
   inference failure.
6. The CPU profile's existing `enable_mkldnn=False`, `cpu_threads=1`, and
   determinism behavior MUST remain unchanged.

### Test And Harness Requirements

1. Automated test defaults MUST remain CPU/stub safe. Normal CI must not require
   GPU, Paddle model downloads, or ROCm device access.
2. GPU tests MUST be opt-in or correctly skipped when prerequisites are absent.
3. A failed GPU preflight MUST be actionable: the output should say whether the
   next fix is dependency install, container device exposure, or unsupported
   hardware/runtime.
4. The harness MUST be able to request the GPU profile through the existing
   pipeline profile interface once the profile is enabled.
5. Timing comparison MUST be captured without adding a new required persisted
   benchmark artifact.

### GPU Performance Optimization Requirements

1. The GPU lane MUST avoid duplicated PPStructureV3 construction where a
   preflight-created engine can be reused safely by the actual preprocessing
   call, or the preflight MUST stop before heavy PPStructureV3 initialization
   and let the production engine construction act as the step-6 proof.
2. Warm corpus mode MUST support one reusable `ppstructurev3@gpu` engine per
   process, matching the intent of the existing warm CPU profile.
3. The timing model MUST distinguish one-time costs from per-document costs:
   Paddle import, Paddle bind probe, PPStructureV3 init, MIOpen/COMGR warmup,
   rasterization, per-page inference, and artifact write.
4. GPU benchmark runs MUST exclude optional warmup time from per-document
   steady-state timing, while still reporting warmup time separately.
5. The pipeline MUST keep `ppstructurev3@cpu` as the default until GPU
   preprocessing is materially faster on the same corpus sample and quality
   remains acceptable.
6. Any reduction of the PPStructureV3 module set, OCR model size, DPI, or page
   region MUST be measured against vendor-identity quality before becoming the
   normal GPU lane.
7. The GPU lane MUST still fail fast rather than silently falling back to CPU
   when an optimization path is unavailable.

## Success Criteria

Preflight success criteria:

1. A developer can run one documented command in the intended bench environment
   and see whether Paddle GPU is available.
2. The command reports the exact Python interpreter and Paddle version used.
3. The command identifies CPU-only Paddle installs distinctly from missing GPU
   device exposure.

Profile success criteria, if Paddle GPU is available:

4. `python -m dartwing_ocr.pipeline run --document-folder <temp-doc> --start-at preprocess --stop-after preprocess --preprocess-profile ppstructurev3@gpu --overwrite` writes a schema-valid `preprocess_output.json`.
5. The same command fails fast with no artifact write when GPU prerequisites are
   intentionally absent.
6. `ppstructurev3@cpu` still passes its existing tests.
7. GPU output for `inv_001_easy` has non-empty `document_text` and at least
   three layout blocks.
8. A small CPU-vs-GPU comparison records initialization time and per-document
   preprocessing time for the same input.

Promotion criteria for future default consideration:

9. GPU preprocessing is materially faster than warm CPU preprocessing on the
   same local corpus sample.
10. GPU preprocessing is repeatable enough for the intended use. If byte-level
    determinism differs from CPU, the feature must record that limitation and
    keep GPU out of committed baseline regeneration until a follow-up decision.

Optimization success criteria:

11. Single-document GPU runtime is decomposed into named timing phases so the
    project can tell whether the current two-minute cost is startup, tuning,
    rasterization, inference, or artifact writing.
12. Warm GPU corpus mode processes multiple documents without reconstructing
    PPStructureV3 for every document.
13. A warm GPU run reports first-document initialization/warmup separately from
    subsequent per-document inference time.
14. At least one optimization slice demonstrates a measured runtime reduction
    on `inv_001_easy` or explains, with phase timings, why the bottleneck moved
    to a non-optimized phase.

## Recommended Implementation Order

1. Add a preflight script or CLI command that diagnoses the current environment
   without changing pipeline behavior.
2. Update bench/devcontainer documentation or config so GPU device exposure is
   explicit.
3. Determine whether Paddle GPU can run on the AMD/ROCm WSL workstation.
4. If preflight cannot pass on this hardware, stop at a documented blocker and
   do not add a pretend live profile.
5. If preflight passes, refactor PPStructureV3 construction to accept a device
   setting.
6. Add `ppstructurev3@gpu` to the closed profile vocabulary and adapter
   registry.
7. Add GPU-gated integration tests and CPU regression tests.
8. Add timing comparison output and documentation.
9. Decide in a later feature whether GPU becomes the default or remains an
   opt-in workstation profile.

## Implementation Feature List

The GPU proof is complete enough to split optimization into smaller follow-on
features. These are implementation features, not new product surfaces unless
their acceptance criteria say otherwise.

### Feature 015: GPU Engine Reuse And Phase Timing

Purpose: remove duplicated startup work and make the current two-minute runtime
explainable.

Scope:

- Replace the heavy preflight-plus-runtime double initialization with one
  process-scoped GPU readiness result and one reusable PPStructureV3 engine.
- Ensure `ppstructurev3@gpu` cold and warm runs use the same engine cache rules
  as the CPU warm path, with a single-device-per-process guard.
- Add phase timing for Paddle import/bind, PPStructureV3 init, warmup,
  rasterization, inference, and artifact writing.
- Surface the timing in existing run summary metadata without adding a new
  persisted benchmark artifact.

Acceptance:

- One GPU preprocessing process constructs PPStructureV3 no more than once.
- A warm corpus run over at least two documents reports GPU init/warmup only on
  the first document and inference time on each successful document.
- Existing CPU/stub CI remains GPU-free.
- The temp `inv_001_easy` run produces the same schema-valid `.gpu0` artifact
  and includes phase timing sufficient to identify the slowest phase.

### Feature 016: GPU Warmup And MIOpen Cache Stabilization

Purpose: reduce first-real-document latency caused by MIOpen/COMGR tuning and
make benchmark timing repeatable after reboot or cache clear.

Scope:

- Add an explicit optional GPU warmup step after engine construction and before
  timed corpus documents.
- Keep `MIOPEN_FIND_MODE=2` as the default workstation fast-find mode unless a
  measured alternative is better.
- Document cache locations and startup behavior for `~/.cache/miopen` and
  `~/.cache/comgr`.
- Record warmup time separately from document inference time.

Acceptance:

- Warmup can be run intentionally and is not confused with per-document OCR
  time.
- Repeated runs on the same warmed cache have less timing variance than cold
  cache runs.
- MIOpen workspace warnings are captured as known runtime diagnostics or
  eliminated by configuration if a safe configuration is found.

### Feature 017: PPStructureV3 Module And Model Reduction

Purpose: stop paying for PPStructureV3 components that are not needed for stage
1 vendor identity.

Scope:

- Audit the actual runtime adapter options, not just preflight options, and
  confirm unused modules are disabled in the live GPU preprocessing path.
- Test lighter PaddleOCR detection/recognition model variants against the
  stage 1 vendor identity corpus.
- Keep output schema unchanged; only the internal OCR/layout strategy changes.

Acceptance:

- The GPU lane logs or records the model/module configuration used.
- At least two model/module configurations are benchmarked against the same
  small corpus.
- Any selected lighter configuration preserves vendor-identity quality gates
  before it becomes the default GPU configuration.

### Feature 018: DPI And Region Strategy

Purpose: reduce image size and page area processed by OCR while protecting
vendor-name recall.

Scope:

- Benchmark 300 DPI against lower DPI settings such as 240 and 200.
- Add a vendor-identity-first region strategy that can process header/top-page
  regions before escalating to full-page PPStructureV3.
- Fall back to full-page processing when confidence or evidence coverage is
  insufficient.

Acceptance:

- DPI changes are measured for speed and extraction quality.
- Region-first mode never writes a partial artifact that violates the existing
  schema.
- The fallback path is deterministic and visible in timing/diagnostic metadata.

### Feature 019: OCR-Only Fast Lane Evaluation

Purpose: decide whether stage 1 vendor identity really needs full
PPStructureV3 layout/table inference on every document.

Scope:

- Prototype an OCR-lines-plus-coordinates preprocessing lane that skips full
  structure/table recognition.
- Compare downstream vendor identity extraction and routing decisions against
  the full PPStructureV3 lane.
- Keep this as an experimental lane until accuracy is known.

Acceptance:

- The fast lane can process the same temp corpus without schema changes.
- The evaluator shows whether vendor identity accuracy is acceptable compared
  with full PPStructureV3.
- The project has a documented decision to promote, revise, or discard the
  fast lane.

## Risks And Mitigations

- **Risk: PaddlePaddle GPU support is CUDA-oriented and does not provide a
  usable AMD/ROCm WSL wheel for this machine.**
  Mitigation: make preflight the first deliverable and stop with a clear
  documented blocker if the runtime is not viable.
- **Risk: Docker Desktop hides the WSL GPU device from `py-bench`.**
  Mitigation: mirror the explicit device/library mapping pattern already used
  for `dartwing-ollama`, or document that Paddle GPU must run WSL-native or
  native Linux instead of inside `py-bench`.
- **Risk: The GPU profile silently runs on CPU.**
  Mitigation: fail fast unless Paddle reports a GPU-capable build and a selected
  GPU device before PPStructureV3 inference starts.
- **Risk: GPU inference is faster but not byte-stable.**
  Mitigation: keep GPU opt-in and avoid committed baseline regeneration until a
  separate determinism decision accepts or mitigates the difference.
- **Risk: GPU model memory requirements exceed the workstation or container
  allocation.**
  Mitigation: test a single-document smoke first, then a small warm corpus,
  before full-corpus runs.
- **Risk: GPU and CPU output quality differ.**
  Mitigation: compare schema validity, block counts, document text presence, and
  downstream evaluator results before using GPU outputs for baseline decisions.

## Open Questions

1. Is the supported Paddle GPU path for this workstation WSL Docker,
   WSL-native, or native Linux?
2. Does the project want the profile name `ppstructurev3@gpu`, or should the
   profile be more explicit, such as `ppstructurev3@workstation-gpu`?
3. If AMD/ROCm Paddle is not viable, do we pause this feature, try a source
   build, or require CUDA hardware for the GPU profile?
4. What repeatability threshold is acceptable for GPU preprocessing if exact
   byte-identical output is not achievable?
5. Should GPU preflight live under `scripts/`, the preprocessing package, or the
   pipeline CLI?

## Fallback

If Paddle GPU cannot run in the current workstation environment, feature 014
should still land a clear diagnostic outcome:

- documented preflight command
- documented failure mode
- no enabled `ppstructurev3@gpu` live adapter
- no change to the default `ppstructurev3@cpu` profile

That outcome is useful because it prevents future work from assuming that
Ollama ROCm success implies Paddle GPU support on the same WSL/AMD stack.
