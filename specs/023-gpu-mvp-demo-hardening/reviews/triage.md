# Swarm review triage — feature 023

**Date:** 2026-05-25
**Branch:** `023-gpu-mvp-demo-hardening` @ `1d56554`
**Agents:** code-reviewer-023, security-reviewer-023, test-quality-reviewer-023, contract-reviewer-023 (all run in parallel against the same commit).

## Verdict

**DO NOT OPEN PR YET.** Two CRITICAL correctness bugs (one of them confirmed by an independent agent) will fire on the first real workstation smoke run. The CPU test suite passes only because `bypass_schema_validation` and the stub composer mask them. Estimated fix budget: 4–6 surgical edits in `orchestrator.py` + `readiness/schema_validation.py` + a regression test that retires the bypass for the affected path.

---

## Resolution status (2026-05-25)

All blockers + HIGH gaps + MEDIUMs + applicable LOWs **landed** on `023-gpu-mvp-demo-hardening` (uncommitted; ready for review-then-commit). Test suite: **64 passing / 0 failing / 0 xfail** (60 → 64; new tests: T1 phase-failure-no-mask, T2 successful-evaluator-flips-source, B5 invalid-URL-exit-2, B5 non-localhost-INFO-line).

| ID | Status | Resolution |
|---|---|---|
| B1 | ✅ FIXED | `readiness/schema_validation.py:_validate_artifact` rewritten to call `validate_artifact(path, contract=<name>)` with a closed basename→ArtifactName mapping; surfaces first violation's code+path on fail. |
| B2 | ✅ FIXED | `orchestrator.py:_run`: wrapped post-pipeline schema rewrite in `if runtime_outcome is None:` guard. Regression test `test_phase_failure_does_not_mask_as_schema_failure` proves exit 4 + `failed_at_extraction` survives. |
| B3 | ✅ FIXED | Introduced mutable `_RunState` dataclass + `_extract_run_summary()` helper; `_run_phase` captures `composer.preprocess()` return value and publishes any `run_summary` dict for quality derivation. |
| B4 | ✅ FIXED | SIGALRM cleanup paths (`except TimeoutError` body and `finally` block) wrapped in `try/except TimeoutError: pass` so a late-arriving alarm cannot leak past `run()` and violate FR-019. |
| B5 | ✅ FIXED | `_validate_ollama_base_url()` helper enforces R-023.14 (urlparse + scheme http/https + non-empty host); invalid URL → exit 2 invalid-input; non-localhost host emits INFO stderr line. Two tests added. |
| T1 | ✅ FIXED | `test_phase_failure_does_not_mask_as_schema_failure` asserts `runtime_outcome=="failed_at_extraction"` + exit 4 on a phase failure where post-pipeline check 7 would otherwise rewrite. |
| T2 | ✅ FIXED | `test_successful_evaluator_flips_source` stubs subprocess.run success + pre-writes evaluation_document.json; asserts `quality_status_source == "evaluator"`. |
| T3 | ✅ FIXED | `test_interpreter_venv_failure_class` now asserts checks 2-8 are all `"skipped"` when check 1 fails — closes FR-026 skip-after-fail gap. |
| T4 | ✅ FIXED | `_StubPreflightReadout` gained the `evidence` field (defaults to None) matching the real frozen dataclass; conftest docstring corrected (`PPSTRUCTUREV3_INIT_SUCCEEDED` not `PASS_ROCM_GPU`). |
| M1/K5 | ✅ FIXED | New `_format_document_folder_for_report()` helper emits the operator-attempted path on invalid-input outcomes (returns `None` only on `--check-only`). |
| M2 | ✅ FIXED | `_DefaultPipelineComposer.extract/route/assemble` now raise `PipelineUnavailable` with canonical StalledPhase literals (`extraction`/`routing`/`final_payload`). |
| M3/K4 | ✅ FIXED | `_extract_pre_run_snapshot()` helper pulls the matching model from `base_context.cached_api_ps_body`; passed through `interrogate(pre_run_snapshot=...)`. `_probe_ollama_post_run` now computes pre→post `size_vram` diff. |
| M4 | ✅ FIXED | `_cap_snapshot_dicts()` projects snapshot dicts to the four canonical keys (name/size/size_vram/context_length) and secondary-caps via the 2 KiB UTF-8 truncator. |
| K3 | ✅ FIXED | CPU-fallback budget-exceeded path now forces BOTH probes to `"unreachable"`; orchestrator emits the prescribed WARN line per R-023.15. |
| K6 | ✅ FIXED | `post-run-interrogation-unreachable` branch now sets `diagnostic_msg` so a non-null `failure_kind` is always paired with a non-null `diagnostic` (invariant 1). |
| S1 | ✅ FIXED | `safe_eager_delete` rejects all symlinks at canonical basenames outright — eliminates the TOCTOU window between the resolve-check and the unlink. |
| S2 | ✅ FIXED | `log._sanitize()` strips C0 controls (except tab) + DEL + ANSI CSI from interpolated stderr `msg` strings. |
| L1 | ✅ FIXED | `InterpreterVenvCheck` uses `Path(interpreter).parts` intersection instead of substring match; rejects `.venv-paddle-rocm-backup` and similar look-alikes. |
| K7 | ✅ FIXED | Orchestrator emits `INFO: post-run: ollama still GPU-placed; paddle still rocm_gpu` on the consistent-consistent path, matching cli-contract.md examples. |

