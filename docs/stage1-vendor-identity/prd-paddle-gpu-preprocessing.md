# PRD: Workstation Paddle GPU Preprocessing

## Purpose

This PRD defines the product requirements for feature 014: proving whether the
stage 1 PPStructureV3 preprocessing profile can run on the workstation GPU and,
if it can, adding an explicit GPU preprocessing profile that the harness can use
for faster validation.

The feature is intentionally staged as a runtime spike plus opt-in profile. It
does not replace the existing `ppstructurev3@cpu` path until the GPU path proves
that it is visible to the runtime, schema-compatible, sufficiently stable, and
measurably faster on the same corpus documents.

## Problem Statement

Feature 011 made the top-level pipeline warm enough to avoid rebuilding
PPStructureV3 once per document, but the full-structure preprocessing profile is
still CPU-only. That leaves the GPU unused for the slowest local pipeline stage.

The current local state is:

- `src/ledgerlinc_ocr/preprocessing/ocr.py` constructs `PPStructureV3` with
  `device="cpu"`.
- The profile resolver rejects `ppstructurev3@gpu` because feature 011 scoped
  PPStructureV3 as CPU-only.
- The `py-bench` virtual environment has `paddle==3.3.1` and
  `paddleocr==3.5.0`, but the installed Paddle wheel is CPU-only
  (`compiled_cuda == False`, `cuda_count == 0`).
- The workstation GPU is an AMD/ROCm WSL device (`/dev/dxg`, `gfx1151`).
- The `ledgerlinc-ollama` container maps `/dev/dxg` and selected ROCm/WSL
  libraries, but `py-bench` currently does not expose `/dev/dxg`.
- The existing warm PPStructure CPU integration test can run, but it is slow
  enough to make regular harness-driven validation uncomfortable.

The core unknown is not only code-level device selection. It is whether this
AMD/ROCm WSL environment has a compatible Paddle GPU runtime at all. If it
does not, the project still needs a clear preflight failure and documented
decision before spending time wiring a non-working profile.

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

## Success Criteria

Preflight success criteria:

1. A developer can run one documented command in the intended bench environment
   and see whether Paddle GPU is available.
2. The command reports the exact Python interpreter and Paddle version used.
3. The command identifies CPU-only Paddle installs distinctly from missing GPU
   device exposure.

Profile success criteria, if Paddle GPU is available:

4. `python -m ledgerlinc_ocr.pipeline run --document-folder <temp-doc> --start-at preprocess --stop-after preprocess --preprocess-profile ppstructurev3@gpu --overwrite` writes a schema-valid `preprocess_output.json`.
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

## Risks And Mitigations

- **Risk: PaddlePaddle GPU support is CUDA-oriented and does not provide a
  usable AMD/ROCm WSL wheel for this machine.**
  Mitigation: make preflight the first deliverable and stop with a clear
  documented blocker if the runtime is not viable.
- **Risk: Docker Desktop hides the WSL GPU device from `py-bench`.**
  Mitigation: mirror the explicit device/library mapping pattern already used
  for `ledgerlinc-ollama`, or document that Paddle GPU must run WSL-native or
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
