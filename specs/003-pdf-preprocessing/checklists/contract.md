# Contract Alignment Checklist: PDF Preprocessing (Stage 1)

**Purpose**: Release-gate validation that the spec's language matches the frozen
`contracts/stage1_vendor_identity/v1.0.0/preprocess_output.schema.json` contract
without drift, gaps, or reinterpretation. Every item below validates the
requirements themselves, not the implementation.
**Created**: 2026-04-20
**Feature**: [spec.md](../spec.md)
**Depth**: Release gate
**Audience**: Reviewer (PR + contract owner)

## Contract Versioning

- [ ] CHK001 Is `contract_set_version` pinned to a specific value (`"1.0.0"`) and cross-referenced to `contracts/stage1_vendor_identity/v1.0.0/`? [Traceability, Spec §FR-018]
- [ ] CHK002 Is the distinction between `contract_set_version` (frozen) and `pipeline_version` (build-specific) explicitly stated? [Clarity, Spec §FR-018]
- [ ] CHK003 Is the forbidden surface of contract modification explicitly called out (no edits to the frozen schema set in this slice)? [Completeness, Spec §FR-018]
- [ ] CHK004 Is the amendment path (`contracts/stage1_vendor_identity/AMENDMENTS.md`) referenced as out-of-scope for this slice? [Completeness, Spec §Assumptions]

## Required-Key Alignment

- [ ] CHK005 Does the spec enumerate every top-level required key the schema demands (`contract_set_version`, `pipeline_version`, `document_id`, `source_type`, `source_file`, `page_count`, `pages`, `document_text`, `tables`, `quality`, `ingestion_sources`, `warnings`)? [Completeness, Spec §FR-017..FR-020]
- [ ] CHK006 Is every required per-page key named (`page_number`, `width`, `height`, `rotation_detected`, `blocks`, `raw_ocr_lines`)? [Completeness, Spec §FR-005..FR-009]
- [ ] CHK007 Is every required per-block key named (`block_id`, `block_type`, `bbox`, `reading_order`, `text`, `confidence`)? [Completeness, Spec §FR-008]
- [ ] CHK008 Is every required per-line key named (`line_id`, `bbox`, `text`, `confidence`)? [Completeness, Spec §FR-009]
- [ ] CHK009 Are the three mandatory `ingestion_sources` keys named exactly (`paddleocr_vl`, `falcon_ocr`, `falcon_perception`)? [Completeness, Spec §FR-015]

## Closed Vocabulary Conformance

- [ ] CHK010 Is `source_type` restricted to the literal value `"pdf"`, with non-PDF inputs rejected before artifact write? [Clarity, Spec §FR-001 §FR-003]
- [ ] CHK011 Is the `block_type` vocabulary listed in the same closed form the schema enforces (`text`, `title`, `table`, `figure`, `header`, `footer`)? [Consistency, Spec §FR-008]
- [ ] CHK012 Is `rotation_detected` restricted to `{0, 90, 180, 270}` with a normalization rule for off-values? [Clarity, Spec §FR-006]
- [ ] CHK013 Is `scan_quality` restricted to `{good, fair, poor}`? [Consistency, Spec §FR-013]
- [ ] CHK014 Is `noise_level` restricted to `{low, medium, high}`? [Consistency, Spec §FR-013]
- [ ] CHK015 Is `ingestion_sources.*.status` restricted to `{success, failure, not_implemented}`? [Consistency, Spec §FR-015]

## Identifier Contracts

- [ ] CHK016 Is the `block_id` pattern stated as `^p\d+_b\d+$` (matching the schema) and tied to `page_number`? [Clarity, Spec §FR-008]
- [ ] CHK017 Is the `line_id` pattern stated as `^p\d+_l\d+$`? [Clarity, Spec §FR-009]
- [ ] CHK018 Is the uniqueness scope of identifiers (per-page vs. per-document) unambiguously specified? [Clarity, Spec §FR-008 §FR-009]
- [ ] CHK019 Is the relationship between `reading_order` and the numeric suffix of `block_id` specified (or explicitly left open)? [Ambiguity, Spec §FR-008]

## Field-Value Contracts

