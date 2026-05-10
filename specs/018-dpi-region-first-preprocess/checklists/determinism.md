# Determinism Checklist: DPI Reduction And Region-First Vendor Identity Preprocess

**Purpose**: Validate that requirements covering deterministic targeting, deterministic fallback triggering, reproducible identifiers, and deterministic page coverage are complete, clear, and consistent. This is a release-gate checklist.
**Created**: 2026-05-10
**Feature**: [spec.md](../spec.md)

## Region-Strategy Targeting Determinism

- [ ] CHK001 - Is the requirement that the region-first strategy's per-page or per-document targeting decisions MUST be deterministic explicit? [Completeness, Spec §FR-006]
- [ ] CHK002 - Is the prohibition on targeting decisions depending on extraction, classification, or vendor-identity model output explicit and exhaustive (covers ALL three model classes, not just extraction)? [Clarity, Spec §FR-006]
- [ ] CHK003 - Is "re-derivable from inputs alone" specified concretely (PDF page geometry, page index, layout heuristics) so a reviewer can audit the input set? [Clarity, Spec §FR-006]
- [ ] CHK004 - Is the constraint that two runs of the same strategy on the same input produce the same targeting explicit and measurable? [Measurability, Spec §FR-006]
- [ ] CHK005 - Are the inputs to the targeting decision enumerated narrowly enough that a reviewer can spot a non-deterministic input slipping in (e.g., wall-clock time, random seed, environment variable, model output)? [Coverage, Spec §FR-006]

## Page-Coverage Determinism (Q2)

- [ ] CHK006 - Is the page-coverage rule for the `header-first-v1`-class preset on multi-page invoices stated as a single deterministic rule (page 1 header band only; pages 2..N empty records)? [Clarity, Spec §Edge Cases, Clarifications Q2]
- [ ] CHK007 - Is the prohibition on page-coverage decisions depending on model output explicit (mirrors FR-006 for the page-skipping decision specifically)? [Consistency, Spec §Edge Cases, FR-006]
- [ ] CHK008 - Is the input set for the page-coverage decision (page index, PDF page geometry) enumerated so reviewers can audit determinism? [Clarity, Spec §Edge Cases, Clarifications Q2]
- [ ] CHK009 - Is the rule for single-page PDFs under the header-first preset explicit (process header band on the single page; `pages.length == 1`), or does the spec rely on the multi-page rule degenerating gracefully? [Gap, Spec §Edge Cases]
- [ ] CHK010 - Is the rule for landscape / rotated / unusual aspect-ratio PDFs explicit, or is the deferral to plan explicit? [Gap, Spec §FR-006, Assumptions]

## Fallback Trigger Determinism (Q3)

- [ ] CHK011 - Is the FR-007 trigger condition stated as a single deterministic rule (concatenation of `blocks[].text` in the targeted region on page 1, with whitespace stripped, is empty)? [Clarity, Spec §FR-007, Clarifications Q3]
- [ ] CHK012 - Is the trigger condition explicitly re-derivable from `preprocess_output.json` alone (no external state, no model output)? [Completeness, Spec §FR-007, Clarifications Q3]
- [ ] CHK013 - Is "whitespace stripped" defined precisely enough to be implementable without ambiguity (e.g., Unicode whitespace categories, or explicit deferral to plan)? [Gap, Spec §FR-007]
- [ ] CHK014 - Is the targeted region the same for the trigger check as for the original region-first preprocessing pass (so the trigger is computed on the actual targeted region, not on a different region)? [Consistency, Spec §FR-007, Clarifications Q3]
- [ ] CHK015 - Is the prohibition on "trigger condition depends on raw_ocr_lines or anything outside `blocks[].text` in the targeted region" explicit, or is it implied? [Clarity, Spec §FR-007]
- [ ] CHK016 - Is the trigger evaluation point (after region-first preprocessing completes; before falling back) explicit so reviewers can verify it does not run mid-pipeline? [Clarity, Spec §FR-007, Clarifications Q3]

## Fallback Path Determinism (Q1)

