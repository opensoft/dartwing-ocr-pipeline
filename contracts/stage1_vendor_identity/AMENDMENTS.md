# Stage 1 Vendor-Identity Contract Set — Amendment Log

This file is the changelog for the `contracts/stage1_vendor_identity/` contract set and the checklist contributors follow when proposing a change.

## Amendment Checklist

Before you change any contract, work through these steps in order:

1. **Decide the version bump**.
   - `MAJOR`: any removal, rename, or narrowing of an allowed-value set; any change that invalidates previously valid artifacts.
   - `MINOR`: additive change (new optional field, new enum value, new tag, new cross-artifact rule).
   - `PATCH`: typos, wording, non-behavioral cleanup.
   Pick the smallest bump that honestly describes the change.
2. **Update the human-facing documentation layer**. Edit whichever of the following the change affects:
   - `docs/stage1-vendor-identity/schemas.md`
   - `docs/stage1-vendor-identity/dataset-layout.md`
   - `docs/stage1-vendor-identity/scoring.md`
   - `docs/stage1-vendor-identity/architecture.md`
   - `.specify/memory/constitution.md`
3. **Create a new version directory** `contracts/stage1_vendor_identity/v<new-version>/` by copying the previous version's contents verbatim, then apply your delta inside the new directory. Do not mutate a shipped version directory.
4. **Update `contract_set.json`** in the new version directory so `contract_set_version` matches the directory name and any new schema/tag/rule entries are registered.
5. **Update the validator** if the change affects Tier 2 rules:
   - Add or rename violation codes in `src/ledgerlinc_ocr/validator/report.py`.
   - Add or update rule code in `src/ledgerlinc_ocr/validator/cross_artifact.py` (or the relevant module).
6. **Update fixtures and tests** under `tests/contract_tests/` to cover the new rules; keep the existing `1.0.0` fixtures validating against `1.0.0` unchanged.
7. **Append a new entry below** in the changelog section naming the version bump and the change.
8. **Run `pytest tests/contract_tests/`** and confirm no regressions. New fixtures should validate only under the new version; prior fixtures should continue to validate under the prior version.
9. **Open a PR.** The branch name should include the new version (e.g. `contracts-1.1.0-add-tag-foo`). The PR body should reference this file.

Per the repo constitution, the documentation layer and the machine-readable layer must never contradict each other. Do not merge partial amendments.

## Changelog

### v1.0.0 — 2026-04-12

**Branch**: `001-freeze-schemas-folder-contracts`

Initial freeze of the stage 1 vendor-identity contract set. Delivered:

- Seven artifact JSON Schemas:
  - `preprocess_output.schema.json`
  - `edge_extraction_output.schema.json`
  - `routing_decision.schema.json`
  - `final_structured_payload.schema.json`
  - `expected.schema.json`
  - `evaluation_document.schema.json`
  - `evaluation_run_summary.schema.json`
- One folder contract:
  - `folder.schema.json` (consumed as JSON configuration by `ledgerlinc_ocr.validator.folder`)
- Contract-set metadata in `contract_set.json`:
  - semver `1.0.0`
  - closed `challenge_tags` vocabulary (18 tags, sourced from `docs/stage1-vendor-identity/dataset-layout.md`)
  - declared cross-artifact rules: `PROVENANCE_TRIAD_INCONSISTENT`, `EVIDENCE_REFERENCE_UNRESOLVED`, `DOCUMENT_COUNT_MISMATCH`
  - declared pipeline-versioned artifacts: the four pipeline artifacts only
  - declared policy-versioned artifacts: `routing_decision` only
- Stable violation-code vocabulary (see `src/ledgerlinc_ocr/validator/report.py`).
- CLI surface at `python -m ledgerlinc_ocr.validator` (see `specs/001-freeze-schemas-folder-contracts/contracts/validator-cli.md`).

