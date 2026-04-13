---

description: "Task list for feature 001-freeze-schemas-folder-contracts"
---

# Tasks: Freeze Schemas & Folder Contracts

**Input**: Design documents from `/specs/001-freeze-schemas-folder-contracts/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (all present)

**Tests**: INCLUDED. SC-002 requires that 100% of required rules, enumerations, nullability rules, and cross-artifact rules are enforced by the validator (not just documented). Research R3 partitions rules into Tier 1 (JSON Schema) and Tier 2 (Python). A test suite with fixture-driven good/bad cases is the only way to prove both tiers cover every FR — so tests are first-class tasks. Follow TDD within each story: the fixtures and test files land before the implementation they exercise.

**Organization**: Tasks are grouped by the four user stories from spec.md (three P1, one P2). Each user story is independently testable — when a story's phase completes, its `Independent Test` criterion from spec.md can be executed against the built system.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User-story phase tasks only; Setup / Foundational / Polish tasks omit it
- File paths are absolute to repo root `/workspace/projects/ledgerlinc/ledgerlinc-model-ocr-pipeline/` unless stated otherwise

## Path Conventions

Single-project Python layout per `plan.md > Project Structure`:

- Runtime contract layer: `contracts/stage1_vendor_identity/v1.0.0/`
- Validator source: `src/ledgerlinc_ocr/validator/`
- Runtime corpus root: `tests/stage1_vendor_identity/` (empty scaffold in this feature)
- Test suite for this feature: `tests/contract_tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish Python packaging, source tree, and empty scaffolds so downstream tasks can drop files in known locations.

- [X] T001 Create `pyproject.toml` at repo root declaring the `ledgerlinc_ocr` package under `src/` (src-layout), Python `>=3.12`, runtime deps `jsonschema>=4.22,<5` and `pydantic>=2.7,<3`, dev deps `pytest>=8.2,<9`, and a `[tool.pytest.ini_options]` block scoped to `tests/contract_tests/`
- [X] T002 [P] Create source package skeleton: empty `src/ledgerlinc_ocr/__init__.py`, `src/ledgerlinc_ocr/validator/__init__.py`, `src/ledgerlinc_ocr/validator/__main__.py` (stub calling `cli.main()`), and empty stub files `cli.py`, `loader.py`, `artifact.py`, `folder.py`, `corpus.py`, `cross_artifact.py`, `report.py`, `version.py` inside `src/ledgerlinc_ocr/validator/`
- [X] T003 [P] Create runtime contract layer skeleton: `contracts/stage1_vendor_identity/v1.0.0/` directory, plus empty placeholder files for the seven artifact schemas (`preprocess_output.schema.json`, `edge_extraction_output.schema.json`, `routing_decision.schema.json`, `final_structured_payload.schema.json`, `expected.schema.json`, `evaluation_document.schema.json`, `evaluation_run_summary.schema.json`) and `folder.schema.json` — files contain only `{}` until their owning story fills them
- [X] T004 [P] Create test-suite scaffold: `tests/contract_tests/__init__.py`, `tests/contract_tests/fixtures/good/`, `tests/contract_tests/fixtures/bad/`, and the runtime corpus root `tests/stage1_vendor_identity/.gitkeep`
- [X] T005 Install the package in editable mode with `pip install -e .` and verify `python -c "import ledgerlinc_ocr.validator"` succeeds inside the devcontainer

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build the parts of the validator and contract-set machinery that every user story depends on — report shape, contract-set loader, generic JSON-Schema validator, CLI skeleton, and shared test scaffolding. No story-specific artifact contract is written yet; those land in their own stories.

**⚠️ CRITICAL**: No user-story phase work can begin until this phase is complete.

