# Contract Preservation Checklist: OCR-Only Fast Lane For Vendor Identity

**Purpose**: Validate that requirements protecting the four canonical stage 1 artifact schemas, the active contract set, `pipeline_version`, `phase_timings`, and the additive-only `run_summary` surface (now extended with `preprocess_strategy_id` and `ocr_only_fallback_count`) are complete, clear, and consistent. This is a release-gate checklist.
**Created**: 2026-05-11
**Feature**: [spec.md](../spec.md)

## Schema Preservation (preprocess_output.json + four canonical artifacts)

- [x] CHK001 - Are all four canonical stage 1 artifact schemas (`preprocess_output`, `edge_extraction_output`, `routing_decision`, `final_structured_payload`) explicitly named as immutable by this feature? [Completeness, Spec §FR-020]
- [x] CHK002 - Is the prohibition on adding, removing, renaming, or retyping any field in `preprocess_output.json` reasserted for the OCR-only preset (FR-003) AND for the fallback path's `ppstructurev3` output? [Clarity, Spec §FR-003, FR-009]
- [x] CHK003 - Is the invariant "page count, page index, coordinate origin, coordinate units, block-index ordering rules, and `pages.length == page_count`" stated identically to feature 018's contract for the OCR-only output? [Consistency, Spec §FR-003, Edge Cases]
- [x] CHK004 - Is `contract_set_version` immutability explicitly required? [Completeness, Spec §FR-020]
- [x] CHK005 - Is the prohibition on touching `contracts/stage1_vendor_identity/AMENDMENTS.md` for this feature explicit (except via the FR-021 escape hatch)? [Completeness, Spec §FR-021, SC-011]
- [x] CHK006 - Is `schema_version` named so the SC-011 verification is unambiguous? [Clarity, Spec §SC-011]
- [x] CHK007 - Is the verification mechanism for SC-011 (`git diff main -- contracts/stage1_vendor_identity/`) executable as written? [Measurability, Spec §SC-011]
- [x] CHK008 - Is the requirement that OCR-only `blocks[]` may be derived from line clustering (content difference) but MUST match the existing schema (shape unchanged) explicit and unambiguous? [Clarity, Spec §FR-002, Edge Cases]

## run_summary Additive-Only Surface

- [x] CHK009 - Are the two new `run_summary` fields enumerated by name (`preprocess_strategy_id`, `ocr_only_fallback_count`) and is no other new field implied? [Completeness, Spec §FR-008, FR-007]
- [x] CHK010 - Are the data types of the two new `run_summary` fields specified (string, integer)? [Completeness, Spec §FR-008, FR-007]
- [x] CHK011 - Is the boundary between "additive on `run_summary` (allowed)" and "additive on `preprocess_output.json` (forbidden)" explicit for BOTH new fields? [Clarity, Spec §FR-009, FR-020]
- [x] CHK012 - Is the prohibition on renaming, removing, or retyping any existing `run_summary` field explicit, including feature 017's `module_set_id` / `det_rec_variant_id` / `ppstructure_modules_invoked` AND feature 018's `raster_profile_id` / `region_strategy_id` / `region_strategy_fallback_count`? [Completeness, Spec §FR-009, FR-022]
- [x] CHK013 - Are JSON serialization properties (key ordering, whitespace, trailing newline) for `run_summary` specified, or is non-specification intentional and consistent with feature 017/018's stance? [Gap]
- [x] CHK014 - Is the position/ordering of new `run_summary` fields specified, or is order-agnosticism explicit? [Gap]
- [x] CHK015 - Is the always-emit policy (FR-007 / FR-010) explicit for BOTH new fields on ALL run kinds (gpu / cpu / stub) so absence ⇒ regression signal? [Completeness, Spec §FR-010, FR-007]
- [x] CHK016 - Is the requirement that the two new fields coexist with — not replace — feature 017's and feature 018's identifier surfaces explicit (no overlap, no replacement)? [Consistency, Spec §FR-008, Key Entities]

## Phase Timings & Pipeline Version Invariants

