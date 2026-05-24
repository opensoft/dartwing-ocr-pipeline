# FR ↔ Task ↔ Test Coverage Matrix — Feature 022 (OCR Semantic Quality Gate)

**Generated**: 2026-05-24 (T070 / SC-010).
**Scope**: FR-001 through FR-034 from `spec.md`.
**Source of truth**: `spec.md` (FR definitions), `tasks.md` (task IDs), `tests/` (test file paths).

Per FR-032 / SC-010: every active FR MUST map to at least one task AND at least one test. Any row with **zero** tasks or **zero** tests is a spec-or-tasks bug.

## Coverage Table

| FR | Summary | Implementation Tasks | Test Coverage |
|---|---|---|---|
| FR-001 | Optional `semantic_table_truth.json` sidecar separate from `expected.json` | T015 (sidecar loader), T016 (schema), T017 (validator wiring) | `tests/unit/validator/test_semantic_table_truth_*.py`; `tests/contract_tests/test_semantic_table_truth_schema.py` |
| FR-002 | Row-truth contract (`row_id` + `required_row_text_tokens` mandatory; Q-SEC-2/B safety pattern) | T015, T016, T018 (row uniqueness check) | `tests/unit/validator/test_semantic_table_truth_row_shape.py`; `tests/unit/validator/test_semantic_table_truth_security_pattern.py` |
| FR-003 | `document_id` matches folder basename + Q-SEC-2/B safety pattern | T017 | `tests/unit/validator/test_semantic_table_truth_document_id_mismatch.py` |
| FR-004 | Reject sidecar on row violation; error names row_id + field + reason | T018 | `tests/unit/validator/test_semantic_table_truth_row_violation_messages.py` |
| FR-005 | No-sidecar path: vendor-identity continues unchanged | T043 (writer respects absence) | `tests/integration/test_us4_non_regression.py::test_as5_*` |
| FR-006 | `expected.json` shape unchanged | T015 (no schema edit) | `tests/contract_tests/test_carried_schemas_byte_identical.py` |
| FR-007 | Gate runs automatically when sidecar present (no new CLI flag); body-OCR excludes feature-020 header band | T023, T024 (gate entrypoint), T025 (header-band exclusion) | `tests/unit/evaluator/test_semantic_gate_entrypoint.py`; `tests/unit/evaluator/test_semantic_gate_header_band_exclusion.py` |
| FR-008 | No model call, no network, no OCR-confidence-as-truth | T023 (gate impl), T031 (CPU/no-network audit) | `tests/unit/evaluator/test_semantic_quality_module_safety.py` |
| FR-009 | Missing-required-content check via NFKC + casefold + punctuation strip (Unicode `P*`) | T026 (normalization), T027 (required-content check) | `tests/unit/evaluator/test_semantic_normalization.py`; `tests/unit/evaluator/test_check_missing_required_content.py` |
| FR-010 | Malformed-currency-shape check via anchored money regex against raw tokens | T028 (currency check) | `tests/unit/evaluator/test_check_malformed_currency_shape.py` |
| FR-011 | Binary row-text-coverage check (no threshold) | T029 (coverage check) | `tests/unit/evaluator/test_check_row_text_coverage_gap.py` |
| FR-012 | Row-alignment failure with deterministic tie-break by serialization order then sidecar order | T030 (alignment check + Q7/Q24 tie-break) | `tests/unit/evaluator/test_check_row_alignment_failure.py`; `tests/unit/evaluator/test_alignment_tie_break_determinism.py` |
| FR-013 | OCR confidence is supporting evidence only (no per-row promotion) | T032 (supporting_evidence shape) | `tests/unit/evaluator/test_supporting_evidence_shape.py` |
| FR-014 | Deterministic verdict + stable JSON serialization (Q34: sorted keys, UTF-8, LF, trailing newline, Decimal 6-dp ROUND_HALF_EVEN) | T033 (`stable_json.dump_stable`) | `tests/unit/evaluator/test_stable_json.py`; `tests/integration/test_us4_non_regression.py::test_as1_evaluation_artifacts_are_byte_deterministic` |
| FR-015 | Failed-check records carry category + row_id + field + expected + observed + predicate, in fixed Q17 order, no short-circuit | T044 (writer), T045 (failed-check ordering) | `tests/unit/evaluator/test_failed_check_record_shape.py`; `tests/unit/evaluator/test_failed_check_q17_ordering.py` |
| FR-016 | Closed snake_case status enum (Q26) + any-fail aggregation + Q42 invariant hard-error | T044, T046 (`SemanticGateInvariantError`) | `tests/unit/evaluator/test_semantic_table_quality_passed_value_domain.py`; `tests/unit/evaluator/test_semantic_gate_invariant_error.py` |
| FR-017 | `evaluation_document.json` carries `semantic_table_quality` (status + failed_checks + row_reasons object + supporting_evidence + cause when unevaluable) | T043 (writer), T044 (row_reasons aggregation) | `tests/unit/evaluator/test_evaluation_document_semantic_block.py`; `tests/contract_tests/test_evaluation_document_v1_3_schema.py` |
| FR-018 | `evaluation_run_summary.json` top-level `semantic_table_quality_metrics` namespace + `semantic_document_statuses` array | T047 (metrics namespace), T048 (per-doc statuses), T050 (Q39 calibration exclusion) | `tests/unit/evaluator/test_semantic_quality_metrics.py`; `tests/contract_tests/test_evaluation_run_summary_v1_3_schema.py` |
| FR-019 | Backward-compat read path: pre-feature reports still validate; absent `semantic_table_quality_passed` interpreted as `null` | T049 (`supports_semantic_quality_fields` version guard) | `tests/unit/evaluator/test_evaluator_backward_compat_read_path.py` |
| FR-020 | Semantic exposed separately from vendor-identity scoring | T043, T047 | `tests/integration/test_us4_non_regression.py::test_as3_*`; `tests/contract_tests/test_evaluation_run_summary_v1_3_schema.py` |
| FR-021 | No change to feature 019 OCR-only fallback | T056 (no-rewrite assertion) | `tests/integration/test_features_019_021_unchanged.py` |
| FR-022 | No change to feature 020 evidence-gate behavior or run-summary fields | T056 | `tests/integration/test_features_019_021_unchanged.py`; `tests/integration/test_us4_non_regression.py::test_as3_*` |
| FR-023 | No change to feature 021 GPU MVP promotion | T056 | `tests/integration/test_features_019_021_unchanged.py` |
| FR-024 | `vendor_identity_passed` meaning + values unchanged | T056 (FR-024 byte-identity assertion) | `tests/integration/test_us4_non_regression.py::test_as1_vendor_identity_passed_values_byte_identical` |
| FR-025 | New `semantic_table_quality_passed` sibling field with Q20 value domain | T044, T049 | `tests/unit/evaluator/test_semantic_table_quality_passed_value_domain.py`; `tests/integration/test_us4_non_regression.py::test_as4_*`, `::test_as5_*` |
| FR-026 | Degraded-body samples isolated to `tests/stage1_semantic_quality/`; Q25 synthetic US2 fixture; Q40/Q44 uniform PII screening | T011 (corpus root), T012 (synthetic fixture), T013 (labeling-guide update T061), T014 (dataset-layout update T062) | `tests/contract_tests/test_semantic_quality_corpus_root_present.py`; `tests/unit/validator/test_us2_synthetic_fixture_round_trip.py` |
| FR-027 | Canonical-pattern allowlist (Q23 / MI-21) partitions corpus into scored vs calibration; default-exclude | T060 (`validate corpus` partition) + T050 (metrics exclusion) | `tests/unit/validator/test_corpus_pattern.py`; `tests/integration/test_us5_calibration_handling.py`; `tests/unit/validator/test_validate_corpus_calibration_reporting.py` |
| FR-028 | No in-place rewrite of features 019/020/021 (additive only) | T056 | `tests/integration/test_features_019_021_unchanged.py` |
| FR-029 | No learned classifier, no new model runtime, no remote service, no prompt-owned routing | T023 (deterministic gate) + T031 (audit) | `tests/unit/evaluator/test_semantic_quality_module_safety.py` |
| FR-030 | Line-items NOT a stage 1 MVP requirement | T056 (FR-030 negative assertions: grep + schema-byte-identity) | `tests/integration/test_features_019_021_unchanged.py::test_no_line_item_strings_in_feature_022_code`; `::test_v1_3_final_structured_payload_byte_identical_to_v1_2` |
| FR-031 | No canonical schema/baseline changes beyond Q14 contract bump | T001 (v1.3.0 contract-set bump), T002 (carry v1.2.0 schemas byte-identical), T063 (AMENDMENTS entry) | `tests/contract_tests/test_carried_schemas_byte_identical.py`; `tests/contract_tests/test_v1_3_readme_mentions_v1_3_0.py` |
| FR-032 | Every active FR has at least one task + one test | T070 (this document) | This file (`coverage-fr-task-test.md`) — meta-coverage validation |
| FR-033 | Semantic verdict NOT integrated into runtime; harness/evaluator/report-only | T056 (no `src/dartwing_ocr/{preprocessing,extract,router,assembler}/` changes) | `tests/integration/test_features_019_021_unchanged.py::test_no_protected_subtree_files_changed_by_feature_022` |
| FR-034 | Air-gapped operation (security-clarify Q-SEC-7/B) — no DNS/socket/HTTP from gate normal path | T031 (named enforcement test per spec FR-034 statement) | `tests/unit/evaluator/test_semantic_quality_module_safety.py` (covers no-network audit per MI-1) |

