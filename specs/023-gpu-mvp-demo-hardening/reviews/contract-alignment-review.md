# Contract-alignment review — feature 023

**Date:** 2026-05-25
**Reviewer:** contract-reviewer-023 agent (general-purpose, swarm review)
**Branch:** 023-gpu-mvp-demo-hardening @ 1d56554

## Summary

7 findings: 0 CRITICAL, 2 HIGH, 4 MEDIUM, 1 LOW.

Status: NEEDS-ATTENTION

The bulk of the contract surface is faithfully implemented. The closed
enums in `enums.py` mirror `data-model.md §4` exactly; the dataclass shape
in `report.py` matches the 21 top-level keys in `data-model.md §1`; the
serializer in `serialization.py` honors R-023.12 (sort_keys=False,
ensure_ascii=False, compact separators), R-023.21 (3-dp rounding) and
Q5 (2 KiB UTF-8-boundary truncation of `CheckDiagnostic.observed`); the
8-check readiness vocabulary in `enums.READINESS_CHECK_ORDER` and the
runner's fixed-order skip semantics match `contracts/readiness-vocabulary.md`;
the closed exit-code table and the evaluator-subprocess argv pin-down
(R-023.13) are exact.

The two HIGH findings are: (1) the post-pipeline schema-validation check
can overwrite a phase-failure runtime_outcome (e.g., `failed_at_extraction`)
to `failed_at_final_payload` because there is no guard against the
phase-failure cascade where the next phase's artifacts simply don't
exist on disk; (2) `OLLAMA_BASE_URL` is consumed without the R-023.14
validation gate (no scheme/host check, no non-localhost INFO warning,
no exit-2 on malformed URL).

## Findings

