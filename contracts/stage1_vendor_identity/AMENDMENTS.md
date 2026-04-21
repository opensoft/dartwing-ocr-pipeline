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
