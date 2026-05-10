# Fallback-Path Checklist: DPI Reduction And Region-First Vendor Identity Preprocess

**Purpose**: Validate that the spec, research, contracts, and quickstart agree end-to-end on the FR-007 region-first → full-page fallback path: trigger condition, fallback action, granularity, partial-output discard, engine reuse, `phase_timings.*` accounting, `region_strategy_fallback_count` semantics, per-document attribution recoverability, and operator-visible signals. This is a release-gate checklist (post-plan).
**Created**: 2026-05-10
**Feature**: [spec.md](../spec.md)

## Disposition (Clarifications Q1: Fall-Back, Not Fail-Fast)

- [ ] CHK001 - Is the FR-007 disposition stated as "fall back to full-page on that document" everywhere it appears (spec FR-007, Edge Cases, Clarifications session, US2 acceptance scenario 3, R-018.7, contracts/module-invariants.md I-018.5, quickstart.md §7)? [Consistency, Spec §FR-007, Clarifications Q1]
- [ ] CHK002 - Is the prohibition on fail-fast in this scenario explicit and stated identically in spec / research / contracts / quickstart so an implementer cannot accidentally re-introduce fail-fast? [Coverage, Spec §FR-007, R-018.7]
- [ ] CHK003 - Is the prohibition on silent blank `preprocess_output.json` output explicit and reasserted alongside the fall-back rule? [Completeness, Spec §FR-007]
- [ ] CHK004 - Is the requirement that the fallback's `preprocess_output.json` MUST validate against the existing schema (i.e., the full-page strategy's normal output) explicit? [Completeness, Spec §FR-007, US2 acceptance scenario 3]

## Trigger Condition (Clarifications Q3: Whitespace-Stripped Empty)

