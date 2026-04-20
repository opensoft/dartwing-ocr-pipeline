# Contract Alignment Checklist: Evidence Packet Assembly

**Purpose**: Release-gate validation that the spec's language matches the
pending `contracts/stage1_vendor_identity/v1.1.0/` amendment — the new
`evidence_packet.schema.json` plus the `folder.schema.json` delta —
without drift, gaps, or reinterpretation. Every item below validates the
requirements themselves, not the implementation.
**Created**: 2026-04-20
**Feature**: [spec.md](../spec.md)
**Depth**: Release gate
**Audience**: Reviewer (PR + contract owner)

## Contract Versioning

- [ ] CHK001 Does the spec pin the new packet's `contract_set_version` to a specific value and tie it to a new directory under `contracts/stage1_vendor_identity/`? [Traceability, Spec §FR-013]
- [ ] CHK002 Is the version-bump tier (MAJOR/MINOR/PATCH) explicitly classified per `AMENDMENTS.md` step 1, with rationale? [Clarity, Spec §FR-015c]
- [ ] CHK003 Is the amendment procedure referenced by path (`contracts/stage1_vendor_identity/AMENDMENTS.md`) so reviewers know which checklist governs the bump? [Traceability, Spec §FR-015c §Dependencies]
- [ ] CHK004 Is the rule "previously valid `v1.0.0` artifacts remain valid under the new version" stated explicitly? [Consistency, Spec §FR-015c §Assumptions]

## New Artifact Schema (`evidence_packet.schema.json`)

- [ ] CHK005 Does the spec enumerate every top-level required key the new schema must enforce (`contract_set_version`, `document_id`, `source_file`, `page_count`, `pages`, `reading_order`, `document_text`, `tables`, `ingestion_sources`, `perceptual_observations`, `candidate_vendor_signals`)? [Completeness, Spec §FR-004..FR-008]
- [ ] CHK006 Is the required-key list for `ingestion_sources` named (`paddleocr_vl`, `falcon_ocr`, `falcon_perception`)? [Completeness, Spec §FR-004]
- [ ] CHK007 Is the required-key list for each `ingestion_sources.*` entry named (`enabled`, `status`, `payload`)? [Completeness, Spec §FR-005]
- [ ] CHK008 Is `ingestion_sources.*.status` restricted to the same closed vocabulary as `preprocess_output` (`success`, `failure`, `not_implemented`)? [Consistency, Spec §FR-005]
- [ ] CHK009 Is the required-key list for `perceptual_observations` named (`status`, `logos`, `stamps`, `header_candidates`, `footer_candidates`)? [Completeness, Spec §FR-007]
- [ ] CHK010 Is the required-key list for `candidate_vendor_signals` named (`company_name`, `addresses`, `emails`, `websites`, `phones`, `tax_ids`)? [Completeness, Spec §FR-008]
- [ ] CHK011 Is each regex-hint object's required-key list named (`value`, `document_text_offset`, `document_text_length`, `page_index`, `block_index`, `line_index`, `provenance`)? [Completeness, Spec §FR-008 Q5]

## Closed Vocabulary Conformance

- [ ] CHK012 Is the `provenance` value for stage 1 literal `"unverified"` on every regex hint? [Clarity, Spec §FR-008]
- [ ] CHK013 Is the schema's openness at `provenance` (string vs. fixed enum) stated so future values (e.g. `voter_confirmed`) land without a MAJOR bump? [Clarity, Spec §Data Model]
- [ ] CHK014 Is the rule "when `status ∈ {failure, not_implemented}`, `payload` MUST be `null`" stated? [Consistency, Spec §Data Model]
- [ ] CHK015 Is the stage-1 sentinel `payload = {"kind": "structural"}` for `paddleocr_vl` on success specified? [Clarity, Spec §Data Model]

## Folder Contract Amendment

- [ ] CHK016 Does the spec state that `evidence_packet.json` is added to `reserved_generated_filenames` as an **optional** file (not required)? [Clarity, Spec §FR-015c]
- [ ] CHK017 Is the "folder validates whether the file is present or absent" rule stated? [Consistency, Spec §SC-008]
- [ ] CHK018 Is the rule "no other artifact's reserved-filename status is changed" explicitly stated (the four existing artifacts remain as-is)? [Completeness, Spec §FR-016]
- [ ] CHK019 Is the destination path (`<per-document-folder>/evidence_packet.json`) specified unambiguously (same folder as `preprocess_output.json`, not a subdirectory)? [Clarity, Spec §FR-015b §US4]

## Identifier & Reference Contracts

