# Tasks: Deterministic Routing (Stage 1 Vendor-Identity)

**Input**: Design documents from `/specs/008-routing/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/cli-contract.md, quickstart.md

**Tests**: Test tasks ARE included. The 003-pdf-preprocessing precedent, the constitution's Principle V (benchmarkable/reproducible delivery), and the `checklists/determinism.md` release gate all require executable verification per acceptance scenario. The contract surface (schema validity, byte-identical reruns, hard-error exits, canonical string exactness) is only auditable through tests.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- New router package: `src/ledgerlinc_ocr/router/`
- Unit tests: `tests/unit/router/`
- Integration tests: `tests/integration/router/`
- Fixtures: `tests/fixtures/router/`
- Per plan.md "Project Structure"

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the router package skeleton and test tree. No routing logic yet.

- [X] T001 Create `src/ledgerlinc_ocr/router/` package with empty `__init__.py` and a module docstring identifying the package as the stage 1 deterministic router
- [X] T002 [P] Create `tests/unit/router/__init__.py` and `tests/integration/router/__init__.py` so pytest discovers the new trees alongside `tests/contract_tests/`
- [X] T003 [P] Create `tests/fixtures/router/` directory with a `README.md` explaining fixtures are hand-authored minimal `edge_extraction_output.json` samples (NOT model runs) and listing the fixture filenames expected by later tasks
- [X] T004 Verify `pyproject.toml` requires no new third-party dependencies for the router (only the existing `jsonschema>=4.22,<5` and `pydantic>=2.7,<3` are used) per research.md Decision 1; add a docstring comment in `src/ledgerlinc_ocr/router/__init__.py` stating "no new third-party dependency" to lock the decision
- [X] T005 [P] Update `CLAUDE.md` "Active Technologies" section to list `008-routing: reuses `ledgerlinc_ocr.validator` for dual-schema validation; no new deps` (one line, matching the 003 precedent)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Typed errors, version constants, canonical string vocabulary, input loader, artifact writer. These MUST exist before any rule or check is implemented because every user story writes an artifact and loads/validates an input.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T006 [P] Create `src/ledgerlinc_ocr/router/errors.py` with typed exceptions `MissingInputError`, `UnreadableInputError`, `MalformedInputError`, `VersionDriftError`, `ContractAssertionError`, each carrying a `human_message` attribute (used by the CLI exit-code taxonomy in `contracts/cli-contract.md`)
- [X] T007 [P] Create `src/ledgerlinc_ocr/router/version.py` exposing `POLICY_VERSION = "stage1-routing-policy-v1.0.0"` (per research.md Decision 3) and `build_pipeline_version() -> str` returning `"stage1-routing-v0.1.0"` (per research.md Decision 4); both are module-level constants, no I/O
- [X] T008 [P] Create `src/ledgerlinc_ocr/router/reasons.py` with frozen canonical string constants: `REASON_COMPANY_NAME_INFERRED = "company_name_inferred"`, `REASON_SPAM_GATE = "post_extraction_spam_gate_failed"`, `REASON_SECONDARY_FLOOR = "secondary_identifiers_insufficient"`, `REASON_UPSTREAM_FAILURE = "upstream_extraction_failed"`, plus `AFFIRMATIVE_*` and `INFORMATIONAL_*` string constants per research.md Decisions 9 and 10 (e.g., `AFFIRMATIVE_NAME_EXPLICIT`, `INFORMATIONAL_UPSTREAM_PARTIAL`, `INFORMATIONAL_CONTRACT_VIOLATION_PRESENT_INFERRED_BOTH_TRUE`)
- [X] T009 [P] [US1 bootstrap] Create the minimal green-path fixture `tests/fixtures/router/clean_explicit_name_full_identity.json` — schema-valid `edge_extraction_output.json` with `status="success"`, `contract_set_version="1.0.0"`, an explicit grounded `company_name`, a complete address (city/state/postal_code grounded), one grounded tax_id, and grounded website+email so every downstream rule can resolve against it
- [X] T010 Create `src/ledgerlinc_ocr/router/input_loader.py` implementing `load_and_validate(path: Path) -> dict` that raises `MissingInputError` / `UnreadableInputError` / `MalformedInputError` / `VersionDriftError` with the precise semantics in FR-003 and `contracts/cli-contract.md`. MUST validate against `contracts/stage1_vendor_identity/v1.0.0/edge_extraction_output.schema.json` via `ledgerlinc_ocr.validator` (research.md Decision 1). No rule logic, no output.
- [X] T011 Create `src/ledgerlinc_ocr/router/artifact.py` implementing `assemble_and_write(folder: Path, artifact: dict) -> Path` that (a) validates the dict against `routing_decision.schema.json` BEFORE any filesystem write, raising `ContractAssertionError` on failure; (b) writes atomically via temp-file + `os.replace`, dumping with `json.dumps(artifact, indent=2, sort_keys=False, ensure_ascii=False) + "\n"` (research.md Decision 7); (c) returns the final path. No rule logic.
- [X] T012 [P] Create `tests/unit/router/test_version.py` verifying (a) `POLICY_VERSION` is a non-empty string, (b) `build_pipeline_version()` returns a non-empty string with the `stage1-routing-v` prefix, (c) both are stable (calling twice returns identical values)

**Checkpoint**: Foundation ready. User story implementation can now begin.

---

## Phase 3: User Story 1 - Emit A Schema-Valid Deterministic `routing_decision.json` For One Document (Priority: P1) 🎯 MVP

**Goal**: One-command routing of a per-document folder that produces a schema-valid `routing_decision.json` next to the input, byte-identical across reruns (except `processed_at`), with `consensus_summary` pinned to the stage 1 single-voter values and `reasons` fully populated even for `edge_accept`.

**Independent Test**: Using the fixture from T009, run `python -m ledgerlinc_ocr.router route <folder>`. Verify the output passes `python -m ledgerlinc_ocr.validator validate artifact --schema routing_decision <folder>/routing_decision.json`, the `document_id` matches the input, `consensus_summary` is `{"mode":"single_voter_baseline","agreement_level":"not_applicable"}`, `decision == "edge_accept"`, `review_status == {"manual_review_required": false, "review_reason": null}`, and `reasons` contains at least one affirmative entry. Two consecutive runs diff only on `processed_at`.

### Tests for User Story 1

- [X] T013 [P] [US1] Create `tests/unit/router/test_checks.py` with one test per `checks` boolean (`company_name_present`, `company_name_inferred`, `address_has_minimum_components`, `at_least_one_tax_id_present`, `website_or_email_present`, `post_extraction_spam_gate_passed`) covering grounded / null / partial inputs; tests call the functions in `checks.py` directly (unit level, no filesystem)
- [X] T014 [P] [US1] Create `tests/unit/router/test_scores.py` verifying the canonical FR-017 formulas EXACTLY: `company_name_score` binary (1.0 iff explicit+grounded; 0.0 otherwise), `address_score` = grounded/5 over {street_1, city, state, postal_code, country} (research.md Decision 5), `tax_id_score` = grounded/4, `contact_score` = grounded/3 over {website, phone, email}, `overall_vendor_identity_score` = arithmetic mean of the four. Include boundary cases: all null → 0.0; all grounded → 1.0
- [X] T015 [P] [US1] Create `tests/unit/router/test_input_loader.py` covering missing file → `MissingInputError`, unreadable bytes → `UnreadableInputError`, malformed JSON → `MalformedInputError`, schema-invalid content → `MalformedInputError`, `contract_set_version != "1.0.0"` → `VersionDriftError`
- [X] T016 [P] [US1] Create `tests/unit/router/test_artifact.py` verifying (a) schema-invalid dict is rejected BEFORE any file appears on disk, (b) successful write is atomic (no partial `.tmp` leftover on success), (c) JSON is serialized with `indent=2` and trailing newline per research.md Decision 7
- [X] T017 [P] [US1] Create `tests/integration/router/test_us1_schema_valid.py` (AC#1 + AC#2): stage the T009 fixture in a tmp folder, invoke the router CLI via `subprocess`, assert exit code 0 and that the written artifact validates against `routing_decision.schema.json`, `contract_set_version == "1.0.0"`, `document_id` matches input, `processed_at` is a valid ISO-8601 UTC `Z`-suffixed string, `pipeline_version` and `policy_version` are non-empty
- [X] T018 [P] [US1] Create `tests/integration/router/test_us1_consensus_summary.py` (AC#3): assert `consensus_summary == {"mode":"single_voter_baseline","agreement_level":"not_applicable"}` exactly
- [X] T019 [P] [US1] Create `tests/integration/router/test_us1_decision_review_status_consistency.py` (AC#4): assert `decision == "edge_accept"` iff `manual_review_required == false` AND `review_reason is None`, and the inverse, using two fixtures (green path from T009 and a missing-name fixture — minimal inline variant; the canonical missing-name fixture lands in T026)
- [X] T020 [P] [US1] Create `tests/integration/router/test_us1_reasons_traceability.py` (AC#5): assert the green-path `edge_accept` emits at least one affirmative entry in `reasons` (FR-016); and that for `edge_review_required`, `review_status.review_reason` equals the highest-priority entry in `reasons` (exercised lightly here; exhaustively in US3 priority tests)
- [X] T021 [P] [US1] Create `tests/integration/router/test_us1_determinism.py` (AC#6, SC-004): run the CLI twice against the same fixture, diff both artifacts; assert bytes are identical EXCEPT the `processed_at` field (verify by parsing JSON, popping `processed_at`, comparing canonical serializations)
- [X] T022 [P] [US1] Create `tests/integration/router/test_us1_no_side_effects.py` (AC#7): stage a fixture folder containing `edge_extraction_output.json`, `preprocess_output.json`, `expected.json`, `notes.md`, `source.pdf`, and a `votes/` dir; after running the router, assert (a) every non-output file's mtime and content hash are unchanged, (b) no file is created outside the folder, (c) reserved filenames `final_structured_payload.json` and `evaluation_document.json` are not created, (d) `votes/` is untouched

### Implementation for User Story 1

- [X] T023 [US1] Create `src/ledgerlinc_ocr/router/checks.py` with pure functions `compute_checks(input_dict: dict) -> dict` returning the six booleans per FR-009–FR-013 and the grounding helper `is_grounded(field: dict) -> bool` (non-null value AND non-empty evidence). No scoring, no rules.
- [X] T024 [US1] Create `src/ledgerlinc_ocr/router/scores.py` with pure function `compute_scores(input_dict: dict) -> dict` implementing the five FR-017 formulas (clarification Q2 + research.md Decision 5 for `address_score` denominator). Confidence MUST NOT appear anywhere in this module (FR-018).
- [X] T025 [US1] Create `src/ledgerlinc_ocr/router/pipeline.py` with `run(folder: Path, pipeline_version: str, policy_version: str) -> Path` orchestrating: load+validate input → compute checks → compute scores → assemble green-path artifact (decision=`edge_accept`, review_status cleared, `reasons` with affirmative entries per FR-016, `consensus_summary` pinned, `processed_at` = current UTC Z-second per Decision 8) → validate-and-write. Rule logic deferred to later phases via a placeholder `apply_rules(...)` that for this task always returns the green-path decision (no forcing rules yet). Also create `src/ledgerlinc_ocr/router/__main__.py` and `src/ledgerlinc_ocr/router/cli.py` with the `route` subcommand surface pinned by `contracts/cli-contract.md` and FR-025.

**Checkpoint**: US1 MVP complete. The router processes the green-path fixture end-to-end and emits a schema-valid, deterministic artifact. Rule enforcement lands in US2–US5.

---

## Phase 4: User Story 2 - Missing-Name Invariant Routes To Review With The Canonical Reason (Priority: P1)

**Goal**: Enforce the constitutional Principle IV invariant — any input with `company_name.inferred == true` OR `company_name.present == false` routes to `edge_review_required` with `review_reason == "company_name_inferred"` exactly.

**Independent Test**: Run the router against fixtures `missing_name_inferred.json` (name missing/inferred) and `missing_name_with_strong_secondaries.json` (missing name + two grounded secondaries). Assert both produce `decision == "edge_review_required"` and `review_reason == "company_name_inferred"` exactly. Assert strong secondaries do NOT override. Assert every `edge_accept` document carries `company_name_present == true AND company_name_inferred == false` in `checks`.

### Tests for User Story 2

- [X] T026 [P] [US2] Create `tests/fixtures/router/missing_name_inferred.json` — schema-valid input with `vendor_candidate.company_name = {"value": "Acme Guess", "confidence": 0.3, "evidence": ["line_0"], "present": false, "inferred": true}` plus at least one grounded secondary (so the missing-name rule clearly outranks secondary-floor in later tests)
- [X] T027 [P] [US2] Create `tests/fixtures/router/missing_name_with_strong_secondaries.json` — identical to T026's `company_name` block but with grounded address (city+state+postal), grounded EIN, grounded website AND email, grounded phone — i.e., overwhelming secondary evidence
- [X] T028 [P] [US2] Create `tests/integration/router/test_us2_missing_name_canonical_string.py` (AC#1, AC#2, AC#3): run against T026; assert `decision == "edge_review_required"`, `manual_review_required == true`, `review_reason == "company_name_inferred"` exactly (byte-level string comparison, no variants); assert `checks.company_name_present == false` AND `checks.company_name_inferred == true`; assert the reason appears in the `reasons` array
- [X] T029 [P] [US2] Create `tests/integration/router/test_us2_missing_name_vs_strong_secondaries.py` (AC#4): run against T027; assert `decision == "edge_review_required"` stands despite strong secondaries; assert `review_reason == "company_name_inferred"` (missing-name outranks secondary-floor per FR-015 priority)
- [X] T030 [P] [US2] Create `tests/integration/router/test_us2_edge_accept_requires_explicit_name.py` (AC#5): run against T009's green-path fixture; assert every `edge_accept` decision the router emits has `checks.company_name_present == true AND checks.company_name_inferred == false`

### Implementation for User Story 2

- [X] T031 [US2] Create `src/ledgerlinc_ocr/router/rules.py` with `apply_rules(checks: dict, scores: dict, input_dict: dict) -> RuleResult` returning the fired rule IDs and their canonical reason strings. Implement ONLY the missing-name rule in this task: fires iff `company_name.inferred == true` OR `company_name.present == false`, emits `REASON_COMPANY_NAME_INFERRED`. Wire `pipeline.py` to use `apply_rules(...)` and map results through `reasons.py` into the artifact's `decision`, `review_status`, and priority-ordered `reasons` array per FR-015.

**Checkpoint**: US2 complete. Missing-name invariant holds. Spam-gate, secondary-floor, and upstream-failure rules still return no-fire.

---

## Phase 5: User Story 3 - Secondary Identifier Floor Forces Review When Vendor Grounding Is Thin (Priority: P2)

**Goal**: Enforce `>= 2` grounded secondary identifiers from the 4-slot set `{address_has_minimum_components, at_least_one_tax_id_present, website_or_email_present, phone-grounded}` (research.md Decision 6) or route to `edge_review_required` with `review_reason == "secondary_identifiers_insufficient"`. Pin `address_has_minimum_components` as `city AND state AND postal_code` grounded. Pin `at_least_one_tax_id_present` to require evidence grounding, not just a non-null value.

**Independent Test**: Run the router against three fixtures with an explicit grounded `company_name` and varying secondary strength: A=zero, B=exactly one, C=exactly two. Assert A+B route to `edge_review_required` with secondary-floor reason; C routes to `edge_accept`. Assert the six `checks` booleans reflect inputs faithfully. Assert priority order wins when missing-name AND secondary-floor both fire.

### Tests for User Story 3

- [X] T032 [P] [US3] Create `tests/fixtures/router/explicit_name_zero_secondaries.json` (AC#1): grounded explicit company_name; all address components null; all tax_ids null; website/phone/email all null
- [X] T033 [P] [US3] Create `tests/fixtures/router/explicit_name_one_secondary.json` (AC#2): grounded explicit company_name; website grounded; everything else null (exactly one slot)
- [X] T034 [P] [US3] Create `tests/fixtures/router/explicit_name_two_secondaries.json` (AC#3): grounded explicit company_name; address grounded (city+state+postal_code); email grounded; tax_ids and phone null — expect two floor slots satisfied → `edge_accept`
- [X] T035 [P] [US3] Create `tests/integration/router/test_us3_secondary_identifier_floor.py` (AC#1, AC#2, AC#3) covering all three fixtures and the floor threshold
- [X] T036 [P] [US3] Create `tests/integration/router/test_us3_address_minimum_components.py` (AC#4): parametrize across {city-only, state-only, postal-only, city+state, city+postal, state+postal, city+state+postal} asserting `address_has_minimum_components` is true ONLY for the full triple
- [X] T037 [P] [US3] Create `tests/integration/router/test_us3_tax_id_floor.py` (AC#5): parametrize across {non-null value but empty evidence → false, null value → false, grounded ein → true, multiple grounded tax_ids → still counts as one floor slot}; also verify `at_least_one_tax_id_present` is true iff ≥1 slot is grounded
- [X] T038 [P] [US3] Create `tests/integration/router/test_us3_priority_order.py` (AC#6): fixture with missing-name AND secondary-deficit both firing; assert `reasons` contains BOTH canonical strings in the order `[company_name_inferred, secondary_identifiers_insufficient]` per FR-015; assert `review_reason == "company_name_inferred"` (missing-name outranks secondary-floor)

### Implementation for User Story 3

- [X] T039 [US3] Extend `src/ledgerlinc_ocr/router/rules.py` with the secondary-identifier floor rule: count grounded slots across `{checks.address_has_minimum_components, checks.at_least_one_tax_id_present, checks.website_or_email_present, phone-grounded-bool}` (phone-grounded computed inline from `vendor_candidate.phone` per research.md Decision 6). If count `< 2` AND no higher-priority rule fired, append `REASON_SECONDARY_FLOOR`. Ensure `reasons` ordering follows FR-015 priority even when multiple rules fire (extend the `reasons.py` ordering helper here if needed).

**Checkpoint**: US3 complete. Secondary-identifier floor enforced with phone treated as an independent 4th slot. Priority order between missing-name and secondary-floor demonstrated.

---

## Phase 6: User Story 4 - Post-Extraction Spam Gate Catches All-Noise Documents (Priority: P2)

**Goal**: Enforce the spam-gate rule — if every structural vendor_candidate field is null simultaneously (`company_name.value == null` AND all address components null AND all tax_ids null AND website/phone/email all null), fire `REASON_SPAM_GATE`. Pin its threshold as part of `policy_version` (changing it bumps `policy_version`).

**Independent Test**: Run the router against `all_null_spam.json`. Assert `checks.post_extraction_spam_gate_passed == false`, `decision == "edge_review_required"`, `review_reason == "post_extraction_spam_gate_failed"`. Run against T009's green-path fixture. Assert `post_extraction_spam_gate_passed == true` and spam-gate contributes nothing to `reasons`.

### Tests for User Story 4

- [X] T040 [P] [US4] Create `tests/fixtures/router/all_null_spam.json` — schema-valid input where `vendor_candidate.company_name.value == null` AND every address component value is null AND every tax_id value is null AND `website`, `phone`, `email` all null; `extraction_notes` or `warnings` note the empty page
- [X] T041 [P] [US4] Create `tests/integration/router/test_us4_post_extraction_spam_gate.py` (AC#1, AC#2, AC#5): run against T040 and T009; assert spam-gate boolean + reason behavior; assert for the spam fixture `overall_vendor_identity_score` is `0.0` or near-zero (every per-category score is 0 → mean is 0) per AC#5
- [X] T042 [P] [US4] Create `tests/integration/router/test_us4_spam_gate_policy_version.py` (AC#3): assert `policy_version` is present on the spam-gate output (round-trip through `version.POLICY_VERSION`) — this test is the enforcement point for SC-010; document in a comment that any threshold change requires bumping `POLICY_VERSION` and updating this test's expected value
- [X] T043 [P] [US4] Create `tests/integration/router/test_us4_priority_over_spam_gate.py` (AC#4): fixture with spam-gate firing AND missing-name firing (i.e., `company_name.value != null` is impossible under the pure spam threshold, so construct a case where `company_name.inferred == true` AND every other field is null — this still fires both spam-gate on the structural null condition AND missing-name). Assert `review_reason == "company_name_inferred"` (missing-name outranks spam-gate); assert both strings appear in `reasons` in the FR-015 order `[company_name_inferred, post_extraction_spam_gate_failed]`

### Implementation for User Story 4

- [X] T044 [US4] Extend `src/ledgerlinc_ocr/router/checks.py` with the `post_extraction_spam_gate_passed` boolean per FR-013. Extend `src/ledgerlinc_ocr/router/rules.py` with the spam-gate rule: fires iff `post_extraction_spam_gate_passed == false`; emits `REASON_SPAM_GATE` at priority 2. Confirm `reasons.py` ordering helper handles the 2-rule case (missing-name + spam-gate) in FR-015 order.

**Checkpoint**: US4 complete. Spam-gate is the only stage 1 spam defense (assumption from spec + checklist `routing-policy.md` CHK031). Priority between missing-name and spam-gate demonstrated.

---

## Phase 7: User Story 5 - Graceful Degradation Honors Input Status And Surfaces Hard Errors (Priority: P3)

**Goal**: Propagate input `status` correctly; default defensively on `status == "failure"`; exit non-zero with no artifact on hard errors (missing / unreadable / schema-invalid / version-drift); handle FR-024 contract violations (`present==true AND inferred==true`, `present==false AND inferred==false`).

**Independent Test**: Run the router against each of the five US5 conditions (success/partial/failure inputs; missing and schema-invalid inputs; version-drifted input). Assert per-scenario behavior matches AC#1–AC#6, with hard errors producing exit codes per `contracts/cli-contract.md`.

### Tests for User Story 5

- [X] T045 [P] [US5] Create `tests/fixtures/router/partial_upstream.json` (AC#2): green-path shape but `status == "partial"`, with `warnings` populated
- [X] T046 [P] [US5] Create `tests/fixtures/router/failure_upstream.json` (AC#3): minimally-populated vendor_candidate but `status == "failure"` with `warnings` naming the upstream failure
- [X] T047 [P] [US5] Create `tests/fixtures/router/version_drift.json` (AC#5): otherwise-valid input but `contract_set_version == "0.9.0"`
- [X] T048 [P] [US5] Create `tests/fixtures/router/forbidden_present_true_inferred_true.json` (FR-024): schema-valid shape but `vendor_candidate.company_name.present == true` AND `.inferred == true`
- [X] T049 [P] [US5] Create `tests/integration/router/test_us5_partial_input.py` (AC#1, AC#2): run against T009 (success → output status success) and T045 (partial → output status partial + `INFORMATIONAL_UPSTREAM_PARTIAL` entry in reasons)
- [X] T050 [P] [US5] Create `tests/integration/router/test_us5_failure_input.py` (AC#3): run against T046; assert output status is `"partial"` or `"failure"`, `decision == "edge_review_required"`, `review_reason == "upstream_extraction_failed"`, the upstream failure is named in reasons
- [X] T051 [P] [US5] Create `tests/integration/router/test_us5_hard_errors.py` (AC#4, AC#5, SC-006): parametrize across {missing file, unreadable file, schema-invalid JSON, T047 version-drift}; assert exit code is non-zero per `contracts/cli-contract.md` (code 2 for malformed/version-drift; code 3 for internal), NO `routing_decision.json` exists in the folder afterward, and stderr contains a human-readable cause
- [X] T052 [P] [US5] Create `tests/integration/router/test_us5_schema_valid_on_bad_input.py` (AC#5 clarification): run against T045 and T046; assert each emitted `routing_decision.json` still passes `routing_decision.schema.json` validation (status `"partial"` / `"failure"` is a value, not a schema violation)
- [X] T053 [P] [US5] Create `tests/integration/router/test_us5_reconstruction.py` (AC#6, SC-005, SC-009): for each of {T009, T026, T034, T040, T045, T046}, load only the written `routing_decision.json` and the documented rule set; assert the `decision` can be reconstructed from `checks` + `scores` + `reasons` + `policy_version` alone (no access to the input)
- [X] T054 [P] [US5] Create `tests/integration/router/test_extractor_invariant_violation.py` (FR-024): run against T048; assert output `status == "partial"`, `decision == "edge_review_required"`, `reasons` contains `INFORMATIONAL_CONTRACT_VIOLATION_PRESENT_INFERRED_BOTH_TRUE` (per research.md Decision 11), and the router did NOT silently "correct" the violation
- [X] T055 [P] [US5] Create `tests/integration/router/test_no_model_no_cloud.py` (FR-019): assert the router module tree contains no imports of `requests`, `httpx`, `ollama`, `paddleocr`, `falcon`, or any model/network library (scan via `grep` on the `router/` package); assert the router performs zero network calls when invoked (run the CLI via subprocess with a `sitecustomize.py` on `PYTHONPATH` that patches `socket.socket.connect` and `socket.create_connection` to raise — NOT the `socket.socket` class itself, since `ssl.py` subclasses it at import time; run against T009; assert success)

### Implementation for User Story 5

- [X] T056 [US5] Extend `src/ledgerlinc_ocr/router/rules.py` with the upstream-failure rule (fires iff input `status == "failure"`; emits `REASON_UPSTREAM_FAILURE` at priority 4) and the contract-violation path (FR-024; fires iff forbidden combos observed in `vendor_candidate.company_name`; emits the `INFORMATIONAL_CONTRACT_VIOLATION_*` informational entry and forces `status = "partial"` + `decision = "edge_review_required"`). Extend `pipeline.py` to map input `status` to output `status` per FR-020 and to append `INFORMATIONAL_UPSTREAM_PARTIAL` when input is `"partial"`. Confirm `reasons.py` ordering helper emits the full FR-015 sequence (priority rules 1–4, then affirmatives, then informational entries) deterministically.

**Checkpoint**: All five user stories complete. The router handles green path, missing-name, secondary-floor, spam-gate, partial/failure inputs, and contract violations, all deterministically and all byte-identical across reruns (except `processed_at`).

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Validate the slice against release gates, sweep the corpus for determinism, walk the quickstart, and update cross-cutting docs.

- [X] T057 [P] Run the full contract-checklist walkthrough (`specs/008-routing/checklists/contract.md`) against the spec and the delivered code; record any gaps as follow-up commits
- [X] T058 [P] Run the full determinism-checklist walkthrough (`specs/008-routing/checklists/determinism.md`) against the delivered code; confirm every item is met or explicitly deferred with rationale
- [X] T059 [P] Run the full routing-policy-checklist walkthrough (`specs/008-routing/checklists/routing-policy.md`); confirm canonical strings, priority order, and `policy_version` lifecycle are wired correctly
- [X] T060 [P] Run the full failure-handling-checklist walkthrough (`specs/008-routing/checklists/failure-handling.md`); confirm hard-error exit codes, no-partial-artifact guarantee, and defensive decision defaults match
- [X] T061 Create a corpus-determinism sweep test `tests/integration/router/test_corpus_determinism_sweep.py` that (if `tests/stage1_vendor_identity/inv_*/edge_extraction_output.json` fixtures exist) runs the router twice over each, diffs the artifacts, and asserts byte-identity except for `processed_at`. If the corpus is not yet populated, the test skips with a message pointing at 005 and 006
- [X] T062 Walk `specs/008-routing/quickstart.md` end-to-end in a clean devcontainer; fix any drift between the written doc and the delivered CLI (e.g., argument names, output field ordering, exit-code messages)
- [X] T063 [P] Update `CLAUDE.md` "Key References" section to add a block for `specs/008-routing/` listing `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/cli-contract.md`, `quickstart.md`, and the four checklists (parallel to the 003 block)
- [X] T064 [P] Update `docs/stage1-vendor-identity/architecture.md` (if needed) so the routing step references the delivered CLI (`python -m ledgerlinc_ocr.router route`) and the canonical reason-string vocabulary — do NOT restate content; cross-link to the spec
- [X] T065 Run the full test suite (`pytest tests/unit/router tests/integration/router tests/contract_tests`) and confirm zero failures, zero skips on required scenarios, and that coverage includes every acceptance scenario from US1–US5

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Stories (Phase 3–7)**: All depend on Foundational phase completion
  - **US1 (P1)** is the MVP and must land first; it delivers the green-path artifact that US2–US5 extend
  - **US2 (P1)** and **US3 (P2)**, **US4 (P2)**, **US5 (P3)** each extend the rule set; they can be implemented in parallel ONCE US1 has shipped the pipeline shape, because they touch different branches in `rules.py`/`reasons.py` and have disjoint fixtures and integration test files. Merge conflicts in `rules.py` are managed by landing priority order
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational (Phase 2) — No dependencies on other stories
- **US2 (P1)**: Can start after US1's `pipeline.py` skeleton + `apply_rules(...)` contract exist (T025); missing-name rule is the first real rule to land
- **US3 (P2)**: Can start after US2 (priority ordering uses US2's `REASON_COMPANY_NAME_INFERRED` as the higher-priority comparator in T038)
- **US4 (P2)**: Can start after US3 (priority ordering T043 requires both earlier rules' canonical strings and the reasons-ordering helper to exist). Otherwise independent
- **US5 (P3)**: Can start after US4 — upstream-failure rule and contract-violation path require the complete `reasons.py` ordering helper (all four priority slots) to be in place

### Within Each User Story

- Fixtures (T009, T026, T027, T032, T033, T034, T040, T045, T046, T047, T048) are [P] — different files, no cross-dependencies
- Unit tests (T012, T013, T014, T015, T016) are [P] within the same phase — different files
- Integration tests within a single user story are [P] — different files, different fixtures
- Implementation tasks that touch the SAME file (`rules.py`, `reasons.py`, `pipeline.py`) are sequential and NOT [P]: T031 → T039 → T044 → T056

### Parallel Opportunities

- Phase 1: T002, T003, T005 are [P]
- Phase 2: T006, T007, T008, T009, T012 are [P]; T010 and T011 are sequential against distinct files but depend on T006–T008
- Phase 3 (US1): T013–T022 are all [P] (all in different files); T023, T024 are [P]; T025 is the orchestration task, sequential after T023 + T024
- Phase 4 (US2): T026–T030 are [P]; T031 is sequential (touches `rules.py`)
- Phase 5 (US3): T032–T038 are [P]; T039 is sequential (extends `rules.py`)
- Phase 6 (US4): T040–T043 are [P]; T044 is sequential (extends `rules.py`)
- Phase 7 (US5): T045–T055 are [P]; T056 is sequential (extends `rules.py` + `pipeline.py`)
- Phase 8: T057–T060, T063, T064 are [P]; T061, T062, T065 are sequential (they exercise the full delivered system)

---

## Parallel Example: User Story 1

```bash
# Launch all US1 fixtures + unit tests together:
Task: "Create tests/fixtures/router/clean_explicit_name_full_identity.json"
Task: "Create tests/unit/router/test_checks.py"
Task: "Create tests/unit/router/test_scores.py"
Task: "Create tests/unit/router/test_input_loader.py"
Task: "Create tests/unit/router/test_artifact.py"

