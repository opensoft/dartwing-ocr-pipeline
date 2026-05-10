# Contract Preservation Checklist: PPStructureV3 Module And Model Reduction

**Purpose**: Validate that requirements protecting the four canonical stage 1 artifact schemas, the active contract set, `pipeline_version`, and the additive-only `run_summary` surface are complete, clear, and consistent. This is a release-gate checklist.
**Created**: 2026-05-09
**Feature**: [spec.md](../spec.md)

## Schema Preservation (preprocess_output.json + four canonical artifacts)

- [x] CHK001 - Are all four canonical stage 1 artifact schemas (`preprocess_output`, `edge_extraction_output`, `routing_decision`, `final_structured_payload`) explicitly named as immutable by this feature? [Completeness, Spec §FR-019]
- [x] CHK002 - Is the prohibition on adding, removing, renaming, or retyping any field in `preprocess_output.json` reasserted for BOTH the reduced module set and every lighter detection/recognition variant? [Clarity, Spec §FR-003]
- [x] CHK003 - Is `contract_set_version` immutability explicitly required? [Completeness, Spec §FR-019]
- [x] CHK004 - Is the prohibition on touching `contracts/stage1_vendor_identity/AMENDMENTS.md` for this feature explicit? [Completeness, Spec §FR-019, SC-010]
- [x] CHK005 - Is `schema_version` (and which artifact carries it) named so the SC-010 verification is unambiguous? [Clarity, Spec §SC-010]
- [x] CHK006 - Is the verification mechanism for SC-010 (`git diff main -- contracts/stage1_vendor_identity/`) executable as written? [Measurability, Spec §SC-010]

## Phase Timings & Pipeline Version Invariants

- [x] CHK007 - Are all eight `phase_timings.*` keys (`paddle_import`, `gpu_bind_probe`, `engine_init`, `rasterization`, `per_page_inference`, `artifact_write`, `total`, `warmup`) explicitly named as immutable in shape? [Completeness, Spec §Edge Cases, FR-009]
- [x] CHK008 - Is the prohibition on lighter variants changing `phase_timings` shape stated identically (renaming, removing, retyping) to feature 015/016 phrasing? [Consistency, Spec §Edge Cases]
- [x] CHK009 - Is `pipeline_version`'s `.gpu0` / `.cpu0` suffix pattern explicitly preserved across all configurations introduced by this feature? [Clarity, Spec §FR-021, SC-009]
- [x] CHK010 - Is "pipeline_version shape established in features 014/015/016" defined precisely enough to verify "unchanged"? [Measurability, Spec §FR-019]

## run_summary Additive-Only Surface

- [x] CHK011 - Are the three new `run_summary` fields enumerated by name (`module_set_id`, `det_rec_variant_id`, `ppstructure_modules_invoked`) and is no other new field implied? [Completeness, Spec §FR-008, FR-001, FR-009]
- [x] CHK012 - Are the data types of the three new `run_summary` fields specified (string, string, list-of-strings)? [Completeness, Spec §FR-008, FR-001]
- [x] CHK013 - Is the boundary between "additive on `run_summary` (allowed)" and "additive on `preprocess_output.json` (forbidden)" explicit? [Clarity, Spec §FR-009, FR-019]
- [x] CHK014 - Is the prohibition on renaming, removing, or retyping any existing `run_summary` field explicit? [Completeness, Spec §FR-009]
- [x] CHK015 - Are JSON serialization properties (key ordering, whitespace, trailing newline) for `run_summary` specified, or is non-specification intentional? [Gap]
- [x] CHK016 - Is the position/ordering of new `run_summary` fields specified, or is order-agnosticism explicit? [Gap]
- [x] CHK017 - Does the spec define what counts as a "field rename" vs. a "field addition" so reviewers can apply FR-009 unambiguously? [Clarity, Gap]

## module_set_id / det_rec_variant_id / ppstructure_modules_invoked Vocabularies