- [ ] CHK005 - Is the trigger condition stated as "concatenation of `blocks[].text` in the targeted region on page 1, with whitespace stripped, is empty" everywhere it appears? [Consistency, Spec §FR-007, Clarifications Q3, R-018.7, contracts/module-invariants.md I-018.5]
- [ ] CHK006 - Is the trigger condition explicitly required to be re-derivable from `preprocess_output.json` alone (no model-output dependence beyond what produced the blocks themselves)? [Completeness, Spec §FR-007, FR-006]
- [ ] CHK007 - Is the rule "trigger inspects only `blocks[].text`, NOT `raw_ocr_lines[].text`, NOT bounding-box presence, NOT block count" explicit so an implementer doesn't conflate signals? [Clarity, R-018.7, contracts/module-invariants.md I-018.5]
- [ ] CHK008 - Is "whitespace-stripped" defined precisely (Python `str.strip()` semantics — Unicode whitespace categories) so the boundary cases (NBSP, tab, newline, ZWSP) are unambiguous? [Clarity, R-018.7]
- [ ] CHK009 - Is the rule "the trigger evaluates AFTER region-first preprocessing completes and BEFORE the fallback decision" explicit so a future refactor doesn't accidentally evaluate it mid-pipeline? [Clarity, R-018.7]
- [ ] CHK010 - Is the rule "the targeted region for the trigger check is the SAME region used for the original region-first predict" explicit (so the trigger doesn't accidentally compute on a different page or band)? [Consistency, R-018.7]

## Granularity (Clarifications Q1: Per-Document)

- [ ] CHK011 - Is the fallback granularity stated as per-document everywhere it appears (not per-page, not per-corpus)? [Consistency, Spec §FR-007, Clarifications Q1, R-018.7, contracts/module-invariants.md I-018.10]
- [ ] CHK012 - Is the rule "the trigger fires at most once per document" explicit (once it fires, the document is reprocessed under full-page and the orchestrator moves on)? [Clarity, R-018.8, contracts/module-invariants.md I-018.10]
- [ ] CHK013 - Is the prohibition on per-page fallback explicit so a future "smarter" implementation doesn't try to keep page 1 region-first while re-running pages 2..N as full-page on a single document? [Clarity, R-018.7]

## Partial-Output Discard Semantics (R-018.7)

- [ ] CHK014 - Is the rule "the partial region-first output is FULLY discarded on a triggered fallback" explicit? [Completeness, R-018.7]
- [ ] CHK015 - Is the rule "the full-page strategy's output REPLACES the partial output (no merging)" explicit? [Clarity, R-018.7]
- [ ] CHK016 - Is the prohibition on emitting a mixed `pages[]` (partial page 1 + full pages 2..N) explicit so the per-document attribution rule from Clarifications Q4 stays unambiguous? [Consistency, R-018.7, Clarifications Q4]

## Engine Reuse on Fallback (R-018.9; Carry-Forward of Feature 015 FR-001)

- [ ] CHK017 - Is the rule "the fallback path MUST reuse the SAME PPStructureV3 engine instance" explicit? [Completeness, R-018.9, contracts/module-invariants.md I-018.3]
- [ ] CHK018 - Is the relationship to feature 015 FR-001 (PPStructureV3 constructed exactly once per process) explicit so reviewers can verify the carry-forward? [Traceability, Spec §FR-022, R-018.9]
- [ ] CHK019 - Is the prohibition on constructing a second engine for the fallback predict explicit so a future refactor doesn't introduce per-fallback engine init cost? [Clarity, R-018.9]
- [ ] CHK020 - Is the assumption "PPStructureV3 is stateless across `predict` calls" documented so the engine-reuse safety claim is auditable? [Assumption, R-018.9]

## `phase_timings.*` Accounting Under Fallback (R-018.10)

- [ ] CHK021 - Is the rule "`phase_timings.rasterization` reports the COMBINED wall-clock time on fallen-back documents (region-first attempt + full-page rasterization)" explicit? [Completeness, R-018.10]
- [ ] CHK022 - Is the same combined-cost rule applied to `phase_timings.per_page_inference` explicit? [Consistency, R-018.10]
- [ ] CHK023 - Is the prohibition on adding a new `phase_timings.*` sub-key for the region-first attempt's separate cost explicit (FR-022 — `phase_timings.*` shape is frozen)? [Completeness, R-018.10, Spec §FR-022, contracts/module-invariants.md I-018.8]
- [ ] CHK024 - Is the operator-facing reading rule explicit ("readers comparing `(reduced-v1, header-first-v1)` to `(reduced-v1, full-page)` can attribute timing differences to fallback overhead via `region_strategy_fallback_count`")? [Clarity, R-018.10, quickstart.md Appendix A]
- [ ] CHK025 - Is the rule "header-first CAN be slower than full-page on documents that fell back" explicitly named so benchmark readers don't interpret a higher-than-legacy timing as a code bug? [Clarity, R-018.10]

## `region_strategy_fallback_count` Semantics (Clarifications Q4 + R-018.8)

- [ ] CHK026 - Is the unit ("number of documents that fell back in this run") explicit and unambiguous in spec / research / contracts / quickstart? [Consistency, Spec §FR-009, R-018.8, Clarifications Q4]
- [ ] CHK027 - Is the always-emit-with-default-0 rule explicit on EVERY non-region-first run (`full-page`, `cpu-default`, `stub-default`)? [Completeness, Spec §FR-009, FR-011, R-018.8, contracts/module-invariants.md I-018.9]
- [ ] CHK028 - Is the range explicitly bounded `[0, N]` where N is documents-in-run? [Clarity, R-018.8, contracts/run-summary-schema.md §3]
- [ ] CHK029 - Is the determinism property explicit (two runs of the same `(raster_profile_id, region_strategy_id)` × same corpus subset produce the same `region_strategy_fallback_count`)? [Measurability, Spec §FR-006, R-018.8, determinism.md CHK026]
- [ ] CHK030 - Is the prohibition on `region_strategy_fallback_count` appearing inside `preprocess_output.json` explicit (Clarifications Q4 explicitly restricted this to `run_summary`)? [Completeness, Spec §FR-009, FR-020, contracts/run-summary-schema.md §4]

## Per-Document Attribution Recoverability (Clarifications Q4)

- [ ] CHK031 - Is the per-document attribution rule (fallen-back documents have full-length populated `pages[]`; clean region-first multi-page documents have page 1 populated and pages 2..N empty) documented so operators can recover attribution from `preprocess_output.json` without extra metadata? [Clarity, Spec §FR-009, Clarifications Q4, R-018.8, contracts/module-invariants.md I-018.10]
- [ ] CHK032 - Is the consequence "no per-document fallback marker is needed on `run_summary`" explicit so a future contributor doesn't try to add one? [Clarity, R-018.8, contracts/run-summary-schema.md §3]
- [ ] CHK033 - Is the reconstruction procedure documented end-to-end (operator sees `region_strategy_fallback_count: K` on `run_summary`; operator scans the K corresponding documents' `preprocess_output.json` to find the K fallen-back ones via `pages[]` shape) so operators don't need to guess? [Coverage, quickstart.md §7]

## `pages[]` Shape Invariant Cross-References (Clarifications Q2)

- [ ] CHK034 - Is the `pages.length == page_count` invariant explicitly cross-referenced from FR-007's fallback path text (so a reader of FR-007 alone knows the fallback's output respects the invariant)? [Consistency, Spec §FR-007, Clarifications Q2]
- [ ] CHK035 - Is the rule "a fallen-back document's `pages[]` has all entries populated (because the full-page strategy ran), while a clean region-first multi-page document has page 1 populated and pages 2..N empty" stated identically in spec Edge Cases, Q4 clarification, R-018.7, and contracts/module-invariants.md I-018.6? [Consistency]
- [ ] CHK036 - Is the empty-page-record schema (page_number, width, height, rotation_detected from PDF; blocks: [], raw_ocr_lines: []) explicitly documented in spec / R-018.6 / data-model.md / contracts so an implementer doesn't reinvent it? [Completeness, R-018.6, data-model.md §Empty page record]

## Coordinate System Under Fallback (R-018.15 / FR-002)

- [ ] CHK037 - Is the rule "after fallback, page 1's bbox coordinates come from the full-page strategy (NOT from the discarded region-first attempt)" explicit so coordinate-translation logic isn't accidentally applied twice? [Clarity, R-018.7, R-018.15]
- [ ] CHK038 - Is the FR-002 coordinate-system invariant ("identical to legacy on the same fixture, modulo ±1 pixel rasterization rounding") explicitly required to hold for the full-page fallback output (the same way it holds for a normal full-page run)? [Consistency, Spec §FR-002, R-018.15]

## Operator-Facing Signal Coherence (Quickstart §7)

- [ ] CHK039 - Does quickstart §7 ("FR-007 fallback path verification") cover the three operator-visible signatures of a fallback (`region_strategy_fallback_count` advanced; `pages[]` fully populated; `phase_timings.*` shows combined cost)? [Coverage, quickstart.md §7]
- [ ] CHK040 - Is the requirement for a fixture that forces the trigger explicit (so the spec doesn't assume one trivially exists)? [Gap, quickstart.md §7]
- [ ] CHK041 - Is the procedure for selecting / constructing a fallback-forcing fixture documented, or is the deferral to `tasks.md` explicit? [Gap, quickstart.md §7]

## Cross-Artifact End-to-End Consistency

- [ ] CHK042 - Is the fallback path described identically in spec FR-007, R-018.7, contracts/module-invariants.md I-018.5 + I-018.6 + I-018.10, contracts/run-summary-schema.md §3, and quickstart.md §7? [Consistency]
- [ ] CHK043 - Are the four `/speckit.clarify` resolutions (Q1 disposition, Q2 page coverage, Q3 trigger, Q4 fallback field shape) cross-referenced from R-018.7 / R-018.6 / R-018.8 so a reader of the research artifact alone can trace each decision to its clarification? [Traceability]
- [ ] CHK044 - Is the relationship between `region_strategy_id`, `region_strategy_fallback_count`, and the recoverable per-document attribution rule a single coherent story across spec / contracts / quickstart (rather than three separately-described mechanisms that happen to overlap)? [Consistency]

## Edge Cases Under Fallback

- [ ] CHK045 - Is the contract for "what happens when the FR-007 fallback ITSELF produces blank output (i.e., full-page also yields no text on this document)" defined, or is the deferral to plan / a future feature explicit? [Gap, failure-handling.md CHK023]
- [ ] CHK046 - Is the contract for "what happens when the trigger fires on document K-1 of a corpus run and the engine state for document K is somehow affected" defined (or explicitly out of scope because R-018.9 + the engine's stateless-predict assumption rule it out)? [Gap, R-018.9]
- [ ] CHK047 - Is the contract for "what happens on a single-page PDF whose page 1 header band has no text" defined (the trigger fires; the document falls back to full-page on the single page; `pages[]` length stays 1; counter increments by 1)? [Coverage, R-018.7]

## Notes

- Items test the spec / research / contracts / quickstart text describing the fallback path — not the implementation that performs the fallback. A `[ ]` item asks "is this written clearly/completely/consistently across artifacts?" not "does the code fall back correctly?".
- The fallback path crosses five artifacts (spec, clarifications, research, contracts, quickstart) and every checklist item asks whether those artifacts agree.