# Launch all US1 integration test scaffolds in parallel:
Task: "Create tests/integration/router/test_us1_schema_valid.py"
Task: "Create tests/integration/router/test_us1_consensus_summary.py"
Task: "Create tests/integration/router/test_us1_decision_review_status_consistency.py"
Task: "Create tests/integration/router/test_us1_reasons_traceability.py"
Task: "Create tests/integration/router/test_us1_determinism.py"
Task: "Create tests/integration/router/test_us1_no_side_effects.py"

# Launch the two pure modules in parallel before orchestration:
Task: "Create src/ledgerlinc_ocr/router/checks.py"
Task: "Create src/ledgerlinc_ocr/router/scores.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all rules)
3. Complete Phase 3: User Story 1 (green-path only; no forcing rules yet — the artifact is always `edge_accept`)
4. **STOP and VALIDATE**: Run the quickstart against T009's fixture; confirm schema validity and byte-identical rerun
5. This slice is a valid MVP: the evaluator (007) can begin integration testing against a schema-valid artifact before the forcing rules ship

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 → Green-path determinism + schema validity (MVP!)
3. US2 (Principle IV) → Missing-name invariant lands — unblocks the missing-name corpus (SC-002, SC-008)
4. US3 → Secondary-identifier floor lands — aligns router with evaluator's `vendor_identity_passed` gate
5. US4 → Spam-gate lands — closes the "garbage in, accepted vendor identity out" hole
6. US5 → Graceful degradation + hard errors — makes every failure mode legible
7. Polish → Release-gate checklists + corpus sweep + documentation

