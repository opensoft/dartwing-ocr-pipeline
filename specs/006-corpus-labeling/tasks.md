---
description: "Task list for 006-corpus-labeling"
---

# Tasks: Corpus Scaffolding & Human Labeling (Stage 1 Vendor-Identity)

**Input**: Design documents from `/specs/006-corpus-labeling/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included where required by `contracts/validator-delta.md` (the module-API delta mandates ≥5 contract test cases for the new `FOLDER_SOURCE_PDF_UNREADABLE` code). Corpus content has no runtime tests — the validator CLI is the test.

**Organization**: Tasks are grouped by user story so each story is independently implementable and testable per `spec.md` priorities (US1=P1, US2=P1, US3=P2, US4=P3).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable — touches different files with no dependency on any incomplete non-parallel task.
- **[Story]**: Which user story this task belongs to (US1 / US2 / US3 / US4). Setup, Foundational, and Polish tasks have no story label.
- Exact file paths are included in every task description.

## Path Conventions

This is a single-project Python package. Code lives in `src/ledgerlinc_ocr/`, tests in `tests/`, corpus content in `tests/stage1_vendor_identity/`, docs in `docs/stage1-vendor-identity/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the dev environment and existing validator behave as expected before adding the narrow extension.

- [ ] T001 Verify editable dev install works: `python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"` in repo root; confirm `pypdf` and `jsonschema` resolve.
- [ ] T002 Run the existing validator contract tests to establish a green baseline: `.venv/bin/pytest tests/contract_tests/ -q` — must pass before the Phase 2 code change.
- [ ] T003 Verify the validator CLI loads and shows the frozen contract set: `python -m ledgerlinc_ocr.validator show contract-set` — must print `contract_set_version = "1.0.0"` with all 7 artifact schemas plus the folder contract.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Extend the folder validator to enforce FR-003's "readable `source.pdf`" at the structural-parse level (Clarification Q4). Every US1 acceptance scenario depends on this check being present.

**⚠️ CRITICAL**: US1 folder-scaffolding acceptance cannot be validated until Phase 2 is complete.

- [ ] T004 Add `FOLDER_SOURCE_PDF_UNREADABLE = "FOLDER_SOURCE_PDF_UNREADABLE"` to the `ViolationCode` class in `src/ledgerlinc_ocr/validator/report.py`, placed alongside the existing folder codes. Do not reorder or rename any other constants.
- [ ] T005 Extend `validate_folder()` in `src/ledgerlinc_ocr/validator/folder.py` to, for each existing `source.pdf`, (a) assert non-zero file size and (b) attempt `pypdf.PdfReader(path, strict=False)` plus `len(reader.pages)` inside a try/except; on any failure emit one `Violation` with `severity=Severity.ERROR`, `violation_code="FOLDER_SOURCE_PDF_UNREADABLE"`, `field_path="/source.pdf"`, `expected="FR-003 readable source.pdf"`, and `source_file=str(path)`. Skip the check when `source.pdf` is absent (avoid duplicate findings with `FOLDER_MISSING_REQUIRED_FILE`). Depends on T004.
- [ ] T006 [P] Author contract test `tests/contract_tests/test_folder_source_pdf_readability.py` with 5 cases per `contracts/validator-delta.md`: (1) valid minimal PDF passes, (2) missing file emits `FOLDER_MISSING_REQUIRED_FILE` only, (3) zero-byte `source.pdf` emits `FOLDER_SOURCE_PDF_UNREADABLE`, (4) text-file renamed `.pdf` emits `FOLDER_SOURCE_PDF_UNREADABLE`, (5) truncated valid PDF emits `FOLDER_SOURCE_PDF_UNREADABLE`. Each test asserts `violation_code`, `severity`, and `field_path`. Depends on T004.
- [ ] T007 Run `.venv/bin/pytest tests/contract_tests/ -q` — all new cases and all existing tests must pass. Depends on T005, T006.

**Checkpoint**: Validator now enforces PDF structural readability. User story phases can begin.

---

## Phase 3: User Story 1 — Corpus Folder Scaffolding (Priority: P1) 🎯 MVP

