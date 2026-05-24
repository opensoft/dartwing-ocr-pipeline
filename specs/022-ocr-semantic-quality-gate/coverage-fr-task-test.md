# FR ↔ Task ↔ Test Coverage Matrix — Feature 022 (OCR Semantic Quality Gate)

**Generated**: 2026-05-24 (T070 / SC-010).
**Updated**: 2026-05-24 after Copilot + Codex PR #51 review — test paths reconciled against the actual `tests/` tree.
**Scope**: FR-001 through FR-034 from `spec.md`.
**Sources of truth**: `spec.md` (FR definitions), `tasks.md` (task IDs), real files under `tests/` (test paths). Every test path below was confirmed to exist via `ls` at generation time.

Per FR-032 / SC-010: every active FR MUST map to at least one task AND at least one test. Any row with **zero** tasks or **zero** tests is a spec-or-tasks bug.

## Coverage Table

| FR | Summary | Implementation Tasks | Test Coverage |
|---|---|---|---|
| FR-001 | Optional `semantic_table_truth.json` sidecar separate from `expected.json` | T001 (v1.3.0 contract-set bump), T015–T018 (sidecar validator) | `tests/contract_tests/test_semantic_table_truth_schema.py`; `tests/contract_tests/test_contract_set_v1_3.py::test_v1_3_lists_semantic_table_truth_schema`; `tests/unit/validator/test_semantic_table_truth_validator.py` |
| FR-002 | Row-truth contract (`row_id` + `required_row_text_tokens` mandatory; Q-SEC-2/B safety pattern; normalized decimal strings for currency) | T015, T016 (schema), T018 (row uniqueness) | `tests/contract_tests/test_semantic_table_truth_schema.py::test_f_row_missing_row_id`; `::test_g_row_missing_required_row_text_tokens`; `::test_h_row_with_empty_required_row_text_tokens_array`; `::test_i_row_with_empty_string_token_inside_tokens`; `::test_j_row_with_unit_price_currency_symbol_rejected`; `::test_k_row_with_unit_price_insufficient_cents_rejected`; `::test_l_row_with_unit_price_two_decimals_accepted`; `::test_m_row_with_amount_comma_grouping_rejected`; `::test_n_row_with_additional_unknown_property_rejected`; `::test_r_canonical_row_id_accepted`; `::test_t_row_id_exceeds_max_length_rejected`; `tests/unit/validator/test_semantic_table_truth_validator.py` |
| FR-003 | `document_id` matches folder basename + Q-SEC-2/B safety pattern | T017 (validator wiring) | `tests/contract_tests/test_semantic_table_truth_schema.py::test_q_canonical_document_id_accepted`; `::test_s_path_traversal_document_id_rejected`; `::test_t2_document_id_exceeds_max_length_rejected`; `::test_x_empty_document_id_rejected`; `tests/unit/validator/test_semantic_table_truth_validator.py`; `tests/integration/test_us1_sidecar_validation.py` |
| FR-004 | Reject sidecar on row violation; error names row_id + field + reason | T018 | `tests/unit/validator/test_semantic_table_truth_validator.py`; `tests/integration/test_us1_sidecar_validation.py` |
| FR-005 | No-sidecar path: vendor-identity continues unchanged | T043 (writer respects absence) | `tests/integration/test_us4_non_regression.py::test_as5_no_sidecar_yields_semantic_passed_null`; `::test_as5_no_sidecar_run_summary_semantic_status_not_applicable` |
| FR-006 | `expected.json` shape unchanged | T002 (carry v1.2.0 schemas byte-identical) | `tests/contract_tests/test_contract_set_v1_3.py::test_carried_schemas_byte_identical`; `tests/contract_tests/test_contract_set_v1_3.py::test_expected_schema_byte_identical_f9_resolution` |
| FR-007 | Gate runs automatically when sidecar present (no new CLI flag); body-OCR excludes feature-020 header band | T023 (gate entrypoint), T024 (body OCR builder), T025 (header-band exclusion / MI-6 / MI-7) | `tests/unit/evaluator/test_semantic_quality_body_ocr.py`; `tests/unit/evaluator/test_semantic_quality_report.py`; `tests/integration/test_us2_independent_test.py` |
| FR-008 | No model call, no network, no OCR-confidence-as-truth | T023 (gate impl), T031 (CPU/no-network audit) | `tests/unit/evaluator/test_semantic_quality_module_safety.py`; `tests/unit/preprocessing/test_evidence_gate_module_safety_unit.py`; `tests/unit/preprocessing/test_evidence_gate_cpu_isolation.py` |
| FR-009 | Missing-required-content check via NFKC + casefold + punctuation strip (Unicode `P*`) | T026 (normalization), T027 (required-content check) | `tests/unit/evaluator/test_semantic_quality_normalize.py`; `tests/unit/evaluator/test_semantic_quality_checks.py`; `tests/unit/evaluator/test_semantic_quality_body_ocr.py` |
| FR-010 | Malformed-currency-shape check via anchored money regex against raw tokens | T028 (currency check) | `tests/unit/evaluator/test_semantic_quality_currency.py`; `tests/unit/evaluator/test_semantic_quality_checks.py` |
| FR-011 | Binary row-text-coverage check (no threshold) | T029 (coverage check) | `tests/unit/evaluator/test_semantic_quality_checks.py`; `tests/unit/evaluator/test_semantic_quality_body_ocr.py` |
| FR-012 | Row-alignment failure with deterministic tie-break by serialization order then sidecar order | T030 (alignment + Q7/Q24 tie-break) | `tests/unit/evaluator/test_semantic_quality_anchor.py::TestTieBreak`; `tests/unit/evaluator/test_semantic_quality_anchor.py::TestDeterminism`; `tests/unit/evaluator/test_semantic_quality_checks.py` |
| FR-013 | OCR confidence is supporting evidence only (no per-row promotion) | T032 (supporting_evidence shape) | `tests/unit/evaluator/test_semantic_quality_report.py::TestSupportingEvidenceClosedShape` |
| FR-014 | Deterministic verdict + stable JSON serialization (Q34: sorted keys, UTF-8, LF, trailing newline, Decimal 6-dp ROUND_HALF_EVEN) | T033 (`stable_json.dump_stable`) | `tests/unit/evaluator/test_stable_json.py`; `tests/unit/evaluator/test_semantic_quality_determinism.py`; `tests/integration/test_us4_non_regression.py::test_as1_evaluation_artifacts_are_byte_deterministic` |
| FR-015 | Failed-check records carry category + row_id + field + expected + observed + predicate, in fixed Q17 order, no short-circuit | T044 (writer), T045 (failed-check ordering) | `tests/unit/evaluator/test_semantic_quality_report.py::TestFailedChecksFlatArrayShape`; `tests/unit/evaluator/test_semantic_quality_report.py::TestRowReasonsMultiCategoryAggregation`; `tests/unit/evaluator/test_semantic_quality_checks.py` |
| FR-016 | Closed snake_case status enum (Q26) + any-fail aggregation + Q42 invariant hard-error | T044, T046 (`SemanticGateInvariantError`) | `tests/unit/evaluator/test_semantic_quality_aggregate.py::TestStatusStringLiterals`; `tests/unit/evaluator/test_semantic_table_quality_passed_value_domain.py`; `tests/unit/evaluator/test_semantic_quality_unevaluable.py::TestInvariantHardError`; `tests/unit/evaluator/test_exceptions.py` |
| FR-017 | `evaluation_document.json` carries `semantic_table_quality` (status + failed_checks + row_reasons object + supporting_evidence + cause when unevaluable) | T043 (writer), T044 (row_reasons aggregation) | `tests/contract_tests/test_evaluation_document_v1_3.py`; `tests/unit/evaluator/test_semantic_quality_report.py`; `tests/integration/test_us3_evaluator_reports.py` |
| FR-018 | `evaluation_run_summary.json` top-level `semantic_table_quality_metrics` namespace + `semantic_document_statuses` array | T047 (metrics namespace), T048 (per-doc statuses), T050 (Q39 calibration exclusion) | `tests/unit/evaluator/test_semantic_quality_metrics.py`; `tests/contract_tests/test_evaluation_run_summary_v1_3.py`; `tests/integration/test_us3_evaluator_reports.py` |
| FR-019 | Backward-compat read path: pre-feature reports still validate; absent `semantic_table_quality_passed` interpreted as `null` | T049 (`supports_semantic_quality_fields` version guard) | `tests/contract_tests/test_backward_compat_v1_2.py`; `tests/contract_tests/test_evaluation_document_v1_3.py`; `tests/contract_tests/test_evaluation_run_summary_v1_3.py` |
| FR-020 | Semantic exposed separately from vendor-identity scoring | T043, T047 | `tests/integration/test_us4_non_regression.py::test_as3_vendor_identity_summary_unchanged_with_semantic_sidecar`; `tests/contract_tests/test_evaluation_run_summary_v1_3.py` |
| FR-021 | No change to feature 019 OCR-only fallback | T056 (umbrella non-regression test) | `tests/integration/test_features_019_021_unchanged.py::test_feature_019_ocr_only_module_imports`; `tests/integration/test_features_019_021_unchanged.py::test_no_protected_subtree_files_changed_by_feature_022` |
| FR-022 | No change to feature 020 evidence-gate behavior or run-summary fields | T056 | `tests/integration/test_features_019_021_unchanged.py::test_feature_020_evidence_gate_module_imports`; `tests/integration/test_features_019_021_unchanged.py::test_no_protected_subtree_files_changed_by_feature_022`; `tests/integration/test_us4_non_regression.py::test_as3_vendor_identity_summary_unchanged_with_semantic_sidecar` |
| FR-023 | No change to feature 021 GPU MVP promotion | T056 | `tests/integration/test_features_019_021_unchanged.py::test_feature_021_pipeline_runner_module_imports`; `tests/integration/test_features_019_021_unchanged.py::test_no_protected_subtree_files_changed_by_feature_022` |
| FR-024 | `vendor_identity_passed` meaning + values unchanged | T056 + T054 (US4 byte-identity) | `tests/integration/test_us4_non_regression.py::test_as1_vendor_identity_passed_values_byte_identical`; `tests/integration/test_us4_non_regression.py::test_as1_per_document_vendor_identity_byte_identical` |
| FR-025 | New `semantic_table_quality_passed` sibling field with Q20 value domain | T044, T049 | `tests/unit/evaluator/test_semantic_table_quality_passed_value_domain.py`; `tests/integration/test_us4_non_regression.py::test_as4_failed_semantic_with_passing_vendor_marks_passed_false`; `tests/integration/test_us4_non_regression.py::test_as5_no_sidecar_yields_semantic_passed_null` |
| FR-026 | Degraded-body samples isolated to `tests/stage1_semantic_quality/`; Q25 synthetic US2 fixture; Q40/Q44 uniform PII screening | T011 (corpus root), T012 (synthetic fixture), T061 (labeling-guide), T062 (dataset-layout) | `tests/integration/test_us2_independent_test.py`; `tests/contract_tests/test_folder_contract_v1_3.py` |
| FR-027 | Canonical-pattern allowlist (Q23 / MI-21) partitions corpus into scored vs calibration; default-exclude | T060 (`validate corpus` partition), T050 (metrics exclusion) | `tests/unit/validator/test_corpus_pattern.py`; `tests/integration/test_us5_calibration_handling.py`; `tests/unit/validator/test_validate_corpus_calibration_reporting.py` |
| FR-028 | No in-place rewrite of features 019/020/021 (additive only) | T056 | `tests/integration/test_features_019_021_unchanged.py::test_no_protected_subtree_files_changed_by_feature_022` |
| FR-029 | No learned classifier, no new model runtime, no remote service, no prompt-owned routing | T023 (deterministic gate) + T031 (audit) | `tests/unit/evaluator/test_semantic_quality_module_safety.py`; `tests/unit/preprocessing/test_evidence_gate_module_safety_unit.py` |
| FR-030 | Line-items NOT a stage 1 MVP requirement | T056 (FR-030 negative assertions: grep + schema-byte-identity) | `tests/integration/test_features_019_021_unchanged.py::test_fr030_no_line_item_strings_in_src` (parametrized over 4 forbidden strings); `tests/integration/test_features_019_021_unchanged.py::test_fr030_no_line_items_property_in_v1_3_schemas`; `tests/integration/test_features_019_021_unchanged.py::test_fr030_final_structured_payload_schema_byte_identical_v1_2_to_v1_3`; `tests/integration/test_features_019_021_unchanged.py::test_fr030_expected_schema_byte_identical_v1_2_to_v1_3` |
| FR-031 | No canonical schema/baseline changes beyond Q14 contract bump | T001 (v1.3.0 contract-set bump), T002 (carry v1.2.0 schemas byte-identical), T063 (AMENDMENTS entry) | `tests/contract_tests/test_contract_set_v1_3.py::test_carried_schemas_byte_identical`; `tests/contract_tests/test_contract_set_v1_3.py::test_v1_3_readme_mentions_v1_3_0`; `tests/contract_tests/test_contract_set_v1_3.py::test_amended_schemas_present_at_v1_3` |
| FR-032 | Every active FR has at least one task + one test | T070 (this document) | This file (`coverage-fr-task-test.md`) — meta-coverage validation |
| FR-033 | Semantic verdict NOT integrated into runtime; harness/evaluator/report-only | T056 (no `src/dartwing_ocr/{preprocessing,extract,router,assembler}/` changes) | `tests/integration/test_features_019_021_unchanged.py::test_no_protected_subtree_files_changed_by_feature_022` |
| FR-034 | Air-gapped operation (security-clarify Q-SEC-7/B) — no DNS/socket/HTTP from gate normal path | T031 (named enforcement test per spec FR-034 statement) | `tests/unit/evaluator/test_semantic_quality_module_safety.py`; `tests/unit/preprocessing/test_evidence_gate_module_safety_unit.py` |

