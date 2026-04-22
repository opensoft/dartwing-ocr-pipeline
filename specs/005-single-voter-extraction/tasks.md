---
description: "Task list for 005-single-voter-extraction"
---

# Tasks: Single-Voter Edge Extraction (Stage 1 Vendor-Identity)

**Input**: Design documents from `/specs/005-single-voter-extraction/`
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/cli-contract.md`, `contracts/voter-config.md`, `quickstart.md`

**Tests**: Included. The spec's per-story "Independent Test" sections and Constitution Principle V (benchmarkable / reproducible delivery) make tests load-bearing for this slice. Reconciliation in particular is a deterministic pure function (SC-009, research §R-013), so every reconciliation rule has a dedicated unit test; every user-story acceptance scenario has an integration test.

**Organization**: Tasks are grouped by user story. Phase 1 + Phase 2 are shared infrastructure that unblocks every story. Phase 3 (US1) is the MVP — end-to-end pipeline producing a schema-valid artifact. Phases 4–7 (US2–US5) layer acceptance-scenario tests against the MVP pipeline, closing any gaps the fixtures surface.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks).
- **[Story]**: Which user story the task belongs to (US1–US5). Setup / Foundational / Polish tasks carry no story label.
- File paths are absolute within the repo root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project layout and dependency wiring so every later phase starts from a consistent base.

- [X] T001 Create module skeleton `src/ledgerlinc_ocr/extract/` with empty `__init__.py`, `__main__.py`, `cli.py`, `pipeline.py`, `config.py`, `prompt.py`, `parse.py`, `reconcile.py`, `artifact.py`, `errors.py`, `exit_codes.py`, `version.py`
- [X] T002 Create voter seam skeleton under `src/ledgerlinc_ocr/extract/voters/`: `__init__.py`, `base.py`, `ollama.py`, `stub.py`, and a `configs/` directory plus `configs/prompts/` directory (both empty for now)
- [X] T003 Add runtime dependencies to `pyproject.toml` under `[project].dependencies`: `httpx>=0.27,<1`, `PyYAML>=6.0,<7`. Retain existing deps.
- [X] T004 [P] Reinstall editable package with new deps: `.venv/bin/pip install -e ".[dev]"` (verifies the new deps resolve on Python 3.12 in the devcontainer)
- [X] T005 [P] Create test tree: `tests/unit/extract/__init__.py`, `tests/integration/extract/__init__.py`, `tests/fixtures/extract/.gitkeep`
- [X] T006 [P] Register new test paths in `pyproject.toml` under `[tool.pytest.ini_options].testpaths` only if not already covered — `tests/unit` and `tests/integration` roots already exist from 003; no-op if already present.
- [X] T007 Wire console script entry in `pyproject.toml` under `[project.scripts]`: `ledgerlinc-extract = "ledgerlinc_ocr.extract.cli:main"` alongside the existing `ledgerlinc-preprocess` and `ledgerlinc-pipeline` entries.
- [X] T008 [P] Ensure packaged data is included for voter configs: update `pyproject.toml` `[tool.setuptools.package-data]` (or equivalent) so `ledgerlinc_ocr.extract.voters.configs/*.yaml` and `ledgerlinc_ocr.extract.voters.configs.prompts/*.md` ship with the wheel.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared primitives every user story depends on — typed errors, exit-code table, pipeline-version builder, voter-config loader (with pydantic validation), voter adapter Protocol, and the stub voter (testing seam for US4 + CI without Ollama).

**⚠️ CRITICAL**: No user story work begins until Phase 2 is green.

- [X] T009 [P] Implement typed errors in `src/ledgerlinc_ocr/extract/errors.py`: `InputContractDrift`, `OllamaUnreachable`, `OllamaModelUnavailable`, `MalformedResponse`, `UnrepairableResponse`, `VoterConfigInvalid`, `ArtifactAssemblyError`, `FolderWriteError`. Each carries a `message` and optional `detail` dict; no logic, no imports beyond stdlib.
- [X] T010 [P] Implement `src/ledgerlinc_ocr/extract/exit_codes.py` with the R-011 exit-code table as module constants: `EXIT_OK=0`, `EXIT_UNEXPECTED=1`, `EXIT_INPUT_CONTRACT_DRIFT=2`, `EXIT_OLLAMA_UNREACHABLE=3`, `EXIT_MODEL_UNAVAILABLE=4`, `EXIT_UNREPAIRABLE_RESPONSE=5`, `EXIT_VOTER_CONFIG_INVALID=6`, `EXIT_FOLDER_WRITE=7`. Include a `for_error(exc)` helper mapping errors.py classes to exit codes.
- [X] T011 [P] Implement `src/ledgerlinc_ocr/extract/version.py`: `build_pipeline_version()` returning `"{package_version}+{short_sha}"` per research.md §R-009. Read package version via `importlib.metadata.version("ledgerlinc-ocr")`; read short SHA from `ledgerlinc_ocr._build_sha` if importable, else fall back to `"unknown"`.
- [X] T012 [P] Implement `src/ledgerlinc_ocr/extract/config.py`: pydantic models `OllamaCallConfig`, `SamplingConfig`, `PromptConfig`, `ReconciliationConfig`, `ModelRuntimeConfig`, `VoterConfig` exactly as data-model.md specifies. All models configured with `extra = "forbid"`. Add `load_voter_config(name_or_path: str, base_dir: Path) -> VoterConfig` that resolves per contracts/voter-config.md (CLI path → `LEDGERLINC_VOTER_CONFIG_DIR/<name>.yaml` → packaged `voters/configs/<name>.yaml`), parses with `yaml.safe_load`, and raises `VoterConfigInvalid` on any YAML or validation error.
- [X] T013 [P] Implement the voter-adapter Protocol in `src/ledgerlinc_ocr/extract/voters/base.py`: `class VoterAdapter(Protocol)` with one method `call(rendered_prompt: str, config: VoterConfig) -> RawModelResponse`. Define `RawModelResponse` as a frozen dataclass with `body: str`, `duration_ms: int`, `model_echo: str | None`, `done: bool`. No implementation beyond the Protocol.
- [X] T014 [P] Implement the stub voter in `src/ledgerlinc_ocr/extract/voters/stub.py`: `class StubVoter` implementing `VoterAdapter`. Reads a fixture-path override from the voter config (extension key handled outside pydantic, per contracts/voter-config.md); returns a `RawModelResponse` whose `body` is the fixture file's contents. Zero network. Raises `FileNotFoundError` wrapped as `MalformedResponse` with fixture-path detail if the file is missing.
- [X] T015 [P] Write the packaged stub config `src/ledgerlinc_ocr/extract/voters/configs/stub.yaml` with the exact shape from contracts/voter-config.md "Stub voter" section, and a no-op prompt at `src/ledgerlinc_ocr/extract/voters/configs/prompts/stub_noop.md` (single line stating the stub voter does not use prompt content).
- [X] T016 [P] Write the packaged stage 1 config `src/ledgerlinc_ocr/extract/voters/configs/gemma-edge.yaml` with the exact shape from contracts/voter-config.md "gemma-edge.yaml" section. Prompt template path: `prompts/gemma_edge_extractor.md` (template body authored in US1 task T033; placeholder file with a TODO comment acceptable at this task's completion).
- [X] T017 [P] Unit test `tests/unit/extract/test_version.py`: verifies `build_pipeline_version()` format is `^\S+\+\S+$`, returns `"unknown"` as the SHA suffix when `_build_sha` module is absent (monkeypatch `importlib.import_module` or similar), and that two calls in the same process are byte-identical.
- [X] T018 [P] Unit test `tests/unit/extract/test_config.py`: happy-path load of `stub.yaml` through `load_voter_config`; rejects unknown top-level key (`extra = "forbid"`); rejects `voter_role="admin"` (enum); rejects `consensus_mode="three_voter"` (enum); rejects negative `timeout_seconds`; rejects `ungrounded_confidence_cap=1.5`. Every rejection raises `VoterConfigInvalid`.
- [X] T019 [P] Unit test `tests/unit/extract/test_exit_codes.py`: verifies the exit-code table values match R-011 exactly; verifies `for_error(OllamaUnreachable(...))` returns `3`; verifies unknown exception → `1`.
- [X] T020 [P] Unit test `tests/unit/extract/test_stub_voter.py`: verifies StubVoter reads a fixture file and returns a `RawModelResponse` with the file's contents as `body`; verifies missing fixture raises `MalformedResponse` with the path in `detail`.

**Checkpoint**: Phase 2 green — all foundational modules compile, unit tests pass. User-story work can proceed.

---

## Phase 3: User Story 1 - Produce a Schema-Valid `edge_extraction_output.json` For One Document (Priority: P1) 🎯 MVP

**Goal**: Running the extractor against a per-document folder containing a schema-valid `preprocess_output.json` writes an `edge_extraction_output.json` into the same folder that validates against the frozen v1.0.0 schema, carries matching `document_id` and `contract_set_version`, populates `model_runtime` and `vote_metadata` from the voter config, and populates every required `vendor_candidate` / `invoice_header_fields` sub-field with `{value, confidence, evidence}` (or the expanded shape for `total_amount`). Exits `0` on success.

**Independent Test**: Run `python -m ledgerlinc_ocr.extract --folder tests/fixtures/extract/us1_happy/ --voter stub` (where the stub fixture returns a canned clean JSON). Exit code `0`, `edge_extraction_output.json` written next to `preprocess_output.json`, `python -m ledgerlinc_ocr.validator validate artifact <path> --kind edge_extraction_output` passes, `document_id` matches, `contract_set_version == "1.0.0"`, `vote_metadata.voter_role == "primary_extractor"`, `vote_metadata.consensus_mode == "single_voter_baseline"`, `document_type.value == "invoice"`, every required sub-field present with the correct shape, `status == "success"`, `warnings == []`.

### Tests for User Story 1

> Write these first; they should FAIL until T033 lands.

- [X] T021 [P] [US1] Create happy-path fixture folder `tests/fixtures/extract/us1_happy/`: `preprocess_output.json` (small synthetic packet, one page, a handful of blocks/lines with realistic vendor-like text and known block_ids/line_ids) and `voter_response_clean.json` (canned model JSON: all required fields populated, every `evidence` array cites IDs that exist in `preprocess_output.json`, `company_name.value` set to the grounded string). Document the fixture's relation to the stub config (fixture path referenced from a test-local variant of stub.yaml).
- [X] T022 [P] [US1] Create `tests/fixtures/extract/us1_happy/voter_config.yaml` — a stub-voter config whose fixture-path extension key points at `voter_response_clean.json`. Used by the US1 tests through `--voter-config` rather than the packaged `stub.yaml`.
- [X] T023 [P] [US1] Integration test `tests/integration/extract/test_us1_schema_valid.py::test_ac1_artifact_written_and_validates` — covers US1 AC#1 (artifact written at `<folder>/edge_extraction_output.json`, validates against the frozen schema).
- [X] T024 [P] [US1] Integration test `tests/integration/extract/test_us1_ids_match.py::test_ac2_ids_and_timestamps` — covers US1 AC#2 (`document_id` equals input's; `contract_set_version == "1.0.0"`; `processed_at` parseable as ISO-8601; `pipeline_version` non-empty).
- [X] T025 [P] [US1] Integration test `tests/integration/extract/test_us1_vendor_block.py::test_ac3_vendor_candidate_shape` — covers US1 AC#3 (every required `vendor_candidate` sub-field present; shapes, bounds, evidence regex).
- [X] T026 [P] [US1] Integration test `tests/integration/extract/test_us1_header_block.py::test_ac4_invoice_header_fields` — covers US1 AC#4 (`invoice_number` / `invoice_date` shapes; `total_amount` expanded shape with `value` number-or-null and `currency` string-or-null).
- [X] T027 [P] [US1] Integration test `tests/integration/extract/test_us1_status_consistency.py::test_ac5_status_success_implies_no_hard_warning` — covers US1 AC#5 (`status == "success"` implies `warnings == []`; `status == "partial"` implies `len(warnings) >= 1`; `status == "failure"` implies at least one explanatory warning).
- [X] T028 [P] [US1] Integration test `tests/integration/extract/test_us1_no_sidecar_writes.py::test_ac6_folder_write_boundaries` — covers US1 AC#6 (extractor writes only `edge_extraction_output.json` into the folder; does not modify `preprocess_output.json`; does not create reserved downstream filenames `routing_decision.json`, `final_structured_payload.json`, `evaluation_document.json`, `consensus_output.json`, or anything under `votes/`). Use directory snapshot diff before/after.

### Implementation for User Story 1

- [X] T029 [P] [US1] Implement `src/ledgerlinc_ocr/extract/prompt.py`: `render_prompt(packet: dict, template_path: Path, voter_config: VoterConfig) -> str`. Loads the Markdown prompt template, substitutes a serialized view of the preprocessing packet (per-page `block_id: text` and `line_id: text` listings, plus document-level `ingestion_sources` status). Deterministic for a given `(packet, template)` pair. Use stdlib `string.Template` or `str.format_map` — no heavy templating engine.
- [X] T030 [P] [US1] Implement `src/ledgerlinc_ocr/extract/parse.py`: `parse_model_response(raw_body: str) -> tuple[dict, list[str]]`. Strict `json.loads` first; on failure, apply the minimal repair pipeline from research.md §R-007 (strip markdown code fences, strip leading/trailing prose, strip BOM); re-attempt `json.loads`. Returns `(parsed_dict, repair_trail)` where `repair_trail` lists every repair step that fired (empty on clean parse). Raises `UnrepairableResponse` if both attempts fail.
- [X] T031 [P] [US1] Implement the Ollama voter in `src/ledgerlinc_ocr/extract/voters/ollama.py`: `class OllamaVoter` implementing `VoterAdapter`. Reads `OLLAMA_BASE_URL` env var (raises `OllamaUnreachable` if unset or empty); POSTs to `{OLLAMA_BASE_URL}/api/generate` with body `{model, prompt, format, options: {temperature, seed, top_p, top_k, num_predict}}` per voter config. Single `httpx.Client` request with `httpx.Timeout(read=config.ollama.timeout_seconds, connect=config.ollama.connect_timeout_seconds)`. No retries. Maps `httpx.ConnectError` / `httpx.TimeoutException` → `OllamaUnreachable`. Detects "model not found" in response JSON (Ollama returns `{"error": "model '...' not found"}`) → raises `OllamaModelUnavailable`. Successful response → returns `RawModelResponse` with the `response` field body.
- [X] T032 [US1] Implement the deterministic reconciliation pipeline in `src/ledgerlinc_ocr/extract/reconcile.py` per data-model.md "Reconciliation State Machine": pure function `reconcile(packet, parsed, config, now, pipeline_version, repair_trail) -> dict`. Steps 1–8 exactly as written: metadata assembly, model-proposed field extraction (null-default on missing), evidence reconciliation (regex + resolve against `packet.evidence_index`), ungrounded-confidence cap, company-name `present`/`inferred` override, `document_type.value` coercion, status derivation per R-008 truth table, warnings + extraction_notes normalization. Post-conditions asserted before return (XOR invariant, no empty-string values, every evidence ID resolvable).
- [X] T033 [US1] Implement `src/ledgerlinc_ocr/extract/artifact.py`: `assemble_and_write(artifact_dict, folder_path)` that runs the in-repo validator against `contracts/stage1_vendor_identity/v1.0.0/edge_extraction_output.schema.json`, raises `ArtifactAssemblyError` on schema failure (should be unreachable — reconcile.py's post-conditions prevent it), then writes atomically via `edge_extraction_output.json.tmp-{pid}` → `os.replace(..., edge_extraction_output.json)` (FR-019 / FR-018 / US1 AC#6). Raises `FolderWriteError` on I/O failure.
- [X] T034 [US1] Implement `src/ledgerlinc_ocr/extract/pipeline.py`: `Pipeline.run(folder_path, voter_config, voter) -> Path`. Orchestrates: load `<folder>/preprocess_output.json`, validate against preprocess schema, check `contract_set_version == "1.0.0"` (raise `InputContractDrift` otherwise), call `render_prompt` → `voter.call(rendered_prompt, voter_config)` → `parse_model_response` → `reconcile(...)` → `assemble_and_write(...)`. Returns the written path. Captures `datetime.now(UTC)` once at start so `processed_at` is stable.
- [X] T035 [US1] Implement `src/ledgerlinc_ocr/extract/cli.py` and `src/ledgerlinc_ocr/extract/__main__.py`: argparse with `--folder` (required), `--voter` (required), `--voter-config` (optional override), `--log-level` (default `INFO`). `main(argv=None) -> int`. Selects `OllamaVoter` or `StubVoter` based on `model_runtime.provider` ("stub" → StubVoter, anything else → OllamaVoter). Catches every typed error class and returns the mapped exit code via `exit_codes.for_error`. Emits a single INFO-level stderr line on success naming the status + warnings count; emits ERROR-level stderr line with the exception's message on hard failure. `__main__.py` is a two-line dispatch to `cli.main`.
- [X] T036 [US1] Author the stage 1 prompt template `src/ledgerlinc_ocr/extract/voters/configs/prompts/gemma_edge_extractor.md` per research.md §R-006: system + user sections, explicit JSON-key list, ID map placeholder, evidence-first rules, company-name invariant rule. Keep the prompt deterministic (no dates, no run-specific text beyond the packet substitution).
- [X] T037 [US1] Add `contract_tests/test_edge_extraction_output_shape.py::test_us1_happy_fixture_shape` — loads the US1 happy-path fixture output (generated by the integration tests or inline), re-validates against the frozen schema, and asserts the `present XOR inferred` invariant. This is a thin schema-level guardrail on top of the integration tests.
- [X] T091 [P] [US1] Unit test `tests/unit/extract/test_reconcile_determinism.py` — closes the analysis C2 gap (SC-009). Call `reconcile(packet, parsed, config, now, pipeline_version, repair_trail)` twice with identical inputs (same dict objects, same frozen `now` datetime, same `pipeline_version` string) and assert the two returned dicts are byte-equal under `json.dumps(..., sort_keys=True)`. Include a second case that varies only `now` / `pipeline_version` and asserts only those two fields differ. This is the contractual determinism proof SC-009 claims.

**Checkpoint**: Phase 3 green — MVP runs end-to-end against the stub voter happy-path fixture, all US1 acceptance tests pass. SC-001, SC-007, SC-010 (in the happy-path sense), SC-009 (on the reconcile surface) demonstrated.

---

## Phase 4: User Story 2 - Every Extracted Field Is Grounded In The Preprocessing Evidence Packet (Priority: P1)

**Goal**: Every evidence ID in the output resolves to a real `block_id` or `line_id` in `preprocess_output.json`. Bogus IDs are filtered out, emit a warning, and downgrade confidence per FR-011. Fields with empty evidence after reconciliation still retain the model's `value` but have confidence capped.

**Independent Test**: Stage a per-document folder with a known `preprocess_output.json`; run the extractor against a stub-voter fixture whose response contains a mix of valid, malformed, and unresolvable evidence IDs. Verify every ID in the output resolves; dropped IDs appear in `warnings`; capped fields have `confidence <= UNGROUNDED_CONFIDENCE_CAP` (0.30 per research §R-003); `status == "partial"`.

### Tests for User Story 2

- [X] T038 [P] [US2] Create fixture `tests/fixtures/extract/us2_evidence/voter_response_bogus_evidence.json`: same packet as US1 but voter response claims evidence from IDs that don't exist in `preprocess_output.json` for half its fields, and malformed-pattern IDs (e.g., `p1_x5`, `b0`) for another field. Pair with a small `voter_config.yaml` pointing at this fixture.
- [X] T039 [P] [US2] Unit test `tests/unit/extract/test_reconcile_evidence.py`: exercise reconcile.py step 3 in isolation — feed a packet with a known `evidence_index`, feed a parsed response with (a) valid IDs that resolve, (b) pattern-malformed IDs, (c) pattern-valid IDs that don't resolve in this packet, (d) duplicated IDs. Assert final evidence arrays contain only resolved IDs, in first-seen order, deduplicated; assert one warning per dropped ID naming the field and the dropped ID.
- [X] T040 [P] [US2] Unit test `tests/unit/extract/test_reconcile_confidence_cap.py`: verify FR-011 cap is applied per-field when `evidence == []` post-reconciliation; applied to every scalar field, `total_amount.confidence`, and `document_type.confidence`; NOT applied when evidence is non-empty; the cap value comes from `config.reconciliation.ungrounded_confidence_cap`.
- [X] T041 [P] [US2] Integration test `tests/integration/extract/test_us2_evidence_grounding.py::test_ac1_every_evidence_resolves` — US2 AC#1: walk every `evidence` array in the artifact, assert each string matches `^p\d+_[bl]\d+$` and exists in the input packet's `evidence_index`.
- [X] T042 [P] [US2] Integration test `tests/integration/extract/test_us2_evidence_grounding.py::test_ac2_bogus_ids_filtered_and_warned` — US2 AC#2: bogus IDs are removed; `warnings` names the field and dropped ID; surviving evidence determines grounding.
- [X] T043 [P] [US2] Integration test `tests/integration/extract/test_us2_evidence_grounding.py::test_ac3_empty_evidence_downgrades_confidence` — US2 AC#3: scalar fields with empty-after-reconciliation evidence retain the model value but have `confidence <= UNGROUNDED_CONFIDENCE_CAP`.
- [X] T044 [P] [US2] Integration test `tests/integration/extract/test_us2_evidence_grounding.py::test_ac4_empty_company_name_evidence_forces_override` — US2 AC#4: when `company_name.evidence == []`, `company_name.present == false` AND `company_name.inferred == true`, regardless of model's `present` claim.
- [X] T045 [P] [US2] Integration test `tests/integration/extract/test_us2_evidence_grounding.py::test_ac5_reconciliation_discoverable` — US2 AC#5: every reconciliation adjustment is visible in either `warnings` or `extraction_notes`.

### Implementation for User Story 2

(Reconciliation is already implemented in T032. Phase 4 closes any gaps the tests surface.)

- [X] T046 [US2] Close any gaps T039–T045 surface in `src/ledgerlinc_ocr/extract/reconcile.py`. Common candidates: per-field warning message format, deduplication stability, cap applied pre-write vs post-write. No scope beyond making the US2 tests green.

**Checkpoint**: Phase 4 green — evidence grounding and ungrounded-confidence cap behave per spec. SC-003 demonstrable on the US2 fixtures.

---

## Phase 5: User Story 3 - Missing-Name Invariants Are Enforced At The Extractor Level (Priority: P2)

**Goal**: On documents where no explicit company name appears, the extractor emits `company_name.present == false` AND `company_name.inferred == true`, deterministically, regardless of model claim. The exclusive-or invariant from FR-013 holds for every document.

**Independent Test**: Run the extractor against a stub-voter fixture whose preprocess packet has no block/line supporting an explicit company name and whose model response emits a best-guess `company_name.value` with `present=true` claim. Verify the extractor overrides to `present=false, inferred=true`, writes an `extraction_notes` entry explaining the override, and keeps the invariant pair (never both true, never both false). Then run against a fixture where the name IS explicit; verify `present=true, inferred=false, evidence` non-empty.

### Tests for User Story 3

- [X] T047 [P] [US3] Create fixture `tests/fixtures/extract/us3_missing_name/` with `preprocess_output.json` containing blocks/lines that plausibly include everything else (addresses, totals) but NO block whose text supports an explicit company name; pair with `voter_response_guess_with_present_true.json` that claims `company_name.present=true, value="Acme Co", evidence=[]`.
- [X] T048 [P] [US3] Create fixture `tests/fixtures/extract/us3_grounded_name/` — twin of US1 happy path but designed so `company_name.evidence` must be non-empty in any reasonable voter response.
- [X] T049 [P] [US3] Unit test `tests/unit/extract/test_reconcile_provenance.py`: exercise reconcile.py step 5 — with `evidence != []` → `present=true, inferred=false`; with `evidence == []` → `present=false, inferred=true` regardless of what the parsed response claims; assert the override adds an `extraction_notes` entry; assert the XOR post-condition.
- [X] T050 [P] [US3] Integration test `tests/integration/extract/test_us3_missing_name.py::test_ac1_grounded_name_positive_path` — US3 AC#1 using the US3 grounded fixture.
- [X] T051 [P] [US3] Integration test `tests/integration/extract/test_us3_missing_name.py::test_ac2_guess_present_false_inferred_true` — US3 AC#2 using the US3 missing-name fixture.
- [X] T052 [P] [US3] Integration test `tests/integration/extract/test_us3_missing_name.py::test_ac3_override_recorded_in_notes` — US3 AC#3: override entry appears in `extraction_notes` or `warnings`.
- [X] T053 [P] [US3] Integration test `tests/integration/extract/test_us3_missing_name.py::test_ac4_downstream_can_read_provenance` — US3 AC#4: artifact alone carries sufficient provenance (both invariant fields present and schema-valid; reading routing-relevant info from this artifact does NOT require re-reading preprocess_output.json). Assert by parsing ONLY the artifact and deriving a would-be `manual_review_required` boolean.
- [X] T054 [P] [US3] Integration test `tests/integration/extract/test_us3_missing_name.py::test_ac5_invariant_pair_across_fixtures` — US3 AC#5: run both US3 fixtures, assert `present XOR inferred == True` for each; assert the (true, true) and (false, false) combinations never appear.

### Implementation for User Story 3

(Override logic is already implemented in T032. Phase 5 closes any gaps US3 tests surface.)

- [X] T055 [US3] Close any gaps T049–T054 surface in `src/ledgerlinc_ocr/extract/reconcile.py`. No scope beyond making the US3 tests green.

**Checkpoint**: Phase 5 green — missing-name invariants enforced at the extractor level per constitution principle IV. SC-002 demonstrable on the US3 fixtures; corpus-level 100% gate is validated later via quickstart.md against the 5 real missing-name documents.

---

## Phase 6: User Story 4 - The Voter Framework Is Pluggable And Architecture-Ready For The Three-Vote Ensemble (Priority: P2)

**Goal**: Swapping the stage 1 voter slot for another voter (or a stub) requires only voter configuration + prompt/adapter module — not changes to input/output contract, reconciliation, or folder layout. Each voter's artifact differs only in `model_runtime` / `vote_metadata.voter_id` / model-dependent values.

**Independent Test**: Run the extractor twice against the same per-document folder with two different voter configs — the stub voter with fixture A and the stub voter with fixture B (simulating Gemma vs. Qwen). Verify each invocation writes a schema-valid artifact; `model_runtime` / `vote_metadata.voter_id` differ; `document_id`, evidence-packet identifiers, and overall artifact shape are identical.

### Tests for User Story 4

- [X] T056 [P] [US4] Create a second stub-voter config + fixture simulating a "Qwen-edge" voter: `tests/fixtures/extract/us4_qwen_sim/voter_config.yaml` (distinct `voter_id`, `model_runtime.model_name`, `model_runtime.model_version`, `model_runtime.runtime`) and `voter_response_clean.json` (may reuse US1's canned response content; only the config identifies it as a different voter).
- [X] T057 [P] [US4] Integration test `tests/integration/extract/test_us4_pluggable_voter.py::test_ac1_stage_1_gemma_runtime_fields` — US4 AC#1: using `voters/configs/gemma-edge.yaml`, verify all four `model_runtime` fields (`provider`, `model_name`, `model_version`, `runtime`) are non-empty and match config. (Uses `StubVoter` backend for this test by substituting provider="stub" in a test-local copy of the config; the point is the config-to-artifact plumbing, not the Ollama call.)
- [X] T058 [P] [US4] Integration test `tests/integration/extract/test_us4_pluggable_voter.py::test_ac2_vote_metadata_pinned_values` — US4 AC#2: `voter_id` non-empty, `voter_role == "primary_extractor"`, `consensus_mode == "single_voter_baseline"`.
- [X] T059 [P] [US4] Integration test `tests/integration/extract/test_us4_pluggable_voter.py::test_ac3_swap_voter_no_code_change` — US4 AC#3: run against the same folder with config A (gemma-sim stub) and config B (qwen-sim stub); assert artifact shape (top-level keys, sub-field keys, types) is identical; assert `model_runtime` and `vote_metadata.voter_id` differ; assert no code under `src/ledgerlinc_ocr/extract/` was touched between the two runs (by invoking the same installed module).
- [X] T060 [P] [US4] Integration test `tests/integration/extract/test_us4_pluggable_voter.py::test_ac4_artifact_filename_stable` — US4 AC#4: both runs write to `<folder>/edge_extraction_output.json` (second run overwrites first per spec Edge Cases); no `votes/` subdirectory is created; the extractor does not yet implement multi-voter orchestration.
- [X] T061 [P] [US4] Integration test `tests/integration/extract/test_us4_pluggable_voter.py::test_ac5_voter_role_enum_coverage` — US4 AC#5: load and validate a config with `voter_role: "secondary_extractor"` — verify `VoterConfig` pydantic accepts the enum value BUT the extractor runtime refuses it in stage 1 (because `consensus_mode` can only be `single_voter_baseline` under the v1.0.0 schema, and the stage-1 semantics require `primary_extractor`). The accepted-at-schema-level check plus the runtime rejection keeps the enum honored while keeping stage 1 single-voter-only.

### Implementation for User Story 4

(Pluggable shape is already implemented via T013 Protocol + T012 config + T031/T014 adapters. Phase 6 adds only the fixture, the alternate config, and any runtime-check for T061.)

- [X] T062 [US4] Add a runtime check in `src/ledgerlinc_ocr/extract/pipeline.py` that rejects `voter_role != "primary_extractor"` at stage 1 with a clear error, even though the pydantic enum accepts the other values. Raise `VoterConfigInvalid` with a message naming the reserved-for-future-use status. This is what US4 AC#5 verifies.

**Checkpoint**: Phase 6 green — voter-framework pluggability demonstrated. SC-004 and SC-008 demonstrable.

---

## Phase 7: User Story 5 - Graceful Degradation On Model, Network, And Parsing Failures (Priority: P3)

**Goal**: Every hard failure (Ollama unreachable, model unavailable, input contract drift, unrepairable JSON, voter config invalid) exits non-zero with a clear stderr message and writes no artifact. Every soft failure (JSON repair, defaulted sub-field, dropped evidence, partial input packet) produces a schema-valid artifact with `status` in `{partial, failure}` and at least one `warnings` entry.

**Independent Test**: Quickstart.md §"Hard-failure smoke tests" lists the exact commands. Each must produce its pinned exit code and either an artifact with the expected `status` or no artifact, per the exit-code table in R-011.

### Tests for User Story 5

- [X] T063 [P] [US5] Create fixtures for the failure matrix in `tests/fixtures/extract/us5_failures/`:
  - `drift_folder/preprocess_output.json` — valid schema but `contract_set_version = "1.0.1"` (should trigger `InputContractDrift`, exit `2`)
  - `schema_invalid_folder/preprocess_output.json` — missing required key (exit `2`)
  - `malformed_json/voter_response.txt` — JSON wrapped in ```json fences with prose prefix (repair path)
  - `missing_subfield/voter_response.json` — valid JSON missing `vendor_candidate.tax_ids.vat_id` (default path)
  - `unrepairable/voter_response.txt` — pure prose, no JSON (exit `5`)
  - `empty_response/voter_response.txt` — empty string (exit `5`)
  - `blank_packet/preprocess_output.json` — schema-valid packet with zero blocks + zero lines on every page (should produce `status="failure"` artifact with `exit=0`)
  - Pair each with a test-local `voter_config.yaml` pointing the stub voter at the right fixture body.
- [X] T064 [P] [US5] Unit test `tests/unit/extract/test_parse.py`: exercise parse.py — clean JSON parses with empty `repair_trail`; markdown-fenced JSON repairs with one entry; prose-prefixed JSON repairs; BOM-prefixed JSON repairs; pure prose raises `UnrepairableResponse`; empty string raises `UnrepairableResponse`.
- [X] T065 [P] [US5] Unit test `tests/unit/extract/test_reconcile_defaults.py`: exercise reconcile.py step 2 — when a required sub-field is absent from the parsed dict, it's defaulted to the null shape, a warning is emitted naming the field, and the "soft failure" bit is set (feeds status derivation).
- [X] T066 [P] [US5] Unit test `tests/unit/extract/test_reconcile_status.py`: exercise reconcile.py step 7 across the R-008 truth table — clean inputs → `success`; any soft-bit set with some grounded evidence → `partial`; all-null + all-empty-evidence → `failure`.
- [X] T067 [P] [US5] Integration test `tests/integration/extract/test_us5_hard_failures.py::test_ac1_ollama_unreachable` — US5 AC#1 (Ollama path): set `OLLAMA_BASE_URL` to an unreachable port (e.g., `http://127.0.0.1:1`), use a non-stub voter config, confirm exit `3`, no artifact, stderr names "unreachable".
- [X] T068 [P] [US5] Integration test `tests/integration/extract/test_us5_hard_failures.py::test_ac1_contract_drift` — US5 AC#1 (input path): point `--folder` at the drift_folder fixture, confirm exit `2`, no artifact, stderr names "contract_set_version".
- [X] T069 [P] [US5] Integration test `tests/integration/extract/test_us5_hard_failures.py::test_ac1_schema_invalid_input` — US5 AC#1 (input path): point `--folder` at the schema_invalid_folder fixture, confirm exit `2`, no artifact.
- [X] T070 [P] [US5] Integration test `tests/integration/extract/test_us5_hard_failures.py::test_config_invalid` — broken YAML at `--voter-config` path → exit `6`, no artifact.
- [X] T071 [P] [US5] Integration test `tests/integration/extract/test_us5_hard_failures.py::test_ac4_unrepairable_response` — US5 AC#4: unrepairable fixture → exit `5`, no artifact. (The artifact-with-failure-status path from R-012 is exercised separately by the blank-packet test below, where reconciliation *does* run.)
- [X] T072 [P] [US5] Integration test `tests/integration/extract/test_us5_soft_failures.py::test_ac2_json_repair_warns` — US5 AC#2: malformed_json fixture → exit `0`, `status="partial"`, `warnings` includes the repair description.
- [X] T073 [P] [US5] Integration test `tests/integration/extract/test_us5_soft_failures.py::test_ac3_missing_subfield_defaulted` — US5 AC#3: missing_subfield fixture → exit `0`, `status="partial"`, defaulted sub-field present with the null-shape, `warnings` names the defaulted field.
- [X] T074 [P] [US5] Integration test `tests/integration/extract/test_us5_soft_failures.py::test_ac4_blank_packet_failure_status` — Edge Case + US5 AC#4 artifact path: blank_packet fixture → exit `0`, `status="failure"`, every `value` null, every `evidence` empty, `warnings` explains.
- [X] T075 [P] [US5] Integration test `tests/integration/extract/test_us5_soft_failures.py::test_ac5_warnings_are_informative` — US5 AC#5: every warning from the above tests is a non-empty string and names the field/page/stage.
- [X] T076 [P] [US5] Integration test `tests/integration/extract/test_us5_soft_failures.py::test_ac6_schema_valid_regardless_of_status` — US5 AC#6: validate every soft-failure artifact from T072–T074 against the frozen schema; all pass.
- [X] T077 [P] [US5] Integration test `tests/integration/extract/test_host_ollama_smoke.py::test_gemma_edge_smoke` — real-Ollama smoke test against `gemma-edge.yaml`. Auto-skip when `OLLAMA_BASE_URL` unreachable (use `pytest.importorskip` + pre-flight GET to `/api/tags`). Asserts a schema-valid artifact is written and `status in {success, partial}`; does NOT assert specific values.
- [X] T089 [P] [US5] Integration test `tests/integration/extract/test_us5_hard_failures.py::test_ac1_model_unavailable` — closes the analysis C1 gap. Use `pytest-httpserver` or a monkeypatched `httpx.Client` transport that returns the Ollama `model '<tag>' not found` error payload; point the extractor at that mock endpoint via `OLLAMA_BASE_URL`. Assert exit code `4` (`EXIT_MODEL_UNAVAILABLE`), no `edge_extraction_output.json` written, stderr contains the configured model tag and the word "not available" / "not found".
- [X] T090 [P] [US5] Fixture + integration test for partial-input propagation (analysis C3, FR-023). Create `tests/fixtures/extract/us5_partial_input/preprocess_output.json` that is schema-valid with populated blocks BUT has `ingestion_sources.falcon_perception.status == "failure"` and a non-empty top-level `warnings` array. Pair with a clean stub voter response. Add `tests/integration/extract/test_us5_soft_failures.py::test_partial_input_propagation` — assert exit code `0`, `status in {"success", "partial"}`, and that the input-side partiality is visible in the output's `extraction_notes` or `warnings` (at least one entry references `falcon_perception` or the input warning).

### Implementation for User Story 5

(Error handling is wired in T031 + T034 + T035. Phase 7 closes any gaps the failure tests surface.)

- [X] T078 [US5] Close any gaps T067–T076, T089, T090 surface in `src/ledgerlinc_ocr/extract/pipeline.py`, `voters/ollama.py`, `reconcile.py`, or `cli.py`. Common candidates: distinguishing `OllamaModelUnavailable` from generic 4xx, making the stderr message specific enough for each exit code, ensuring the blank-packet path reaches reconciliation rather than short-circuiting earlier, and plumbing input-side `preprocess_output.warnings` / `ingestion_sources[*].status == "failure"` into `extraction_notes`.

**Checkpoint**: Phase 7 green — full hard/soft failure matrix behaves per spec. SC-005 and SC-006 demonstrable on the US5 fixtures.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final cross-cutting additions, documentation cross-links, and release-gate validation against the real 20-document corpus.

- [X] T079 [P] Document cross-link in `docs/stage1-vendor-identity/ollama-runtime.md`: add a subsection "Extractor timeout + no-retry convention" linking to `specs/005-single-voter-extraction/research.md §R-002` (timeout) and §R-001 (httpx, no retries). Do not change other runtime guidance.
- [X] T080 [P] Update `CLAUDE.md` "Key References" block to add `specs/005-single-voter-extraction/spec.md`, `…/plan.md`, `…/research.md`, `…/contracts/cli-contract.md`, `…/contracts/voter-config.md` pointers alongside the existing 003 references.
- [X] T081 [P] Add a `tests/unit/extract/test_artifact.py` covering the atomic-write sequence: temp file exists during write, disappears after `os.replace`; an intentionally-invalid dict fails validation before any file is written (partial-file invisible).
- [X] T082 [P] Add a `tests/integration/extract/test_corpus_walk.py::test_all_20_docs_schema_valid` — runs the stub voter against every folder under `tests/stage1_vendor_identity/inv_*` that carries a `preprocess_output.json` from the 003 slice, using a deterministic canned fixture response. Asserts 100% schema validity (SC-001 on the stub path; the real Gemma path remains a developer smoke test, not a CI gate).
- [X] T083 [P] Add `tests/integration/extract/test_corpus_walk.py::test_missing_name_invariant_100pct` — the same stub walk but over the 5 `inv_*_missing_name/` folders, with a fixture that claims `present=true, evidence=[]` — asserts every output has `present=false, inferred=true` (SC-002 demonstrated on the stub path).
- [X] T084 [P] Add `tests/integration/extract/test_corpus_walk.py::test_evidence_resolves_100pct` — every evidence ID in every output from the stub walk resolves against the corresponding preprocess packet (SC-003).
- [X] T085 [P] Add a performance guardrail `tests/unit/extract/test_reconcile_perf.py`: reconcile.py on a synthetic 10-page packet + reasonable model response completes in < 500 ms on the `pipeline-dev` devcontainer (SC-007 is <2 s excluding model; this unit-level guardrail is a much tighter inner check).
- [X] T092 [P] Integration perf guardrail `tests/integration/extract/test_pipeline_perf.py::test_full_pipeline_minus_model_under_2s` — closes the analysis C4 gap on SC-007. Run the extractor end-to-end against the US1 happy fixture with the stub voter (zero network, canned response), measure wall-clock for packet load → prompt render → parse → reconcile → artifact write, assert < 2 s on the `pipeline-dev` devcontainer (CPU-only, Python 3.12). The stub voter's own read time is inside the measured window (no subtraction) because it is the stand-in for the "non-model" overhead.
- [X] T093 [P] Module-boundary test `tests/unit/extract/test_no_downstream_imports.py` — closes the analysis C5 gap on FR-020/FR-021. Walk `src/ledgerlinc_ocr/extract/**/*.py` (excluding `__pycache__`), parse each file with `ast.parse`, and assert no `Import` or `ImportFrom` node references a package or module name in the banned set: `routing`, `consensus`, `final_payload`, `evaluation`, and any cloud-provider SDK names (`boto3`, `google.cloud`, `azure.ai`). Also assert no import of the `requests` library (httpx only — R-001). Keeps FR-020/FR-021 structurally enforced.
- [X] T086 Run `python -m ledgerlinc_ocr.validator validate corpus tests/stage1_vendor_identity/` after Phase 8 and resolve any drift — the validator should now report `edge_extraction_output.json` present (stub-generated) alongside `preprocess_output.json` for every folder, with all artifacts schema-valid.
- [X] T087 Walk the `checklists/contract.md`, `checklists/determinism.md`, and `checklists/failure-handling.md` items; mark each checkbox `[x]` where the codebase now satisfies the requirement-quality question, or open a follow-up issue for any `[Gap]`/`[Ambiguity]` items that still stand.
- [X] T088 Update `CLAUDE.md` "Recent Changes" block with a one-line note that 005 landed and points at `specs/005-single-voter-extraction/quickstart.md`.

---

## Dependencies & Execution Order

> **Task-ID convention**: Task IDs reflect creation order, not strict in-phase execution order. IDs T089–T093 are post-`/speckit.analyze` gap-close additions appended at the end of the list and folded back into the earlier phases (T091 into Phase 3, T089/T090 into Phase 7, T092/T093 into Phase 8). Phases and the `[P]` markers are authoritative for execution sequencing — do not try to execute by numeric ID order.

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Phase 1 completion — BLOCKS all user stories.
- **User Story 1 (Phase 3)**: Depends on Phase 2. MVP. Once green, the pipeline is real.
- **User Stories 2–5 (Phases 4–7)**: Depend on Phase 3 (they consume the MVP pipeline). Within each story, tests for that story can be written in parallel with implementation gap-closes (T046, T055, T062, T078).
- **Polish (Phase 8)**: Depends on Phases 3–7 green. T086 in particular requires the full corpus-walk tests to have run at least once.

### User Story Dependencies

- **US1 (P1)**: Blocks on Phase 2. Independent of US2–US5 for correctness but is the substrate they test against.
- **US2 (P1)**: Blocks on US1 reconcile.py + pipeline. Runs in parallel with US3/US4/US5 after that.
- **US3 (P2)**: Blocks on US1 reconcile.py. Runs in parallel with US2/US4/US5.
- **US4 (P2)**: Blocks on US1 pipeline + voter seam. Runs in parallel with US2/US3/US5.
- **US5 (P3)**: Blocks on US1 full pipeline (errors + exit codes are wired in US1 tasks T031/T035). Runs in parallel with US2/US3/US4.

### Within Each Phase

- Tests in each phase are written alongside (or just before) their implementation closure task. Each phase carries a single "close any gaps" implementation task (T046, T055, T062, T078); most of the code for each story already exists after US1.
- Fixtures (T021–T022, T038, T047–T048, T056, T063) have no dependencies beyond the preprocessing schema and can be authored in parallel with Phase 2 if staffed.

### Parallel Opportunities

- **Phase 1**: T004–T006 can run together; T003 and T007 depend on T001/T002.
- **Phase 2**: T009–T016 are all `[P]` (different files, no inter-deps). T017–T020 unit tests are all `[P]` and depend on the matching implementation file existing (T011/T012/T010/T014 respectively).
- **Phase 3**: T021–T028 (fixtures + integration tests) are all `[P]` and independent of each other. T029–T031 implementation tasks are `[P]` (different files). T032 (reconcile) depends on T009 (errors). T033–T036 are sequential on T032. T091 (determinism unit test) runs `[P]` alongside T037 once T032 lands.
- **Phases 4–7**: All fixture + unit + integration tests marked `[P]` can run in parallel within a phase; the single gap-close implementation task per phase runs last. T089 / T090 (post-analysis additions in Phase 7) are `[P]` and fold into T078's gap-close scope.
- **Phase 8**: T079–T085, T092, T093 are all `[P]` (different files). T086–T088 run sequentially at the end.

---

## Parallel Example: User Story 1

```bash
# Fixtures + integration tests, all parallelizable:
Task: "Create happy-path fixture folder tests/fixtures/extract/us1_happy/"
Task: "Integration test test_us1_schema_valid.py"
Task: "Integration test test_us1_ids_match.py"
Task: "Integration test test_us1_vendor_block.py"
Task: "Integration test test_us1_header_block.py"
Task: "Integration test test_us1_status_consistency.py"
Task: "Integration test test_us1_no_sidecar_writes.py"