Stage 1 is deliberately narrow: PDF input, vendor identity only, no line items, single-voter baseline. Forward-compatibility for the three-voter ensemble is maintained at the *shape* level (`vote_metadata` present, `votes/` and `consensus_output.json` reserved, ensemble `consensus_metrics` fields optional) but any future non-single-voter run requires a contract-set amendment that adds the relevant enum values.

### v1.1.0 — 2026-04-21

**Branch**: `004-evidence-packet-assembly`

**Tier**: MINOR — additive only. All v1.0.0 artifacts remain byte-identical
and valid under v1.1.0.

Summary: introduce the `evidence_packet` artifact — a deterministic,
voter-agnostic, Trijunction-shaped data structure assembled from
`preprocess_output.json`. The packet is the stable interface single-voter
and future three-voter extraction slices will program against; it carries
no voter-, model-, or prompt-specific content.

What was added:

- New artifact schema: `evidence_packet.schema.json` (Draft 2020-12).
  Required top-level keys (in order): `contract_set_version`,
  `document_id`, `source_file`, `page_count`, `pages`, `reading_order`,
  `document_text`, `tables`, `ingestion_sources`, `perceptual_observations`,
  `candidate_vendor_signals`. `additionalProperties: false` at every
  object level. Shape mirrors `preprocess_output.schema.json` for
  passthrough fields (pages, blocks, raw_ocr_lines, bbox).
- `contract_set.json` delta:
  - `contract_set_version` → `"1.1.0"`.
  - `"evidence_packet"` appended to `artifact_names`.
  - `"evidence_packet": "evidence_packet.schema.json"` added to
    `artifact_schemas`.
  - **NOT** added to `pipeline_versioned_artifacts` or
    `policy_versioned_artifacts` — the packet is a voter-facing data
    structure, not a pipeline versioned artifact in the v1.0.0 sense.
- `folder.schema.json` delta: `"evidence_packet.json"` appended to
  `reserved_generated_filenames`. The packet file is **optional** at
  the folder level (produced only at DEBUG logger level); the folder
  contract accepts both presence and absence.

Preservation note: no v1.0.0 file was edited. `v1.0.0/` remains the
authoritative snapshot for downstream consumers that have not yet
opted into v1.1.0. `v1.1.0/` is a superset.

Amendment path for Falcon OCR and Falcon Perception: when those sources
land, their `ingestion_sources.<source>.status` flips from
`not_implemented` to `success`/`failure` and `payload` becomes non-null.
No packet key order, key set, or type changes are required — the shape
locked in v1.1.0 is the forward-compat commitment (see US2 AC#2 and SC-005
in `specs/004-evidence-packet-assembly/spec.md`).

### v1.2.0 — 2026-04-23

**Branch**: `010-pp-structurev3-preprocessing`

