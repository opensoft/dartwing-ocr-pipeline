# Determinism Checklist: OCR-Only Fast Lane For Vendor Identity

**Purpose**: Validate that requirements covering deterministic preprocessing-strategy selection, the FR-005 combined two-threshold eligibility / sufficiency check, deterministic fallback disposition, reproducible identifiers, and deterministic benchmark accounting are complete, clear, and consistent. This is a release-gate checklist.
**Created**: 2026-05-11
**Feature**: [spec.md](../spec.md)

## Preprocessing-Strategy Selection Determinism

- [x] CHK001 - Is the requirement that `preprocess_strategy_id` resolution is deterministic and re-derivable from configuration alone explicit (no wall-clock, no random seed, no model output participates)? [Completeness, Spec §FR-001, FR-004]
- [x] CHK002 - Is the rule that selection is by preset name only (closed vocabulary; no free-form module override) explicit? [Clarity, Spec §FR-001]
- [x] CHK003 - Is the constraint that two runs with the same explicit configuration produce the same `preprocess_strategy_id` value explicit and measurable? [Measurability, Spec §SC-004]
- [x] CHK004 - Is the requirement that two runs that differ on the preprocessing-strategy axis emit different `preprocess_strategy_id` values explicit and measurable? [Measurability, Spec §SC-004]

## Eligibility / Sufficiency-Check Determinism (Clarifications Q2)

- [x] CHK005 - Is the FR-005 trigger stated as a single deterministic rule (combined two-threshold check; token count AND detector-confidence aggregate both ≥ thresholds ⇒ sufficient; else fall back)? [Clarity, Spec §FR-005, Clarifications Q2]
- [x] CHK006 - Is the requirement that BOTH thresholds must hold for sufficiency (AND-semantics, not OR-semantics) explicit and unambiguous? [Clarity, Spec §FR-005, Clarifications Q2]
- [x] CHK007 - Is the prohibition on the check depending on extraction, classification, or vendor-identity model output explicit and exhaustive (covers ALL three model classes)? [Clarity, Spec §FR-005, FR-006]
- [x] CHK008 - Is "derivable from preprocessing-pass inputs alone" specified concretely (page geometry, rasterized page metadata, OCR-only detector / recognizer output) so a reviewer can audit the input set? [Clarity, Spec §FR-005, FR-006]
- [x] CHK009 - Is the constraint that the same input always yields the same disposition explicit (two runs of the same OCR-only configuration on the same input produce the same fallback decision)? [Measurability, Spec §FR-006, SC-012]
- [x] CHK010 - Is "non-whitespace token" defined precisely enough to be implementable without ambiguity (e.g., Unicode whitespace categories vs. ASCII whitespace; tokenization splits), or is the deferral to plan explicit? [Gap, Spec §FR-005]
- [x] CHK011 - Is the confidence aggregation function (mean / weighted-mean / median / other) explicitly deferred to `/speckit.plan` with the constraint that the choice MUST be deterministic? [Clarity, Spec §FR-005, Assumptions]
- [x] CHK012 - Is the rule for empty / zero-detection inputs (no OCR boxes ⇒ confidence aggregate undefined) defined, or is the deferral to plan explicit (candidate: treat as sufficiency-fail)? [Gap, Spec §FR-005]
- [x] CHK013 - Is the targeted region for the eligibility check the same region the OCR-only pass actually processed (so the check is computed on the actual processed region, not a different region)? [Consistency, Spec §FR-005]

## Fallback Disposition Determinism

- [x] CHK014 - Is the fallback action stated as a single deterministic rule (fall back to `ppstructurev3` on that document; emit `ppstructurev3` `preprocess_output.json`; increment `ocr_only_fallback_count`)? [Clarity, Spec §FR-005, FR-007]
- [x] CHK015 - Is the fallback granularity unambiguous ("on that document" — not per-page, not per-corpus)? [Clarity, Spec §FR-005, Edge Cases]
- [x] CHK016 - Is the prohibition on partial-output retention explicit (partial OCR-only output for that document is discarded; `ppstructurev3` output replaces it), or is the deferral to plan explicit? [Gap, Spec §FR-005]
- [x] CHK017 - Is the trigger evaluation point (after OCR-only preprocessing completes; before falling back) explicit so reviewers can verify it does not run mid-pipeline? [Clarity, Spec §FR-005]
- [x] CHK018 - Is the prohibition on silent blank output explicit alongside the prohibition on fail-fast in the fallback scenario? [Completeness, Spec §FR-005, Edge Cases]