- [X] T006 Write `contracts/stage1_vendor_identity/v1.0.0/contract_set.json` with fields `contract_set_version: "1.0.0"`, `artifact_schemas` map (seven keys pointing to their `*.schema.json` siblings — files exist but are empty until later stories), `folder_schema` path, `challenge_tags: []` (populated in US2), `cross_artifact_rules: []` (populated per story), and `artifact_names` list of the seven names
- [X] T007 [P] Write `src/ledgerlinc_ocr/validator/report.py` with: `Severity` str-enum (`error`, `warning`); `ArtifactName` str-enum (the seven names); `ViolationCode` constants module exposing every stable code from `data-model.md` (`SCHEMA_REQUIRED_MISSING`, `NULL_VS_EMPTY_STRING`, `CONTRACT_SET_VERSION_INCOMPATIBLE`, `CHALLENGE_TAG_UNKNOWN`, `TAX_ID_TYPE_INVALID`, `VOTE_METADATA_MISSING`, `REVIEW_REASON_NULL_WHEN_REQUIRED`, `EXPECTED_HAS_PREDICTIONS`, `MISSING_NAME_TRIAD_VIOLATION`, `PROVENANCE_TRIAD_INCONSISTENT`, `EVIDENCE_REFERENCE_UNRESOLVED`, `DOCUMENT_COUNT_MISMATCH`, `FOLDER_MISSING_REQUIRED_FILE`, `FOLDER_NOTES_MISSING_SOFT`, `FOLDER_NAME_INVALID`, `FOLDER_RESERVED_FILENAME_COLLISION`, `SCHEMA_TYPE_MISMATCH`, `SCHEMA_ENUM_VIOLATION`, `SCHEMA_PATTERN_VIOLATION`, `SCHEMA_ADDITIONAL_PROPERTIES`, `PIPELINE_VERSION_MISSING`, `POLICY_VERSION_MISSING`, `CONTRACT_SET_VERSION_MISSING`); `Violation` Pydantic model with fields `severity`, `target`, `field_path`, `violation_code`, `reason`, `expected`, `source_file`; `ValidationOutcome` Pydantic model conforming 1:1 to `specs/001-freeze-schemas-folder-contracts/contracts/report.schema.json`
- [X] T008 [P] Write `src/ledgerlinc_ocr/validator/loader.py` exposing `ContractSet` dataclass (`version`, `artifact_schemas`, `folder_schema`, `challenge_tags`, `cross_artifact_rules`), exceptions `ContractSetNotFoundError` and `ContractSetCorruptError`, and `load_contract_set(version: str | None)` that scans `contracts/stage1_vendor_identity/` for the requested version (or picks the latest) and validates `contract_set.json` references resolve
- [X] T009 [P] Write `src/ledgerlinc_ocr/validator/version.py` with `parse_semver(s) -> tuple[int, int, int]`, `is_compatible(artifact_version, validator_version) -> bool` (stage 1 rule: major-equal, minor/patch ignored), and helper to format `CONTRACT_SET_VERSION_INCOMPATIBLE` violations
- [X] T010 Write `src/ledgerlinc_ocr/validator/artifact.py` implementing `validate_artifact(path, contract, *, version)` using `jsonschema.Draft202012Validator.iter_errors(...)`, mapping each `ValidationError` to a `Violation` via a keyword→violation-code table (e.g. `required` → `SCHEMA_REQUIRED_MISSING`, `type` → `SCHEMA_TYPE_MISMATCH`, `enum` → `SCHEMA_ENUM_VIOLATION`, `pattern` → `SCHEMA_PATTERN_VIOLATION`, `additionalProperties` → `SCHEMA_ADDITIONAL_PROPERTIES`), plus explicit checks for `NULL_VS_EMPTY_STRING` (empty-string values under `value`-typed fields), `CONTRACT_SET_VERSION_MISSING`, `PIPELINE_VERSION_MISSING`, and `POLICY_VERSION_MISSING`; returns a `ValidationOutcome`; depends on T007, T008, T009
- [X] T011 Write `src/ledgerlinc_ocr/validator/cli.py` with argparse subcommands `validate artifact`, `validate folder`, `validate corpus`, `show contract-set`, each supporting `--json` / `--text` mutually exclusive flags and `--contract-set-version`; define exit codes (`0` pass, `1` validation fail, `2` usage, `3` internal); wire only the `artifact` and `show contract-set` subcommands for now, leaving `folder` and `corpus` to fail with exit code 2 until their owning stories wire them; depends on T010
- [X] T012 Write `src/ledgerlinc_ocr/validator/__init__.py` re-exporting the public surface promised by `specs/001-freeze-schemas-folder-contracts/contracts/module-api.md` (`ArtifactName`, `Severity`, `Violation`, `ValidationOutcome`, `ContractSet`, `load_contract_set`, `validate_artifact`, `validate_folder`, `validate_corpus`, `ContractSetNotFoundError`, `ContractSetCorruptError`, `InvalidArtifactNameError`) — the two yet-unimplemented functions (`validate_folder`, `validate_corpus`) are imported from their stub modules and raise `NotImplementedError` until US2/US3 land
- [X] T013 [P] Write `tests/contract_tests/conftest.py` with pytest fixtures for the contract-set path (`contracts/stage1_vendor_identity/v1.0.0/`), fixture root (`tests/contract_tests/fixtures/`), and helper functions `load_good(artifact)` / `load_bad(name)` that return parsed JSON
- [X] T014 [P] Write `tests/contract_tests/test_report_shape.py` asserting that a `ValidationOutcome.model_dump(mode="json")` validates against `specs/001-freeze-schemas-folder-contracts/contracts/report.schema.json` for both pass and fail cases (use synthetic `Violation` instances); depends on T007
- [X] T015 [P] Write `tests/contract_tests/test_version_stamping.py` covering, parametrized over every applicable artifact type: (a) missing `contract_set_version` produces `CONTRACT_SET_VERSION_MISSING`; (b) a mismatched major version against the validator target produces `CONTRACT_SET_VERSION_INCOMPATIBLE`; (c) matching major version but different minor/patch passes; (d) missing `pipeline_version` on any pipeline-produced artifact (`preprocess_output`, `edge_extraction_output`, `routing_decision`, `final_structured_payload`) produces `PIPELINE_VERSION_MISSING`; (e) missing `policy_version` on `routing_decision` produces `POLICY_VERSION_MISSING`; (f) `expected`, `evaluation_document`, and `evaluation_run_summary` do NOT require `pipeline_version` / `policy_version` and must pass without them; depends on T009, T010

**Checkpoint**: The validator can load contract-set `1.0.0`, run the generic JSON-Schema path against any schema (empty schemas treat every document as valid), emit a conforming structured report, and signal pass/fail via exit code. User-story phases can now begin in parallel.

---

## Phase 3: User Story 1 — Pipeline Developer Codes Against a Frozen Artifact Shape (Priority: P1) 🎯 MVP

**Goal**: Deliver frozen JSON-Schema contracts for the four pipeline artifacts (`preprocess_output`, `edge_extraction_output`, `routing_decision`, `final_structured_payload`) plus the cross-artifact provenance-triad rule. A pipeline developer can validate any of the four artifacts end-to-end via `python -m ledgerlinc_ocr.validator validate artifact` and receive machine-readable or human-readable results with exit codes.

**Independent Test**: From spec.md US1 — hand-write a sample `edge_extraction_output.json` that conforms to `contracts/stage1_vendor_identity/v1.0.0/edge_extraction_output.schema.json`, run `python -m ledgerlinc_ocr.validator validate artifact` against it, observe exit `0`; introduce a deliberate violation (empty string for null, missing `vote_metadata`, invalid tax-ID type, `present = false` without `inferred = true`), re-run, observe exit `1` and a violation list that points at the field path.

