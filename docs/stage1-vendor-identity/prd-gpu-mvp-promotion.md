# PRD: GPU MVP Promotion

## Purpose

This PRD defines the product requirements for the post-feature-020 GPU MVP
promotion feature. Feature 020 is sufficient for the MVP feature surface:
deterministic vendor-identity evidence signals, run-summary observability, the
OCR-only skip-fallback opt-in, downstream compatibility, and CPU-safe
regression coverage.

It is not sufficient, by itself, to claim an exclusively GPU-backed MVP. The
remaining work is to close the GPU-deferred verification items, record
workstation benchmark and quality evidence, and update the operator/demo path
so the MVP is run through GPU profiles deliberately and fail-fast when GPU is
unavailable.

The intended Speckit feature name is:

- `021-gpu-mvp-promotion`

## Problem Statement

The MVP implementation now has the right pipeline behavior, but the project is
still split between two operational modes:

- CPU/stub-safe paths are fully merge-gated and remain useful for CI.
- GPU paths are supported by profile flags and preflight contracts, but several
feature-020 GPU proof points are explicitly deferred in
`specs/020-vendor-evidence-gate/quickstart.md` Appendix B.

Those deferred items include:

- real end-to-end skip-fallback tests on `ppstructurev3@gpu`
- borderline fallback tests on `ppstructurev3@gpu`
- lazy PPStructureV3 construction behavior when all OCR-only candidates are
  sufficient and skip-fallback suppresses every document
- `--gpu-warmup` exception behavior when warmup intentionally forces
  construction
- FR-015 four-run benchmark numbers for the fixed five-document subset
- FR-016 two-metric quality-gate evidence
- the operator-facing decision on whether skip-fallback stays opt-in or becomes
  the default after GPU validation

Until those proof points are closed, the team can demo feature 020 safely on
CPU, but should not represent the MVP as GPU-only or performance-promoted.

## Goal

Promote the MVP operating posture from CPU-safe feature completeness to
GPU-backed validation readiness:

- run the stage 1 MVP through workstation GPU preprocessing and GPU extraction
- fail fast instead of silently falling back when GPU is explicitly selected
- turn the deferred feature-020 GPU checks into real executable tests or
  documented benchmark outputs
- record latency and quality evidence in the feature-020 appendices
- update demo instructions so the canonical MVP demo uses GPU profiles
- make a documented promotion decision for the skip-fallback behavior

This feature is primarily a validation, promotion, and documentation slice. It
should avoid adding new product behavior unless the quality gate passes and the
team explicitly chooses to promote the skip-fallback default.

## Users and Stakeholders

Primary users:

- pipeline developers running the final MVP demo
- operators validating workstation GPU readiness
- reviewers deciding whether the OCR-only skip-fallback path is safe to
  promote

Stakeholders:

- Dartwing OCR/model pipeline engineering
- runtime and workstation owners for AMD/ROCm WSL and native Linux ROCm paths
- evaluation and harness owners who need comparable GPU benchmark evidence

## Scope

Included:

- Verify the active workstation environment using
  `python -m dartwing_ocr.preprocessing.preflight`.
- Require `state == "ppstructurev3_init_succeeded"` before any GPU MVP demo or
  benchmark run.
- Use `.venv-paddle-rocm` or another explicitly GPU-capable interpreter for
  GPU validation; do not rely on the CPU `.venv`.
- Verify host Ollama GPU placement for extraction (`ollama@gpu`) before
  claiming a full GPU-backed run.
- Replace feature-020 deferred GPU placeholders with meaningful executable
  checks where practical:
  - `test_evidence_gate_skip_fallback.py`
  - `test_evidence_gate_skip_fallback_borderline.py`
  - GPU variants in `test_evidence_gate_all_suppressed_lazy_construction.py`
  - `test_evidence_gate_benchmark.py`
  - `test_quality_gate_two_metric_evidence_gate.py`