## Identifier Reproducibility (FR-008 / FR-010)

- [x] CHK019 - Is the requirement that two runs with the same `preprocess_strategy_id` configuration on the same input produce the same identifier value explicit? [Measurability, Spec §SC-004]
- [x] CHK020 - Is the requirement that two runs that differ on `preprocess_strategy_id` produce different identifier values explicit? [Measurability, Spec §SC-004]
- [x] CHK021 - Is the always-emit policy for `preprocess_strategy_id` explicit on every run kind (gpu / cpu / stub) so absence ⇒ regression signal (FR-010)? [Completeness, Spec §FR-010]
- [x] CHK022 - Is the requirement that identifier values are stable across process restarts and across hosts (no host-specific tokens, no PIDs) explicit, or is it implied by "human-readable string"? [Gap, Spec §FR-008]

## ocr_only_fallback_count Determinism

- [x] CHK023 - Is the requirement that two runs of the same configuration on the same corpus subset produce the same `ocr_only_fallback_count` value explicit or implied? [Measurability, Spec §FR-007]
- [x] CHK024 - Is the always-emit-with-default-0 rule on non-OCR-only runs (`ppstructurev3`, `ppstructurev3@cpu`, stub-adapter) deterministic and unambiguous? [Clarity, Spec §FR-007]
- [x] CHK025 - Is the counter's increment rule (one increment per document whose OCR-only check tripped — not per threshold, not per page) explicit? [Clarity, Spec §FR-007, Key Entities]

## Benchmark Reproducibility (FR-015 / FR-017)

- [x] CHK026 - Is the requirement that the same fixed small corpus subset is used for the OCR-only candidate and the `ppstructurev3` baseline explicit? [Completeness, Spec §FR-015]
- [x] CHK027 - Is the requirement that the benchmark records per-document `phase_timings.*` (not just aggregate) explicit so re-derivation is possible from research artifacts? [Completeness, Spec §FR-015, FR-017]
- [x] CHK028 - Is the requirement that the benchmark records the candidate's `preprocess_strategy_id` value alongside the numbers explicit (and any active `(raster_profile_id, region_strategy_id)` pair from feature 018)? [Completeness, Spec §FR-017]
- [x] CHK029 - Is the rule for handling fallen-back documents in the benchmark (counted in the cell; contributing to that cell's timings and quality numbers) explicit, or is the deferral to plan explicit? [Gap, Spec §FR-015]
- [x] CHK030 - Is the corpus subset's identity (which `inv_*` folders) deferred to `/speckit.plan` with the constraint that it match feature 018's four-corner subset where possible? [Clarity, Spec §Assumptions]

## Process- and Engine-Level Determinism Carry-Forward

- [x] CHK031 - Is the carry-forward of feature 015 FR-001 (PPStructureV3 constructed exactly once per process *when invoked*) explicit, including the explicit exception that the engine MAY remain unconstructed under `preprocess_strategy_id = ocr-only-v1` runs? [Consistency, Spec §FR-022]
- [x] CHK032 - Is the carry-forward of feature 015 FR-004 (GPU readiness probed at most once per process) explicit and untouched by the new preprocess-strategy axis? [Consistency, Spec §FR-022]
- [x] CHK033 - Is the carry-forward of feature 015 FR-006 (single-device-per-process guard) explicit and untouched? [Consistency, Spec §FR-022]
- [x] CHK034 - Is the carry-forward of feature 016 warmup determinism explicit and untouched? [Consistency, Spec §FR-022]
- [x] CHK035 - Is the carry-forward of feature 018 region-strategy determinism (`region_strategy_fallback_count` semantics, header-first-v1 page-coverage rule) explicit and untouched by the OCR-only axis? [Consistency, Spec §FR-022, FR-026]

## Notes

- Items test the determinism *guarantees* the spec makes, not the implementation that delivers them.
- The closed-vocabulary contract (FR-001 — no free-form module override) is itself a determinism property: it eliminates an unbounded input space from runtime configuration.
- The FR-005 trigger is a *combined* two-threshold rule (AND-semantics); CHK005–CHK013 deserve close review at planning time when the threshold numerics and confidence aggregation function are fixed.