**Goal**: 20 per-document folders on disk with real, readable `source.pdf` files, correctly named and distributed 5/5/5/5, passing the folder validator even before any `expected.json` is labeled.

**Independent Test**: `python -m ledgerlinc_ocr.validator validate corpus tests/stage1_vendor_identity` reports 20 documents discovered, 5/5/5/5 distribution, contiguous `inv_001..inv_020`, every folder name matches the pattern, and no `FOLDER_SOURCE_PDF_UNREADABLE` or `FOLDER_RESERVED_FILENAME_COLLISION` errors. (Expected errors at this phase: `FOLDER_MISSING_REQUIRED_FILE` for the still-unwritten `expected.json` files — those resolve in Phase 4.)

### US1 planning

- [ ] T008 [US1] Draft candidate-document shortlist in `specs/006-corpus-labeling/candidates.md` (new file, this feature dir only — not committed to the corpus): at least 25 candidate PDFs (team-held + public samples) with provenance, license note, and intended difficulty bucket per research.md §2. This is a working doc that survives only until T029.
- [ ] T009 [US1] Apply the PII/license screening checklist (research.md §5) to each candidate in `specs/006-corpus-labeling/candidates.md`; mark each as INCLUDE or EXCLUDE with reason. Final include list must be at least 20 passing candidates distributed 5/5/5/5. Depends on T008.

### US1 folder creation (20 parallel placements — different folders)

- [ ] T010 [P] [US1] Create `tests/stage1_vendor_identity/inv_001_easy/` and place `source.pdf` from the approved-easy list.
- [ ] T011 [P] [US1] Create `tests/stage1_vendor_identity/inv_002_easy/` and place `source.pdf`.
- [ ] T012 [P] [US1] Create `tests/stage1_vendor_identity/inv_003_easy/` and place `source.pdf`.
- [ ] T013 [P] [US1] Create `tests/stage1_vendor_identity/inv_004_easy/` and place `source.pdf`.
- [ ] T014 [P] [US1] Create `tests/stage1_vendor_identity/inv_005_easy/` and place `source.pdf`.
- [ ] T015 [P] [US1] Create `tests/stage1_vendor_identity/inv_006_medium/` and place `source.pdf`.
- [ ] T016 [P] [US1] Create `tests/stage1_vendor_identity/inv_007_medium/` and place `source.pdf`.
- [ ] T017 [P] [US1] Create `tests/stage1_vendor_identity/inv_008_medium/` and place `source.pdf`.
- [ ] T018 [P] [US1] Create `tests/stage1_vendor_identity/inv_009_medium/` and place `source.pdf`.
- [ ] T019 [P] [US1] Create `tests/stage1_vendor_identity/inv_010_medium/` and place `source.pdf`.
- [ ] T020 [P] [US1] Create `tests/stage1_vendor_identity/inv_011_hard/` and place `source.pdf` (target at least one of: remit_to_differs_from_vendor, low_quality_scan, faint_text, rotated_scan per research.md §3).
- [ ] T021 [P] [US1] Create `tests/stage1_vendor_identity/inv_012_hard/` and place `source.pdf`.
- [ ] T022 [P] [US1] Create `tests/stage1_vendor_identity/inv_013_hard/` and place `source.pdf`.
- [ ] T023 [P] [US1] Create `tests/stage1_vendor_identity/inv_014_hard/` and place `source.pdf`.
- [ ] T024 [P] [US1] Create `tests/stage1_vendor_identity/inv_015_hard/` and place `source.pdf`.
- [ ] T025 [P] [US1] Create `tests/stage1_vendor_identity/inv_016_missing_name/` and place `source.pdf` (no explicit company name string anywhere on the document — faint-but-present is `hard`, not `missing_name`).
- [ ] T026 [P] [US1] Create `tests/stage1_vendor_identity/inv_017_missing_name/` and place `source.pdf`.
- [ ] T027 [P] [US1] Create `tests/stage1_vendor_identity/inv_018_missing_name/` and place `source.pdf`.
- [ ] T028 [P] [US1] Create `tests/stage1_vendor_identity/inv_019_missing_name/` and place `source.pdf`.
- [ ] T029 [P] [US1] Create `tests/stage1_vendor_identity/inv_020_missing_name/` and place `source.pdf`. After T029, delete `specs/006-corpus-labeling/candidates.md` — its only job was to gate inclusion.