# Implementation modules (different files, no inter-deps):
Task: "Implement prompt.py"
Task: "Implement parse.py"
Task: "Implement voters/ollama.py"

# Then sequentially:
Task: "Implement reconcile.py"     # depends on errors.py (Phase 2)
Task: "Implement artifact.py"      # depends on reconcile.py output shape
Task: "Implement pipeline.py"      # depends on prompt, parse, reconcile, artifact
Task: "Implement cli.py / __main__.py"  # depends on pipeline.py
Task: "Author prompt template gemma_edge_extractor.md"   # can be parallel with cli.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup — package skeleton + deps.
2. Complete Phase 2: Foundational — errors, exit codes, version, config loader, voter seam, stub voter.
3. Complete Phase 3: User Story 1 — stub-voter happy-path end-to-end pipeline + 6 integration tests.
4. **STOP and VALIDATE**: Run the quickstart's US1 smoke path against the stub voter. Run `pytest tests/unit/extract tests/integration/extract -k us1`.
5. Demo: one schema-valid `edge_extraction_output.json` produced from one per-document folder.

### Incremental Delivery

1. MVP (above) → demo.
2. Layer US2 (evidence grounding) → pytest -k us2 → evidence-first demo.
3. Layer US3 (missing-name) → pytest -k us3 → provenance-invariant demo.
4. Layer US4 (pluggability) → pytest -k us4 → stub-vs-Gemma-sim shape diff demo.
5. Layer US5 (failure modes) → pytest -k us5 → exit-code matrix demo.
6. Polish (Phase 8) → full-suite + corpus walk + host-Ollama smoke.

