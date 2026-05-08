## 1. Preconditions

- [ ] 1.1 Complete feature 019 and record the decision to promote, conditionally promote, revise, or discard the OCR-only fast lane.
- [ ] 1.2 Capture the feature 019 OCR evidence strategy, quality gates, and known failure modes as the starting contract for Jetson preprocessing.
- [ ] 1.3 Confirm the first Jetson target details: hardware class, JetPack/OS version, Python environment, OCR package path, Ollama install path, and expected Gemma 4 E2B model tag.

## 2. Speckit Feature 020: Jetson Edge Runtime Preflight

- [ ] 2.1 From a clean `main` checkout, create Speckit feature `020-jetson-edge-runtime-preflight`.
- [ ] 2.2 Specify a Jetson preflight command/module that classifies runtime readiness before artifact writes.
- [ ] 2.3 Include readiness states for missing Jetson runtime, missing OCR dependency, OCR GPU unavailable, Jetson-local Ollama unreachable, selected edge model unavailable, and ready.
- [ ] 2.4 Require default tests to remain non-Jetson-safe and live Jetson tests to be opt-in or skipped with actionable reasons.
- [ ] 2.5 Land and verify feature 020 before starting live adapter work.

## 3. Speckit Feature 021: Edge OCR Jetson Preprocessing

- [ ] 3.1 From a clean `main` checkout after 020 lands, create Speckit feature `021-edge-ocr-jetson-preprocessing`.
- [ ] 3.2 Replace the deferred `edge-ocr@jetson` preprocessing adapter with a live adapter based on the accepted or revised feature 019 fast-lane strategy.
- [ ] 3.3 Preserve the canonical `preprocess_output.json` schema and filename while making the selected `edge-ocr@jetson` profile visible in metadata or profile/version strings.
- [ ] 3.4 Enforce truthful evidence: do not fabricate layout blocks or tables when the lightweight OCR path does not observe them.
- [ ] 3.5 Enforce no CPU-only heavy OCR fallback; GPU fallback is allowed only when it runs on the Jetson GPU lane and is recorded in metadata.

## 4. Speckit Feature 022: Ollama Jetson Extraction

- [ ] 4.1 From a clean `main` checkout after 021 lands, create Speckit feature `022-ollama-jetson-extraction`.
- [ ] 4.2 Replace the deferred `ollama@jetson` extraction adapter with a live adapter using the existing Jetson endpoint resolution surface.
- [ ] 4.3 Pin the edge voter configuration to the selected Gemma 4 E2B model tag or documented Jetson-compatible equivalent.
- [ ] 4.4 Reuse the existing extraction schema, evidence grounding, model-response parsing, and deterministic provenance rules.
- [ ] 4.5 Fail before writing `edge_extraction_output.json` when the Jetson endpoint, GPU path, or configured edge model is unavailable.

## 5. Speckit Feature 023: Edge-Fast Harness Validation

- [ ] 5.1 From a clean `main` checkout after 022 lands, create Speckit feature `023-edge-fast-harness-validation`.
- [ ] 5.2 Run `--stack-preset edge-fast` end to end for at least one committed corpus document on Jetson hardware.
- [ ] 5.3 Run evaluator `--run-pipeline --stack-preset edge-fast` through the existing subprocess boundary without importing pipeline runtime modules.
- [ ] 5.4 Compare `edge-fast` against `full-workstation` using explicit run namespaces or copied folders, never two competing canonical artifact sets in one normal document folder.
- [ ] 5.5 Report pass/fail, review routing, challenge-tag regressions, and timing metadata separately for `edge-fast`.

## 6. Documentation And Closure

- [ ] 6.1 Update `docs/stage1-vendor-identity/architecture.md` with the live Jetson edge-fast behavior and fallback policy.
- [ ] 6.2 Update `docs/stage1-vendor-identity/ollama-runtime.md` with the Jetson-local endpoint, model setup, and operator preflight workflow.
- [ ] 6.3 Add a post-019 decision note or cross-reference documenting why the chosen fast-lane strategy is acceptable or experimental on Jetson.
- [ ] 6.4 Archive this OpenSpec change only after the corresponding Speckit features and reviews land.
