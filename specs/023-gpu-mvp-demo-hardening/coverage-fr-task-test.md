# Coverage matrix — Feature 023 GPU MVP Demo Hardening

**Generated:** 2026-05-25 (post-US2/US3/US4 + analyze-remediation pass)
**Mirrors:** `specs/022-ocr-semantic-quality-gate/coverage-fr-task-test.md` convention (audit walkthrough 2026-05-25 Q8).

One row per requirement (FR / SC) mapping to (a) the implementation task IDs that satisfy it and (b) the test task / test function IDs that exercise it. Test functions are listed by their pytest dotted path (relative to `tests/integration/gpu_demo/`). Workstation-only tests are marked `[gpu]`.

## Functional Requirements

| FR | Description | Implementation tasks | Source files | Test functions |
|---|---|---|---|---|
| FR-001 | Canonical demo CLI entry point | T001, T002, T005, T016, T035 | `src/dartwing_ocr/gpu_demo/__main__.py`, `cli.py`, `pyproject.toml` `[project.scripts]` | `test_cli_smoke.py::test_help_exits_zero`, `test_cli_smoke.py::test_version_exits_zero_and_prints_version` |
| FR-002 | Run from Paddle ROCm venv + invoke preflight | T025, T026 | `readiness/interpreter.py`, `readiness/paddle_preflight.py` | `test_readiness_failures.py::test_interpreter_venv_failure_class`, `test_readiness_failures.py::test_readiness_failure_class[paddle_cpu_only-…]` |
| FR-003 | Report includes interpreter path | T009, T034 | `report.py:DemoRunReport.interpreter_path`, `orchestrator.py` | `test_report_shape.py::test_success_outcome` |
| FR-004 | Ollama readiness independent from Paddle | T027 | `readiness/ollama_reach.py` | `test_readiness_failures.py::test_readiness_failure_class[ollama_unreachable-…]` |
| FR-005 | Active voter config + size_vram == size GPU placement + `--voter-config` override | T013, T029 | `voter_config_loader.py`, `readiness/ollama_placement.py` | `test_readiness_failures.py::test_readiness_failure_class[ollama_partial_placement-…]`, `test_check_only.py::test_invalid_voter_config_exits_2`, `test_voter_config.py::test_multi_voter_warns_and_uses_first` |
| FR-006 | `OLLAMA_BASE_URL` + `OLLAMA_CONTEXT_LENGTH` readiness check | T027, T030 | `readiness/ollama_reach.py`, `readiness/ollama_ctx_len.py` | `test_readiness_failures.py::test_readiness_failure_class[ollama_ctx_too_small-…]`, `test_ollama_base_url.py::test_demo_ignores_other_ollama_urls` |
| FR-007 | Fail fast before any pipeline artifact write | T034, T042 | `orchestrator.py` (early-exit on readiness fail) | `test_check_only.py::test_check_only_fail_ollama_unreachable`, `test_readiness_failures.py::*` |
| FR-008 | 600 s bounded pipeline timeout, exit 3 on timeout | T032, T034 | `orchestrator.py` (SIGALRM + `_run_phase` TimeoutError re-raise) | `test_runtime_outcomes.py::test_timeout_sets_stalled_phase` (parameterized × 4 phases) |
| FR-009 | Produce + schema-validate 4 canonical artifacts | T031, T034 | `readiness/schema_validation.py`, stub composer in `conftest.py` | `test_cli_flow.py::test_happy_path`, `test_exit_codes.py::test_exit_5_schema_validation_failed` |
| FR-010 | Runtime vs quality distinct fields + `quality_status` closed enum | T009, T017, T060, T063 | `report.py`, `quality_status.py`, `quality_derivation.py`, `orchestrator.py` | `test_report_shape.py::test_success_outcome`, `test_quality_status.py::*` (9 tests), `test_with_evaluator.py::*` (3 tests) |
| FR-011 | `header-first-v1` default + `--preset full-ocr` opt-in | T016, T034 | `cli.py` (argparse choices), `orchestrator.py` | `test_cli_smoke.py::test_help_exits_zero` (flag visible in help) |
| FR-012 | No silent CPU fallback (readiness + post-run interrogation) | T062, T064 | `cpu_fallback.py`, `orchestrator.py` step 6b | `test_cpu_fallback.py::test_post_run_probe_detects_ollama_fallback`, `test_cpu_fallback.py::test_post_run_probe_unreachable_keeps_success` |
| FR-013 | No Jetson behavior | — (negative requirement) | (Out of Scope §) | (no test required for negative requirement) |
| FR-014 | No contract-set bump | — (negative requirement) | (Out of Scope §; `contract_set_version` unchanged at v1.3.0) | (validator suite confirms v1.3.0 unchanged) |
| FR-015 | No line-item extraction quality work | — (negative requirement) | (Out of Scope §) | (no test required) |
| FR-016 | Closed readiness vocabulary + fixed execution order + skip-on-fail | T033, T044 | `readiness/runner.py`, `enums.py` `READINESS_CHECK_ORDER`, every readiness module | `test_readiness_order.py::test_skip_on_upstream_fail` (parameterized × 5 checks), `test_readiness_failures.py::*` (6 classes covered) |
| FR-017 | Deterministic eager-delete + symlink-escape guard + partial-delete failure | T018, T034, T066–T069 | `folder_canonicalize.py`, `orchestrator.py` | `test_eager_delete.py::test_symlink_escape_aborts_exit_2`, `test_eager_delete.py::test_partial_delete_failure_aborts_exit_2`, `test_eager_delete.py::test_idempotent_on_missing_files`, `test_eager_delete.py::test_preserves_non_canonical_files` |
| FR-018 | `--check-only` readiness-only mode | T016, T042 | `cli.py`, `orchestrator.py` `--check-only` branch | `test_check_only.py::test_check_only_pass_emits_stable_shape`, `test_check_only.py::test_check_only_within_10s_warm`, `test_check_only.py::test_check_only_does_not_check_source_pdf` |
| FR-019 | Always-emit stable-shape JSON line on stdout; stderr separate | T009, T010, T034, T015 | `report.py`, `serialization.py`, `orchestrator.py`, `log.py` | `test_check_only.py::test_check_only_pass_emits_stable_shape` (17 keys), `test_report_shape.py::test_success_outcome`, `test_float_precision.py::*`, `test_diagnostics.py::test_stderr_mirrors_json_diagnostic_for_ollama_version` |
| FR-020 | Closed `runtime_outcome` enum + `stalled_phase` for timeout | T008, T034, T050 | `enums.py`, `orchestrator.py` | `test_runtime_outcomes.py::test_timeout_sets_stalled_phase` (× 4 phases), `test_runtime_outcomes.py::test_failed_at_phase` (× 4 phases) |
| FR-021 | Closed exit-code table 0–5 | T007, T034 | `exit_codes.py`, `orchestrator.py` `_exit_code_for` | `test_exit_codes.py::test_exit_0_success`, `test_exit_codes.py::test_exit_1_readiness_failed`, `test_exit_codes.py::test_exit_2_invalid_input_voter_config`, `test_exit_codes.py::test_exit_2_invalid_input_missing_source_pdf`, `test_exit_codes.py::test_exit_4_pipeline_runtime_error`, `test_exit_codes.py::test_exit_5_schema_validation_failed`, `test_runtime_outcomes.py::test_timeout_sets_stalled_phase` (exit 3) |
| FR-022 | `--with-evaluator` default off + warn-and-skip on missing sidecar | T061, T063 | `evaluator_subprocess.py`, `orchestrator.py` | `test_with_evaluator.py::test_invoke_evaluator_sidecar_missing`, `test_with_evaluator.py::test_warn_and_skip_no_sidecar_via_cli`, `test_with_evaluator.py::test_evaluator_subprocess_failure_keeps_source_gate` |
| FR-023 | Minimum Ollama version + named `ollama-version` check | T028 | `readiness/ollama_version.py` | `test_readiness_failures.py::test_readiness_failure_class[ollama_old_version-…]`, `test_readiness_order.py::test_skip_on_upstream_fail[ollama-version-…]` |
| FR-024 | `schema_version` + `pipeline_version` fields | T009, T011 | `report.py`, `version.py` | `test_report_shape.py::test_success_outcome`, `test_check_only.py::test_check_only_pass_emits_stable_shape` |
| FR-025 | `phase_timings` 4 keys + `total_runtime_seconds` | T009, T034 | `report.py`, `orchestrator.py` | `test_check_only.py::test_check_only_pass_emits_stable_shape` (all null under `--check-only`), `test_cli_flow.py::test_happy_path` (populated on success), `test_runtime_outcomes.py::test_failed_at_phase` (mixed null per phase), `test_float_precision.py::*` |
| FR-025a | `--check-only` runtime/quality/timing/artifact fields null | T042 | `orchestrator.py` `--check-only` branch | `test_check_only.py::test_check_only_pass_emits_stable_shape` |
| FR-026 | Readiness summary with all 8 check statuses + failing check name | T033 | `readiness/runner.py` | `test_check_only.py::test_check_only_pass_emits_stable_shape`, `test_readiness_order.py::*` |
| FR-027 | `--document-folder` default + missing `source.pdf` → exit 2 | T016, T034, T043 | `cli.py`, `orchestrator.py` source.pdf gate | `test_exit_codes.py::test_exit_2_invalid_input_missing_source_pdf`, `test_check_only.py::test_check_only_does_not_check_source_pdf` |

