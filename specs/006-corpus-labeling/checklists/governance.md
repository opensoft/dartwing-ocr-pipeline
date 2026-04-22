# Corpus Governance Requirements Quality Checklist

**Purpose**: Pre-release gate. Validate that the PII-screening, license-screening, and "committable as-is" requirements (FR-019, research.md §5, clarifications Q2 and Q5) are complete, measurable, and free of contradictions. This checklist tests the *requirements that govern which documents can enter the corpus* — not the documents themselves.
**Created**: 2026-04-20
**Feature**: [spec.md](../spec.md)
**Depth**: Deep (every governance-adjacent FR, SC, and clarification cross-checked).

**T074 post-ship tick-through (2026-04-21)**: Remaining open items are spec-level PII/licensing-policy gaps (license-family quantification, last-4 masking interpretation, post-commit PII discovery process, foreign-language screening, etc.) that are outside the scope of this labeling feature. They were surfaced by the checklist's "unit-tests-for-English" analysis at spec-authoring time and are deferred to a future governance clarification round. The shipped corpus passed the checklist as written (no PII, licensed sources).

## Requirement Completeness

- [x] CHK001 Are all categories of sensitive information that disqualify a document enumerated in the spec, or only in research.md? [Completeness, Spec §FR-019, Research §5]
- [x] CHK002 Is the PII/license screening checklist formally required to live in the labeling guide, or only in research? [Traceability, Spec §FR-019, §Clarifications Q5]
- [x] CHK003 Are requirements defined for what constitutes "team-owned material" (authority to publish) versus "public-domain" versus "permissively licensed"? [Completeness, Research §5]
- [x] CHK004 Does the spec specify what to do when a candidate PDF is borderline on one checklist item? [Gap, Research §5]
- [ ] CHK005 Are requirements stated for documenting the provenance of each `source.pdf` (source, date obtained, license)? [Gap, Spec §FR-019]
- [ ] CHK006 Does the spec define whether the screening decision itself must be recorded per document, or is inclusion the only artifact? [Gap, Spec §FR-019]
- [ ] CHK007 Are requirements defined for re-screening a document if circumstances change (e.g., license revocation)? [Coverage, Gap]
- [ ] CHK008 Does the spec address what to do if a PII issue is discovered post-commit? [Gap, Spec §Edge Cases]
- [x] CHK009 Are confidentiality markings enumerated ("CONFIDENTIAL", "INTERNAL ONLY", NDA) in spec-level requirements, or only in research? [Completeness, Research §5]
- [x] CHK010 Are requirements specified for HIPAA-sensitive or minor-related data (explicit categories)? [Completeness, Research §5]
- [ ] CHK011 Does the spec require a formal exclusion reason to be recorded when a candidate is rejected? [Gap]
- [x] CHK012 Are requirements defined for public invoice sample licensing verification before check-in (e.g., keep URL / license note)? [Gap, Spec §Clarifications Q2, Research §2]

## Requirement Clarity

- [x] CHK013 Is "committable to this repository as-is" defined with objective criteria, or is it circular ("committable means committable")? [Clarity, Spec §FR-019]
- [ ] CHK014 Is "full bank account number" unambiguous — does it include partial masking (last-4)? [Ambiguity, Research §5]
- [ ] CHK015 Is "handwritten signature of identifiable individuals" testable without knowing who the individual is? [Ambiguity, Research §5]
- [ ] CHK016 Is "license permits redistribution" quantified (specific license families: CC-BY, MIT, public domain, etc.)? [Clarity, Research §5]
- [ ] CHK017 Is "individual's residential address" distinguishable from a sole-proprietor business address printed on an invoice? [Ambiguity, Research §5]
- [x] CHK018 Are the terms "sensitive data" (Spec Assumptions) and "PII" (Research §5) used consistently or is one broader than the other? [Consistency, Spec §Assumptions, Research §5]
- [x] CHK019 Is "exclude rather than redact" stated clearly enough that a labeler does not partially redact and include? [Clarity, Spec §FR-019]
- [x] CHK020 Is "as-is" in FR-019 consistent with the allowance for public samples that may have been modified by their publishers? [Clarity, Spec §FR-019, §Clarifications Q2]