### Tests for User Story 1 (written before implementation-heavy tasks) ⚠️

> **NOTE**: Each test here must FAIL until its corresponding implementation task lands.

- [X] T016 [P] [US1] Write `tests/contract_tests/fixtures/good/preprocess_output.json` — one conforming sample with two pages, block/line IDs matching `^p\d+_b\d+$` / `^p\d+_l\d+$`, `ingestion_sources.paddleocr_vl.status = "success"` and both Falcon entries `status = "not_implemented"`, stamped with `contract_set_version: "1.0.0"`
- [X] T017 [P] [US1] Write `tests/contract_tests/fixtures/good/edge_extraction_output.json` — conforming sample with every vendor-identity field present, `vote_metadata.consensus_mode = "single_voter_baseline"`, every `evidence[]` referencing IDs present in `good/preprocess_output.json`, invoice-header fields populated, `contract_set_version: "1.0.0"`
- [X] T018 [P] [US1] Write `tests/contract_tests/fixtures/good/routing_decision.json` — `decision = "edge_accept"`, `consensus_summary = {mode: "single_voter_baseline", agreement_level: "not_applicable"}`, all scores in `[0,1]`, all check booleans set, `review_status.manual_review_required = false`, `review_status.review_reason = null`
- [X] T019 [P] [US1] Write `tests/contract_tests/fixtures/good/final_structured_payload.json` — flattened vendor fields, `company_name.present = true`, `company_name.inferred = false`, trace block pointing at sibling files in the per-document folder
- [X] T020 [P] [US1] Write `tests/contract_tests/fixtures/bad/empty_string_for_null.json` — a copy of good `edge_extraction_output.json` with `vendor_candidate.phone.value = ""` (must trigger `NULL_VS_EMPTY_STRING`)
- [X] T021 [P] [US1] Write `tests/contract_tests/fixtures/bad/missing_vote_metadata.json` — good `edge_extraction_output.json` with `vote_metadata` removed (must trigger `VOTE_METADATA_MISSING`)
- [X] T022 [P] [US1] Write `tests/contract_tests/fixtures/bad/tax_id_invalid_type.json` — good `edge_extraction_output.json` with an extra `tax_ids.sales_tax` key (must trigger `TAX_ID_TYPE_INVALID` via `additionalProperties: false` on `tax_ids`)
- [X] T023 [P] [US1] Write `tests/contract_tests/fixtures/bad/review_reason_null_when_required.json` — good `routing_decision.json` with `manual_review_required = true` and `review_reason = null` (must trigger `REVIEW_REASON_NULL_WHEN_REQUIRED`)
- [X] T024 [P] [US1] Write `tests/contract_tests/fixtures/bad/inferred_without_review_required.json` — good `final_structured_payload.json` with `company_name.present = false`, `company_name.inferred = true`, and `review_status.manual_review_required = false` (must trigger `MISSING_NAME_TRIAD_VIOLATION`)
- [X] T025 [P] [US1] Write `tests/contract_tests/fixtures/bad/evidence_reference_unresolved.json` — good `edge_extraction_output.json` paired with good `preprocess_output.json`, but with `vendor_candidate.company_name.evidence = ["p1_l999"]` (must trigger `EVIDENCE_REFERENCE_UNRESOLVED` when the pair is validated together)
- [X] T026 [P] [US1] Write `tests/contract_tests/test_artifact_contracts.py` covering: (a) every good fixture from T016–T019 passes; (b) every bad fixture from T020–T024 fails with the expected `violation_code`; (c) the `violation` entries carry non-empty `field_path` pointers for every per-field rule
- [X] T027 [P] [US1] Write `tests/contract_tests/test_cross_artifact.py` covering: (a) the provenance triad accepts consistent quadruples (`expected` ↔ `edge_extraction_output` ↔ `routing_decision` ↔ `final_structured_payload`) across a synthetic folder; (b) flipping any one of the four triad fields produces `PROVENANCE_TRIAD_INCONSISTENT`; (c) unresolved evidence IDs produce `EVIDENCE_REFERENCE_UNRESOLVED`
- [X] T028 [P] [US1] Write `tests/contract_tests/test_cli_artifact.py` covering: (a) `validate artifact --contract edge_extraction_output <good>` returns exit `0` and empty `violations`; (b) same command against `bad/empty_string_for_null.json` returns exit `1` with at least one `NULL_VS_EMPTY_STRING`; (c) `--json` output parses and matches the report schema; (d) `--text` output contains the violation code and field path

### Implementation for User Story 1