### Parallel Team Strategy

With multiple developers after US1 ships:

1. Developer A: US2 (missing-name) → US5 (graceful degradation) — because US5 inherits priority-ordering machinery laid down by US2
2. Developer B: US3 (secondary floor) — independent fixtures and tests
3. Developer C: US4 (spam-gate) — independent fixtures and tests
4. Merge order on `rules.py`: US2 → US3 → US4 → US5 (priority order; each appends to the same table)
5. Checklists in Phase 8 can be walked in parallel by any reviewer

---

## Phase 9: Post-Analyze Remediation

**Purpose**: Close the three MEDIUM findings and one LOW finding raised by `/speckit.analyze` against the delivered implementation. All 65 prior tasks are complete; this phase adds coverage that the audit identified as missing. No spec or plan changes — these tasks tighten enforcement of requirements that are already written.

**Dependencies**: Phases 1–8 complete. No phase ordering inside Phase 9; all four tasks touch disjoint files and can run in parallel.

- [X] T066 [P] Finding C1 (SC-001 timing budget): Add a timing assertion in `tests/integration/router/test_us1_schema_valid.py` (or a new `tests/integration/router/test_sc001_timing_budget.py` if isolation is cleaner) that stages the T009 fixture, runs the CLI via `subprocess`, measures wall-clock from `subprocess.run` entry to exit, and asserts the single-document route completes within a 1500 ms CI-tolerant budget (spec SC-001 pins 200 ms on a developer workstation; CI machines are noisier, so the runtime bound is widened but the intent is preserved). Add an inline comment referencing SC-001 and noting the CI-tolerance rationale so a future tightening is straightforward.
- [X] T067 [P] Finding C2 (FR-002 key-order): Extend `tests/integration/router/test_us1_schema_valid.py` with a new test `test_checks_and_scores_key_order_matches_schema` that reads the raw bytes of the written `routing_decision.json`, loads it via `json.loads(..., object_pairs_hook=list)` or `json.JSONDecoder().raw_decode` to preserve insertion order, and asserts the `checks` and `scores` blocks emit their keys in exactly the order declared by the `required` arrays in `contracts/stage1_vendor_identity/v1.0.0/routing_decision.schema.json`. This enforces the FR-002 clause "implementation-dependent key ordering is forbidden".
- [X] T068 [P] Finding C3 (SC-010 PR-review gate): Add a new section `## POLICY_VERSION Bump Gate (PR-review, not runtime)` to `specs/008-routing/checklists/routing-policy.md` with bullets naming (a) the rule-layer modules that trigger a required bump — `src/ledgerlinc_ocr/router/rules.py`, `checks.py`, `reasons.py`, `version.py`, and the canonical reason-string constants; (b) the reviewer's responsibility to reject any such PR missing a `POLICY_VERSION` edit; (c) a pointer to FR-005 and SC-010 as the authoritative language. The checklist is the process home for a non-runtime gate; do NOT add CI automation in this task (that would require a separate spec/amendment).
- [X] T069 [P] Finding C5 (symmetric FR-024 case): Create `tests/fixtures/router/forbidden_present_false_inferred_false.json` — schema-valid `edge_extraction_output.json` identical to `forbidden_present_true_inferred_true.json` except `vendor_candidate.company_name.present == false` AND `.inferred == false`. Parametrize `tests/integration/router/test_extractor_invariant_violation.py` to exercise both forbidden combinations; assert each produces `status == "partial"`, `decision == "edge_review_required"`, and a contract-violation reason entry.

