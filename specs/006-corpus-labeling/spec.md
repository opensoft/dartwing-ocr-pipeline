# Feature Specification: Corpus Scaffolding & Human Labeling (Stage 1 Vendor-Identity)

**Feature Branch**: `006-corpus-labeling`
**Created**: 2026-04-20
**Status**: Draft
**Input**: User description: "Corpus scaffolding & human labeling. call this 006-corpus-labeling. read the docs for details"

## Clarifications

### Session 2026-04-20

- Q: Where does the labeling guide live? → A: `docs/stage1-vendor-identity/labeling-guide.md` (alongside existing stage 1 docs)
- Q: What is the source of the 20 PDFs? → A: Mix of team-held invoices plus public samples to fill sparse buckets/tags
- Q: Is the US4 "independent reviewer re-labels a document" test a hard merge gate? → A: No — soft/aspirational; the guide must be complete in principle, no external reviewer required to land the feature
- Q: What does the validator treat as "readable" for `source.pdf`? → A: File exists + parseable by a PDF library without error (structural integrity, no render step)
- Q: Who screens source PDFs for PII / license issues before check-in? → A: Labeler applies a written screening checklist documented in the labeling guide; no separate reviewer sign-off

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Corpus Folder Scaffolding Exists And Validates Structurally (Priority: P1)

A pipeline developer or reviewer needs to run any stage 1 workstream (preprocessing, extraction, routing, evaluation) against real invoices. Before any of that is possible, the 20-document corpus must physically exist on disk: each document must live in its own per-document folder under `tests/stage1_vendor_identity/` with the correct name, the correct difficulty suffix, and a real `source.pdf`. The folder validator must accept every folder's layout even before any `expected.json` is labeled.

**Why this priority**: Every downstream harness and pipeline slice assumes the corpus folder contract already holds. Without the 20 folders, neither the evaluator nor any end-to-end pipeline run can be demonstrated. This is the minimum viable deliverable — folders and PDFs in place, correctly named, discoverable by the validator and by every workstream.

**Independent Test**: Run `python -m dartwing_ocr.validator validate corpus tests/stage1_vendor_identity` on the branch. Verify the validator reports 20 documents discovered, the difficulty distribution is exactly 5/5/5/5 across `easy`/`medium`/`hard`/`missing_name`, every folder name matches `^inv_\d{3}_(easy|medium|hard|missing_name)$`, every folder contains a readable `source.pdf`, and no folder fails the unconditional structural checks defined by `folder.schema.json`.

**Acceptance Scenarios**:

1. **Given** the corpus root `tests/stage1_vendor_identity/` after this feature lands, **When** a reviewer lists the folders, **Then** there are exactly 20 folders, numbered `inv_001_*` through `inv_020_*`, with no gaps in the 3-digit sequence and exactly 5 folders of each difficulty.
2. **Given** any document folder, **When** the validator runs folder-level checks, **Then** the folder name matches the mandated pattern, the derived `document_id` equals the full folder name (e.g., `inv_007_hard`), is unique within the corpus, and `source.pdf` is present and non-empty.
3. **Given** the corpus scaffolding is in place, **When** a second developer clones the branch, **Then** `source.pdf` opens in a standard PDF viewer for all 20 documents and no folder contains reserved generated filenames (`preprocess_output.json`, `edge_extraction_output.json`, `routing_decision.json`, `final_structured_payload.json`, `evaluation_document.json`) or the reserved `votes/` subdirectory.
4. **Given** the corpus scaffolding, **When** a reviewer inspects the four difficulty buckets, **Then** each bucket's 5 documents are drawn from distinct real-world vendors where possible, and no two documents in the same bucket are duplicates of the same source file.

---

### User Story 2 - Every Document Has Human-Labeled Expected Truth That Validates (Priority: P1)

A developer iterating on the extraction pipeline needs a stable, hand-labeled ground truth per document so evaluation is a meaningful comparison, not a guess. Every one of the 20 documents must have an `expected.json` that conforms to the frozen `expected.schema.json` contract at `contract_set_version = "1.0.0"` and captures the vendor-identity truth a human reviewer would stand behind.

**Why this priority**: Without labeled truth, the evaluator has nothing to compare against. This is not merely schema validation — it is the foundation of every quality claim stage 1 will ever make. Labels that are inconsistent, guessed, or schema-valid-but-wrong will silently bias every future pipeline decision. This story and US1 together are the minimum shippable corpus.

