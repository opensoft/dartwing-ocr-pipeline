# Determinism Checklist: PDF Preprocessing (Stage 1)

**Purpose**: Release-gate validation that the spec specifies byte-identical,
repeatable output with the rigor needed for evaluation stability. Every item
validates the requirements, not the implementation.
**Created**: 2026-04-20
**Feature**: [spec.md](../spec.md)
**Depth**: Release gate
**Audience**: Reviewer (PR + evaluation owner)

## Fixed Inputs to Determinism

- [ ] CHK001 Is the rasterization DPI pinned to a specific numeric value (300) rather than described qualitatively? [Clarity, Spec §FR-004]
- [ ] CHK002 Is the DPI specified as a project-wide constant, not a runtime flag? [Clarity, Spec §FR-004 §Assumptions]
- [ ] CHK003 Is the rule "changing DPI constitutes a pipeline-version bump" stated? [Clarity, Spec §FR-004]
- [ ] CHK004 Is the coordinate space of bboxes (rasterized pixels, not PDF points) pinned unambiguously? [Clarity, Spec §FR-005]

## Byte-Identical Guarantee

- [ ] CHK005 Does the spec state byte-identical reruns as a hard requirement (not just "stable" or "consistent")? [Clarity, Spec §FR-012]
- [ ] CHK006 Are the inputs that must be held constant for byte-identity enumerated (PDF bytes, pipeline version, ingestion-source configuration)? [Completeness, Spec §FR-012]
- [ ] CHK007 Is there a success criterion that quantifies determinism across the corpus (e.g., "100% of cases")? [Measurability, Spec §SC-002]
- [ ] CHK008 Does the spec state that byte-identity covers field *values* AND field *ordering*? [Completeness, Spec §US1 AC#2]

## Ordering Rules

- [ ] CHK009 Is the ordering rule for `pages` stated (ascending by `page_number` starting at 1)? [Clarity, Spec §US2 AC#1]
- [ ] CHK010 Is the ordering rule for `blocks` within a page stated (by `reading_order` ascending, unique, contiguous, starting at 1)? [Clarity, Spec §FR-008 §US2 AC#2]
- [x] CHK011 Is the ordering rule for `raw_ocr_lines` within a page stated deterministically? [Resolved — Spec §FR-009: sort by `bbox[1]` asc, `bbox[0]` asc, `line_id` asc]
- [x] CHK012 Is the tie-break rule when two detection artifacts share the same primary sort key specified? [Resolved — Spec §FR-009: `line_id` ascending]

## Identifier Stability

- [ ] CHK013 Does the spec state that `block_id` values are stable across reruns of the same input? [Completeness, Spec §US1 AC#2]
- [ ] CHK014 Does the spec state that `line_id` values are stable across reruns of the same input? [Clarity, Spec §FR-009]
- [x] CHK015 Is the interaction between page-scoping and stability specified — e.g., a failure on page 2 does not reshuffle page 3's IDs? [Resolved — Spec §FR-009a + §US1 AC#2: page-scoped in the strict sense; other-page failures cannot renumber this page's IDs]
- [ ] CHK016 Is the relationship between `reading_order` and the block-id suffix stated explicitly (so reviewers know whether they can drift independently)? [Ambiguity, Spec §FR-008]

## `document_text` Join Discipline

- [ ] CHK017 Is `document_text` specified as the deterministic concatenation of per-page text? [Clarity, Spec §FR-010]
- [ ] CHK018 Is the page ordering used for `document_text` specified (`page_number` ascending)? [Clarity, Spec §FR-010 §US2 AC#4]
- [ ] CHK019 Is the join strategy ("fixed and documented in code") required to be byte-stable? [Clarity, Spec §FR-010]
- [x] CHK020 Is the per-page join unit specified — blocks vs. raw lines — so implementations cannot diverge? [Resolved — Spec §FR-010: `blocks[].text` in `reading_order` asc, intra-page separator `"\n"`]
- [x] CHK021 Is the inter-page separator pinned (string constant) rather than left to implementation taste? [Resolved — Spec §FR-010: inter-page separator `"\n\n"`]

## Quality-Signal Determinism

- [ ] CHK022 Are the three input metrics for quality signals enumerated exactly (avg OCR line confidence, low-confidence line percentage, skew angle)? [Completeness, Spec §FR-013]
- [ ] CHK023 Is it stated that quality signals are rule-derived, not model-judged? [Clarity, Spec §FR-013]
- [ ] CHK024 Is the threshold-calibration deferral (exact numbers decided at planning/implementation) explicitly scoped to values only, not to the rule form? [Clarity, Spec §Clarifications 2026-04-20]
- [ ] CHK025 Are the quality thresholds required to be deterministic constants in code (not random, not per-run)? [Clarity, Spec §FR-013]

## Reading-Order Determinism

- [ ] CHK026 Is `reading_order` required to be contiguous integers starting at 1 within each page? [Clarity, Spec §FR-008 §US2 AC#2]
- [ ] CHK027 Is `reading_order` required to be unique within a page (no ties)? [Clarity, Spec §US2 AC#2]
- [x] CHK028 Does the spec address what `reading_order` means for non-text blocks (figures, tables)? [Resolved — Spec §FR-008: all blocks share one `reading_order` sequence; non-text blocks positioned by top-y / left-x / `block_id`]

## Rotation Determinism

- [ ] CHK029 Is the rotation snap rule (nearest allowed value) specified unambiguously? [Clarity, Spec §FR-006]
- [ ] CHK030 Is emitting a warning on rotation normalization required, with content that identifies the page? [Completeness, Spec §FR-006 §FR-014]
- [x] CHK031 Is the rasterized page's recorded `width` / `height` required to reflect the *post-rotation* image dimensions? [Resolved — Spec §FR-005: post-rotation coordinate space; bbox max cannot exceed `width`/`height`]

## Environment / Runtime Bounds

- [ ] CHK032 Is the requirement "no cloud calls during preprocessing" stated? [Completeness, Spec §FR-023]
- [ ] CHK033 Is the requirement "no GPU dependency for preprocessing" stated at least implicitly via "local" + the devcontainer path? [Clarity, Spec §FR-023 §Assumptions §SC-008]
- [x] CHK034 Does the spec address the risk that OCR-engine version drift could break byte-identity across developer machines? [Resolved — Spec §FR-018 + §Assumptions: `pipeline_version` encodes PaddleOCR-VL package + model-weights identifier; mismatched envs surface as version delta, not silent drift]
- [ ] CHK035 Does the spec state that debug-only outputs (per-page PNGs) must not be part of the determinism contract? [Clarity, Spec §FR-007]

## Measurable Acceptance

- [ ] CHK036 Is there a measurable pass criterion for determinism (SC-002)? [Measurability, Spec §SC-002]
- [ ] CHK037 Is there a measurable pass criterion for `line_id` stability on the "easy" subset (SC-003)? [Measurability, Spec §SC-003]
- [ ] CHK038 Do the determinism acceptance scenarios (US1 AC#2) enumerate every field expected to be byte-stable (block ordering, raw lines, reading order, IDs, bboxes, document_text)? [Completeness, Spec §US1 AC#2]

## Notes

- Check items off as completed: `[x]`
- Any `[Gap]` left open here is a latent determinism bug — treat as blocking for release
- Determinism is the load-bearing property for evaluation stability (SC-002, SC-003); prefer tightening the spec over tolerating ambiguity