- Run the fixed five-document GPU benchmark subset from feature 020:
  `inv_001_easy`, `inv_002_easy`, `inv_006_medium`, `inv_011_hard`,
  `inv_012_hard`, unless a prior feature appendix supplies a more specific
  fixed subset.
- Preserve the four-run benchmark discipline from feature 020:
  warmup once, legacy default twice, skip-fallback candidate twice, discard the
  first timing run for each lane, and compare run 2 values.
- Record every emitted `phase_timings.*` key for benchmarked documents,
  including `paddle_import`, `gpu_bind_probe`, `engine_init`, `warmup`,
  `rasterization`, `per_page_inference`, `artifact_write`, and `total` when
  present.
- Verify the feature-020 timing expectation: on suppressed documents, only
  `per_page_inference` and `total` should materially decrease relative to the
  legacy run; other timing keys should stay within the measured jitter band.
- Run the two-metric quality gate:
  - candidate aggregate vendor-identity score is greater than or equal to the
    legacy aggregate score
  - candidate per-document pass count is greater than or equal to the legacy
    pass count
- Fill feature-020 Appendix A and Appendix B with the benchmark and quality
  results, or leave explicit failure evidence if a promotion candidate fails.
- Update the operator demo path to use GPU profiles:
  - preprocessing: `ppstructurev3@gpu`
  - extraction: `ollama@gpu` or the `full-workstation` preset once it expands
    to the desired GPU-backed profile set
  - no CPU fallback in demo commands
- Document the promotion decision:
  - keep skip-fallback opt-in by default, or
  - promote skip-fallback to default only after the two-metric quality gate
    passes and legacy behavior remains explicitly selectable.

Explicitly out of scope:

- Removing CPU/stub test paths from CI. CPU/stub paths remain the default
  safety net for fast contract and unit validation.
- Deleting `ppstructurev3@cpu` or making it impossible to run. The operational
  demo may be GPU-only, but the implementation should preserve CPU/stub
  profiles unless a separate architecture change is approved.
- Changing canonical artifact schemas or filenames.
- Introducing remote cloud-provider execution or credentials.
- Implementing Jetson `edge-fast` GPU validation.
- Adding recurring over-time surveillance for
  `evidence_gate_suppressed_fallback_count`; feature 020 explicitly defers that
  to a later ops feature.
- Regenerating committed corpus baselines from GPU output unless a separate
  contract decision accepts GPU output as the new canonical baseline.

## Requirements

### GPU Readiness Requirements

1. The feature MUST run Paddle GPU preflight before any benchmark or demo run.
2. A GPU promotion run MUST stop if preflight does not return
   `ppstructurev3_init_succeeded`.
3. The selected interpreter path MUST be visible in logs or run notes so it is
   clear whether `.venv-paddle-rocm` or another GPU-capable environment was
   used.
4. Host Ollama GPU readiness MUST be verified independently of Paddle GPU
   readiness. Ollama GPU success does not prove Paddle GPU success, and Paddle
   GPU success does not prove extractor model placement.
5. Selecting a GPU profile MUST fail fast when GPU prerequisites are missing;
   it MUST NOT silently run the CPU profile.

### Benchmark Requirements

1. The benchmark MUST use the same document subset for legacy and candidate
   runs.
2. The benchmark MUST run legacy default and skip-fallback candidate twice
   each after warmup; the first run in each pair is treated as warm-in and the
   second run is the comparison point.
3. The benchmark MUST capture per-document gate decisions,
   `evidence_gate_state_counts`, `evidence_gate_suppressed_fallback_count`,
   `ocr_only_fallback_count`, and `preprocess_strategy_id`.
4. For suppressed documents, only `per_page_inference` (the top-level per-doc
   sibling of `phase_timings` on each `per_document[i]` record, NOT a
   `phase_timings.*` child key) and `phase_timings.total` are expected to
   decrease materially. Other `phase_timings.*` keys should stay constant
   within the measured jitter band.
