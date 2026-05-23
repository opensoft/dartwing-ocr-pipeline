---
description: "Task list for feature 022 — OCR Semantic Quality Gate"
---

# Tasks: OCR Semantic Quality Gate

**Input**: Design documents from `/specs/022-ocr-semantic-quality-gate/`
**Prerequisites**: plan.md, spec.md (44 clarifications), research.md (R-022.1…R-022.15), data-model.md, contracts/ (module-invariants.md, schema-amendments.md, validator-cli-contract.md, evaluator-output-contract.md), quickstart.md

**Tests**: Test tasks are REQUIRED for this feature — FR-032 mandates that every active functional requirement be covered by at least one implementation task AND at least one test, and SC-010 makes the FR↔task↔test mapping a measurable success criterion. All gate tests are CPU-only and Paddle-free (MI-1).

**Organization**: Tasks are grouped by the five user stories from `spec.md` so each story can be implemented and verified independently. Implementation dependency order is US1 → US2 → US3 → US4 → US5, which honors P1/P2/P3 priorities except that US3 (P2 — report surface) lands before US4 (P1 — non-regression) because US4's `document_pass_fail.semantic_table_quality_passed` assertions consume the US3 writer integration. US1, US2, and US5 are independent of each other once the foundational phase completes.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story this task belongs to (US1, US2, US3, US4, US5); omitted for Setup/Foundational/Polish phases
- All file paths are absolute under `/workspace/projects/dartwing/ocr-pipeline-worktrees/022-ocr-semantic-quality-gate/` (the feature worktree root)

## Path Conventions

Single-project Python library + CLI extension. Source under `src/dartwing_ocr/`, contracts under `contracts/stage1_vendor_identity/`, tests under `tests/` (existing roots: `contract_tests/`, `unit/`, `integration/`; one new root `stage1_semantic_quality/` per Q15/Q40).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the empty v1.3.0 contract-set directory and seed the new test root so subsequent phases can write into stable locations.

- [X] T001 Create directory `contracts/stage1_vendor_identity/v1.3.0/` (empty placeholder; populated by Foundational phase).
- [X] T002 [P] Create directory `tests/stage1_semantic_quality/inv_001_hard/` (empty placeholder; populated by US2 fixture tasks; subfolder name follows Q40 canonical `^inv_\d{3}_(easy|medium|hard)$` pattern).
- [X] T003 [P] Verify `pyproject.toml` declares `jsonschema>=4.22,<5` and `pydantic>=2.7,<3` (no new pinned dependency added — confirm both lines exist and CI install path is unchanged).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Ship the cross-cutting code and contract artifacts every user story depends on: the v1.3.0 contract-set copy + bump, the shared `corpus_pattern` allowlist (used by both validator and metrics), the `stable_json` serializer (used by both per-doc and run-summary writers), and the gate's hard-error exception type.

**CRITICAL**: No user-story implementation may begin until Phase 2 is complete.

### Contract set v1.3.0 (R-022.5 / Q14)

- [X] T004 Copy every file under `contracts/stage1_vendor_identity/v1.2.0/` to `contracts/stage1_vendor_identity/v1.3.0/` byte-identical (`preprocess_output.schema.json`, `edge_extraction_output.schema.json`, `routing_decision.schema.json`, `final_structured_payload.schema.json`, `evidence_packet.schema.json`, `expected.schema.json`, `evaluation_document.schema.json`, `evaluation_run_summary.schema.json`, `folder.schema.json`, `contract_set.json`, `README.md`). T009/T010/T011/T012 will modify the four amended schemas afterward.
- [X] T005 Write `contracts/stage1_vendor_identity/v1.3.0/semantic_table_truth.schema.json` per `contracts/schema-amendments.md` Schemas-added section: Draft 2020-12, `$id` `https://dartwing.internal/schemas/stage1/v1.3.0/semantic_table_truth.schema.json`, top-level `{document_id, rows, schema_version?}` with `additionalProperties: false`; `$defs.row` requires `{row_id, required_row_text_tokens}`, optional `{quantity, description, unit_price, amount}`, `additionalProperties: false`; `unit_price`/`amount` match `^\d+\.\d{2}$` (Q9/R-022.5). **Plus security-clarify Q-SEC-2/B**: `document_id` AND `row_id` carry the safety pattern `^[A-Za-z0-9_-]{1,64}$` PLUS `minLength: 1` PLUS `maxLength: 64` — rejects path-traversal, control characters, whitespace, and runaway identifier lengths.
- [X] T006 Update `contracts/stage1_vendor_identity/v1.3.0/contract_set.json` — set `contract_set_version = "1.3.0"`, add `semantic_table_truth.schema.json` to the schema listing, keep all other v1.2.0 entries.

### Shared helpers (no new dependency; pure stdlib + existing libs)

- [X] T007 [P] Create `src/dartwing_ocr/validator/corpus_pattern.py` defining `CANONICAL_FOLDER_PATTERN = re.compile(r"^inv_\d{3}_(easy|medium|hard)$")` and `is_scored_corpus_folder(folder_basename: str) -> bool` per data-model §9 / MI-21 / R-022.15. Module-level compile.
- [X] T008 [P] Create `src/dartwing_ocr/evaluator/stable_json.py` exposing `dump_stable(obj, path: Path) -> None` per R-022.3: `json.dumps(sort_keys=True, ensure_ascii=False, indent=2)`, UTF-8, LF line endings, trailing newline at EOF, no trailing whitespace; custom `JSONEncoder` that detects `decimal.Decimal`, rounds to 6 dp with `ROUND_HALF_EVEN`, emits as JSON number via `float()`. Pure stdlib (`json`, `decimal`, `pathlib`).
- [X] T009 [P] Create `src/dartwing_ocr/evaluator/exceptions.py` defining `SemanticGateInvariantError(Exception)` per MI-19 / Q42 / R-022.14 — raised on gate-time invariant violation; never converted to `unevaluable`.
- [X] T010 [P] Update `src/dartwing_ocr/contract_versions.py` — bump `CURRENT_CONTRACT_SET_VERSION` from `"1.2.0"` to `"1.3.0"`; keep v1.2.0 loader function importable for backward-compat reads (FR-019 / Q43 / R-022.9).

### Foundational unit tests