**Independent Test**: Run `python -m dartwing_ocr.validator validate corpus tests/stage1_vendor_identity`. Verify every `expected.json` validates against `expected.schema.json`, the `document_id` in each file matches the one derived from its folder name, `contract_set_version` equals `"1.0.0"` everywhere, all 5 missing-name documents satisfy the invariant set (company_name.present=false, company_name.inferred=true, expected_review.manual_review_required=true, expected_review.review_reason="company_name_inferred"), and no file contains predicted values, confidence values, or evaluation outcomes.

**Acceptance Scenarios**:

1. **Given** any document folder, **When** the validator reads `expected.json`, **Then** the file conforms to `expected.schema.json`, `document_id` matches the full folder name, every `challenge_tags` entry is drawn from the closed vocabulary frozen in the contract, and `difficulty` in the file matches the folder-name suffix.
2. **Given** any document NOT in the `missing_name` bucket (i.e., `easy`, `medium`, or `hard`), **When** the expected truth is inspected, **Then** `expected_vendor_candidate.company_name.present == true`, `.inferred == false`, and `.value` is the labeler's best reading of the explicit company name as it appears on the document (normalized for legibility only, not renamed to a parent entity).
3. **Given** any document in the `missing_name` bucket, **When** the expected truth is inspected, **Then** `expected_vendor_candidate.company_name.present == false`, `.inferred == true`, `.value` holds the labeler's best-guess inferred company name (may be null if no inference is defensible), `expected_review.manual_review_required == true`, and `expected_review.review_reason == "company_name_inferred"`.
4. **Given** any document with no explicit tax ID, website, phone, or email on the page, **When** the expected truth is inspected, **Then** those fields are `null` (never empty strings), and the address component fields follow the same null-for-missing rule per-field (e.g., `street_2` is `null` if the document only has a single street line).
5. **Given** the full corpus, **When** challenge-tag coverage is inspected across all 20 documents, **Then** every tag from the frozen vocabulary that is materially exercised by the chosen documents appears at least once in aggregate, and critically, `missing_company_name` appears on (and only on) the 5 missing-name documents while `explicit_company_name` appears on (and only on) at least the 15 non-missing documents.
6. **Given** any `expected.json`, **When** a reviewer inspects its contents, **Then** the file contains no keys outside the schema (`additionalProperties: false` is enforced by the contract) and contains no prediction-side data such as confidence scores, evidence pointers, OCR lines, or evaluator verdicts.

---

### User Story 3 - Reviewer Notes Explain Difficulty And Known Traps (Priority: P2)

A developer investigating a regression needs to understand quickly why a given document was placed in its difficulty bucket and what specific traps (remit-to mismatch, faint text, multi-entity header, logo-only branding, etc.) the document contains. Every `hard` and `missing_name` document must have a `notes.md` that explains those choices. `easy` and `medium` documents should have brief notes when the categorization is non-obvious.

**Why this priority**: Labels without context are hard to re-verify and harder to defend. Reviewer notes turn the corpus from "a pile of PDFs with JSON" into a curated diagnostic instrument. Notes are a hard requirement for `hard` and `missing_name` per the folder contract (`notes_md_by_difficulty`); they are a soft (warning-only) requirement for `easy` and `medium`.

**Independent Test**: Run the folder validator on every document. Verify all 5 `hard` and all 5 `missing_name` documents contain a non-empty `notes.md`. For those 10 required notes, verify each file names (a) why the document was placed in its difficulty bucket, (b) at least one concrete trap or feature present on the document that justifies the `challenge_tags` chosen, and (c) any labeler decision that a reviewer would otherwise have to guess (e.g., which of two visible entities is the true vendor).

**Acceptance Scenarios**:

1. **Given** any `hard` or `missing_name` document, **When** the folder validator runs, **Then** `notes.md` is present, non-empty, and the validator does not emit the "missing notes" hard error for that folder.
2. **Given** any `easy` or `medium` document without a `notes.md`, **When** the folder validator runs, **Then** the validator emits at most a soft warning and does not fail the corpus.
3. **Given** any `missing_name` document's `notes.md`, **When** a reviewer reads it, **Then** the file explains why no explicit company name was findable, what the labeler inferred as a best-guess vendor (if any), and which alternative entities on the page (e.g., remit-to, parent company, billing-to) were rejected.
4. **Given** any `hard` document's `notes.md`, **When** a reviewer reads it, **Then** the file names at least one specific trap — multi-entity header, remit-to mismatch, faint text, low-quality scan, portal cover page, rotated scan, logo-only branding, or similar — and the trap is represented in `challenge_tags` in the same document's `expected.json`.