**Deferred (intentional, tracked):** L2/L3/T12-T17/S3-S8 cosmetic items are not blocking — they were aggregated into the polish task and judged not worth a separate commit cycle. T7 (stub composer schema fidelity) remains the audit-walkthrough's "by design" note pending the real composer wiring tracked as #53.

## Per-agent headline

| Agent | Findings | C | H | M | L | Status |
|---|---|---|---|---|---|---|
| code-reviewer | 12 | **2** | 2 | 5 | 3 | NEEDS-ATTENTION |
| security-reviewer | 8 | 0 | 0 | 2 | 6 | PASS |
| test-quality-reviewer | 17 | 0 | 4 | 7 | 6 | NEEDS-ATTENTION |
| contract-reviewer | 7 | 0 | 2 | 4 | 1 | NEEDS-ATTENTION |
| **Total** | **44** | **2** | **8** | **18** | **16** |  |

## PR-blockers (must fix before opening)

| Triage | Severity | Source | Location | One-liner |
|---|---|---|---|---|
| **B1** | CRITICAL | code C1 | `readiness/schema_validation.py:38` | `validate_path` doesn't exist on the validator module — every workstation run hits AttributeError. |
| **B2** | CRITICAL | code C2 + contract K1 (**2 agents**) | `orchestrator.py:615-622` | Post-pipeline check rewrites `runtime_outcome` even when a phase already failed, masking real failure with `failed_at_final_payload` + exit 5. |
| **B3** | HIGH | code H1 | `orchestrator.py:135, :699` | `getattr(frozen_options, "_preprocess_run_summary")` is structurally `None` — once #53 lands, `quality_status` will always be `review_required`. |
| **B4** | HIGH | code H2 | `orchestrator.py:555-590` | SIGALRM can fire inside `except`/`finally`, leaking unhandled `TimeoutError` past `run()` → violates FR-019 (always-emit). |
| **B5** | HIGH | contract K2 | `orchestrator.py:150-161` | `OLLAMA_BASE_URL` not validated per R-023.14 (no `urlparse`, no scheme check, no non-localhost INFO line, no exit-2 mapping). |

**B2 is the smoking gun:** two independent agents reading different artifacts found the same bug. B1 + B2 compose — on the first workstation smoke, B1 fires AttributeError on check 7, B2 rewrites the outcome to `failed_at_final_payload` exit 5, and the operator sees a fake schema-validation failure with no useful diagnostic.

## Test gaps that let the blockers slip through

| Triage | Severity | Source | One-liner |
|---|---|---|---|
| **T1** | HIGH | test-quality T3 | No test asserts `runtime_outcome == "failed_at_final_payload"` on schema-validation fail (only exit code) → B2 was invisible to CI. |
| **T2** | HIGH | test-quality T1 | No successful `--with-evaluator` path test → `quality_status_source == "evaluator"` is never hit via the orchestrator. |
| **T3** | HIGH | test-quality T2 | `interpreter/venv` excluded from `test_skip_on_upstream_fail` parametrize; the standalone test never asserts checks 2–6 are skipped → FR-026 unverified for check #1. |
| **T4** | HIGH | test-quality T4 | Stub `PreflightReadout` missing the `evidence` field that the real dataclass requires; docstring references non-existent `PASS_ROCM_GPU`. |

