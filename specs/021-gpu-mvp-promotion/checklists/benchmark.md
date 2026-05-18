# Benchmark Discipline Checklist: GPU MVP Promotion

**Purpose**: Validate that the four-run benchmark discipline, jitter-band semantics, `phase_timings.*` recording, and scratch-copy rules are written precisely enough that a third party can re-derive the promotion verdict from Appendix A alone, without re-running anything.
**Created**: 2026-05-18
**Feature**: [spec.md](../spec.md)

This checklist tests the *requirements writing* of the benchmark — not the benchmark numbers themselves. Items target completeness, clarity, consistency, measurability of FR-011 through FR-018 plus US3 plus the Benchmark Run Record and Jitter Band entities.

## Document Subset Requirements (FR-011)

- [ ] CHK001 Is the fixed five-document subset (`inv_001_easy`, `inv_002_easy`, `inv_006_medium`, `inv_011_hard`, `inv_012_hard`) enumerated identically in FR-011, US3 narrative, and Assumptions? [Consistency, Spec §FR-011]
- [ ] CHK002 Is the precedence rule ("unless an earlier appendix supplies a more specific fixed subset") clear about which appendix, where, and how a reviewer resolves it? [Clarity, Spec §FR-011, §Assumptions]
- [ ] CHK003 Are the difficulty tiers (easy / medium / hard) covered by the subset (2 easy + 1 medium + 2 hard), with the difficulty mix stated as intentional? [Completeness, Spec §FR-011]
- [ ] CHK004 Is the requirement explicit that the same five documents are used for legacy AND candidate (FR-013), with no per-lane subset variance allowed? [Consistency, Spec §FR-011, §FR-013]

## Four-Run Discipline (FR-012)

- [ ] CHK005 Is the four-run sequence stated with explicit ordering (warmup → legacy-default ×2 → candidate ×2) so a reviewer can flag a re-ordered execution? [Clarity, Spec §FR-012]
- [ ] CHK006 Is the warmup run identified as separate from the legacy and candidate pairs (i.e., not part of either lane's "run 1")? [Clarity, Spec §FR-012, §US3]
- [ ] CHK007 Is the "first run in each pair treated as warm-in and discarded" rule stated for BOTH lanes symmetrically? [Consistency, Spec §FR-012]
- [ ] CHK008 Is "the second run is the comparison point" stated unambiguously for both lanes — i.e., is there no remaining hint of averaging or median? [Clarity, Spec §FR-012, §FR-015]
- [ ] CHK009 Is the rationale (MIOpen/COMGR cache cold-vs-warm domination) cross-linked to the Edge Cases section so a reviewer understands why the discipline exists? [Traceability, Spec §FR-012, §Edge Cases]

## Lane Symmetry (FR-013)

- [ ] CHK010 Is FR-013's "same document subset" requirement testable from the run record (each lane's run-2 lists the same five document IDs)? [Measurability, Spec §FR-013]
- [ ] CHK011 Is the symmetry requirement extended to identical input files (same `source.pdf` bytes) across lanes, or only to the document set list? [Completeness, Gap]

## Phase Timing Coverage (FR-014)