- [X] T029 [P] [US1] Write `contracts/stage1_vendor_identity/v1.0.0/preprocess_output.schema.json` — JSON Schema Draft 2020-12 covering FR-006, FR-007, FR-008, FR-003, FR-004, FR-005a. `additionalProperties: false` at the top level and at each `block` / `raw_ocr_line` / `ingestion_sources.*`; `pages[].blocks[].block_id` and `pages[].raw_ocr_lines[].line_id` constrained by patterns `^p\d+_b\d+$` and `^p\d+_l\d+$`; `ingestion_sources.{paddleocr_vl, falcon_ocr, falcon_perception}.status` enum of `success | failure | not_implemented`
- [X] T030 [P] [US1] Write `contracts/stage1_vendor_identity/v1.0.0/edge_extraction_output.schema.json` — covers FR-009, FR-010, FR-011, FR-012, FR-013, FR-003, FR-005a. `vote_metadata` required with `consensus_mode` enum (`single_voter_baseline` plus forward-compatible values); `vendor_candidate.tax_ids` has `additionalProperties: false` and exactly the four typed keys (`ein`, `state_tax_id`, `vat_id`, `other_tax_id`); address decomposed into the six documented fields; every `value`-typed field uses `{type: [string, null]}` or `{type: [number, null]}` and forbids empty strings via `{"not": {"const": ""}}`
- [X] T031 [P] [US1] Write `contracts/stage1_vendor_identity/v1.0.0/routing_decision.schema.json` — covers FR-014, FR-015, FR-016, FR-017, FR-005, FR-005a. `decision` enum (`edge_accept`, `edge_review_required`, with `$comment` noting forward-compatibility); `consensus_summary` required; `review_status` uses `if / then` so `review_reason` cannot be `null` when `manual_review_required = true`
- [X] T032 [P] [US1] Write `contracts/stage1_vendor_identity/v1.0.0/final_structured_payload.schema.json` — covers FR-018, FR-019, FR-005a. Flattened `vendor_candidate` with `{value, confidence}` pairs; `company_name` additionally carries `{present, inferred}`; `trace` block required; the missing-name triad (`present = false` ⇒ `inferred = true` ∧ `manual_review_required = true`) expressed as an `if / then` / `else` block that surfaces as `MISSING_NAME_TRIAD_VIOLATION` at the field-mapping layer
- [X] T033 [US1] Update `contracts/stage1_vendor_identity/v1.0.0/contract_set.json` to register the four pipeline artifact schemas (set their `artifact_schemas` entries to the real file paths) and to add `PROVENANCE_TRIAD_INCONSISTENT` + `EVIDENCE_REFERENCE_UNRESOLVED` to `cross_artifact_rules`
- [X] T034 [US1] Implement `src/ledgerlinc_ocr/validator/cross_artifact.py` with `check_provenance_triad(artifacts: dict[ArtifactName, JSONDoc]) -> list[Violation]` and `check_evidence_references(preprocess: JSONDoc, extraction: JSONDoc) -> list[Violation]`; map their outputs into `ValidationOutcome` via the keyword-driven table established in T010
- [X] T035 [US1] Extend `src/ledgerlinc_ocr/validator/artifact.py` so that `validate_artifact` augments the jsonschema-driven violations with a missing-name triad check on `final_structured_payload` artifacts (turning the schema-level `if/then` flag into a `MISSING_NAME_TRIAD_VIOLATION` code with a precise field path)
- [X] T036 [US1] Extend `src/ledgerlinc_ocr/validator/cli.py` so that when more than one artifact is validated in sequence (either via repeated `validate artifact` or via folder/corpus modes wired later) the provenance-triad and evidence-reference checks run automatically; keep single-artifact invocations scoped to in-file checks only

**Checkpoint**: A pipeline developer can now hand-write any of the four pipeline artifacts, validate it individually, and get deterministic pass/fail + itemized violations. Cross-artifact rules run when multiple pipeline artifacts are submitted together.

---

## Phase 4: User Story 2 — Human Labeler Produces Truth Against a Frozen Folder Layout (Priority: P1)

**Goal**: Deliver the frozen `expected.json` contract, the folder contract (including the conditional `notes.md` rule from clarification 5), and the `validate folder` CLI path. A labeler can create `tests/stage1_vendor_identity/inv_XXX_<difficulty>/`, drop in `source.pdf` + `expected.json` + `notes.md`, and validate the whole folder without touching any pipeline code.

**Independent Test**: From spec.md US2 — create `tests/stage1_vendor_identity/inv_099_easy/`, add an empty placeholder `source.pdf`, author an `expected.json` from the frozen contract, run `python -m ledgerlinc_ocr.validator validate folder <path>`, confirm pass. Delete `notes.md` and confirm a WARNING (not an error) for easy/medium. Change `difficulty` to `hard` and confirm the missing `notes.md` becomes an error. Introduce a `challenge_tag` not in `dataset-layout.md` and confirm `CHALLENGE_TAG_UNKNOWN`.

### Tests for User Story 2 ⚠️

