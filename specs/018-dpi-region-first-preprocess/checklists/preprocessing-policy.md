# Preprocessing-Policy Checklist: DPI Reduction And Region-First Vendor Identity Preprocess

**Purpose**: Validate that requirements covering the DPI-preset and region-strategy preset surfaces, the closed vocabularies, the FR-016 promotion gate, the legacy-preservation invariant, and the operator-visibility surface for both new policy axes are complete, clear, and consistent. This is a release-gate checklist.
**Created**: 2026-05-10
**Feature**: [spec.md](../spec.md)

## DPI Preset Surface (FR-001 / FR-002 / FR-003)

- [x] CHK001 - Is the DPI preset selector requirement explicit (preset-name only; no free-form numeric DPI knob on the runtime path)? [Completeness, Spec §FR-001]
- [x] CHK002 - Are the at-landing presets bounded (`legacy` + at least one reduced preset, e.g., `reduced-v1`)? [Completeness, Spec §FR-001]
- [x] CHK003 - Is "legacy preset = the rasterization DPI active on `main` at landing time of feature 017" defined precisely enough to fix `legacy`'s numeric value? [Clarity, Spec §FR-001, Assumptions]
- [x] CHK004 - Is the rule "adding a future preset is a code change plus a new `raster_profile_id` value" explicit so a runtime numeric override cannot slip in? [Clarity, Spec §FR-001]
- [x] CHK005 - Is the prohibition on changing `preprocess_output.json` field shape under the reduced preset explicit (modulo rounding tolerance)? [Completeness, Spec §FR-002]
- [x] CHK006 - Is the requirement that the legacy DPI preset MUST remain a valid selection explicit (can never be removed)? [Completeness, Spec §FR-003, FR-018]

## Region-Strategy Preset Surface (FR-004 / FR-005 / FR-006)

- [x] CHK007 - Is the region-strategy preset selector requirement explicit (preset-name only; no free-form region coordinates on the runtime path)? [Completeness, Spec §FR-004]
- [x] CHK008 - Are the at-landing presets bounded (`full-page` + at least one region-first preset, e.g., `header-first-v1`)? [Completeness, Spec §FR-004]
- [x] CHK009 - Is "`full-page` preset = the legacy strategy active on `main` at landing time of feature 017" defined precisely enough to fix what `full-page` does? [Clarity, Spec §FR-004, Assumptions]
- [x] CHK010 - Is the rule "adding a future preset is a code change plus a new `region_strategy_id` value" explicit so a runtime per-run coordinate override cannot slip in? [Clarity, Spec §FR-004]
- [x] CHK011 - Is the requirement that targeting decisions be deterministic and re-derivable from inputs alone (FR-006) cross-referenced from the region-strategy preset Key Entity? [Consistency, Spec §FR-006, Key Entities]
- [x] CHK012 - Is the requirement that the `full-page` preset MUST remain a valid selection explicit (can never be removed)? [Completeness, Spec §FR-018]
- [x] CHK013 - Is the multi-page page-coverage rule for `header-first-v1`-class presets (page 1 only; pages 2..N empty records; `pages.length == page_count` invariant) cross-referenced into the Key Entities entry so reviewers reading just the entity definition see it? [Consistency, Spec §Key Entities, Clarifications Q2]
- [x] CHK014 - Is the exact heuristic and header band proportion for `header-first-v1` deferred to `/speckit.plan` explicitly (with the constraint that it MUST satisfy FR-006)? [Clarity, Spec §Assumptions]

## Four-Corner Benchmark Discipline (FR-005)

- [x] CHK015 - Is the four-corner matrix enumerated by name (legacy DPI × full-page, reduced DPI × full-page, legacy DPI × region-first, reduced DPI × region-first)? [Completeness, Spec §FR-005]
- [x] CHK016 - Is the requirement that the same fixed corpus subset is used for every cell explicit? [Completeness, Spec §FR-005]
- [x] CHK017 - Is the requirement that BOTH per-document `phase_timings.*` and the existing evaluator's vendor-identity quality numbers be recorded for each cell explicit? [Completeness, Spec §FR-005]
- [x] CHK018 - Is the requirement that the cell's `(raster_profile_id, region_strategy_id)` pair be recorded alongside its numbers in the research artifact explicit? [Completeness, Spec §FR-017]
- [x] CHK019 - Is the rule for crossing the cell more than once (cell is `(reduced-v1, header-first-v1)`, run twice on the same subset) defined, or is the deferral to plan explicit? [Gap, Spec §FR-005]
- [x] CHK020 - Is the corpus subset's identity (which `inv_*` folders) deferred to `/speckit.plan` with the constraint that it match feature 017's subset where possible? [Clarity, Spec §Assumptions]

## Promotion Gate (FR-016 / FR-017 / FR-018)