- [X] T011 [P] Add `tests/unit/validator/test_corpus_pattern.py` — verify `CANONICAL_FOLDER_PATTERN` matches `inv_001_easy`/`inv_010_medium`/`inv_999_hard`; rejects `inv_024_hard_degraded_body`, `inv_001`, `inv_001_extra`, `INV_001_HARD`, empty string (Q23 / MI-21 / SC-009).
- [X] T012 [P] Add `tests/unit/evaluator/test_stable_json.py` — verify sort_keys at every nesting level; UTF-8 + LF + trailing newline + no trailing whitespace; `Decimal("0.1234565")` round-half-to-even at 6 dp emits as JSON number `0.123456` (banker's rounding); `Decimal("0.1234575")` emits as `0.123458`; integer counts emit as JSON integers; byte-identity across two consecutive calls (Q34 / FR-014 / MI-16).
- [X] T013 [P] Add `tests/unit/evaluator/test_exceptions.py` — verify `SemanticGateInvariantError` is an `Exception` subclass; raising it does not get caught by a generic `try: ... except Exception` block that converts to `unevaluable` (Q42 / MI-19).
- [X] T014 [P] Add `tests/contract_tests/test_contract_set_v1_3.py` — load `contracts/stage1_vendor_identity/v1.3.0/contract_set.json` and verify `contract_set_version == "1.3.0"`; verify every v1.2.0 schema file exists byte-identical at v1.3.0 except the four amended ones (T004); verify `semantic_table_truth.schema.json` is listed and loads as valid JSON Schema Draft 2020-12 (R-022.5). **Plus FR-006 byte-identity assertion (per F9 resolution)**: `contracts/stage1_vendor_identity/v1.3.0/expected.schema.json` MUST be byte-identical (SHA-256 match) to `contracts/stage1_vendor_identity/v1.2.0/expected.schema.json` — guards against silent shape drift in the `expected.json` vendor-identity truth contract (FR-006 / MI-23).

**Checkpoint**: Foundation ready — US1/US2/US5 implementation may now proceed in parallel. (US3 depends on US2 verdict shape; US4 depends on US2 and US3.)

---

## Phase 3: User Story 1 — Author and validate the semantic table truth sidecar (Priority: P1)

**Goal**: Ship the `semantic_table_truth.json` validator and the `validate semantic-truth` CLI subcommand so a fixture author can author and verify a sidecar in isolation. No gate logic and no evaluator integration in this phase.

**Independent Test**: From `spec.md` US1 — Author a `semantic_table_truth.json` for one degraded-body fixture; run the validator and confirm it accepts a well-formed sidecar, rejects one whose `document_id` mismatches the folder, and rejects one whose rows violate the contract. Confirm a folder with no sidecar still validates under the existing `expected.json` contract.

### Tests for User Story 1 (write first, ensure they FAIL before implementation)

- [ ] T015 [P] [US1] Add `tests/contract_tests/test_semantic_table_truth_schema.py` — for each of these inputs, assert the v1.3.0 `semantic_table_truth.schema.json` accepts the GOOD cases and rejects the BAD cases: (a) good single-row sidecar with all optional cells; (b) good multi-row sidecar with row-text-tokens-only rows; (c) missing top-level `document_id`; (d) missing `rows`; (e) empty `rows` array (minItems 1); (f) row missing `row_id`; (g) row missing `required_row_text_tokens`; (h) row with empty `required_row_text_tokens` array; (i) row with empty-string token inside `required_row_text_tokens`; (j) row with `unit_price = "$21.00"` (currency symbol rejected); (k) row with `unit_price = "21.0"` (insufficient cents digits); (l) row with `unit_price = "21.00"` accepted; (m) row with `amount = "1,234.56"` rejected (comma not allowed by `^\d+\.\d{2}$`); (n) row with additional unknown property rejected (`additionalProperties: false`); (o) sidecar with additional top-level property rejected; (p) optional `schema_version: "1.3.0"` accepted. **Plus security-clarify Q-SEC-2/B safety-pattern test cases**: (q) `document_id = "inv_001_hard"` accepted (canonical); (r) `row_id = "row-1"` accepted; (s) `document_id = "../etc/passwd"` rejected (path-traversal — fails `^[A-Za-z0-9_-]{1,64}$`); (t) `row_id` 65-char string rejected (exceeds `maxLength: 64`); (u) `row_id = "row 1"` rejected (whitespace not in charset); (v) `row_id = "row.1"` rejected (period not in charset); (w) `row_id = "row "` rejected (control character); (x) `document_id = ""` rejected (`minLength: 1`).
- [ ] T016 [P] [US1] Add `tests/unit/validator/test_semantic_table_truth_validator.py` — for `dartwing_ocr.validator.semantic_table_truth.validate_sidecar(folder_path)`: (a) accept good sidecar; (b) reject `document_id` mismatch with error string containing BOTH the declared value AND the folder basename (Q41); (c) reject duplicate `row_id` across rows with error naming the duplicate `row_id` and the duplicate index (Q11 / Q41); (d) reject row missing `row_id` with `[<array_index>]` identifier in the error (Q41); (e) reject row with `unit_price = "$21.00"` with error naming `row_id`, field `unit_price`, and a one-line reason mentioning `^\d+\.\d{2}$`; (f) all row violations reported, not just the first (validator-cli-contract.md §Error message content). **Plus security-clarify Q-SEC-2/B**: (g) reject row with `row_id = "../escape"` — named-error includes `row_id` value and one-line reason mentioning the safety pattern `^[A-Za-z0-9_-]{1,64}$`; (h) reject sidecar with `document_id = "../../../etc/passwd"` — named-error includes both the declared `document_id` and the safety-pattern violation reason; (i) reject 65-char `row_id` with reason citing `maxLength: 64` or pattern violation.
- [ ] T017 [P] [US1] Add `tests/contract_tests/test_folder_contract_v1_3.py` — load v1.3.0 `folder.schema.json` and verify (a) folder without `semantic_table_truth.json` still validates; (b) folder with `semantic_table_truth.json` validates; (c) mandatory artifacts (`source.pdf`, `expected.json`) still required unchanged from v1.2.0; (d) sidecar listed as optional in the schema (T011 schema edit).
- [ ] T018 [P] [US1] Add `tests/integration/test_us1_sidecar_validation.py` — acceptance scenarios AS1-AS5: (AS1) well-formed sidecar in scored folder accepted; (AS2) mismatched `document_id` rejected with named-mismatch error; (AS3) malformed row (e.g. duplicate `row_id`) rejected with row-identifying error; (AS4) folder with no sidecar still validates under existing `expected.json` contract — no new requirement imposed (FR-005); (AS5) `expected.json` shape unchanged — fixture written with original vendor-identity-only shape still validates (FR-006 / MI-23).

### Implementation for User Story 1

- [ ] T019 [P] [US1] Amend `contracts/stage1_vendor_identity/v1.3.0/folder.schema.json` — list `semantic_table_truth.json` as an OPTIONAL file in the per-document folder contract (mandatory artifacts `source.pdf` and `expected.json` unchanged). Update `$id` to v1.3.0.
- [ ] T020 [US1] Create `src/dartwing_ocr/validator/semantic_table_truth.py` implementing `validate_sidecar(folder_path: Path) -> SemanticTruthValidationResult`: (1) check file exists; (2) parse JSON (catch `json.JSONDecodeError`); (3) jsonschema-validate against v1.3.0 `semantic_table_truth.schema.json` (loaded via existing `validator.loader`); (4) verify `document_id == folder_path.name` (Q41 mismatch error: name both); (5) verify all `row_id` values unique (Q11); (6) row-by-row checks reporting ALL violations not just the first (Q41); (7) raise/return structured `SemanticTruthValidationError` with the Q41 message contents. Module-level `EXPECTED_CELL_DECIMAL_REGEX = re.compile(r"^\d+\.\d{2}$")` per data-model §9.
- [ ] T021 [US1] Update `src/dartwing_ocr/validator/folder.py` — when a folder contains `semantic_table_truth.json`, call `semantic_table_truth.validate_sidecar(folder)` after existing mandatory-artifact checks (FR-005: when absent, behavior unchanged from v1.2.0). Surface sidecar errors as folder-validation errors with the contract-defined exit-code mapping (validator-cli-contract.md §`validate folder` — codes 3, 4, 5).
- [ ] T022 [US1] Update `src/dartwing_ocr/validator/cli.py` — add `validate semantic-truth <folder>` subcommand per validator-cli-contract.md §`validate semantic-truth`: 7-step flow with exit codes 0, 1, 2, 3, 4, 5; calls into `semantic_table_truth.validate_sidecar`. Update `validate folder` argparse to surface the new exit codes 3/4/5; existing codes 0/1/2 unchanged.

**Checkpoint**: User Story 1 fully functional — a fixture author can run `python -m dartwing_ocr.validator validate semantic-truth <folder>` and get pass/fail with Q41-compliant error messages. T018 integration tests should pass green at this point with no gate code present.

---

## Phase 4: User Story 2 — Deterministically evaluate semantic/table OCR quality (Priority: P1)

**Goal**: Ship the deterministic gate that consumes `preprocess_output.json` + `semantic_table_truth.json` and returns a `SemanticQualityResult` (status + failed_checks + row_reasons + supporting_evidence + optional cause). No evaluator/writer integration in this phase — the gate is a pure function that returns an in-memory result object. The hand-authored synthetic fixture at `tests/stage1_semantic_quality/inv_001_hard/` is created here so US2 can be tested end-to-end.

**Independent Test**: From `spec.md` US2 — Run the gate on the committed synthetic fixture; confirm the verdict is `failed`, names at least one concrete failed check, and re-runs byte-identical (SC-001 / SC-002 / SC-007).

### Tests for User Story 2 (write first, ensure they FAIL before implementation)

- [X] T023 [P] [US2] Add `tests/unit/evaluator/test_semantic_quality_normalize.py` covering FR-009 / Q5 / Q32: (a) NFKC normalization (full-width digits `０１２` → `012`, accented `é` composed/decomposed equivalence); (b) `casefold()` on Turkish `İ`/`ı` and German `ß` → `ss`; (c) Unicode whitespace collapse (NBSP, em-space, tab, newline all → single ASCII space); (d) `P*` category stripping covers `Pc` (`_`), `Pd` (`-`), `Pe` (`)`), `Pf` (`»`), `Pi` (`«`), `Po` (`.` `,` `:`), `Ps` (`(`); (e) idempotence: `normalize(normalize(x)) == normalize(x)` on a parametrized list of inputs.
- [X] T024 [P] [US2] Add `tests/unit/evaluator/test_semantic_quality_body_ocr.py` covering Q22 / R-022.4: (a) lines on page-1 with `bbox.top` y-fraction < 0.25 excluded; (b) lines on page-1 with y-fraction ≥ 0.25 included; (c) all pages 2..N fully included regardless of y; (d) `header_band_excluded == True` when at least one page-1 line was filtered, `False` otherwise; (e) `Y_THRESHOLD_FRACTION` is imported from `preprocessing.evidence_gate`, not redeclared (MI-7); (f) lane-robust: identical results on PPStructureV3 vs OCR-only `preprocess_output.json` shapes.
- [X] T025 [P] [US2] Add `tests/unit/evaluator/test_semantic_quality_anchor.py` covering FR-012 / Q7 / Q24: (a) row anchored to span containing the most `required_row_text_tokens` (NOT fuzzy edit distance); (b) tie-break by earliest `preprocess_output.json` serialization-order position (page array index, then line index); (c) further ties broken by sidecar declaration order; (d) anchor span returns `None` for empty `BodyOcrEvidence`; (e) deterministic across two consecutive runs on the same input.
- [X] T026 [P] [US2] Add `tests/unit/evaluator/test_semantic_quality_currency.py` covering FR-010 / Q10 / Q16 / Q35: (a) `CANONICAL_MONEY_REGEX` accepts `$21.00`, `21.00`, `$1,234.56`, `1234.56`; rejects `$21:00`, `$22:`, `21.0`, `21`, `$1,23.00`; (b) per-field digit-sequence matching: a quantity token `21` is NOT misclassified as currency for an `amount = "21.00"` field; (c) when no candidate token exists for a declared currency field, return signals `missing-required-content` not `malformed-currency-shape`; (d) regex applied to RAW token before FR-009 normalization (a `$21:00` token survives normalization to `2100` which would pass; the raw `$21:00` is what's evaluated).
- [X] T027 [P] [US2] Add `tests/unit/evaluator/test_semantic_quality_checks.py` covering FR-009 / FR-011 / FR-012 / Q17 / Q18: (a) all four predicates evaluated for every row (no short-circuit); (b) failed checks recorded in fixed order: `malformed-currency-shape` → `missing-required-content` → `row-text-coverage-gap` → `row-alignment-failure`; (c) outer iteration is sidecar row declaration order; (d) a row with both malformed currency AND missing description records BOTH failures (Q18 — no mutual exclusion); (e) row-text-coverage gap is binary — single missing token triggers failure with no numeric threshold.
- [X] T028 [P] [US2] Add `tests/unit/evaluator/test_semantic_quality_aggregate.py` covering FR-016 / Q4 / Q26: (a) status `failed` when any `failed_checks` entry exists; (b) status `passed` when zero failed checks across all rows; (c) status `not_applicable` when no sidecar; (d) status `unevaluable` when sidecar present but preprocess unreadable; (e) status string is verbatim one of `passed`/`failed`/`not_applicable`/`unevaluable` (MI-11) — no capitalization, no `None`.
- [X] T029 [P] [US2] Add `tests/unit/evaluator/test_semantic_quality_report.py` covering FR-017 / Q29 / Q30 / Q31 / Q37: (a) `failed_checks` is flat ordered array (source of truth) with all FR-015 fields per row+category; (b) `row_reasons` is a JSON **object keyed by `row_id`** (not an array) whose values are the closed record `{categories: list[str], reason: str}` with `categories` carrying kebab-case failed-category labels in the fixed Q17 order and `reason` a short one-line human-readable summary; (c) `row_reasons` derivable by grouping `failed_checks` (MI-14); each `row_id` appears at most once as a key; (d) `supporting_evidence` closed shape `{body_confidence_mean, body_confidence_min, body_line_count, body_token_count, header_band_excluded}` — no extra keys; when `body_line_count == 0` both `body_confidence_mean` and `body_confidence_min` are `0.0` (NOT `null` — per F3 resolution / R-022.12); (e) `cause` populated only when `status == unevaluable` and is one of the four Q31 enum values; (f) `cause_detail` optional free-text.
- [X] T030 [P] [US2] Add `tests/unit/evaluator/test_semantic_quality_unevaluable.py` covering Q31 / R-022.13 cascade: (a) `preprocess_output.json` missing → cause `preprocess_output_missing`; (b) file present but unparseable JSON → cause `preprocess_output_invalid_json`; (c) file parses but fails schema → cause `preprocess_output_schema_invalid`; (d) file parses + schema-valid but zero body OCR lines → cause `body_ocr_unreadable`; (e) gate-time invariant violation (e.g. anchor returns inconsistent span) raises `SemanticGateInvariantError` and is NOT recorded as `unevaluable` (Q42 / MI-19).
- [X] T031 [P] [US2] Add `tests/unit/evaluator/test_semantic_quality_module_safety.py` covering MI-1: (a) `import dartwing_ocr.evaluator.semantic_quality` succeeds in a subprocess with `PYTHONPATH` excluding Paddle; (b) `sys.modules` after the import contains no key starting with `paddle`; (c) no socket / DNS activity occurs during a gate run (monkey-patch `socket.socket.connect` to raise and verify the gate still completes).
- [X] T032 [P] [US2] Add `tests/unit/evaluator/test_semantic_quality_determinism.py` covering SC-007 / FR-014 / MI-2: run the gate twice on the same synthetic fixture inputs; assert the two `SemanticQualityResult` dataclass values are equal AND the byte-serialization through `stable_json.dump_stable` is byte-identical.
- [X] T033 [P] [US2] Add `tests/integration/test_us2_independent_test.py` — US2 acceptance scenarios AS1-AS7 against the synthetic fixture: (AS1) `$21:00` observed vs `21.00` expected → failed currency-shape; (AS2) missing required cell → failed missing-required-content; (AS3) shifted/split row → failed row-alignment; (AS4) partial row text → failed row-text-coverage; (AS5) high body_confidence_mean ≈ 0.97 + failing content checks → status remains `failed`; (AS6) two runs byte-identical (SC-007); (AS7) no network and no model call during the run (assert via monkey-patched `socket.socket` and absence of `paddle*` modules).

### Implementation for User Story 2

- [X] T034 [P] [US2] Create `src/dartwing_ocr/evaluator/semantic_quality_normalize.py` exposing `normalize(text: str) -> str` per data-model §11: NFKC → casefold → Unicode whitespace collapse (`re.sub(r"\s+", " ", text)`) → strip every code point whose `unicodedata.category(ch)[0] == "P"` → `strip()`. Stdlib only (`unicodedata`, `re`). Idempotent.
- [X] T035 [P] [US2] Create `src/dartwing_ocr/evaluator/semantic_quality_body_ocr.py` exposing `build_body_ocr_evidence(preprocess_output_dict: dict) -> BodyOcrEvidence` per data-model §3: iterate `preprocess_output.json` pages in serialization order (Q24), filter page-1 lines below `EVIDENCE_GATE_Y_THRESHOLD_FRACTION = 0.25` (imported from `preprocessing.evidence_gate` per MI-7 / R-022.4), build `included_lines: list[BodyOcrLine]` with `raw_text`/`detector_confidence`/`page_index`/`line_index`/`raw_tokens` (whitespace-split), set `header_band_excluded`, and build `normalized_search_string` by joining `raw_text` values with single ASCII space and applying `normalize()` once (Q33 / MI-6).
- [X] T036 [P] [US2] Create `src/dartwing_ocr/evaluator/semantic_quality_anchor.py` exposing `anchor_rows(rows: list[SemanticTableRowTruth], evidence: BodyOcrEvidence) -> dict[str, RowAnchor | None]` per data-model §12: for each row, generate candidate contiguous spans over `included_lines`, score by count of `required_row_text_tokens` present in the span's normalized text, pick max-count span; tie-break by earliest `(page_index, line_index)` (Q24), then sidecar declaration order; return `RowAnchor(row_id, start_line_index, end_line_index)` per row.
- [X] T037 [P] [US2] Create `src/dartwing_ocr/evaluator/semantic_quality_currency.py` exposing `CANONICAL_MONEY_REGEX = re.compile(r"^\$?\d{1,3}(,\d{3})*\.\d{2}$")` at module load and `locate_currency_token(span_raw_tokens, expected_digit_seq, already_matched_indices) -> tuple[int, str] | None`: scan tokens in serialization order, return first not-yet-matched raw token whose digit-only representation equals `expected_digit_seq` (per Q35). Stdlib only (`re`).
- [X] T038 [US2] Create `src/dartwing_ocr/evaluator/semantic_quality_checks.py` exposing the four predicate functions: `evaluate_missing_required_content(row, normalized_search_string) -> list[FailedCheck]` (FR-009 substring containment), `evaluate_currency_shape(row, anchor, evidence, currency_match_state) -> list[FailedCheck]` (FR-010 / Q10 / Q16 / Q35 — RAW token, anchored regex, defer-missing rule), `evaluate_row_text_coverage(row, normalized_search_string) -> list[FailedCheck]` (FR-011 binary), `evaluate_row_alignment(row, anchor, evidence) -> list[FailedCheck]` (FR-012 anchored-span ordering). Each returns 0..N `FailedCheck` records; no short-circuit (MI-3). Plus orchestrator `evaluate_all_rows(rows, evidence) -> list[FailedCheck]` that runs the outer row loop and inner check-category loop in the fixed Q17 order and assembles the flat array with `position_index` per data-model §4.
- [X] T039 [P] [US2] Create `src/dartwing_ocr/evaluator/semantic_quality_report.py` exposing `build_semantic_quality_result(status, failed_checks, evidence, cause=None, cause_detail=None) -> SemanticQualityResult` per data-model §6/§7: build closed `supporting_evidence` shape with 6-dp `body_confidence_mean`/`body_confidence_min` (Decimal + ROUND_HALF_EVEN), `body_line_count`, `body_token_count`, `header_band_excluded`; when `body_line_count == 0` emit BOTH mean and min as `0.0` (NOT `null` — per F3 resolution / R-022.12). Derive `row_reasons` as a JSON object keyed by `row_id` (NOT an array) from `failed_checks` grouped by `row_id` (MI-14); each value is the closed record `{categories: list of failed-category labels in fixed Q17 order, reason: str}`. `failed_checks` is always present when `status ∈ {passed, failed, unevaluable}` — non-empty when failed, empty array `[]` when passed or unevaluable, omitted only when `status == not_applicable` (per F5 resolution / data-model §7). `row_reasons` is required when `status == failed`; omitted otherwise. Populate `cause` only when `status == unevaluable`. Define dataclasses `FailedCheck`, `RowReasonEntry` (carrying `categories` + `reason`; the `row_id` is the parent dict key), `SupportingEvidence`, `SemanticQualityResult` (pydantic v2 BaseModels are fine since pydantic is an existing dep).
- [X] T040 [US2] Create `src/dartwing_ocr/evaluator/semantic_quality.py` — the gate entry point. Define `SEMANTIC_QUALITY_GATE_VERSION = "v1"` and `run_semantic_quality_gate(preprocess_output_path: Path | None, sidecar_path: Path | None, folder_basename: str) -> SemanticQualityResult` orchestrating: (1) sidecar absent → `status = not_applicable`, no supporting_evidence; (2) sidecar present, run the R-022.13 four-step `unevaluable` cause cascade — file missing / invalid JSON / schema invalid / no body lines — and return early with the matching closed `cause`; (3) otherwise build `BodyOcrEvidence` (T035), anchor rows (T036), evaluate all rows (T038) in the fixed Q17 order with no short-circuit, aggregate by any-fail rule (MI-10 / Q4) into `passed`/`failed`, build the report (T039) and return. Raise `SemanticGateInvariantError` (T009) for invariant violations per MI-19. No Paddle import, no network call (MI-1).
- [X] T041 [US2] Create the synthetic US2 fixture at `tests/stage1_semantic_quality/inv_001_hard/preprocess_output.json`: hand-authored, schema-valid against v1.3.0 `preprocess_output.schema.json` (T004 copy), 8 body rows reproducing the `inv_024_hard_degraded_body` calibration pattern — per-line `detector_confidence` ≈ 0.97 (high), but body text contains colon-for-decimal currency (e.g. `$21:00`), missing quantity values, and mutated descriptions per R-022.6. No `source.pdf` (Q25 / MI-25).
- [X] T042 [US2] Create the matching sidecar at `tests/stage1_semantic_quality/inv_001_hard/semantic_table_truth.json`: 8 rows; `document_id = "inv_001_hard"`; per row declare `row_id`, `required_row_text_tokens` (description-derived), `unit_price` and `amount` as `^\d+\.\d{2}$` strings so the gate's currency-shape check fires on at least one row; passes T020 sidecar validator. Q40-compliant folder name.

**Checkpoint**: User Story 2 fully functional — `run_semantic_quality_gate(...)` returns a deterministic verdict object for the synthetic fixture. T033 integration test passes green. No evaluator-writer integration yet; results are in-memory only.

---

## Phase 5: User Story 3 — Surface semantic table quality in evaluator reports (Priority: P2)

**Goal**: Land the report surface — the writer extension that emits `semantic_table_quality` + `document_pass_fail.semantic_table_quality_passed` on `evaluation_document.json`, the `semantic_table_quality_metrics` namespace + per-document status entries on `evaluation_run_summary.json`, the schema additions that make those fields valid, and the backward-compat read path (FR-019 / Q43) so pre-feature reports still validate. US4 (P1 non-regression) depends on this phase.

**Independent Test**: From `spec.md` US3 — Run the evaluator over a corpus containing at least one document with a sidecar and at least one without; confirm `evaluation_document.json` for the sidecar document includes `semantic_table_quality`; confirm the without-sidecar document reports semantic status `not_applicable`; confirm `evaluation_run_summary.json` includes the metrics namespace; confirm a pre-feature report still validates.

### Tests for User Story 3 (write first, ensure they FAIL before implementation)

- [ ] T043 [P] [US3] Add `tests/contract_tests/test_evaluation_document_v1_3.py` — v1.3.0 `evaluation_document.schema.json` accepts: (a) report with no `semantic_table_quality` and `semantic_table_quality_passed: null`; (b) report with `semantic_table_quality.status == "passed"`, `failed_checks: []`, no `row_reasons` (per F5 resolution — empty array on passed/unevaluable, omitted only on not_applicable); (c) report with `status == "failed"` and required `failed_checks` (non-empty) + `row_reasons` (object keyed by `row_id` with `{categories, reason}` values per F1/F2 resolution) + `supporting_evidence`; (d) report with `status == "unevaluable"`, `failed_checks: []`, `supporting_evidence` with `body_confidence_min: 0.0` (NOT null per F3), and required `cause` from closed enum + optional `cause_detail`; (e) report rejecting `status == "FAILED"` (must be snake_case verbatim per Q26 / MI-11); (f) `supporting_evidence` with extra key rejected; (g) `failed_checks[].category` not in the four kebab-case values rejected; (h) `row_reasons` as a JSON ARRAY rejected (must be object keyed by `row_id`); (i) `row_reasons` value missing `categories` or `reason` rejected.
- [ ] T044 [P] [US3] Add `tests/contract_tests/test_evaluation_run_summary_v1_3.py` — v1.3.0 `evaluation_run_summary.schema.json` accepts the additive top-level `semantic_table_quality_metrics` namespace (Q36) with all eight fields; `semantic_table_quality_pass_rate: null` when `semantic_evaluable_document_count == 0` accepted; top-level sibling array `semantic_document_statuses` (pinned per F6 — NOT nested inside metrics) with closed-shape entries `{document_id, semantic_table_quality_status, semantic_table_quality_passed}` accepted; rejects metrics with extra unknown key; rejects unknown semantic status string; rejects a `semantic_document_statuses` entry missing any of the three required fields.
- [ ] T045 [P] [US3] Add `tests/contract_tests/test_backward_compat_v1_2.py` covering FR-019 / SC-008 / Q43: (a) a pre-feature `evaluation_document.json` (no `semantic_table_quality`, no `semantic_table_quality_passed`) loaded through the backward-compat read path is accepted without raising; (b) the reader returns `semantic_table_quality_passed = None` (Python `None` ⇄ JSON `null`) for the absent field (Q43 / MI-24); (c) a pre-feature `evaluation_run_summary.json` (no `semantic_table_quality_metrics`) still validates.
- [ ] T046 [P] [US3] Add `tests/unit/evaluator/test_semantic_quality_metrics.py` covering FR-018 / Q19 / Q36 / Q39: (a) all eight `semantic_table_quality_metrics` fields populate from a mixed-status document list; (b) `semantic_evaluable_document_count == semantic_passed_document_count + semantic_failed_document_count`; (c) `semantic_table_quality_pass_rate` rounded to 6 dp ROUND_HALF_EVEN; (d) `pass_rate == null` when evaluable=0; (e) `semantic_failed_check_counts` is an object keyed by the four kebab-case categories; (f) calibration folders (non-matching `CANONICAL_FOLDER_PATTERN`) appear in per-document entries but are EXCLUDED from aggregate counts (Q39 / MI-20).
- [ ] T047 [P] [US3] Add `tests/integration/test_us3_evaluator_reports.py` — US3 acceptance scenarios AS1-AS4: (AS1) sidecar document → `evaluation_document.json` includes `semantic_table_quality` object with `status`, `failed_checks` (always present), `row_reasons` (object keyed by `row_id` when status==failed), `supporting_evidence`; (AS2) mixed corpus → `evaluation_run_summary.json` includes both top-level sibling keys `semantic_table_quality_metrics` AND `semantic_document_statuses` (per F6 — array, parallel to metrics), AND vendor-identity pass rates comparable to prior runs; (AS3) pre-feature report still loads (FR-019 / SC-008); (AS4) existing vendor-identity metric values unchanged (FR-020).

### Implementation for User Story 3

- [ ] T048 [US3] Amend `contracts/stage1_vendor_identity/v1.3.0/evaluation_document.schema.json` per `contracts/schema-amendments.md`: add optional `semantic_table_quality` object (closed shape per Q29/Q30/Q31/Q37 — required `status` ∈ four-value enum; `failed_checks` array ALWAYS PRESENT when the object is present, items are closed-shape records with kebab-case `category` enum, `row_id`, nullable `field`, `expected`, nullable `observed`, `predicate`, `position_index` — non-empty when `status == failed`, empty `[]` when `status ∈ {passed, unevaluable}` per F5 resolution / data-model §7; `row_reasons` is a JSON OBJECT keyed by `row_id` with closed `{categories, reason}` value records — NOT an array, per F1/F2 resolution and `schema-amendments.md` `row_reasons.additionalProperties` definition; `row_reasons` required when `status == failed`, omitted otherwise; conditional `supporting_evidence` closed shape (`body_confidence_min` always `type: number`, never nullable, per F3 resolution); conditional `cause` ∈ four-value enum + optional `cause_detail`); add `document_pass_fail.semantic_table_quality_passed: boolean | null`. Existing vendor-identity properties untouched; `$id` bumped to v1.3.0.
- [ ] T049 [US3] Amend `contracts/stage1_vendor_identity/v1.3.0/evaluation_run_summary.schema.json` per schema-amendments.md: add top-level `semantic_table_quality_metrics` object with eight fields (Q19 / Q36); add top-level sibling array key **`semantic_document_statuses`** (pinned per F6 resolution — NOT nested inside `semantic_table_quality_metrics`) whose items are closed-shape records `{document_id: non-empty string, semantic_table_quality_status: one of the four Q26 enum values, semantic_table_quality_passed: boolean | null}`. Both new top-level keys are optional in the schema for backward-compat per FR-019 / SC-008. Existing vendor-identity / feature-020 fields untouched.
- [ ] T050 [P] [US3] Create `src/dartwing_ocr/evaluator/semantic_quality_metrics.py` per data-model §8 / R-022.15: `build_metrics_namespace(per_document_results: list[tuple[folder_basename, SemanticQualityResult]]) -> dict` computes the eight `semantic_table_quality_metrics` fields, calling `corpus_pattern.is_scored_corpus_folder` to exclude calibration folders from aggregates (Q39 / MI-20) while STILL including them in per-document status entries. Use `Decimal` + ROUND_HALF_EVEN for `semantic_table_quality_pass_rate` 6-dp rounding; emit `null` when evaluable=0.
- [ ] T051 [US3] Modify the existing per-document evaluation writer at `src/dartwing_ocr/evaluator/document.py` (the module that emits `evaluation_document.json` — NOT `report.py`, which is the run-summary writer handled by T052): always include `document_pass_fail.semantic_table_quality_passed` per MI-17 / Q20 — `true` when status=`passed`, `false` when `failed` or `unevaluable`, `null` when `not_applicable`. When status ∈ {passed, failed, unevaluable}, also include the `semantic_table_quality` object with conditional sub-fields per data-model §7. Route serialization through `stable_json.dump_stable` (MI-16). Calls `run_semantic_quality_gate` (T040) once per document — sidecar absent → not_applicable verdict without reading preprocess_output.
- [ ] T052 [US3] Modify the existing run-summary serializer (`src/dartwing_ocr/evaluator/report.py` — the module that emits `evaluation_run_summary.json`): call `semantic_quality_metrics.build_metrics_namespace` (T050) and emit the result as a top-level sibling key `semantic_table_quality_metrics` (Q36). Emit per-document semantic status entries as the top-level sibling array `semantic_document_statuses` (pinned key name per F6 resolution / `contracts/evaluator-output-contract.md` §`semantic_document_statuses`), sorted by deterministic run-document order; each entry is the closed record `{document_id, semantic_table_quality_status, semantic_table_quality_passed}`. Calibration folders are included in `semantic_document_statuses` per Q39 / MI-20 but excluded from `semantic_table_quality_metrics` aggregate counts (the exclusion logic lives in T050, not here). Route through `stable_json.dump_stable`. Existing vendor-identity / feature-020 fields untouched (FR-020 / FR-022 / MI-22).
- [ ] T053 [US3] Implement the backward-compat read path in `src/dartwing_ocr/validator/artifact.py` (or the equivalent existing reader module): when reading an `evaluation_document.json` that lacks `document_pass_fail.semantic_table_quality_passed`, interpret as `None` per Q43 / MI-24. When reading an `evaluation_run_summary.json` that lacks `semantic_table_quality_metrics`, accept and return the object as-is. Use the retained v1.2.0 schema loader from T010 for read-tolerant validation per R-022.9.

**Checkpoint**: User Story 3 fully functional — running the evaluator over a folder with a sidecar produces an `evaluation_document.json` containing `semantic_table_quality`, and the run produces an `evaluation_run_summary.json` containing the metrics namespace. Pre-feature artifacts still validate.

---

## Phase 6: User Story 4 — Preserve vendor-identity behavior and gate whole-invoice claims (Priority: P1)

**Goal**: Verify (not implement — most code lands in US3) that adding the gate does not change feature 019/020/021 behavior or `document_pass_fail.vendor_identity_passed` values, and that `document_pass_fail.semantic_table_quality_passed` has the correct value domain `true`/`false`/`null` end-to-end across the four status cases. This phase is mostly tests + a small amount of integration glue.

**Independent Test**: From `spec.md` US4 — Run the existing 20-document vendor-identity corpus before and after the feature lands; confirm vendor-identity pass/fail, feature-020 run-summary fields, and `vendor_identity_passed` values are byte-identical. Separately confirm `semantic_table_quality_passed: false` for failing-semantic + passing-vendor, and `null` for no-sidecar.

### Tests for User Story 4 (write first, ensure they FAIL before implementation/integration)

- [ ] T054 [P] [US4] Add `tests/integration/test_us4_non_regression.py` — US4 acceptance scenarios AS1-AS6: (AS1) capture pre-feature baseline output of evaluator over `tests/stage1_vendor_identity/` (20 docs) into a checked-in golden file, then after the feature lands assert vendor-identity pass/fail, all four feature-020 `evidence_gate_*` run-summary fields, and every `document_pass_fail.vendor_identity_passed` value byte-identical to the golden (SC-006 / MI-22); (AS2) document with sufficient vendor-identity evidence + failing semantic verdict → vendor-identity passes AND semantic fails independently; (AS3) feature-020 `sufficient` decision unchanged when semantic gate also runs (FR-022); (AS4) failed semantic + passing vendor → `document_pass_fail.semantic_table_quality_passed: false` (FR-025); (AS5) no-sidecar folder → `semantic_table_quality_passed: null`, no semantic pass inferred from vendor-identity (FR-025 / SC-005); (AS6) feature 019 OCR-only fallback trigger + feature 021 GPU MVP promotion criteria unchanged — assert by running pre-existing feature 019/021 integration tests still pass after the feature lands.
- [ ] T055 [P] [US4] Add `tests/unit/evaluator/test_semantic_table_quality_passed_value_domain.py` covering MI-17 / Q20 / FR-025: parametrized over the four `status` values, assert the writer (T051) produces `semantic_table_quality_passed = true / false / false / null` for `passed / failed / unevaluable / not_applicable` respectively, with no other inputs to the mapping.
- [ ] T056 [P] [US4] Add `tests/integration/test_features_019_021_unchanged.py` — smoke test that imports the existing feature 019 OCR-only fallback module and the feature 021 GPU MVP promotion logic and confirms no module under `src/dartwing_ocr/preprocessing/`, `src/dartwing_ocr/extract/`, `src/dartwing_ocr/router/`, or `src/dartwing_ocr/assembler/` was modified by feature 022 (git-diff check OR module-hash check); a CI-style assertion that this feature is harness-side only per Principle I / FR-028. **Plus FR-030 explicit negative assertion (per F8 resolution)**: grep `src/dartwing_ocr/` for the strings `line_item`, `line-item`, `line items`, and `extract_lines` and assert zero matches in code added by this feature (allowlist any pre-existing matches by content hash so the test is not noisy); assert no v1.3.0 contract schema declares a `line_items` property; assert `final_structured_payload.schema.json` v1.3.0 is byte-identical to v1.2.0 (no line-item field was added).

### Implementation for User Story 4 (small glue if needed)

- [ ] T057 [US4] Capture the pre-feature vendor-identity baseline. From a clean checkout of `main` (no feature 022 code), run the evaluator over `tests/stage1_vendor_identity/` and commit the output as a golden artifact at `tests/integration/goldens/vendor_identity_baseline_pre_022/evaluation_run_summary.json` plus the 20 per-document `evaluation_document.json` files. T054 AS1 reads these to assert byte-identity post-feature. (If a pre-feature run cannot be captured because the feature has been in-progress, use the most recent committed baseline before feature 022 commits; document the SHA in the golden directory's README.)

**Checkpoint**: User Story 4 fully verified — vendor-identity baseline byte-identical (SC-006 met), `semantic_table_quality_passed` value-domain end-to-end correct, features 019/021 untouched. Hard release gate is green.

---

## Phase 7: User Story 5 — Govern degraded-body fixture corpus promotion (Priority: P3)

**Goal**: Wire the canonical-pattern allowlist into `validate corpus` so calibration folders (e.g. `inv_024_hard_degraded_body`) are reported in a separate calibration count and excluded from scored aggregation; verify the metrics aggregator (T050) honors the same rule end-to-end. Update labeling-guide to apply PII screening to the new corpus root.

**Independent Test**: From `spec.md` US5 — Confirm a noncanonical folder is recognized as calibration material and excluded from scored corpus evaluation output. Confirm that promoting such a sample to scored corpus data is only valid when accompanied by the folder-contract, truth-contract, labeling-guide, and evaluator updates.

### Tests for User Story 5 (write first, ensure they FAIL before implementation)

- [ ] T058 [P] [US5] Add `tests/integration/test_us5_calibration_handling.py` — US5 acceptance scenarios AS1-AS3 plus Q39: (AS1) folder `inv_024_hard_degraded_body` placed under a temp corpus root → `validate corpus` reports it under "Calibration folders" not "Scored corpus folders"; (AS2) the calibration folder's per-document evaluation still runs; (AS3) scored aggregation excludes calibration folders (SC-009); (Q39) calibration folder with a sidecar → gate runs, per-document status entry appears in `evaluation_run_summary.json`, but the eight aggregate counts in `semantic_table_quality_metrics` exclude it.
- [ ] T059 [P] [US5] Add `tests/unit/validator/test_validate_corpus_calibration_reporting.py` — for a synthetic corpus root containing 2 scored folders + 1 calibration folder, `validate corpus` prints the reporting block specified in validator-cli-contract.md §`validate corpus` (scored count, valid/invalid, calibration count, sidecar counts); exit code matches the contract's lowest-non-zero rule.

### Implementation for User Story 5

- [ ] T060 [US5] Modify `src/dartwing_ocr/validator/cli.py` `validate corpus` subcommand to apply `corpus_pattern.is_scored_corpus_folder` per subfolder discovered, partition into scored vs calibration sets, and emit the reporting block specified in validator-cli-contract.md §`validate corpus`. Per-document artifact validation runs on both partitions; only scored partition contributes to scored aggregation counts. Exit code per the contract (lowest non-zero of all encountered failures).
- [ ] T061 [P] [US5] Update `docs/stage1-vendor-identity/labeling-guide.md` to add `tests/stage1_semantic_quality/` as a corpus root subject to identical PII/license pre-inclusion screening (Q44 / FR-026). Document that the Q25 synthetic US2 fixture carries no real PII by construction, but every future committed fixture under that root must pass the same screening.
- [ ] T062 [P] [US5] Update `docs/stage1-vendor-identity/dataset-layout.md` to reference the new `tests/stage1_semantic_quality/` root, the Q40 subfolder pattern `^inv_\d{3}_(easy|medium|hard)$`, and the calibration-folder exclusion rule (Q23 / MI-21). Cross-link to MI-20/MI-21.

**Checkpoint**: All five user stories are independently functional. Corpus governance is enforced — no calibration folder appears in scored output.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation updates, the contract-set amendment changelog entry, and full quickstart-walkthrough validation. These tasks have no functional code but are required by the constitution's Quality Gate #2 and by FR-031.

- [ ] T063 Append the v1.3.0 entry to `contracts/stage1_vendor_identity/AMENDMENTS.md` per R-022.10 / Q14 / FR-031: level-two heading `## v1.3.0 — 2026-05-23`, one-sentence summary, bulleted list of the four impacted schemas (`semantic_table_truth.schema.json` added, `evaluation_document.schema.json` extended, `evaluation_run_summary.schema.json` extended, `folder.schema.json` extended), justification cross-referencing feature 022 + Clarifications Q14, statement that v1.2.0 remains frozen and read-accessible. Cross-link to `specs/022-ocr-semantic-quality-gate/`.
- [ ] T064 [P] Update `docs/stage1-vendor-identity/schemas.md` to document the v1.3.0 delta: new `semantic_table_truth.json` sidecar shape; additive `semantic_table_quality` / `document_pass_fail.semantic_table_quality_passed` fields on `evaluation_document.json`; additive `semantic_table_quality_metrics` namespace on `evaluation_run_summary.json`; backward-compat read path for pre-feature reports.
- [ ] T065 [P] Promote `docs/stage1-vendor-identity/prd-ocr-semantic-quality-gate.md` from draft seed to active feature PRD; record the 44 Clarifications outcomes and the landed decisions; cross-link `specs/022-ocr-semantic-quality-gate/spec.md` and the OpenSpec change `openspec/changes/add-ocr-semantic-quality-gate/`.
- [ ] T066 [P] Update `contracts/stage1_vendor_identity/v1.3.0/README.md` to note the v1.3.0 delta and link to `AMENDMENTS.md`.
- [ ] T067 [P] Update repo-root `CLAUDE.md` (the "Recent Changes" section is already current; verify it covers feature 022; add the `tests/stage1_semantic_quality/` corpus root entry under Key References).
- [ ] T068 Run every walkthrough in `specs/022-ocr-semantic-quality-gate/quickstart.md` end-to-end on a clean checkout; record output snippets; confirm each scenario produces the documented result. Failing walkthroughs are bugs in either the implementation OR the quickstart; resolve before marking complete.
- [ ] T069 Run `python -m pytest tests/contract_tests/ tests/unit/ tests/integration/` and confirm all new tests (T011–T018, T023–T033, T043–T047, T054–T056, T058–T059) pass plus the pre-existing suite remains green (SC-006).
- [ ] T070 Verify FR↔task↔test coverage matrix per SC-010: every FR-001 through FR-034 (FR-034 added 2026-05-23 per security-clarify Q-SEC-7/B — air-gapped operation; maps to T031 enforcement test, no new implementation task) maps to at least one task in this file AND at least one test. Produce a coverage report at `specs/022-ocr-semantic-quality-gate/coverage-fr-task-test.md` (one row per FR with the task IDs and test file paths that cover it). Any FR with zero implementation tasks OR zero tests is a spec-or-tasks bug; resolve before declaring the feature complete.

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: No dependencies; runs first.
- **Phase 2 (Foundational)**: Depends on Phase 1; BLOCKS all user-story phases. T004 must complete before T005/T006/T019/T048/T049 (those edit files inside v1.3.0). T007/T008/T009/T010 are independent of T004 and each other.
- **Phase 3 (US1)**: Depends on Phase 2. T020 depends on T005/T019. T021 depends on T020. T022 depends on T021. T018 integration test depends on T020/T021/T022.
- **Phase 4 (US2)**: Depends on Phase 2 only — independent of US1 (the gate logic does not need the sidecar VALIDATOR; only the sidecar FILE). Can run in parallel with US1. T040 depends on T034/T035/T036/T037/T038/T039/T009. T041/T042 are fixture data with no code dependencies. T033 depends on T040 + T041 + T042.
- **Phase 5 (US3)**: Depends on Phase 4 (the writer in T051 calls `run_semantic_quality_gate` from T040). T048/T049 schema edits depend on T004. T050 depends on T007 + T039. T051 depends on T040 + T008 + T050. T052 depends on T050 + T008. T053 depends on T010.
- **Phase 6 (US4)**: Depends on Phase 5 (US4 tests assert behavior produced by US3's writer integration). T057 baseline capture can happen at any time on a pre-feature checkout — schedule it before Phase 2 lands functional changes, OR pull from the most recent pre-feature commit on `main`.
- **Phase 7 (US5)**: Depends on Phase 2 (T007 corpus_pattern) and Phase 5 (T050 metrics aggregator). T060 depends on T007. T058/T059 depend on T060.
- **Phase 8 (Polish)**: Depends on all user-story phases being complete. T069 depends on every test task. T070 requires the full task list and test surface.

### Within each user story

- Tests are written FIRST per FR-032 and must fail before the implementation tasks land.
- Within US2 the dependency chain is: normalize → body_ocr → anchor → currency → checks → report → gate entry point (T034 → T035 → T036 → T037 → T038 → T039 → T040). Fixture tasks T041/T042 are parallel to the code chain.
- US3 implementation order: schema edits (T048/T049) before serializer changes (T051/T052), because the serializers may load the schema for self-validation.

### Parallel opportunities

- **Phase 2**: T007, T008, T009, T010 are independent [P] tasks; T011, T012, T013, T014 are independent test [P] tasks.
- **Phase 3 US1**: T015, T016, T017, T018 are independent test [P] tasks; T020 and T019 can land in parallel because they touch different files.
- **Phase 4 US2**: T023–T033 are all independent test [P] tasks (different files). Implementation tasks T034, T035, T036, T037, T039 are independent code files [P]; T038/T040 are gated by the upstream chain. T041/T042 are independent of the code chain.
- **Phase 5 US3**: T043, T044, T045, T046, T047 are independent test [P] tasks. T048 and T049 are independent schema files [P]. T050 is independent of T051/T052.
- **Phase 6 US4**: T054, T055, T056 are independent test [P] tasks.
- **Phase 7 US5**: T058, T059 are independent test [P] tasks; T061, T062 are independent doc [P] tasks.
- **Phase 8 Polish**: T063, T064, T065, T066, T067 are independent files [P]; T068, T069, T070 run sequentially at the end.

---

## Parallel Example: User Story 2 implementation tasks

```bash
# After T034 lands, run these five module-creation tasks in parallel:
Task: T035 Create src/dartwing_ocr/evaluator/semantic_quality_body_ocr.py
Task: T036 Create src/dartwing_ocr/evaluator/semantic_quality_anchor.py
Task: T037 Create src/dartwing_ocr/evaluator/semantic_quality_currency.py
Task: T039 Create src/dartwing_ocr/evaluator/semantic_quality_report.py
Task: T041 Create tests/stage1_semantic_quality/inv_001_hard/preprocess_output.json
Task: T042 Create tests/stage1_semantic_quality/inv_001_hard/semantic_table_truth.json
```

```bash
# After Phase 2 lands, US1 and US2 can run in parallel (different developers):
Developer A: US1 tasks T015–T022
Developer B: US2 tasks T023–T042
```

---

## Implementation Strategy

### MVP First (US1 + US2 only)

1. Complete Phase 1 + Phase 2.
2. Complete Phase 3 (US1) — fixture authors can validate sidecars.
3. Complete Phase 4 (US2) — gate produces a deterministic verdict on the synthetic fixture.
4. **STOP and VALIDATE**: At this point the gate's core deterministic logic exists and is testable in isolation. The verdict is not yet visible in the evaluator's normal output — it's an in-memory object only. This is the "MVP slice that demonstrates the gate works without integrating it into the report surface."

### Incremental delivery

1. After MVP: Phase 5 (US3) makes the verdict visible in `evaluation_document.json` and aggregated in `evaluation_run_summary.json` — the gate becomes useful to reviewers.
2. Phase 6 (US4) is the hard release gate — vendor-identity baseline byte-identical, value-domain end-to-end. **Block release on T054 passing.**
3. Phase 7 (US5) hardens corpus governance — protects scored corpus integrity.
4. Phase 8 lands the documentation amendment trail and runs the quickstart walkthroughs.

### Critical-path note

The FR↔task↔test coverage check at T070 (per SC-010 / FR-032) is the final completeness gate. If T070 surfaces an uncovered FR, the resolution is to add the missing task or test back into the appropriate user-story phase before declaring the feature complete — not to weaken the FR.

---

## Notes

- All gate code is CPU-only and Paddle-free per MI-1. No new pinned dependency is added.
- All newly-written semantic outputs go through `stable_json.dump_stable` per MI-16 for byte-identical reproducibility (SC-007).
- Vendor-identity fields on `evaluation_document.json` and `evaluation_run_summary.json` are byte-identical before and after the feature lands per MI-22; T054 / T057 are the measurable enforcement.
- The synthetic US2 fixture under `tests/stage1_semantic_quality/inv_001_hard/` contains NO `source.pdf` per Q25 / MI-25 — adding one would violate the fixture-isolation contract.
- Calibration folders (e.g. `inv_024_hard_degraded_body`) remain calibration evidence only at landing; promotion to scored corpus data is governed by FR-026 and requires the full amendment path (out of scope for this feature).
- Runtime pipeline integration is explicitly out of scope per Q3 / FR-033 — the semantic verdict is evaluator/harness/report-only at landing.