## Summary

- **Total FRs**: 34 (FR-001 through FR-034)
- **FRs with ≥1 implementation task**: 34 / 34 ✓
- **FRs with ≥1 real (existing) test**: 34 / 34 ✓
- **Uncovered FRs**: 0 — SC-010 PASS.

Every test file referenced in this matrix exists in `tests/`. Every test function reference (`::test_name`) exists in the named file. Confirm via `git ls-files tests/` + `grep "^def test_" <file>`.

## Notes on tasks that span multiple FRs

- **T031** (CPU-only / no-Paddle / no-network audit) is the named single enforcement test for FR-008, FR-029, and FR-034 per the spec's own statement ("T031 IS the named enforcement test for FR-034; no new test task is added").
- **T056** (`test_features_019_021_unchanged.py`) is the umbrella non-regression test for FR-021, FR-022, FR-023, FR-028, FR-030, and FR-033 — by design, it makes a single git-history-aware sweep over `src/dartwing_ocr/` and asserts no protected-subtree changes plus the FR-030 line-items negative assertions in one place.
- **T070** (this file) implements FR-032 by enumerating the FR→task→test map; it is meta-coverage validation and the file itself IS the test artifact (the document existing with zero `0 / N ✗` rows IS the pass).

## How to re-derive this matrix

1. Read FR list from `spec.md` (`grep -E "^- \*\*FR-[0-9]" specs/022-ocr-semantic-quality-gate/spec.md`).
2. Read task list from `tasks.md` (Phase 3–8 tasks).
3. Walk `tests/{contract_tests,unit,integration}/` for test files; cross-reference filenames AND `^def test_` function names against the FR each test docstring or filename names.
4. **Verify every reference EXISTS** before committing. The mechanically correct verification command for both function and class selectors is:

   ```bash
   .venv/bin/python -m pytest --collect-only \
     <every test_path or test_path::node referenced in this matrix> \
     --quiet
   ```

   pytest collection succeeds only when every supplied `file::node` resolves; a typo in a function name OR a class name produces a collection error and fails the command. Run this from the repo root before committing any change to this matrix.

   For ad-hoc file-existence checks: `git ls-files tests/` for files; `grep -nE "^def test_" <file>` for top-level functions; `grep -nE "^class Test" <file>` for class selectors.

   The initial 2026-05-24 draft of this matrix shipped with fabricated test paths and was rewritten after Copilot + Codex PR #51 review caught it.

If a future amendment adds an FR-035, append a row to the table and recompute the summary; if a future amendment removes an FR, strike its row and update the summary count.