**Tier**: MINOR — additive only. All v1.0.0 and v1.1.0 artifacts remain
byte-identical and valid under v1.2.0 (every previously-accepted `confidence`
value is still accepted; the change only widens what's permitted).

Summary: permit `null` on `preprocess_output.block.confidence` and
`preprocess_output.ocr_line.confidence`, and on the mirrored structural
confidence fields in `evidence_packet`, so preprocessing can persist the
engine-missing case without substituting `0.0`. Required to unblock feature
010's FR-004 / R-013 rule ("missing → `null`, never `0.0`, never empty"),
while preserving the contract's numeric `[0.0, 1.0]` confidence domain.

What changed relative to v1.1.0:

- `preprocess_output.schema.json`:
  - `$defs.block.properties.confidence.type` widened from `"number"` to
    `["number", "null"]`.
  - `$defs.ocr_line.properties.confidence.type` widened the same way.
  - `minimum: 0.0` and `maximum: 1.0` stay in place — they apply only
    when the value is a number (JSON Schema ignores numeric bounds on
    null), so engine-emitted numbers are still required to be in
    `[0.0, 1.0]`. This keeps the widening strictly to the null case;
    preprocessing persists missing, non-finite, or out-of-range scores as
    `null` instead of fabricating an in-range value.
- `evidence_packet.schema.json`:
  - `$defs.block.properties.confidence.type` widened from `"number"` to
    `["number", "null"]`.
  - `$defs.ocr_line.properties.confidence.type` widened the same way, so
    evidence-packet assembly can validate a v1.2-compatible
    `preprocess_output.json` without coercing missing evidence to `0.0`.
- `contract_set.json`:
  - `contract_set_version` → `"1.2.0"`.
  - `description` updated to name the amendment.
  - No change to `artifact_names`, `artifact_schemas`, `folder_schema`,
    `pipeline_versioned_artifacts`, `policy_versioned_artifacts`,
    `challenge_tags`, or `cross_artifact_rules`.

What did NOT change:

- No other schema in `v1.2.0/` was edited. Every other schema file is
  byte-identical to the corresponding file in `v1.1.0/`.
- No validator rule code changed. `src/ledgerlinc_ocr/validator/` keeps
  its existing Tier 2 rule set; jsonschema covers the widened type on
  its own.
- Existing artifacts stamped `"1.0.0"` or `"1.1.0"` remain major-compatible
  with the v1.2.0 validator. New preprocessing artifacts and evidence packets
  generated by feature 010 emit `contract_set_version = "1.2.0"` so artifacts
  that may contain nullable structural confidence advertise the contract set
  that permits that shape.

Preservation note: no v1.0.0 or v1.1.0 file was edited. Both remain the
authoritative snapshots for consumers that haven't opted into v1.2.0.
`v1.2.0/` is a strict superset.

Test coverage for the new acceptance shape:

- `tests/contract_tests/fixtures/preprocess_output/confidence_null.json` —
  minimal v1.2.0-stamped fixture carrying one block and one OCR line with
  `confidence: null`.
- `tests/contract_tests/test_preprocess_output_confidence_null.py` —
  validates the fixture against `ArtifactName.PREPROCESS_OUTPUT` using
  the v1.2.0 contract set; a regression that silently reverts the schema
  would fail this test.

## Deferred enhancements (not scheduled)

Proposals captured here are honest signal that a concern is known and valid, but has been deferred from the feature that surfaced it. Each entry should state the motivation, a sketch of the change, and the bump it would require.

### D-001 — Multi-role vendor addresses

**Raised during**: 006-corpus-labeling (T031, HP Indigo invoice had distinct `Sold from` and `Remit To` addresses for the same entity).

**Motivation**: Real vendors commonly print several addresses on a single invoice that play different operational roles. Today `expected_vendor_candidate.address` is a single object, which forces the labeler to pick one and hides the others. The `remit_to_differs_from_vendor` challenge tag is a binary hint but cannot carry the second address.

**Proposed roles to model** (starting point, not final):
1. Legal address (corporate / registered)
2. Mailing address (general correspondence)
3. Physical address (operational site)
4. Ship-from address
5. Ship-to / RMA return address
6. Remit-to address (payment / lockbox)

**Sketch of the change**: replace `expected_vendor_candidate.address` (single object) with either (a) `addresses` (object keyed by role → address) or (b) `address` remains the primary + a new optional `alternate_addresses` array. Option (a) is cleaner; option (b) is more backwards-compatible.

**Version bump**: **MAJOR** — the shape of `expected.schema.json` changes and every existing fixture becomes invalid. Also cascades into `edge_extraction_output` and `final_structured_payload` if consistency is desired across the artifact set.

**Why deferred**: mid-feature contract breakage would re-start the 006 labeling pass and block downstream consumers. Most stage 1 invoices show at most 1–2 addresses, and vendor *identity* does not depend on distinguishing all six roles. Downstream payment / RMA workflows that need role granularity will exist in later stages and are the correct home for this expansion.

**006 workaround**: T064 labeling guide locks `expected_vendor_candidate.address` = primary / sold-from / physical address; remit-to presence is surfaced only via the `remit_to_differs_from_vendor` challenge tag.