### US1 structural validation

- [ ] T030 [US1] Run `python -m ledgerlinc_ocr.validator validate corpus tests/stage1_vendor_identity` and confirm: 20 folders discovered, 5/5/5/5 distribution, contiguous `inv_001..inv_020`, zero `FOLDER_NAME_INVALID`, zero `FOLDER_SOURCE_PDF_UNREADABLE`, zero `FOLDER_RESERVED_FILENAME_COLLISION`. (Expected failures: `FOLDER_MISSING_REQUIRED_FILE` for absent `expected.json` — deferred to US2.) Depends on T010–T029.

**Checkpoint**: US1 is complete — the corpus exists structurally. US2 labeling can now begin.

---

## Phase 4: User Story 2 — Every Document Has Human-Labeled Expected Truth (Priority: P1)

**Goal**: 20 hand-authored `expected.json` files, one per folder, each conforming to `contracts/stage1_vendor_identity/v1.0.0/expected.schema.json`, with `document_id` and `difficulty` matching the folder name, missing-name invariants satisfied on the 5 missing-name docs, and challenge-tag coverage meeting FR-015/FR-016.

**Independent Test**: `python -m ledgerlinc_ocr.validator validate corpus tests/stage1_vendor_identity` reports zero errors; every `expected.json` validates against the schema; all 5 missing-name docs satisfy the triad (`company_name.present=false`, `company_name.inferred=true`, `manual_review_required=true`, `review_reason="company_name_inferred"`); no document has predicted values / confidence / evaluator verdicts (enforced by `additionalProperties: false`).

### US2 labeling (20 parallel files — different paths)

- [ ] T031 [P] [US2] Author `tests/stage1_vendor_identity/inv_001_easy/expected.json` — non-missing invariants (`company_name.present=true`, `inferred=false`, verbatim `value`). Include `explicit_company_name` in `challenge_tags`.
- [ ] T032 [P] [US2] Author `tests/stage1_vendor_identity/inv_002_easy/expected.json`.
- [ ] T033 [P] [US2] Author `tests/stage1_vendor_identity/inv_003_easy/expected.json`.
- [ ] T034 [P] [US2] Author `tests/stage1_vendor_identity/inv_004_easy/expected.json`.
- [ ] T035 [P] [US2] Author `tests/stage1_vendor_identity/inv_005_easy/expected.json`.
- [ ] T036 [P] [US2] Author `tests/stage1_vendor_identity/inv_006_medium/expected.json` — at least one doc in 006–010 must include `ein_present` (FR-015).
- [ ] T037 [P] [US2] Author `tests/stage1_vendor_identity/inv_007_medium/expected.json`.
- [ ] T038 [P] [US2] Author `tests/stage1_vendor_identity/inv_008_medium/expected.json`.
- [ ] T039 [P] [US2] Author `tests/stage1_vendor_identity/inv_009_medium/expected.json`.
- [ ] T040 [P] [US2] Author `tests/stage1_vendor_identity/inv_010_medium/expected.json` — at least one doc in 006–015 must include one of `vat_id_present` / `state_tax_id_present` / `other_tax_id_present` (FR-015).
- [ ] T041 [P] [US2] Author `tests/stage1_vendor_identity/inv_011_hard/expected.json` — at least one of 011–015 must include `remit_to_differs_from_vendor` + `low_quality_scan` + `logo_only` across the bucket (FR-015 critical tag coverage).
- [ ] T042 [P] [US2] Author `tests/stage1_vendor_identity/inv_012_hard/expected.json`.
- [ ] T043 [P] [US2] Author `tests/stage1_vendor_identity/inv_013_hard/expected.json`.
- [ ] T044 [P] [US2] Author `tests/stage1_vendor_identity/inv_014_hard/expected.json`.
- [ ] T045 [P] [US2] Author `tests/stage1_vendor_identity/inv_015_hard/expected.json`.
- [ ] T046 [P] [US2] Author `tests/stage1_vendor_identity/inv_016_missing_name/expected.json` — missing-name invariants: `company_name.present=false`, `inferred=true`, `manual_review_required=true`, `review_reason="company_name_inferred"`, `challenge_tags` includes `missing_company_name` and EXCLUDES `explicit_company_name` (FR-016).
- [ ] T047 [P] [US2] Author `tests/stage1_vendor_identity/inv_017_missing_name/expected.json`.
- [ ] T048 [P] [US2] Author `tests/stage1_vendor_identity/inv_018_missing_name/expected.json`.
- [ ] T049 [P] [US2] Author `tests/stage1_vendor_identity/inv_019_missing_name/expected.json`.
- [ ] T050 [P] [US2] Author `tests/stage1_vendor_identity/inv_020_missing_name/expected.json`.