- [x] CHK017 - Are all eight `phase_timings.*` keys (`paddle_import`, `gpu_bind_probe`, `engine_init`, `rasterization`, `per_page_inference`, `artifact_write`, `total`, `warmup`) explicitly named as immutable in shape by this feature? [Completeness, Spec §Edge Cases, FR-022]
- [x] CHK018 - Is the prohibition on this feature changing `phase_timings` shape stated identically to feature 015/016/017/018 phrasing (renaming, removing, retyping)? [Consistency, Spec §Edge Cases]
- [x] CHK019 - Is `pipeline_version`'s `.gpu0` / `.cpu0` suffix pattern explicitly preserved across all preset combinations introduced by this feature? [Clarity, Spec §FR-022, SC-010]
- [x] CHK020 - Is the per-document `phase_timings.per_page_inference` semantics for the OCR-only path (time spent in det+rec only, no layout module) explicitly preserved as the same key, unchanged definition? [Clarity, Spec §Edge Cases]
- [x] CHK021 - Is the `phase_timings.rasterization` accounting for fallen-back documents (combined OCR-only attempt + `ppstructurev3` time vs. final-only) specified, or is the deferral to plan explicit? [Gap, Spec §FR-005]

## preprocess_strategy_id Vocabulary

- [x] CHK022 - Is the closed vocabulary for `preprocess_strategy_id` at landing explicitly bounded (`ppstructurev3` + at least one OCR-only preset like `ocr-only-v1` + a CPU/stub default value)? [Completeness, Spec §FR-001, FR-008]
- [x] CHK023 - Are CPU-default and stub-adapter values for `preprocess_strategy_id` specified, or is the deferral to plan explicit (candidates: `ppstructurev3`, `cpu-default`)? [Gap, Spec §FR-010, Assumptions]
- [x] CHK024 - Is the prohibition on free-form per-run module selection on the runtime path explicit (FR-001: preset-name only)? [Consistency, Spec §FR-001, Key Entities]
- [x] CHK025 - Is "adding a future preset is a code change plus a new `preprocess_strategy_id` value" explicit so a runtime module override cannot slip in? [Clarity, Spec §FR-001]
- [x] CHK026 - Is the human-readable-string requirement (not opaque numeric hashes) reasserted for `preprocess_strategy_id`? [Clarity, Spec §FR-008]
- [x] CHK027 - Is the OCR-only preset's canonical identifier value (e.g., `ocr-only-v1`) deferred to plan with the constraint that it MUST belong to the closed FR-001 vocabulary? [Clarity, Spec §FR-001, Assumptions]

## ocr_only_fallback_count Semantics

- [x] CHK028 - Is the unit of `ocr_only_fallback_count` ("number of documents that fell back in this run") explicit and unambiguous (not pages, not page-document pairs, not threshold trips)? [Clarity, Spec §FR-007, Key Entities]
- [x] CHK029 - Is the default value (`0`) on `ppstructurev3`, `ppstructurev3@cpu`, and stub-adapter runs explicit? [Completeness, Spec §FR-007]
- [x] CHK030 - Is the relationship between `ocr_only_fallback_count` and `preprocess_strategy_id` defined (counter is meaningful only when `preprocess_strategy_id` selects an OCR-only preset; on other selections it MUST emit `0`)? [Consistency, Spec §FR-007]
- [x] CHK031 - Is the prohibition on `ocr_only_fallback_count` appearing inside `preprocess_output.json` explicit? [Completeness, Spec §FR-009, FR-020]
- [x] CHK032 - Is the per-document attribution recoverable from `preprocess_output.json` shape derivation rule documented (e.g., a per-document hint that distinguishes OCR-only vs. fallen-back `ppstructurev3` output), or is the deferral to plan explicit? [Gap, Spec §FR-007]

## FR-021 Benchmark Artifact Escape Hatch

- [x] CHK033 - Is the FR-021 escape hatch (introducing a new persisted benchmark artifact) precisely conditioned on `/speckit.clarify` or `/speckit.plan` evidence that `run_summary` + harness/evaluator outputs are insufficient? [Clarity, Spec §FR-021]
- [x] CHK034 - If the escape hatch is taken, are the required deliverables (`data-model.md` + `research.md` + AMENDMENTS update) enumerated? [Completeness, Spec §FR-021]
- [x] CHK035 - Is the default position (no new persisted benchmark artifact at landing) consistent between FR-021, the Out of Scope subsection, and Assumptions? [Consistency]

