# Contract Preservation Checklist: DPI Reduction And Region-First Vendor Identity Preprocess

**Purpose**: Validate that requirements protecting the four canonical stage 1 artifact schemas, the active contract set, `pipeline_version`, `phase_timings`, and the additive-only `run_summary` surface are complete, clear, and consistent. This is a release-gate checklist.
**Created**: 2026-05-10
**Feature**: [spec.md](../spec.md)

## Schema Preservation (preprocess_output.json + four canonical artifacts)

- [x] CHK001 - Are all four canonical stage 1 artifact schemas (`preprocess_output`, `edge_extraction_output`, `routing_decision`, `final_structured_payload`) explicitly named as immutable by this feature? [Completeness, Spec §FR-020]
- [x] CHK002 - Is the prohibition on adding, removing, renaming, or retyping any field in `preprocess_output.json` reasserted for BOTH the reduced-DPI preset and EVERY region-strategy preset (including header-first fallback path)? [Clarity, Spec §FR-002, FR-010]
- [x] CHK003 - Is `contract_set_version` immutability explicitly required? [Completeness, Spec §FR-020]
- [x] CHK004 - Is the prohibition on touching `contracts/stage1_vendor_identity/AMENDMENTS.md` for this feature explicit (except via the FR-021 escape hatch)? [Completeness, Spec §FR-021, SC-011]
- [x] CHK005 - Is `schema_version` (and which artifact carries it) named so the SC-011 verification is unambiguous? [Clarity, Spec §SC-011]
- [x] CHK006 - Is the verification mechanism for SC-011 (`git diff main -- contracts/stage1_vendor_identity/`) executable as written? [Measurability, Spec §SC-011]
- [x] CHK007 - Is the requirement that coordinate origin, units, page index, and block index in `preprocess_output.json` stay identical to the legacy DPI run (modulo rounding tolerance) explicit for the reduced-DPI preset? [Completeness, Spec §FR-002]
- [x] CHK008 - Is "modulo numerical rasterization differences within rounding tolerance" defined precisely enough for the planner to fix the tolerance, or is the deferral to `/speckit.plan` explicit? [Gap, Spec §FR-002]

## pages[] Invariant for Region-First Strategy

