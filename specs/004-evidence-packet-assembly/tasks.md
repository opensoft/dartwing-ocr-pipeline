---
description: "Task list for 004-evidence-packet-assembly"
---

# Tasks: Evidence Packet Assembly (Trijunction-Ready)

**Input**: Design documents from `/specs/004-evidence-packet-assembly/`
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/cli-contract.md`, `quickstart.md`

**Tests**: Included. The spec's per-story "Independent Test" sections and Constitution Principle V (benchmarkable / reproducible delivery) make tests load-bearing for this slice. Every user story gets at least one integration test that exercises its acceptance scenarios. Contract-amendment correctness is also covered by dedicated schema-level tests.

**Organization**: Tasks are grouped by user story. Phase 1 + Phase 2 are shared infrastructure (including the `v1.1.0` contract-set amendment, which must land before any user-story work). Phase 3 is the MVP. Later stories slot in behind the MVP without breaking it.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks).
- **[Story]**: Which user story the task belongs to (US1, US2, US3, US4). Setup / Foundational / Polish tasks carry no story label.
- File paths are absolute within the repo root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Module skeleton, test-tree wiring, and CLI registration so every later phase starts from a consistent base. No logic in this phase.

- [X] T001 Create module skeleton `src/ledgerlinc_ocr/evidence_packet/` with empty `__init__.py`, `__main__.py`, `cli.py`, `assembler.py`, `schema.py`, `serialization.py`, `regex_hints.py`, `offset_mapping.py`, `errors.py`, `version.py`
- [X] T002 [P] Create sub-module skeleton `src/ledgerlinc_ocr/evidence_packet/sections/` with empty `__init__.py`, `structural.py`, `tables.py`, `trijunction.py`, `perceptual.py`, `candidate_signals.py`
- [X] T003 [P] Create test tree: `tests/unit/evidence_packet/__init__.py`, `tests/integration/evidence_packet/__init__.py`, `tests/contract_tests/evidence_packet_schema/__init__.py`, `tests/fixtures/evidence_packet/.gitkeep`
- [X] T004 [P] Register new test paths in `pyproject.toml` under `[tool.pytest.ini_options].testpaths` if not already covered (confirm `tests/unit` and `tests/integration` are present; the new `tests/contract_tests/evidence_packet_schema` is picked up by the existing `tests/contract_tests` entry)
- [X] T005 Wire console script entry in `pyproject.toml` under `[project.scripts]`: `ledgerlinc-evidence-packet = "ledgerlinc_ocr.evidence_packet.cli:main"`
- [X] T006 [P] Reinstall editable package to register the new console script: `.venv/bin/pip install -e ".[dev]"`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The `v1.1.0` contract-set amendment, the new artifact schema, the folder-contract delta, typed errors, and the schema loader. Every user story consumes these.

**⚠️ CRITICAL**: No user-story work begins until Phase 2 is green. In particular, the packet schema MUST exist before US1 tests can be written.

### Contract-Set Amendment (v1.0.0 → v1.1.0)

- [X] T007 Copy `contracts/stage1_vendor_identity/v1.0.0/` verbatim to `contracts/stage1_vendor_identity/v1.1.0/` (all ten existing files; no edits). Use `cp -a` or equivalent to preserve bytes.
- [X] T008 Edit `contracts/stage1_vendor_identity/v1.1.0/contract_set.json`: set `contract_set_version` to `"1.1.0"`; append `"evidence_packet"` to `artifact_names`; add `"evidence_packet": "evidence_packet.schema.json"` to `artifact_schemas`. Do NOT add `evidence_packet` to `pipeline_versioned_artifacts` or `policy_versioned_artifacts`.
- [X] T009 Edit `contracts/stage1_vendor_identity/v1.1.0/folder.schema.json`: append `"evidence_packet.json"` to `reserved_generated_filenames`. Add an inline note / `$comment` clarifying that `evidence_packet.json` is **optional** (generated only at DEBUG logger level), unlike the other reserved filenames.
- [X] T010 Create `contracts/stage1_vendor_identity/v1.1.0/evidence_packet.schema.json` — Draft 2020-12 JSON Schema mirroring `data-model.md` exactly. Required top-level keys (in order): `contract_set_version`, `document_id`, `source_file`, `page_count`, `pages`, `reading_order`, `document_text`, `tables`, `ingestion_sources`, `perceptual_observations`, `candidate_vendor_signals`. `additionalProperties: false` at every object level. Reuse `$defs/bbox`, `$defs/page`, `$defs/block`, `$defs/ocr_line`, `$defs/ingestion_source` shapes from `preprocess_output.schema.json` so passthrough fields validate identically.
- [X] T011 Append v1.1.0 entry to `contracts/stage1_vendor_identity/AMENDMENTS.md` following the established format: branch name, summary, what was added (new artifact schema + folder-contract delta), tier (MINOR, additive), preservation note (all v1.0.0 artifacts remain valid under v1.1.0).

### Validator Awareness of v1.1.0

- [X] T012 Audit `src/ledgerlinc_ocr/validator/` to confirm it loads the contract set by version directory (not by hardcoded `v1.0.0/` paths). If a hardcode exists, parameterize the internal loader so `contracts/stage1_vendor_identity/v1.1.0/` is discoverable alongside `v1.0.0/`. Exposing a user-facing `--version` CLI flag is out of scope for this slice; internal code paths and existing tests MUST treat `v1.1.0` as the current contract set once the amendment lands.
- [X] T013 [P] Add validator fixture under `tests/contract_tests/evidence_packet_schema/fixtures/`: `valid_minimal_packet.json` — the smallest packet that validates (one page, one block, one line, all Trijunction slots `not_implemented`, all signal lists empty, `company_name: null`, `addresses: []`).
- [X] T014 [P] Add validator fixture `tests/contract_tests/evidence_packet_schema/fixtures/invalid_missing_ingestion_source.json` — a packet missing the `falcon_perception` key. Used by T015.
- [X] T015 [P] Contract test `tests/contract_tests/evidence_packet_schema/test_schema_valid_packet.py`: parse `contracts/stage1_vendor_identity/v1.1.0/evidence_packet.schema.json` with `Draft202012Validator`, validate `valid_minimal_packet.json` (expect success), validate `invalid_missing_ingestion_source.json` (expect failure naming `falcon_perception`).
- [X] T016 [P] Contract test `tests/contract_tests/evidence_packet_schema/test_folder_schema_amendment.py`: load `v1.1.0/folder.schema.json`, assert `"evidence_packet.json" in reserved_generated_filenames`, assert the folder contract still validates the existing corpus fixture whether or not `evidence_packet.json` is present (use `tests/stage1_vendor_identity/` as the sample tree; skip gracefully if a folder fixture is not yet populated).
- [X] T017 [P] Contract test `tests/contract_tests/evidence_packet_schema/test_contract_set_metadata.py`: load `v1.1.0/contract_set.json`, assert `contract_set_version == "1.1.0"`, assert `"evidence_packet"` is in `artifact_names` but NOT in `pipeline_versioned_artifacts` or `policy_versioned_artifacts`.

### Foundational Modules

- [X] T018 [P] Implement typed errors in `src/ledgerlinc_ocr/evidence_packet/errors.py`: `PacketAssemblyError` (base), `PreprocessInputMissing`, `PreprocessInputInvalid`, `PacketInvalid`. Each subclass carries the offending path (when applicable) and a human-readable message. Exit-code mapping lives in `cli.py`, not in the exceptions.
- [X] T019 [P] Implement `src/ledgerlinc_ocr/evidence_packet/version.py`: module constants `CONTRACT_SET_VERSION = "1.1.0"`, `PACKET_FILENAME = "evidence_packet.json"`.
- [X] T020 [P] Implement `src/ledgerlinc_ocr/evidence_packet/schema.py`: module-level `_PACKET_SCHEMA_PATH` pointing at `contracts/stage1_vendor_identity/v1.1.0/evidence_packet.schema.json`; `_PREPROCESS_SCHEMA_PATH` pointing at the corresponding preprocess schema under `v1.1.0/`; cached `Draft202012Validator` instances; helpers `validate_packet(dict) -> None` and `validate_preprocess_input(dict) -> None` that raise `PacketInvalid` / `PreprocessInputInvalid` respectively with sorted-by-path error messages (mirroring 003's `artifact.py::validate`).
- [X] T021 [P] Implement `src/ledgerlinc_ocr/evidence_packet/serialization.py`: `write_packet_atomic(packet: dict, out_path: Path) -> Path` that imports and delegates to `ledgerlinc_ocr.preprocessing.artifact.write_atomic` (per research Decision 7). No new serialization dialect.
- [X] T022 [P] Unit test `tests/unit/evidence_packet/test_errors.py`: verifies that each typed error is a subclass of `PacketAssemblyError`, that messages preserve the offending path argument, and that none of the typed errors are subclasses of each other (avoids accidental catch-cascades).
- [X] T023 [P] Unit test `tests/unit/evidence_packet/test_schema.py`: verifies schema-loader caching (two calls return the same validator instance), verifies that a deliberately corrupted packet raises `PacketInvalid` with the bad path in the message, verifies that a deliberately corrupted preprocess input raises `PreprocessInputInvalid`.

**Checkpoint**: Phase 2 green — the `v1.1.0` contract directory validates, the validator tests pass, and the foundational error/schema/serialization modules compile and pass unit tests. User-story work may begin.

---

## Phase 3: User Story 1 — Voter-Ready Packet From Preprocess Output (Priority: P1) 🎯 MVP

**Goal**: Running the assembler against a per-document folder with a valid `preprocess_output.json` returns a packet dict that validates against `v1.1.0/evidence_packet.schema.json`, contains faithfully-derived structural evidence, exposes `not_implemented` slots for Falcon OCR / Falcon Perception, and surfaces deterministic regex hints for emails, URLs, US phones, and EIN-shaped tax IDs. At DEBUG logger level, the same call also writes `evidence_packet.json` into the folder.

**Independent Test**: Using a hand-crafted fixture `preprocess_output.json` containing one page with an email, a URL, a US phone, and an EIN in its `document_text`, call `assemble_from_folder(folder)` at default logger level — assert the returned dict validates, contains the expected regex hits in document order with full source references, and writes zero files. Re-call at DEBUG level — assert the same dict plus a byte-identical `evidence_packet.json` on disk. Re-run ten times at DEBUG — assert ten byte-identical files.

### Tests for User Story 1

> Write these first; they should FAIL until T036 lands.

- [X] T024 [P] [US1] Fixture `tests/fixtures/evidence_packet/minimal_valid.json` — a hand-crafted `preprocess_output.json` with one page, one block, one OCR line, `ingestion_sources.paddleocr_vl.status == "success"`, Falcon slots `not_implemented`, `document_text` empty (no regex hits). Stamped `contract_set_version: "1.0.0"` to exercise the v1.0.0 → v1.1.0 upgrade path.
- [X] T025 [P] [US1] Fixture `tests/fixtures/evidence_packet/with_regex_hits.json` — two pages, `document_text` containing: `"Contact: accounts@acme.com or visit https://acme.example.com/pay. Phone (555) 123-4567. EIN 12-3456789."` plus a second page with a second email and a second phone. Used to exercise regex ordering + duplicates + source-reference integrity.
- [X] T026 [P] [US1] Fixture `tests/fixtures/evidence_packet/multi_match.json` — same email twice, two phones, one URL; mixed across two blocks on one page. Verifies no-dedup + document-order invariants.
- [X] T027 [P] [US1] Fixture `tests/fixtures/evidence_packet/all_sources_not_implemented.json` — `ingestion_sources.paddleocr_vl.enabled == false, status == "not_implemented"`; Falcon slots also `not_implemented`; `pages == []`, `document_text == ""`. Verifies zero-evidence edge case still produces a valid packet.
- [X] T028 [P] [US1] Integration test `tests/integration/evidence_packet/conftest.py` — shared pytest fixture `folder_with_preprocess(tmp_path, preprocess_fixture_name)` that copies a named fixture into `tmp_path/inv_001_easy/preprocess_output.json` and returns the folder path.
- [X] T029 [P] [US1] Integration test `tests/integration/evidence_packet/test_us1_schema_valid_packet.py::test_ac1_passthrough_is_faithful` — US1 AC#1. Assembles from `minimal_valid.json`; asserts packet validates; asserts `pages`, `reading_order`, `document_text`, `tables` are faithfully derived (no added keys, no inferred values).
- [X] T030 [P] [US1] Integration test `tests/integration/evidence_packet/test_us1_determinism.py::test_ac2_byte_identical_ten_runs` — US1 AC#2 + SC-002. Calls `assemble_from_folder` ten times at DEBUG, diffs the ten `evidence_packet.json` byte streams, asserts all identical.
- [X] T031 [P] [US1] Integration test `tests/integration/evidence_packet/test_us1_ingestion_slots.py::test_ac3_slot_preservation` — US1 AC#3. Uses `all_sources_not_implemented.json`; asserts all three `ingestion_sources` keys present; asserts `payload` is `null` for every `not_implemented` / `failure` slot.
- [X] T032 [P] [US1] Integration test `tests/integration/evidence_packet/test_us1_regex_hints.py::test_ac4_ordered_hints_with_source_refs` — US1 AC#4 + SC-009 + Clarifications Q4/Q5. Uses `with_regex_hits.json` and `multi_match.json`; asserts emails, URLs, phones, tax_ids are emitted in ascending `document_text_offset`; asserts duplicates preserved; asserts every hit has non-null `page_index`, `block_index`, `line_index`; asserts `document_text[offset:offset+length] == value` for every hit; asserts `company_name == null` and `addresses == []`.
- [X] T033 [P] [US1] Integration test `tests/integration/evidence_packet/test_us1_logging_persistence.py::test_ac5_debug_writes_default_does_not` — US1 AC#5 + SC-006 + SC-007. At default logger, asserts `evidence_packet.json` is absent after call; asserts all other artifacts in the folder are byte-identical before and after. At DEBUG, asserts `evidence_packet.json` is present and validates; asserts the other artifacts are still byte-identical.

### Implementation for User Story 1

- [X] T034 [P] [US1] Implement `src/ledgerlinc_ocr/evidence_packet/regex_hints.py`: four compiled patterns `EMAIL_RE`, `URL_RE`, `US_PHONE_RE`, `EIN_RE` per research Decision 3 (explicit flags, no runtime composition); function `find_hints(document_text: str) -> dict[str, list[tuple[str, int, int]]]` returning a dict with keys `emails`, `websites`, `phones`, `tax_ids`, each a list of `(value, start_offset, end_offset)` in ascending `start_offset`. No deduplication.
- [X] T035 [P] [US1] Implement `src/ledgerlinc_ocr/evidence_packet/offset_mapping.py`: function `build_offset_index(pages: list[dict]) -> tuple[str, list[tuple[int,int,int,int]]]` that rebuilds `document_text` exactly as 003's `join_document_text` does and simultaneously records `(block_start_offset, block_end_offset, page_index, block_index)` tuples sorted by `block_start_offset`. Function `reverse_map(offset: int, index: list, pages: list) -> tuple[int,int,int]` that returns `(page_index, block_index, line_index)` for a given `document_text` offset via `bisect.bisect_right`, computing `line_index` as `block.text[:(offset - block_start)].count("\n")`.
- [X] T036 [P] [US1] Implement `src/ledgerlinc_ocr/evidence_packet/sections/structural.py`: `build_structural_section(preprocess_output) -> dict` returning `{"pages": sorted-pages, "reading_order": [block_ids...], "document_text": "..."}`. Includes the byte-equality assertion against `preprocess_output["document_text"]`; on mismatch raises `PacketAssemblyError`.
- [X] T037 [P] [US1] Implement `src/ledgerlinc_ocr/evidence_packet/sections/tables.py`: `build_tables_section(preprocess_output) -> list` — pure passthrough of `preprocess_output["tables"]`. No re-interpretation (FR-006).
- [X] T038 [P] [US1] Implement `src/ledgerlinc_ocr/evidence_packet/sections/trijunction.py`: `build_ingestion_sources(preprocess_output) -> dict` returning the three-slot object per `data-model.md`. For `paddleocr_vl`: `enabled` and `status` mirror input; `payload` is `{"kind":"structural"}` when `status == "success"` else `null`. For `falcon_ocr` and `falcon_perception`: `enabled`/`status` mirror input; `payload` always `null` in stage 1.
- [X] T039 [P] [US1] Implement `src/ledgerlinc_ocr/evidence_packet/sections/perceptual.py`: `build_perceptual_observations(preprocess_output) -> dict` returning `{"status": <mirror falcon_perception.status>, "logos": [], "stamps": [], "header_candidates": [], "footer_candidates": []}`. Stage 1 always yields empty arrays.
- [X] T040 [US1] Implement `src/ledgerlinc_ocr/evidence_packet/sections/candidate_signals.py`: `build_candidate_signals(preprocess_output, offset_index) -> dict`. Runs `find_hints` over `document_text`; for each hit calls `reverse_map` to get `(page_index, block_index, line_index)`; emits hint objects in the order specified by `data-model.md`; sets `company_name = null`, `addresses = []`, `provenance = "unverified"` on every hit. Asserts `document_text[offset:offset+length] == value` for every emitted hit (raises `PacketAssemblyError` on mismatch).
- [X] T041 [US1] Implement `src/ledgerlinc_ocr/evidence_packet/assembler.py`: `assemble_from_preprocess(preprocess_output: dict, *, document_id: str | None = None) -> dict`. Steps: (1) `schema.validate_preprocess_input(preprocess_output)`; (2) build offset index from `pages`; (3) call each section builder in order; (4) construct the top-level packet dict in the fixed insertion order from `data-model.md`; (5) `schema.validate_packet(packet)`; (6) return the dict. Raises `PreprocessInputInvalid` or `PacketInvalid` on validation failure. Does NO filesystem I/O.
- [X] T042 [US1] Implement `src/ledgerlinc_ocr/evidence_packet/__init__.py`: export `assemble_from_folder`, `assemble_from_preprocess`, `PacketAssemblyError`, `PreprocessInputMissing`, `PreprocessInputInvalid`, `PacketInvalid`. Implement `assemble_from_folder(folder: Path) -> dict`: resolve folder to absolute path; open `<folder>/preprocess_output.json`; raise `PreprocessInputMissing` (wrapping the original `OSError`) if unreadable; `json.load` the file; raise `PreprocessInputMissing` if it is not JSON; call `assemble_from_preprocess`; if `logging.getLogger("ledgerlinc_ocr").isEnabledFor(logging.DEBUG)` then call `serialization.write_packet_atomic(packet, folder / "evidence_packet.json")`; return the dict.
- [X] T043 [US1] Implement `src/ledgerlinc_ocr/evidence_packet/cli.py`: argparse with positional `folder`, optional `-v/--verbose` (count action). On startup, if `verbose >= 1`, set the `ledgerlinc_ocr` logger level to `DEBUG` and install a stderr `StreamHandler` at `WARNING` format per `cli-contract.md`. Call `assemble_from_folder(Path(folder).resolve())`. Catch `PreprocessInputMissing` → exit 2, `PreprocessInputInvalid` → exit 3, `PacketInvalid` → exit 4, `OSError` during persistence → exit 5, other `Exception` → exit 1. Emit a single compact JSON line on stdout per `cli-contract.md` (`status`, `folder`, `persisted`, `contract_set_version`).
- [X] T044 [US1] Implement `src/ledgerlinc_ocr/evidence_packet/__main__.py`: single line delegating to `cli.main()`.
- [X] T045 [P] [US1] Unit test `tests/unit/evidence_packet/test_regex_hints.py`: verifies each pattern matches the intended positive cases (single email, bare `https://...`, `(555) 123-4567`, `12-3456789`) and rejects the close-but-wrong negatives (ZIP+4 `12345-6789`, IP-only URL, bare-domain `acme.com`, non-hyphenated 9-digit ID). Verifies ascending-offset ordering and no-dedup on duplicates.
- [X] T046 [P] [US1] Unit test `tests/unit/evidence_packet/test_offset_mapping.py`: verifies that `build_offset_index` rebuilds `document_text` byte-identically to a reference 003 join; verifies `reverse_map` returns the correct `(page_index, block_index, line_index)` for offsets at block boundaries, mid-block, and after a newline within a multi-line block; verifies that a mismatch between rebuilt and input `document_text` raises `PacketAssemblyError`.
- [X] T047 [P] [US1] Unit test `tests/unit/evidence_packet/test_trijunction_slots.py`: verifies every input combination of `{enabled, status}` for `paddleocr_vl` produces the correct `payload` (structural sentinel vs. `null`); verifies Falcon slots always get `null` payloads in stage 1 regardless of their `status`.
- [X] T048 [P] [US1] Unit test `tests/unit/evidence_packet/test_candidate_signals_nulls.py`: verifies `company_name == null` and `addresses == []` on every fixture in `tests/fixtures/evidence_packet/` regardless of `document_text` content; verifies `provenance == "unverified"` on every emitted hint.
- [X] T049 [P] [US1] Unit test `tests/unit/evidence_packet/test_serialization.py`: verifies `write_packet_atomic` produces byte-identical output for two identical dicts; verifies the on-disk file has no trailing newline; verifies `indent=2`, `ensure_ascii=False`, `sort_keys=False` are honored (by inspecting the output rather than by mocking the call).
- [X] T050 [P] [US1] Unit test `tests/unit/evidence_packet/test_null_discipline.py`: FR-014. Recursively walks every fixture-derived packet asserting: every string value is non-empty OR the key is documented as nullable in `data-model.md`; every list value is typed (possibly `[]` but never `null`); every object key matches the documented set.

