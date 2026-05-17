## Why

Feature 019 is the decision point for whether OCR-lines-plus-coordinates can replace full PPStructureV3 evidence for stage 1 vendor identity. If 019 promotes or conditionally accepts that fast lane, the next project risk is proving the same edge-first path on Jetson hardware without weakening the artifact contracts or silently falling back to CPU.

## What Changes

- Add the governed path for turning the already-recognized `edge-fast` stack into a live Jetson validation stack after feature 019 completes.
- Replace the current deferred `edge-ocr@jetson` and `ollama@jetson` behavior with live Jetson-capable adapters in subsequent Speckit features.
- Require Jetson-specific preflight before live edge runs: hardware/runtime visibility, OCR GPU viability, Jetson-local Ollama reachability, selected edge model availability, and no CPU-only fallback.
- Preserve the existing four canonical stage 1 artifact filenames and schemas for `edge-fast` runs.
- Require edge run metadata to distinguish `edge-fast` from `full-workstation` and `cloud-workstation` results.
- Define comparison flow against the workstation baseline through the existing harness/evaluator boundary, not by moving benchmark/report ownership into the pipeline.
- Keep the implementation in this repository under the existing profile grammar; no separate edge OCR repository is introduced.
- No breaking changes to the default `full-workstation` path.

## Capabilities

### New Capabilities

- `jetson-edge-fast-validation`: Defines the post-019 Jetson edge validation capability for `edge-fast`, including Jetson preflight, live `edge-ocr@jetson`, live `ollama@jetson`, fail-fast/no-CPU-fallback semantics, runtime metadata, and evaluator comparison expectations.

### Modified Capabilities

- None. Existing Speckit feature 011 already reserved the profile names and stack-preset surface; this change governs the live behavior that was intentionally deferred.

## Impact

- Pipeline runtime/profile dispatch: `src/dartwing_ocr/pipeline/profiles.py`, `src/dartwing_ocr/pipeline/stages.py`, `src/dartwing_ocr/pipeline/runner.py`, `src/dartwing_ocr/pipeline/corpus_run.py`.
- Preprocessing implementation: new or extended edge OCR adapter under `src/dartwing_ocr/preprocessing/` or a profile-owned sibling module.
- Extraction implementation: Jetson lane resolution and Gemma 4 E2B configuration through the existing Ollama adapter layer.
- Evaluator/harness invocation: pass-through of `--stack-preset edge-fast` and `--ollama-jetson-url` remains the boundary; evaluator owns comparison and reports.
- Tests: new Jetson-gated integration tests plus CPU/stub-safe default tests proving unavailable Jetson prerequisites skip or fail clearly.
- Documentation: `docs/stage1-vendor-identity/architecture.md`, `ollama-runtime.md`, and the post-019 fast-lane decision note.
