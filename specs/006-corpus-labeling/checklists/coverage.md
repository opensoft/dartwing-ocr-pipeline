# Corpus Coverage Rules Requirements Quality Checklist

**Purpose**: Pre-release gate. Validate that requirements governing corpus *coverage* — the 5/5/5/5 difficulty distribution (FR-001), the contiguous `inv_001`..`inv_020` numbering (FR-002), the critical `challenge_tags` coverage (FR-015), the `challenge_tags` invariants (FR-016), and the "no reserved filename" rule (FR-013, FR-020) — are complete, measurable, and free of contradictions. This checklist tests whether the *coverage rules themselves* are written well enough that a reviewer can objectively audit the corpus against them.
**Created**: 2026-04-20
**Feature**: [spec.md](../spec.md)
**Depth**: Deep (every coverage-related FR/SC cross-checked for clarity and measurability).

**Checklist disposition cleanup (2026-05-06)**: T074 already triaged the remaining items as future-scope concurrency/growth questions (simultaneous-PR numbering, `inv_NNN` re-use after retirement, future corpus growth beyond 20, `.DS_Store` handling), not blockers for the shipped 20-document corpus. The boxes are ticked to record that disposition; any reopened requirement belongs in a new feature/change.

## Requirement Completeness

- [x] CHK001 Is every critical tag in FR-015 explicitly enumerated (not just "at minimum the following")? [Completeness, Spec §FR-015]
- [x] CHK002 Does the spec define what "critically" means for tag coverage — must-exist vs. nice-to-have? [Clarity, Spec §FR-015]
- [x] CHK003 Are requirements stated for the non-critical tags ("coverage encouraged but not required") in an auditable way, or is that encouragement untestable? [Measurability, Spec §FR-015]
- [x] CHK004 Does the spec enumerate the full closed `challenge_tags` vocabulary, or does it only cite `dataset-layout.md`? [Completeness, Spec §FR-006]
- [x] CHK005 Are requirements stated for per-difficulty tag distribution (e.g., must `low_quality_scan` appear on a `hard`-bucket doc or is any bucket acceptable)? [Gap, Spec §FR-015]
- [x] CHK006 Does the spec define what "materially exercised" means in US2 Scenario 5? [Clarity, Spec §US2]
- [x] CHK007 Are requirements stated for documenting the FR-015-satisfying tag allocation up-front (research plan), or is that an internal implementation choice? [Gap, Research §3]
- [x] CHK008 Does the spec require a machine-checkable coverage audit (validator CLI), or only a human one? [Measurability, Spec §FR-014, §FR-015]
- [x] CHK009 Are all reserved generated filenames enumerated identically in FR-013 and the folder contract? [Consistency, Spec §FR-013, Data-Model §2]
- [x] CHK010 Does the spec require the ensemble-reserved `votes/` subdirectory and `consensus_output.json` to be absent, or only document that they are reserved? [Clarity, Spec §FR-020]
- [x] CHK011 Is FR-015's "at least one of `{vat_id_present, state_tax_id_present, other_tax_id_present}`" requirement stated in a machine-checkable form? [Measurability, Spec §FR-015]
- [x] CHK012 Are requirements defined for `inv_NNN` ordering when two documents are added concurrently (simultaneous PRs)? [Gap, Coverage]

## Requirement Clarity

- [x] CHK013 Is "exactly 5 of each difficulty" unambiguous, or could a labeler interpret it as "approximately 5"? [Clarity, Spec §FR-001]
- [x] CHK014 Is "contiguous from `001` through `020` with no gaps" specified so that a deleted document must be renumbered? [Clarity, Spec §FR-002]
- [x] CHK015 Is "where possible" in US1 Scenario 4 ("distinct real-world vendors") measurable, or is it discretionary? [Ambiguity, Spec §US1]
- [x] CHK016 Is "no two documents in the same bucket are duplicates of the same source file" defined by content hash, filename, or both? [Ambiguity, Spec §US1]
- [x] CHK017 Is "aggregate" in US2 Scenario 5 ("every tag materially exercised") distinguishable from per-bucket coverage? [Clarity, Spec §US2]
- [x] CHK018 Does the spec define how many tags a single document may carry (any upper bound)? [Gap]
- [x] CHK019 Is the difference between "tag encouraged" and "tag required" stated with an auditable threshold? [Clarity, Spec §FR-015]
- [x] CHK020 Is "no gaps in the 3-digit sequence" enforceable when the corpus grows beyond 20 (i.e., does the rule scale)? [Clarity, Spec §FR-002]

