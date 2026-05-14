---
description: "Task list for 009-final-payload implementation"
---

# Tasks: Final Structured Payload Assembly (Stage 1 Vendor-Identity)

**Input**: Design documents from `/specs/009-final-payload/`
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/module-api.md`, `contracts/cli-contract.md`, `quickstart.md`

**Tests**: Included. The spec's six user stories each define an "Independent Test" section, and `research.md` Decision 10 pre-identifies the seven fixture pairs each test consumes. Per-story tests are mandatory for this feature.

**Organization**: Tasks are grouped by user story. US1 and US2 are both P1 (MVP); US3/US4 are P2; US5/US6 are P3. Every story is independently testable once Phase 2 completes.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Maps task to a user story (US1–US6); omitted for Setup/Foundational/Polish
- Paths are repo-relative; all work lives under `src/dartwing_ocr/assembler/` and `tests/` per `plan.md` §Project Structure

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffold the new submodule and wire it into the existing package.

- [X] T001 Create empty submodule skeleton at `src/dartwing_ocr/assembler/__init__.py` and `src/dartwing_ocr/assembler/__main__.py` (module-loadable, no real logic yet)
- [X] T002 [P] Create fixture folder skeleton `tests/fixtures/assembler/` with a `README.md` describing the seven fixture pairs from `research.md` §Decision 10
- [X] T003 [P] Create `tests/pipeline_tests/__init__.py` marker if absent; confirm `tests/contract_tests/__init__.py` and `tests/unit/__init__.py` already exist (no rewrite)
- [X] T004 Register `dartwing-assemble` console script in `pyproject.toml` under `[project.scripts]` pointing at `dartwing_ocr.assembler.cli:main`

**Checkpoint**: Module is importable; console script is declared; fixture folder exists.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Error taxonomy, version builder, deterministic write, `Invocation` dataclass, and the golden fixture pair — every user story depends on these.

**⚠️ CRITICAL**: No user story phase may begin until all Phase 2 tasks complete.

- [X] T005 Implement exit codes and exception hierarchy in `src/dartwing_ocr/assembler/errors.py` per `contracts/module-api.md` §Exception hierarchy (`EXIT_OK=0`, `EXIT_UNEXPECTED=1`, `EXIT_INPUT_REJECTED=2`, `EXIT_INTERNAL_ERROR=3`; `AssemblerError` base; `InputRejectedError` and seven concrete subclasses; `OutputSchemaInvalidError`; every subclass carries `exit_code` and `kind` class attributes)
- [X] T006 [P] Implement `SLICE_PREFIX = "009-final-payload"`, `SEMVER = "0.1.0"`, and `build_pipeline_version(semver: str = SEMVER) -> str` returning `"009-final-payload@<semver>"` in `src/dartwing_ocr/assembler/version.py` per `research.md` Decision 3
- [X] T007 [P] Implement deterministic JSON writer `write_final_payload(path: Path, payload: dict) -> None` in `src/dartwing_ocr/assembler/write.py` per `research.md` Decision 1 (schema-order key insertion via `FINAL_KEY_ORDER` constant, `indent=2`, `ensure_ascii=False`, trailing newline, UTF-8)
- [X] T008 Define `@dataclass(frozen=True) class Invocation` with fields `document_folder: Path`, `pipeline_version: str | None = None`, `now_utc: Callable[[], datetime] | None = None` in `src/dartwing_ocr/assembler/pipeline.py` per `contracts/module-api.md` §Invocation (run() function body is a TODO stub at this point)
- [X] T009 [P] Create golden fixture pair `tests/fixtures/assembler/happy_grounded/edge_extraction_output.json` and `routing_decision.json` per `research.md` §Decision 10 table row 1 (grounded company name with present=true/inferred=false, full address, one EIN, email; routing decision=edge_accept, manual_review_required=false, review_reason=null; both contract_set_version=1.0.0; document_id="inv_happy_grounded_001")
- [X] T010 [P] Add unit test `tests/unit/test_assembler_version.py` asserting `build_pipeline_version()` returns `"009-final-payload@0.1.0"` and a custom semver override returns `"009-final-payload@0.2.0"`
- [X] T011 [P] Add unit test `tests/unit/test_assembler_write.py` asserting `write_final_payload` produces byte-identical output for the same dict across two calls (including key order) and writes a trailing newline

**Checkpoint**: Error taxonomy, version builder, JSON writer, `Invocation`, and the happy fixture are all in place. User stories may now proceed in priority order, or in parallel by developer assignment.

---

## Phase 3: User Story 1 — Schema-Valid Payload Emission (Priority: P1) 🎯 MVP

**Goal**: Assembler reads one valid folder, writes one schema-valid `final_structured_payload.json` with every required top-level key populated correctly from the two inputs.

**Independent Test**: Run the assembler against `tests/fixtures/assembler/happy_grounded/`; confirm `final_structured_payload.json` is written next to the inputs, validates against `contracts/stage1_vendor_identity/v1.0.0/final_structured_payload.schema.json`, reports `contract_set_version == "1.0.0"`, carries the same `document_id` as both inputs, and has every required top-level key non-empty. Two invocations produce outputs byte-identical except for `processed_at`.

### Tests for User Story 1

- [X] T012 [P] [US1] Add `tests/contract_tests/test_final_payload_assembler_tie_in.py` — given the assembler's output on the `happy_grounded` fixture, validate it against `final_structured_payload.schema.json` via the existing `dartwing_ocr.validator.artifact` loader; assert exit 0 / schema-valid
- [X] T013 [US1] Add `tests/pipeline_tests/test_assembler_us1_happy_path.py` covering acceptance scenarios US1 AS-1..AS-6: all required top-level keys present, `contract_set_version == "1.0.0"`, `processed_at` ISO-8601 UTC, `pipeline_version == "009-final-payload@0.1.0"` (not copied from inputs), `document_type == "invoice"`, `document_id` equals both inputs, and two runs differ only by `processed_at`

### Implementation for User Story 1

- [X] T014 [US1] Implement `src/dartwing_ocr/assembler/trace.py` producing the fixed `{source_file, preprocess_output_file, edge_extraction_output_file, routing_decision_file}` dict per `data-model.md` §TraceBlock (placeholder: real US5 tests tighten this)
- [X] T015 [US1] Flesh out `run(invocation: Invocation) -> Path` in `src/dartwing_ocr/assembler/pipeline.py` with the full assembly sequence: load inputs via `dartwing_ocr.validator.artifact.load_and_validate` (Decision 4), build the payload dict in `FINAL_KEY_ORDER`, call `write_final_payload`, return the absolute path. Minimal body: uses placeholder flatten/quality/review helpers that pass-through or return schema-satisfying defaults so the happy path validates. Subsequent stories tighten each slot.
- [X] T016 [US1] Ensure `contract_set_version = "1.0.0"` and `document_type = "invoice"` are emitted as literal constants, and `processed_at` uses the injected clock per `research.md` Decision 2

**Checkpoint**: US1 is green against `happy_grounded`. The rest of the stories tighten the per-slot behaviors; US1's schema-validity guarantee holds throughout.

---

## Phase 4: User Story 2 — Flatten Evidence, Preserve Provenance & Confidence (Priority: P1)

**Goal**: Evidence arrays are stripped at every nesting depth; `value` / `confidence` / `company_name.present` / `company_name.inferred` are copied exactly; `invoice_header_fields` are excluded.

**Independent Test**: Run against a fixture whose extractor has populated `{value, confidence, evidence}` blocks plus null blocks; verify every present field emits `{value, confidence}` only (no evidence), `company_name` emits `{value, present, inferred, confidence}`, null fields survive as `{value: null, confidence: <number>}`, and `invoice_header_fields` is absent from output. Re-validate against the frozen schema.

### Tests for User Story 2

- [X] T017 [P] [US2] Add `tests/pipeline_tests/test_assembler_us2_flatten.py` covering US2 AS-1..AS-6: populated fields emit `{value, confidence}`; null fields survive; `company_name` four keys copied exactly; `invoice_header_fields` never appears; zero `evidence` keys anywhere at any depth (recursive walk); `present`/`inferred` not recomputed
- [X] T018 [P] [US2] Add parameterized unit test `tests/unit/test_assembler_flatten_table.py` iterating `FIELDS_TO_FLATTEN` and asserting each entry produces the documented output shape for a synthetic input

### Implementation for User Story 2

- [X] T019 [US2] Implement `FIELDS_TO_FLATTEN` table and `flatten_vendor_candidate(extractor: dict) -> dict` in `src/dartwing_ocr/assembler/flatten.py` per `data-model.md` §`FIELDS_TO_FLATTEN` Table and `research.md` Decision 7 (kind `value_confidence` → `{value, confidence}`; kind `company_name` → `{value, present, inferred, confidence}`; never emit `evidence`)
- [X] T020 [US2] Wire `flatten_vendor_candidate` into `pipeline.run()` replacing the US1 placeholder; confirm `invoice_header_fields`, `model_runtime`, `vote_metadata`, `extraction_notes`, `warnings`, `status` from the extractor are NOT propagated

**Checkpoint**: US2 is green. Output is flattened correctly; US1 still passes.

---

## Phase 5: User Story 3 — Review Status Propagates Verbatim (Priority: P2)

**Goal**: `review_status.manual_review_required` and `review_status.review_reason` are byte-identical to routing's, including the canonical string `"company_name_inferred"`. FR-016 routing-internal contradictions are NOT soft-surfaced (those belong to US6).

**Independent Test**: Run against three fixtures (accept, review-required with `company_name_inferred`, review-required with `secondary_identifiers_insufficient`). Verify `final_structured_payload.json:review_status` is byte-identical to `routing_decision.json:review_status` in each case.

### Tests for User Story 3

- [X] T021 [P] [US3] Create fixture pair `tests/fixtures/assembler/missing_name_inferred/edge_extraction_output.json` + `routing_decision.json` per `research.md` §Decision 10 row 2 (company_name present=false, inferred=true; routing review_reason="company_name_inferred")
- [X] T022 [P] [US3] Create fixture pair `tests/fixtures/assembler/empty_extraction_spam_gate/edge_extraction_output.json` + `routing_decision.json` per `research.md` §Decision 10 row 3 (all-null vendor_candidate; routing review_reason="post_extraction_spam_gate_failed")
- [X] T023 [P] [US3] Add `tests/pipeline_tests/test_assembler_us3_review_status.py` covering US3 AS-1..AS-4: exact-string propagation for `company_name_inferred`; null survival when accept; propagation of arbitrary unknown strings (spec Edge Case §3); accept + null review_reason consistency

### Implementation for User Story 3

- [X] T024 [US3] Implement `copy_review_status_verbatim(routing: dict) -> dict` in `src/dartwing_ocr/assembler/pipeline.py` (or a small helper inline) — a pure dict copy with no normalization, aliasing, or default substitution
- [X] T025 [US3] Wire `copy_review_status_verbatim` into `pipeline.run()` replacing the US1 placeholder `review_status` slot

**Checkpoint**: US3 is green across all three fixtures. US1 and US2 still pass.

---

## Phase 6: User Story 4 — Deterministic Quality Summary (Priority: P2)

**Goal**: `quality_summary` is derived deterministically per the pinned stage-1 policy `0.1.0`. Formula: `round(clip(0.5 * company_name.confidence + 0.5 * mean(secondary_confidences, default 0.0), 0, 1), 4)`. `secondary_identifiers_found` ordering exactly matches the schema enum's declared order.

**Independent Test**: Run against the grounded fixture (US1's `happy_grounded`) and the spam-gate fixture. Verify `overall_vendor_confidence` reproduces exactly across re-runs; `explicit_name_found` is `true` iff `present AND NOT inferred`; `consensus_level == "single_voter_baseline"` always; `secondary_identifiers_found` lists only grounded identifiers in schema enum order; empty-case yields `0.0` / `false` / `"single_voter_baseline"` / `[]`.

### Tests for User Story 4

- [X] T026 [P] [US4] Add unit test `tests/unit/test_assembler_quality_formula.py` parameterized over: all-null input → `overall=0.0`; company only (no secondaries) → `overall=0.5*company_conf`; grounded company + address+email → matches `round(0.5*cn + 0.5*mean(addr_mean, email), 4)`; confirm rounding to 4 decimals
- [X] T027 [P] [US4] Add unit test `tests/unit/test_assembler_secondary_identifiers.py` parameterized over: city+state+postal all grounded → includes `"address"`; only city+state grounded → excludes `"address"`; each tax-ID slot grounded individually → includes that string; output ordering equals `["address", "ein", "state_tax_id", "vat_id", "other_tax_id", "website", "phone", "email"]` regardless of insertion order
- [X] T028 [P] [US4] Add `tests/pipeline_tests/test_assembler_us4_quality_summary.py` covering US4 AS-1..AS-6 against `happy_grounded` and `empty_extraction_spam_gate` fixtures; include determinism check (two runs → identical `quality_summary`)

### Implementation for User Story 4

- [X] T029 [US4] Implement `SECONDARY_ENUM_ORDER` and `derive_secondary_identifiers(extractor: dict) -> list[str]` in `src/dartwing_ocr/assembler/quality.py` per `data-model.md` §Secondary identifiers derivation
- [X] T030 [US4] Implement `compute_overall_vendor_confidence(extractor: dict, secondary_ids: list[str]) -> float` in `src/dartwing_ocr/assembler/quality.py` per `data-model.md` §`overall_vendor_confidence` derivation including `round(_, 4)` (research Decision 6)
- [X] T031 [US4] Implement `build_quality_summary(extractor: dict) -> dict` composing the four fields (`overall_vendor_confidence`, `explicit_name_found = company_name.present and not company_name.inferred`, `consensus_level = "single_voter_baseline"`, `secondary_identifiers_found`) in `src/dartwing_ocr/assembler/quality.py`
- [X] T032 [US4] Wire `build_quality_summary` into `pipeline.run()` replacing the US1 placeholder `quality_summary` slot

**Checkpoint**: US4 is green including the all-null spam-gate case. US1–US3 still pass.

---

## Phase 7: User Story 5 — Trace Block References Upstream Artifacts (Priority: P3)

**Goal**: Four relative paths in `trace` all resolve to existing files in the per-document folder when those files are present; paths are always relative (never absolute).

**Independent Test**: Run against a folder populated with all four upstream filenames; verify each `trace.*_file` equals the documented relative filename and resolves when opened from the folder. Run against a folder missing `source.pdf` (JSON inputs still present); verify the assembler does not fabricate or omit the reference (it still names `"source.pdf"` — spec Edge Case §7).

### Tests for User Story 5

- [X] T033 [P] [US5] Add `tests/pipeline_tests/test_assembler_us5_trace.py` covering US5 AS-1..AS-5: trace values equal the four documented filenames; paths resolve when the files exist; paths are relative (no `/`, no `Path.is_absolute()`); `source_file` still named `"source.pdf"` even if the PDF is absent (spec Edge Case §7)

### Implementation for User Story 5

- [X] T034 [US5] Tighten `src/dartwing_ocr/assembler/trace.py` to produce exactly `{"source_file": "source.pdf", "preprocess_output_file": "preprocess_output.json", "edge_extraction_output_file": "edge_extraction_output.json", "routing_decision_file": "routing_decision.json"}` per `data-model.md` §TraceBlock; remove any US1 placeholder logic

**Checkpoint**: US5 is green. US1–US4 still pass.

---

## Phase 8: User Story 6 — Hard Failures On Invariant Violations (Priority: P3)

**Goal**: The assembler refuses to produce a payload when any of the six cross-input invariants fail. In every case: no output written, exit non-zero, stderr JSON names the failure cause.

**Independent Test**: Run against six failure fixtures (missing extractor, missing routing, document_id mismatch, contract drift, schema-invalid input, routing contradiction). For each: verify no `final_structured_payload.json` exists after the run, exit code is 2 (or 3 for output-schema-invalid), and stderr JSON's `kind` matches the documented taxonomy.

### Tests for User Story 6

- [X] T035 [P] [US6] Create fixture pair `tests/fixtures/assembler/contract_drift/` per `research.md` §Decision 10 row 4 (extractor with `contract_set_version = "1.1.0"`, routing with `"1.0.0"`)
- [X] T036 [P] [US6] Create fixture pair `tests/fixtures/assembler/document_id_mismatch/` per `research.md` §Decision 10 row 5 (`document_id = "inv_005"` vs. `"inv_006"`)
- [X] T037 [P] [US6] Create fixture pair `tests/fixtures/assembler/routing_contradiction/` per `research.md` §Decision 10 row 6 (routing `decision=edge_accept` but `manual_review_required=true, review_reason="company_name_inferred"`) — FR-016 + Clarifications Q1
- [X] T038 [P] [US6] Create fixture `tests/fixtures/assembler/schema_invalid_extractor/` per `research.md` §Decision 10 row 7 (extractor JSON missing `status` required field)
- [X] T039 [P] [US6] Add `tests/pipeline_tests/test_assembler_us6_hard_failures.py` covering all six US6 acceptance scenarios plus FR-016 contradiction; each asserts exit code, stderr JSON `kind` field, absence of `final_structured_payload.json`, and that no input file was mutated
- [X] T040 [P] [US6] Add unit test `tests/unit/test_assembler_routing_consistency.py` parameterized over all four FR-016 contradiction shapes (Decision 9 enumeration) plus the two valid shapes (accept+null, review+named-reason)

### Implementation for User Story 6

- [X] T041 [US6] Implement `check_inputs_exist(folder: Path) -> None`, `check_inputs_readable(folder: Path) -> tuple[dict, dict]`, `check_contract_versions(extractor, routing)`, `check_document_ids_match(extractor, routing)`, and `check_routing_internal_consistency(routing)` in `src/dartwing_ocr/assembler/validation.py` per `data-model.md` §Cross-input invariant table and `research.md` Decision 9
- [X] T042 [US6] Wire the six invariant checks into `pipeline.run()` in the order documented in `data-model.md` §Cross-input invariant table (file existence → JSON parseable → schema-valid → contract version → document_id → routing consistency); raise the corresponding `AssemblerError` subclass on first failure
- [X] T043 [US6] Ensure `pipeline.run()` validates the ASSEMBLED output via `load_and_validate` before writing the file (invariant #7 → `OutputSchemaInvalidError` → exit 3); if validation fails, write nothing

**Checkpoint**: US6 is green across all six hard-fail scenarios + FR-016. US1–US5 still pass.

---

## Phase 9: CLI Integration

**Purpose**: Expose the assembler via `python -m dartwing_ocr.assembler` and the `dartwing-assemble` console script per `contracts/cli-contract.md`.

- [X] T044 Implement `main(argv: list[str] | None = None) -> int` in `src/dartwing_ocr/assembler/cli.py` (argparse with `--document-folder` required and `--pipeline-version` optional; catch each `AssemblerError` subclass and emit the stderr JSON `{"status":"error","kind":"<kind>","message":"<msg>"}`; return the subclass's `exit_code`; catch `Exception` → `EXIT_UNEXPECTED`; mirrors `src/dartwing_ocr/preprocessing/cli.py`)
- [X] T045 Wire `__main__.py` to `cli.main()` so `python -m dartwing_ocr.assembler` works
- [X] T046 [P] Add `tests/pipeline_tests/test_assembler_cli.py` covering: `--help` exits 0; missing `--document-folder` exits 2 with argparse error; successful run on `happy_grounded` exits 0 with no stdout; each failure fixture produces the documented exit code and stderr JSON `kind`
- [X] T047 [P] Export the public surface in `src/dartwing_ocr/assembler/__init__.py`: `from .pipeline import Invocation, run`, `from .version import build_pipeline_version` per `contracts/module-api.md` §Public surface

**Checkpoint**: CLI works end-to-end. `python -m dartwing_ocr.assembler --document-folder tests/fixtures/assembler/happy_grounded/` produces a schema-valid output.

---

## Phase 10: Polish & Cross-Cutting Concerns

- [X] T048 [P] Run the quickstart steps in `specs/009-final-payload/quickstart.md` end-to-end against `tests/fixtures/assembler/happy_grounded/`; capture any discrepancy as a quickstart.md edit (not a code change)
- [X] T049 [P] Measure wall-clock on `happy_grounded` (SC-001 target ≤ 200 ms on a developer workstation); record the observed value in `specs/009-final-payload/quickstart.md` §Performance note
- [X] T050 [P] Walk the four release-gate checklists (`specs/009-final-payload/checklists/contract.md`, `determinism.md`, `failure-handling.md`, `scope.md`) and tick items (`- [x]`) as the corresponding spec sections are verified; resolve any `[Gap]`-marked items by editing `spec.md` or documenting the resolution in `research.md`
- [X] T051 [P] Update the `Key References` section of `CLAUDE.md` to include the new spec paths (`specs/009-final-payload/spec.md`, `plan.md`, `research.md`) so future agent invocations see the authoritative documents
- [X] T052 [P] Add cross-cutting test `tests/pipeline_tests/test_assembler_inputs_read_only.py` covering FR-024: on both the happy path and every US6 failure path, assert that `edge_extraction_output.json`, `routing_decision.json`, `preprocess_output.json`, `expected.json`, `notes.md`, and `source.pdf` (when present) are byte-identical (SHA-256) before and after the run. Confirms inputs are never mutated regardless of success/failure branch.
- [X] T053 [P] Add import-audit test `tests/unit/test_assembler_import_boundary.py` covering FR-023 and FR-025: statically inspect every module under `src/dartwing_ocr/assembler/` and assert zero imports from `dartwing_ocr.preprocessing`, `dartwing_ocr.pipeline` (except shared error helpers if any), any model client library, `requests`, `httpx`, `urllib`, or `socket`. Confirms the assembler is pure, artifact-to-artifact, and cannot call a model or the network.
- [X] T054 Run the full test suite `.venv/bin/pytest tests/contract_tests/ tests/pipeline_tests/ tests/unit/` and confirm all new and existing tests pass (no regressions against 001/002/003)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately.
- **Phase 2 (Foundational)**: Depends on Phase 1. **BLOCKS all user stories.**
- **Phase 3 (US1 P1)**: Depends on Phase 2. MVP checkpoint.
- **Phase 4 (US2 P1)**: Depends on Phase 2 + Phase 3 (US1's `run()` skeleton is extended in US2). Can also run immediately after Phase 2 if US1 tests are treated as regression gates.
- **Phase 5 (US3 P2)**: Depends on Phase 2. Independent of US2/US4.
- **Phase 6 (US4 P2)**: Depends on Phase 2. Independent of US2/US3.
- **Phase 7 (US5 P3)**: Depends on Phase 2. Independent of other user stories.
- **Phase 8 (US6 P3)**: Depends on Phase 2 + Phase 3 (needs `pipeline.run()` to exist so invariant checks can be wired in).
- **Phase 9 (CLI)**: Depends on Phase 2 through Phase 8 (wraps the full `run()` surface).
- **Phase 10 (Polish)**: Depends on all prior phases.

### User Story Dependencies

- US1 (P1) is the schema-validity gate — every subsequent story's output must still schema-validate, and their tests rely on the fixtures/pipeline US1 establishes.
- US2 (P1) tightens US1's flattening placeholder. US1's output already schema-validates, but US2's tests enforce the no-evidence + shape invariants.
- US3 (P2), US4 (P2), US5 (P3) each tighten a different placeholder slot in `pipeline.run()`; they can progress in parallel.
- US6 (P3) adds the invariant-check layer and depends on US1's `run()` existing; the invariant checks run BEFORE assembly, so US2–US5 continue to work.

### Within Each User Story

- Tests are written first (checked in) but may legitimately pass only after the implementation tasks land — treat each test file as the acceptance spec for the implementation tasks that follow it.
- Helpers (`flatten`, `quality`, `trace`, `validation`) are written before being wired into `pipeline.run()`.
- Fixtures are committed before the tests that consume them.

### Parallel Opportunities

- **Phase 1**: T002, T003 are both `[P]` — parallel with T001/T004.
- **Phase 2**: T006, T007, T009, T010, T011 are all `[P]` — can run in parallel after T005 (errors.py) lands, since T008's dataclass depends only on imports.
- **Phase 4 (US2)**: T017, T018 parallel; then T019 blocks T020.
- **Phase 5 (US3)**: T021, T022, T023 parallel; then T024 blocks T025.
- **Phase 6 (US4)**: T026, T027, T028 parallel; T029/T030/T031 can parallel (different functions in same file); T032 blocks nothing.
- **Phase 8 (US6)**: T035, T036, T037, T038, T039, T040 all parallel (different files); T041 blocks T042/T043.
- **Phase 9 (CLI)**: T046, T047 parallel with T044 after T044 lands.
- **Phase 10 (Polish)**: T048, T049, T050, T051, T052, T053 all parallel; T054 is the final gate (full test suite).

---

## Parallel Example: Phase 2 (Foundational)

```bash
# After T005 (errors.py) lands, launch in parallel:
Task: "Implement version.py — SEMVER/SLICE_PREFIX + build_pipeline_version()"  # T006
Task: "Implement write.py — deterministic JSON writer"                         # T007
Task: "Create fixture pair tests/fixtures/assembler/happy_grounded/"           # T009
Task: "Add unit test tests/unit/test_assembler_version.py"                     # T010
Task: "Add unit test tests/unit/test_assembler_write.py"                       # T011
```

## Parallel Example: Phase 8 (US6 Hard Failures)

```bash
# Fixtures + tests run in parallel — all different files:
Task: "Create fixture tests/fixtures/assembler/contract_drift/"          # T035
Task: "Create fixture tests/fixtures/assembler/document_id_mismatch/"    # T036
Task: "Create fixture tests/fixtures/assembler/routing_contradiction/"   # T037
Task: "Create fixture tests/fixtures/assembler/schema_invalid_extractor/" # T038
Task: "Add tests/pipeline_tests/test_assembler_us6_hard_failures.py"     # T039
Task: "Add tests/unit/test_assembler_routing_consistency.py"             # T040
```

---

## Implementation Strategy

### MVP First (US1 + US2 — both are P1)

1. Complete Phase 1 (Setup) + Phase 2 (Foundational).
2. Complete Phase 3 (US1) — schema-valid emission lands.
3. Complete Phase 4 (US2) — flattening is correct.
4. **STOP and VALIDATE**: Run `python -m dartwing_ocr.assembler --document-folder tests/fixtures/assembler/happy_grounded/` (once Phase 9 minimal CLI is in place — or invoke `pipeline.run(Invocation(...))` directly). Confirm schema-valid output with zero evidence keys.
5. The MVP delivers the "clean downstream handoff" contract guaranteed by the spec's P1 stories.

### Incremental Delivery

1. Setup + Foundational ready → `Invocation`, `run()` skeleton, fixtures, error taxonomy all exist.
2. US1 + US2 → MVP: schema-valid + correctly flattened output on grounded input.
3. US3 → review-status verbatim on three review_reason shapes.
4. US4 → `quality_summary` formula + ordering pinned.
5. US5 → trace block hardened.
6. US6 → hard-fail invariant layer.
7. CLI integration + polish → `dartwing-assemble` usable end-to-end, all four checklists walked, quickstart validated.

### Parallel Team Strategy

After Phase 2 closes:

- Dev A: Phase 3 (US1) then Phase 4 (US2) sequentially (shared `pipeline.run()` file).
- Dev B: Phase 5 (US3) and Phase 6 (US4) — independent helpers.
- Dev C: Phase 7 (US5) — trace.py.
- Dev D: Phase 8 (US6) fixtures (T035–T038) and unit test T040 — completely independent.

All four streams converge at Phase 9 (CLI) and Phase 10 (polish), which proceed after every story phase closes.

---

## Notes

- `[P]` tasks = different files, no unresolved dependencies on incomplete tasks.
- `[Story]` labels map tasks to the spec's six user stories for traceability to acceptance criteria.
- Every story must remain independently testable after its phase closes — a regression in US3's verbatim propagation must not break US1's schema-valid output.
- Commit after each task or logical group (hooks settings show auto-commit prompts between phases are available).
- Stop at any checkpoint (end of Phase 2, 3, 4, 6, 8, or 9) to deploy/demo the current increment.
- Avoid: blurring the pipeline/harness boundary (Constitution §I), collapsing deterministic code into model output (Constitution §III), or rewriting the frozen v1.0.0 contract (use `AMENDMENTS.md` if needed).
