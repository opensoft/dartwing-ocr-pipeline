# Preprocessing-Policy Checklist: OCR-Only Fast Lane For Vendor Identity

**Purpose**: Validate that requirements covering the OCR-only preset surface, the closed `preprocess_strategy_id` vocabulary, the FR-015 benchmark, the FR-016 promotion gate, the legacy-preservation invariant, and the operator-visibility surface for the new policy axis are complete, clear, and consistent. This is a release-gate checklist.
**Created**: 2026-05-11
**Feature**: [spec.md](../spec.md)

## OCR-Only Preset Surface (FR-001 / FR-002 / FR-003 / FR-004)

- [x] CHK001 - Is the preprocessing-strategy preset selector requirement explicit (preset-name only; no free-form per-run module override on the runtime path)? [Completeness, Spec §FR-001]
- [x] CHK002 - Are the at-landing presets bounded (`ppstructurev3` + at least one OCR-only preset like `ocr-only-v1`)? [Completeness, Spec §FR-001]
- [x] CHK003 - Is "`ppstructurev3` preset = the strategy active on `main` at landing time of feature 018" defined precisely enough to fix the preset's behavior? [Clarity, Spec §FR-001, Assumptions]
- [x] CHK004 - Is the rule "adding a future preset is a code change plus a new `preprocess_strategy_id` value" explicit so a runtime module override cannot slip in? [Clarity, Spec §FR-001]
- [x] CHK005 - Is the OCR-only preset's invocation contract explicit (PaddleOCR text-detection + text-recognition only; NO layout-detection, table-recognition, formula-recognition, or seal-recognition modules)? [Completeness, Spec §FR-002]
- [x] CHK006 - Is the prohibition on changing `preprocess_output.json` field shape under the OCR-only preset explicit (page count, page index, coordinate origin / units, block-index ordering, `pages.length == page_count` invariant all preserved)? [Completeness, Spec §FR-003]
- [x] CHK007 - Is the rule that OCR-only `blocks[]` MAY be derived from line clustering (content difference, not shape difference) explicit so the planner can implement clustering without violating the schema? [Clarity, Spec §FR-002, Edge Cases]
- [x] CHK008 - Is the requirement that the `ppstructurev3` preset MUST remain a valid selection explicit (can never be removed by this feature)? [Completeness, Spec §FR-004, FR-018]
- [x] CHK009 - Is the exact deterministic line-clustering algorithm and parameters deferred to `/speckit.plan` explicitly (with the constraint that it MUST satisfy FR-006)? [Clarity, Spec §Assumptions]

## preprocess_strategy_id Closed Vocabulary

- [x] CHK010 - Is the closed vocabulary for `preprocess_strategy_id` at landing explicitly bounded (`ppstructurev3` + at least one OCR-only preset + a CPU/stub default value)? [Completeness, Spec §FR-001, FR-010]
- [x] CHK011 - Are CPU-default and stub-adapter values for `preprocess_strategy_id` specified, or is the deferral to plan explicit (candidates: `ppstructurev3` or `cpu-default`)? [Gap, Spec §FR-010, Assumptions]
- [x] CHK012 - Is the human-readable-string requirement (not opaque numeric hash) explicit for `preprocess_strategy_id`? [Clarity, Spec §FR-008]
- [x] CHK013 - Is the OCR-only preset's canonical identifier value (e.g., `ocr-only-v1`) deferred to plan with the constraint that it MUST belong to the closed FR-001 vocabulary? [Clarity, Spec §FR-001, Assumptions]
- [x] CHK014 - Is the rule that any future preset (e.g., a future `ocr-only-v2`) needs both a code change AND a new identifier value (not a runtime toggle) explicit? [Clarity, Spec §FR-001]

## Benchmark Discipline (FR-015 / FR-017)