---

### User Story 4 - A Labeling Guide Lets A New Reviewer Label Or Audit A Document (Priority: P3)

A newcomer to the project needs to be able to pick up one of the 20 documents (or a new candidate) and either produce or audit its `expected.json` without reverse-engineering conventions from existing files. A labeling guide co-located with the corpus lays out the conventions in one place: which string to pick for the company name, how to decide `present` vs `inferred`, when a difficulty should be `hard` vs `missing_name`, how `challenge_tags` are assigned, and how null-handling and normalization differ from scoring normalization.

**Why this priority**: A guide is not strictly required to ship the 20 labeled documents, but without it the corpus will drift the moment a second labeler joins. This is a small deliverable that pays for itself the first time the corpus grows or a label is disputed.

**Independent Test**: This test is aspirational, not a merge gate. The guide must be written to the standard that a reviewer who has never labeled a stage 1 document could pick one `easy` document's `source.pdf`, read the guide, and produce an `expected.json` from scratch whose output validates against the schema and agrees with the committed label on every required field (or diverges only in well-understood ways the guide itself acknowledges, e.g., company-name casing before normalization). Actually running this test with an external reviewer is explicit follow-on work and is NOT required for this feature to land. See SC-007 for the corresponding measurable outcome.

**Acceptance Scenarios**:

1. **Given** the committed labeling guide, **When** a reviewer reads it, **Then** the guide states explicit rules for every required `expected.json` key, including the closed `challenge_tags` vocabulary, the four difficulty definitions, and the missing-name invariants.
2. **Given** a disputed label, **When** a reviewer cites the guide, **Then** the guide contains enough decision rules to resolve common disputes without relying on tribal knowledge (e.g., remit-to vs vendor selection, DBA vs legal name selection, rotation interpretation, partial-address handling).
3. **Given** the guide, **When** a new candidate PDF is evaluated for inclusion, **Then** the guide describes how to decide the difficulty bucket and how to pick `challenge_tags`, so a new candidate can be placed consistently with the existing 20.

---

### Edge Cases

