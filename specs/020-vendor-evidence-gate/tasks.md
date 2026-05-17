---

description: "Task list for feature 020 — Deterministic Vendor-Identity Signals And Early Accept Gate"
---

# Tasks: Deterministic Vendor-Identity Signals And Early Accept Gate

**Input**: Design documents from `/specs/020-vendor-evidence-gate/`
**Prerequisites**: `plan.md` (required), `spec.md` (required for user stories), `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

---

> **B post-review note (post-merge of MVP)**: Several US2 tasks describe an
> `EvidenceGate` dataclass + `EVIDENCE_GATES = {"v1": EvidenceGate(...)}`
> registry. The MVP implementation collapsed that scaffolding to module
> constants + `decide_for_gate(gate_id, signals)` dispatch because the
> registry had size exactly one at landing (YAGNI per the project
> constitution). The tasks remain ticked because the underlying contract
> they describe — closed-vocabulary preset selection, re-derivability,
> additive extension for v2 — is preserved by the flatter shape. See
> `data-model.md §1` and `research.md R-020.2` for the post-review
> reconciliation. Specifically: `T017` (EvidenceGate dataclass), `T019`
> (EVIDENCE_GATES registry registration), and `T020` (EvidenceGateResult
> validation against registry) describe the original plan; the landed
> code uses the flatter `decide_for_gate` form documented in the
> reconciled spec.


**Tests**: Included by default. The spec mandates specific named tests as part of every FR/SC/MI (the contract documents under `contracts/` and the smoke-test list in `quickstart.md` enumerate them explicitly), and FR-024 / R-020.15 require `@pytest.mark.gpu` marking with a CPU-safe deferral floor. Tests are part of the deliverable, not optional.

**Organization**: Tasks are grouped by user story (US1–US7) to enable independent implementation and review. P1 stories (US1–US4) are load-bearing for the feature's value; P2 (US5–US6) are regression guards; P3 (US7) is the promotion-gate evidence.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story label (US1–US7); omitted for Setup, Foundational, and Polish phases
- Include exact file paths in descriptions
- All new code files live under `src/ledgerlinc_ocr/preprocessing/` or `src/ledgerlinc_ocr/pipeline/`; all new test files under `tests/unit/preprocessing/` or `tests/pipeline_tests/` per Plan § Source Code
- `@gpu` suffix on test file names is informational; the marker is the literal `@pytest.mark.gpu` decorator in the file (FR-024)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the worktree is ready for evidence-gate implementation. No new dependency pins (Plan § Technical Context: "**No new pinned dependency**").

- [x] T001 Verify the editable install is current — run `.venv/bin/pip install -e ".[dev]"` from the worktree root and confirm `python -c "import ledgerlinc_ocr"` succeeds without errors
- [x] T002 Verify the existing CPU test suite passes against the current branch tip (post-feature-019 baseline) — run `.venv/bin/pytest tests/contract_tests/ tests/unit/ tests/pipeline_tests/` and confirm exit 0 before any new code lands; capture this as the regression baseline for US6
- [x] T003 Capture pre-feature-020 fixtures from the current branch tip (post-feature-019 baseline) for use by downstream tests — save all of the following under `tests/fixtures/feature_020_baseline/` (create if missing): (a) one `run_summary` JSON line from a feature-019 stub-adapter run (for T022 / T048); (b) one `preprocess_output.json` per strategy from a feature-019 `inv_001_easy` run under each of `full-page`, `header-first-v1`, `ppstructurev3`, `ocr-only-v1` (for T008a strategy uniformity + T048 byte-identity baseline). **C6 fix**: if any referenced fixture turns out not to exist on the branch tip at write time, capture it here BEFORE writing the dependent test — do NOT skip the test or weaken it to "if available". Reuse the path convention from features 017/018/019 (`tests/fixtures/`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish the identifier constants and module-level scaffolding every user story depends on. Until this phase completes, no user story can land its tests.

**⚠️ CRITICAL**: No user-story phase may start until Phase 2 is complete.

- [x] T004 Add identifier constants to `src/ledgerlinc_ocr/preprocessing/identifiers.py` — `EVIDENCE_GATE_ID_V1 = "v1"` and `EVIDENCE_GATE_ID_DEFAULT = EVIDENCE_GATE_ID_V1`; preserve all existing feature 017/018/019 strings unchanged (Plan § Source Code; R-020.2; data-model.md Appendix A)

**Checkpoint**: Identifier constants exist and are importable. US1–US7 can now proceed in priority order (US1 → US2 → US3 → US4 → US5 → US6 → US7), with internal parallelism per phase.

---

## Phase 3: User Story 1 — Deterministic vendor-identity evidence signals from `preprocess_output.json` (Priority: P1) 🎯 MVP

**Goal**: Compute the five FR-001 signals (`vendor_name_candidate_count`, `header_band_token_density`, `ocr_detection_confidence_mean`, `business_suffix_present`, `tax_id_shaped_present`) over the page-1 header band as a pure function of `preprocess_output.json` content — CPU-safe, no Paddle import, byte-identical across reruns and hosts.

**Independent Test**: Run any of the five signal unit tests below on a host with no Paddle installed. Each test passes a synthetic `preprocess_output.json` dict to `evaluate_evidence_gate(...)` and asserts byte-identical signal values across two invocations (SC-001).

### Tests for User Story 1 ⚠️

> **NOTE**: Write each test FIRST and confirm it FAILS before the corresponding implementation task lands.

- [x] T005 [P] [US1] Author `tests/unit/preprocessing/test_evidence_gate_signals_unit.py` — per-signal unit tests covering: vendor-name-candidate counting (length, casing, stop-word exclusion, case folding), header-band token-density tokenization (whitespace + NFKC), `ocr_detection_confidence_mean` aggregation including the empty-band → `0.0` case, `business_suffix_present` regex matching across all enumerated suffixes (`LLC`/`Inc`/`Incorporated`/`Ltd`/`Limited`/`GmbH`/`S.A.`/`S.A.S.`/`Corp`/`Corporation`/`Co.`), `tax_id_shaped_present` matching for EIN (`XX-XXXXXXX`) and VAT (2-letter country prefix + 2..12 alphanumerics with **at least one digit** — see `data-model.md §6` for the literal pattern; B2 / Phase 6 post-review tightening); assert byte-equality across two invocations on the same input (MI-6 / SC-001). **Cross-host claim (SC-001 second clause) — verified by-construction**: include an inline test-file docstring noting that signal computation is order-independent over detection boxes (uses `sum()` / `statistics.mean` / regex match, no hash-set iteration, no float-comparison ordering), and that NFKC normalization (T007) plus pinned regex patterns make the output environment-independent. Add a small assertion that two `evaluate_evidence_gate` calls within the same process produce identical `EvidenceGateResult` objects — the cross-host claim has no float-ordering risk to test against
- [x] T006 [P] [US1] Author `tests/unit/preprocessing/test_evidence_gate_y_threshold_unit.py` — synthetic multi-page fixtures with tokens at varied y-coordinates; assert tokens with `bbox_top_y / page_height < 0.25` are in-band, tokens at or above the boundary are out-of-band, multi-page documents only see `pages[0]` tokens (R-020.5)
- [x] T007 [P] [US1] Author `tests/unit/preprocessing/test_evidence_gate_nfkc_unit.py` — pass strings containing fullwidth forms and combining characters; assert the normalized token list matches the canonical (NFKC) form for every signal (MI-9 / R-020.3)
- [x] T008 [P] [US1] Author `tests/unit/preprocessing/test_evidence_gate_module_safety_unit.py` — assert `import preprocessing.evidence_gate` succeeds in a process with no Paddle / no `paddleocr` / no `paddlepaddle` import (MI-4 / MI-5); use the existing CPU-only test marker pattern
- [x] T008a [P] [US1] Author `tests/unit/preprocessing/test_evidence_gate_strategy_uniformity.py` — load captured `preprocess_output.json` fixtures from each of the four strategies in scope (`full-page` from feature 018, `header-first-v1` from feature 018, `ppstructurev3` from feature 019, `ocr-only-v1` from feature 019) and assert `evaluate_evidence_gate(<output>)` succeeds on each, returns the correct `FiveSignalSet` types (`int`/`int`/`float`/`bool`/`bool`), and produces a decision in the closed three-state vocabulary. The signal VALUES will differ across strategies (different OCR runs see different tokens) — that is expected and not asserted; this test verifies the SHAPE / type uniformity required by FR-002 ("computable on the output of any preprocessing strategy in scope today" / "MUST NOT require layout-derived blocks" / "MUST NOT require any feature-018 region-strategy-specific shape"). Use existing committed `preprocess_output.json` fixtures from `tests/fixtures/` or `tests/stage1_vendor_identity/inv_001_easy/preprocess_output.json` snapshots produced by the prior features

### Implementation for User Story 1

- [x] T009 [US1] Create `src/ledgerlinc_ocr/preprocessing/evidence_gate.py` — module scaffolding: `Y_THRESHOLD_FRACTION = 0.25`, `DENSITY_THRESHOLD = 8`, `CONFIDENCE_THRESHOLD = 0.70` (all `Final[...]`); `VENDOR_NAME_STOP_WORDS: Final[frozenset[str]]` per data-model.md §8; compile `BUSINESS_SUFFIX_RE`, `TAX_ID_EIN_RE`, `TAX_ID_VAT_RE` per R-020.4 / data-model.md §6 (CPU-safe — only `re` and stdlib at module load; no Paddle, no `paddleocr`, no `paddlepaddle` imports — MI-4 / MI-5)
- [x] T010 [US1] In `src/ledgerlinc_ocr/preprocessing/evidence_gate.py`, add the frozen dataclass `FiveSignalSet` per data-model.md §2 with the five typed fields and validation rules (no `NaN`, no `Infinity`, `ocr_detection_confidence_mean ∈ [0.0, 1.0]`)
- [x] T011 [US1] In `src/ledgerlinc_ocr/preprocessing/evidence_gate.py`, implement `_extract_header_band_tokens(preprocess_output: dict, *, y_threshold_fraction: float = 0.25)` — apply NFKC normalization to each block/box's recognized text, tokenize on whitespace, filter by `bbox_top_y / page_height < y_threshold_fraction` on `pages[0]` only (R-020.3 / R-020.5)
- [x] T012 [US1] In `src/ledgerlinc_ocr/preprocessing/evidence_gate.py`, implement the five signal computations as private helpers operating on the band-token list and the band's detection-box confidences; ensure empty-band returns the negative-level tuple per R-020.3 / data-model.md §2
- [x] T013 [US1] In `src/ledgerlinc_ocr/preprocessing/evidence_gate.py`, expose `evaluate_evidence_gate(preprocess_output: dict, *, gate_id: str = "v1") -> EvidenceGateResult` returning the populated `FiveSignalSet` (decision wiring lands in US2); the function MUST accept only the `preprocess_output` dict (MI-2 / MI-3)
- [x] T013a [P] [US1] Author `tests/unit/preprocessing/test_evidence_gate_malformed_input.py` — CPU-safe; covers the spec §Edge Cases "Malformed `preprocess_output.json` reaches the gate" rule. Pass each of the following malformed dicts to `evaluate_evidence_gate(...)` and assert behavior: (a) missing `pages` key — assert decision == `"insufficient"`, all five signals at negative level (`0` / `0` / `0.0` / `False` / `False`); (b) `pages=[]` (zero pages) — same assertion; (c) `pages=[{}]` (page 0 has no `blocks` / no `raw_ocr_lines` / no geometry) — same assertion; (d) `pages=[{"blocks": [], "raw_ocr_lines": []}]` (empty page-1 explicit) — same assertion; (e) `pages[0]["height_pt"]` missing or zero (y-fraction comparison cannot apply) — same assertion (fail closed via empty-band tuple); (f) wrong-type fields (e.g., `pages` is a string, `blocks` is None) — same assertion. For all six cases, assert the gate does NOT raise. **Suppression-on-malformed assertion**: also assert `should_suppress_fallback(preprocess_strategy_id="ocr-only-v1", fr_005_trigger_would_fire=True, opt_in_active=True, candidate_gate_decision=<insufficient from above>)` returns `False` — malformed input MUST NOT enable suppression even with all three other conjuncts true (R-020.8 / spec §Edge Cases).

**Checkpoint**: US1 complete. The five signals compute deterministically and byte-identically on any host. Tests T005–T008 pass. No Paddle import is reachable from `evidence_gate.py`. The signal set is observable internally but is not yet emitted on `run_summary` (that lands in US3).

---

## Phase 4: User Story 2 — Three-state early-sufficiency gate decision (Priority: P1)

**Goal**: Map the FR-001 five-signal set into one of `sufficient` / `borderline` / `insufficient` via the `v1` explicit decision table (R-020.6). The decision is pure, re-derivable from the recorded signals + the documented table without re-running the binary (SC-002 / SC-012), and selectable via the closed-vocabulary `evidence_gate_id` preset registry (R-020.2).

**Independent Test**: Construct three synthetic `FiveSignalSet` tuples (all-positive, all-negative, mixed) and assert `EVIDENCE_GATES["v1"].decide(signals)` returns `sufficient`, `insufficient`, `borderline` respectively. Re-run on the same tuples and assert byte-identical decisions (MI-6 / MI-7).

### Tests for User Story 2 ⚠️

- [x] T014 [P] [US2] Author `tests/unit/preprocessing/test_evidence_gate_decision_unit.py` — parameterized table covering all 32 truth-table rows from `contracts/evidence-gate-rule.md` § Decision table; assert 3 rows fire `sufficient`, 1 row fires `insufficient`, 28 rows fire `borderline`; assert the inclusive-on-the-high-side comparison at the three numeric thresholds (count exactly 1, density exactly 8, confidence exactly 0.70) qualifies as positive (R-020.6 / evidence-gate-rule.md § V1 decision table)
- [x] T015 [P] [US2] Author `tests/unit/preprocessing/test_evidence_gate_rederivability_unit.py` — for each row in T014's truth table, assert `result.decision == EVIDENCE_GATES[result.evidence_gate_id].decide(result.signals)` (MI-7 / SC-002 / SC-012 — operator-side re-derivability guarantee)
- [x] T016 [P] [US2] Author `tests/unit/preprocessing/test_evidence_gate_registry_unit.py` — assert `dict(EVIDENCE_GATES) == {"v1": <expected>}` at module load (registry size one at landing — MI-25); assert `EvidenceGate.decide` return type is constrained to the closed three-state vocabulary (MI-26)

### Implementation for User Story 2

- [x] T017 [US2] In `src/ledgerlinc_ocr/preprocessing/evidence_gate.py`, expose the gate preset surface as module-level `Final[...]` constants (`EVIDENCE_GATE_ID_V1`, `Y_THRESHOLD_FRACTION`, `DENSITY_THRESHOLD`, `CONFIDENCE_THRESHOLD`). *(Phase 2 H2 collapse: the original plan called for an `EvidenceGate` frozen dataclass — replaced by module-level constants + `decide_for_gate` dispatch because the registry had size exactly one at landing; the closed-vocabulary contract and the R-020.2 extension path are unchanged. See data-model.md §1.)*
- [x] T018 [US2] In `src/ledgerlinc_ocr/preprocessing/evidence_gate.py`, implement `_v1_decide(signals: FiveSignalSet) -> Literal["sufficient", "borderline", "insufficient"]` as the literal boolean expression from R-020.6 / evidence-gate-rule.md (use `>=` inclusive-on-the-high-side comparisons; return the closed-vocabulary literal with no fallback default)
- [x] T019 [US2] In `src/ledgerlinc_ocr/preprocessing/evidence_gate.py`, expose the v1 dispatch path via `decide_for_gate(gate_id: str, signals: FiveSignalSet) -> GateDecision`. The function accepts only `EVIDENCE_GATE_ID_V1` at landing and raises `KeyError` otherwise (Phase 2 H2: replaced the prior `EVIDENCE_GATES = {"v1": EvidenceGate(...)}` registry with a flatter dispatch hook; v2 lands as an additive code branch per R-020.2).
- [x] T020 [US2] In `src/ledgerlinc_ocr/preprocessing/evidence_gate.py`, add the frozen `EvidenceGateResult` dataclass per data-model.md §3 with fields `signals`, `decision`, `evidence_gate_id` and the validation invariant `decision == decide_for_gate(evidence_gate_id, signals)` (Phase 6: dispatch via `decide_for_gate` rather than calling `_v1_decide` directly, so adding v2 to the dispatch table is enough — no need to update the post-init separately).
- [x] T021 [US2] Update `evaluate_evidence_gate(...)` in `src/ledgerlinc_ocr/preprocessing/evidence_gate.py` to wire the decision through: compute `FiveSignalSet` via US1 helpers, call `decide_for_gate(gate_id, signals)`, return `EvidenceGateResult(signals=..., decision=..., evidence_gate_id=gate_id)`.

**Checkpoint**: US2 complete. `evaluate_evidence_gate(preprocess_output_dict)` returns a deterministic three-state decision over the five signals. Tests T014–T016 pass alongside US1's T005–T008. The closed-vocabulary preset registry is in place; future presets land via additive entries.

---

## Phase 5: User Story 3 — Gate decision and signal set visible on `run_summary` (Priority: P1)

**Goal**: Emit four additive top-level fields (`evidence_gate_id`, `evidence_gate_state_counts`, `evidence_gate_documents`, `evidence_gate_suppressed_fallback_count`) on every `kind: "run_summary"` stdout line produced by the new binary. Bump the codebase-level `SCHEMA_VERSION` from `"0.1.6"` to `"0.1.7"` (R-020.9). Always-emit invariant: all four fields present on stub-adapter, CPU, and (deferred) GPU runs (MI-16 / MI-17 / SC-003).

**Independent Test**: A stub-adapter run with zero documents emits a `run_summary` line containing `schema_version="0.1.7"`, `evidence_gate_id="v1"`, `evidence_gate_state_counts={"sufficient":0,"borderline":0,"insufficient":0}`, `evidence_gate_documents=[]`, `evidence_gate_suppressed_fallback_count=0`. Two stub-adapter runs produce byte-identical values across all four fields.

### Tests for User Story 3 ⚠️

- [x] T022 [P] [US3] Author `tests/pipeline_tests/test_run_summary_schema_0_1_7.py` — assert `schema_version == "0.1.7"` on stub-adapter and `ppstructurev3@cpu` runs; assert presence of all four new fields with default values; assert the `evidence_gate_state_counts` object has all three keys present (NOT sparse — MI-17); assert features 014–019 keys remain byte-identical to the captured pre-feature-020 fixture from T003 (MI-19 / FR-011 / FR-022 / SC-009). **C7 — FR-003 PII-safety closure assertion**: for every element of `evidence_gate_documents`, assert `set(record.keys()) == {"document_id", "decision", "signals"}` AND `set(record["signals"].keys()) == {"vendor_name_candidate_count", "header_band_token_density", "ocr_detection_confidence_mean", "business_suffix_present", "tax_id_shaped_present"}` — no extra keys, no `vendor_name_candidate_tokens` / `matched_tax_id_values` / `matched_suffix_substring` / any other field that would leak raw token text. Assert the value types are exactly `int / int / float / bool / bool`. A future regression that adds a raw-text field to signals MUST fail this assertion.
- [x] T023 [P] [US3] Author `tests/pipeline_tests/test_evidence_gate_corpus_run.py` — stub-adapter run on a small synthetic corpus; assert per-document gate decisions appear in `evidence_gate_documents`; assert `evidence_gate_state_counts[s]` equals the count of `evidence_gate_documents[i].decision == s` for each of the three states (MI-18); assert deterministic ordering (alphabetical by `document_id` per `corpus_run.py` iteration — R-020.11 / data-model.md §4)
- [x] T024 [P] [US3] Author `tests/pipeline_tests/test_evidence_gate_field_order.py` — assert the four new fields are emitted in the deterministic order (`evidence_gate_id`, `evidence_gate_state_counts`, `evidence_gate_documents`, `evidence_gate_suppressed_fallback_count`) AFTER feature 019's `preprocess_strategy_id` and `ocr_only_fallback_count` (R-020.10 / run-summary-schema.md § Order of keys)

### Implementation for User Story 3

- [x] T025 [US3] In `src/ledgerlinc_ocr/pipeline/timing.py`, bump `SCHEMA_VERSION = "0.1.6"` → `SCHEMA_VERSION = "0.1.7"` (R-020.9)
- [x] T026 [US3] In `src/ledgerlinc_ocr/pipeline/timing.py`, extend `RunSummary` (dataclass) with four new fields per data-model.md §5: `evidence_gate_id: str = EVIDENCE_GATE_ID_DEFAULT`, `evidence_gate_state_counts: dict[str, int]` (default factory returns `{"sufficient": 0, "borderline": 0, "insufficient": 0}`), `evidence_gate_documents: list[dict]` (default factory returns `[]`), `evidence_gate_suppressed_fallback_count: int = 0`; preserve every existing field name/type/default unchanged (FR-011 / FR-022 / MI-19)
- [x] T027 [US3] In `src/ledgerlinc_ocr/pipeline/timing.py`, update `RunSummary.to_dict()` to emit the four new keys in deterministic order AFTER feature 019's two fields and BEFORE any future additive field (R-020.10 / run-summary-schema.md)
- [x] T028 [US3] In `src/ledgerlinc_ocr/pipeline/corpus_run.py`, after each document's preprocessing completes, call `evaluate_evidence_gate(<final preprocess_output dict>)` and: (a) increment `evidence_gate_state_counts[result.decision]`; (b) append an `EvidenceGateDocumentRecord`-shaped dict (`document_id` + `decision` + nested `signals` object per data-model.md §4) to `evidence_gate_documents`; iteration order follows the existing per-document iteration (typically alphabetical by `document_id` — R-020.11)
- [x] T029 [US3] In `src/ledgerlinc_ocr/pipeline/runner.py`, mirror T028's wiring for the single-document path — evaluate the gate on the document's final `preprocess_output.json` and populate the four new `RunSummary` fields; `document_id` derived from the input folder's basename (R-020.11)
- [x] T030 [US3] Ensure stub-adapter runs emit the four new fields with default values (`evidence_gate_id="v1"`, all-zero counters, empty array, `0`) regardless of profile (MI-16 / MI-17) — verify the wiring does NOT short-circuit on stub adapters

**Checkpoint**: US3 complete. Every run of the new binary emits the four new `run_summary` fields with correct values. Tests T022–T024 pass. The codebase-level schema is at `0.1.7`. No canonical artifact schema is touched (FR-020 / SC-010).

---

## Phase 6: User Story 4 — Skip-fallback for OCR-only `sufficient` runs (Priority: P1)

**Goal**: Implement the FR-007 shape (b) skip-fallback behavior — when the gate decision over the OCR-only candidate output is `sufficient` AND the opt-in is active AND feature 019's FR-005 trigger would fire, suppress the PPStructureV3 fallback and keep the OCR-only output as final; increment `evidence_gate_suppressed_fallback_count`. Opt-in via `--evidence-gate-skip-fallback` + `LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK` env var; off by default (FR-012). Only the `sufficient` gate state may trip suppression (FR-009 / SC-011).

**Independent Test**: On a `ppstructurev3@gpu` + `--preprocess-strategy=ocr-only-v1` + `--evidence-gate-skip-fallback` run against a fixture where the gate decision is `sufficient` AND FR-005 fires, assert `evidence_gate_suppressed_fallback_count == 1`, `ocr_only_fallback_count == 0` for that document, and the document's `evidence_gate_documents[i].decision == "sufficient"`. On the same setup against a `borderline` fixture, assert the inverse: `evidence_gate_suppressed_fallback_count == 0`, `ocr_only_fallback_count == 1`. (GPU-marked; deferrable per R-020.15; CPU-safe predicate tests gate the merge.)

### Tests for User Story 4 ⚠️

- [ ] T031 [P] [US4] Author `tests/unit/preprocessing/test_evidence_gate_optin_unit.py` — cover `resolve_evidence_gate_skip_fallback` precedence: CLI True wins over any env value; CLI False (absent) + truthy env (`"1"`, `"true"`, `"yes"`, `"on"`, case-insensitive) → True; CLI False + falsy env (`"0"`, `"false"`, `"no"`, `"off"`, `""`, unset) → False; unrecognized env value rejects via the same error path as existing `_PRESET_ENV_VAR` helpers (R-020.1); assert `evidence_gate_skip_fallback_warn_message(active_profile)` returns a string containing the literal substring `--evidence-gate-skip-fallback ignored:` (MI-22)
- [ ] T032 [P] [US4] Author `tests/unit/preprocessing/test_evidence_gate_suppress_predicate.py` — exhaustive 16-row truth-table coverage of `should_suppress_fallback(preprocess_strategy_id, fr_005_trigger_would_fire, opt_in_active, candidate_gate_decision)`; assert it returns `True` iff ALL four conjuncts hold; assert `borderline` and `insufficient` candidate decisions NEVER trigger suppression regardless of the other three inputs (MI-13 / MI-14 / FR-009 / SC-011)
- [ ] T033 [P] [US4] Author `tests/pipeline_tests/test_evidence_gate_skip_fallback.py` — mark with `@pytest.mark.gpu` (FR-024 / R-020.15); GPU end-to-end run on a `sufficient`-eligible fixture under `--preprocess-strategy=ocr-only-v1 --evidence-gate-skip-fallback`; assert `evidence_gate_suppressed_fallback_count == 1`, `ocr_only_fallback_count == 0` for the document, the document's `evidence_gate_documents` entry records `decision: "sufficient"`, and the final `preprocess_output.json` is the OCR-only candidate (R-020.7 / R-020.8)
- [ ] T033a [P] [US4] Author `tests/pipeline_tests/test_evidence_gate_all_suppressed_lazy_construction.py` — covers the FR-007 lazy-construction clause (Clarifications Session 2026-05-16 Q2 Option B): PPStructureV3 construction is lazy under skip-fallback, with the `--gpu-warmup` operator-opt-in as the sole forcing exception. The file collects three logically related scenarios in distinct test functions so a reader sees both the "no construction" path and the "construction forced by warmup" path side-by-side. **`test_lazy_no_warmup` (GPU `@pytest.mark.gpu`, deferrable per R-020.15)**: run `--preprocess-strategy=ocr-only-v1 --evidence-gate-skip-fallback` (NO `--gpu-warmup`) on a multi-doc corpus where every document is `sufficient` and every FR-005 trigger would fire; via instrumentation assert `_ENGINE` (PPStructureV3) is `None` after the run AND the run's `phase_timings.warmup` for PPStructureV3 is `0` AND `evidence_gate_suppressed_fallback_count` equals the document count AND `ocr_only_fallback_count == 0` for the run (mirrors feature 019 T036 `test_warmup_engine_binding.py` pattern). **`test_lazy_cpu_safe` (CPU-safe — merge-gating)**: via injected fake `preprocess_strategy` (the same seam T040 lands per I3 fix), assert that on a multi-doc corpus where all candidates evaluate to `sufficient` AND the opt-in is active, the construction-decision path in `preprocessing/pipeline.py` never calls the PPStructureV3 factory — exercise via a recording stub that fails the test if called. Gates merge per R-020.15 even if the GPU variants are deferred. **`test_forced_construction_with_warmup` (GPU `@pytest.mark.gpu`, deferrable)**: same setup as `test_lazy_no_warmup` but WITH `--gpu-warmup`; assert PPStructureV3 IS constructed at warmup time (forced by the operator) AND `phase_timings.warmup` for PPStructureV3 is non-zero AND `evidence_gate_suppressed_fallback_count` still equals the document count — the operator-opt-in trade-off documented in the FR-007 lazy-construction clause
- [ ] T034 [P] [US4] Author `tests/pipeline_tests/test_evidence_gate_skip_fallback_borderline.py` — mark with `@pytest.mark.gpu`; same setup as T033 but on a `borderline`-eligible fixture; assert `evidence_gate_suppressed_fallback_count == 0`, `ocr_only_fallback_count == 1`, the document's `evidence_gate_documents` entry records the gate decision over the POST-fallback PPStructureV3 output (MI-11 / R-020.7). GPU-only; CPU-safe coverage of the same MI-11 invariant lives in T034a (split out for I2 / clarity)
- [ ] T034a [P] [US4] Author `tests/pipeline_tests/test_evidence_gate_skip_fallback_borderline_cpu.py` — CPU-safe variant of T034 using an injected fake `preprocess_strategy` whose fallback path is observable; assert MI-11 (gate evaluated TWICE per document — once on the OCR-only candidate for the suppression decision, once on the post-fallback output for the recorded decision) without requiring GPU; assert the recorded `evidence_gate_documents` entry reflects the post-fallback evaluation, not the candidate evaluation; merge-gates US4 even if T034 is deferred per R-020.15
- [ ] T035 [P] [US4] Author `tests/pipeline_tests/test_evidence_gate_recorded_over_final.py` — CPU-safe via injection; assert that for a fixture where the candidate evaluation differs from the final evaluation, the RECORDED decision in `evidence_gate_documents` matches the gate evaluation over the FINAL `preprocess_output.json` (MI-10 / R-020.7)

### Implementation for User Story 4

- [ ] T036 [US4] Create `src/ledgerlinc_ocr/preprocessing/evidence_gate_optin.py` — CPU-safe module mirroring `preprocess_strategy_optin.py` exactly; export `EVIDENCE_GATE_SKIP_FALLBACK_ENV_VAR = "LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK"`, `resolve_evidence_gate_skip_fallback(cli_value: bool | None, env: Mapping[str, str] | None = None) -> bool`, and `evidence_gate_skip_fallback_warn_message(active_profile: str) -> str` returning a string containing the literal `--evidence-gate-skip-fallback ignored: active profile is not ppstructurev3@gpu` grep-able marker (R-020.1 / R-020.12 / MI-22)
- [ ] T037 [US4] In `src/ledgerlinc_ocr/preprocessing/evidence_gate.py`, implement `should_suppress_fallback(*, preprocess_strategy_id, fr_005_trigger_would_fire, opt_in_active, candidate_gate_decision) -> bool` per R-020.8 / MI-13; pure function, no globals, four-conjunct predicate. The predicate is colocated with the gate body (not in `evidence_gate_optin.py`) because it consumes `candidate_gate_decision`, which is a gate output — the opt-in module owns CLI/env resolution and warn-message strings only
- [ ] T038 [US4] In `src/ledgerlinc_ocr/preprocessing/cli.py`, add the `--evidence-gate-skip-fallback` boolean flag (default `False`) and wire it through the existing CLI parsing path; help-text excerpt per `contracts/cli-contract.md` § Help text; place adjacent to feature 019's `--preprocess-strategy`
- [ ] T039 [US4] In `src/ledgerlinc_ocr/preprocessing/cli.py`, call `resolve_evidence_gate_skip_fallback(cli_value, env)` to compute the active opt-in; when resolved `True` AND active profile is NOT `ppstructurev3@gpu`, emit exactly one stderr line via `evidence_gate_skip_fallback_warn_message(active_profile)` and continue with the run unchanged (warn-and-proceed, MI-22 / MI-23 / R-020.12); same exit code as the no-flag run
- [ ] T040 [US4] In `src/ledgerlinc_ocr/preprocessing/pipeline.py` (`run_preprocess`), integrate the gate per the R-020.7 evaluation order: (1) preprocessing produces a candidate `preprocess_output.json`; (2) if `preprocess_strategy_id == "ocr-only-v1"` AND the feature 019 FR-005 trigger fires AND the opt-in is active, evaluate `evaluate_evidence_gate(<candidate>)`; (3) if the candidate decision is `sufficient`, suppress fallback (keep OCR-only as final) AND increment `evidence_gate_suppressed_fallback_count` on the run-level `RunSummary`; (4) otherwise run feature 019's existing PPStructureV3 fallback unchanged and re-evaluate the gate on the post-fallback output for the recorded decision; the RECORDED decision is always the gate evaluation over the FINAL `preprocess_output.json` (R-020.7 / MI-10 / MI-11 / MI-12). **I3 fix — injection seam for T034a**: while wiring the fallback branch, factor the "(strategy_id, fr_005_trigger_would_fire) → fallback_or_keep" decision so it can be exercised in CPU-safe tests without invoking PaddleOCR. Mirror the prior-feature pattern used by `preprocess_strategy_optin` (feature 019) and `region_strategy_optin` (feature 018): expose either (a) a module-level helper that takes preprocessing-pass state as keyword args and returns the disposition (suppress / fallback / keep), or (b) a `preprocess_strategy_factory` parameter on `run_preprocess` accepting a stub. T034a uses whichever seam this task lands; if neither pattern fits, document the chosen seam shape in `contracts/module-invariants.md` as a new MI under "Evaluation-order invariants"
- [ ] T041 [US4] In `src/ledgerlinc_ocr/pipeline/cli.py`, add the same `--evidence-gate-skip-fallback` flag + env-var fallback wiring as T038 + T039 (warm-corpus path); preserve the orthogonal-composition precedent established by features 014–019; help-text identical to the preprocessing CLI
- [ ] T042 [US4] Propagate per-document suppression events from `preprocessing/pipeline.py::run_preprocess` to `pipeline/corpus_run.py` so the corpus-level `RunSummary.evidence_gate_suppressed_fallback_count` aggregates correctly across all documents in a corpus run (the counter is an integer sum of per-document increments)

**Checkpoint**: US4 complete. The skip-fallback behavior is opt-in and behaves deterministically. CPU-safe tests (T031, T032, T035, plus T034 CPU variant) pass; GPU-marked tests (T033, T034 GPU variant) are merge-deferred per R-020.15. The four-conjunct predicate is exhaustively covered. The flag is off by default per FR-012 / MI-20.

---

## Phase 7: User Story 5 — Default CPU profile and CI without GPU stay safe (Priority: P2)

**Goal**: Guarantee that CPU profiles, stub adapters, and no-GPU CI continue to work after this feature lands. The CPU surface gets observability (US1/US2/US3 fields) but no behavioral change. The opt-in flag on a CPU/stub profile fires warn-and-proceed (FR-013) with no behavior change and the same exit code.

**Independent Test**: On a host without Paddle GPU, run the default test suite (`.venv/bin/pytest -m "not gpu"`) and confirm exit 0 — including all signal-set and gate-decision unit tests. Run `python -m ledgerlinc_ocr.preprocessing --evidence-gate-skip-fallback --preprocess-profile ppstructurev3@cpu ... 2>&1 | grep -F -- "--evidence-gate-skip-fallback ignored:"` and confirm exit 0 with the grep match.

### Tests for User Story 5 ⚠️

- [ ] T043 [P] [US5] Author `tests/unit/preprocessing/test_cpu_warn_and_proceed_evidence_gate.py` — CPU-safe; invokes the CLI with `--evidence-gate-skip-fallback` on `ppstructurev3@cpu` and stub-adapter profiles; asserts exactly ONE stderr line matches the grep-able marker (MI-22); asserts the four new `run_summary` fields are still emitted with default values (gate runs on CPU per FR-014); asserts the exit code equals the no-flag run on the same fixture (MI-23); covers the env-var fallback path with `LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK=1`
- [ ] T044 [P] [US5] Author `tests/unit/preprocessing/test_evidence_gate_no_warn_paths.py` — CPU-safe; assert the warn does NOT fire when (a) opt-in is unset, (b) active profile IS `ppstructurev3@gpu` with `--preprocess-strategy != ocr-only-v1`, (c) active profile IS `ppstructurev3@gpu` with `ocr-only-v1` but no document triggers FR-005 (MI-24 / R-020.12 "The warn fires only when..." conditions)
- [ ] T045 [P] [US5] Author `tests/unit/preprocessing/test_evidence_gate_cpu_isolation.py` — assert no CPU code path imports any GPU-only module from feature 019's preprocess-strategy machinery (FR-014); use the existing test pattern from feature 016/017/018/019's CPU-isolation tests

### Implementation for User Story 5

- [ ] T046 [US5] Verify (no code change expected — pure audit task) that `src/ledgerlinc_ocr/preprocessing/evidence_gate.py` and `src/ledgerlinc_ocr/preprocessing/evidence_gate_optin.py` import only `re`, `typing`, `dataclasses`, `collections.abc`, and other stdlib symbols at module load (no `paddleocr`, no `paddlepaddle`, no `paddle` import); if any GPU-only import slipped in via integration tasks T036–T042, refactor to guard the import (lazy / conditional) so MI-4 / MI-5 / FR-014 still hold
- [ ] T047 [US5] Verify (no code change expected — pure audit task) that `src/ledgerlinc_ocr/pipeline/timing.py`, `src/ledgerlinc_ocr/pipeline/corpus_run.py`, and `src/ledgerlinc_ocr/pipeline/runner.py` still import-clean on a no-Paddle host; integrate `tests/unit/preprocessing/test_evidence_gate_module_safety_unit.py` (T008) into the default CI selection to enforce this on every PR

**Checkpoint**: US5 complete. CPU CI is green. The warn-and-proceed path is exercised on the default no-GPU suite. No CPU code path imports GPU-only modules.

---

## Phase 8: User Story 6 — Output schema and downstream contracts unchanged (Priority: P2)

**Goal**: Verify that the four canonical stage 1 artifact schemas, the active `contract_set_version`, and the `pipeline_version` shape are unchanged by this feature, and that every downstream stage (evidence-packet assembler, single-voter extractor, router, final-payload assembler, evaluator) accepts the outputs without modification.

**Independent Test**: Run a small corpus subset end-to-end through preprocess → evidence packet → extract → route → assemble → evaluate under each configuration this feature introduces (legacy default, opt-in on `ppstructurev3@cpu` (warn-and-proceed), opt-in on `ppstructurev3@gpu` + `ocr-only-v1`). Confirm every emitted artifact validates under its existing schema in `contracts/stage1_vendor_identity/v1.2.0/`, and that the existing `tests/contract_tests/` suite passes unchanged.

### Tests for User Story 6 ⚠️

- [ ] T048 [P] [US6] Author `tests/pipeline_tests/test_legacy_byte_identity_evidence_gate.py` — CPU variant; a run with NO `--evidence-gate-skip-fallback` flag and no truthy env var produces a `preprocess_output.json` byte-identical to a pre-feature-020 baseline on the same fixture (SC-006 / SC-007 / FR-019 / MI-20); compare against a captured baseline under `tests/fixtures/` (reuse the feature 019 baseline if available)
- [ ] T049 [P] [US6] Author `tests/pipeline_tests/test_canonical_artifacts_unchanged.py` — assert `git diff main -- contracts/stage1_vendor_identity/` shows zero changes attributable to this feature's PR (SC-010); assert `contract_set_version` reads the same value as on `main` (FR-020); run as a CPU-safe regression check
- [ ] T050 [P] [US6] Author `tests/pipeline_tests/test_downstream_stages_accept_outputs.py` — end-to-end run on at least one fixture (CPU variant; GPU end-to-end deferred per R-020.15); preprocess → evidence packet → extract (stub voter) → route → assemble → evaluate; assert every emitted artifact validates against its `contracts/stage1_vendor_identity/v1.2.0/*.schema.json`; assert no canonical artifact contains any gate-related field (FR-021 / SC-007). **No-sidecar assertion (FR-021)**: snapshot the per-document folder's file list (e.g., `set(p.name for p in folder.iterdir())`) BEFORE the run; after the run, assert the only NEW files are the four canonical artifacts (`preprocess_output.json`, `edge_extraction_output.json`, `routing_decision.json`, `final_structured_payload.json`) — no `evidence_gate.json` / `gate_decision.json` / `signals.json` / any other sidecar appears. Optional debug-mode `page_*.png` are tolerated only if they pre-existed in the snapshot

### Implementation for User Story 6

- [ ] T051 [US6] Verify (no code change expected — pure audit task) that nothing in `evidence_gate.py`, `evidence_gate_optin.py`, the CLI wiring, or the `RunSummary` changes touches `contracts/stage1_vendor_identity/v1.2.0/*.schema.json` or `contract_set.json`; if any change is detected, revert and route through `contracts/stage1_vendor_identity/AMENDMENTS.md` instead (FR-020)
- [ ] T052 [US6] Run the existing `tests/contract_tests/` suite against the post-feature-020 branch tip and confirm exit 0 (FR-020 / SC-009); document the result inline in this task before marking done
- [ ] T052a [P] [US6] Author `tests/pipeline_tests/test_evidence_gate_counter_invariance.py` — CPU-safe; construct a `RunSummary` with `region_strategy_fallback_count=2` and `ocr_only_fallback_count=1` (non-zero starting values); run the gate aggregation path (T028's wiring); assert both counters remain at their input values (`2` and `1` respectively) — the gate MUST NOT alter, suppress, or shadow either counter (FR-023). Symmetric assertion: set `evidence_gate_state_counts` to non-zero values; run feature 018's region-strategy fallback path; assert the gate counters remain at their input values

**Checkpoint**: US6 complete. Canonical artifacts are untouched. Downstream stages accept the gate-instrumented outputs without modification. T048–T050 pass on CPU. The existing contract test suite still passes.

---

## Phase 9: User Story 7 — Quality-gate guard before any behavioral default change (Priority: P3)

**Goal**: Lay down the FR-016 / R-020.14 two-metric quality gate as a follow-up evaluation mechanism. At landing, the opt-in remains OFF by default (FR-012); promoting it to ON requires BOTH metrics (aggregate vendor-identity field score from `evaluation_run_summary.json` AND per-document pass count per `scoring.md`) to be `>=` the legacy default's values on the FR-015 5-doc subset. If GPU is available at landing, record the evidence in `research.md` Appendix B; otherwise defer per R-020.15 with explicit tracking in this `tasks.md` and in `quickstart.md` Appendix B.

**Independent Test**: On a GPU host, run the FR-015 benchmark over the 5-doc subset for both the legacy default and the skip-fallback candidate; read `evaluation_run_summary.json` from both runs; assert `candidate_aggregate_score >= legacy_aggregate_score` AND `candidate_pass_count >= legacy_pass_count`. If GPU unavailable, the deferral is captured below and in `quickstart.md` Appendix B.

### Tests for User Story 7 ⚠️

- [ ] T053 [P] [US7] Author `tests/pipeline_tests/test_evidence_gate_benchmark.py` — mark with `@pytest.mark.gpu` (R-020.15 deferrable); GPU run over the fixed 5-doc subset (R-020.13). **5-doc subset lookup procedure**: (1) FIRST, read `specs/017-ppstructurev3-module-reduction/quickstart.md` Appendix A and `specs/019-ocr-only-fast-lane/quickstart.md` § FR-015 benchmark table — if either has been filled at landing time with three concrete `inv_*` folder names, use that exact list to preserve cross-feature comparability per R-020.13. (2) If neither has been filled (as of 2026-05-16 both list the 3 medium/hard docs as TBD), use this candidate subset matching the R-017.11 constraint of "2 easy + 1 mid-difficulty + 2 challenging": `inv_001_easy`, `inv_002_easy`, `inv_006_medium`, `inv_011_hard`, `inv_012_hard`. (3) Record the actual subset used in `specs/020-vendor-evidence-gate/quickstart.md` Appendix A at landing time so the subset is auditable. **Four-run benchmark discipline (R-020.16)**: (a) invoke `--gpu-warmup` ONCE at the start of the benchmark session to populate MIOpen / COMGR caches and warm engine pools (feature 016 / 019 precedent); (b) run the legacy default (no opt-in) over the 5-doc subset TWICE, discard run 1's timings as additional warm-in, record run 2's `phase_timings.*` as the legacy baseline; (c) run the skip-fallback candidate (opt-in active) over the same subset TWICE, discard run 1, record run 2 as the candidate; (d) for each document, compute the latency delta `(legacy_total - candidate_total)` AND the host's run-to-run jitter band (absolute spread between the two legacy `phase_timings.total` values on that document); (e) report all FOUR runs' `phase_timings.*` values for EVERY emitted key per document (`paddle_import`, `gpu_bind_probe`, `engine_init`, `warmup`, `rasterization`, `per_page_inference`, `artifact_write`, `total` per feature 014/015/016 timing surface) in `quickstart.md` Appendix A, plus the per-doc jitter band on each key (absolute spread between the two legacy runs for that key). **Per-key change assertion (FR-015 per-key change clause, Clarifications Session 2026-05-16 Q1 Option A)**: in the test body, for each suppressed document (one with `evidence_gate_suppressed_fallback_count` incrementing on that doc), assert ONLY `phase_timings.per_page_inference` and `phase_timings.total` decrease vs. legacy run 2 on that document; assert `paddle_import`, `gpu_bind_probe`, `engine_init`, `warmup`, `rasterization`, `artifact_write` stay within the per-key jitter band (defined per key from step (d)). For unsuppressed documents (where candidate gate decision was `borderline` or `insufficient` and the fallback ran), assert all keys stay within their respective jitter bands. The benchmark also emits per-doc gate decisions, per-corpus `evidence_gate_state_counts`, and per-doc `evidence_gate_suppressed_fallback_count` increments; persists the run 2 `run_summary` JSON for use by T056 (no new artifact written to the corpus — Plan § Storage). Cold-cache runs (after `~/.cache/miopen` clearance) are explicitly OUT of FR-015 scope per R-020.16
- [ ] T054 [P] [US7] Author `tests/pipeline_tests/test_quality_gate_two_metric_evidence_gate.py` — mark with `@pytest.mark.gpu`; read `evaluation_run_summary.json` from both the legacy and candidate runs over the 5-doc subset; assert `candidate aggregate field score >= legacy aggregate field score` AND `candidate per-document pass count >= legacy per-document pass count`; fail the test (NOT skip) if either metric regresses, so a failing promotion candidate is visibly rejected (FR-016 / R-020.14 / SC-008)

### Implementation for User Story 7

- [ ] T055 [US7] Confirm `MI-20` invariant holds: at landing, `resolve_evidence_gate_skip_fallback(cli_value=None, env=<empty>)` returns `False`; the opt-in default is OFF on every profile. No code change required if T036 wired the default correctly; if not, fix and re-run T031
- [ ] T056 [US7] If GPU is available at landing, run T053 + T054 and record the resulting quality-gate evidence in `specs/020-vendor-evidence-gate/research.md` Appendix B using the table format documented there (legacy aggregate_score / candidate aggregate_score / legacy pass / candidate pass per document plus TOTAL row); also record the FR-015 benchmark numbers in `specs/020-vendor-evidence-gate/quickstart.md` Appendix A using the table format documented there. If GPU is NOT available, mark Appendix B with the explicit deferral cross-reference per T058 below
- [ ] T057 [US7] If quality-gate passes AND the team chooses to promote: flip the default in `src/ledgerlinc_ocr/preprocessing/evidence_gate_optin.py::resolve_evidence_gate_skip_fallback` (the only place the default lives); record the promotion in `research.md` Appendix B alongside the `evidence_gate_id="v1"` reference (FR-017 / FR-018 / MI-21). **Post-promotion verification (FR-018)**: after flipping the default, run the existing CLI accepting an explicit-off configuration (`LEDGERLINC_EVIDENCE_GATE_SKIP_FALLBACK=0 python -m ledgerlinc_ocr.preprocessing ...` and equivalent for the pipeline CLI); assert the legacy non-behaving behavior is reproduced (no suppression, `evidence_gate_suppressed_fallback_count == 0`); add a regression test under `tests/pipeline_tests/test_legacy_behavior_selectable_after_promotion.py` (or extend T043) that asserts the explicit-off path remains selectable. **If quality-gate fails OR the team makes no promotion decision, this task closes as "default unchanged; legacy behavior preserved" — NOT as a failure.**

**Checkpoint**: US7 complete. Either (a) the quality-gate evidence is recorded and a promotion decision is made, or (b) the deferral is captured in Appendix B + this `tasks.md` (T058 below). The legacy default is preserved on any failure / undecided path.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, deferred-GPU tracking, and final regression verification across all stories.

- [x] T058 If any GPU-marked test (T033, T034 GPU variant, T053, T054) or the FR-015 / FR-016 evaluation was deferred per R-020.15, populate `specs/020-vendor-evidence-gate/quickstart.md` Appendix B with the deferral list (one checkbox per deferred item, cross-referenced to a follow-up GitHub issue or task ID); confirm `research.md` Appendix B carries a one-line cross-reference to the same follow-up identifier (FR-026 / R-020.15). **Surveillance follow-up (Clarifications Session 2026-05-16 Q3 Option D)**: append a separate Appendix B entry naming the over-time-regression surveillance gap for `evidence_gate_suppressed_fallback_count` — checkbox text "Out-of-PR surveillance: recurring GPU benchmark / snapshot-diff / alerting for `evidence_gate_suppressed_fallback_count` regression — DEFERRED to follow-up ops feature; T033 is the in-PR safety net at landing". Cross-reference to a tracking GitHub issue (create one if none exists). This entry persists in Appendix B even if all other GPU deferrals are closed at landing — the surveillance question is a permanent follow-up, not a deferred verification.
- [x] T059 [P] Update `CLAUDE.md` § Recent Changes with a one-line entry for feature 020 (signal-set + gate + skip-fallback opt-in + 0.1.6 → 0.1.7 schema bump); update `CLAUDE.md` § Key References with the new `specs/020-vendor-evidence-gate/` artifact list
- [x] T060 [P] Run the full CPU-safe test suite from the worktree root — `.venv/bin/pytest -m "not gpu"` — and confirm exit 0; capture the result and confirm the legacy regression baseline from T002 has not drifted (every previously-passing test still passes)
- [x] T061 [P] Run `git diff main -- contracts/stage1_vendor_identity/` and confirm an empty diff (SC-010); run `git diff main -- tests/stage1_vendor_identity/` and confirm no committed corpus baseline files were modified (SC-006 / FR-019)
- [x] T062 Walk through `specs/020-vendor-evidence-gate/quickstart.md` Path 1 + Path 5 + Path 6 (the three CPU-safe paths) on the worktree and confirm each produces the documented observable behavior; for Paths 2, 3, 4, 7 mark "deferred — GPU required" if GPU unavailable, and verify each appears in T058's deferral list
- [x] T063 Final pre-PR check: confirm every item in `specs/020-vendor-evidence-gate/checklists/contract.md`, `determinism.md`, `failure-handling.md`, `scope.md`, and `evidence-gate-policy.md` has a corresponding pass/fail signal in the implementation; mark each checklist item `[x]` for items passing OR add an inline comment noting the deferred verification

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Stories (Phases 3–9)**: Depend on Foundational phase; US1 → US2 → US3 → US4 → US5/US6/US7 (US5 and US6 can run after US4 in parallel with each other; US7 depends on US4 + US6 being landable)
- **Polish (Phase 10)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: Depends on T004 only — produces the signal-set computation
- **US2 (P1)**: Depends on US1 (uses `FiveSignalSet`) — produces the v1 decision table
- **US3 (P1)**: Depends on US1 + US2 (uses `evaluate_evidence_gate`) — produces the `run_summary` surface
- **US4 (P1)**: Depends on US1 + US2 + US3 (needs gate + run_summary fields + counter) — produces the skip-fallback behavior
- **US5 (P2)**: Depends on US4 (warn-and-proceed needs the flag) — protects the CPU path
- **US6 (P2)**: Depends on US3 (needs the surface to verify) — protects the canonical schemas
- **US7 (P3)**: Depends on US4 (needs the behavior to evaluate) and US6 (needs schema stability for the evaluator) — produces the promotion-gate evidence

### Within Each User Story

- Test tasks land before their corresponding implementation tasks (TDD): each test MUST fail before the implementation lands
- Module scaffolding (`evidence_gate.py`, `evidence_gate_optin.py`) before integration into CLI / pipeline
- Pure-function helpers (signal computation, decision table, suppression predicate) before orchestration (`pipeline.py`, `cli.py`)
- Single-document path (`runner.py`) and corpus path (`corpus_run.py`) wiring is symmetric and can be done in parallel

### Parallel Opportunities

- **Phase 3 (US1)** tests T005–T008 + T008a + T013a can run in parallel (different files); implementation T009–T013 run sequentially within `evidence_gate.py` (T013a only requires T013 to be in place since it calls `evaluate_evidence_gate`)
- **Phase 4 (US2)** tests T014–T016 can run in parallel; implementation T017–T021 run sequentially within `evidence_gate.py`
- **Phase 5 (US3)** tests T022–T024 can run in parallel; implementation T025–T030 run mostly sequentially (T025 → T026 → T027 in `timing.py`, then T028/T029 in parallel across `corpus_run.py` and `runner.py`)
- **Phase 6 (US4)** tests T031–T035 + T033a + T034a can run in parallel (different files); implementation T036–T042 has a partial order: T036 + T037 [P], then T038/T039 (preprocess CLI) and T041 (pipeline CLI) in parallel, then T040 (`pipeline.py` integration — also lands the injection seam T033a CPU-safe variant needs), then T042 (corpus aggregation)
- **Phase 7 (US5)** tests T043–T045 [P]; T046/T047 are audit tasks that can run in parallel
- **Phase 8 (US6)** tests T048–T050 + T052a [P]; T051/T052 audit tasks in parallel
- **Phase 9 (US7)** tests T053/T054 [P]; T055–T057 sequential
- **Phase 10** T059–T061 [P]; T058 must precede T062 (which references it); T063 last

---

## Parallel Example: User Story 1

```bash
# Author all five CPU-safe unit-test files in parallel (different files, no shared state):
Task: "Author tests/unit/preprocessing/test_evidence_gate_signals_unit.py"
Task: "Author tests/unit/preprocessing/test_evidence_gate_y_threshold_unit.py"
Task: "Author tests/unit/preprocessing/test_evidence_gate_nfkc_unit.py"
Task: "Author tests/unit/preprocessing/test_evidence_gate_module_safety_unit.py"
Task: "Author tests/unit/preprocessing/test_evidence_gate_strategy_uniformity.py"

# Then sequentially build out preprocessing/evidence_gate.py (single file — serial):
Task: "T009 scaffolding (constants, regex, stop-words)"
Task: "T010 FiveSignalSet dataclass"
Task: "T011 _extract_header_band_tokens helper"
Task: "T012 five signal computations"
Task: "T013 evaluate_evidence_gate public API"
```

---

## Parallel Example: User Story 4

```bash
# Author all six test files in parallel (different files, no shared state):
Task: "T031 tests/unit/preprocessing/test_evidence_gate_optin_unit.py"
Task: "T032 tests/unit/preprocessing/test_evidence_gate_suppress_predicate.py"
Task: "T033 tests/pipeline_tests/test_evidence_gate_skip_fallback.py @gpu"
Task: "T034 tests/pipeline_tests/test_evidence_gate_skip_fallback_borderline.py @gpu"
Task: "T034a tests/pipeline_tests/test_evidence_gate_skip_fallback_borderline_cpu.py"
Task: "T035 tests/pipeline_tests/test_evidence_gate_recorded_over_final.py"

# Then build the optin module + predicate in parallel:
Task: "T036 src/ledgerlinc_ocr/preprocessing/evidence_gate_optin.py (new module)"
Task: "T037 should_suppress_fallback predicate in preprocessing/evidence_gate.py"

# CLI wiring across two CLIs in parallel:
Task: "T038 + T039 src/ledgerlinc_ocr/preprocessing/cli.py (flag + warn-and-proceed)"
Task: "T041 src/ledgerlinc_ocr/pipeline/cli.py (flag + warn-and-proceed)"

# Then integrate (single file — serial):
Task: "T040 src/ledgerlinc_ocr/preprocessing/pipeline.py (R-020.7 evaluation order + R-020.8 suppression)"
Task: "T042 src/ledgerlinc_ocr/pipeline/corpus_run.py (per-doc counter aggregation)"
```

---

## Implementation Strategy

### MVP First (US1 + US2 + US3 — the observability slice)

1. Complete Phase 1 (Setup) and Phase 2 (Foundational)
2. Complete Phases 3, 4, 5 (US1, US2, US3) — this delivers deterministic five-signal computation, three-state gate decision, and operator-visible `run_summary` surface
3. **STOP and VALIDATE**: every run of the new binary emits four new `run_summary` fields with correct values; the recorded decision is re-derivable from the recorded signals + the documented v1 table (SC-002 / SC-012). This is a self-contained landing — no behavioral change yet, just observability
4. Deploy as an internal preview if desired; merge if MVP gate is what the team wants this PR to ship

### Full Behavioral Slice (US1–US6)

5. Add Phase 6 (US4) — skip-fallback behavior with opt-in flag (off by default)
6. Add Phase 7 (US5) — CPU/CI safety regression guard
7. Add Phase 8 (US6) — canonical-schema preservation regression guard
8. Final CPU smoke run; merge

### Optional Promotion Slice (US7)

9. If GPU available at landing, run Phase 9 (US7) — record the FR-016 / R-020.14 quality-gate evidence and decide promotion
10. If GPU unavailable, capture the deferral in Phase 10 (T058) per R-020.15

### Parallel Team Strategy

With multiple developers post-Phase 2:

- Developer A: Phases 3 + 4 (US1 + US2 — pure function core, single file)
- Developer B: Phase 5 (US3 — `pipeline/timing.py` + `corpus_run.py` + `runner.py`, shared with Developer A's outputs)
- Developer C: After Phase 5, takes Phase 6 (US4 — CLI wiring + pipeline integration)
- Developer A or D: Phase 7 + Phase 8 (US5 + US6 — mostly regression tests)

---

## Notes

- `[P]` tasks operate on different files with no incomplete dependencies
- `[Story]` label maps each task to its user story for traceability and independent review
- Every user story is independently testable and lands a self-contained increment
- Test tasks MUST be authored and FAIL before their corresponding implementation lands (TDD per the template)
- Commit after each task or logical group; small commits ease ultrareview
- Stop at any checkpoint to validate the story slice in isolation
- GPU-marked tests are skipped (not failed) on no-GPU hosts per `@pytest.mark.gpu` and the existing CI configuration (FR-024 / SC-005)
- The deferral checkbox list in `quickstart.md` Appendix B is the single source of truth for GPU follow-ups; do not duplicate it elsewhere
- Avoid: vague tasks; same-file conflicts inside a parallel set; cross-story dependencies that violate the independent-test criterion