- [ ] CHK012 Are the seven enumerated `phase_timings.*` keys (`paddle_import`, `gpu_bind_probe`, `engine_init`, `warmup`, `rasterization`, `per_page_inference`, `artifact_write`, `total`) reproduced identically in FR-014 and US3 narrative? [Consistency, Completeness, Spec §FR-014, §US3]
- [ ] CHK013 Is "when present" defined — i.e., when is a phase key expected to be present vs. legitimately absent (e.g., `engine_init` absent under all-suppressed lazy construction)? [Clarity, Spec §FR-014, §FR-008]
- [ ] CHK014 Is the "record every emitted phase_timings.* key" requirement testable as a strict superset rule (the record contains at least every emitted key; no key may be omitted on a whim)? [Measurability, Spec §FR-014]
- [ ] CHK015 Is the requirement clear that absence of a phase key is *itself* recorded (not silent omission), so FR-008's lazy-construction verification is reviewable? [Coverage, Spec §FR-008, §FR-014]
- [ ] CHK016 Is the phase-key vocabulary closed (only the named keys exist in feature 015's `run_summary` lineage), or is the spec ambiguous about future additions? [Clarity, Gap]

## Jitter Band Semantics (FR-015)

- [ ] CHK017 Is the jitter-band formula `max(|legacy_run2 − legacy_run1|, |candidate_run2 − candidate_run1|)` reproduced identically in FR-015, the Jitter Band entity, Assumptions, and the Clarifications bullet? [Consistency, Spec §FR-015, §Clarifications]
- [ ] CHK018 Is the material-change rule `|candidate_run2 − legacy_run2| > threshold` stated unambiguously (strict greater-than, not ≥)? [Clarity, Spec §FR-015]
- [ ] CHK019 Is the per-document, per-phase-key granularity stated everywhere — i.e., no global jitter band, no per-document aggregate? [Consistency, Spec §FR-015, §Jitter Band entity]
- [ ] CHK020 Is the formula's denominator-free, absolute-value form explicit (no fixed percentage band layered on top, per Assumptions clarification)? [Clarity, Spec §Assumptions]
- [ ] CHK021 Is the handling for the case `legacy_run1 == legacy_run2 AND candidate_run1 == candidate_run2` (threshold = 0) specified — does any non-zero candidate-vs-legacy delta count as material? [Coverage, Gap]
- [ ] CHK022 Is the timing-unit convention explicit (seconds? milliseconds? nanoseconds?), so the recorded numbers in Appendix A are reproducible? [Clarity, Gap]

## Material-Change Direction (FR-016)

- [ ] CHK023 Is FR-016 explicit that only `per_page_inference` and `total` are *permitted* to materially decrease on suppressed documents (other keys staying within jitter is the expected case)? [Clarity, Spec §FR-016]
- [ ] CHK024 Is FR-016 symmetric about direction — i.e., a candidate-vs-legacy *increase* in `per_page_inference` on a suppressed document is also a finding? [Coverage, Clarity, Gap]
- [ ] CHK025 Is "flagged as a finding, not absorbed silently" defined operationally — what artifact records the finding, and who reads it? [Clarity, Measurability, Spec §FR-016]
- [ ] CHK026 Is the inverse case (suppressed-and-only-`per_page_inference`-and-`total`-decrease) traceable to SC-006? [Traceability, Spec §FR-016, §SC-006]

## Run-Summary Coverage on Benchmark (FR-017)

- [ ] CHK027 Are the five required per-document run_summary fields (`evidence_gate_state_counts`, `evidence_gate_suppressed_fallback_count`, `ocr_only_fallback_count`, `preprocess_strategy_id`, plus the per-document gate decision) enumerated identically in FR-017 and US3 scenario 4? [Consistency, Completeness, Spec §FR-017]
- [ ] CHK028 Is the per-document gate decision required to be recorded in Appendix A explicitly per document, not only as an aggregate? [Clarity, Spec §FR-017, §US3]
- [ ] CHK029 Is the relationship between FR-017's recording requirement and feature 020's `evidence_gate_documents` table (which already carries per-document decisions) explicit — is Appendix A a transcription, a derivation, or both? [Clarity, Gap]

## Scratch-Copy Discipline (FR-018)

- [ ] CHK030 Is FR-018 unambiguous about which directory tree may NOT be mutated (`tests/stage1_vendor_identity/`), and is the scratch root requirement (`/tmp` or another explicit scratch root) named? [Clarity, Spec §FR-018]
- [ ] CHK031 Is the "intentionally a baseline-regeneration command" exception out-of-scope-marked, so an inspector recognizes it should not appear in this feature's deliverables? [Clarity, Spec §FR-018, §FR-033]
- [ ] CHK032 Is the scratch-copy rule extended to demo runs (US5 scenario 6) and not only benchmark runs? [Consistency, Spec §FR-018, §US5]
- [ ] CHK033 Is the requirement testable from a single artifact — e.g., can a reviewer assert "no benchmark output landed under `tests/stage1_vendor_identity/`" by inspecting commits or `find` output? [Measurability, Spec §SC-011]
- [ ] CHK034 Is the layout convention under `/tmp` defined precisely enough for a reproducer to find legacy run-2 vs. candidate run-2 outputs? [Coverage, Gap]

## Benchmark Run Record Entity

- [ ] CHK035 Is the Benchmark Run Record entity defined with all four indexing axes (document × lane × run × phase_timings key)? [Completeness, Spec §Key Entities]
- [ ] CHK036 Is the "20 records per benchmark" arithmetic (5 documents × 2 lanes × 2 runs) cross-checked against FR-011/FR-012? [Consistency, Spec §Key Entities, §FR-011, §FR-012]
- [ ] CHK037 Is the role of run-1 (warm-in, not in Appendix A) vs run-2 (comparison point, in Appendix A) stated in the entity definition? [Clarity, Spec §Key Entities]

## Appendix A Recording (FR-023)

- [ ] CHK038 Is FR-023 specific about which file holds the recording (`specs/020-vendor-evidence-gate/quickstart.md` Appendix A) and what alternative recording (blocked/failing evidence) looks like? [Clarity, Spec §FR-023]
- [ ] CHK039 Is the Appendix A content surface complete (per-document per-lane run-2 phase keys + jitter bands + per-document run_summary observability) so a third party can re-derive the verdict (SC-005)? [Completeness, Spec §FR-023, §SC-005]
- [ ] CHK040 Is the alternative path ("explicit blocked/failing evidence naming the cause") defined with the same recording rigor as the PASS path (named blocker, evidence trail, no silent skip)? [Coverage, Spec §FR-023, §FR-010]
- [ ] CHK041 Is the granularity of "per-document statement of which keys changed materially vs. stayed within jitter" (SC-005) explicit — one line per document, or one entry per (document × phase key)? [Clarity, Spec §SC-005]

## Acceptance Criteria for Benchmark

- [ ] CHK042 Is SC-005's "sufficient for a third party to re-derive the promotion verdict without re-running" testable from Appendix A alone (no source-code consultation)? [Measurability, Spec §SC-005]
- [ ] CHK043 Is SC-006 measurable against a closed set of phase keys (FR-014 enumeration), so "any other key crossing the jitter band" is countable? [Measurability, Spec §SC-006, §FR-014]
- [ ] CHK044 Is SC-011's "zero benchmark or demo runs mutate the committed corpus" testable via `git status` or commit diff inspection alone? [Measurability, Spec §SC-011]

## Gaps to Flag

- [ ] CHK045 Is the requirement for recording the `evidence_gate_id` per benchmarked document explicit, so a reviewer can confirm the preset identity matches across lanes? [Gap, Spec §US5]
- [ ] CHK046 Is the requirement for recording the workstation environment fingerprint (ROCm version, Paddle wheel version, Ollama version) explicit, or only implicit in "run notes"? [Gap, Coverage]
- [ ] CHK047 Are requirements defined for the case where the candidate-lane suppressed-document count differs from the expected (e.g., a document the operator expected to be `sufficient` is `borderline` on this run)? [Gap, Edge Case]
- [ ] CHK048 Is the requirement explicit about whether the benchmark must record successful Paddle preflight state per run (so post-hoc auditors know the gate passed for each run)? [Gap, Coverage]
- [ ] CHK049 Is FR-007 (the inverse of FR-006 — `borderline` and `insufficient` documents MUST still run PPStructureV3 fallback on `ppstructurev3@gpu`, with `evidence_gate_suppressed_fallback_count` *not* incrementing for them) covered by an explicit benchmark-record requirement, so the decision-table compliance is verifiable per-document from Appendix A? [Gap, Coverage, Spec §FR-007, §US2 Scenario 2]

## Notes

- This checklist tests whether the benchmark *requirements* are well-written; the benchmark numbers themselves are out-of-scope for this checklist (they are the Appendix A deliverable).
- The principal failure mode here is timing-keys drift (a new `phase_timings.*` key in feature-015-or-later that this spec doesn't enumerate); CHK016 and CHK045 flag that risk.
- Items CHK022, CHK034, CHK046, CHK048 are genuine gaps that the spec could clarify; they are not necessarily blocking for `/speckit.plan`.