- **Duplicate vendor across documents**: Two or more documents may share the same vendor (e.g., different invoices from the same supplier). Each document must be labeled independently against its own page content; identical values across documents are acceptable, but the labeler must not copy labels between documents without reading each source.
- **Document legitimately has no tax ID, website, phone, or email**: The field is `null`, not `""`. The choice of `challenge_tags` for that document must not claim those artifacts are "present".
- **Two visible entities on one page (e.g., vendor logo at top, remit-to address block)**: The labeler picks the billing entity (vendor), not the remit-to entity. The corresponding `challenge_tags` includes `multi_entity_page` and, if the remit-to address differs, `remit_to_differs_from_vendor`.
- **Company name only appears in a logo, not as text**: `company_name.present == true` (it IS present on the document, just in logo form), `company_name.inferred == false`, `challenge_tags` includes `logo_only`. Not a `missing_name` case unless the logo itself is ambiguous enough that the labeler cannot commit to a reading.
- **Multi-page PDFs**: The entire document folder still represents ONE logical invoice. Labels describe the vendor identity implied by the whole document; acceptance does not require labels to track page-scoped evidence.
- **International invoices (non-US format)**: State may be a province or "null" when inapplicable; postal code may use non-US formats; `tax_ids.vat_id` is populated for EU/UK documents, with `ein` null. These are valid and do not require schema changes.
- **DBA vs legal name**: Label the name as it appears on the document. If the document shows "Acme Widgets Inc. dba AcmeWerx", the labeler writes the on-page string verbatim (normalization for scoring happens at evaluation time, not label time).
- **Scanned-to-PDF with heavy rotation or skew**: The label still describes the logical content; `challenge_tags` should include `rotated_scan`, `low_quality_scan`, or `faint_text` as applicable, and the document may be placed in `hard`.
- **Document that could plausibly be `missing_name` OR `hard`**: The difficulty bucket is a labeler decision captured in `notes.md`. `missing_name` is reserved for cases where no explicit company name string is on the document at all; a faint-but-present name is `hard`, not `missing_name`.
- **PII concerns on real invoices**: Source PDFs in the corpus are treated as test fixtures checked into the repository. The feature does not introduce a redaction workflow; if a document cannot be committed as-is, it must not be chosen for the corpus.
- **A source PDF becomes unreadable later**: Deleting and re-adding a document is handled as a new amendment; this feature does not prescribe re-labeling workflow beyond the first cut.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The corpus root `tests/stage1_vendor_identity/` MUST contain exactly 20 per-document folders at the end of this feature, and their difficulty distribution MUST be exactly 5 `easy`, 5 `medium`, 5 `hard`, and 5 `missing_name`.
- **FR-002**: Every document folder name MUST conform to the pattern `^inv_\d{3}_(easy|medium|hard|missing_name)$`, the 3-digit numeric prefix MUST be contiguous from `001` through `020` with no gaps, and the `document_id` derived from the folder name MUST equal the full folder name (e.g., `inv_007_hard`) and be unique across the corpus.
- **FR-003**: Every document folder MUST contain a readable, non-empty `source.pdf`. "Readable" at the validator level means the file exists, is non-empty, and opens without error via a standard PDF parsing library (structural integrity check only; no page-rendering dependency). The corpus MUST NOT rely on any PDF outside the per-document folders.
- **FR-004**: Every document folder MUST contain an `expected.json` that validates against `contracts/stage1_vendor_identity/v1.0.0/expected.schema.json` and sets `contract_set_version` to `"1.0.0"`.
- **FR-005**: Every `expected.json` MUST set `document_id` to match the full folder name (e.g., folder `inv_007_hard/` -> `document_id "inv_007_hard"`), and MUST set `difficulty` to match the folder-name suffix. The two MUST NOT diverge.
- **FR-006**: Every `challenge_tags` value MUST be drawn from the closed vocabulary frozen in the v1.0.0 contract. Any new tag requires the amendment path in `contracts/stage1_vendor_identity/AMENDMENTS.md` and is explicitly out of scope for this feature.
- **FR-007**: For every document NOT in the `missing_name` bucket, `expected_vendor_candidate.company_name.present` MUST be `true`, `expected_vendor_candidate.company_name.inferred` MUST be `false`, and `expected_vendor_candidate.company_name.value` MUST be the labeler's reading of the explicit company name on the document (never null).
- **FR-008**: For every document in the `missing_name` bucket, `expected_vendor_candidate.company_name.present` MUST be `false`, `expected_vendor_candidate.company_name.inferred` MUST be `true`, `expected_review.manual_review_required` MUST be `true`, and `expected_review.review_reason` MUST be the exact string `"company_name_inferred"`.
- **FR-009**: For any field whose value is absent from the source document, the label MUST be `null` — never an empty string and never an invented placeholder. This applies to all optional fields: `street_1`, `street_2`, `city`, `state`, `postal_code`, `country`, `ein`, `state_tax_id`, `vat_id`, `other_tax_id`, `website`, `phone`, `email`, and `company_name.value` in missing-name documents when no defensible inference exists.
- **FR-010**: No `expected.json` MAY contain keys outside the schema (enforced by `additionalProperties: false`) and no `expected.json` MAY contain predicted values, confidence scores, evidence pointers, OCR lines, evaluator verdicts, or any other generated-side data.
- **FR-011**: Every `hard` and every `missing_name` document folder MUST contain a non-empty `notes.md` explaining the difficulty choice and at least one concrete feature or trap that justifies the `challenge_tags` set on that document.
- **FR-012**: `easy` and `medium` document folders SHOULD contain a `notes.md` when the categorization or a label choice is non-obvious, but the absence of `notes.md` for those difficulties is a soft (warning-only) validator condition, not a corpus failure.
- **FR-013**: No document folder MAY contain any of the reserved generated filenames (`preprocess_output.json`, `edge_extraction_output.json`, `routing_decision.json`, `final_structured_payload.json`, `evaluation_document.json`) or the reserved `votes/` subdirectory at the end of this feature. The corpus must be "input only" when shipped.
- **FR-014**: The full corpus MUST pass `python -m dartwing_ocr.validator validate corpus tests/stage1_vendor_identity` with no hard errors. Soft warnings for missing `notes.md` on `easy` or `medium` documents are acceptable.
- **FR-015**: The `challenge_tags` across the full corpus MUST collectively exercise at least the following critical tags at least once: `explicit_company_name`, `missing_company_name`, `logo_only`, `remit_to_differs_from_vendor`, `low_quality_scan`, `ein_present`, and at least one of `vat_id_present` / `state_tax_id_present` / `other_tax_id_present`. Coverage of the remaining tags is encouraged but not required for this feature.
- **FR-016**: `missing_company_name` MUST appear as a `challenge_tag` on every `missing_name` document and MUST NOT appear on any non-missing document. Conversely, `explicit_company_name` MUST appear on every non-missing document and MUST NOT appear on any `missing_name` document. In this feature, the validator enforces the company-name triad (`MISSING_NAME_TRIAD_VIOLATION` on `expected.json` with `difficulty=missing_name`) and the closed `challenge_tags` vocabulary (`CHALLENGE_TAG_UNKNOWN`); the tag *pairing* rule in this FR is audit-enforced (see plan.md §Audit-only Enforcement and tasks.md T052), alongside the aggregate coverage rule in FR-015. A future amendment may add a machine check.
- **FR-017**: The feature MUST deliver a labeling guide at `docs/stage1-vendor-identity/labeling-guide.md`, checked into the repository, that documents the conventions applied to `expected.json` and `notes.md`: difficulty definitions, `challenge_tags` assignment rules, null-vs-empty-string policy, company-name provenance (present/inferred/value) decision tree, remit-to vs vendor selection, DBA vs legal name selection, the missing-name invariants, and the PII/license screening checklist required by FR-019. The guide MUST be cross-linked from the stage 1 documentation index (`docs/stage1-vendor-identity/README.md`) and added to the Key References section of `CLAUDE.md`.
- **FR-018**: Labels MUST be recorded verbatim as they appear on the source document, subject only to legibility normalization (e.g., removing obvious scanning artifacts in a character read). Value normalization for scoring (lowercase, whitespace collapse, state abbreviation equivalence, website scheme stripping, phone digits-only, etc. per `scoring.md`) MUST happen at evaluation time, not at label time.
- **FR-019**: Source PDFs included in the corpus MUST be committable to this repository as-is. The labeling guide MUST include a written PII/license screening checklist (e.g., no individual's home address, no full payment card or bank account numbers, no handwritten signatures, no licenses that forbid redistribution). The labeler applies this checklist per document before inclusion; no separate reviewer sign-off is required for this feature. Documents that fail the checklist MUST be excluded from the 20 rather than redacted in place. This feature does not introduce a redaction pipeline.
- **FR-020**: The corpus MUST remain compatible with the ensemble-mode folder layout reserved by the folder contract: no file in any document folder may collide with the reserved `consensus_output.json` filename. (The reserved `votes/` subdirectory is already covered by FR-013; FR-020 adds the ensemble-specific consensus filename on top of that umbrella.)

### Key Entities

- **Document folder**: One real-world invoice's on-disk home. Name follows `inv_NNN_<difficulty>`. Holds `source.pdf`, `expected.json`, optionally `notes.md`. Is the unit the folder validator treats as one document.
- **Source PDF (`source.pdf`)**: The original invoice file, committed in-tree. Not modified by this feature after placement.
- **Expected-truth label (`expected.json`)**: The hand-authored ground truth for vendor identity and review routing on one document. Conforms to `expected.schema.json` at `contract_set_version = "1.0.0"`. Contains `document_id`, `difficulty`, `challenge_tags`, `expected_review`, `expected_vendor_candidate`, and optional `notes`.
- **Vendor candidate fields**: The nested `expected_vendor_candidate` object: `company_name` (with `value`, `present`, `inferred`), `address` (with `street_1`, `street_2`, `city`, `state`, `postal_code`, `country`), `tax_ids` (with `ein`, `state_tax_id`, `vat_id`, `other_tax_id`), `website`, `phone`, `email`.
- **Reviewer notes (`notes.md`)**: A short, human-readable Markdown file explaining difficulty and traps. Required for `hard` and `missing_name`. Soft-recommended for `easy` and `medium`.
- **Challenge tag**: A string drawn from the closed vocabulary frozen in v1.0.0, used to summarize document features the corpus is exercising. Not a prediction; a curation signal.
- **Difficulty bucket**: One of `easy`, `medium`, `hard`, `missing_name`. The corpus is partitioned 5/5/5/5 across these buckets.
- **Labeling guide**: A repository document that captures the conventions this feature applies to `expected.json` and `notes.md`. The single point of reference for future labelers and auditors.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `python -m dartwing_ocr.validator validate corpus tests/stage1_vendor_identity` exits with zero hard errors on the branch that lands this feature.
- **SC-002**: 20 per-document folders exist, distributed exactly 5/5/5/5 across `easy`/`medium`/`hard`/`missing_name`, with contiguous numeric prefixes `inv_001` through `inv_020`.
- **SC-003**: 100% of the 20 documents have a readable `source.pdf` and a schema-valid `expected.json`, with `document_id` and `difficulty` in the JSON agreeing with the folder name.
- **SC-004**: 100% of the 5 `missing_name` documents satisfy the missing-name invariants (`company_name.present == false`, `company_name.inferred == true`, `manual_review_required == true`, `review_reason == "company_name_inferred"`).
- **SC-005**: 100% of `hard` and `missing_name` documents (10 of 10) have a non-empty `notes.md` that names the difficulty reason and at least one concrete trap aligned with that document's `challenge_tags`.
- **SC-006**: Critical `challenge_tags` coverage meets FR-015: at minimum `explicit_company_name`, `missing_company_name`, `logo_only`, `remit_to_differs_from_vendor`, `low_quality_scan`, `ein_present`, and at least one non-EIN tax-ID tag each appear in at least one document.
- **SC-007**: The labeling guide is written to the standard that a reviewer previously unfamiliar with the project could, using only the guide and a random corpus `source.pdf`, independently produce an `expected.json` that agrees with the committed label on every required field (modulo casing/whitespace acknowledged by the guide). This is measured by guide completeness review (every required `expected.json` key has an explicit rule in the guide; every difficulty bucket is defined; every missing-name invariant is stated). Physically running the test with an outside reviewer is follow-on work and not required for this feature.
- **SC-008**: No `expected.json` in the corpus contains schema-disallowed keys, predicted values, confidence scores, or evaluator verdicts (enforced by contract validation in SC-001 but called out separately because it is a governance guarantee, not just a schema check).
- **SC-009**: The corpus is fully usable as input to the preprocessing slice (003) and future extraction/evaluation slices without any adapter code: other workstreams read from `tests/stage1_vendor_identity/inv_*/source.pdf` and the matching `expected.json` directly.

## Assumptions

- The 20 candidate invoice PDFs are drawn from a mix of (a) real-world invoices already in the team's possession and (b) publicly-available invoice samples/templates used specifically to fill sparse difficulty buckets or challenge-tag coverage gaps (e.g., `logo_only`, `missing_name`, `low_quality_scan`). Both sources must satisfy FR-019's "committable as-is" rule; any PDF that would require redaction or raises licensing concerns is excluded from the 20 rather than remediated in place.
- Single-labeler authoring is acceptable for this first cut. Multi-labeler review, inter-rater agreement, and label versioning are follow-on work.
- Hand-editing JSON against the frozen contract (with the validator as the safety net) is the labeling interface. A dedicated labeling UI is out of scope for stage 1.
- Sensitive data on source PDFs either does not exist in the chosen documents or is not a blocker for check-in. No redaction pipeline is introduced; documents that would require redaction are excluded from the 20 rather than redacted in place.
- Normalization for scoring (lowercase, whitespace, abbreviations, etc.) lives in evaluator code per `scoring.md` and is NOT pre-applied to labels. Labels are recorded verbatim from the source document.
- The folder contract, `expected.schema.json`, and challenge-tag vocabulary are stable at `contract_set_version = "1.0.0"` for the life of this feature. Any schema or vocabulary change blocks the feature and requires the amendment path.
- Ensemble-mode artifacts (`votes/`, `consensus_output.json`) are not produced by this feature. The corpus is shipped input-only.
- Stage 1 is PDF-only; images and other formats are explicitly not part of the corpus.
- Downstream slices (preprocessing, extraction, routing, evaluation) consume the corpus read-only and write their outputs into the same per-document folders at runtime; the corpus authored by this feature does not pre-populate any generated artifact.