### Parallel Team Strategy

With multiple developers post-Phase 3:

1. Team completes Phase 1–3 together (sequential, shared substrate).
2. Once US1 MVP is green:
   - Developer A: US2 fixtures + tests + any reconcile gap-close.
   - Developer B: US3 fixtures + tests + any reconcile gap-close.
   - Developer C: US4 alternate voter configs + pluggability tests.
   - Developer D: US5 failure fixtures + hard/soft failure tests.
3. Converge on Polish (Phase 8) after all US phases green.

---

## Notes

- `[P]` tasks = different files, no dependencies on incomplete tasks.
- `[Story]` label maps each task to the user story it serves (US1–US5); Setup / Foundational / Polish tasks carry no story label.
- Tests are REQUIRED for this slice (Constitution V + per-story Independent Test sections). Write tests first where possible; at minimum ensure they FAIL before the matching implementation task lands.
- Every user story should remain independently runnable after its phase closes — US2–US5 do not break US1; US5 failure paths do not break US1–US4 happy paths.
- Commit after each task or logical group. The existing extension-hooks configuration will prompt for commits between phases.
- Stop at any checkpoint to validate the story independently.
- Avoid cross-story dependencies inside `src/ledgerlinc_ocr/extract/` — the MVP in US1 is the shared substrate; later USs are fixtures + tests + small gap-closes only.