## Corpus Baseline Immutability

- [x] CHK036 - Are committed corpus baselines under `tests/stage1_vendor_identity/*/` named as off-limits to this feature? [Completeness, Spec §FR-019, SC-007]
- [x] CHK037 - Is the legitimate channel for baseline regeneration named (`docs/stage1-vendor-identity/dataset-layout.md` + `labeling-guide.md` flow)? [Clarity, Spec §FR-019]
- [x] CHK038 - Is the verification mechanism for SC-007 (PR diff against `main` on baseline paths) executable as written? [Measurability, Spec §SC-007]

## Feature 014 / 015 / 016 / 017 / 018 Guarantee Carry-Forward

- [x] CHK039 - Does FR-022 enumerate the carried-forward guarantees by FR-number (015 FR-001 / FR-004 / FR-006 / FR-008, 016 FR-001..FR-020, 017 FR-001 / FR-008 / FR-010, 018 FR-008 / FR-009 / FR-011)? [Completeness, Spec §FR-022]
- [x] CHK040 - Is the carry-forward of `module_set_id` / `det_rec_variant_id` / `ppstructure_modules_invoked` shape explicit so this feature does not silently re-shape feature 017's identifier surface? [Consistency, Spec §FR-009, FR-022]
- [x] CHK041 - Is the carry-forward of `raster_profile_id` / `region_strategy_id` / `region_strategy_fallback_count` shape explicit so this feature does not silently re-shape feature 018's identifier surface? [Consistency, Spec §FR-009, FR-022]
- [x] CHK042 - Is the qualified "construct-PPStructureV3 exactly once when invoked" exception (the engine MAY remain unconstructed when `preprocess_strategy_id = ocr-only-v1`) explicit so feature 015 FR-001 cannot be read to require construction? [Clarity, Spec §FR-022]

## Downstream Contract Preservation

- [x] CHK043 - Are the four downstream consumers (evidence-packet 004, extract 005, router 008, assembler 009, evaluator 007) explicitly listed as needing to accept new OCR-only outputs unmodified? [Completeness, Spec §FR-022, US5]
- [x] CHK044 - Is "downstream consumer accepts without modification" measurable (existing schema validates; no downstream code change) per SC-008? [Measurability, Spec §SC-008]
- [x] CHK045 - Is the requirement that the fallback path's `ppstructurev3` output flows through evidence-packet → extract → route → assemble → evaluate without contract changes explicit? [Coverage, Spec §SC-008]
- [x] CHK046 - Is the verification mechanism for SC-008 (end-to-end small-corpus pipeline run with schema validation at each stage) testable as written? [Measurability]

## Cross-Section Consistency

- [x] CHK047 - Are FR-020 and FR-021 consistent (both forbid contract changes) without overlap or contradiction? [Consistency]
- [x] CHK048 - Is the requirement that adding a future preset needs a new `preprocess_strategy_id` value (not a runtime toggle) consistent across FR-001, the Clarifications session, and the Key Entities entry? [Consistency, Spec §FR-001, Key Entities]
- [x] CHK049 - Are the boundaries with feature 017 (module_set / det_rec) and feature 018 (raster_profile / region_strategy) named so contract-affecting scope creep is detectable? [Completeness, Spec §FR-026, Out of Scope]
- [x] CHK050 - Is the boundary "no new pinned dependency; same PaddleOCR text-det/rec variants" explicit (FR-027) so a different OCR engine cannot smuggle a contract change in? [Consistency, Spec §FR-027, Out of Scope]

## Notes

- Items intentionally test the requirements text, not the implementation. A `[x]` item asserts "the spec is clear/complete/consistent here" — not "the code does X correctly".
- The two new additive `run_summary` fields (`preprocess_strategy_id`, `ocr_only_fallback_count`) deserve close review at planning time alongside the SCHEMA_VERSION lineage (post-feature-018: 0.1.5 → 0.1.6 for this feature, exact bump to be confirmed at plan).