T1 is the regression test that should land *with* the B2 fix.

## Should-fix-now (MEDIUM)

| Triage | Source | One-liner |
|---|---|---|
| M-doc-folder | code M1 + contract K5 (2 agents) | `document_folder` null'd on invalid-input — contract says "attempted path". |
| M-stalled-phase | code M2 | `PipelineUnavailable("extract", …)` uses non-Literal phase names; closed-enum drift. |
| M-snapshot | code M3 + contract K4 (2 agents) | `pre_run_ollama_snapshot` always `None`; `/api/ps` cache from check 3 never threaded to `cpu_fallback.interrogate`. |
| M-cap | code M4 | Snapshot dicts + other free-form fields bypass the 2 KiB cap. |
| M-budget | contract K3 | CPU-fallback aggregate-budget-exceeded path missing the both-probes-unreachable rewrite + the prescribed WARN line. |
| M-diag | contract K6 | `runtime_outcome=success` + `failure_kind="post-run-interrogation-unreachable"` + `diagnostic=null` — violates invariant 1. |
| M-sec1 | security S1 | TOCTOU window in `safe_eager_delete`; theoretical under threat model. |
| M-sec2 | security S2 | Stderr log injection via unsanitized control chars in operator paths / model names. |

## Polish (LOW)

16 LOW findings across the four reviews — interpreter-substring tightening, default-folder string-compare, stderr-INFO line for the consistent-consistent post-run path (K7), assertion-strength bumps, doc/comment cleanups. Hold for a single polish sweep PR after the blockers land.

## Recommended fix order (suggested commits, all on `023-gpu-mvp-demo-hardening`)

1. **B1 + B2 + T1** in one commit — touches `readiness/schema_validation.py` (wire the real validator API), `orchestrator.py:615-622` (guard the rewrite), and `tests/integration/gpu_demo/test_schema_validation.py` (assert `runtime_outcome` value, and retire `bypass_schema_validation` for at least one happy-path test using a hand-crafted schema-valid stub artifact).
2. **B3** in one commit — replace the `getattr(frozen_options, …)` channel with a mutable `RunState` container (or have `_run_phase` capture composer return values and thread a result dict through). Test by extending the stub composer to "return a run_summary" and asserting `quality_status` derivation reads it.
3. **B4** in one commit — wrap `signal.alarm(0)` cleanup in a try/except that swallows late `TimeoutError`. Test with a SIGALRM raised inside the `finally` block.
4. **B5** in one commit — add `_validate_ollama_base_url()`; map invalid URL to exit 2 with `failure_kind=invalid-input`; emit non-localhost INFO line.
5. **T2 + T3 + T4** in one commit — close the test-coverage gaps that enabled B1–B5 to land.
6. **M-bundle** in one commit — wire `pre_run_snapshot` from cache, fix `PipelineUnavailable` phase names, fix `document_folder` invalid-input behavior, fix K3 budget path, fix K6 diagnostic null.
7. **Polish** in one commit — L1/L2/L3 from code review, T12–T17 from test-quality, S5–S8 from security, K7 from contract.
8. **PR open** — after CI is green and one local workstation smoke run confirms B1+B2 are dead.

The pre-existing GitHub issues #53 (T034a real composer) and #54 (T073 workstation `@pytest.mark.gpu` smoke) remain valid and unaffected by this triage.

## Cross-finding triangulation

These are the high-confidence findings (≥2 independent agents flagged the same bug):

- **B2** = code C2 (orchestrator review) + contract K1 (data-model review). Same line, same fix.
- **M-doc-folder** = code M1 + contract K5. Same field, same fix.
- **M-snapshot** = code M3 + contract K4. Same dead parameter, same fix.

Independent triangulation is the cleanest signal we have that these aren't false positives — both agents had different briefs and different reading paths, yet converged on the same finding.