- [ ] CHK017 - Is the FR-007 fallback action stated as a single deterministic rule (fall back to full-page on that document; emit full-page-strategy `preprocess_output.json`; record on `run_summary`)? [Clarity, Spec §FR-007, Clarifications Q1]
- [ ] CHK018 - Is the prohibition on partial-output retention explicit (partial region-first output is discarded; full-page output replaces it)? [Gap, Spec §FR-007]
- [ ] CHK019 - Is the fallback granularity unambiguous ("on that document" — not per-page, not per-corpus)? [Clarity, Spec §FR-007, Clarifications Q1]
- [ ] CHK020 - Is the prohibition on silent blank output explicit alongside the prohibition on fail-fast in the fallback scenario? [Completeness, Spec §FR-007, Clarifications Q1]

## Identifier Reproducibility (FR-008 / FR-011)

- [ ] CHK021 - Is the requirement that two runs with the same `(raster_profile_id, region_strategy_id)` configuration on the same input produce the same identifier-pair value explicit? [Measurability, Spec §SC-004]
- [ ] CHK022 - Is the requirement that two runs that differ on `raster_profile_id` produce different identifier-pair values explicit? [Measurability, Spec §SC-004]
- [ ] CHK023 - Is the requirement that two runs that differ on `region_strategy_id` produce different identifier-pair values explicit? [Measurability, Spec §SC-004]
- [ ] CHK024 - Is the always-emit policy for `raster_profile_id` and `region_strategy_id` explicit on every run kind so absence ⇒ regression signal (FR-011)? [Completeness, Spec §FR-011]
- [ ] CHK025 - Is the requirement that identifier values are stable across process restarts and across hosts (no host-specific tokens, no PIDs) explicit, or is it implied by "human-readable string"? [Gap, Spec §FR-008]

## Fallback Counter Determinism (Q4)

- [ ] CHK026 - Is the requirement that two runs of the same configuration on the same corpus subset produce the same `region_strategy_fallback_count` value explicit or implied? [Measurability, Spec §FR-009, Clarifications Q4]
- [ ] CHK027 - Is the always-emit-with-default-0 rule on non-region-first runs deterministic and unambiguous? [Clarity, Spec §FR-009, Clarifications Q4]
- [ ] CHK028 - Is the relationship between `region_strategy_fallback_count == K` and "K documents had `pages[]` populated to full length" derivable from a deterministic count rule? [Consistency, Spec §FR-009, Clarifications Q4]

## Benchmark Reproducibility (FR-005 / FR-017)

- [ ] CHK029 - Is the requirement that the same fixed corpus subset is used for every cell of the four-corner matrix explicit? [Completeness, Spec §FR-005]
- [ ] CHK030 - Is the requirement that the benchmark records per-document `phase_timings.*` (not just aggregate) explicit so re-derivation is possible from research artifacts? [Completeness, Spec §FR-005, FR-017]
- [ ] CHK031 - Is the requirement that the benchmark records the `(raster_profile_id, region_strategy_id)` pair alongside the numbers explicit? [Completeness, Spec §FR-017]
- [ ] CHK032 - Is the rule for handling fallen-back documents in the benchmark (counted in the cell, contributing to that cell's timings) explicit, or is the deferral to plan explicit? [Gap, Spec §FR-005]

## Process- and Engine-Level Determinism Carry-Forward

- [ ] CHK033 - Is the carry-forward of feature 015 FR-001 (PPStructureV3 constructed exactly once per process) explicit and untouched by either new preset axis? [Consistency, Spec §FR-022]
- [ ] CHK034 - Is the carry-forward of feature 015 FR-004 (GPU readiness probed at most once per process) explicit and untouched? [Consistency, Spec §FR-022]
- [ ] CHK035 - Is the carry-forward of feature 015 FR-006 (single-device-per-process guard) explicit and untouched? [Consistency, Spec §FR-022]
- [ ] CHK036 - Is the carry-forward of feature 016 warmup determinism explicit and untouched? [Consistency, Spec §FR-022]

## Notes

- Items test the determinism *guarantees* the spec makes, not the implementation that delivers them.
- The closed-vocabulary contract (FR-001 / FR-004 — no free-form numeric DPI knob, no free-form region coordinates) is itself a determinism property: it eliminates an unbounded input space from runtime configuration.
