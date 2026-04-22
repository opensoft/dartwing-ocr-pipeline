# Labeling-Guide Requirements Quality Checklist

**Purpose**: Pre-release gate. Validate that the requirements *for the labeling guide itself* (FR-017, the companion clarifications, and the outline in research.md §4) are complete, clear, consistent, and measurable. This checklist tests the written requirements — not the guide's prose — so that when the guide is authored it has an unambiguous target.
**Created**: 2026-04-20
**Feature**: [spec.md](../spec.md)
**Depth**: Deep (every FR/SC/clarification that touches the guide is cross-checked).

**T074 post-ship tick-through (2026-04-21)**: Items CHK017, CHK020, CHK024, CHK037, CHK040 resolved by `docs/stage1-vendor-identity/labeling-guide.md` and ticked. Remaining open items (CHK018, CHK030, CHK033, CHK034) are spec-level gaps outside this feature's scope — deferred to a future spec clarification round rather than shipped as a labeling-guide change.

## Requirement Completeness

- [x] CHK001 Does the spec enumerate every section the labeling guide MUST contain, or does it only list examples? [Completeness, Spec §FR-017]
- [x] CHK002 Are requirements for each of the 12 sections listed in research.md §4 traced to a specific FR or clarification? [Traceability, Research §4]
- [x] CHK003 Is the guide's required audience (labelers, auditors, or both) specified? [Gap, Spec §FR-017]
- [x] CHK004 Are requirements defined for what the guide must say about the `challenge_tags` closed vocabulary beyond "assignment rules"? [Completeness, Spec §FR-017]
- [x] CHK005 Does the spec require the guide to cite the authoritative schema files (`expected.schema.json`, `folder.schema.json`) by path? [Gap, Spec §FR-017]
- [x] CHK006 Are requirements specified for how the guide documents the four difficulty buckets beyond "difficulty definitions"? [Completeness, Spec §FR-017]
- [x] CHK007 Does the spec require the guide to include the PII/license screening checklist, or does it only require the checklist's existence somewhere? [Consistency, Spec §FR-017, §FR-019]
- [x] CHK008 Are requirements stated for the guide's "null vs empty string" coverage — must it list every optional field, or only give examples? [Completeness, Spec §FR-017, §FR-009]
- [x] CHK009 Does the spec mandate that the guide explain the `logo_only` → non-missing-name rule, or is that left to the labeler's interpretation? [Gap, Spec §Edge Cases]
- [x] CHK010 Are requirements defined for how the guide handles "rejected alternative entities" (remit-to, parent co., billing-to)? [Completeness, Spec §FR-017, §US3]
- [x] CHK011 Is the labeling workflow (screen → place → label → validate) required to be documented step-by-step, or just mentioned? [Clarity, Research §4 step 10]
- [x] CHK012 Does the spec require the guide to define a dispute-resolution process, or is that a research-document suggestion only? [Gap, Research §4 step 11]

## Requirement Clarity

- [x] CHK013 Is "discoverable from the stage 1 documentation index" quantified with an explicit link requirement, or is it an ambient expectation? [Clarity, Spec §FR-017]
- [x] CHK014 Is the exact file path `docs/stage1-vendor-identity/labeling-guide.md` locked in, or is the location still negotiable? [Ambiguity, Spec §Clarifications Q1, §FR-017]
- [x] CHK015 Is the expected guide length, format, or structure (prose, Q&A, decision trees) specified? [Gap, Spec §FR-017]
- [x] CHK016 Are the terms "conventions", "decision tree", and "invariants" used consistently between FR-017, research.md §4, and the clarifications? [Consistency, Spec §Clarifications Q1]
- [x] CHK017 Is "legibility normalization" defined precisely enough for a labeler to distinguish it from scoring-time normalization? [Clarity, Spec §FR-018]
- [ ] CHK018 Does the spec state what "verbatim" means for on-page strings that span multiple lines or include OCR-ambiguous glyphs? [Ambiguity, Spec §FR-018]
- [x] CHK019 Is "newcomer to the project" (US4) operationalized with any prerequisites (e.g., must have read the constitution)? [Clarity, Spec §US4]
- [x] CHK020 Is "on-page string" ambiguous when the same name appears in multiple forms (header + footer + logo)? [Ambiguity, Spec §FR-018]