- [ ] CHK020 Is `page_index` specified as 0-based and defined as "index into the sorted `pages[]` array"? [Clarity, Spec §Data Model]
- [ ] CHK021 Is `block_index` specified as 0-based within the page's `blocks[]` sorted by `reading_order`? [Clarity, Spec §Data Model]
- [ ] CHK022 Is `line_index` defined with a deterministic formula (e.g. newline count in `block.text` before the match offset)? [Clarity, Spec §FR-008 Q5; Research Decision 2]
- [ ] CHK023 Is the `reading_order[]` top-level packet field specified as a flattened array of `block_id` strings in the same order used to build `document_text`? [Clarity, Spec §Data Model]
- [ ] CHK024 Is the invariant "`document_text[offset:offset+length] == value`" stated as an assembly-time assertion, not just a hope? [Completeness, Spec §Data Model Invariants]

## Field-Value Contracts

- [ ] CHK025 Are `document_text_offset` and `document_text_length` bounded (`integer >= 0`)? [Completeness, Spec §Data Model]
- [ ] CHK026 Is the coordinate frame for any bboxes passed through from `preprocess_output` explicitly unchanged (the packet does not re-project)? [Consistency, Spec §FR-006]
- [ ] CHK027 Is `page_count` required to equal `len(pages)` (same invariant 003 enforces)? [Consistency, Spec §FR-006]
- [ ] CHK028 Is `contract_set_version` required to be a string matching the same semver pattern used by the frozen contract set? [Consistency, Spec §FR-013]

## Null / Empty Discipline

- [ ] CHK029 Is the null-usage rule for scalars ("null, never empty string") stated for the new artifact? [Clarity, Spec §FR-014]
- [ ] CHK030 Is the empty-list rule for lists ("`[]`, never missing, never `null`") stated? [Clarity, Spec §FR-014]
- [ ] CHK031 Is the `candidate_vendor_signals.company_name == null` rule for stage 1 stated as a contract, not an accident? [Completeness, Spec §FR-008 Q2]
- [ ] CHK032 Is the `candidate_vendor_signals.addresses == []` rule for stage 1 stated as a contract? [Completeness, Spec §FR-008 Q2]
- [ ] CHK033 Is the "no schema-prohibited keys" rule stated for the packet (no voter/model/prompt keys ever)? [Consistency, Spec §FR-009]

## Cross-Artifact Consistency

- [ ] CHK034 Is the packet's `document_text` required to byte-match `preprocess_output["document_text"]`? [Consistency, Spec §Data Model Invariants]
- [ ] CHK035 Is the packet's `pages[]` required to passthrough 003's `pages[]` unchanged (no re-indexing, no filtering)? [Consistency, Spec §FR-006]
- [ ] CHK036 Is the packet's `tables[]` required to passthrough 003's `tables[]` unchanged (no re-interpretation)? [Consistency, Spec §FR-006 §Edge Cases]
- [ ] CHK037 Does the spec state that the four existing per-document artifacts remain byte-identical before and after assembly? [Completeness, Spec §FR-016 §SC-006]

## Ingestion-Source Declaration (Trijunction-Ready)

- [ ] CHK038 Is the stage-1 status of `paddleocr_vl` (`enabled: true`, `status: "success"` when `preprocess_output` succeeded) specified? [Completeness, Spec §FR-004 §FR-005]
- [ ] CHK039 Is the stage-1 status of `falcon_ocr` and `falcon_perception` (`enabled: false`, `status: "not_implemented"`, `payload: null`) specified? [Completeness, Spec §FR-004 §FR-005 §Q2 Resolved]
- [ ] CHK040 Is the extension path — flipping a source from `not_implemented` to `success` without schema changes — stated? [Completeness, Spec §FR-004 §US2 AC#2]

## Validation Obligation

- [ ] CHK041 Does the spec require that every assembled packet validate against `evidence_packet.schema.json` before being returned (not just before being persisted)? [Completeness, Spec §FR-015a §Clarifications Q3]
- [ ] CHK042 Is the input-side obligation — validate `preprocess_output.json` against its schema before assembling — stated? [Completeness, Spec §FR-003 §FR-017]
- [ ] CHK043 Is the "no partial / schema-invalid packet on disk" rule stated (persistence only happens after output validation passes)? [Clarity, Spec §FR-015a §FR-015b]
- [ ] CHK044 Is the validator tooling identified (`python -m ledgerlinc_ocr.validator validate artifact --schema .../evidence_packet.schema.json ...`)? [Traceability, Spec §Quickstart]

## Notes

- Check items off as completed: `[x]`
- Flag unresolved `[Gap]` / `[Ambiguity]` / `[Conflict]` items for spec amendment before implementation begins
- Contract is not yet frozen — resolve contract/spec conflicts by updating **whichever is wrong**; once `v1.1.0` is merged, the schema becomes the authority