- [x] CHK018 - Is the closed vocabulary for `module_set_id` at landing explicitly bounded (`legacy`, `reduced-v1`, plus a CPU/stub default value)? [Completeness, Spec §FR-002, Clarifications]
- [x] CHK019 - Is the closed vocabulary for `det_rec_variant_id` defined, or is the deferral to `/speckit.plan` explicit? [Gap, Spec §Assumptions]
- [x] CHK020 - Are CPU-default and stub-adapter values for `module_set_id` and `det_rec_variant_id` specified, or is the deferral to plan explicit? [Gap, Spec §FR-010, Clarifications]
- [x] CHK021 - Is the element type of `ppstructure_modules_invoked` (string sub-module name) specified? [Clarity, Spec §FR-001]
- [x] CHK022 - Is the empty-list semantic for `ppstructure_modules_invoked` on the stub adapter explicit? [Clarity, Spec §FR-001]
- [x] CHK023 - Is the human-readable-string requirement (not opaque numeric hashes) reasserted for `module_set_id` and `det_rec_variant_id`? [Clarity, Spec §FR-008]

## Downstream Contract Preservation

- [x] CHK024 - Are the four downstream consumers (evidence-packet 004, extract 005, router 008, assembler 009, evaluator 007) explicitly listed as needing to accept new GPU outputs unmodified? [Completeness, Spec §FR-004, US5]
- [x] CHK025 - Is "downstream consumer accepts without modification" measurable (existing schema validates; no downstream code change) per SC-007? [Measurability, Spec §SC-007]
- [x] CHK026 - Is the priority rule "schema preservation > module-disable savings" explicit when a downstream stage depends on a module's output? [Clarity, Spec §FR-004]
- [x] CHK027 - Is "module is referenced by a downstream consumer" defined operationally (which preprocess_output fields trace to which PPStructureV3 sub-module)? [Gap, Spec §FR-004]
- [x] CHK028 - Is the verification mechanism for SC-007 (end-to-end small-corpus pipeline run with schema validation at each stage) testable as written? [Measurability]

## FR-020 Benchmark Artifact Escape Hatch

- [x] CHK029 - Is the FR-020 escape hatch (introducing a new persisted benchmark artifact) precisely conditioned on `/speckit.clarify` or `/speckit.plan` evidence that `run_summary` + harness/evaluator outputs are insufficient? [Clarity, Spec §FR-020]
- [x] CHK030 - If the escape hatch is taken, are the required deliverables (data-model.md + research.md + AMENDMENTS update) enumerated? [Completeness, Spec §FR-020]
- [x] CHK031 - Is the default position (no new persisted benchmark artifact at landing) consistent between FR-020, the Out of Scope subsection, and Assumptions? [Consistency]

## Corpus Baseline Immutability

- [x] CHK032 - Are committed corpus baselines under `tests/stage1_vendor_identity/*/` named as off-limits to this feature? [Completeness, Spec §FR-018, SC-006]
- [x] CHK033 - Is the legitimate channel for baseline regeneration named (`docs/stage1-vendor-identity/dataset-layout.md` + `labeling-guide.md` flow)? [Clarity, Spec §FR-018]
- [x] CHK034 - Is the verification mechanism for SC-006 (PR diff against `main` on baseline paths) executable as written? [Measurability, Spec §SC-006]

## Cross-Section Consistency

- [x] CHK035 - Are FR-019 and FR-021 consistent (both forbid contract changes) without overlap or contradiction? [Consistency]
- [x] CHK036 - Is the requirement that adding a future module-set preset needs a new `module_set_id` value (not a runtime toggle) consistent across FR-002, the Clarifications session, and the Key Entities entry? [Consistency, Spec §FR-002, Clarifications, Key Entities]
- [x] CHK037 - Are the boundaries with feature 018 (DPI / region-first) and feature 019 (OCR-only fast lane) named so contract-affecting scope creep is detectable? [Completeness, Spec §FR-025, FR-026]