| ID | Severity | Contract source | Code location | Drift | Recommendation |
|----|----------|-----------------|---------------|-------|----------------|
| K1 | HIGH | cli-contract.md exit-code table + readiness-vocabulary.md §7 (skip rule) | orchestrator.py:611-622 | After a phase failure (e.g. `failed_at_extraction`), `run_post_pipeline` still runs check 7 (artifact-schema-validation). The check sees missing artifacts and returns `fail`, which the orchestrator then uses to rewrite `runtime_outcome` from `failed_at_extraction` to `failed_at_final_payload` and to set exit code 5 instead of 4. | Skip check 7 (mark `"skipped"`) when an earlier `runtime_outcome` is already non-null and not `"success"`; OR guard the rewrite loop with `if runtime_outcome in (None, "success")`. |
| K2 | HIGH | research.md R-023.14 + cli-contract.md "Environment variables" | orchestrator.py:157 (only reads env var) | The demo never validates `OLLAMA_BASE_URL`. Required by R-023.14: parse via `urllib.parse.urlparse`, require scheme `http`/`https`, require non-empty host, emit `INFO:` line for non-localhost hosts, exit 2 on invalid URL syntax. None of those are implemented. | Add a `_validate_ollama_base_url()` helper called before the readiness phase; map `ValueError`/parse-failure to exit 2 (`invalid-input`); emit `log.info` for non-localhost. |
| K3 | MEDIUM | data-model.md §5 + research.md R-023.15 (aggregate-budget WARN) | cpu_fallback.py:117-129 | When the aggregate 5 s budget is exceeded after the Ollama probe, the code keeps the actual Ollama probe result and marks only Paddle `"unreachable"`. R-023.15 says: "Combined budget exceeded → BOTH probes are marked unreachable; demo emits `WARN:[run_id] post-run interrogation exceeded 5s budget; CPU-fallback detection inconclusive`". Neither the both-probes-unreachable rewrite nor the WARN line is implemented. | When `elapsed >= _AGGREGATE_BUDGET_SECONDS`, force `ollama_post_run = paddle_post_run = "unreachable"` AND surface a budget-exceeded flag that the orchestrator turns into the prescribed WARN line. |
| K4 | MEDIUM | data-model.md §5 + research.md R-023.15 (pre-run snapshot) | orchestrator.py:642-651 | `interrogate()` is called without `pre_run_snapshot=...`; the orchestrator never threads the `/api/ps` body cached by check 3 (`OllamaReachabilityCheck`'s `side_channel`) into the CPU-fallback probe. As a result `pre_run_ollama_snapshot` is always `None` in the emitted report, breaking the data-model promise that the pre-run snapshot is captured "when known" — and it IS known, because check 3 publishes it. | Pull the matching model entry from `base_context.cached_api_ps_body["models"]` (after run_pre_pipeline), pass it via `pre_run_snapshot=` to `interrogate()`, and have cpu_fallback echo it back through the outcome. |
| K5 | MEDIUM | data-model.md §1 (`document_folder` semantics) + demo-report-schema.md field reference | orchestrator.py:250-252 | `document_folder` is computed as `str(options.document_folder.resolve()) if not options.check_only and options.document_folder.exists() else None`. data-model.md says "On invalid-input outcomes (missing source.pdf, etc.), this field captures the path that was *attempted*, not `null`". When the supplied folder does not exist (e.g. `--document-folder /tmp/no-such-folder`), the report emits `null` instead of the attempted path. The matrix shows "str-or-null" for invalid-input, so this is interpretive — but the reference text explicitly says "not null". | Resolve the path *attempt* (`str(options.document_folder)` or `str(options.document_folder.resolve())` even when it doesn't exist) on invalid-input outcomes so operators can see which path was rejected. |
| K6 | MEDIUM | data-model.md §1 (cross-field invariant 1, post-run-interrogation diagnostic) + demo-report-schema.md `diagnostic` field | orchestrator.py:661-667 | When the pipeline succeeds but post-run interrogation returns `unreachable`, the orchestrator sets `failure_kind = "post-run-interrogation-unreachable"` and emits a WARN line — but `diagnostic_msg` is never assigned. The emitted report has `runtime_outcome=success`, `failure_kind="post-run-interrogation-unreachable"`, `diagnostic=null`. The demo-report-schema.md says `diagnostic` is the operator-friendly one-liner; leaving it null contradicts the failure-kind being non-null. | Assign `diagnostic_msg = f"post-run interrogation could not confirm GPU placement (ollama={...}, paddle={...})"` in the same branch where `failure_kind` is set. |
| K7 | LOW | cli-contract.md "Worked examples" (line 209 stderr signal) | orchestrator.py CPU-fallback section | The happy-path stderr example shows `INFO:[run_id] post-run: ollama still GPU-placed; paddle still rocm_gpu` before the final success line. The orchestrator emits no INFO line on the consistent-consistent path — only the WARN line on unreachable or the ERROR line on fell_back. | After CPU-fallback returns `consistent`/`consistent`, emit `log.info(run_id, "post-run: ollama still GPU-placed; paddle still rocm_gpu")` to match the documented example. |

## Detailed findings

### K1 — Phase-failure runtime_outcome silently rewritten to failed_at_final_payload

**Severity:** HIGH
**Contract source:** `contracts/cli-contract.md` exit-code table (exit 4 for `pipeline-runtime-error`, exit 5 only for `artifact-schema-validation-failed`); `data-model.md §1` invariant 3 (`failed_at_<phase>` → that phase non-null, later phases null, `quality_status` null); `contracts/readiness-vocabulary.md` §7 (check 7 runs "after the pipeline runs *and only after all 4 phases produced their artifacts*").
**Code location:** `orchestrator.py:611-622`
**What the contract says:** Check 7 evaluates schema validity *of artifacts produced by a completed pipeline*. A pipeline that failed at extraction does not produce `routing_decision.json` or `final_structured_payload.json`. The exit code for that scenario is 4 (`pipeline-runtime-error`) with `runtime_outcome = "failed_at_extraction"`.
**What the code does:** `run_post_pipeline(post_ctx, pre_results)` runs check 7 whenever `pre_failed=False` and `check_only=False` — irrespective of whether the pipeline itself failed mid-phase. Check 7 then reports `fail` because most of the four artifacts are missing on disk. The unconditional loop at lines 615-622 then overwrites `runtime_outcome` (already `"failed_at_extraction"` from `_run_phase`) to `"failed_at_final_payload"` and `failure_kind` to `"artifact-schema-validation-failed"`. The exit code becomes 5 instead of 4.
**Drift:** A genuine extraction-phase failure is misreported as a schema-validation failure; the closed exit-code semantics are violated.
**Suggested fix:** In `orchestrator.py:614`, guard the rewrite:
```python
for r in post_results:
    if r.name == "artifact-schema-validation" and r.status == "fail":
        if runtime_outcome in (None, "success"):
            runtime_outcome = "failed_at_final_payload"
            failure_kind = "artifact-schema-validation-failed"
            ...
```
OR, more invasively, in `runner.run_post_pipeline`, accept an additional `pipeline_failed: bool` argument and short-circuit both post-checks to `"skipped"` when the pipeline did not complete every phase.

---

### K2 — `OLLAMA_BASE_URL` not validated per R-023.14

**Severity:** HIGH
**Contract source:** `research.md` R-023.14 ("URL parsed via `urllib.parse.urlparse`; scheme must be `http` or `https`; host non-empty. ... Invalid URL syntax → exit 2 (invalid input/usage). Non-localhost → emit INFO stderr line."); `cli-contract.md` "Environment variables" table.
**Code location:** `orchestrator.py:150-161` (`_build_options_from_args`), with no upstream validator.
**What the contract says:** Three behaviors: (a) parse via `urllib.parse.urlparse`; (b) hard-fail with exit 2 on invalid URL (e.g. missing scheme); (c) soft INFO line if host is non-localhost / non-127.0.0.1 (so operators have a paper trail when probing across LAN).
**What the code does:** Reads the env var verbatim, hands it to readiness checks, which paste it into `f"{base_url.rstrip('/')}/api/ps"`. A malformed URL surfaces as `httpx.ConnectError` mid-readiness instead of exit 2 with an `invalid-input` diagnostic.
**Drift:** Operators on a misconfigured workstation see an opaque readiness failure instead of the intended "your URL is invalid" exit-2 path. The non-localhost INFO line is silently absent.
**Suggested fix:** Add a small `_validate_ollama_base_url(url) -> str` helper called inside `_build_options_from_args` (or just after argparse). Raise a custom exception that the orchestrator maps to `failure_kind="invalid-input"` + `ExitCode.INVALID_INPUT`. Emit `log.info(run_id, f"using non-localhost Ollama base URL: {url}")` after the validator returns when the host is not `localhost`/`127.0.0.1`.

---

### K3 — Aggregate-budget-exceeded path is incomplete

**Severity:** MEDIUM
**Contract source:** `research.md` R-023.15 ("Combined budget exceeded → both probes are marked `unreachable`; demo emits `WARN:[run_id] post-run interrogation exceeded 5s budget; CPU-fallback detection inconclusive`.")
**Code location:** `cpu_fallback.py:117-129`
**What the contract says:** Both probes set to `"unreachable"`, AND a specific WARN stderr line is emitted.
**What the code does:** Forces `paddle_post_run = "unreachable"` only; keeps the actual Ollama result (which may be `"fell_back"` or `"consistent"`). `budget_exceeded=True` is recorded on the outcome but the orchestrator never reads it and never emits the WARN line.
**Drift:** The CPU-fallback verdict in the report may be inconsistent with the "we ran out of time" signal. Operators won't see the prescribed WARN line.
**Suggested fix:** In `cpu_fallback.interrogate`, when `elapsed >= _AGGREGATE_BUDGET_SECONDS` after the Ollama probe, set BOTH `ollama_post_run` and `paddle_post_run` to `"unreachable"`, AND mark `budget_exceeded=True`. In the orchestrator (after `interrogate(...)`), check `outcome.budget_exceeded` and emit `log.warn(run_id, "post-run interrogation exceeded 5s budget; CPU-fallback detection inconclusive")`.

---

### K4 — `pre_run_ollama_snapshot` is always null

**Severity:** MEDIUM
**Contract source:** `data-model.md §5` (`pre_run_ollama_snapshot: dict | None — full /api/ps entry captured at readiness (when known)`); `research.md` R-023.15 ("compare placement vs pre-run snapshot").
**Code location:** `orchestrator.py:642-651`
**What the contract says:** When the readiness phase succeeded and the `/api/ps` body was cached (via `OllamaReachabilityCheck.side_channel` → `base_context.cached_api_ps_body`), the matching model entry should be threaded into `interrogate()` and echoed back into `CPUFallbackDetection.pre_run_ollama_snapshot`. The example success report at `data-model.md` line 265 shows it populated with the full model dict.
**What the code does:** Calls `cpu_fallback_mod.interrogate(ollama_base_url=..., expected_model=...)` with no `pre_run_snapshot=` argument. `_probe_ollama_post_run` accepts the parameter but it defaults to `None`. The emitted report always has `pre_run_ollama_snapshot: null`.
**Drift:** Operators can compare current state to nothing; the SC-004 "we were GPU at readiness, and still GPU after the run" assertion isn't observable from the report.
**Suggested fix:** After `run_pre_pipeline` returns the updated context, extract the matching model entry from `base_context.cached_api_ps_body["models"]` by name, then pass it as `pre_run_snapshot=` to `interrogate()`.

---

### K5 — `document_folder` swallows the attempted path on invalid-input

**Severity:** MEDIUM
**Contract source:** `data-model.md §1` field reference ("On invalid-input outcomes (missing source.pdf, etc.), this field captures the path that was *attempted*, not `null` — operators need to know which path failed validation."). The outcome-matrix at `contracts/demo-report-schema.md` line 230 records "str-or-null" for invalid-input, which is mildly looser.
**Code location:** `orchestrator.py:250-252`
**What the contract says:** Emit the attempted path on invalid-input — the operator's primary triage cue.
**What the code does:** `document_folder = str(options.document_folder.resolve()) if not options.check_only and options.document_folder.exists() else None`. When the path doesn't exist (the canonical invalid-input case), the field becomes `null`.
**Drift:** Operators triaging "what did I type wrong" lose the breadcrumb. Note: the `diagnostic` field at the top level does include the path; the structured `document_folder` field does not.
**Suggested fix:** Emit `str(options.document_folder)` (or `str(options.document_folder.resolve(strict=False))`) under the invalid-input branches, even when the directory does not exist. Reserve `null` for `--check-only` only.

---

### K6 — Success + post-run-interrogation-unreachable has null `diagnostic`

**Severity:** MEDIUM
**Contract source:** `contracts/demo-report-schema.md` field reference for `diagnostic` ("On success: `null`. On any failure: a one-sentence summary of the primary failure."); `data-model.md §1` invariant 1 (`runtime_outcome == "success"` may carry `failure_kind == "post-run-interrogation-unreachable"` "when post-run probes could not confirm GPU placement but did not detect CPU fallback").
**Code location:** `orchestrator.py:661-667`
**What the contract says:** When `failure_kind` is non-null, the operator-friendly `diagnostic` summary should be non-null too — that's the cross-stream observability contract.
**What the code does:** Emits a `log.warn(run_id, "post-run interrogation could not confirm GPU placement ...")` line, but does not assign `diagnostic_msg`. The emitted JSON has `failure_kind: "post-run-interrogation-unreachable"`, `diagnostic: null`.
**Drift:** Soft inconsistency between the WARN stderr line and the structured report. Automation that filters by `diagnostic IS NOT NULL` will miss this case.
**Suggested fix:** Inside the `elif outcome.unreachable ...` branch, set `diagnostic_msg = f"post-run interrogation could not confirm GPU placement (ollama={outcome.ollama_post_run}, paddle={outcome.paddle_post_run})"`.

---

### K7 — Missing happy-path post-run INFO line

**Severity:** LOW
**Contract source:** `contracts/cli-contract.md` line 209 worked example (`INFO:[a1b2c3d4] post-run: ollama still GPU-placed; paddle still rocm_gpu`).
**Code location:** `orchestrator.py` CPU-fallback section (lines 640-667)
**What the contract says:** On the consistent/consistent path, the operator sees a positive INFO line confirming the post-run interrogation found nothing wrong.
**What the code does:** Emits an ERROR line on `fell_back`, a WARN line on `unreachable`, and nothing on the consistent path.
**Drift:** Operators following the runbook will see a missing line vs. the documented example. The other observability signals (the JSON report's `cpu_fallback_detection` block) carry the information, so this is cosmetic.
**Suggested fix:** After the `if outcome.fell_back ... elif outcome.unreachable ...` branches, add `else: log.info(run_id, "post-run: ollama still GPU-placed; paddle still rocm_gpu")`.

---

## Verified contracts (positive findings — explicit pass)

### Report shape

- **DemoRunReport top-level key set (data-model.md §1, FR-019 stable-shape):** PASS. All 21 top-level keys are declared as dataclass fields in `report.py:88-111`, and `_report_to_dict` in `serialization.py:67-109` emits them all unconditionally (with `null` for non-applicable values, never omitted). Every early-exit path in the orchestrator (voter-config-load failure, canonicalize failure, source.pdf missing, readiness fail, --check-only, eager-delete failure, success) routes through `_build_report` → `_emit_report`, so the stable-shape promise holds across outcomes.
- **`kind` constant (data-model.md §1 invariant 7):** PASS. `enums.DEMO_REPORT_KIND = "demo_run_report"` and the field is non-overridable from `_build_report` (it carries the default in `DemoRunReport.kind`). No alternative spelling appears anywhere in the source.
- **`schema_version` constant (FR-024):** PASS. `enums.DEMO_REPORT_SCHEMA_VERSION = "0.1.0"`, used in `_build_report` and on every outcome.
- **`bounded_timeout_seconds = 600` (FR-008):** PASS. `enums.BOUNDED_TIMEOUT_SECONDS = 600`; `OrchestratorOptions.bounded_timeout_seconds` defaults to it; `signal.alarm(options.bounded_timeout_seconds)` uses it.
- **`run_id` UUID4 format (R-023.6):** PASS. `run_id.new_run_id()` returns `str(uuid.uuid4())`. `prefix_for(run_id)` returns `run_id[:8]`. `log.py:_emit` formats stderr lines as `"{severity}:[{prefix_for(run_id)}] {msg}\n"`.

### Closed enums (data-model.md §4)

- **`RuntimeOutcome` (6 values):** PASS. `enums.py:14-21` matches data-model.md verbatim. Orchestrator never emits a value outside this set.
- **`StalledPhase` (4 values):** PASS. `enums.py:23` matches; `timeout_observed["phase"]` is restricted to `("preprocess", "extraction", "routing", "final_payload")` at orchestrator.py:561.
- **`QualityStatus` (3 values):** PASS. `enums.py:25`; `quality_status._GATE_TRUTH_TABLE` only ever returns one of the three values; defensive fallback to `"review_required"`.
- **`QualityStatusSource` (2 values):** PASS. `enums.py:27`; the truth-table function returns `"gate"` or `"evaluator"`.
- **`FailureKind` (7 values):** PASS. `enums.py:29-37` matches data-model.md verbatim.
- **`ReadinessCheckName` (8 values):** PASS. `enums.py:39-48` matches; the `READINESS_CHECK_ORDER` tuple at line 55-64 pins the same order.
- **`ReadinessCheckStatus` (3 values):** PASS. `enums.py:50` matches.
- **`ProbeResult` (4 values):** PASS. `enums.py:52` matches data-model.md §5.

### Cross-field invariants (data-model.md §1)

- **Invariant 5 (`quality_status` non-null IFF `runtime_outcome == "success"`):** PASS. The orchestrator's quality-derivation block at lines 673-707 is gated by `if runtime_outcome == "success"`. Every other early-exit path (voter-config fail, canonicalize fail, source.pdf missing, readiness fail, --check-only, eager-delete fail) passes `quality_status=None, quality_status_source=None` explicitly. Phase-failure path leaves both at None (initialized at line 673-674). Timeout path skips the quality block. The bi-conditional holds across all 7 outcome classes audited. The only nuance is that on the `failed_at_extraction` rewrite triggered by CPU-fallback (line 654), the orchestrator does NOT reset `quality_status` because the rewrite happens AFTER the success path computed quality. But the orchestrator block at 712-716 also re-tests `if runtime_outcome == "success"` so the final stderr signal does not emit on CPU-fallback. This is correct but subtle. After the rewrite, the emitted report could carry a non-null `quality_status` paired with `runtime_outcome == "failed_at_extraction"` — **see note below**.
- **Invariant 5 — CPU-fallback rewrite edge case:** **DRIFT (sub-finding of K1's neighborhood, not raised as a separate K# because it requires the K1 fix to surface).** At orchestrator.py:653, when CPU-fallback rewrites `runtime_outcome` from `"success"` to `"failed_at_extraction"`, the quality-status block has already run and `quality_status`/`quality_status_source` are populated. The subsequent `_build_report` call at line 718 passes those non-null values along with `runtime_outcome="failed_at_extraction"`. This **violates invariant 5**. Suggested fix: after the CPU-fallback rewrite at line 654, explicitly reset `quality_status = None; quality_status_source = None`. This is a small but real drift; logged here in the invariant-5 entry rather than as a separate K# because it shares K1's "post-run logic mutates runtime_outcome without resetting dependent state" theme. Recommend folding into the K1 fix.
- **Invariant 2 (timeout):** PASS. `_on_timeout` raises `TimeoutError`; orchestrator catches it at line 579-585 and sets `runtime_outcome="timeout"`, `failure_kind="pipeline-runtime-timeout"`, `stalled_phase = timeout_observed["phase"]`. `quality_status` is null because the gated block at line 675 doesn't execute.
- **Invariant 4 (no-pipeline-ran outcomes):** PASS. Every pre-pipeline early-exit (voter-config fail, canonicalize fail, source.pdf missing, readiness fail, --check-only success) passes `phase_timings=_empty_phase_timings()` (all four keys null), `total_runtime_seconds=None`, `quality_status=None`, `artifact_paths=None`, `stalled_phase=None`.
- **Invariant 6 (--check-only):** PASS. `failing_check_name` is set only when `pre_passed=False`; `document_folder` is explicitly overwritten to `None` at line 462 via `dataclasses.replace`; `failure_kind=None` on success, `"readiness-failed"` on fail.
- **Invariant 7 (`kind` always `"demo_run_report"`):** PASS. `DEMO_REPORT_KIND` constant; no alternative spelling appears.
- **Invariant 8 (`cpu_fallback_detection` always present with closed-set values):** PASS. `_all_null_cpu_fallback()` returns a `CPUFallbackDetection` with both probes set to `"skipped"` on every no-pipeline-ran path; the post-run interrogation builds a real `CPUFallbackDetection` on pipeline paths.

### Exit-code mapping (FR-021, cli-contract.md §"Exit codes")

- **Exit 0 (success):** PASS. `_exit_code_for` returns `ExitCode.SUCCESS` when `runtime_outcome == "success"`.
- **Exit 1 (readiness-failed):** PASS. Returned when `failure_kind == "readiness-failed"`. The readiness-fail branch at orchestrator.py:409-436 sets this.
- **Exit 2 (invalid-input):** PASS. Returned when `failure_kind == "invalid-input"`. Voter-config failure, canonicalize failure, source.pdf missing, and eager-delete failure all set this.
- **Exit 3 (pipeline-runtime-timeout):** PASS. Returned when `runtime_outcome == "timeout"` OR `failure_kind == "pipeline-runtime-timeout"`. `_run_phase` re-raises `TimeoutError` so the outer handler at line 579 catches it.
- **Exit 4 (pipeline-runtime-error / cpu-fallback-detected):** PASS. Falls through `_exit_code_for` to the catch-all `ExitCode.PIPELINE_RUNTIME_ERROR`. CPU-fallback rewrite at line 653-660 sets the right pair.
- **Exit 5 (artifact-schema-validation-failed):** PASS *for the intended case* (post-pipeline schema check fails after a successful run). DRIFT for the unintended case where check 7 mis-rewrites a phase failure — see **K1**.
- **No other exit codes are produced:** PASS. The `IntEnum` only defines 0-5; `_exit_code_for` returns one of those six values exhaustively.

### Fixed-order readiness vocabulary (FR-016, readiness-vocabulary.md)

- **8-check declaration order:** PASS. `READINESS_CHECK_ORDER` at `enums.py:55-64` matches the contract verbatim. `runner._build_pre_pipeline_checks` and `_build_post_pipeline_checks` instantiate them in the same order.
- **Skip-after-first-fail rule:** PASS. `runner.run_pre_pipeline` lines 84-91 marks every check after a fail as `"skipped"` with `elapsed_seconds=0.0` and no diagnostic. Same pattern in `run_post_pipeline`.
- **`--check-only` skips checks 7-8:** PASS. `run_post_pipeline` lines 102-104 returns `"skipped"` for both when `context.check_only` is True.
- **Side-channel forwarding (cached `/api/ps` body):** PASS. `OllamaReachabilityCheck` publishes `side_channel=body`; `runner` updates `ctx.cached_api_ps_body` via `dataclasses.replace`. Downstream `OllamaPlacementCheck` and `OllamaContextLengthCheck` read it. `OllamaPlacementCheck` explicitly does NOT republish `side_channel` (deliberate, with a comment at lines 107-110).
- **`failing_check_name` is the first failing check:** PASS. `first_failing_check_name` at `runner.py:135-140` iterates `pre_results` and returns the first `"fail"`.

### Per-check predicates (readiness-vocabulary.md)

- **Check 1 — interpreter/venv:** PASS (FR-002 / FR-003). `interpreter.py` resolves `sys.executable` via `os.path.realpath` and substring-matches against `(".venv-paddle-rocm", ".venv-paddle-dcu")`. The substring match is a soft form of "under prefix" — acceptable on Linux paths.
- **Check 2 — paddle-rocm-preflight (Q7 two-shape distinction):** PASS. `paddle_preflight.py:31-67` distinguishes (a) `ImportError`/`ModuleNotFoundError` (observed = `{"import_error": ...}`) from (b) state != `PPSTRUCTUREV3_INIT_SUCCEEDED` (observed = `{"import_ok": true, "state": ...}`). Single closed-vocabulary check name retained.
- **Check 3 — ollama-reachability (2-second timeout):** PASS. `ollama_reach.py:24` sets `_HTTP_TIMEOUT_SECONDS = 2.0`. Caches body via `side_channel`.
- **Check 4 — ollama-version (min 0.4.0):** PASS. `ollama_version.py:88` compares `Version(raw_version) >= Version(MIN_OLLAMA_VERSION)`. Pre-empts check 5 via the runner's skip-after-fail rule.
- **Check 5 — ollama-model-gpu-placement (size_vram > 0 AND size_vram == size):** PASS. `ollama_placement.py:102` enforces the exact strict equality.
- **Check 6 — ollama-context-length:** PASS. `ollama_ctx_len.py:67-72` — when the field is absent, returns `"pass"` (soft pass with the runtime-fallback contract). When present, requires `ctx_len >= context.ollama_context_length`.
- **Check 7 — artifact-schema-validation:** PASS for the predicate itself (validates all 4 artifacts, aggregates failures into a list preserving canonical order). DRIFT for the orchestrator's handling of the check's verdict — see **K1**.
- **Check 8 — pipeline-runtime-timeout:** PASS. `runtime_timeout.py` reads `context.runtime_timeout_observed` (set by the orchestrator's `_on_timeout` handler) and reports fail with the `>{BOUNDED_TIMEOUT_SECONDS} seconds (stalled in phase '...')` diagnostic.

### 2 KiB truncation with UTF-8 boundary (Q5)

- **Implementation:** PASS. `serialization.py:36-53`. `_truncate_observed_value` JSON-renders the value, encodes UTF-8, truncates to ≤2048 bytes, retreats while continuation bytes (`(byte & 0xC0) == 0x80`) appear at the tail, decodes with `errors="ignore"` for safety, appends `"… [truncated]"`.
- **Sentinel string:** PASS. `_TRUNCATION_SENTINEL = "… [truncated]"` matches the contract verbatim.
- **No `observed_original_bytes` sibling:** PASS (Q5 option A — operators see only the truncated form).

### 3-dp float rounding (R-023.21)

- **`round_wall_clock` helper:** PASS. `serialization.py:26-33` rounds non-null floats to 3 dp.
- **Applied to every wall-clock field:** PASS. `_report_to_dict` (lines 85, 91, 99-102, 103) routes `ReadinessCheck.elapsed_seconds`, `ReadinessSummary.elapsed_seconds`, `PhaseTimings.{preprocess,extraction,routing,final_payload}`, and `total_runtime_seconds` through `round_wall_clock`. `cpu_fallback_detection` fields are dicts/strings — no floats to round.

### stderr severity prefix format (R-023.7)

- **Format:** PASS. `log.py:_emit` writes `f"{severity}:[{prefix_for(run_id)}] {msg}\n"`. Severities INFO/WARN/ERROR.
- **Line buffering:** PASS. `_ensure_line_buffering` reconfigures `sys.stderr` to line-buffered mode; idempotent.
- **8-char prefix:** PASS. `run_id[:8]` per R-023.6.

### Success-path stderr signals (Q1, Q2)

- **Q1 — full run success line:** PASS. orchestrator.py:712-716 emits `log.info(run_id, f"runtime: success / quality: {quality_status}")` immediately before the final `_emit_report` call.
- **Q2 — `--check-only` success line:** PASS. orchestrator.py:443 emits `log.info(run_id, f"readiness passed ({round(pre_elapsed, 3)}s)")` on the check-only-success branch.

### Sub-module stderr propagation (Q10)

- **Phase-tag closed set (preprocess / extraction / routing / final_payload / evaluator):** PARTIAL PASS. The orchestrator's `_run_phase` emits `phase: {phase} (starting)` and `phase: {phase} → {elapsed}s` lines, which carry the phase tag from the closed set. Evaluator subprocess output is NOT replayed line-by-line — only the result is consumed and emitted as a single WARN line on failure. The contract at cli-contract.md line 130 says "captured stderr is replayed through `log.info(run_id, f"<phase>: <line>")`". The current implementation does the structured composition tags but does NOT line-by-line replay captured stderr from the (in-process) sub-modules or the (subprocess) evaluator. DRIFT — but soft, because the in-process composer is stubbed and the evaluator runs with `capture_output=True` and `--quiet` so its stderr is intentionally suppressed. Logged here as PARTIAL PASS pending the real sub-module wiring (R-023.1 follow-on session).

### Exit-code table — per-cell (FR-021)

- **`(success, null) → 0`:** PASS.
- **`(success, "post-run-interrogation-unreachable") → 0`:** PASS. `_exit_code_for` returns `ExitCode.SUCCESS` on `runtime_outcome == "success"` regardless of `failure_kind`.
- **`(null, "readiness-failed") → 1`:** PASS.
- **`(null, "invalid-input") → 2`:** PASS.
- **`("timeout", "pipeline-runtime-timeout") → 3`:** PASS.
- **`("failed_at_<phase>", "pipeline-runtime-error") → 4`:** PASS.
- **`("failed_at_extraction", "cpu-fallback-detected") → 4`:** PASS via the catch-all branch.
- **`("failed_at_final_payload", "artifact-schema-validation-failed") → 5`:** PASS for the intended case. DRIFT for the misuse case described in K1.

### R-023 decisions (21 total)

- **R-023.1 (in-process composition):** PASS (stubbed by design — `_DefaultPipelineComposer` raises `PipelineUnavailable` for every phase; tests substitute a stub composer; the real wiring is deferred to a follow-on session per the docstring at orchestrator.py:106-115).
- **R-023.2 (`pipeline_version` from importlib.metadata):** PASS. `version.py:8-13`.
- **R-023.3 (exception → exit-code mapping):** PARTIAL PASS. The generic `except Exception` catch-all at orchestrator.py:542-547 maps every sub-module exception to `failed_at_<phase>` + `pipeline-runtime-error` + exit 4. The contract enumerates specific exception classes (PreprocessError, ExtractionError, RoutingError, AssemblerInvariantError, OllamaContextWindowError) that "should be" caught explicitly to set specific diagnostics. With the stubbed default composer (R-023.1), the explicit exception classes are not yet exercised; the catch-all is correct for the current state. DRIFT will surface only when the real composer lands.
- **R-023.4 (test stubbing strategy):** PASS (out of scope for the runtime code, but the test infrastructure honoring `cpu`/`gpu` markers exists per pyproject.toml).
- **R-023.5 (`gpu` pytest marker registered):** PASS. `pyproject.toml:63-65` declares the `gpu` marker.
- **R-023.6 (UUID4 run_id; 8-char stderr prefix):** PASS. `run_id.new_run_id()` and `prefix_for()`.
- **R-023.7 (no `--verbose`/`--quiet`; INFO/WARN/ERROR severity prefix):** PASS. cli.py declares only the 5 closed flags + --help/--version; log.py uses fixed severity prefixes.
- **R-023.8 (no per-phase sub-budgets):** PASS. The only timeout is the 600 s SIGALRM around the full pipeline (orchestrator.py:572).
- **R-023.9 (cold vs warm cache budgets; SC-007 warm-only):** PASS (runbook-level only; no code obligation).
- **R-023.10 (minimum Ollama version 0.4.0):** PASS. `enums.MIN_OLLAMA_VERSION = "0.4.0"`; `ollama_version.py` enforces it.
- **R-023.11 (closed CheckDiagnostic key set + stderr mirror):** PASS. Every readiness check emits a `CheckDiagnostic` with the four declared keys (`checked`, `observed`, `expected`, `remediation`); `diagnostics.format_diagnostic_line` projects to stderr.
- **R-023.12 (field-order stability):** PASS. `serialization.to_json_line` uses `sort_keys=False, ensure_ascii=False, separators=(",", ":")`. Declaration order in `_report_to_dict` matches `data-model.md §1` and the schema-doc order.
- **R-023.13 (evaluator subprocess argv):** PASS. `evaluator_subprocess.py:51-62` matches the pin-down exactly: `[sys.executable, "-m", "dartwing_ocr.evaluator", "evaluate-document", "--folder", str(document_folder), "--quiet"]`, `cwd=str(document_folder)`, `env=os.environ.copy()`, `capture_output=True`, `text=True`, `timeout=60.0`, `check=False`. Sidecar warn-and-skip and subprocess-failure warn-and-fallback both implemented per the R-023.13 expanded clause.
- **R-023.14 (`OLLAMA_BASE_URL` validation):** **DRIFT — see K2.**
- **R-023.15 (CPU-fallback probes):** PARTIAL PASS. Probe timeouts (2 s each), aggregate budget (5 s), `fell_back` rewrite to `failed_at_extraction` + `cpu-fallback-detected`, `unreachable` → `post-run-interrogation-unreachable` are all implemented. Aggregate-budget-exceeded path is incomplete (K3); pre-run snapshot is not threaded (K4); consistent-path INFO line missing (K7); diagnostic_msg is null in the unreachable success case (K6).
- **R-023.16 (CI test runtime budget):** N/A (test infrastructure, not source).
- **R-023.17 (runbook update strategy):** N/A (doc).
- **R-023.18 (pytest fixture corpus):** N/A (test infrastructure).
- **R-023.19 (not composed with feature 011):** PASS by absence (no feature-011 imports in the gpu_demo package).
- **R-023.20 (quality_status truth table):** PASS. `quality_status._GATE_TRUTH_TABLE` matches the 6-row table verbatim. Evaluator downgrade-only rule at lines 61-67. Warn-and-skip preserves `"gate"` source per Q4.
- **R-023.21 (3-dp float rounding):** PASS. Verified above.

### Idempotency contract (FR-017)

- **Eager-delete by exact basename:** PASS. `folder_canonicalize.safe_eager_delete` iterates `CANONICAL_ARTIFACT_BASENAMES` (4 exact names) — no glob, no recursion.
- **Symlink-escape pre-flight:** PASS. `safe_eager_delete` calls `resolved.relative_to(folder_str)` and raises `EagerDeleteError` on escape; the orchestrator maps to exit 2.
- **Idempotent on missing files:** PASS. The delete loop checks `target.is_symlink() or target.exists()` before `unlink()`.
- **Exit 2 on permission/IO failure:** PASS. `except OSError as exc` wraps the unlink and re-raises as `EagerDeleteError`.
- **Source.pdf, expected.json, semantic_table_truth.json preserved (SC-010):** PASS. Only the 4 declared basenames are targeted.
- **`--check-only` skips eager-delete:** PASS. Orchestrator's eager-delete call at line 467-475 is in the post-readiness, non-check-only branch.

### --check-only contract (FR-018)

- **Checks 1-6 execute; 7-8 reported as skipped:** PASS. `run_pre_pipeline` runs the first 6; `run_post_pipeline` returns `"skipped"` for both when `context.check_only` is True.
- **No pipeline runs:** PASS. The check-only branch at orchestrator.py:438-464 emits the report and returns before reaching the eager-delete + phase block.
- **No eager-delete:** PASS.
- **No post-run device interrogation:** PASS. The CPU-fallback block at line 641 is gated by `if runtime_outcome is not None`; under --check-only `runtime_outcome` stays `None`.
- **All pipeline/quality/timing/artifact fields null:** PASS.
- **`document_folder = null`:** PASS. `dataclasses.replace(report, document_folder=None)` at line 462.
- **`bounded_timeout_seconds = 600`:** PASS.

### Sundry

- **`pyproject.toml [project.scripts]` exposes `dartwing-gpu-demo`:** PASS. Line 42.
- **`python -m dartwing_ocr.gpu_demo` entry point:** PASS. `__main__.py` calls `cli.main()` and exits with the returned code.
- **`--help` / `--version` exit 0 without emitting `DemoRunReport`:** PASS. argparse exits before the orchestrator is imported (lazy import at cli.py:104).

---

## What was reviewed

- `src/dartwing_ocr/gpu_demo/__init__.py`
- `src/dartwing_ocr/gpu_demo/__main__.py`
- `src/dartwing_ocr/gpu_demo/cli.py`
- `src/dartwing_ocr/gpu_demo/cpu_fallback.py`
- `src/dartwing_ocr/gpu_demo/diagnostics.py`
- `src/dartwing_ocr/gpu_demo/enums.py`
- `src/dartwing_ocr/gpu_demo/evaluator_subprocess.py`
- `src/dartwing_ocr/gpu_demo/exit_codes.py`
- `src/dartwing_ocr/gpu_demo/folder_canonicalize.py`
- `src/dartwing_ocr/gpu_demo/log.py`
- `src/dartwing_ocr/gpu_demo/orchestrator.py`
- `src/dartwing_ocr/gpu_demo/quality_derivation.py`
- `src/dartwing_ocr/gpu_demo/quality_status.py`
- `src/dartwing_ocr/gpu_demo/report.py`
- `src/dartwing_ocr/gpu_demo/run_id.py`
- `src/dartwing_ocr/gpu_demo/serialization.py`
- `src/dartwing_ocr/gpu_demo/version.py`
- `src/dartwing_ocr/gpu_demo/voter_config_loader.py`
- `src/dartwing_ocr/gpu_demo/readiness/__init__.py`
- `src/dartwing_ocr/gpu_demo/readiness/base.py`
- `src/dartwing_ocr/gpu_demo/readiness/runner.py`
- `src/dartwing_ocr/gpu_demo/readiness/interpreter.py`
- `src/dartwing_ocr/gpu_demo/readiness/paddle_preflight.py`
- `src/dartwing_ocr/gpu_demo/readiness/ollama_reach.py`
- `src/dartwing_ocr/gpu_demo/readiness/ollama_version.py`
- `src/dartwing_ocr/gpu_demo/readiness/ollama_placement.py`
- `src/dartwing_ocr/gpu_demo/readiness/ollama_ctx_len.py`
- `src/dartwing_ocr/gpu_demo/readiness/schema_validation.py`
- `src/dartwing_ocr/gpu_demo/readiness/runtime_timeout.py`
- `pyproject.toml` ([project.scripts] + pytest markers)

Cross-checked against:
- `specs/023-gpu-mvp-demo-hardening/spec.md` (28 FRs)
- `specs/023-gpu-mvp-demo-hardening/data-model.md` (§1 21 keys + 8 invariants; §4 8 enums; §5 CPUFallbackDetection; §6 VoterConfigReference; §9–§11 JSON examples)
- `specs/023-gpu-mvp-demo-hardening/contracts/cli-contract.md` (5-flag set; exit-code table; stdout/stderr discipline; idempotency contract; --check-only contract)
- `specs/023-gpu-mvp-demo-hardening/contracts/demo-report-schema.md` (top-level shape; field reference; outcome matrix)
- `specs/023-gpu-mvp-demo-hardening/contracts/readiness-vocabulary.md` (fixed-order; per-check predicate; diagnostic shape)
- `specs/023-gpu-mvp-demo-hardening/research.md` (R-023.1 through R-023.21)
- `specs/023-gpu-mvp-demo-hardening/audit-walkthrough-2026-05-25.md` (Q1–Q12)

## What was NOT reviewed

- Test files under `tests/integration/gpu_demo/` (separate agent)
- Security concerns (separate agent — `reviews/security-review.md` exists)
- Code correctness beyond contract alignment (separate agent)
- The runbook at `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md` (process artifact, not code)
- `coverage-fr-task-test.md` (traceability artifact, not code)
- The actual sub-module composer's per-phase behavior (R-023.1 default composer is intentionally stubbed; the real wiring lands in a follow-on workstation session)