## Summary

- **Total FRs**: 34 (FR-001 through FR-034)
- **FRs with ≥1 implementation task**: 34 / 34 ✓
- **FRs with ≥1 test**: 34 / 34 ✓
- **Uncovered FRs**: 0 — SC-010 PASS.

## Notes on tasks that span multiple FRs

- **T031** (CPU-only / no-Paddle / no-network audit) is the named single enforcement test for FR-008, FR-029, and FR-034 per the spec's own statement ("T031 IS the named enforcement test for FR-034; no new test task is added").
- **T056** (`test_features_019_021_unchanged.py`) is the umbrella non-regression test for FR-021, FR-022, FR-023, FR-028, FR-030, and FR-033 — by design, it makes a single git-history-aware sweep over `src/dartwing_ocr/` and asserts no protected-subtree changes plus the FR-030 line-items negative assertions in one place.
- **T070** (this file) implements FR-032 by enumerating the FR→task→test map; it is meta-coverage validation and the file itself IS the test artifact (the document existing with zero `0 / N ✗` rows IS the pass).

## How to re-derive this matrix

1. Read FR list from `spec.md` (`grep -E "^- \*\*FR-[0-9]" specs/022-ocr-semantic-quality-gate/spec.md`).
2. Read task list from `tasks.md` (Phase 3–8 tasks).
3. Walk `tests/{contract_tests,unit,integration}/` for test files whose filename or top-level docstring names the FR.
4. Cross-reference and update any row where an FR no longer maps to a task or test — that is a real bug.

If a future amendment adds an FR-035, append a row to the table and recompute the summary; if a future amendment removes an FR, strike its row and update the summary count.