**Checkpoint**: Phase 3 green — MVP delivered. `assemble_from_folder` works end-to-end, CLI ships, all US1 tests pass.

---

## Phase 4: User Story 2 — Pluggable Trijunction Sources (Priority: P2)

**Goal**: Prove that the packet's Trijunction-shaped slots are load-bearing: every slot is always present, every slot carries a status-driven payload shape, and adding a future Falcon adapter is a drop-in population (no schema change).

**Independent Test**: Read `evidence_packet.schema.json` and assert all three Trijunction slot keys are `required` with their sub-schemas. Simulate a "future Falcon OCR wired in" by producing a packet whose `falcon_ocr.status == "success"` and `falcon_ocr.payload == {"kind":"text_plus_spam_gate", ...}` in-memory, and assert the packet STILL validates against the current schema (the schema permits new `kind` values on success).

### Tests for User Story 2

- [X] T051 [P] [US2] Integration test `tests/integration/evidence_packet/test_us2_pluggable_slots.py::test_ac1_all_three_slots_present` — US2 AC#1. Asserts every fixture's assembled packet has `ingestion_sources.{paddleocr_vl, falcon_ocr, falcon_perception}` as keys, each with `enabled`, `status`, `payload` sub-keys. Uses all fixtures, including `all_sources_not_implemented.json`.
- [X] T052 [P] [US2] Integration test `tests/integration/evidence_packet/test_us2_pluggable_slots.py::test_ac2_status_driven_payload` — US2 AC#2. Asserts `payload` is `null` for every slot with `status in {"failure","not_implemented"}`; asserts `payload` is the structural sentinel for `paddleocr_vl` on success; asserts the schema's `payload` definition permits a future success-path object on any slot (schema-level check only, no data).
- [X] T053 [P] [US2] Unit test `tests/unit/evidence_packet/test_trijunction_shape_forward_compat.py`: constructs an in-memory packet with `falcon_ocr.status == "success"` and `falcon_ocr.payload == {"kind":"text_plus_spam_gate","text":"hello","spam_gate":{"flagged":False,"reason":None}}`; asserts the packet validates against `v1.1.0/evidence_packet.schema.json` WITHOUT schema edits (demonstrates SC-005).