- [x] CHK021 - Are the TWO quality-gate metrics enumerated by name and source (per-corpus aggregate vendor-identity field score from `evaluation_run_summary.json`; per-document pass count per `docs/stage1-vendor-identity/scoring.md`)? [Completeness, Spec §FR-016]
- [x] CHK022 - Is "parity" defined precisely as `candidate_metric >= legacy_metric` for BOTH metrics? [Clarity, Spec §FR-016]
- [x] CHK023 - Is the rule that BOTH metrics must pass (not just one, not weighted average) explicit? [Clarity, Spec §FR-016]
- [x] CHK024 - Is the requirement that no new metric is introduced by this feature explicit (gate uses only existing evaluator outputs)? [Completeness, Spec §FR-016]
- [x] CHK025 - Is the relationship to feature 017 FR-015 (promotion-gate precedent) explicit? [Traceability, Spec §FR-016]
- [x] CHK026 - Is the requirement that quality-gate evidence be recorded in `research.md` alongside the candidate's identifier pair explicit? [Completeness, Spec §FR-017]
- [x] CHK027 - Is the requirement that promotion MUST NOT remove the legacy `(raster_profile_id, region_strategy_id)` configuration as a selectable option explicit? [Completeness, Spec §FR-018]
- [x] CHK028 - Is the per-axis promotion granularity defined (can the team promote a new DPI default while keeping the legacy region strategy as default)? [Gap, Spec §FR-016, FR-017]
- [x] CHK029 - Is the rule for promoting a *combined* `(reduced-v1, header-first-v1)` candidate explicit (gate is computed on the combined cell, not on each axis independently)? [Clarity, Spec §FR-016]

## Operator Visibility on Both Policy Axes (FR-008 / FR-011)

- [x] CHK030 - Is the always-emit policy explicit for `raster_profile_id` and `region_strategy_id` on every run (gpu / cpu / stub) so absence ⇒ regression? [Completeness, Spec §FR-008, FR-011]
- [x] CHK031 - Is the human-readable-string requirement (not opaque numeric hash) explicit for both fields? [Clarity, Spec §FR-008]
- [x] CHK032 - Are the CPU-default values for both fields specified, or is the deferral to plan explicit (candidate `cpu-default`)? [Gap, Spec §FR-011, Assumptions]
- [x] CHK033 - Is the requirement that two runs that differ on a single policy axis emit different identifier values on that axis (and same on the other) explicit and measurable? [Measurability, Spec §SC-004]
- [x] CHK034 - Is the coexistence rule with feature 017's `module_set_id` / `det_rec_variant_id` (no overlap; no replacement) explicit? [Consistency, Spec §Key Entities]

## Fallback Visibility (FR-009 / Clarifications Q4)

- [x] CHK035 - Is the `region_strategy_fallback_count` field type (integer), default (`0`), and unit ("number of documents that fell back in this run") explicit? [Completeness, Spec §FR-009, Clarifications Q4]
- [x] CHK036 - Is the always-emit-on-non-region-runs policy explicit (fallback counter emits `0` on full-page / cpu-default / stub runs)? [Completeness, Spec §FR-009, Clarifications Q4]
- [x] CHK037 - Is the prohibition on the fallback counter appearing inside `preprocess_output.json` explicit? [Completeness, Spec §FR-009, FR-020]
- [x] CHK038 - Is the per-document attribution recoverable from `pages[]` shape derivation rule documented so operators don't have to read source? [Clarity, Spec §FR-009, Clarifications Q4]

## Boundaries with Adjacent Features

- [x] CHK039 - Is the boundary with feature 017 (`module_set_id` / `det_rec_variant_id` / `ppstructure_modules_invoked` semantics unchanged) explicit so this feature can't quietly re-shape feature 017's surface? [Completeness, Spec §FR-022, Out of Scope]
- [x] CHK040 - Is the boundary with feature 019 (OCR-only fast lane reserved for 019; this feature's region-first still runs the existing PPStructureV3 module set on the targeted region) explicit? [Completeness, Spec §FR-026, Out of Scope]
- [x] CHK041 - Is the boundary "this feature is GPU-side only — CPU defaults stay as they are" explicit, so promotion-gate decisions cannot accidentally flip a CPU default? [Completeness, Spec §Out of Scope]

## Cross-Section Consistency

- [x] CHK042 - Are FR-001 (DPI selector) and FR-004 (region selector) symmetric in shape (same activation pattern; same closed-vocabulary contract; same prohibition on free-form runtime overrides)? [Consistency, Spec §FR-001, FR-004]
- [x] CHK043 - Are the Key Entities entries for "Rasterization-DPI preset" and "Region strategy preset" consistent with FR-001 / FR-004 on closed vocabularies? [Consistency, Spec §Key Entities, FR-001, FR-004]
- [x] CHK044 - Are the Assumptions section entries on DPI numerics, region-first heuristic, and CPU-default identifier strings all consistently deferred to `/speckit.plan` (not to `/speckit.clarify`)? [Consistency, Spec §Assumptions]
- [x] CHK045 - Is the FR-021 escape hatch (new persisted benchmark artifact only if `run_summary` + harness/evaluator outputs prove insufficient) consistent with the assumption (Assumptions §9) that no new persisted benchmark artifact is needed at landing? [Consistency, Spec §FR-021, Assumptions]

## Notes

- Items test that the spec's preprocessing-policy text — DPI presets, region presets, promotion gating, and operator visibility for both — is complete/clear/consistent.
- The two policy axes (DPI and region strategy) are deliberately symmetric in shape; CHK042–CHK043 catch asymmetries that would surprise operators or planners.