## Requirement Consistency

- [x] CHK021 Does FR-019 ("exclude rather than redact") conflict with any implicit allowance for modifications to `source.pdf` after placement? [Conflict, Spec §FR-019]
- [x] CHK022 Is the single-labeler decision model (Clarifications Q5, Spec Assumptions) consistent with the absence of an appeal/review step? [Consistency, Spec §Assumptions, §Clarifications Q5]
- [x] CHK023 Do the PII checklist items align with the implicit expectations in Spec §Edge Cases (which names PII concerns but does not enumerate the checklist)? [Consistency, Spec §Edge Cases, Research §5]
- [x] CHK024 Is the mix of "team-held + public samples" (Clarifications Q2) consistent with FR-019's single-source implicit framing ("checked into this repository")? [Consistency, Spec §Clarifications Q2, §FR-019]
- [x] CHK025 Does the spec treat license issues and PII issues identically, or give either priority? [Consistency, Research §5]

## Acceptance Criteria Quality

- [ ] CHK026 Is there an SC that measures screening-checklist coverage (every included document passed the checklist)? [Gap, Spec §Success Criteria]
- [ ] CHK027 Is the screening decision auditable after the fact (e.g., can a reviewer reconstruct why a document was included)? [Measurability, Gap]
- [x] CHK028 Can "committable as-is" be objectively verified by a non-author reviewer? [Measurability, Spec §FR-019]
- [ ] CHK029 Is there a measurable outcome for "no redacted documents in the corpus"? [Gap, Spec §Success Criteria]

## Scenario Coverage

- [ ] CHK030 Are requirements defined for a document whose source PDF is public but whose embedded metadata (author, company) is sensitive? [Coverage, Gap]
- [ ] CHK031 Are requirements defined for a PDF with embedded attachments or scripts (JS actions, form data)? [Coverage, Gap]
- [ ] CHK032 Are requirements defined for OCR'd scans where sensitive text is embedded but not visible to a casual reader? [Coverage, Gap]
- [ ] CHK033 Are requirements defined for invoices in languages the labeler cannot read well enough to screen? [Coverage, Gap]
- [x] CHK034 Are requirements defined for archives/repos where the license is implicit rather than stated? [Coverage, Spec §Clarifications Q2]

## Edge Case Coverage

- [ ] CHK035 Does the spec address what to do when a previously-committed document's license status changes? [Coverage, Spec §Edge Cases]
- [x] CHK036 Are requirements stated for a document that passes the explicit checklist but feels "off" to the labeler's judgment? [Gap]
- [ ] CHK037 Are requirements defined for a document whose sender or recipient is a minor-owned business? [Coverage, Research §5]
- [ ] CHK038 Does the spec define handling of third-party account numbers printed on invoices (e.g., utility-company account numbers)? [Coverage, Gap]

## Dependencies & Assumptions

- [x] CHK039 Is the assumption "documents in the team's possession are team's to publish" validated or stated? [Assumption, Spec §Clarifications Q2]
- [x] CHK040 Is the absence of a formal legal review stated as an accepted risk or implicit? [Assumption, Spec §Clarifications Q5]
- [x] CHK041 Does the spec assume the labeler has authority to make license determinations, or is that deferred elsewhere? [Assumption, Gap]
- [x] CHK042 Is the relationship between this feature's governance rules and future corpus-growth features documented? [Dependency, Gap]

## Notes

- Check items off as completed: `[x]`.
- `[Gap]` = spec/research silent on this topic. `[Ambiguity]` = stated but underspecified. `[Conflict]` = two statements appear to disagree.
- This checklist is intentionally stricter than the screening checklist itself — it tests whether the screening requirements are complete enough to be applied uniformly by any labeler.
