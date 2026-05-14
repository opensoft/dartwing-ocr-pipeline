# Fallback-Path Checklist: OCR-Only Fast Lane For Vendor Identity

**Purpose**: Validate that requirements covering the OCR-only → `ppstructurev3` per-document fallback — the FR-005 combined two-threshold eligibility / sufficiency trigger, the deterministic disposition, the per-document fallback artifact contract, the `ocr_only_fallback_count` semantics, and the orthogonality with feature 018's region-first fallback — are complete, clear, and consistent. This is a release-gate checklist focused on the principal slice-specific surface 019 introduces.
**Created**: 2026-05-11
**Feature**: [spec.md](../spec.md)

## Eligibility / Sufficiency Trigger Specification (Clarifications Q2)

- [x] CHK001 - Is the trigger stated as a single deterministic rule with AND-semantics on the two thresholds (sufficiency holds only when token count ≥ threshold AND confidence aggregate ≥ threshold)? [Clarity, Spec §FR-005, Clarifications Q2]
- [x] CHK002 - Is the token-count side defined precisely (aggregate OCR-detected non-whitespace token count across the document's targeted region(s))? [Clarity, Spec §FR-005]
- [x] CHK003 - Is the confidence side defined precisely (aggregate of PaddleOCR text-detector confidence across detected boxes; aggregation function deferred to plan)? [Clarity, Spec §FR-005]
- [x] CHK004 - Is the rationale for AND-semantics explicit (character count alone is too easy to satisfy with junk text; confidence alone can miss thin-but-useful evidence) so a reviewer cannot quietly flip it to OR-semantics? [Clarity, Spec §Clarifications Q2]
- [x] CHK005 - Is the trigger evaluation point explicit (after OCR-only preprocessing completes for that document; before falling back) so reviewers can verify it does not run mid-page or mid-pipeline? [Clarity, Spec §FR-005]
- [x] CHK006 - Is the rule for empty / zero-detection inputs (no OCR boxes ⇒ confidence aggregate undefined) defined, or is the deferral to plan explicit (candidate: treat as sufficiency-fail and fall back)? [Gap, Spec §FR-005]
- [x] CHK007 - Is the requirement that the same input always yields the same disposition stated separately from the determinism check (so an implementation cannot quietly add a small jitter to the threshold check)? [Measurability, Spec §FR-006, SC-012]

## Inputs to the Trigger Decision (Bounded Set)

- [x] CHK008 - Is the input set for the trigger decision enumerated (page geometry, rasterized page metadata, OCR-only detector / recognizer output)? [Completeness, Spec §FR-005, FR-006]
- [x] CHK009 - Is the prohibition on extraction, classification, or vendor-identity model output participating in the decision explicit and exhaustive (all three model classes named)? [Clarity, Spec §FR-005, FR-006]
- [x] CHK010 - Is the prohibition on non-deterministic inputs (wall-clock time, random seed, env vars, model output) implicit-from-bounding or explicit? [Coverage, Spec §FR-006]
- [x] CHK011 - Is the targeted region for the trigger check the same region the OCR-only pass actually processed (so the check is not computed on a different region than the one that produced the evidence)? [Consistency, Spec §FR-005]

## Fallback Granularity and Action

- [x] CHK012 - Is the fallback granularity unambiguous ("on that document" — not per-page, not per-corpus)? [Clarity, Spec §FR-005, Edge Cases]
- [x] CHK013 - Is the fallback action stated as a single deterministic rule (fall back to `ppstructurev3` on that document; emit `ppstructurev3` `preprocess_output.json`; increment `ocr_only_fallback_count`)? [Clarity, Spec §FR-005, FR-007]
- [x] CHK014 - Is the prohibition on partial-output retention explicit (partial OCR-only output for that document is discarded; `ppstructurev3` output replaces it), or is the deferral to plan explicit? [Gap, Spec §FR-005]
- [x] CHK015 - Is the contract for what happens if the FR-005 fallback ITSELF produces blank output defined (`ppstructurev3` produces a normal sparse but schema-valid output; no double fallback), or is the deferral to plan explicit? [Gap, Spec §FR-005]
- [x] CHK016 - Is the prohibition on silent blank output AND the prohibition on fail-fast both explicit on the fallback path? [Completeness, Spec §FR-005, Edge Cases]

## Per-Document Fallback Artifact Contract

- [x] CHK017 - Is the requirement that the fallen-back document's `preprocess_output.json` is the `ppstructurev3` output (not a hybrid; not a marked OCR-only-with-warning artifact) explicit? [Completeness, Spec §FR-005, US3 acceptance scenario 2]
- [x] CHK018 - Is the requirement that the fallen-back document's `preprocess_output.json` validates against the existing schema (no new field, no rename, no retyping) explicit? [Completeness, Spec §FR-003, FR-020]
- [x] CHK019 - Is the requirement that page count, page index, coordinate origin / units, block-index ordering, and `pages.length == page_count` on the fallen-back document remain identical to a normal `ppstructurev3` run explicit? [Consistency, Spec §FR-003, Edge Cases]
- [x] CHK020 - Is the relationship to feature 018's region-strategy decision on the fallen-back document defined (does the `ppstructurev3` fallback respect the active `region_strategy_id` or always use `full-page`)? [Gap, Spec §FR-026]

## ocr_only_fallback_count Semantics

- [x] CHK021 - Is the unit of `ocr_only_fallback_count` ("number of documents that fell back in this run") explicit and unambiguous (not pages, not threshold trips, not page-document pairs)? [Clarity, Spec §FR-007, Key Entities]
- [x] CHK022 - Is the always-emit-with-default-0 policy explicit on every run kind (gpu / cpu / stub / `ppstructurev3` selection)? [Completeness, Spec §FR-007]
- [x] CHK023 - Is the increment rule (one increment per document; never per threshold trip; never per page) explicit? [Clarity, Spec §FR-007, Key Entities]
- [x] CHK024 - Is the prohibition on `ocr_only_fallback_count` appearing inside `preprocess_output.json` explicit? [Completeness, Spec §FR-009, FR-020]
- [x] CHK025 - Is the relationship "`ocr_only_fallback_count == K` ⇒ K documents in this run had their OCR-only pass fall back to `ppstructurev3`" stated as a one-to-one mapping derivable from the rule (not an estimate, not a sampled count)? [Measurability, Spec §FR-007]

## Threshold Tuning Provenance

- [x] CHK026 - Is the deferral of both threshold values (integer for token count, float for confidence aggregate) to `/speckit.plan` explicit, with the constraint that they MUST be fixed before benchmark runs? [Clarity, Spec §FR-005, Assumptions]
- [x] CHK027 - Is the requirement that the threshold values are recorded in this feature's research artifact alongside the candidate's `preprocess_strategy_id` value explicit (so a future reader can re-derive the tuning decision)? [Completeness, Spec §FR-005, FR-017]
- [x] CHK028 - Is the deferral of the confidence aggregation function (mean / weighted-mean / median / other) to `/speckit.plan` explicit, with the constraint that the chosen function MUST be deterministic? [Clarity, Spec §FR-005, Assumptions]
- [x] CHK029 - Is the requirement that a threshold-tuning change is a code change plus a new `preprocess_strategy_id` value (not a runtime knob) explicit? [Clarity, Spec §FR-001]

## Orthogonality with Feature 018's Region-First Fallback

- [x] CHK030 - Is the boundary "preprocess strategy axis and region strategy axis compose orthogonally" stated explicitly in FR-026? [Completeness, Spec §FR-026]
- [x] CHK031 - Is the rule "each axis emits its own deterministic disposition on `run_summary` independently" explicit (the two `*_fallback_count` fields can BOTH be non-zero in the same run on the same document)? [Clarity, Spec §FR-026]
- [x] CHK032 - Is the OCR-only-on-header-first-v1 composition described concretely (rasterize only header band, run OCR-only det+rec on that crop, emit schema-valid `preprocess_output.json` with header-band blocks on page 1 and empty records on pages 2..N per feature 018 Q2)? [Completeness, Spec §Edge Cases]
- [x] CHK033 - Is the prohibition on this feature changing feature 018's `region_strategy_fallback_count` disposition or feature 008's deterministic routing surface explicit? [Consistency, Spec §FR-026]

## Edge Behavior

- [x] CHK034 - Is the contract for an OCR-only run that produces zero detected boxes on the entire document defined (sufficiency-fails, falls back), or is the deferral to plan explicit? [Gap, Spec §FR-005]
- [x] CHK035 - Is the contract for a single-page PDF under OCR-only + `header-first-v1` explicit (process header band on the single page; fall back if sufficiency-fail), or does the spec rely on the multi-page rule degenerating gracefully? [Gap, Spec §Edge Cases]
- [x] CHK036 - Is the contract for landscape / rotated / unusual aspect-ratio PDFs under OCR-only explicit, or is the deferral to plan explicit? [Gap, Spec §FR-005, Assumptions]
- [x] CHK037 - Is the rule for an OCR-only run on a document where the targeted region is empty by construction (e.g., zero-area crop) defined, or is the deferral to plan explicit? [Gap, Spec §FR-005]

## Notes

- Items test that the spec's text describing the fallback path is complete/clear/consistent — not that the code under test executes the fallback correctly.
- CHK001–CHK009 (trigger specification and inputs) are the highest-risk subset; an ambiguous trigger at planning time means an unverifiable fallback at implementation time.
- The two open thresholds (token count integer, confidence aggregate float) and the confidence aggregation function are the principal /speckit.plan deliverables that downstream Tasks will block on.