## Requirement Consistency

- [x] CHK021 Does FR-015 (critical tag set) align with FR-016 (`explicit_company_name` / `missing_company_name` invariants) without overlap or contradiction? [Consistency, Spec §FR-015, §FR-016]
- [x] CHK022 Does FR-016 ("`missing_company_name` MUST appear on every `missing_name` document") align with the schema's `challenge_tags` enum and the `additionalProperties: false` rule? [Consistency, Spec §FR-016, Contract]
- [x] CHK023 Is the 5/5/5/5 distribution in FR-001 consistent with the folder contract's enum order `["easy","medium","hard","missing_name"]`? [Consistency, Spec §FR-001]
- [x] CHK024 Does FR-013's reserved-filename list match the folder contract's `reserved_generated_filenames` list exactly? [Consistency, Spec §FR-013, Folder-Contract]
- [x] CHK025 Does the spec's claim "corpus must be 'input only' when shipped" (FR-013) align with the existence of a `notes.md` file (which is input, not generated)? [Consistency, Spec §FR-013]

## Acceptance Criteria Quality

- [x] CHK026 Is SC-002 ("5/5/5/5 distribution, contiguous prefixes") verifiable by a single validator command exit code? [Measurability, Spec §SC-002, §FR-014]
- [x] CHK027 Is SC-006 ("Critical `challenge_tags` coverage") verifiable by the validator or only by human inspection? [Measurability, Spec §SC-006]
- [x] CHK028 Is SC-009 ("Corpus usable as input to 003/later slices without adapter code") measurable by a specific test, or only by inspection? [Measurability, Spec §SC-009]
- [x] CHK029 Is there a measurable outcome for "no duplicate source PDFs within a bucket"? [Gap, Spec §Success Criteria, §US1]
- [x] CHK030 Is "distinct real-world vendors where possible" testable or inherently discretionary? [Measurability, Spec §US1]

## Scenario Coverage

- [x] CHK031 Are requirements defined for what happens if a chosen document fails to exercise any of the non-critical tags (does it block merge)? [Coverage, Spec §FR-015]
- [x] CHK032 Are requirements defined for when a document exercises a tag AND an explicit tag (e.g., `logo_only` on a non-missing-name doc)? [Coverage, Spec §Edge Cases]
- [x] CHK033 Are requirements defined for a document that would exercise a tag but the labeler judges it borderline (does tag-or-not-tag default to tag)? [Gap, Coverage]
- [x] CHK034 Are requirements defined for corpus growth — how the 5/5/5/5 rule evolves if future features add 10 more documents? [Coverage, Gap]

## Edge Case Coverage

- [x] CHK035 Does the spec address `inv_NNN` re-use after a document is removed (e.g., can `inv_007` be "retired" and re-assigned)? [Gap, Spec §FR-002]
- [x] CHK036 Are requirements defined for `evaluation_run_summary.json` at the corpus root (currently allowed by folder contract) during this feature's ship state? [Gap, Spec §FR-013]
- [x] CHK037 Does the spec address whether a `.DS_Store` / editor temp file in a corpus folder fails the validator? [Gap, Spec §FR-013]
- [x] CHK038 Are requirements defined for a document that matches no `challenge_tags` at all (empty array)? [Coverage, Schema]

## Dependencies & Assumptions

- [x] CHK039 Is the folder contract (`folder.schema.json`) treated as the source of truth for distribution rules, or does the spec duplicate them? [Dependency, Spec §FR-001]
- [x] CHK040 Is the assumption "we can source 20 documents that collectively hit FR-015" validated or stated as a risk? [Assumption, Research §3]
- [x] CHK041 Does the spec assume the challenge-tag vocabulary is frozen for the life of this feature? [Assumption, Spec §FR-006]
- [x] CHK042 Is the dependency on the validator (for FR-014 measurement) declared as a hard prerequisite? [Dependency, Spec §FR-014]

## Notes

- Check items off as completed: `[x]`.
- `[Gap]` = requirement silent. `[Ambiguity]` = stated but underspecified. `[Conflict]` = two statements appear to disagree.
- This checklist is intentionally adversarial — it attempts to break the coverage rules by finding silent cases, not to validate that the 20 documents hit the rules.
