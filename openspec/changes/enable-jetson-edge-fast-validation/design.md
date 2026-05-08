## Context

The stage 1 controller already recognizes `edge-fast`, `edge-ocr@jetson`, and `ollama@jetson`, but live execution is intentionally deferred. Today those selections fail fast through `DeferredImplementationError`, which proves the CLI surface and no-silent-fallback behavior without requiring Jetson hardware in normal development.

Feature 019 is expected to evaluate an OCR-only fast lane on the workstation against the full PPStructureV3 baseline. Jetson work should start only after that decision records whether OCR-lines-plus-coordinates are accurate enough for vendor identity, because the Jetson edge profile should reuse or adapt that chosen fast-lane strategy rather than inventing another preprocessing shape.

The Jetson target remains stage 1 vendor identity only. It must keep the existing folder/artifact contracts, the deterministic routing/final-payload ownership, and the harness/evaluator boundary.

## Goals / Non-Goals

**Goals:**

- Turn the recognized `edge-fast` stack into a live Jetson validation path after feature 019.
- Add a Jetson preflight that classifies environment, OCR GPU viability, Ollama endpoint readiness, and model availability before artifact writes.
- Implement live `edge-ocr@jetson` preprocessing from the 019 fast-lane decision while preserving `preprocess_output.json`.
- Implement live `ollama@jetson` extraction against Jetson-local Ollama and the Gemma 4 E2B edge voter configuration.
- Keep CPU/stub default tests safe and make Jetson tests opt-in or clearly skipped when hardware is unavailable.
- Allow evaluator reports to compare `edge-fast` against `full-workstation` without changing scoring ownership.

**Non-Goals:**

- No remote cloud provider calls or cloud fallback.
- No separate repository for edge OCR.
- No change to the default `full-workstation` stack.
- No CPU-only fallback for edge OCR or Jetson model inference.
- No line-item extraction, service deployment, or multi-voter ensemble behavior.
- No required new persisted benchmark artifact.

## Decisions

### Decision 1: Gate Jetson implementation on the feature 019 fast-lane decision

Jetson implementation SHALL begin only after 019 promotes, conditionally promotes, or revises the OCR-only fast lane. The Jetson profile will reuse the selected OCR evidence strategy and quality gates from 019.

Alternatives considered:

- Implement Jetson OCR independently now: rejected because it risks creating a second evidence strategy before the workstation fast lane has been measured.
- Wait for the full cloud/workstation ensemble: rejected because edge OCR and Jetson-local extraction are separable from cloud-class voter work.

### Decision 2: Split implementation into Speckit features 020 through 023

This OpenSpec change governs one capability, but implementation should land as sequential Speckit features:

- `020-jetson-edge-runtime-preflight`
- `021-edge-ocr-jetson-preprocessing`
- `022-ollama-jetson-extraction`
- `023-edge-fast-harness-validation`

This keeps hardware preflight, preprocessing, extraction, and harness comparison independently testable while preserving one OpenSpec decision trail.

### Decision 3: Replace deferred adapters, do not add new profile names

The profile grammar and stack-preset names from feature 011 remain authoritative. Implementation will remove the relevant Jetson triples from the deferred-live set only when real adapters and preflight gates exist.

Alternatives considered:

- Add `edge-ocr@gpu` or `edge-ocr@cpu`: rejected because edge OCR is Jetson GPU-specific in stage 1 and CPU fallback is explicitly forbidden.
- Add a generic `real` profile: rejected because stage-specific lane selection is already the stable contract.

### Decision 4: Jetson preflight is mandatory before live edge artifact writes

The Jetson preflight must prove enough runtime readiness to avoid misleading artifacts:

- target OS/JetPack and Python environment are known
- OCR package and GPU path are available
- Jetson-local Ollama endpoint is reachable
- selected Gemma 4 E2B model is available
- model inference and OCR are not CPU-only fallbacks

Failures should be structured and actionable. Where the run is hardware-gated test code, absence of Jetson hardware should skip; where the user explicitly selects `edge-fast`, runtime absence should fail fast or route to review according to the stage contract.

### Decision 5: `edge-ocr@jetson` preserves schema and truthfulness over richness

The edge OCR profile must emit schema-valid `preprocess_output.json`, but it must not fabricate layout blocks or tables that the lightweight engine did not observe. Missing structure should be represented with explicit empty/typed fields and profile metadata, not invented evidence.

If 019 proves that layout-free evidence is insufficient for a subset, the Jetson profile may use a larger fallback only when that fallback also runs on the Jetson GPU lane and records the fallback in metadata.

### Decision 6: `ollama@jetson` reuses the extraction boundary with Jetson lane resolution

The Jetson extraction adapter should reuse the existing extraction orchestration and Ollama response parsing. The lane-specific behavior is endpoint/model selection plus preflight, not a new extraction contract. Gemma 4 E2B remains an evidence judge/extractor; deterministic provenance and routing remain code-owned.

### Decision 7: Comparisons remain harness/evaluator-owned

Side-by-side comparison of `edge-fast` and `full-workstation` should use explicit run namespaces or temporary corpus copies. A normal document folder still has one canonical set of four stage artifacts for the selected run.

The evaluator owns scoring, pass/fail, summary reports, and timing comparison display. The pipeline may expose run metadata but must not create a new required benchmark artifact.

## Risks / Trade-offs

- Jetson OCR package support differs from the workstation fast-lane package -> Mitigation: make preflight the first feature and document the exact supported JetPack/package path before adapter work.
- OCR-only evidence may pass easy documents but fail hard or missing-name documents -> Mitigation: require feature 019 quality-gate evidence and compare edge-fast by difficulty/challenge tag before promotion.
- Jetson-local model serving may be too slow or memory-constrained for Gemma 4 E2B -> Mitigation: model preflight and single-document smoke tests come before corpus runs.
- Runtime metadata could be insufficient to separate baseline and edge results -> Mitigation: require selected stack/profile/model/lane in run metadata or artifact-visible profile strings.
- Test suite could become hardware-dependent -> Mitigation: keep default tests CPU/stub safe and use opt-in Jetson markers for hardware tests.

## Migration Plan

1. Complete feature 019 and record the fast-lane decision.
2. Create Speckit feature `020` from `main` for Jetson preflight only.
3. After `020` lands, create `021` for live `edge-ocr@jetson` preprocessing.
4. After `021` lands, create `022` for live `ollama@jetson` extraction.
5. After `022` lands, create `023` for end-to-end `edge-fast` harness validation and baseline comparison.
6. Archive this OpenSpec change only after the corresponding Speckit work and review land.

Rollback is straightforward for each implementation slice: restore the specific profile triple to deferred-live behavior and keep the recognized CLI surface intact.

## Open Questions

- Which exact Jetson OS/JetPack/Python package combination is the first supported target?
- Which OCR package/configuration from feature 019 maps cleanly to Jetson GPU execution?
- What minimum Gemma 4 E2B model tag or quantization is acceptable for Jetson-local Ollama?
- Which corpus subset should be the first Jetson smoke set before the full 20-document run?
- What quality threshold from feature 019 is required before edge-fast can be considered for routine validation rather than experimental testing?