- [x] CHK015 - Are the benchmark cells enumerated by name (`ppstructurev3` baseline AND at least one OCR-only candidate; same fixed subset for every cell)? [Completeness, Spec §FR-015]
- [x] CHK016 - Is the requirement that the same fixed small stage 1 vendor-identity corpus subset (the one feature 018 used for its four-corner matrix) is used for every cell explicit? [Completeness, Spec §FR-015, Assumptions]
- [x] CHK017 - Is the requirement that BOTH per-document `phase_timings.*` and the existing evaluator's vendor-identity quality numbers be recorded for each cell explicit? [Completeness, Spec §FR-015]
- [x] CHK018 - Is the requirement that the cell's `preprocess_strategy_id` value (and the active `(raster_profile_id, region_strategy_id)` pair from feature 018) be recorded alongside its numbers in the research artifact explicit? [Completeness, Spec §FR-017]
- [x] CHK019 - Is the rule for handling fallen-back documents in a benchmark cell (counted in the cell; contributing to that cell's timings and quality numbers) defined, or is the deferral to plan explicit? [Gap, Spec §FR-015]
- [x] CHK020 - Is the corpus subset's identity (which `inv_*` folders) deferred to `/speckit.plan` with the constraint that it match feature 018's subset? [Clarity, Spec §Assumptions]

## Promotion Gate (FR-016 / FR-017 / FR-018)

- [x] CHK021 - Are the TWO quality-gate metrics enumerated by name and source (per-corpus aggregate vendor-identity field score from `evaluation_run_summary.json`; per-document pass count per `docs/stage1-vendor-identity/scoring.md`)? [Completeness, Spec §FR-016]
- [x] CHK022 - Is "parity" defined precisely as `candidate_metric >= legacy_metric` for BOTH metrics? [Clarity, Spec §FR-016]
- [x] CHK023 - Is the rule that BOTH metrics must pass (not just one, not a weighted average) explicit? [Clarity, Spec §FR-016]
- [x] CHK024 - Is the requirement that no new metric is introduced by this feature explicit (gate uses only existing evaluator outputs)? [Completeness, Spec §FR-016]
- [x] CHK025 - Is the relationship to feature 017 FR-015 / feature 018 FR-016 (promotion-gate precedent) explicit? [Traceability, Spec §FR-016]
- [x] CHK026 - Is the requirement that quality-gate evidence be recorded in `research.md` alongside the candidate's `preprocess_strategy_id` value explicit? [Completeness, Spec §FR-017]
- [x] CHK027 - Is the requirement that promotion MUST NOT remove the legacy `preprocess_strategy_id = ppstructurev3` configuration as a selectable option explicit? [Completeness, Spec §FR-018]
- [x] CHK028 - Is the per-axis promotion granularity defined (can the team promote a new preprocess-strategy default while keeping the legacy `raster_profile_id` / `region_strategy_id` defaults)? [Gap, Spec §FR-016, FR-017]
- [x] CHK029 - Is the rule for promoting a *combined* `(preprocess_strategy_id, raster_profile_id, region_strategy_id)` candidate explicit (gate computed on the combined cell, not per axis independently)? [Clarity, Spec §FR-016]

## Operator Visibility on the Preprocessing-Strategy Axis (FR-008 / FR-010)

- [x] CHK030 - Is the always-emit policy explicit for `preprocess_strategy_id` on every run (gpu / cpu / stub) so absence ⇒ regression? [Completeness, Spec §FR-008, FR-010]
- [x] CHK031 - Is the human-readable-string requirement (not opaque numeric hash) explicit? [Clarity, Spec §FR-008]
- [x] CHK032 - Is the requirement that two runs that differ on the preprocessing-strategy axis emit different `preprocess_strategy_id` values (and same on other axes) explicit and measurable? [Measurability, Spec §SC-004]
- [x] CHK033 - Is the coexistence rule with feature 017's `module_set_id` / `det_rec_variant_id` / `ppstructure_modules_invoked` AND feature 018's `raster_profile_id` / `region_strategy_id` / `region_strategy_fallback_count` (no overlap, no replacement) explicit? [Consistency, Spec §FR-008, Key Entities]

## Fallback Visibility (FR-007 / Clarifications Q2)

- [x] CHK034 - Is the `ocr_only_fallback_count` field type (integer), default (`0`), and unit ("number of documents that fell back in this run") explicit? [Completeness, Spec §FR-007, Key Entities]
- [x] CHK035 - Is the always-emit-on-non-OCR-only-runs policy explicit (fallback counter emits `0` on `ppstructurev3` / `ppstructurev3@cpu` / stub runs)? [Completeness, Spec §FR-007]
- [x] CHK036 - Is the prohibition on the fallback counter appearing inside `preprocess_output.json` explicit? [Completeness, Spec §FR-009, FR-020]
- [x] CHK037 - Is the rule "counter is meaningful only when `preprocess_strategy_id` selects an OCR-only preset; on other selections it emits `0`" explicit? [Consistency, Spec §FR-007]

## Boundaries with Adjacent Features

- [x] CHK038 - Is the boundary with feature 017 (`module_set_id` / `det_rec_variant_id` / `ppstructure_modules_invoked` semantics unchanged) explicit so this feature can't quietly re-shape feature 017's surface? [Completeness, Spec §FR-022, FR-027, Out of Scope]
- [x] CHK039 - Is the boundary with feature 018 (region-strategy and DPI axes compose orthogonally with the new preprocess-strategy axis; feature 018's fallback disposition unchanged) explicit per FR-026? [Completeness, Spec §FR-026]
- [x] CHK040 - Is the boundary "no new OCR engine; no non-Paddle OCR runtime; OCR-only uses the same det/rec variants as feature 017's `det_rec_variant_id`" explicit per FR-027? [Completeness, Spec §FR-027]
- [x] CHK041 - Is the boundary "this feature is GPU-side only — CPU defaults stay as they are" explicit, so promotion-gate decisions cannot accidentally flip a CPU default? [Completeness, Spec §Out of Scope]
- [x] CHK042 - Is the boundary "feature 008 deterministic routing surface unchanged; the two new identifier fields are operator-consumed, not routing inputs" explicit? [Completeness, Spec §FR-026, Out of Scope]

## Cross-Section Consistency

- [x] CHK043 - Are the Key Entities entries for "Preprocessing-strategy preset" and "OCR-only eligibility / sufficiency rule" consistent with FR-001 / FR-005 on closed vocabularies and deterministic-derivability? [Consistency, Spec §Key Entities, FR-001, FR-005]
- [x] CHK044 - Are the Assumptions section entries on confidence aggregation function, threshold values, line-clustering algorithm, preset naming, and CPU-default identifier strings all consistently deferred to `/speckit.plan` (not to `/speckit.clarify`)? [Consistency, Spec §Assumptions]
- [x] CHK045 - Is the FR-021 escape hatch (new persisted benchmark artifact only if `run_summary` + harness/evaluator outputs prove insufficient) consistent with the assumption that no new persisted benchmark artifact is needed at landing? [Consistency, Spec §FR-021, Assumptions]
- [x] CHK046 - Are FR-008 and FR-010 consistent (FR-008 defines the field; FR-010 governs always-emit on every profile)? [Consistency, Spec §FR-008, FR-010]

## Notes

- Items test that the spec's preprocessing-policy text — the OCR-only preset surface, the promotion gating, the operator visibility — is complete/clear/consistent.
- The new preprocessing-strategy axis is the third identifier axis on `run_summary` (after feature 017's module-set axis and feature 018's raster-profile + region-strategy axes); CHK033 catches asymmetries that would surprise operators or planners.