- [X] T037 [P] [US2] Write `tests/contract_tests/fixtures/good/expected_explicit_easy.json` — an `easy` document with explicit company name, full address, EIN, `challenge_tags` drawn only from the closed vocabulary, `contract_set_version: "1.0.0"`, no `confidence` / `predicted` / evaluation fields
- [X] T038 [P] [US2] Write `tests/contract_tests/fixtures/good/expected_missing_name.json` — a `missing_name` document with `company_name.present = false`, `company_name.inferred = true`, `company_name.value` set to a best-guess string, `expected_review.manual_review_required = true`, `expected_review.review_reason = "company_name_inferred"`
- [X] T039 [P] [US2] Write `tests/contract_tests/fixtures/good/folder_inv_001_easy/` with `source.pdf` (empty placeholder), `expected.json` (symlink or copy of `expected_explicit_easy.json` with `document_id = "inv_001"`), and `notes.md`
- [X] T040 [P] [US2] Write `tests/contract_tests/fixtures/bad/expected_contains_confidence.json` — good explicit-easy with an added `expected_vendor_candidate.company_name.confidence = 0.9` (must trigger `EXPECTED_HAS_PREDICTIONS` via `additionalProperties: false`)
- [X] T041 [P] [US2] Write `tests/contract_tests/fixtures/bad/expected_unknown_challenge_tag.json` — good explicit-easy with `challenge_tags = ["explicit_company_name", "not_a_real_tag"]` (must trigger `CHALLENGE_TAG_UNKNOWN`)
- [X] T042 [P] [US2] Write `tests/contract_tests/fixtures/bad/folder_missing_notes_hard/` — valid folder structure except `notes.md` absent AND `expected.json.difficulty = "hard"` (must trigger `FOLDER_MISSING_REQUIRED_FILE` with severity `error`)
- [X] T043 [P] [US2] Write `tests/contract_tests/fixtures/bad/folder_missing_notes_easy/` — valid folder structure except `notes.md` absent AND `expected.json.difficulty = "easy"` (must produce a `FOLDER_NOTES_MISSING_SOFT` WARNING, not an error; `passed = true`)
- [X] T044 [P] [US2] Write `tests/contract_tests/fixtures/bad/folder_missing_source_pdf/` — folder missing `source.pdf` (must trigger `FOLDER_MISSING_REQUIRED_FILE` severity `error`)
- [X] T045 [P] [US2] Write `tests/contract_tests/fixtures/bad/folder_name_invalid/` — a folder named `invoice_001_easy/` instead of `inv_001_easy/` (must trigger `FOLDER_NAME_INVALID`)
- [X] T045a [P] [US2] Write `tests/contract_tests/fixtures/bad/folder_reserved_filename_collision/` — a valid `inv_002_easy` folder whose operator has dropped a hand-authored `preprocess_output.json` alongside `source.pdf` and `expected.json` before any pipeline run, with no evidence of pipeline provenance (missing `pipeline_version` or missing `contract_set_version` on that file). Must trigger `FOLDER_RESERVED_FILENAME_COLLISION` with severity `error` on that file.
- [X] T046 [P] [US2] Write `tests/contract_tests/test_expected_contract.py` — exercises good + bad expected fixtures; asserts missing-name rule enforced (FR-024)
- [X] T047 [P] [US2] Write `tests/contract_tests/test_folder_contract.py` — exercises all folder fixtures (T039, T042, T043, T044, T045, T045a); explicitly asserts that `folder_missing_notes_easy` returns `passed = true` with exactly one warning, and that `folder_reserved_filename_collision` returns `passed = false` with a `FOLDER_RESERVED_FILENAME_COLLISION` violation naming the offending file
- [X] T048 [P] [US2] Write `tests/contract_tests/test_cli_folder.py` — exercises `validate folder` CLI path on a good folder (exit 0, no warnings beyond the expected `notes.md` soft-miss case) and a bad folder (exit 1); confirms `--json` output aggregates folder-level and artifact-level violations under one `ValidationOutcome`

### Implementation for User Story 2

- [X] T049 [P] [US2] Write `contracts/stage1_vendor_identity/v1.0.0/expected.schema.json` — covers FR-020 through FR-024. `additionalProperties: false` at every level (hard-blocks predictions and confidence); `difficulty` enum; `challenge_tags[]` enforced via `uniqueItems: true` plus an enum generated from the closed vocabulary in `dataset-layout.md`; an `if / then` block enforcing the missing-name triad on `difficulty = missing_name`
- [X] T050 [P] [US2] Write `contracts/stage1_vendor_identity/v1.0.0/folder.schema.json` — a JSON description (not a JSON-of-file schema) of per-document and corpus-root folder rules: allowed folder-name patterns, required input files by difficulty, reserved generated filenames, reserved ensemble names. Consumed by `folder.py` rather than by `jsonschema`
- [X] T051 [US2] Update `contracts/stage1_vendor_identity/v1.0.0/contract_set.json` to: (a) add `expected` artifact schema path; (b) set `folder_schema` path; (c) populate `challenge_tags` with the 17 tags from `docs/stage1-vendor-identity/dataset-layout.md` exactly (`explicit_company_name`, `missing_company_name`, `logo_only`, `footer_only`, `address_only`, `website_present`, `email_domain_present`, `ein_present`, `state_tax_id_present`, `vat_id_present`, `other_tax_id_present`, `multi_entity_page`, `remit_to_differs_from_vendor`, `low_quality_scan`, `rotated_scan`, `dense_header`, `portal_cover_page`, `faint_text`)
- [X] T052 [US2] Implement `src/ledgerlinc_ocr/validator/folder.py` — parses folder name (`^inv_\d{3}_(easy|medium|hard|missing_name)$`) into `FolderInspection`, loads `expected.json` to confirm `difficulty` matches folder suffix (emit `FOLDER_NAME_INVALID` on mismatch), enforces FR-029 conditional `notes.md` rule, detects reserved-filename presence on files that are not among the pipeline-generated set, returns a `ValidationOutcome`
- [X] T053 [US2] Wire `validate folder` subcommand in `src/ledgerlinc_ocr/validator/cli.py` to `folder.py`, replacing the T011 stub; ensure folder-mode invocation also runs `cross_artifact.check_provenance_triad` when the four pipeline artifacts are all present in the folder
- [X] T054 [US2] Add `src/ledgerlinc_ocr/validator/__init__.py` concrete `validate_folder` (replacing the `NotImplementedError` stub from T012)
- [X] T055 [US2] Write `tests/stage1_vendor_identity/README.md` pointing labelers at `docs/stage1-vendor-identity/dataset-layout.md`, the `expected` contract, and the `python -m ledgerlinc_ocr.validator validate folder` quickstart

**Checkpoint**: Labeling work can proceed in parallel with pipeline development. A labeler authors `expected.json` + `notes.md`, validates the folder, and gets deterministic, readable feedback.

---

## Phase 5: User Story 3 — Evaluator Compares Outputs Against Frozen Evaluation Contracts (Priority: P1)

**Goal**: Deliver the two evaluation-artifact contracts (`evaluation_document`, `evaluation_run_summary`) and the `validate corpus` CLI path. An evaluator developer can hand-write evaluation artifacts (before the real evaluator exists) and confirm their shape; the harness can validate the whole corpus in one invocation and aggregate failures across 20 documents (FR-036b).