### US2 validation

- [ ] T051 [US2] Run `python -m ledgerlinc_ocr.validator validate corpus tests/stage1_vendor_identity` and confirm zero errors across schema, folder, and cross-artifact checks. Specifically confirm: every `expected.json` validates, every `document_id` matches its folder's `inv_NNN` prefix, every `difficulty` matches the folder-name suffix, no `MISSING_NAME_TRIAD_VIOLATION`, no `EXPECTED_HAS_PREDICTIONS`, no `CHALLENGE_TAG_UNKNOWN`. Depends on T031–T050.
- [ ] T052 [US2] Manually audit `challenge_tags` coverage across the 20 labels against FR-015: `explicit_company_name` ≥15 non-missing, `missing_company_name` =5 missing, and at least one document each for `logo_only`, `remit_to_differs_from_vendor`, `low_quality_scan`, `ein_present`, and one of `{vat_id_present, state_tax_id_present, other_tax_id_present}`. If a critical tag is missing, return to the relevant T031–T050 task and re-label. Depends on T051.

**Checkpoint**: US2 is complete — the minimum shippable corpus (US1 + US2) now exists. The evaluator has real labeled truth.

---

## Phase 5: User Story 3 — Reviewer Notes (Priority: P2)

**Goal**: Every `hard` and every `missing_name` document has a non-empty `notes.md` that explains the difficulty choice and at least one concrete trap aligned with that document's `challenge_tags`. `easy` and `medium` documents may (optionally) have `notes.md`.

**Independent Test**: `python -m ledgerlinc_ocr.validator validate corpus tests/stage1_vendor_identity` reports zero hard errors; no `FOLDER_MISSING_REQUIRED_FILE` is emitted for any `hard`/`missing_name` document's `notes.md`. Soft warnings (`FOLDER_NOTES_MISSING_SOFT`) for `easy`/`medium` documents are acceptable.

### US3 hard-required notes (5 hard docs)

- [ ] T053 [P] [US3] Write `tests/stage1_vendor_identity/inv_011_hard/notes.md` — cover (a) why the document is `hard`, (b) at least one concrete trap tied to its `challenge_tags`, and (c) any labeler decision a reviewer would otherwise have to guess.
- [ ] T054 [P] [US3] Write `tests/stage1_vendor_identity/inv_012_hard/notes.md`.
- [ ] T055 [P] [US3] Write `tests/stage1_vendor_identity/inv_013_hard/notes.md`.
- [ ] T056 [P] [US3] Write `tests/stage1_vendor_identity/inv_014_hard/notes.md`.
- [ ] T057 [P] [US3] Write `tests/stage1_vendor_identity/inv_015_hard/notes.md`.

### US3 missing-name notes (5 missing_name docs)

- [ ] T058 [P] [US3] Write `tests/stage1_vendor_identity/inv_016_missing_name/notes.md` — cover (a) why no explicit company name was findable, (b) what was inferred as a best-guess vendor (if any), and (c) which alternative entities on the page (remit-to, parent co., billing-to) were rejected.
- [ ] T059 [P] [US3] Write `tests/stage1_vendor_identity/inv_017_missing_name/notes.md`.
- [ ] T060 [P] [US3] Write `tests/stage1_vendor_identity/inv_018_missing_name/notes.md`.
- [ ] T061 [P] [US3] Write `tests/stage1_vendor_identity/inv_019_missing_name/notes.md`.
- [ ] T062 [P] [US3] Write `tests/stage1_vendor_identity/inv_020_missing_name/notes.md`.