### Implementation for User Story 2

> US2 is a shape commitment: US1's implementation already satisfies it. These tasks verify and document the commitment rather than adding new code.

- [X] T054 [P] [US2] Extend `contracts/stage1_vendor_identity/v1.1.0/evidence_packet.schema.json` `ingestion_source.payload` definition to `{"oneOf":[{"type":"null"},{"type":"object","required":["kind"],"properties":{"kind":{"type":"string"}}}]}` — permits null OR any object with a `kind` discriminator. Do NOT close the `kind` enum; that would force a MAJOR bump when Falcon lands.
- [X] T055 [P] [US2] Document the forward-compat story in `data-model.md`'s "Forward-compatibility strategy" section already drafted — cross-reference this contract commitment so future slice authors find it. (Verify the text; edit only if needed.)

**Checkpoint**: Phase 4 green — US2 acceptance scenarios pass, the schema permits forward-compatible Falcon payloads, and the "adding a Falcon adapter requires zero contract changes" claim is covered by a concrete test.

---

## Phase 5: User Story 3 — Voter-Independent Shape (Priority: P2)

**Goal**: Prove that the packet carries no voter-specific, model-specific, or prompt-specific content. Three future voter implementations must be able to read the same packet via the same accessors.

**Independent Test**: Scan the packet recursively for banned substrings (`"prompt"`, `"voter_"`, any model name like `"qwen"`, `"gemma"`, `"phi"`, `"llama"`) in keys and string values. Assert zero hits on every fixture. Also scan the schema itself for the same substrings in `properties` keys.