5. When skip-fallback suppresses every document in a run and `--gpu-warmup` is
   not set, PPStructureV3 SHOULD remain lazily unconstructed for that run.
6. When `--gpu-warmup` is set, PPStructureV3 MAY be constructed even if every
   document is later suppressed; that is the explicit operator trade-off of the
   warmup flag.

### Quality-Gate Requirements

1. The promotion candidate MUST NOT reduce aggregate vendor-identity scoring
   relative to the legacy default on the benchmark subset.
2. The promotion candidate MUST NOT reduce per-document pass count relative to
   the legacy default on the benchmark subset.
3. If either metric regresses, skip-fallback MUST remain opt-in and the
   regression evidence MUST be recorded.
4. If both metrics pass, the team MAY choose to promote skip-fallback to the
   default. Promotion is a decision, not an automatic test side effect.
5. If skip-fallback is promoted, an explicit-off path MUST remain available and
   tested so legacy behavior can still be selected.

### Demo Requirements

1. The demo runbook MUST start with GPU readiness checks:
   - Paddle preflight
   - host Ollama GPU placement
2. The demo commands MUST use GPU profiles and a GPU-capable interpreter.
3. The demo MUST show the feature-020 observability fields in `run_summary`:
   - `schema_version`
   - `preprocess_lane`
   - `preprocess_strategy_id`
   - `evidence_gate_id`
   - `evidence_gate_state_counts`
   - `evidence_gate_documents`
   - `evidence_gate_suppressed_fallback_count`
4. The demo MUST show whether suppression occurred and whether fallback counts
   remained correct.
5. The demo MUST avoid writing into committed corpus folders unless the command
   is intentionally a baseline-regeneration command. Use scratch copies under
   `/tmp` for demo and benchmark runs.

## Success Criteria

1. GPU preflight passes on the workstation environment used for the demo.
2. Host Ollama reports GPU-backed model placement for the extraction lane.
3. The GPU preprocessing lane writes a schema-valid `preprocess_output.json`
   with a GPU lane marker in run metadata or pipeline version.
4. The feature-020 GPU skip-fallback tests are real checks rather than inert
   placeholders, or their remaining deferral is explicitly justified by a
   hardware blocker.
5. The fixed five-document benchmark produces recorded Appendix A numbers.
6. The two-metric quality gate produces a recorded Appendix B verdict.
7. The MVP demo runbook uses GPU profiles and fail-fast readiness checks.
8. A documented decision states whether skip-fallback remains opt-in or is
   promoted to default.
9. CPU/stub CI remains available and green; GPU-only operational posture does
   not remove the fast safety net.

## Risks and Mitigations

- **ROCm environment drift.** WSL, ROCm, Paddle, and model weights can drift
  independently. Mitigation: preflight is mandatory and records the selected
  interpreter/runtime facts before benchmark runs.
- **GPU benchmark noise.** MIOpen and COMGR cache behavior can dominate first
  runs. Mitigation: use the four-run discipline and compare against measured
  jitter bands.
- **Quality regression hidden by latency gains.** Faster OCR-only acceptance
  could reduce vendor-identity accuracy. Mitigation: promotion requires both
  aggregate score and per-document pass count to be non-regressing.
- **Confusing operational GPU-only with CI GPU-only.** CI should remain
  CPU/stub safe. Mitigation: document that GPU-only applies to MVP demo and
  validation runs, not to every repository test.
- **Accidental CPU fallback.** GPU demos lose credibility if a command silently
  runs CPU. Mitigation: use explicit GPU profiles, preflight, and run-summary
  lane checks.

## Fallback

If the GPU promotion candidate fails because GPU prerequisites are unavailable
or quality metrics regress, the MVP remains valid as feature-complete but not
GPU-promoted:

- keep skip-fallback default off
- keep CPU/stub CI as the safety baseline
- keep GPU paths explicit and fail-fast
- record the failed or blocked evidence in feature-020 Appendix B
- defer GPU-only operational claims until a later promotion attempt