## Success Criteria

| SC | Description | Implementation tasks | Test functions |
|---|---|---|---|
| SC-001 | Fresh operator end-to-end via runbook | T072 (runbook), audit-walkthrough Q11 (colleague dry-run appendix) | Colleague Dry-Run Sign-Off appendix in `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md` (process gate, not a code test) |
| SC-002 | 4 artifacts schema-valid on success | T031, T034 | `test_cli_flow.py::test_happy_path`, `test_exit_codes.py::test_exit_5_schema_validation_failed` |
| SC-003 | Named readiness classes detected before pipeline | T040 (parametrize), T044 (closed diag shape) | `test_readiness_failures.py::*` (6 classes), `test_check_only.py::test_check_only_fail_ollama_unreachable` |
| SC-004 | No CPU-mode result reported as GPU success | T062, T064 | `test_cpu_fallback.py::test_post_run_probe_detects_ollama_fallback` (success rewritten to `failed_at_extraction` + `failure_kind: "cpu-fallback-detected"`) |
| SC-005 | Pipeline-runtime + extraction-quality as distinct fields | T009, T010, T060 | `test_report_shape.py::test_success_outcome` |
| SC-006 | Three-run stability gate | T073 (workstation manual smoke `@pytest.mark.gpu`) | Workstation manual run per `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md` §"Three-Run Stability Smoke Procedure (SC-006)"; tracked as issue #54 |
| SC-007 | `--check-only` ≤ 10 s warm | T038 | `test_check_only.py::test_check_only_within_10s_warm` |
| SC-008 | CPU-isolated pytest + workstation manual smoke | every test task; `pyproject.toml` `gpu` marker | full `tests/integration/gpu_demo/` suite (60 tests pass `pytest -m "not gpu"`); workstation manual via T073 (issue #54) |
| SC-009 | Stdout JSON-only parseable on every run mode | T010, T019 | `test_check_only.py::test_check_only_pass_emits_stable_shape`, `test_cli_flow.py::test_happy_path`, all tests parse stdout as JSON |
| SC-010 | Overwrite scope = 4 canonical artifacts only | T017, T069 | `test_eager_delete.py::test_preserves_non_canonical_files` |

## User stories

| US | Story | Implementation phase | Test files |
|---|---|---|---|
| US1 | Canonical one-command GPU MVP demo | Phase 3 (T020–T035) | `test_cli_flow.py`, `test_report_shape.py`, `test_cli_smoke.py` |
| US2 | Fail-fast GPU readiness preflight | Phase 4 (T036–T044) | `test_check_only.py`, `test_readiness_order.py`, `test_readiness_failures.py`, `test_exit_codes.py` |
| US3 | Specific readiness diagnostics | Phase 5 (T045–T052) | `test_diagnostics.py`, `test_runtime_outcomes.py`, `test_schema_validation.py` |
| US4 | Runtime success separated from extraction quality | Phase 6 (T053–T064) | `test_quality_status.py`, `test_with_evaluator.py`, `test_cpu_fallback.py` |

## R-023 decisions

Every research decision maps to either an implementation task or a test:

| R-023.N | Decision | Lands at |
|---|---|---|
| R-023.1 | In-process pipeline composition via `PipelineComposer` Protocol | T034 + T034a (#53) |
| R-023.2 | `pipeline_version` from `importlib.metadata` | T011 |
| R-023.3 | Exception → exit-code mapping | T034 + `contracts/cli-contract.md` |
| R-023.4 | Test stubbing strategy (`httpx.MockTransport` + monkeypatch) | T021, T022 |
| R-023.5 | `@pytest.mark.gpu` marker for workstation-only tests | T006 |
| R-023.6 | UUID4 `run_id` + 8-hex stderr prefix | T014 |
| R-023.7 | Fixed `INFO:`/`WARN:`/`ERROR:` severity prefixes; line-buffered stderr | T015 |
| R-023.8 | No per-phase sub-budgets; only 600 s aggregate | T034 |
| R-023.9 | SC-007 warm-only 10 s; 30 s cold-cache informal target | runbook §Prerequisites |
| R-023.10 | Minimum Ollama version pinned at `0.4.0` | T028, `enums.MIN_OLLAMA_VERSION` |
| R-023.11 | `CheckDiagnostic` closed-key shape | T044 (every readiness module emits structured diagnostic) |
| R-023.12 | Stable-key JSON serialization (`sort_keys=False`, `ensure_ascii=False`) | T010 |
| R-023.13 | `--with-evaluator` subprocess: `python -m dartwing_ocr.evaluator evaluate-document --folder <doc> --quiet` cwd=<doc> 60 s | T061 |
| R-023.14 | `OLLAMA_BASE_URL` (default `http://localhost:11434`) as Ollama discovery | `enums.DEFAULT_OLLAMA_BASE_URL`, T027 |
| R-023.15 | Post-run two-probe device interrogation; 2 s per-probe + 5 s aggregate | T062, T064 |
| R-023.16 | CPU test suite ≤ 60 s wall-clock | actual: ~1 s for 60 tests |
| R-023.17 | Runbook extended in place with 4 new sections + appendix | T072 |
| R-023.18 | Pytest fixture corpus — symlinks to canonical fixture | `tests/integration/gpu_demo/fixtures/{ok,symlink_escape}/` |
| R-023.19 | Not composable with feature 011 stage-runtime profiles | (design decision; no code) |
| R-023.20 | `quality_status` derivation truth-table + evaluator downgrade-only rule | T017, T060, T063 |
| R-023.21 | Float precision: round wall-clock to 3 dp | `serialization.round_wall_clock`, T070 |

## Audit walkthrough Q1–Q12 (2026-05-25)

All 12 questions integrated into spec / plan / contracts / tasks per the audit walkthrough file (`audit-walkthrough-2026-05-25.md`); see column "Implementation tasks" rows above for the specific FR/SC mappings.

## Test count summary

- **60 tests passing** across 17 test files (`pytest tests/integration/gpu_demo/ -m "not gpu"`)
- **0 workstation-only tests landed yet** — T073 (issue #54) is the lone `@pytest.mark.gpu` test, deferred to workstation execution
- **0 `xfail`** — every test is expected to pass on CPU CI

## Open work (tracked separately)

- **Issue #53** — T034a real `_DefaultPipelineComposer` wiring (workstation-side)
- **Issue #54** — T073 three-run stability `@pytest.mark.gpu` smoke (workstation-side)

These are the only two open items at feature-023 release. Each requires the ROCm + host Ollama workstation environment and is tracked via GitHub issue with full acceptance criteria and dependencies.