**Independent Test**: From spec.md US3 — hand-write an `evaluation_document.json` for one document and an `evaluation_run_summary.json` for a fake 20-document run, run `python -m ledgerlinc_ocr.validator validate artifact --contract evaluation_document/summary` against each, confirm pass; make `document_count` disagree with `documents[]` length and confirm `DOCUMENT_COUNT_MISMATCH`; run `validate corpus` against a corpus containing a mix of good and bad document folders and confirm `sub_reports[]` contains one entry per folder plus one for the root-level summary.

### Tests for User Story 3 ⚠️

- [X] T056 [P] [US3] Write `tests/contract_tests/fixtures/good/evaluation_document.json` — covers every result vocabulary value (`match`, `partial_match`, `mismatch`, `missing_prediction`, `unexpected_prediction`, `not_applicable`) across at least eight `field_results` entries and the three document-level pass gates
- [X] T057 [P] [US3] Write `tests/contract_tests/fixtures/good/evaluation_run_summary.json` — 20-document fake run, `document_count = 20`, `documents[]` length 20, all per-difficulty buckets populated, `consensus_metrics.single_voter_baseline_runs = 20`, ensemble-only fields absent
- [X] T058 [P] [US3] Write `tests/contract_tests/fixtures/bad/evaluation_document_invalid_result.json` — good `evaluation_document.json` with one `field_results.*.result = "partial"` (not in the fixed vocabulary; must trigger `SCHEMA_ENUM_VIOLATION`)
- [X] T059 [P] [US3] Write `tests/contract_tests/fixtures/bad/evaluation_run_summary_document_count_mismatch.json` — good `evaluation_run_summary.json` with `document_count = 20` and `documents[]` length 19 (must trigger `DOCUMENT_COUNT_MISMATCH`)
- [X] T060 [P] [US3] Write `tests/contract_tests/test_evaluation_contracts.py` — good + bad fixtures for both evaluation artifacts; explicit assertion that single-voter-baseline `consensus_metrics` passes
- [X] T061 [P] [US3] Write `tests/contract_tests/test_corpus_aggregation.py` — synthetic corpus at `tests/contract_tests/fixtures/good/corpus_sample/` containing two valid document folders plus one invalid one plus a `evaluation_run_summary.json`; asserts `validate_corpus` returns `passed = false`, `sub_reports` length 4, and exactly one `sub_report` per folder/summary

### Implementation for User Story 3

- [X] T062 [P] [US3] Write `contracts/stage1_vendor_identity/v1.0.0/evaluation_document.schema.json` — covers FR-025, FR-026, FR-005a. `field_results` is an object with arbitrary string keys (dotted field paths) and values `{expected, actual, result}`; `result` is the enum of six fixed vocabulary values; `document_pass_fail` required with its three boolean gates
- [X] T063 [P] [US3] Write `contracts/stage1_vendor_identity/v1.0.0/evaluation_run_summary.schema.json` — covers FR-027, FR-005a. Required `overall_metrics`, `consensus_metrics` (with ensemble-only fields optional), `by_difficulty` keyed by the four difficulty values, `by_field` keyed by the scoring-rubric field names, `documents[]` with `{document_id, overall_passed, field_accuracy}`
- [X] T064 [US3] Update `contracts/stage1_vendor_identity/v1.0.0/contract_set.json` to register the two evaluation schemas and add `DOCUMENT_COUNT_MISMATCH` to `cross_artifact_rules`
- [X] T065 [US3] Extend `src/ledgerlinc_ocr/validator/cross_artifact.py` with `check_document_count(run_summary: JSONDoc) -> list[Violation]`
- [X] T066 [US3] Implement `src/ledgerlinc_ocr/validator/corpus.py` exposing `validate_corpus(root, *, version, fail_fast)` that iterates subfolders (invoking `validate_folder`), validates the root-level `evaluation_run_summary.json` when present, collects per-target `ValidationOutcome` objects into `sub_reports`, and computes the top-level `passed` / `counts` as the union of sub-report results
- [X] T067 [US3] Wire `validate corpus` subcommand in `src/ledgerlinc_ocr/validator/cli.py` to `corpus.py`, replacing the T011 stub; support `--fail-fast`
- [X] T068 [US3] Add concrete `validate_corpus` export to `src/ledgerlinc_ocr/validator/__init__.py` (replacing the `NotImplementedError` stub from T012)

**Checkpoint**: Evaluation shapes are frozen and machine-validated; the harness can run `validate corpus` on the full 20-document set and aggregate failures without scraping text (FR-036b).

---

## Phase 6: User Story 4 — Contributor Changes a Contract Through a Governed Path (Priority: P2)

**Goal**: Make the amendment path real: an `AMENDMENTS.md` changelog, a machine-layer `README.md` with the amendment checklist, and self-consistency tests that keep the three artifacts (docs / machine schemas / validator code) from drifting.

**Independent Test**: From spec.md US4 — a contributor takes a proposed contract change (e.g. adding a new `challenge_tag`), follows the `AMENDMENTS.md` checklist, lands a new contract-set version `1.1.0` directory with the delta, and confirms: (a) every existing good fixture still validates under `1.0.0`; (b) a new fixture exercising the new tag validates under `1.1.0` but fails under `1.0.0`; (c) `python -m ledgerlinc_ocr.validator show contract-set` reflects the delta.

### Tests for User Story 4 ⚠️