### US3 validation

- [ ] T063 [US3] Run `python -m ledgerlinc_ocr.validator validate corpus tests/stage1_vendor_identity` — confirm zero `FOLDER_MISSING_REQUIRED_FILE` for `notes.md` on any `hard` or `missing_name` folder. Soft `FOLDER_NOTES_MISSING_SOFT` warnings on `easy`/`medium` folders are acceptable. Depends on T053–T062.

**Checkpoint**: US3 is complete — the corpus is now a curated diagnostic instrument, not just a pile of PDFs.

---

## Phase 6: User Story 4 — Labeling Guide (Priority: P3)

**Goal**: A labeling guide at `docs/stage1-vendor-identity/labeling-guide.md` that captures every convention applied to `expected.json` and `notes.md`, plus the PII/license screening checklist, and is cross-linked from the stage 1 doc index and `CLAUDE.md` Key References.

**Independent Test**: The guide exists, contains every section required by research.md §4 (12 sections), enumerates explicit rules for every required `expected.json` key, states the four difficulty definitions, states the missing-name invariants, and embeds the PII/license screening checklist from research.md §5. Cross-links to the guide exist in `docs/stage1-vendor-identity/README.md`, `CLAUDE.md` Key References, and `tests/stage1_vendor_identity/README.md`.

### US4 authoring

- [ ] T064 [US4] Author `docs/stage1-vendor-identity/labeling-guide.md` following the 12-section outline in research.md §4: (1) purpose, (2) PII/license screening checklist (from research.md §5), (3) folder layout and naming, (4) difficulty bucket definitions, (5) `expected.json` field-by-field walk-through, (6) company-name provenance decision tree, (7) remit-to vs vendor selection, (8) DBA vs legal name selection, (9) null-vs-empty-string handling, (10) labeling workflow, (11) dispute resolution, (12) amendment process.
- [ ] T065 [P] [US4] Add a cross-link to `docs/stage1-vendor-identity/README.md` pointing at `labeling-guide.md` with a one-line description. Depends on T064.
- [ ] T066 [P] [US4] Add `docs/stage1-vendor-identity/labeling-guide.md — conventions for `expected.json` and `notes.md`, PII/license screening checklist` to the Key References list in `CLAUDE.md`. Depends on T064.
- [ ] T067 [P] [US4] Update `tests/stage1_vendor_identity/README.md`'s "Labeling" section to cite `docs/stage1-vendor-identity/labeling-guide.md` as the authoritative reference (in addition to the existing `dataset-layout.md` and `schemas.md` entries). Depends on T064.

### US4 validation

- [ ] T068 [US4] Self-review against SC-007 guide-completeness criteria: confirm every required key in `expected.schema.json` has at least one explicit rule in the guide; every difficulty bucket is defined; every missing-name invariant is stated verbatim; the PII checklist matches research.md §5 exactly. Document the review result inline at the top of `docs/stage1-vendor-identity/labeling-guide.md` or in a short comment in this task. Depends on T064–T067.

**Checkpoint**: US4 is complete — future labelers have a single point of reference.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final corpus-wide validation, success-criteria audit, and documentation closure.