### Tests for User Story 3

- [X] T056 [P] [US3] Integration test `tests/integration/evidence_packet/test_us3_voter_agnostic.py::test_ac1_no_voter_specific_keys_in_packet` — US3 AC#1. Recursively walks every fixture-derived packet (using all `tests/fixtures/evidence_packet/*.json` inputs) asserting no key or string-typed value contains any of: `"prompt"`, `"voter"`, `"qwen"`, `"gemma"`, `"phi"`, `"llama"`, `"token_budget"`, `"temperature"`. Uses `re.search` with word boundaries to avoid false positives on unrelated words.
- [X] T057 [P] [US3] Integration test `tests/integration/evidence_packet/test_us3_voter_agnostic.py::test_ac2_no_voter_specific_keys_in_schema` — US3 AC#2. Loads `v1.1.0/evidence_packet.schema.json`, recursively walks `properties` keys, asserts none of the banned substrings appear.
- [X] T058 [P] [US3] Unit test `tests/unit/evidence_packet/test_no_timestamps_or_uuids.py`: FR-012. Recursively walks every fixture-derived packet asserting no string value matches the ISO-8601 timestamp regex or the UUID regex. Defensive check that a future contributor cannot sneak these in.

### Implementation for User Story 3

> US3 is a negative-space commitment — there is no code to write, only tests that prevent regression.

