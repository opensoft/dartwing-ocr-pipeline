---
description: "Tasks for feature 007-evaluator — Stage 1 Vendor-Identity Evaluator & Reporting"
---

# Tasks: Evaluator & Reporting (Stage 1 Vendor-Identity)

**Input**: Design documents from `specs/007-evaluator/`
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/module-api.md`, `quickstart.md`

**Tests**: Included. Each user story in `spec.md` carries an Independent Test paragraph and concrete Acceptance Scenarios; those are the authoritative test targets. All tests run offline with `pytest-socket` blocking network.

**Organization**: Tasks are grouped by user story. US1 + US2 form the MVP (both P1). US3 + US4 are P2 quality layers that extend the modules established in US1/US2. US5 is P3 (human-readable report).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1…US5). Setup, Foundational, and Polish phases have no story label.
- Every task cites an exact file path under `src/dartwing_ocr/evaluator/` or `tests/evaluator_tests/`.

## Path Conventions

Single-project Python library + CLI co-located with the existing `dartwing_ocr.validator` subpackage. All new code lives under `src/dartwing_ocr/evaluator/` and `tests/evaluator_tests/`; contract tests extend `tests/contract_tests/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffold the evaluator subpackage and test tree.

- [X] T001 Create package skeleton at `src/dartwing_ocr/evaluator/` with empty modules per `plan.md` §Project Structure: `__init__.py`, `__main__.py`, `cli.py`, `document.py`, `corpus.py`, `normalize.py`, `compare.py`, `gates.py`, `scoring.py`, `report.py`, `io.py`, `schema.py`
- [X] T002 [P] Create test tree at `tests/evaluator_tests/` with `__init__.py` and empty `fixtures/` subdirectory
- [X] T003 [P] Verify `pyproject.toml` package discovery picks up `dartwing_ocr.evaluator` (same pattern as `dartwing_ocr.validator`); add an entry only if `python -m dartwing_ocr.evaluator --help` does not resolve after T001

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Constants, typed dataclasses, exceptions, JSON I/O, schema loader wrapper, and CLI skeleton. MUST complete before any user story begins.

**Scope**: Only the shared surface used by every story — no normalization rules, no comparators, no gate logic yet. Those belong to their owning stories.

- [X] T004 Define scoring constants in `src/dartwing_ocr/evaluator/scoring.py` per `data-model.md` §1: `ResultLabel` (str, Enum), `RESULT_VALUES`, `SCORED_FIELDS` (18-tuple in the canonical order from `research.md` §11), `FIELD_WEIGHTS` (sum = 100), `CONTRACT_SET_VERSION = "1.0.0"`, `GATE_THRESHOLD = 0.85`, `GATE_EPSILON = 1e-9`. Add module-level asserts `set(FIELD_WEIGHTS) == set(SCORED_FIELDS)` and `sum(FIELD_WEIGHTS.values()) == 100`
- [X] T005 [P] Define exception hierarchy in `src/dartwing_ocr/evaluator/exceptions.py` per `contracts/module-api.md` §Public exceptions: `EvaluatorError` base, `ContractSetVersionMismatchError`, `DocumentIdMismatchError`, `SchemaValidationError`, `EmptyCorpusError`
- [X] T006 [P] Implement schema loader wrapper in `src/dartwing_ocr/evaluator/schema.py` reusing `dartwing_ocr.validator.loader.load_contract_set` and `validate_artifact` per `research.md` §15; expose `load_evaluation_document_schema()`, `load_evaluation_run_summary_schema()`, `load_expected_schema()`, `load_final_payload_schema()`; translate `jsonschema.ValidationError` into `SchemaValidationError`
- [X] T007 [P] Implement deterministic JSON I/O in `src/dartwing_ocr/evaluator/io.py` per `research.md` §10: `read_json(path)`, `write_json(path, obj)` using `json.dumps(obj, indent=2, ensure_ascii=False, separators=(",", ": "), sort_keys=False)` + UTF-8 encoding + single trailing `\n`; plus a `round_floats(obj, ndigits=6)` recursive helper applied before every write
- [X] T008 Define `FieldResult` dataclass in `src/dartwing_ocr/evaluator/compare.py` per `data-model.md` §2 (`frozen=True, slots=True`), with `__post_init__` validation for the null-on-both-sides / one-side-null / boolean / tax-ID label constraints
- [X] T009 Define `ComparisonSummary` dataclass in `src/dartwing_ocr/evaluator/scoring.py` per `data-model.md` §3, with `__post_init__` enforcing `matched + mismatched + missing_pred + unexpected_pred + partial_count == applicable` and `field_accuracy == round((matched + 0.5 × partial_count) / applicable, 6)` when `applicable > 0`
- [X] T010 Define `DocumentPassFail` dataclass in `src/dartwing_ocr/evaluator/gates.py` per `data-model.md` §4
- [X] T011 Define `DocumentEvaluation` dataclass in `src/dartwing_ocr/evaluator/document.py` per `data-model.md` §5 with invariant `tuple(f.field_name for f in field_results) == SCORED_FIELDS`; serializer drops `document_score` and `folder_path`
- [X] T012 [P] Define run-summary dataclasses (`DifficultyStats`, `OverallMetrics`, `ConsensusMetrics`, `DocumentListEntry`, `RunSummary`) in `src/dartwing_ocr/evaluator/corpus.py` per `data-model.md` §§6–10, enforcing `by_difficulty` key set, `len(documents) == document_count`, and sorted-by-`document_id` ordering
- [X] T013 [P] Define pydantic outcome models (`DocumentEvaluationOutcome`, `RunSummaryOutcome`) in `src/dartwing_ocr/evaluator/outcomes.py` per `data-model.md` §11
- [X] T014 Wire CLI skeleton in `src/dartwing_ocr/evaluator/cli.py` and `src/dartwing_ocr/evaluator/__main__.py` per `contracts/module-api.md` §CLI contract: `argparse` with `evaluate {document,corpus}` subcommands, positional `<folder>` / `<root>`, optional `--contract-set-version` on both subcommands, `--json`/`--text` (default `--text`) on `evaluate document` only, `--no-lazy` on `evaluate corpus` only; exit codes `0` clean, `2` usage, `3` hard error; handler callbacks left as `NotImplementedError` for story phases to fill in
- [X] T015 [P] Re-export the public surface from `src/dartwing_ocr/evaluator/__init__.py` per `contracts/module-api.md` §Public dataclasses and enums: `ResultLabel`, `FieldResult`, `ComparisonSummary`, `DocumentPassFail`, `DocumentEvaluation`, `DifficultyStats`, `OverallMetrics`, `ConsensusMetrics`, `DocumentListEntry`, `RunSummary`, `DocumentEvaluationOutcome`, `RunSummaryOutcome`, and every exception from T005. `evaluate_document` / `evaluate_corpus` are re-exported by their owning story phases