- [ ] CHK020 Is `bbox` specified as exactly four non-negative integers in the page coordinate space? [Clarity, Spec §FR-005 §FR-008]
- [ ] CHK021 Is the coordinate frame (rasterized-image pixels vs. PDF points) stated unambiguously so bboxes and `width`/`height` share a frame? [Consistency, Spec §FR-005]
- [ ] CHK022 Is `confidence` bounded to `[0.0, 1.0]` for both blocks and lines? [Completeness, Spec §FR-008 §FR-009]
- [ ] CHK023 Is `page_count` required to be `≥ 1` and consistent with `len(pages)`? [Consistency, Spec §FR-017]
- [ ] CHK024 Is `reading_order` required to be a unique, contiguous integer sequence starting at `1` within each page? [Clarity, Spec §FR-008]

## Null / Empty Discipline

- [ ] CHK025 Is the null-usage rule ("null only where the schema permits it") stated? [Clarity, Spec §FR-020]
- [ ] CHK026 Is missing OCR text specified as empty string rather than `null`? [Clarity, Spec §FR-020]
- [ ] CHK027 Is the "no schema-prohibited keys" rule stated (no business vendor fields in this artifact)? [Consistency, Spec §FR-020 §FR-021]

## Ingestion-Source Declaration

- [ ] CHK028 Is the stage-1 status of `paddleocr_vl` (enabled, `status: "success"` on normal runs) specified? [Completeness, Spec §US1 AC#3 §FR-015]
- [ ] CHK029 Is the stage-1 status of `falcon_ocr` and `falcon_perception` (`enabled: false`, `status: "not_implemented"`) specified? [Completeness, Spec §FR-015]
- [ ] CHK030 Is the extension path — adding Falcon sources later without breaking the contract — stated? [Completeness, Spec §FR-016]

## Artifact Placement & Invocation

- [ ] CHK031 Is the write location (`tests/stage1_vendor_identity/inv_XXX_<difficulty>/preprocess_output.json`) specified unambiguously? [Clarity, Spec §FR-017]
- [ ] CHK032 Is `document_id` derivation (folder basename, not filename) specified? [Clarity, Spec §FR-002]
- [ ] CHK033 Is `source_file` defined as the relative filename of the input PDF? [Clarity, Spec §FR-003]
- [ ] CHK034 Is the rule "no other stage-1 artifact is written by this slice" stated? [Consistency, Spec §FR-017 §FR-022]

## Validation Obligation

- [ ] CHK035 Does the spec require that every emitted artifact validate against the v1.0.0 schema before being persisted? [Completeness, Spec §FR-019]
- [ ] CHK036 Is the "no partial / schema-invalid artifact on disk" rule stated? [Clarity, Spec §FR-019]
- [ ] CHK037 Is the validator tool identified (`python -m ledgerlinc_ocr.validator validate artifact preprocess_output`)? [Traceability, Spec §US1 Independent Test]

## Cross-Artifact Consistency (Gap Check)

- [x] CHK038 Does the spec state which keys from the schema examples in `docs/stage1-vendor-identity/schemas.md` are required vs. illustrative? [Resolved — Spec §Assumptions: schemas.md examples are illustrative; JSON Schema file is authoritative on conflict]
- [x] CHK039 Does the spec reconcile the example `document_id: "inv_001"` in `schemas.md` with the folder-basename rule `inv_XXX_<difficulty>` in FR-002? [Resolved — Spec §FR-002: `inv_XXX` slice extracted, `_<difficulty>` suffix dropped, anchored to frozen pattern `^inv_\d{3}$`]
- [x] CHK040 Does the spec state the `tables[*]` object shape convention (page reference, bbox, grid) since the schema accepts any object shape there? [Resolved — Spec §FR-011a: pinned keys `page_number`, `block_id`, `bbox`, `rows`, `columns`, optional `cells`; no other keys; part of `pipeline_version`]

## Notes

- Check items off as completed: `[x]`
- Flag unresolved `[Gap]` / `[Ambiguity]` / `[Conflict]` items for spec amendment before implementation begins
- Contract is frozen at v1.0.0 — resolve contract/spec conflicts by updating the **spec**, never the contract (use the AMENDMENTS path if the contract itself is wrong)