- [X] T069 [P] [US4] Write `tests/contract_tests/test_amendment_governance.py` — asserts: (a) every `violation_code` referenced in `contract_set.json.cross_artifact_rules` is actually exported from `report.py`; (b) every schema file named in `contract_set.json.artifact_schemas` exists and is non-empty; (c) every tag in `contract_set.json.challenge_tags` appears verbatim in `docs/stage1-vendor-identity/dataset-layout.md` (regex match over the doc)
- [X] T070 [P] [US4] Write `tests/contract_tests/test_cli_show_contract_set.py` — exercises `show contract-set --json` and asserts the output contains `contract_set_version`, all seven artifact names, the 17 challenge tags, and a non-empty `cross_artifact_rules` list

### Implementation for User Story 4

- [X] T071 [US4] Write `contracts/stage1_vendor_identity/AMENDMENTS.md` — section 1: the amendment checklist (six steps per `research.md` R6); section 2: changelog starting with the `1.0.0` initial-release entry (what it freezes, date `2026-04-12`, branch `001-freeze-schemas-folder-contracts`); leaves the section open for future `1.x` and `2.x` entries
- [X] T072 [P] [US4] Write `contracts/stage1_vendor_identity/v1.0.0/README.md` — one-screen orientation for the machine layer: what each schema is responsible for, how the folder schema is different (JSON config, not JSON Schema of a file), how `contract_set.json` glues everything, and a pointer back to `AMENDMENTS.md` for the amendment path
- [X] T073 [P] [US4] Implement `show contract-set` logic in `src/ledgerlinc_ocr/validator/cli.py` (if the T011 skeleton only wired the subcommand): load the `ContractSet`, render either `--text` (tabular summary) or `--json` (serialize to a stable object containing `version`, `artifact_schemas`, `folder_schema`, `challenge_tags` sorted alphabetically, `cross_artifact_rules` sorted alphabetically)
- [X] T074 [P] [US4] Add a cross-link in `docs/stage1-vendor-identity/schemas.md` pointing at `contracts/stage1_vendor_identity/v1.0.0/` as the machine-readable layer, and noting the `contract_set_version` field on every artifact
- [X] T075 [P] [US4] Add a cross-link in `docs/stage1-vendor-identity/dataset-layout.md` noting that the listed `challenge_tags` vocabulary is frozen as-is at contract-set `1.0.0`, with additions requiring an amendment + version bump

**Checkpoint**: All four user stories deliverable; the frozen contract set is self-consistent, governed, and amendable.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final cleanup, cross-file coherence, and a quickstart dry-run.

- [X] T076 [P] Ensure every fixture in `tests/contract_tests/fixtures/good/` stamps `contract_set_version: "1.0.0"` and that `tests/contract_tests/test_version_stamping.py` (T015) exercises every artifact type against both present and absent `contract_set_version`
- [X] T077 [P] Sweep `src/ledgerlinc_ocr/validator/` for TODOs and stub calls left over from earlier phases; verify no `NotImplementedError` paths remain reachable
- [X] T078 Run the full `pytest tests/contract_tests/` suite in the devcontainer and confirm `0` failures, `0` errors, and a non-zero test count across every story phase
- [X] T079 Walk through `specs/001-freeze-schemas-folder-contracts/quickstart.md` end-to-end in a clean environment (install, `show contract-set`, `validate artifact` pass + fail, `validate folder` pass + fail + missing-notes WARNING, `validate corpus`, amendment simulation) and record any copy-edits needed back into the quickstart
- [X] T079a [P] Write forward-compatibility demonstration fixtures proving SC-008: under `tests/contract_tests/fixtures/forward_compat/`, author (a) a three-voter `edge_extraction_output.json` with `vote_metadata.consensus_mode = "majority_2_of_3"` and a hypothetical future voter role, (b) a matching `routing_decision.json` with a hypothetical future `decision` value, (c) copies of `preprocess_output.json`, `final_structured_payload.json`, and `expected.json` that are identical in shape to the stage 1 good fixtures. Add `tests/contract_tests/test_forward_compatibility.py` asserting: `preprocess_output`, `final_structured_payload`, `expected`, and the folder layout validate unchanged under contract-set `1.0.0`; `edge_extraction_output` and `routing_decision` fail under `1.0.0` only at the specific enum/vocabulary fields that SC-008 permits to change (`vote_metadata.consensus_mode` and `decision`), not at any structural field
- [X] T080 [P] Update the top-level `README.md` with a one-paragraph "Validator & contracts" section that points at `specs/001-freeze-schemas-folder-contracts/quickstart.md` and at `contracts/stage1_vendor_identity/`
- [X] T081 [P] Update `CLAUDE.md` so the "Key References" list includes `contracts/stage1_vendor_identity/` and so the "Architecture" section notes that the stage 1 artifact contracts are now machine-validated (not only documented)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: no dependencies — can start immediately on branch `001-freeze-schemas-folder-contracts`
- **Phase 2 (Foundational)**: depends on Phase 1 — BLOCKS all user stories
- **Phase 3 (US1) / Phase 4 (US2) / Phase 5 (US3)**: all three depend only on Phase 2 and can proceed in parallel once Phase 2 is done
- **Phase 6 (US4)**: depends on at least one of Phase 3 / 4 / 5 having produced a real artifact contract — in practice wait for all three so the self-consistency tests in T069 have material to check
- **Phase 7 (Polish)**: depends on every preceding phase

### User Story Dependencies

- **US1 (P1, pipeline artifacts)**: depends on Foundational only. Delivers the MVP — pipeline developers can validate all four pipeline artifacts.
- **US2 (P1, expected + folder)**: depends on Foundational only. Fully independent of US1 at the *contract* level; at the *validator* level, `validate folder` reuses the artifact validator from Phase 2 / US1 for any pipeline artifacts the labeler drops into the folder, but the folder contract and `expected` contract are independently testable.
- **US3 (P1, evaluation + corpus)**: depends on Foundational only. `validate corpus` reuses `validate_folder` from US2 *if* US2 has landed, but the evaluation-artifact contracts and their tests do not require US2.
- **US4 (P2, governance)**: depends on US1 + US2 + US3 having produced artifact schemas and the `challenge_tags` vocabulary, because the governance self-consistency tests (T069) read those to verify alignment. This is the only story with hard dependencies on earlier stories.