**Checkpoint**: Foundation ready — user story implementation can now begin.

---

## Phase 3: User Story 1 — Per-Document Evaluator (Priority: P1) 🎯 MVP

**Goal**: `python -m dartwing_ocr.evaluator evaluate document <folder>` reads `expected.json` + `final_structured_payload.json`, compares them field-by-field, and writes a schema-valid `evaluation_document.json` into the same folder. Implements the baseline comparison path; US3 later replaces the minimal normalization/gate logic with the full rubric.

**Independent Test**: Run the evaluator against a hand-authored per-document folder covering US1 AC#1–#8; verify `evaluation_document.json` is written, validates against `contracts/stage1_vendor_identity/v1.0.0/evaluation_document.schema.json`, propagates `document_id` / `difficulty` / `challenge_tags`, and all six result labels can be produced.

### Tests for User Story 1

- [X] T016 [P] [US1] Author all-match fixture at `tests/evaluator_tests/fixtures/all_match/` (US1 AC#2) — one `expected.json` + `final_structured_payload.json` where every scored field matches after normalization and `overall_passed` is `True`
- [X] T017 [P] [US1] Author label-coverage fixture at `tests/evaluator_tests/fixtures/label_coverage/` (US1 AC#3–#6) with one example each of: company-name normalization (`"Acme Widgets Inc."` vs `"acme widgets  inc."`), `tax_ids.ein` expected non-null / prediction null (AC#4), `website` expected null / prediction non-null (AC#5), and all four tax-ID sub-fields null on both sides (AC#6)
- [X] T018 [P] [US1] Author hard-error fixture pairs under `tests/evaluator_tests/fixtures/hard_errors/`: `missing_final_payload/`, `contract_set_drift/` (inputs carry `contract_set_version = "0.9.0"`), and `document_id_mismatch/` (each surfaces one `EvaluatorError` subclass from T005)
- [X] T019 [P] [US1] Add `tests/evaluator_tests/test_document_evaluator.py` covering US1 AC#1–#7: `evaluation_document.json` is written and schema-valid, `field_results` ordered by `SCORED_FIELDS`, `comparison_summary` counts/identity hold, and hard errors raise the typed exception while leaving no output on disk. Include an input-immutability assertion covering `FR-019`: capture SHA-256 hashes of `expected.json` and `final_structured_payload.json` before and after every `evaluate_document` call (both on the clean-completion path and on every hard-error path) and assert the hashes are unchanged
- [X] T020 [P] [US1] Add `tests/evaluator_tests/test_determinism.py::test_document_byte_identical` covering US1 AC#8: run `evaluate_document` twice on the all-match fixture and assert the two `evaluation_document.json` files are byte-identical (per-document eval has no `run_id` — nothing is allowed to vary)
- [X] T021 [P] [US1] Add `tests/contract_tests/test_evaluation_artifacts.py` asserting every `evaluation_document.json` written by the US1 fixtures validates against `contracts/stage1_vendor_identity/v1.0.0/evaluation_document.schema.json`

### Implementation for User Story 1

- [X] T022 [US1] Implement dotted-key extraction in `src/dartwing_ocr/evaluator/compare.py`: `extract_field(payload: dict, dotted_name: str) -> Any` that walks `SCORED_FIELDS` keys (`"company_name.value"`, `"address.city"`, `"tax_ids.ein"`, …) and returns the raw value or `None` when any intermediate key is missing
- [X] T023 [US1] Implement baseline comparator in `src/dartwing_ocr/evaluator/compare.py`: `compare_field(field_name, expected, actual) -> FieldResult` handling null-on-both-sides → `NOT_APPLICABLE`, one-side-null cases (`MISSING_PREDICTION` / `UNEXPECTED_PREDICTION`), and strict-equal vs post-normalize-equal path. Partial-match branches and the full rubric are deferred to US3; for US1 emit only `MATCH` / `MISMATCH` beyond the null handling, using the minimal normalizer from T024
- [X] T024 [US1] Implement minimal normalization in `src/dartwing_ocr/evaluator/normalize.py` sufficient for US1 AC#3: `normalize_company(value)` (lowercase, trim, collapse internal whitespace, strip punctuation) and `normalize_default(value)` (lowercase + trim). Full rule set arrives in US3
- [X] T025 [US1] Implement `build_comparison_summary(field_results) -> ComparisonSummary` in `src/dartwing_ocr/evaluator/scoring.py` per `FR-011`: `matched_field_count` counts strict `MATCH` only; `field_accuracy = (matched + 0.5 × partial_count) / applicable` with `partial_count` derived from `field_results`
- [X] T026 [US1] Implement `compute_document_score(field_results) -> float` in `src/dartwing_ocr/evaluator/scoring.py` per `FR-007`: `sum(RESULT_VALUES[fr.result] × FIELD_WEIGHTS[fr.field_name]) / sum(FIELD_WEIGHTS[fr.field_name] for fr in applicable_fields)`; `NOT_APPLICABLE` fields excluded from numerator AND denominator; return `0.0` when every field is `NOT_APPLICABLE`
- [X] T027 [US1] Implement baseline pass gates in `src/dartwing_ocr/evaluator/gates.py`: `vendor_identity_passed(field_results)` per `FR-008` (for US1, use the simple "company_name.value matches AND ≥2 of {address.city-state-postal, any tax_id, website, phone, email}" slot reading from Q3 clarification — US3 tightens the slot semantics), `review_routing_passed(field_results)` per `FR-009`, `overall_passed(vendor_identity_passed, review_routing_passed, document_score)` per `FR-010` using `document_score + GATE_EPSILON >= GATE_THRESHOLD`
- [X] T028 [US1] Implement document orchestration in `src/dartwing_ocr/evaluator/document.py`: `evaluate_document(folder, *, contract_set_version=None) -> DocumentEvaluationOutcome` per `contracts/module-api.md`. Steps: read both inputs via `io.read_json`; schema-validate each via `schema.py`; enforce `contract_set_version == "1.0.0"` and raise `ContractSetVersionMismatchError` on drift (`FR-013`); raise `DocumentIdMismatchError` when inputs disagree; build `field_results` in `SCORED_FIELDS` order; assemble `DocumentEvaluation`; schema-validate output; write `evaluation_document.json` via `io.write_json`. On any raised exception, do NOT write output (`FR-020`)
- [X] T029 [US1] Wire the `evaluate document` CLI branch in `src/dartwing_ocr/evaluator/cli.py` to call `evaluate_document`; `--text` prints a short summary (field accuracy, pass gates, top failing fields) and `--json` dumps the `DocumentEvaluationOutcome` as JSON. Return exit `3` on `EvaluatorError` / `FileNotFoundError` with the offending path on stderr; return `0` on clean completion even if the document fails its gates (`FR-023`)
- [X] T030 [US1] Re-export `evaluate_document` from `src/dartwing_ocr/evaluator/__init__.py`

**Checkpoint**: A developer can run `python -m dartwing_ocr.evaluator evaluate document <folder>` on any fixture and get a schema-valid, deterministic per-document artifact. US1 is independently testable and ready for demo.

---

## Phase 4: User Story 2 — Corpus Aggregator & Run Summary (Priority: P1)

**Goal**: `python -m dartwing_ocr.evaluator evaluate corpus <root>` walks every per-document folder, lazily evaluates any folder missing `evaluation_document.json` (default) or hard-fails in `--no-lazy` mode, writes `evaluation_run_summary.json` at the corpus root, and returns a deterministic `RunSummaryOutcome`. The Markdown report is added in US5; this story delivers the machine JSON only.

**Independent Test**: Run the command against a staged 20-document corpus spanning all four difficulty buckets; verify the summary validates against `contracts/stage1_vendor_identity/v1.0.0/evaluation_run_summary.schema.json`, `by_difficulty` contains exactly `{easy, medium, hard, missing_name}`, `documents[]` is sorted by `document_id`, and the hand-computed aggregate equals `overall_metrics` within 6-decimal tolerance.

### Tests for User Story 2

- [X] T031 [US2] Author 20-document corpus fixture at `tests/evaluator_tests/fixtures/corpus_20/` (5 easy / 5 medium / 5 hard / 5 missing_name) per `research.md` §16; each folder contains only `expected.json` + `final_structured_payload.json` (not `evaluation_document.json`) so lazy eval is exercised; include a deliberate mix of passing and failing documents matching US2 AC#2 and US5 AC#2
- [X] T032 [P] [US2] Author strict-mode fixture at `tests/evaluator_tests/fixtures/corpus_prebuilt_3/` — 3 folders each pre-populated with a valid `evaluation_document.json` so `--no-lazy` completes without invoking `evaluate_document`
- [X] T033 [P] [US2] Author hard-error corpus fixture at `tests/evaluator_tests/fixtures/corpus_bad_input/` — 3 folders where one has an unreadable `expected.json` (to drive the US2 AC#8 abort path)
- [X] T034 [P] [US2] Add `tests/evaluator_tests/test_corpus_aggregator.py` covering US2 AC#1–#7: schema validation, `document_count`, `overall_metrics` equality with hand-computed aggregate, `by_difficulty` key-set + sum identity, `by_field` dotted keys + `[0.0, 1.0]` range, single-voter `consensus_metrics`, `documents[]` sorted ordering
- [X] T035 [P] [US2] Add `tests/evaluator_tests/test_corpus_aggregator.py::test_lazy_eval` covering US2 AC#8 lazy path: start with `corpus_20` (no `evaluation_document.json`), run corpus eval, assert each folder gains a valid `evaluation_document.json` and the run summary is written
- [X] T036 [P] [US2] Add `tests/evaluator_tests/test_corpus_aggregator.py::test_hard_error_no_partial_summary` against `corpus_bad_input/`: expect `EvaluatorError`, verify no `evaluation_run_summary.json` exists afterward (`FR-020`)
- [X] T037 [P] [US2] Add `tests/evaluator_tests/test_corpus_aggregator.py::test_no_lazy_mode` against `corpus_prebuilt_3/`: `--no-lazy` completes; a variant that deletes one folder's `evaluation_document.json` exits `3`
- [X] T038 [P] [US2] Add `tests/evaluator_tests/test_determinism.py::test_run_summary_byte_identical` — run `evaluate_corpus` twice on `corpus_20/`, assert `diff <(jq 'del(.run_id)' a.json) <(jq 'del(.run_id)' b.json)` is empty (quickstart §5, SC-005)
- [X] T039 [P] [US2] Extend `tests/contract_tests/test_evaluation_artifacts.py` to validate every `evaluation_run_summary.json` against its frozen schema

### Implementation for User Story 2

- [X] T040 [US2] Implement `list_document_folders(root) -> list[Path]` in `src/dartwing_ocr/evaluator/corpus.py`: scan `root` for immediate subdirectories containing `expected.json`; sort ascending by folder name; raise `EmptyCorpusError` when the list is empty
- [X] T041 [US2] Implement `_ensure_document_evaluation(folder, *, lazy, contract_set_version)` helper in `corpus.py` per `research.md` §13: if `evaluation_document.json` exists and schema-validates, read-and-reuse it; else if `lazy=True` call `evaluate_document`; else raise `FileNotFoundError` so the CLI surfaces exit `3`. Any hard error aborts the run without writing the summary
- [X] T042 [US2] Implement difficulty aggregation in `corpus.py`: `build_by_difficulty(evaluations) -> dict[str, DifficultyStats]` emitting exactly the four keys `easy`/`medium`/`hard`/`missing_name` in that fixed order (US2 AC#3); each `DifficultyStats.field_accuracy` and `.overall_document_pass_rate` rounded to 6 decimals
- [X] T043 [US2] Implement field aggregation in `corpus.py`: `build_by_field(evaluations) -> dict[str, float]` per `research.md` §12 — corpus-wide unweighted accuracy `(match + 0.5 × partial) / applicable` keyed by dotted `SCORED_FIELDS` names; result values rounded to 6 decimals (the `(match + 0.5 × partial) / applicable` formula is mathematically bounded to `[0.0, 1.0]`, so no explicit clamp is applied)
- [X] T044 [US2] Implement overall-metrics aggregation in `corpus.py`: `build_overall_metrics(evaluations) -> OverallMetrics` per `FR-015` with `field_accuracy`, `vendor_identity_pass_rate`, `review_routing_pass_rate`, `overall_document_pass_rate` rounded to 6 decimals
- [X] T045 [US2] Implement stage-1 consensus metrics in `corpus.py`: `build_consensus_metrics(document_count) -> ConsensusMetrics` with `single_voter_baseline_runs == document_count`, `majority_vote_documents == 0`, `split_decision_documents == 0`, ensemble-rate optionals omitted (`FR-016`)
- [X] T046 [US2] Implement documents-list builder in `corpus.py`: `build_documents_list(evaluations) -> tuple[DocumentListEntry, ...]` sorted ascending by `document_id` (`FR-017`)
- [X] T047 [US2] Implement `generate_run_id() -> str` in `corpus.py` per `research.md` §9: `"run_" + UTC-ISO-8601-with-microseconds + "Z_" + uuid4().hex[:8]` (collision-safe per Edge Cases → Run ID collision)
- [X] T048 [US2] Implement `evaluate_corpus(root, *, contract_set_version=None, lazy=True) -> RunSummaryOutcome` in `corpus.py`: discover folders, ensure per-document evaluations, assemble `RunSummary`, schema-validate the output via `schema.py`, write `evaluation_run_summary.json` at `root` via `io.write_json`. The Markdown side-effect is deferred to US5
- [X] T049 [US2] Wire the `evaluate corpus` CLI branch in `cli.py` to call `evaluate_corpus(root, lazy=not args.no_lazy)`; corpus mode has no `--json`/`--text` flags (stdout is always Markdown, added in US5; the machine-consumable surface is `<root>/evaluation_run_summary.json` on disk per `contracts/module-api.md`); return exit `3` on any `EvaluatorError` / `FileNotFoundError` with the offending folder on stderr
- [X] T050 [US2] Re-export `evaluate_corpus` from `src/dartwing_ocr/evaluator/__init__.py`

**Checkpoint**: MVP complete — `evaluate document` and `evaluate corpus` both work end-to-end with deterministic, schema-valid outputs. Markdown report is still deferred.

---

## Phase 5: User Story 3 — Full Scoring Rubric (Priority: P2)

**Goal**: Replace US1's minimal normalizer/comparator with the complete `scoring.md` rubric: every normalization rule in `research.md` §§1–7, every permitted `partial_match` path, and the full secondary-identifier slot semantics from the Q3 clarification.

**Independent Test**: Run the evaluator against fixtures exercising every rule in `research.md` §§1–7; confirm each field is classified per the rubric. Separately, run it against a fixture where `document_score = 0.87` but `review_routing_passed = False`; verify `overall_passed = False`, confirming gates are conjunctive and not short-circuited by the threshold alone.

### Tests for User Story 3

- [X] T051 [P] [US3] Author normalization fixtures at `tests/evaluator_tests/fixtures/normalization_cases/` covering US3 AC#1 (state `"California"` vs `"CA"`), AC#3 (website `"https://www.example.com/"` vs `"example.com"`), AC#5 (email `"Accounts@Example.COM"` vs `"accounts@example.com"`), plus one case per rule in `research.md` §§1–7
- [X] T052 [P] [US3] Author partial-match fixtures at `tests/evaluator_tests/fixtures/partial_match_cases/` covering US3 AC#2 (ZIP+4 `"94110-1234"` vs `"94110"`), AC#4 (phone with extension `"(415) 555-0198 ext. 203"` vs `"4155550198"`), imperfectly normalized street suffix (US3 Independent Test), and a company-name suffix-stripped case (`"Acme Widgets Inc."` vs `"Acme Widgets Incorporated"` → `MATCH`; `"Acme Widgets"` vs `"Acme Widget Co. of California"` → `PARTIAL_MATCH`)
- [X] T053 [P] [US3] Author gate fixtures at `tests/evaluator_tests/fixtures/secondary_identifier_gates/` — one where `document_score >= 0.85` but `vendor_identity_passed = False` (AC#7); one where `company_name` matches but fewer than 2 secondary slots match (AC#8); one where `manual_review_required = True/False` prediction mismatch drives `review_routing_passed = False` (AC#6)
- [X] T054 [P] [US3] Add `tests/evaluator_tests/test_normalize.py` with one positive and one negative case per rule in `research.md` §§1–7 (state, phone, website, postal, tax_id, street, company)
- [X] T055 [P] [US3] Add `tests/evaluator_tests/test_compare.py` covering every `ResultLabel` trigger path and the `FR-006` partial-match exclusions (booleans never `PARTIAL_MATCH`; `review_reason` never `PARTIAL_MATCH`; all four tax-ID sub-fields never `PARTIAL_MATCH`)
- [X] T056 [P] [US3] Add `tests/evaluator_tests/test_gates.py` covering US3 AC#6 (boolean `manual_review_required` mismatch fails `review_routing_passed`), AC#7 (threshold cannot override failed hard gate), AC#8 (at-least-2 secondary-identifier conjunction with company-name matching), and the exact address-slot semantics from Q3 (address counts iff `city` AND `state` AND `postal_code` all match/acceptable-partial; `street_1`/`street_2`/`country` do NOT contribute to the address slot)
- [X] T057 [P] [US3] Add `tests/evaluator_tests/test_scoring.py` asserting the weight invariants (`sum(FIELD_WEIGHTS.values()) == 100`, `set(FIELD_WEIGHTS) == set(SCORED_FIELDS)`) and `compute_document_score` against two hand-computed fixtures (one all-match, one mixed-label)

### Implementation for User Story 3

- [X] T058 [US3] Extend `src/dartwing_ocr/evaluator/normalize.py` with the full state-abbreviation map per `research.md` §1: hard-coded dict of 50 US states + DC + 5 US territories (PR, GU, AS, MP, VI) mapping 2-letter code ↔ full name; case-insensitive compare
- [X] T059 [US3] Extend `normalize.py` with `normalize_phone(value)` per `research.md` §2: strip every non-digit; return `(digits, had_extension_marker)` tuple so the comparator can emit `PARTIAL_MATCH` when expected included `ext`/`x`/`#` and prediction dropped it
- [X] T060 [US3] Extend `normalize.py` with `normalize_website(value)` per `research.md` §3: lowercase → strip `http(s)://` → strip leading `www.` → strip single trailing `/` → strip query+fragment; preserve path segments
- [X] T061 [US3] Extend `normalize.py` with `normalize_postal(value)` per `research.md` §4: trim; classify as `MATCH` on exact equality, `PARTIAL_MATCH` when one side is the 5-digit prefix of the other, otherwise `MISMATCH`
- [X] T062 [US3] Extend `normalize.py` with `normalize_tax_id(value)` per `research.md` §5: strip spaces, hyphens, dots; uppercase (for country-letter VAT prefixes); `MATCH`/`MISMATCH` only — never `PARTIAL_MATCH`
- [X] T063 [US3] Extend `normalize.py` with `normalize_street(value)` per `research.md` §6: fixed suffix map (`St/Street`, `Rd/Road`, …) + directional prefix map (`N/North`, `NE/Northeast`, …) + lowercase + collapse whitespace + strip punctuation; plus a token-overlap helper returning ≥0.7 overlap when street numbers match → `PARTIAL_MATCH`
- [X] T064 [US3] Extend `normalize.py` with `normalize_company(value)` upgraded per `research.md` §7: strip `Inc`/`LLC`/`Corp`/`Ltd`/`Co.` legal-form suffixes; lowercase + trim + collapse whitespace + strip non-alphanumeric; plus a token-subset+≥3-char-overlap helper for the `PARTIAL_MATCH` branch
- [X] T065 [US3] Extend `normalize.py` with `normalize_email(value)` per `scoring.md`: lowercase + trim. `MATCH`/`MISMATCH` only
- [X] T066 [US3] Route each scored field to its normalizer in `src/dartwing_ocr/evaluator/compare.py`: `compare_field` dispatches on `field_name` via a fixed map; emit `PARTIAL_MATCH` only in cases permitted by `scoring.md` and `FR-006` (booleans/`review_reason`/tax_ids never produce `PARTIAL_MATCH`); strict-match case delegates to the field's `normalize_*`
- [X] T067 [US3] Tighten `vendor_identity_passed` in `src/dartwing_ocr/evaluator/gates.py` to the full `FR-008` rule per Q3 clarification: conjunction of (`company_name.value` match OR acceptable-partial) AND `company_name.present` match AND `company_name.inferred` match AND at-least-2 of the five secondary slots, where:
  - **address slot** = `address.city` AND `address.state` AND `address.postal_code` each resolve to `MATCH` or acceptable `PARTIAL_MATCH` (`street_1`/`street_2`/`country` excluded from the slot)
  - **tax-ID slot** = at least one of `tax_ids.ein`/`.state_tax_id`/`.vat_id`/`.other_tax_id` is strict `MATCH` (tax IDs never partial per `FR-006`)
  - **website/phone/email slots** = that field resolves to `MATCH` or acceptable `PARTIAL_MATCH`
  Each slot contributes at most 1 toward the "at least 2" threshold

**Checkpoint**: `evaluate_document` and `evaluate_corpus` now classify every field per `scoring.md`. US1/US2 acceptance scenarios that depend on normalization (US1 AC#3) and partial matches now pass strictly rather than by accident.

---

## Phase 6: User Story 4 — Missing-Name Invariants (Priority: P2)

**Goal**: Enforce the four-rule missing-name invariant as a hard gate on `review_routing_passed` (and therefore `overall_passed`) for any document in the `missing_name` difficulty bucket. Matching the inferred value alone is never sufficient.

**Independent Test**: Run the evaluator against a valid missing-name fixture (all four invariants satisfied) → `overall_passed == True`. Then run against four variants, each violating exactly one invariant → each fails `review_routing_passed` and therefore `overall_passed`.

### Tests for User Story 4

- [X] T068 [P] [US4] Author fixture at `tests/evaluator_tests/fixtures/missing_name_valid/` — `expected.json` in the `missing_name` bucket with a prediction satisfying all four invariants (`company_name.present = false`, `company_name.inferred = true`, `manual_review_required = true`, `review_reason = "company_name_inferred"`) per US4 AC#1
- [X] T069 [P] [US4] Author 4 violation fixtures at `tests/evaluator_tests/fixtures/missing_name_violations/`: `present_true/`, `inferred_false/`, `manual_review_false/`, `review_reason_wrong/` — each violating exactly one invariant while matching the inferred `value` so the test proves value-match alone cannot save the document (US4 AC#2, AC#3, Independent Test)
- [X] T070 [P] [US4] Add `tests/evaluator_tests/test_gates.py::test_missing_name_invariants` covering US4 AC#1 (all-valid → `review_routing_passed = True`), AC#2 (`present = True` → `vendor_identity_passed = False` AND `overall_passed = False` regardless of `value` matching), AC#3 (non-canonical `review_reason` → `review_routing_passed = False`)
- [X] T071 [P] [US4] Add `tests/evaluator_tests/test_corpus_aggregator.py::test_missing_name_bucket_pass_rate` covering US4 AC#4: extend the `corpus_20/` missing_name bucket so one document violates an invariant; assert `by_difficulty.missing_name.overall_document_pass_rate` counts it as failing

### Implementation for User Story 4

- [X] T072 [US4] Enforce `FR-012` in `src/dartwing_ocr/evaluator/gates.py`: when the evaluated document's `expected.difficulty == "missing_name"`, `review_routing_passed` requires all four invariants to hold in the prediction (`company_name.present == false`, `company_name.inferred == true`, `manual_review_required == true`, `review_reason == "company_name_inferred"`). Thread `difficulty` through the gate API (e.g., add a `missing_name: bool` kwarg to `review_routing_passed`) so the invariant path is a single, testable branch

**Checkpoint**: The stage-1 constitution §IV guarantee (missing-name handling is never lax) is mechanically enforced. All 5 missing-name documents in the corpus are graded under the stricter gate.

---

## Phase 7: User Story 5 — Human-Readable Markdown Report (Priority: P3)

**Goal**: `evaluate corpus` writes `evaluation_run_summary.md` at the corpus root alongside the JSON and streams byte-identical content to stdout per Q4 clarification / `FR-021`. Uses the deterministic layout pinned in `research.md` §14.

**Independent Test**: Run the corpus-level evaluator against `corpus_20/`; verify the Markdown file exists, names the four headline metrics with numeric values, contains the by-difficulty table in fixed order, lists failing documents with id/difficulty/one-line reason, falls back to `_All documents passed._` on a zero-failure run, and stdout capture equals the on-disk file byte-for-byte.

### Tests for User Story 5

- [X] T073 [P] [US5] Add `tests/evaluator_tests/test_report.py::test_headline_metrics` covering US5 AC#1 — all four headline metrics (`overall_document_pass_rate`, `vendor_identity_pass_rate`, `review_routing_pass_rate`, `field_accuracy`) rendered with their numeric values
- [X] T074 [P] [US5] Add `tests/evaluator_tests/test_report.py::test_failing_documents_list` covering US5 AC#2 — each failing-document entry includes `document_id`, difficulty bucket, and a short reason (e.g., `"company_name mismatch; review_reason wrong"`)
- [X] T075 [P] [US5] Add `tests/evaluator_tests/test_report.py::test_zero_failures_fallback` covering US5 AC#3 — running against an all-passing corpus renders `_All documents passed._` in place of the failing-documents list
- [X] T076 [P] [US5] Add `tests/evaluator_tests/test_report.py::test_deterministic_ordering` covering US5 AC#4 — re-rendering from the same `RunSummary` produces byte-identical output; failing docs sorted ascending by `document_id`
- [X] T077 [P] [US5] Add `tests/evaluator_tests/test_report.py::test_md_file_matches_stdout` covering `FR-021` — after running `evaluate_corpus`, the on-disk `evaluation_run_summary.md` equals the captured stdout stream byte-for-byte (modulo trailing-newline convention documented in `io.py`)

### Implementation for User Story 5

- [X] T078 [US5] Implement `render_run_summary(run_summary, *, document_evaluations=()) -> str` in `src/dartwing_ocr/evaluator/report.py` per `research.md` §14: headline section (Run ID, Document count, four pass-rate/accuracy bullets formatted to 3 decimals), `## By difficulty` Markdown table with rows in fixed order `easy → medium → hard → missing_name`, `## Failing documents` section listing each failing document sorted ascending by `document_id` as `- {doc_id} ({difficulty}) — {reason}`, or `_All documents passed._` when there are none. Signature note: the function takes the `RunSummary` plus an optional tuple of `DocumentEvaluation`s so the failing-doc lines can render `(difficulty) — reason`; `RunSummary.documents` alone lacks `difficulty` and `field_results`
- [X] T079 [US5] Implement `summarize_failure(doc_evaluation: DocumentEvaluation) -> str` in `report.py` — a deterministic one-line reason derived from `document_pass_fail` plus the top failing `field_results` sorted by `FIELD_WEIGHTS` descending (ties broken by `SCORED_FIELDS` order); include at most 2 failing fields per document
- [X] T080 [US5] Wire Markdown emission into `src/dartwing_ocr/evaluator/corpus.py`: inside `evaluate_corpus`, after writing the JSON, compute `md = render_run_summary(summary)`, write it to `evaluation_run_summary.md` at `root` via a small `io.write_text(path, text)` helper (UTF-8, single trailing `\n`); store the `md` bytes on `RunSummaryOutcome.md_output_path`
- [X] T081 [US5] Update the `evaluate corpus` CLI branch in `cli.py` to print the rendered Markdown to stdout unconditionally at the end of every corpus run (corpus mode has no `--json`/`--text` flags per `contracts/module-api.md`; the canonical Markdown is the only stdout surface, and the machine-readable `evaluation_run_summary.json` is already on disk at `<root>/evaluation_run_summary.json`); verify byte-equality with the on-disk `.md` file in T077

**Checkpoint**: A developer can answer "did the run pass overall? which documents failed?" by reading stdout or the `.md` file, without opening any JSON (SC-008).

---

## Phase 8: Polish & Cross-Cutting

**Purpose**: Reconcile quickstart drift, add end-to-end contract coverage, exercise the CLI exit-code matrix, and run the full test suite under `pytest-socket`.

- [X] T082 [P] Extend `tests/contract_tests/test_evaluation_artifacts.py` with an end-to-end run against `corpus_20/` asserting every artifact (`evaluation_document.json` per folder + `evaluation_run_summary.json` + `evaluation_run_summary.md` structure) validates / renders cleanly
- [X] T083 [P] Add `tests/evaluator_tests/test_cli.py` exercising `python -m dartwing_ocr.evaluator --help`, both subcommands' `--help`, and the exit-code matrix: `0` clean, `2` usage (bad flag / missing positional), `3` hard error (missing `expected.json`, drifted `contract_set_version` including an explicit `--contract-set-version 2.0.0` rejection case, mismatched `document_id`, and an `--no-lazy` run against a folder missing `evaluation_document.json`). For every exit-`3` case capture stderr via `subprocess.run(..., capture_output=True)` and assert the offending file or folder path appears verbatim in the stderr text (`SC-007`)
- [X] T084 [P] Run the `specs/007-evaluator/quickstart.md` walkthrough end-to-end against `corpus_20/` and reconcile any drift between the quickstart and the implementation (exit codes, CLI flag names, file paths)
- [X] T085 [P] Verify `CLAUDE.md` "Active Technologies" and "Recent Changes" sections are current for 007-evaluator (auto-updated by `update-agent-context.sh` during `/speckit.plan`; check no stale entries from earlier phases)
- [X] T086 Run `.venv/bin/pytest tests/evaluator_tests/ tests/contract_tests/test_evaluation_artifacts.py` with `pytest-socket` enabled; require 100% pass and zero network access
- [X] T087 [P] Add `tests/evaluator_tests/test_performance.py` covering `SC-001` and `SC-002`: a single `evaluate_document` call on the all-match fixture completes in ≤ 1.0 s wall-clock, and `evaluate_corpus` on `corpus_20/` (lazy mode, starting from no `evaluation_document.json`) completes in ≤ 5.0 s wall-clock, both measured via `time.perf_counter()` on the developer workstation baseline. Use a generous buffer only if the CI runner is known to be slower than the dev workstation
- [X] T088 [P] Add `tests/evaluator_tests/test_import_barrier.py` — AST-scan every `src/dartwing_ocr/evaluator/*.py` and assert no module imports from `dartwing_ocr.pipeline` or `dartwing_ocr.preprocessing`. Mechanizes Constitution §I "One Repo, Clear Runtime Boundaries"

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup — blocks every user story
- **User Stories (Phases 3–7)**: Depend on Foundational
  - **US1 (P1)** and **US2 (P1)** together form the MVP. US2 depends on US1 (`evaluate_corpus` calls `evaluate_document`)
  - **US3 (P2)** depends on US1 (extends `normalize.py`/`compare.py`/`gates.py` introduced by US1). Can proceed in parallel with US2
  - **US4 (P2)** depends on US1 (extends `gates.py`). Can proceed in parallel with US2 and US3
  - **US5 (P3)** depends on US2 (Markdown is produced alongside the run summary)
- **Polish (Phase 8)**: Depends on US1–US5 (covers all stories' artifacts)

### Within Each User Story

- Fixtures can be authored in parallel with production code (different files)
- Tests marked `[P]` for the same story can run together after the corresponding production modules exist
- For US2/US5, wire the CLI branch last — Python API is the unit of test

### Parallel Opportunities

- **Phase 2**: T005, T006, T007, T012, T013, T015 are all `[P]` (exceptions, schema loader, I/O, run-summary dataclasses, outcomes, `__init__.py` re-exports live in different files)
- **Phase 3 (US1)**: T016–T021 are all `[P]` fixture / test authoring; T022–T030 are production code and run sequentially within the story
- **Phase 4 (US2)**: T031–T039 are all `[P]`; T040–T050 sequential (each depends on the prior `corpus.py` helper)
- **Phase 5 (US3)**: T051–T057 are all `[P]` fixtures+tests; T058–T067 are normalize/compare/gates extensions — T058–T065 are independent and can run in parallel, T066/T067 depend on them
- **Phase 6 (US4)**: T068–T071 all `[P]`; T072 is a single gate-module edit
- **Phase 7 (US5)**: T073–T077 all `[P]`; T078–T081 largely sequential (T078 before T079 before T080 before T081)
- **Phase 8 (Polish)**: T082–T085 and T087 all `[P]`; T086 last

---

## Parallel Example: Phase 2 Foundational

```bash
# After T004 (constants) lands, launch these in parallel:
Task: "T005 Define exception hierarchy in src/dartwing_ocr/evaluator/exceptions.py"
Task: "T006 Implement schema loader wrapper in src/dartwing_ocr/evaluator/schema.py"
Task: "T007 Implement deterministic JSON I/O in src/dartwing_ocr/evaluator/io.py"
Task: "T012 Define run-summary dataclasses in src/dartwing_ocr/evaluator/corpus.py"
Task: "T013 Define pydantic outcome models in src/dartwing_ocr/evaluator/outcomes.py"
```

## Parallel Example: User Story 3 Fixtures + Tests

```bash
Task: "T051 Author normalization fixtures at tests/evaluator_tests/fixtures/normalization_cases/"
Task: "T052 Author partial-match fixtures at tests/evaluator_tests/fixtures/partial_match_cases/"
Task: "T053 Author gate fixtures at tests/evaluator_tests/fixtures/secondary_identifier_gates/"
Task: "T054 Add tests/evaluator_tests/test_normalize.py"
Task: "T055 Add tests/evaluator_tests/test_compare.py"
Task: "T056 Add tests/evaluator_tests/test_gates.py"
Task: "T057 Add tests/evaluator_tests/test_scoring.py"
```

---

## Implementation Strategy

### MVP (User Stories 1 + 2 — both P1)

1. Phase 1: Setup (T001–T003)
2. Phase 2: Foundational (T004–T015) — BLOCKS everything
3. Phase 3: US1 per-document evaluator (T016–T030) — **stop and validate**: run `evaluate document` on the all-match fixture, confirm artifact is schema-valid and deterministic
4. Phase 4: US2 corpus aggregator (T031–T050) — **stop and validate**: run `evaluate corpus` on `corpus_20/`, confirm summary is schema-valid and deterministic modulo `run_id`

At MVP checkpoint the evaluator can be demoed end-to-end with JSON artifacts only.

### Incremental Delivery

5. Phase 5: US3 full scoring rubric (T051–T067) — every normalization rule and partial-match path is tested; US1 AC#3 and US3 AC#1–#9 all pass strictly rather than by accident
6. Phase 6: US4 missing-name invariants (T068–T072) — SC-004 satisfied
7. Phase 7: US5 Markdown report (T073–T081) — SC-008 satisfied; developers no longer need to open JSON to read the run
8. Phase 8: Polish (T082–T086)

### Parallel Team Strategy

Once Phase 2 ships:
- Dev A: US1 → US3 (comparator/normalization backbone)
- Dev B: US2 → US5 (aggregator + reporting)
- Dev C: US4 (missing-name invariants; tight scope, can land anytime after T027)

All three converge at Polish (Phase 8).

---

## Notes

- `[P]` tasks touch different files and have no dependencies on incomplete peers
- `[Story]` label maps every story-phase task back to `spec.md`'s user stories for traceability
- Determinism (`FR-018`, `SC-005`) is validated by `test_determinism.py` and the quickstart §5 diff recipe — keep the `round_floats(..., ndigits=6)` path in `io.py` intact across all phases
- Harness/pipeline boundary (constitution §I) — evaluator code MUST NOT import from `dartwing_ocr.pipeline` or `.preprocessing`. Reusing `dartwing_ocr.validator` is expected (`research.md` §15)
- Commit after each task or logical group; stop at any checkpoint to validate a story independently
- Avoid: vague tasks, same-file conflicts across `[P]` peers, cross-story dependencies that would break US1/US2 MVP independence