- [X] T059 [US3] Verify `data-model.md`'s "Invariants" list explicitly names the banned-substring scan as an enforcement mechanism. If the current list is silent on the substring check specifically, add a one-line mention to the "No voter/model/prompt strings" invariant.

**Checkpoint**: Phase 5 green — US3 acceptance scenarios pass, negative-space invariants are locked in by tests.

---

## Phase 6: User Story 4 — Per-Document Folder Integration (Priority: P3)

**Goal**: The assembler reads only `<folder>/preprocess_output.json` and — at DEBUG logger level — writes only `<folder>/evidence_packet.json`, leaving the four existing artifacts byte-identical. The folder contract at `v1.1.0` accepts both presence and absence of the packet file.

**Independent Test**: Populate a folder with `source.pdf`, `preprocess_output.json`, and pre-existing dummy `edge_extraction_output.json`, `routing_decision.json`, `final_structured_payload.json`. Hash all of them. Run `ledgerlinc-evidence-packet <folder>` at default level — no file changes, no new files. Hash the dummies again — unchanged. Re-run with `-v` — `evidence_packet.json` appears and validates; the four dummies are still byte-identical. Run `python -m ledgerlinc_ocr.validator validate folder <folder>` in both states — both pass.

### Tests for User Story 4

- [X] T060 [P] [US4] Integration test `tests/integration/evidence_packet/test_us4_folder_integration.py::test_ac1_default_reads_only_preprocess_writes_nothing` — US4 AC#1 + SC-006 + SC-007. Builds a folder with `preprocess_output.json` plus pre-existing dummy files for the other artifacts; snapshot-hashes them; calls `assemble_from_folder` at default logger level; asserts all hashes unchanged; asserts no new files created.
- [X] T061 [P] [US4] Integration test `tests/integration/evidence_packet/test_us4_folder_integration.py::test_ac2_debug_writes_packet_validates` — US4 AC#2. Same setup as T060 but at DEBUG; asserts exactly one new file `evidence_packet.json` appears; asserts it validates against `v1.1.0/evidence_packet.schema.json`; asserts the four dummy files are still byte-identical.
- [X] T062 [P] [US4] Integration test `tests/integration/evidence_packet/test_us4_folder_integration.py::test_ac3_folder_validator_accepts_both_states` — US4 AC#3. Drives `python -m ledgerlinc_ocr.validator validate folder <folder>` (or the equivalent library call) against the folder in both the packet-absent and packet-present states; asserts both exit 0.
- [X] T063 [P] [US4] Integration test `tests/integration/evidence_packet/test_edge_partial_failure.py::test_partial_failure_preserved` — FR-018 + Edge Cases. Uses a fixture where `ingestion_sources.paddleocr_vl.status == "failure"` but the file is otherwise valid; asserts `assemble_from_folder` still produces a packet and the failure status is preserved in the packet's `ingestion_sources.paddleocr_vl.status`.
- [X] T064 [P] [US4] Integration test `tests/integration/evidence_packet/test_edge_invalid_preprocess.py::test_missing_file_exit_2` — FR-017 + Edge Cases. Empty folder; asserts `assemble_from_folder` raises `PreprocessInputMissing`; asserts CLI exit code 2 and a `status: "error", kind: "input_missing"` stdout JSON.
- [X] T065 [P] [US4] Integration test `tests/integration/evidence_packet/test_edge_invalid_preprocess.py::test_invalid_schema_exit_3` — FR-017. Folder contains a `preprocess_output.json` with a missing required key; asserts `PreprocessInputInvalid`; asserts CLI exit code 3.
- [X] T066 [P] [US4] Integration test `tests/integration/evidence_packet/test_edge_invalid_preprocess.py::test_non_json_exit_2` — Folder contains a `preprocess_output.json` with garbage bytes; asserts `PreprocessInputMissing` (per `cli-contract.md`'s kind mapping for non-JSON); asserts CLI exit code 2.
- [X] T067 [P] [US4] Integration test `tests/integration/evidence_packet/test_edge_readonly_folder.py::test_debug_readonly_folder_exit_5` — Edge Cases. Creates a folder, writes `preprocess_output.json`, `chmod -w` the folder; calls CLI with `-v`; asserts exit code 5, `status: "error", kind: "persistence_failed"`; asserts the library-level `assemble_from_preprocess(loaded_dict)` STILL returns the validated packet if called directly (persistence failure is not an assembly failure). Uses a skip marker on OSes where chmod doesn't affect file creation (non-Unix).
- [X] T068 [P] [US4] Integration test `tests/integration/evidence_packet/test_no_ollama_no_cloud.py` — Constitution §I. Uses `pytest-socket` to disable network; runs the MVP fixture end-to-end; asserts assembly completes without attempting any socket connection.
- [X] T068a [P] [US4] Integration test `tests/integration/evidence_packet/test_us4_easy_bucket_regex_coverage.py::test_sc009_recall_on_easy_corpus` — SC-009. For each `tests/stage1_vendor_identity/inv_*_easy/preprocess_output.json` that exists on disk, run `assemble_from_preprocess` and assert every email, `http(s)://` URL, US phone number, and EIN-shaped tax ID literally visible in `document_text` appears in the packet's `candidate_vendor_signals`. Recall is gated at 100%; precision is NOT gated (false positives flagged `unverified` are allowed). Skip gracefully if the easy-bucket corpus is not yet populated on this branch.

### Implementation for User Story 4

> The MVP already writes to the correct folder and persists only at DEBUG. These tasks audit the behavior and close the folder-contract loop.

- [X] T069 [US4] Audit `assemble_from_folder` for any read or write outside `<folder>/preprocess_output.json` and `<folder>/evidence_packet.json`. Add inline comments or an explicit allow-list if needed so reviewers can enforce SC-006 mechanically. Update if any stray I/O exists.
- [X] T070 [US4] Verify `python -m ledgerlinc_ocr.validator validate folder <folder>` correctly picks up the amended `v1.1.0/folder.schema.json` by loading whatever contract-set version the validator's internal loader treats as current (updated in T012). No new CLI flag in this slice.

**Checkpoint**: Phase 6 green — full folder-contract integration; edge cases around missing/invalid input and read-only folders all covered; four existing artifacts provably untouched.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, checklist closeout, final review. No new behavior.

- [X] T071 [P] Update `CLAUDE.md` "Active Technologies" entry for 004 (one-line mention of the evidence packet assembler and the v1.1.0 amendment).
- [X] T072 [P] Update `CLAUDE.md` "Key References" to include `specs/004-evidence-packet-assembly/spec.md` and `specs/004-evidence-packet-assembly/plan.md`.
- [X] T073 [P] Update `docs/stage1-vendor-identity/schemas.md` to cross-reference the new `evidence_packet` schema at `contracts/stage1_vendor_identity/v1.1.0/evidence_packet.schema.json`; note that the frozen v1.0.0 artifacts remain unchanged and that `evidence_packet.json` is optional at the folder level.
- [X] T074 [P] Update `docs/stage1-vendor-identity/architecture.md` if the architecture text currently calls out the evidence packet as "future" — change "future" to "implemented in 004-evidence-packet-assembly". Only edit if that text exists; do not invent new architecture prose.
- [X] T075 Close out `specs/004-evidence-packet-assembly/checklists/contract.md`: walk CHK001–CHK044 and mark each `[x]` when the corresponding spec/contract text is in place; leave `[ ]` and a short note for anything deferred.
- [X] T076 Close out `specs/004-evidence-packet-assembly/checklists/determinism.md`: same exercise for CHK045–CHK077.
- [X] T077 Close out `specs/004-evidence-packet-assembly/checklists/failure-handling.md`: same exercise for CHK078–CHK112.
- [X] T078 Close out `specs/004-evidence-packet-assembly/checklists/requirements.md`: same exercise for CHK113–CHK159.
- [X] T079 Close out `specs/004-evidence-packet-assembly/checklists/scope.md`: same exercise for CHK160–CHK192.
- [X] T080 [P] Run the full test suite (`.venv/bin/pytest tests/contract_tests/ tests/unit/ tests/integration/`); capture any new warnings or failures. Resolve before opening the PR.
- [X] T081 [P] Run `ledgerlinc-evidence-packet tests/stage1_vendor_identity/inv_001_easy` (if the corpus has a real preprocess output in place) at default logger AND at `-v`; capture stdout JSON for both runs and attach to the PR body as a sanity check.

**Checkpoint**: Phase 7 green — docs updated, checklists closed out, full test suite passes, corpus sanity check captured.

---

## Dependencies

**Story completion order (bottom-up)**:

1. Phase 1 (Setup) — no dependencies.
2. Phase 2 (Foundational) — depends on Phase 1. The `v1.1.0` contract directory, `evidence_packet.schema.json`, error types, and schema loader must exist before any user-story phase can run.
3. Phase 3 (US1, MVP) — depends on Phase 2. Delivers a shippable slice on its own.
4. Phase 4 (US2) — depends on Phase 3. Mostly tests + a minor schema clarification (T054).
5. Phase 5 (US3) — depends on Phase 3. Pure negative-space tests; can run in parallel with Phase 4.
6. Phase 6 (US4) — depends on Phase 3. Folder-contract tests + validator wiring; can run in parallel with Phase 4 and Phase 5.
7. Phase 7 (Polish) — depends on all user stories.

**Within-phase dependencies**:

- Phase 2: T007 → T008, T009, T010 (the new directory must exist before its files can be edited). T011 can run in parallel with T012–T017 once T007–T010 are done. T018–T023 are independent of the contract tasks and can run in parallel with them.
- Phase 3: Tests (T024–T033) must be written before implementation (T034–T049); within tests and implementation each, every `[P]`-marked task is independent. T041 (assembler) depends on T034–T040 (section builders and helpers). T042 (`__init__.py` public API) depends on T041. T043 (CLI) depends on T042. T044 (`__main__.py`) depends on T043.
- Phase 4, 5, 6: All tests within each phase are `[P]` parallel. Phase 4's T054 (schema edit) and T055 (doc cross-reference) depend on Phase 2's schema file existing.

## Parallel Execution Opportunities

**Phase 1**: T002–T006 all `[P]`; T001 must land first (defines the package directories).

**Phase 2**:
- After T007 lands, T008, T009, T010, T011 can run in parallel (each edits a different file inside `v1.1.0/`).
- After T010 lands, T013, T014, T015, T016, T017 can all run in parallel (different test files and fixtures).
- T018, T019, T020, T021, T022, T023 are all `[P]` and can run alongside the contract-directory tasks since they live in a different module.

**Phase 3** (MVP):
- Fixtures (T024–T027) can all run in parallel.
- Tests (T029–T033) can all run in parallel once T028 (shared conftest) is in.
- Section builders (T036–T039) can run in parallel; T040 (candidate signals) depends on T035 (offset mapping) and T034 (regex hints).
- Unit tests (T045–T050) are all `[P]` and can run alongside the US1 integration tests once their targets land.

**Phase 4**: T051, T052, T053, T054, T055 all `[P]`.

**Phase 5**: T056, T057, T058 all `[P]`; T059 is doc-only.

**Phase 6**: T060–T068, T068a all `[P]`. T069 and T070 depend on Phase 3's implementation.

**Phase 7**: T071–T081 mostly `[P]` (doc edits on different files; checklist closeouts on different files). T080 (full test suite) runs after all prior phases land.

## Implementation Strategy

**MVP (shippable increment, Phase 1 + Phase 2 + Phase 3)**:

- Delivers `ledgerlinc-evidence-packet <folder>` + `-v` flag and the two-entry-point library API.
- Passes US1's five acceptance scenarios.
- Carries the full `v1.1.0` amendment — new schema, folder-contract delta, validator wiring, amendment log entry.
- Leaves US2/US3/US4 tests red (or pending); they are structural reinforcement on top of a working MVP.

**Incremental delivery after MVP**:

- Phase 4 (US2): 5 tasks, all tests or minor schema clarification.
- Phase 5 (US3): 4 tasks, all negative-space tests.
- Phase 6 (US4): 12 tasks, mostly edge-case + folder-contract integration tests.
- Phase 7 (Polish): 11 tasks, docs + checklist closeout.

**Suggested MVP scope**: **Phase 1 + Phase 2 + Phase 3** (T001–T050). 50 tasks. Delivers a shippable, schema-validating, deterministic evidence-packet assembler that 005 can start programming against immediately.

**Total task count**: 82 tasks across 7 phases.
- Phase 1 (Setup): 6 tasks
- Phase 2 (Foundational): 17 tasks
- Phase 3 (US1 — MVP): 27 tasks
- Phase 4 (US2): 5 tasks
- Phase 5 (US3): 4 tasks
- Phase 6 (US4): 12 tasks
- Phase 7 (Polish): 11 tasks
