# Test-quality review — feature 023

**Date:** 2026-05-25
**Reviewer:** test-quality-reviewer-023 agent (general-purpose, swarm review)
**Branch:** 023-gpu-mvp-demo-hardening @ 1d56554
**Test count:** 60 passing / 0 failing / 0 xfail / 0 skipped (-m "not gpu")

## Summary
17 findings: 0 CRITICAL, 4 HIGH, 7 MEDIUM, 6 LOW.

Status: **NEEDS-ATTENTION** (no blockers; the suite is broadly faithful and the
SIGALRM timeout-path test really does exercise the orchestrator's
TimeoutError → `runtime_outcome="timeout"` mapping. Findings are coverage gaps,
mock-fidelity oversights, and brittleness — not "tautology" defects).

## Findings

| ID | Severity | Category | Test file | Summary | Recommendation |
|----|----------|----------|-----------|---------|----------------|
| T1  | HIGH    | coverage-gap       | test_quality_status.py / test_with_evaluator.py | No end-to-end test of the SUCCESSFUL `--with-evaluator` path through the CLI: every CLI evaluator test forces `subprocess.run` to fail or sidecar to be missing, so `quality_status_source == "evaluator"` is never asserted via the orchestrator. | Add a CLI test where `subprocess.run` is stubbed to return success and an `evaluation_document.json` with `semantic_table_quality.passed: true`; assert source flips to `"evaluator"`. |
| T2  | HIGH    | coverage-gap       | test_readiness_order.py:96 / test_readiness_failures.py:121 | `test_skip_on_upstream_fail` parametrize SKIPS `interpreter/venv` (5 of 6 pre-pipeline checks). The comment at L88 says "tested separately" but `test_interpreter_venv_failure_class` only asserts the failure diagnostic — never asserts that checks 2-6 are then `skipped`. So FR-026's "skip later checks after fail" is unverified for the first check. | Either (a) add `interpreter/venv` to the parametrize matrix (requires undoing `force_venv_interpreter` cleanly), or (b) add an assertion in `test_interpreter_venv_failure_class` that statuses 2-6 are all `"skipped"`. |
| T3  | HIGH    | coverage-gap       | test_runtime_outcomes.py | The `runtime_outcome` closed enum has 6 values: `success`, `failed_at_{preprocess,extraction,routing,final_payload}`, `timeout`. Tests cover all 6, but `runtime_outcome == "failed_at_final_payload"` triggered by **schema-validation failure** (per orchestrator L617) is not asserted anywhere — `test_exit_5_schema_validation_failed` only asserts the exit code, not `runtime_outcome`. | Extend `test_exit_5_schema_validation_failed` (or `test_schema_validation.py::test_multi_artifact_failure`) to assert `parsed["runtime_outcome"] == "failed_at_final_payload"` and `failure_kind == "artifact-schema-validation-failed"`. |
| T4  | HIGH    | mock-fidelity      | conftest.py:33-65 (`_StubPreflightReadout`) | Stub `PreflightReadout` exposes only `state` + `recommendation`. The real dataclass (preflight.py:102-109) has a third REQUIRED field `evidence: PreflightEvidence`. If `paddle_preflight.py` is ever extended to inspect `readout.evidence` (a plausible future change; the production module already calls `readout.state.value` and `readout.recommendation`), the stub will silently fail and tests will report green. | Add `evidence=None` to the stub OR mirror the real dataclass via `dataclasses.replace`-friendly construction. The docstring also references `PASS_ROCM_GPU` which does not exist in `PreflightState` — fix to `PPSTRUCTUREV3_INIT_SUCCEEDED`. |
| T5  | MEDIUM  | mock-fidelity      | conftest.py:106-118 (`ollama_http_stub._mock_get`) | The mock `httpx.get` accepts `(url, timeout=2.0, **_)` but the production calls in `ollama_reach`/`ollama_version`/`cpu_fallback` use `httpx.get(url, timeout=2.0)` — fine — but the mock IGNORES the timeout parameter. Tests cannot exercise the case where `httpx.get` itself raises `httpx.ReadTimeout` mid-call versus `ConnectError`. The handler-based scheme covers one branch. | Add a handler variant that raises `httpx.ReadTimeout` (vs the existing `ConnectError`) to exercise the second `httpx.HTTPError` subclass branch in `ollama_reach.py:38` and `ollama_version.py:39`. |
| T6  | MEDIUM  | tautological-leaning | test_cli_flow.py::test_happy_path_failed_at_phase | Test stubs the composer to raise at `extraction`, then asserts `runtime_outcome == "failed_at_extraction"`. The orchestrator's `_run_phase` (L518-552) is exercised, but the assertion `phase_timings["extraction"] is not None` only proves the stub composer's `_maybe_fail` was reached — it does not prove timing was correctly attached to the failing phase vs. e.g., the next phase. Not strictly tautological (the closure-based phase mapping IS exercised), but the assertion strength is weak: a regression where `timings[phase]` was recorded against the NEXT phase wouldn't fail this test reliably. | Add an explicit assertion that timings of EARLIER phases are non-null AND less than the failing phase's timing; the current `phases_order` slice in `test_failed_at_phase` already does this for later phases — extend to earlier. |
| T7  | MEDIUM  | mock-fidelity      | conftest.py:150-216 (`_StubPipelineComposer`) | Stub artifacts write `{"kind": "preprocess_output", "stub": true}` etc. The v1.3.0 contract schemas require many additional fields (page array, source_pdf, run_summary nesting, etc.). `bypass_schema_validation` papers over this for happy-path tests, but the stub's "kind" string doesn't even match the contract values (e.g., `preprocess_output.json` schema doesn't use that `kind` literal at the top level). This means happy-path tests assert artifact files EXIST but not that they have meaningful content — workstation T073 is the only thing that can catch real schema regressions. The audit-walkthrough flagged this as "by design" but it limits the suite's value as a regression gate. | Either (a) author one realistic minimal artifact per kind that passes v1.3.0 schemas and use it across all happy-path tests (so `bypass_schema_validation` can be retired for most tests), or (b) document the gap explicitly in `coverage-fr-task-test.md` SC-002 row noting CPU tests don't verify schema validity. |
| T8  | MEDIUM  | monkeypatch-leak   | test_eager_delete.py:67 | `monkeypatch.setattr(Path, "unlink", _flaky_unlink)` patches `pathlib.Path.unlink` at the CLASS level. While `monkeypatch` cleanup will restore it after the test, any code in conftest fixtures / orchestrator path that calls `.unlink()` during the same test run gets the flaky behavior. The closure-counted `call_count == 2` may match an unintended deletion. | Tighten the patch to a wrapper helper module (e.g., monkeypatch `folder_canonicalize.Path.unlink` or wrap `safe_eager_delete` directly). Alternatively, use `chmod 0o000` on the second pre-populated file to force a real PermissionError. |
| T9  | MEDIUM  | mock-fidelity      | test_cpu_fallback.py:96-104 | `monkeypatch.setattr(cpu_fb_mod, "_probe_paddle_post_run", _stub_paddle_post)` short-circuits the Paddle probe to always return `"consistent"`. This means the test never exercises the case where Paddle FALLS BACK to CPU during post-run interrogation (a documented R-023.15 scenario). The `outcome.fell_back` boolean is OR'd across both probes (cpu_fallback.py:133), so the orchestrator path for Paddle-only fallback is untested. | Add a parametrize variant where `_probe_paddle_post_run` returns `"fell_back"` (and Ollama is consistent). Assert `cpu_post_run["paddle_post_run"] == "fell_back"` and the overall outcome is rewritten to `failed_at_extraction`. |
| T10 | MEDIUM  | hidden-state       | test_voter_config.py:24-54 | Test uses `force_venv_interpreter` but the multi-voter case never invokes the voter_config_loader's `_auto_discover` path (which has 3 fallback locations including bundled resources via `importlib.resources`). When the override is given, only explicit-path loading is tested. `_auto_discover` is dead code in the test suite. | Add a small test that runs without `--voter-config` and with a `voter_config.yaml` in `tmp_path` set as cwd, verifying auto-discovery (FR-005). Skip if not practical, but flag the gap. |
| T11 | MEDIUM  | timing-sensitive   | test_check_only.py:182-198 (`test_check_only_within_10s_warm`) | Asserts `elapsed < 10.0` for the full CLI invocation with stubs. SC-007 is a real budget but this test runs in ~0.1 s on the dev box. The 10 s margin is generous, but on a heavily-loaded shared CI runner (or under coverage instrumentation) the threshold could be approached if any future expansion adds I/O. | Already low-risk; if R-023.16's "60 s for 60 tests" budget is preserved, this is fine. Document the 100x margin assumption in the test docstring and consider monotonic timing (already used) plus a softer 5 s target with 10 s hard ceiling. |
| T12 | LOW     | assertion-strength | test_cli_flow.py:94, test_report_shape.py:100 | `assert parsed["quality_status"] is not None` (test_happy_path) and `parsed["quality_status"] in ("pass", "weak", "review_required")`. The first is weaker than necessary — it just confirms a value was emitted, not which one. The `test_report_shape.py` version is tighter. | Use the same tight assertion (`in (...)`) in `test_happy_path`. |
| T13 | LOW     | assertion-strength | test_runtime_outcomes.py:73 | `assert parsed["failure_kind"] == "pipeline-runtime-timeout"` after timeout — good. But the `cpu_fallback_detection` field is never asserted in timeout cases; per orchestrator L641, `interrogate()` runs on every pipeline path including timeout, so `cpu_fallback_detection.ollama_post_run` should be `"consistent"` or `"unreachable"` (not `"skipped"`). | Add an assertion in `test_timeout_sets_stalled_phase` that `parsed["cpu_fallback_detection"]["ollama_post_run"] != "skipped"`. |
| T14 | LOW     | coverage-gap       | test_diagnostics.py | Tests stderr-mirrors-JSON for ONE check (ollama-version). The R-023.11 closed `CheckDiagnostic` shape and FR-019 contract apply to ALL 8 checks. Five other failure classes (interpreter/venv, paddle-rocm-preflight, ollama-reachability, ollama-placement, ollama-context-length) have no analogous diagnostic-mirror test. | Parametrize across failure classes (the same matrix `test_readiness_failures.py` uses) and assert the diagnostic's `remediation` prefix appears in stderr for each. |
| T15 | LOW     | coverage-gap       | test_ollama_base_url.py | The test asserts no non-canonical URLs are probed during `--check-only`. The POST-RUN probe via `cpu_fallback.interrogate` ALSO calls `/api/ps` on the same URL; this is not tested. | Extend the test or add a follow-on test that exercises a full happy-path run (with stub composer) and asserts `competing_calls == []` across the entire run including post-run interrogation. |
| T16 | LOW     | mock-fidelity      | conftest.py docstring L6 | The docstring claims `paddle_preflight_stub` returns `PreflightState.PASS_ROCM_GPU` but the actual code returns `PPSTRUCTUREV3_INIT_SUCCEEDED`. `PASS_ROCM_GPU` is not a member of the enum (preflight.py:45-56). Documentation drift. | Fix the docstring. |
| T17 | LOW     | style-nits (aggregated) | various | (a) `test_check_only.py:60` comment says "21 top-level keys exactly (17 in FR-019 + …)" — FR-019 says 17 but the actual set is 21; the inline math `17 + 1 (kind) + 1 (cpu_fb) + 1 (diagnostic) + …` is unfinished. (b) `test_runtime_outcomes.py:115-118` uses string indexing into `phases_order` rather than the canonical `CANONICAL_ARTIFACT_BASENAMES`. (c) Several test docstrings reference task IDs (T021/T022/…) without explaining what they do — fine for cross-ref but adds noise. (d) `test_check_only.py:155` typo in `test_check_only_does_not_check_source_pdf` ("CHK037" appears in the docstring but the file no longer has that line). | Single sweep cleanup; not blocking. |

## Detailed findings

### T1 — Successful-evaluator path not tested via the CLI
**Severity:** HIGH
**Category:** coverage-gap
**Test:** `test_with_evaluator.py::*` and `test_quality_status.py::*`
**Issue:** `test_quality_status.py` extensively tests `derive_quality_status` at the unit level, including the "evaluator agrees → source=evaluator" case. But the orchestrator's wiring of evaluator success → `derive` call → source flip is never exercised end-to-end. Both `test_with_evaluator.py` CLI tests force failure (sidecar missing OR subprocess non-zero).
**Why it matters:** This is the entire point of `--with-evaluator`. If the orchestrator branched wrongly on `eval_result.semantic_table_quality_passed`, the integration test couldn't catch it.
**Suggested fix:** Add `test_with_evaluator.py::test_successful_evaluator_flips_source` that stubs `subprocess.run` to return `CompletedProcess(returncode=0)` AND pre-writes a valid `evaluation_document.json` into the document folder with `semantic_table_quality: {passed: true}`. Assert `parsed["quality_status_source"] == "evaluator"`.

### T2 — `interpreter/venv` failure not in skip-on-upstream-fail parametrize
**Severity:** HIGH
**Category:** coverage-gap
**Test:** `test_readiness_order.py::test_skip_on_upstream_fail`
**Issue:** The parametrize covers 5 of the 6 pre-pipeline checks but the comment at L88 explicitly excludes `interpreter/venv`. The separate `test_interpreter_venv_failure_class` asserts the failing-check name + diagnostic shape but never asserts that checks 2-6 are marked `skipped` after it fails. So FR-026's "fixed-order skip after fail" guarantee is unverified for the FIRST check in the order.
**Why it matters:** A future regression that moved checks 1's fail to NOT short-circuit checks 2-6 would not be detected.
**Suggested fix:** Add an explicit `statuses[name] == "skipped"` assertion for checks 2-8 inside `test_interpreter_venv_failure_class`.

### T3 — `runtime_outcome == "failed_at_final_payload"` from schema-validation untested
**Severity:** HIGH
**Category:** coverage-gap
**Test:** `test_schema_validation.py::test_multi_artifact_failure`, `test_exit_codes.py::test_exit_5_schema_validation_failed`
**Issue:** Orchestrator L613-622 rewrites `runtime_outcome` to `failed_at_final_payload` when artifact-schema-validation fails. No test asserts this rewrite. Tests only assert the exit code and the failing-check name.
**Why it matters:** The closed `RuntimeOutcome` enum has 6 values; CHK006 in `testing-strategy.md` requires "tests for every `runtime_outcome` value". This particular path (schema-validation-induced failed_at_final_payload) is distinct from a composer raising at the final phase.
**Suggested fix:** In `test_multi_artifact_failure`, add `assert parsed["runtime_outcome"] == "failed_at_final_payload"` and `assert parsed["failure_kind"] == "artifact-schema-validation-failed"`.

### T4 — Stub `PreflightReadout` missing `evidence` field
**Severity:** HIGH
**Category:** mock-fidelity
**Test:** `conftest.py::_StubPreflightReadout` (paddle_preflight_stub fixture)
**Issue:** The stub class has 2 attrs (state, recommendation). The real `PreflightReadout` (`src/dartwing_ocr/preprocessing/preflight.py:102-109`) is a frozen dataclass with 3 REQUIRED fields: `state`, `evidence` (PreflightEvidence), `recommendation`. The gpu_demo readiness consumer (`paddle_preflight.py`) currently reads only `state` and `recommendation`, but the stub silently diverges from the dataclass contract.
**Why it matters:** Any future change in `paddle_preflight.py` to log evidence (e.g., for diagnostic enrichment) would AttributeError at runtime in production but pass tests. The docstring also references a non-existent `PreflightState.PASS_ROCM_GPU` (the real success value is `PPSTRUCTUREV3_INIT_SUCCEEDED`).
**Suggested fix:** Either `from dartwing_ocr.preprocessing.preflight import PreflightReadout, PreflightEvidence` and construct a real instance with sensible defaults, or add `evidence: Any = None` to the stub with a runtime check at the consumer site.

### T5 — `httpx.ReadTimeout` branch unexercised in ollama checks
**Severity:** MEDIUM
**Category:** mock-fidelity
**Test:** `conftest.py::ollama_http_stub` and downstream readiness-failure tests
**Issue:** Tests cover `httpx.ConnectError` extensively but never `httpx.ReadTimeout` (a different `httpx.HTTPError` subclass with potentially different `repr`). The `ollama_reach.py:38` and `ollama_version.py:39` `except httpx.HTTPError` blocks treat both identically, but the diagnostic text would differ.
**Why it matters:** Operator triage relies on the diagnostic string in the JSON `observed` field; a `ReadTimeout` vs `ConnectError` distinction matters for debugging.
**Suggested fix:** Add a parametrize variant in `test_readiness_failures.py` that uses a handler raising `httpx.ReadTimeout`. Assert the diagnostic's `observed` field starts with `"ReadTimeout: "`.

### T6 — Weak phase-timing assertion in `test_happy_path_failed_at_phase`
**Severity:** MEDIUM
**Category:** assertion-strength (borderline tautological)
**Test:** `test_cli_flow.py::test_happy_path_failed_at_phase` and `test_runtime_outcomes.py::test_failed_at_phase`
**Issue:** Tests assert "later phases are null" (`pt[later] is None`) but never assert that EARLIER phases ran fully and their timings are non-null. The latter test does this; the former does not. Without verifying earlier phases' timings, a regression where ALL phase timings null'd out wouldn't reliably fail.
**Why it matters:** Phase-timing correctness is a major operator-facing invariant (FR-025).
**Suggested fix:** Add `assert pt["preprocess"] is not None and pt["preprocess"] > 0` in `test_happy_path_failed_at_phase` (paralleling `test_failed_at_phase`).

### T7 — Stub composer artifacts don't match real schemas
**Severity:** MEDIUM
**Category:** mock-fidelity
**Test:** `conftest.py::_StubPipelineComposer`
**Issue:** Writes `{"kind": "preprocess_output", "stub": true}` for each of the four artifacts. This is NOT what feature 003/005/008/009 emit. `bypass_schema_validation` papers over this by no-oping `_validate_artifact`. The audit walkthrough flagged this as "by design" — meaning every CPU test that asserts artifact contents (vs presence) is fictional.
**Why it matters:** SC-002 ("4 artifacts schema-valid on success") is asserted only by `test_cli_flow.py::test_happy_path`, which uses `bypass_schema_validation`. So the assertion exists in the test file but is rendered tautological by the stub layer. Real schema validity is delegated to workstation T073 (which is not yet written, per issue #54).
**Suggested fix:** Author one realistic minimal artifact set that passes v1.3.0 schemas (e.g., a hand-built `preprocess_output.json` with empty `pages[]`, empty `tables[]`, valid `ingestion_sources`) and write those instead. This would allow retiring `bypass_schema_validation` for the happy-path tests and would make schema regressions visible on CI.

### T8 — Global `Path.unlink` patch in eager-delete test
**Severity:** MEDIUM
**Category:** monkeypatch-leak (within-test leakage)
**Test:** `test_eager_delete.py::test_partial_delete_failure_aborts_exit_2`
**Issue:** `monkeypatch.setattr(Path, "unlink", _flaky_unlink)` patches `pathlib.Path.unlink` globally for the test duration. Other code in the test (fixtures, log file rotation, tempdir cleanup) that calls `.unlink()` is affected. The `call_count == 2` happens to align with what the orchestrator does, but it's fragile.
**Why it matters:** A change in the orchestrator's call order (or addition of any other `.unlink()` invocation) would silently change which file gets the forced PermissionError.
**Suggested fix:** Patch `dartwing_ocr.gpu_demo.folder_canonicalize.Path.unlink` (which is the only call site that should be affected) — although Path is a stdlib class, the symbol resolution at the call site goes through `target.unlink()` so a method patch on the imported module's Path wouldn't help. Better: pre-write the file with mode `0o000` so the real PermissionError is raised, no monkeypatch needed.

### T9 — Paddle-only fallback never exercised
**Severity:** MEDIUM
**Category:** coverage-gap
**Test:** `test_cpu_fallback.py::*`
**Issue:** Both CPU-fallback tests force `_probe_paddle_post_run` to return `"consistent"` and toggle ONLY the Ollama probe. The case where Paddle alone fell back (Ollama still GPU-placed) is never tested, even though it's a documented branch of R-023.15.
**Why it matters:** The orchestrator's `outcome.fell_back` flag is OR'd across both probes (cpu_fallback.py:133). A regression that broke the OR (e.g., taking only Ollama) wouldn't be detected.
**Suggested fix:** Add `test_post_run_probe_detects_paddle_fallback` with `_probe_paddle_post_run` stubbed to return `"fell_back"` and Ollama consistent. Assert `cpu_fallback_detection.paddle_post_run == "fell_back"` and outcome rewritten.

### T10 — Voter-config auto-discovery untested
**Severity:** MEDIUM
**Category:** coverage-gap
**Test:** `test_voter_config.py`
**Issue:** Every test provides `--voter-config <path>`. The auto-discovery branch (`voter_config_loader._auto_discover`) — which searches 3 fallback locations including `importlib.resources` bundled defaults — is never invoked. FR-005 requires the bundled default to be honored.
**Why it matters:** A regression breaking the `importlib.resources.files(...)` resolution would not be detected.
**Suggested fix:** Add a test that `chdir`s to a tmp_path with `voter_config.yaml` present and invokes the CLI without `--voter-config`. Assert the resolved path matches.

### T11 — `test_check_only_within_10s_warm` timing margin
**Severity:** MEDIUM
**Category:** timing-sensitive
**Test:** `test_check_only.py::test_check_only_within_10s_warm`
**Issue:** Asserts `elapsed < 10.0`. With stubs the actual time is ~0.1 s — generous 100x margin. SC-007 is a real production budget, but on CI under coverage instrumentation or contention the budget could narrow.
**Why it matters:** Low risk now; flagged for awareness. Wall-clock-bound tests are the #1 source of CI flakiness.
**Suggested fix:** Keep the 10 s ceiling but add a softer mid-target (e.g., warn if > 2 s). Or document that this is testing the stub overhead, not the production SC-007 budget (which is workstation-only).

### T12 — Loose `quality_status is not None` assertion
**Severity:** LOW
**Category:** assertion-strength
**Test:** `test_cli_flow.py::test_happy_path:94`
**Issue:** `assert parsed["quality_status"] is not None` is weaker than `assert parsed["quality_status"] in ("pass", "weak", "review_required")` (which `test_report_shape.py:100` uses correctly).
**Suggested fix:** Use the tight enum assertion in both places.

### T13 — `cpu_fallback_detection` not asserted on timeout
**Severity:** LOW
**Category:** coverage-gap
**Test:** `test_runtime_outcomes.py::test_timeout_sets_stalled_phase`
**Issue:** Orchestrator L641 runs `cpu_fallback.interrogate` on every pipeline path including timeout, so the post-run snapshot should be populated. But the timeout test doesn't assert anything about `cpu_fallback_detection`.
**Suggested fix:** Add a positive assertion that `parsed["cpu_fallback_detection"]["ollama_post_run"]` is one of `("consistent", "fell_back", "unreachable")` — explicitly NOT `"skipped"`.

### T14 — Diagnostic stderr-mirror tested for only 1/6 failure classes
**Severity:** LOW
**Category:** coverage-gap
**Test:** `test_diagnostics.py::test_stderr_mirrors_json_diagnostic_for_ollama_version`
**Issue:** Only the ollama-version failure case is tested. R-023.11 + FR-019 demand the same stderr/JSON mirroring for ALL failure classes.
**Suggested fix:** Parametrize across the 6 (or 5 minus venv) failure classes.

### T15 — `OLLAMA_BASE_URL` isolation untested under full run
**Severity:** LOW
**Category:** coverage-gap
**Test:** `test_ollama_base_url.py::test_demo_ignores_other_ollama_urls`
**Issue:** Tested only under `--check-only`. The POST-RUN CPU-fallback probe also hits `/api/ps`; if it ever probed a non-canonical URL, this test wouldn't catch it.
**Suggested fix:** Add a happy-path variant that uses `_strict_handler` and a stub composer; assert `competing_calls == []` after a full run.

### T16 — Stale enum name in conftest docstring
**Severity:** LOW
**Category:** mock-fidelity (docs)
**Test:** `conftest.py:6`
**Issue:** Docstring says "PreflightState.PASS_ROCM_GPU" — this enum value does not exist. The real success state is `PPSTRUCTUREV3_INIT_SUCCEEDED`.
**Suggested fix:** Fix the docstring.

### T17 — Style nits aggregated
**Severity:** LOW
**Category:** style/docs
**Issue:** Various comment math mismatches, redundant string-indexing, stale task ID references in docstrings. Listed in the summary table.
**Suggested fix:** Single sweep cleanup at next maintenance pass.

## Coverage matrix spot-check (10 rows)

| FR/SC | Claimed test | Actually exercises the FR/SC? | Notes |
|---|---|---|---|
| FR-001 (CLI entry point) | `test_cli_smoke.py::test_help_exits_zero` + `test_version_exits_zero_and_prints_version` | YES | Uses `subprocess.run` against `python -m dartwing_ocr.gpu_demo` — real end-to-end import + argparse. Genuine smoke. |
| FR-002 (Paddle ROCm venv preflight) | `test_readiness_failures.py::test_interpreter_venv_failure_class` + `[paddle_cpu_only-…]` | PARTIAL | The interpreter check is asserted to fail correctly. The Paddle preflight failure asserts the diagnostic shape but the underlying `preflight.classify` is fully stubbed — only the stub's API is exercised, not the real preflight logic. |
| FR-008 (600 s bounded timeout, exit 3) | `test_runtime_outcomes.py::test_timeout_sets_stalled_phase` (parameterized × 4 phases) | YES | The `_TimeoutTriggerComposer` fires SIGALRM mid-phase; the orchestrator's `except TimeoutError: raise` is the load-bearing line and is genuinely exercised. The regression-guard comment in the test docstring is accurate. |
| FR-009 (4 artifacts schema-valid) | `test_cli_flow.py::test_happy_path` + `test_exit_codes.py::test_exit_5_schema_validation_failed` | PARTIAL | Existence is asserted; schema validity is bypassed via `bypass_schema_validation`. The exit-5 path stubs `_validate_artifact` to force failure — exercises orchestrator wiring but not the real validator. Workstation T073 (deferred) is the only real schema check. |
| FR-012 (no silent CPU fallback) | `test_cpu_fallback.py::test_post_run_probe_detects_ollama_fallback` | PARTIAL | Ollama fallback path is exercised end-to-end. Paddle-only fallback is stubbed out (see T9). Combined-fallback case is implicit but not directly asserted. |
| FR-016 (closed readiness vocab + fixed order + skip-on-fail) | `test_readiness_order.py::test_skip_on_upstream_fail` × 5 checks | PARTIAL | 5 of 6 pre-pipeline checks tested for skip behavior. `interpreter/venv` skipped from parametrize (see T2). |
| FR-017 (deterministic eager-delete) | `test_eager_delete.py::test_symlink_escape_aborts_exit_2` + 3 others | YES | Symlink escape uses a real symlink-to-/etc/hostname fixture (a strong real test). The `Path.unlink` monkeypatch in `test_partial_delete_failure_aborts_exit_2` is fragile (T8) but the assertion holds. |
| FR-021 (closed exit-code table 0–5) | `test_exit_codes.py::test_exit_{0..5}_*` | YES | All 6 exit codes covered. Each test triggers the underlying condition (real failure-class for 1, malformed yaml for 2, etc.) — no tautology. |
| FR-022 (--with-evaluator warn-and-skip) | `test_with_evaluator.py::*` (3 tests) | PARTIAL | Sidecar-missing and subprocess-failed branches covered; SUCCESSFUL evaluator (T1) is the gap. |
| FR-025 (phase_timings shape) | `test_check_only.py::test_check_only_pass_emits_stable_shape` + `test_cli_flow.py::test_happy_path` + others | YES | Tested under --check-only (all null), happy path (all populated), and mid-failure (mixed null). |
| SC-007 (--check-only ≤ 10 s warm) | `test_check_only.py::test_check_only_within_10s_warm` | PARTIAL | Asserts the budget with stubs; the workstation budget is the production SC-007 — see T11. |
| SC-009 (stdout JSON-only parseable) | "all tests parse stdout as JSON" | YES | Every stdout assertion does `json.loads(stdout)` and `stdout.count("\n") == 1`. SC-009 is effectively exercised by every test. |

## Tests that DO exercise their claimed FR/SC (positive findings)

- `test_runtime_outcomes.py::test_timeout_sets_stalled_phase` (the new test from `1d56554`) is **not tautological** — the SIGALRM is raised from a real signal subsystem, the orchestrator's `_on_timeout` handler iterates `timings[p] is None` to identify the in-flight phase, and `_run_phase`'s `except TimeoutError: raise` is the actual fix being regression-guarded. The parametrize across all 4 phases gives strong coverage of the closed `StalledPhase` enum.
- `test_eager_delete.py::test_symlink_escape_aborts_exit_2` uses a real symlink fixture (`preprocess_output.json -> /etc/hostname`) — this is a genuinely strong test.
- `test_check_only.py::test_check_only_pass_emits_stable_shape` asserts the FULL set of 21 top-level keys via `set(parsed.keys()) == expected_keys` — would catch any missing/extra key.
- `test_quality_status.py` is unit-level (no monkeypatching), tests a pure function over the truth table — high signal, low brittleness.
- `test_runtime_outcomes.py::test_failed_at_phase` correctly asserts that later phase timings are null AND the failing-phase timing is non-null — strong invariant assertion.
- `test_ollama_base_url.py::test_demo_ignores_other_ollama_urls` uses a strict handler that **records** competing calls into a list; an empty list at the end is a real negative-space assertion (cannot accidentally pass).
- `test_cli_smoke.py` is the only test using `subprocess.run` against the installed entry point — guards against import-time regressions in a way the in-process tests cannot.
- The `force_venv_interpreter` fixture's careful path-discriminating `_patched_realpath` (conftest.py:332-339) demonstrates that the "broadcast monkeypatch" bug mentioned in the agent's context HAS been eliminated: the patch only affects the named `fake_exe` path, not Path.resolve() elsewhere.

## What was reviewed

- All 17 test files under `tests/integration/gpu_demo/`
- `tests/integration/gpu_demo/conftest.py` (every fixture: paddle_preflight_stub, ollama_http_stub, ok_fixture_folder, stub_pipeline_composer, timeout_trigger_composer, bypass_schema_validation, patch_orchestrator_composer, force_venv_interpreter)
- The 4-phase parametrized `test_timeout_sets_stalled_phase` (timeout-path test added in `1d56554`) — traced through `_TimeoutTriggerComposer.preprocess` → `signal.raise_signal(SIGALRM)` → orchestrator's `_on_timeout` handler → `_run_phase`'s `except TimeoutError: raise` → outer `except TimeoutError` → `runtime_outcome = "timeout"`
- Spot-checked 10 rows from `coverage-fr-task-test.md`
- Source modules: `orchestrator.py`, `cli.py`, `cpu_fallback.py`, `quality_status.py`, `evaluator_subprocess.py`, `folder_canonicalize.py`, `voter_config_loader.py`, `enums.py`, `report.py`, all 8 readiness check modules
- `specs/023-gpu-mvp-demo-hardening/contracts/demo-report-schema.md` (verified the 17 vs 21 key claim)

## What was NOT reviewed

- Implementation correctness (separate agent reviews src/)
- Security concerns in tests themselves (separate agent)
- The workstation-only `@pytest.mark.gpu` test (T073) — not yet written; tracked as issue #54
- Pytest configuration / `pyproject.toml` marker registration
- Coverage matrix file's narrative outside the spot-checked rows
- Performance of the test suite (already validated by harness: ~1 s wall-clock for 60 tests)