- [ ] T069 Run the full validator: `python -m ledgerlinc_ocr.validator validate corpus tests/stage1_vendor_identity` — exit code MUST be 0, zero hard errors (SC-001). Soft `FOLDER_NOTES_MISSING_SOFT` warnings on `easy`/`medium` folders are acceptable.
- [ ] T070 Run the full test suite: `.venv/bin/pytest tests/ -q` — all tests green, including the 5 new cases in `tests/contract_tests/test_folder_source_pdf_readability.py`.
- [ ] T071 Audit Success Criteria SC-001 through SC-009 against the shipped corpus; for each SC, record PASS with the command/evidence in a brief note appended to `specs/006-corpus-labeling/plan.md` under a new "## Acceptance Evidence" section.
- [ ] T072 Sweep the corpus for any reserved generated filename (`preprocess_output.json`, `edge_extraction_output.json`, `routing_decision.json`, `final_structured_payload.json`, `evaluation_document.json`) or `votes/` subdirectory or `consensus_output.json` file; fail-closed (FR-013, FR-020). Confirm zero hits.
- [ ] T073 [P] Verify the `CLAUDE.md` Key References section, `docs/stage1-vendor-identity/README.md`, and `tests/stage1_vendor_identity/README.md` all cross-link correctly to the labeling guide and render without broken relative links.
- [ ] T074 [P] Tick the items in `specs/006-corpus-labeling/checklists/labeling-guide.md`, `governance.md`, `coverage.md`, and `invariants.md` whose underlying requirement was resolved by this feature's outputs; leave `[Gap]` items open only if intentionally deferred, with a one-line reason.

---

## Dependencies

```text
Phase 1 (Setup)
  T001 → T002 → T003

Phase 2 (Foundational — blocks US1)
  T004 (new ViolationCode) → T005 (validator extension) → T007 (pytest)
  T004 → T006 (tests) → T007 (pytest)

Phase 3 (US1 — P1)
  T008 → T009 (screening) → T010..T029 (folder placements, [P]) → T030 (validate)

Phase 4 (US2 — P1; depends on US1 complete)
  T030 → T031..T050 ([P]) → T051 (validate) → T052 (coverage audit)

Phase 5 (US3 — P2; depends on US2 complete)
  T051 → T053..T062 ([P]) → T063 (validate)

Phase 6 (US4 — P3; depends only on research; can begin in parallel with Phase 4/5
          but is ordered after US2/US3 per spec priority)
  T064 → T065,T066,T067 ([P]) → T068

Phase 7 (Polish — after all stories)
  T069 → T070 → T071 → T072 → T073,T074 ([P])
```

### Parallel execution examples

- **Phase 2** T006 (tests) runs in parallel with T005 (validator extension). Both depend on T004.
- **Phase 3** T010..T029 (20 folder placements) can run fully in parallel. Each touches a different folder; none writes to shared files.
- **Phase 4** T031..T050 (20 `expected.json` authorings) can run fully in parallel. Each touches a different `expected.json` path.
- **Phase 5** T053..T062 (10 `notes.md` writes) can run fully in parallel.
- **Phase 6** T065, T066, T067 can run in parallel after T064; each touches a different file.

---

## MVP scope

**Minimum shippable increment**: Phase 1 + Phase 2 + Phase 3 (US1) + Phase 4 (US2). This delivers the labeled corpus in enough shape for downstream extraction and evaluation slices to run against real labeled truth. US3 (`notes.md`) and US4 (labeling guide) are quality-of-life deliverables that improve future auditability; they are NOT on the MVP critical path even though FR-011 requires notes for `hard`/`missing_name` by end of feature.

**Full feature acceptance**: Phase 1 through Phase 7. SC-001 through SC-009 all pass. US4's guide-completeness is reviewed (SC-007 is measured by guide structure, not by running an outside reviewer — per Clarification Q3).

---

## Implementation strategy

1. **Setup + Foundational first (Phases 1–2)**: Do not touch any corpus content before the validator extension is in and tested. Without it, US1's structural check is weaker than FR-003 requires.
2. **Build the MVP in one pass (Phases 3–4)**: Candidate shortlist → screening → 20 folder placements → 20 `expected.json` labels → corpus validation. This is the hard part; everything downstream is gravy.
3. **Add notes and guide incrementally (Phases 5–6)**: Each `notes.md` is small. The labeling guide can be drafted as labeling progresses — its content is already substantially specified in research.md §4 so T064 is mostly transcription plus examples.
4. **Close with Polish (Phase 7)**: Full corpus + test-suite validation, SC audit, checklist tick-through.

Parallel opportunities are heavy inside each user story (20 folders / 20 labels / 10 notes) but single-labeler human work makes them sequential in practice. The [P] markers reflect code-level independence so future automation or multi-labeler workflows can parallelize without re-planning.