**Checkpoint**: All four findings closed. Re-run `pytest tests/unit/router tests/integration/router tests/contract_tests` and confirm zero failures. Re-run `/speckit.analyze` to confirm C1/C2/C3/C5 no longer appear (or have moved to "Resolved").

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability (US1–US5 matches spec.md priority ordering: P1, P1, P2, P2, P3)
- Each user story is independently completable and testable — US2–US5 each extend the rules table, fixtures, and integration-test tree in disjoint files
- Verify tests fail before implementing the corresponding rule (classic TDD; the test files are written as [P] alongside fixtures, then the rule code flips them to green)
- Commit after each task or logical group; auto-commit hooks are configured per-event in `.specify/extensions/git/git-config.yml`
- Byte-identical-except-`processed_at` is the binding determinism guarantee (FR-021, SC-004); every integration test that writes an artifact should assert it
- Confidence values MUST NOT appear in any check, score, rule, or gate (FR-018, clarification Q1); grep-enforce this as a Phase 8 lint if needed
- Canonical reason strings are load-bearing — `"company_name_inferred"` in particular coordinates with evaluator 007's US4; changing any canonical string is a `policy_version` bump (SC-010)
- Avoid: vague tasks, same-file conflicts inside one phase, cross-story dependencies that break independence of US3/US4/US5 from US2