- [x] CHK009 - Is the `pages.length == page_count` invariant explicit for the `header-first-v1`-class preset on multi-page invoices? [Completeness, Spec §Edge Cases, Clarifications Q2]
- [x] CHK010 - Are the required fields on empty page records (`page_number`, `width`, `height`, `rotation_detected` derived from PDF; `blocks: []`, `raw_ocr_lines: []`) enumerated so the planner can implement them without guessing? [Clarity, Spec §Edge Cases, Clarifications Q2]
- [x] CHK011 - Is the prohibition on rasterizing or sending pages 2..N to inference under the header-first preset explicit? [Completeness, Spec §Edge Cases, Clarifications Q2]
- [x] CHK012 - Is the constraint that pages 2..N empty records still satisfy `width >= 1` / `height >= 1` (per the existing schema's `minimum: 1`) explicit, or is the derivation-from-PDF-geometry rule sufficient to guarantee it? [Clarity, Spec §Edge Cases]
- [x] CHK013 - Is the per-page `phase_timings` accounting for skipped pages 2..N specified, or is the deferral to plan explicit? [Gap]

## Phase Timings & Pipeline Version Invariants

- [x] CHK014 - Are all eight `phase_timings.*` keys (`paddle_import`, `gpu_bind_probe`, `engine_init`, `rasterization`, `per_page_inference`, `artifact_write`, `total`, `warmup`) explicitly named as immutable in shape by this feature? [Completeness, Spec §Edge Cases, FR-022]
- [x] CHK015 - Is the prohibition on this feature changing `phase_timings` shape stated identically to feature 015/016/017 phrasing (renaming, removing, retyping)? [Consistency, Spec §Edge Cases]
- [x] CHK016 - Is `pipeline_version`'s `.gpu0` / `.cpu0` suffix pattern explicitly preserved across all preset combinations introduced by this feature? [Clarity, Spec §FR-022, SC-010]
- [x] CHK017 - Is "pipeline_version shape established in features 014/015/016/017" defined precisely enough to verify "unchanged"? [Measurability, Spec §FR-020, FR-022]
- [x] CHK018 - Is the `phase_timings.rasterization` accounting for fallen-back documents specified (combined region-first attempt + full-page time vs. final full-page only), or is the deferral to plan explicit? [Gap]

## run_summary Additive-Only Surface

- [x] CHK019 - Are the three new `run_summary` fields enumerated by name (`raster_profile_id`, `region_strategy_id`, `region_strategy_fallback_count`) and is no other new field implied? [Completeness, Spec §FR-008, FR-009, FR-010]
- [x] CHK020 - Are the data types of the three new `run_summary` fields specified (string, string, integer)? [Completeness, Spec §FR-008, FR-009]
- [x] CHK021 - Is the boundary between "additive on `run_summary` (allowed)" and "additive on `preprocess_output.json` (forbidden)" explicit for ALL three new fields, especially `region_strategy_fallback_count`? [Clarity, Spec §FR-009, FR-010, FR-020]
- [x] CHK022 - Is the prohibition on renaming, removing, or retyping any existing `run_summary` field explicit, including feature 017's `module_set_id` / `det_rec_variant_id` / `ppstructure_modules_invoked`? [Completeness, Spec §FR-010, FR-022]
- [x] CHK023 - Are JSON serialization properties (key ordering, whitespace, trailing newline) for `run_summary` specified, or is non-specification intentional and consistent with feature 017's stance? [Gap]
- [x] CHK024 - Is the position/ordering of new `run_summary` fields specified, or is order-agnosticism explicit? [Gap]
- [x] CHK025 - Does the spec define what counts as a "field rename" vs. a "field addition" so reviewers can apply FR-010 unambiguously? [Clarity, Gap]
- [x] CHK026 - Is the always-emit policy (FR-009 / FR-011 / Clarifications Q4) explicit for ALL THREE new fields on ALL run kinds (gpu / cpu / stub) so absence ⇒ regression signal? [Consistency, Spec §FR-011, Clarifications Q4]

## raster_profile_id / region_strategy_id Vocabularies

- [x] CHK027 - Is the closed vocabulary for `raster_profile_id` at landing explicitly bounded (`legacy`, at least one reduced preset like `reduced-v1`, plus a CPU/stub default value)? [Completeness, Spec §FR-001, FR-011]
- [x] CHK028 - Is the closed vocabulary for `region_strategy_id` at landing explicitly bounded (`full-page`, at least one region-first preset like `header-first-v1`, plus a CPU/stub default value)? [Completeness, Spec §FR-004, FR-011]
- [x] CHK029 - Are CPU-default and stub-adapter values for `raster_profile_id` and `region_strategy_id` specified, or is the deferral to plan explicit (candidates: `cpu-default`)? [Gap, Spec §FR-011, Assumptions]
- [x] CHK030 - Is the prohibition on free-form numeric DPI overrides on the runtime path (FR-001) and free-form region coordinates on the runtime path (FR-004) reasserted in BOTH FR and Key Entities so reviewers can spot a runtime knob slipping in? [Consistency, Spec §FR-001, FR-004, Key Entities]
- [x] CHK031 - Is "adding a future preset is a code change plus a new identifier value" explicit so the closed-vocabulary contract is unambiguous? [Clarity, Spec §FR-001, FR-004]
- [x] CHK032 - Is the human-readable-string requirement (not opaque numeric hashes) reasserted for `raster_profile_id` and `region_strategy_id`? [Clarity, Spec §FR-008]

## region_strategy_fallback_count Semantics

- [x] CHK033 - Is the unit of `region_strategy_fallback_count` ("number of documents that fell back in this run") explicit and unambiguous (not pages, not page-document pairs)? [Clarity, Spec §FR-009, Clarifications Q4]
- [x] CHK034 - Is the default value (`0`) on `full-page`, `ppstructurev3@cpu`, and stub-adapter runs explicit? [Completeness, Spec §FR-009, Clarifications Q4]
- [x] CHK035 - Is the "per-document attribution recoverable from `pages[]` shape" derivation rule (full-length populated `pages[]` ⇒ fallback fired; pages 2..N empty ⇒ clean region-first run) documented so operators can apply it without extra tooling? [Clarity, Spec §FR-009, Clarifications Q4]
- [x] CHK036 - Is the relationship between `region_strategy_fallback_count` and `region_strategy_id` defined (fallback counter is meaningful only when `region_strategy_id != full-page` and != CPU-default)? [Consistency, Spec §FR-009]

## Downstream Contract Preservation

- [x] CHK037 - Are the four downstream consumers (evidence-packet 004, extract 005, router 008, assembler 009, evaluator 007) explicitly listed as needing to accept new GPU outputs unmodified across all evaluated DPI × region combinations? [Completeness, Spec §FR-022, US5]
- [x] CHK038 - Is "downstream consumer accepts without modification" measurable (existing schema validates; no downstream code change) per SC-008? [Measurability, Spec §SC-008]
- [x] CHK039 - Is the requirement that empty page records (pages 2..N under header-first) flow through evidence-packet → extract → route → assemble → evaluate without contract changes explicit? [Coverage, Spec §SC-008, Clarifications Q2]
- [x] CHK040 - Is the verification mechanism for SC-008 (end-to-end small-corpus pipeline run with schema validation at each stage) testable as written? [Measurability]

## FR-021 Benchmark Artifact Escape Hatch

- [x] CHK041 - Is the FR-021 escape hatch (introducing a new persisted benchmark artifact) precisely conditioned on `/speckit.clarify` or `/speckit.plan` evidence that `run_summary` + harness/evaluator outputs are insufficient? [Clarity, Spec §FR-021]
- [x] CHK042 - If the escape hatch is taken, are the required deliverables (data-model.md + research.md + AMENDMENTS update) enumerated? [Completeness, Spec §FR-021]
- [x] CHK043 - Is the default position (no new persisted benchmark artifact at landing) consistent between FR-021, the Out of Scope subsection, and Assumptions? [Consistency]

## Corpus Baseline Immutability

- [x] CHK044 - Are committed corpus baselines under `tests/stage1_vendor_identity/*/` named as off-limits to this feature? [Completeness, Spec §FR-019, SC-007]
- [x] CHK045 - Is the legitimate channel for baseline regeneration named (`docs/stage1-vendor-identity/dataset-layout.md` + `labeling-guide.md` flow)? [Clarity, Spec §FR-019]
- [x] CHK046 - Is the verification mechanism for SC-007 (PR diff against `main` on baseline paths) executable as written? [Measurability, Spec §SC-007]

## Feature 014 / 015 / 016 / 017 Guarantee Carry-Forward

- [x] CHK047 - Does FR-022 enumerate the carried-forward guarantees by FR-number (015 FR-001 single-construction, 015 FR-004 single-probe, 015 FR-006 single-device guard, 015 FR-008 no-silent-fallback, 016 FR-001..FR-020 warmup, 017 FR-001 / FR-008 / FR-010)? [Completeness, Spec §FR-022]
- [x] CHK048 - Is the carry-forward of `module_set_id` / `det_rec_variant_id` / `ppstructure_modules_invoked` shape explicit so this feature does not silently re-shape feature 017's identifier surface? [Consistency, Spec §FR-010, FR-022]

## Cross-Section Consistency

- [x] CHK049 - Are FR-020 and FR-021 consistent (both forbid contract changes) without overlap or contradiction? [Consistency]
- [x] CHK050 - Is the requirement that adding a future preset on either axis needs a new identifier value (not a runtime toggle) consistent across FR-001, FR-004, the Clarifications session, and the Key Entities entries? [Consistency, Spec §FR-001, FR-004, Key Entities]
- [x] CHK051 - Are the boundaries with feature 017 (module_set / det_rec) and feature 019 (OCR-only fast lane) named so contract-affecting scope creep is detectable? [Completeness, Spec §FR-026, Out of Scope]

## Notes

- Items intentionally test the requirements text, not the implementation. A "[ ]" item asks "is the spec clear/complete/consistent here?" not "does the code do X correctly?".