## Requirement Consistency

- [x] CHK021 Does FR-017's list of topics ("difficulty, challenge_tags, null-vs-empty, provenance, remit-to, DBA, missing-name") match the 12-section outline in research.md §4 without gaps? [Consistency, Spec §FR-017, Research §4]
- [x] CHK022 Do the `logo_only` edge-case rule (Edge Cases) and the company-name provenance decision tree (Research §4 step 6) resolve the same way? [Consistency, Spec §Edge Cases, Research §4]
- [x] CHK023 Does the spec treat the PII checklist as a guide section (FR-017) AND as its own FR (FR-019) without contradiction about *where* it lives? [Consistency, Spec §FR-017, §FR-019]
- [x] CHK024 Does the "labels recorded verbatim" rule (FR-018) contradict the guide's allowance for "legibility normalization" without specifying the allowed normalizations? [Conflict, Spec §FR-018]
- [x] CHK025 Are the guide's "difficulty bucket definitions" consistent with the folder-contract enum `["easy","medium","hard","missing_name"]` across the spec, data-model.md, and dataset-layout.md? [Consistency, Spec §FR-005, Data-Model §2]
- [x] CHK026 Is the company-name decision tree in research.md §4 consistent with FR-007 (non-missing) + FR-008 (missing) without leaving an undefined branch? [Consistency, Spec §FR-007, §FR-008, Research §4 step 6]

## Acceptance Criteria Quality

- [x] CHK027 Is SC-007 measurable by guide-completeness review alone, or does it implicitly require a human subject? [Measurability, Spec §SC-007, §Clarifications Q3]
- [x] CHK028 Does the spec define "every required `expected.json` key has an explicit rule in the guide" in a way a reviewer can audit without ambiguity? [Measurability, Spec §SC-007]
- [x] CHK029 Are the guide's acceptance criteria testable against the schema (e.g., every schema key gets one guide entry)? [Measurability, Spec §FR-017, §SC-007]
- [ ] CHK030 Is the bar for "enough decision rules to resolve common disputes" (US4 Scenario 2) objectively measurable? [Measurability, Spec §US4]

## Scenario Coverage

- [x] CHK031 Are requirements defined for a labeler encountering a difficulty choice not obviously covered (e.g., `hard` vs `missing_name` borderline)? [Coverage, Spec §Edge Cases]
- [x] CHK032 Does the spec require the guide to cover international-invoice edge cases (VAT-only, non-US states, non-US postal)? [Coverage, Spec §Edge Cases]
- [ ] CHK033 Does the spec require the guide to cover the multi-page PDF case explicitly? [Coverage, Spec §Edge Cases]
- [ ] CHK034 Are requirements stated for how the guide handles a document that passes structural validation but is borderline unreadable to a human? [Gap, Spec §FR-003]
- [x] CHK035 Does the spec require the guide to describe the corpus-growth path (new candidate PDF → difficulty + tag assignment)? [Coverage, Spec §US4 Scenario 3]

## Dependencies & Assumptions

- [x] CHK036 Is the guide's dependency on `dataset-layout.md` (for `challenge_tags` vocabulary) explicitly declared, or is duplication expected? [Dependency, Spec §FR-017]
- [x] CHK037 Is the guide's relationship to `schemas.md` specified (reference vs. reproduce)? [Dependency, Gap]
- [x] CHK038 Does the spec assume the guide will be updated when contracts are amended, or does it leave that to the amendments workflow? [Assumption, Spec §FR-017]

## Ambiguities & Conflicts

- [x] CHK039 Is "labeler" defined consistently (single author in Assumptions, "reviewer" in some scenarios)? [Ambiguity, Spec §Assumptions, §US1]
- [x] CHK040 Does the spec resolve whether the guide is a "living" document or frozen at ship? [Gap]
- [x] CHK041 Is the guide's cross-link requirement to `CLAUDE.md` Key References enforceable via a concrete check? [Measurability, Spec §FR-017]

## Notes

- Check items off as completed: `[x]`.
- `[Gap]` marks items where the spec/research is silent and a decision is needed before the guide is written.
- `[Ambiguity]` marks items where the spec says something but not precisely enough.
- `[Conflict]` marks items where two spec statements appear to disagree — resolution required before shipping.