### Within each User Story

- Fixtures (good + bad) can go in parallel with each other — all different files.
- Tests (`test_*.py`) go before implementation per the TDD convention; they will fail against the empty schemas scaffolded in T003 until the corresponding schema + code lands.
- JSON Schema files within a story can go in parallel (different files).
- `contract_set.json` updates within a story (T033, T051, T064) are sequential because they edit the same file.
- CLI wiring (T036, T053, T067) is sequential within each story because it edits the same `cli.py` — but across stories the edits are additive enough that the natural priority order US1 → US2 → US3 avoids conflict.

### Parallel Opportunities

- All of T002, T003, T004 (Setup) run in parallel.
- All of T007, T008, T009 (Foundational core modules) run in parallel; T010, T011, T012 serialize on them.
- All of T013, T014, T015 (Foundational tests + conftest) run in parallel.
- Within US1, T016–T025 (all fixtures) and T026–T028 (all tests) are all `[P]`; T029–T032 (four schema files) are all `[P]`.
- Within US2, T037–T045 (fixtures) and T046–T048 (tests) are all `[P]`; T049, T050 (schema files) are `[P]`.
- Within US3, T056–T059 (fixtures) and T060, T061 (tests) are `[P]`; T062, T063 (schema files) are `[P]`.
- Within US4, T069, T070 (tests) and T072, T074, T075 (docs) are `[P]`.
- In Polish, T076, T077, T080, T081 are `[P]`.

---

## Parallel Example: User Story 1

```bash
# After Phase 2 completes, a single developer can launch all US1 fixtures + tests in parallel:
Task: "Write good preprocess_output fixture in tests/contract_tests/fixtures/good/preprocess_output.json"   # T016
Task: "Write good edge_extraction_output fixture in tests/contract_tests/fixtures/good/edge_extraction_output.json"   # T017
Task: "Write good routing_decision fixture in tests/contract_tests/fixtures/good/routing_decision.json"   # T018
Task: "Write good final_structured_payload fixture in tests/contract_tests/fixtures/good/final_structured_payload.json"   # T019
Task: "Write bad fixture empty_string_for_null.json"   # T020
# ...T021–T025 similarly
Task: "Write test_artifact_contracts.py"   # T026
Task: "Write test_cross_artifact.py"   # T027
Task: "Write test_cli_artifact.py"   # T028

# And all four schema files in parallel:
Task: "Write preprocess_output.schema.json"   # T029
Task: "Write edge_extraction_output.schema.json"   # T030
Task: "Write routing_decision.schema.json"   # T031
Task: "Write final_structured_payload.schema.json"   # T032
```

---

## Implementation Strategy

### MVP (User Story 1 only)

1. Complete Phase 1 Setup.
2. Complete Phase 2 Foundational (blocks everything).
3. Complete Phase 3 US1 (four pipeline artifact contracts + cross-artifact triad + `validate artifact` CLI).
4. **STOP and validate**: run `pytest tests/contract_tests/test_artifact_contracts.py tests/contract_tests/test_cross_artifact.py tests/contract_tests/test_cli_artifact.py`; run the `validate artifact` CLI against a hand-written `edge_extraction_output.json` and confirm both pass and fail paths.
5. At this point, pipeline developers are unblocked for `preprocess_output`, `edge_extraction_output`, `routing_decision`, `final_structured_payload` implementation work — which covers 7 of the 8 critical-path items in `docs/stage1-vendor-identity/implementation-plan.md`.

### Incremental Delivery (recommended path)

1. Phase 1 + Phase 2 → foundation ready.
2. US1 (P1) → MVP, pipeline devs unblocked.
3. US2 (P1) → labelers unblocked; `tests/stage1_vendor_identity/` corpus starts filling in parallel with pipeline code.
4. US3 (P1) → evaluator devs unblocked; corpus-level validation works.
5. US4 (P2) → amendment path real; contributors can propose contract changes safely.
6. Phase 7 Polish → quickstart dry-run, docs cross-links.

### Parallel Team Strategy

With two or three developers on this feature after Phase 2:

- Dev A: US1 (largest story — 13 tasks).
- Dev B: US2 (10 tasks).
- Dev C: US3 (7 tasks).
- All three converge on the same `contract_set.json` — coordinate via small, rebase-friendly commits per `artifact_schemas` / `challenge_tags` / `cross_artifact_rules` addition.
- US4 and Polish are done after the three P1 stories land, either by any of the devs.

---

## Notes

- `[P]` = different files, no dependencies on incomplete tasks.
- `[Story]` label maps a task to its user story for traceability; setup / foundational / polish tasks deliberately omit it.
- Each user story is independently testable against the `Independent Test` criterion in `spec.md`.
- TDD convention: fixture + test files within each story land before the implementation they exercise; expected initial state is red (tests fail against empty schemas from T003).
- The runtime corpus `tests/stage1_vendor_identity/` is intentionally empty after this feature — labeling is Workstream A from the test-harness PRD and proceeds in parallel with (not inside) this feature.
- `contract_set.json` is edited three times (T033, T051, T064) in sequence; treat those as critical-section edits and rebase rather than parallelizing.
- The 20-document corpus PDFs do not land in this feature; `tests/stage1_vendor_identity/` is created as an empty scaffold only.
