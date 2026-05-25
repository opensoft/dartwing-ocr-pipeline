# Observability + operator-UX review — round 2

**Date:** 2026-05-25
**Reviewer:** observability-reviewer-r2 (general-purpose, swarm round 2)
**Branch:** 023-gpu-mvp-demo-hardening @ 7f4aa00
**Frame:** if a colleague runs the demo cold, can they diagnose a failure in < 60 seconds?

## Diagnostic-message scorecard

| Readiness check | checked | observed | expected | remediation | Score 1-5 | Notes |
|---|---|---|---|---|---|---|
| `interpreter/venv` (`interpreter.py:44`) | `"Python interpreter path"` | absolute interpreter path | `path under one of ['.venv-paddle-rocm', '.venv-paddle-dcu']` | `Activate the Paddle ROCm venv: source .venv-paddle-rocm/bin/activate` | **5** | Best of the set. Verb + path + literal remediation command. |
| `paddle-rocm-preflight` (import-error branch, `paddle_preflight.py:39`) | `"Paddle ROCm wheel import"` | dict `{"import_error": "ImportError: ..."}` | `paddlepaddle_dcu importable from active venv` | `Install paddlepaddle-dcu in .venv-paddle-rocm (it is not currently importable).` | **4** | Solid; could name the pip command explicitly. |
| `paddle-rocm-preflight` (state-error branch, `paddle_preflight.py:83`) | `"Paddle device backend"` | dict `{"import_ok": True, "state": readout.state.value}` | `ppstructurev3_init_succeeded` | uses `readout.recommendation` fallback to generic reinstall | **3** | Heavily depends on what feature 014's preflight returns. If `recommendation` is empty, operator gets a generic "reinstall" — no link to `readiness-paddle.log` or `rocm-smi`. |
| `ollama-reachability` (HTTPError, `ollama_reach.py:44`) | `f"Ollama {url}"` | `f"{type(exc).__name__}: {exc}"` | `HTTP 200 with parseable JSON body` | `Start host Ollama: scripts/start-host-ollama-rocm-wsl.sh` | **5** | Excellent — points at the exact script. |
| `ollama-reachability` (non-200, `ollama_reach.py:64`) | `f"Ollama {url}"` | `f"HTTP {response.status_code}"` | (same) | `Check host Ollama is running and accepting requests.` | **3** | Remediation is hand-wavy. A 503/500 operator won't know whether to restart or wait. |
| `ollama-version` (`ollama_version.py:115`) | `f"Ollama {url}"` | raw version string (e.g. `"0.3.12"`) | `>= 0.4.0` | `Upgrade Ollama to >= 0.4.0; see scripts/start-host-ollama-rocm-wsl.sh.` | **5** | Clear. |
| `ollama-model-gpu-placement` (no entry, `ollama_placement.py:70`) | `f"Ollama /api/ps for model '<name>'"` | `None` | `entry with name '<name>' present` | `Load the model: ollama pull <name> or ensure it is referenced before the demo runs.` | **5** | Names the model + ships the literal `ollama pull` command. |
| `ollama-model-gpu-placement` (partial-VRAM, `ollama_placement.py:117`) | `f"GPU placement of '<name>'"` | dict `{"size": ..., "size_vram": ...}` | `size_vram > 0 AND size_vram == size` | `Restart Ollama on a fresh GPU context; the model is partially or fully on CPU.` | **3** | The numeric observed is helpful, but the remediation buries the lede — operator must already understand that `size_vram < size` means partial placement. Could surface `delta = size - size_vram` bytes. |
| `ollama-context-length` (`ollama_ctx_len.py:87`) | `f"Ollama context length for '<name>'"` | int (e.g. `1024`) | `>= 2048` | `Restart host Ollama with OLLAMA_CONTEXT_LENGTH=2048; see scripts/start-host-ollama-rocm-wsl.sh.` | **5** | Includes the exact env var + value. |
| `artifact-schema-validation` (`schema_validation.py:108`) | `"Schema validation of 4 canonical artifacts"` | list of `{path, error}` dicts | `all four artifacts schema-valid against v1.3.0 contract set` | `Inspect the listed artifact(s); a multi-artifact failure usually indicates a deeper pipeline regression — start with the earliest failure in canonical order.` | **3** | Decent narrative remediation but no command. Operator has to know how to run `python -m dartwing_ocr.validator validate artifact <path>` themselves. |
| `pipeline-runtime-timeout` (`runtime_timeout.py:56`) | `"Pipeline runtime"` | `f">600 seconds (stalled in phase '<phase>')"` | `<= 600 seconds` | `Inspect partial artifacts left in the per-document folder; the stalled phase is identified in 'stalled_phase'. Check Ollama and Paddle health.` | **3** | Vague. Doesn't name `ollama ps` / `rocm-smi` / `top` as concrete next-step commands. |

**Aggregate**: 7 strong (4-5), 4 mediocre (3). The mediocre ones share a pattern — they explain *what* went wrong but tell the operator to "check" or "inspect" without a copy-pasteable command.

## stderr line audit

Lines from `orchestrator.py` (line numbers are 7f4aa00):

| Call site | Severity | Actionable? | Self-contained? | Notes |
|---|---|---|---|---|
| L417 `log.error(run_id, f"invalid input: {exc}")` (voter-config) | ERROR | yes (VoterConfigError messages already name the path / field) | yes | Good. |
| L439 `log.warn(... "voter config has multiple voters; demo uses the first ...")` | WARN | yes — explains chosen model | yes | Correct severity (didn't fail). |
| L453 `log.error(run_id, f"invalid input: {exc}")` (OLLAMA_BASE_URL) | ERROR | yes | yes | `_InvalidOllamaBaseURL` messages are descriptive. |
| L477 `log.info(... "using non-localhost Ollama base URL: ...")` | INFO | informational only | yes | Correct. Could be WARN (non-default behaviour the operator may not realise). See recommendation #4. |
| L490 `log.error(run_id, f"invalid input: {exc}")` (canonicalize) | ERROR | yes | yes | Good. |
| L514 `log.error(... f"invalid input: source.pdf not found in {canonical_folder}")` | ERROR | yes (names the path) | yes | Excellent. |
| L545 `log.info(... "ignoring --document-folder / --preset / --with-evaluator under --check-only")` | INFO | informational | yes | Correct severity. Slightly noisy if only one flag was provided — message names all three. |
| L569 `log.info(... f"readiness: {r.name} → pass ({round(...)}s)")` | INFO | progress signal | yes | One line per pass. 6 lines on a clean run — operator sees progress. |
| L576 `log.error(... diagnostics.format_diagnostic_line(r.name, diag))` | ERROR | yes — single line carries `checked/observed/expected/remediation` | yes | This is the **stderr-line-of-record** for readiness failures. Quality depends entirely on the diagnostic (see scorecard). |
| L614 `log.info(... f"readiness passed ({round(...)}s)")` | INFO | progress | yes | Good `--check-only` success cue. |
| L643 `log.info(... f"eager-delete: 4 artifacts removed from {canonical_folder}")` | INFO | progress | yes | Good. |
| L648 `log.error(... f"invalid input: {exc}")` (eager-delete) | ERROR | yes | yes | Good. |
| L695 `log.info(... f"phase: {phase} (starting)")` | INFO | progress | yes | Critical for the silent-gap problem (see §Progress narrative). |
| L704, L720 `log.error(... f"phase {phase} failed: {exc}")` | ERROR | partial — exception message quality depends on the sub-module | yes | Pipeline runtime errors flow through here. **This is the stderr-line-of-record for exit 4.** |
| L730 `log.info(... f"phase: {phase} → {round(...)}s")` | INFO | progress + timing | yes | Good. |
| L773 `log.error(... f"pipeline runtime timeout — stalled phase: {stalled_phase}")` | ERROR | yes — names the phase | yes | **Stderr-line-of-record for exit 3.** Could include `inspect partial artifacts in <folder>` for parity with the diagnostic. |
| L865 `log.warn(... "post-run interrogation exceeded 5s budget; CPU-fallback detection inconclusive")` | WARN | partial — tells operator the verdict is unreliable, doesn't say what to do | yes | Severity correct (didn't fail outright). See recommendation #6. |
| L878 `log.error(... diagnostic_msg)` (CPU fallback detected) | ERROR | yes — names ollama_post_run + paddle_post_run | yes | Good. |
| L889 `log.warn(... diagnostic_msg)` (post-run-interrogation-unreachable) | WARN | partial | yes | Inconsistency: when `runtime_outcome=success` but probes say "unreachable", we still exit 0. Operator may not realise the WARN is non-blocking. See recommendation #7. |
| L898 `log.info(... "post-run: ollama still GPU-placed; paddle still rocm_gpu")` | INFO | confirmation | yes | Good "everything-still-OK" signal. |
| L915, L921 evaluator WARN lines | WARN | partial | yes | Correct severity. |
| L951 `log.info(... f"runtime: success / quality: {quality_status}")` | INFO | success cue | yes | Excellent final signal. |

## JSON readability

**Well-named fields** (operator can guess them):
- `run_id`, `interpreter_path`, `voter_config_path`, `document_folder`, `runtime_outcome`, `stalled_phase`, `failure_kind`, `quality_status`, `artifact_paths`, `total_runtime_seconds`, `bounded_timeout_seconds`.

**Field-name inconsistencies** (operator surprises):
1. **`extraction` vs `extract`** — `phase_timings.extraction` (full word) but the composer Protocol method is `extract()`. The closed enums `RuntimeOutcome="failed_at_extraction"` and `StalledPhase="extraction"` correctly use the long form. Consistent in stable surface — composer method is implementation-detail only. OK.
2. **`failing_check_name` vs `failure_kind`** — two distinct top-level keys whose names suggest they're related but they describe orthogonal axes (one names a readiness check, the other names the outcome class). On a readiness fail you get `failing_check_name="ollama-version"` AND `failure_kind="readiness-failed"`. A new operator may `jq '.failing_check_name'` and not find anything on an exit-4 run.
3. **`cpu_fallback_detection.ollama_post_run`** uses the `ProbeResult` enum (`"consistent" / "fell_back" / "unreachable" / "skipped"`). The verb tense ("fell_back" past tense, "unreachable" present, "consistent" adjective) is mixed but matches the enum literals — closed vocabulary, acceptable.
4. **`expected_extraction_model`** — clear, but operators may look for `ollama_model` first since the readiness check is named `ollama-model-gpu-placement`. Cross-link is implicit.
5. **`schema_version`** in the JSON refers to the **DemoRunReport schema** (currently `"0.1.0"`), NOT the contract-set version (`"v1.3.0"`) and NOT `pipeline_version`. Triple-namespacing of "versions" is potentially confusing. The two pipeline-related fields (`schema_version` + `pipeline_version`) are adjacent, which helps.

**Closed-enum consistency audit**:
- `RuntimeOutcome`: `success` / `failed_at_<phase>` / `timeout` — mixed snake_case + verb-tense. Acceptable for a closed enum.
- `QualityStatus`: `pass` / `weak` / `review_required` — three distinct grammatical forms. Inherited from feature 020 — out of scope here.
- `FailureKind`: kebab-case (`readiness-failed`, `invalid-input`, `cpu-fallback-detected`) — **inconsistent with snake_case used by `RuntimeOutcome` / `StalledPhase` / `QualityStatusSource`**. Operator running `jq '.failure_kind'` will get `"readiness-failed"` but `jq '.runtime_outcome'` returns `"failed_at_extraction"`. **Recommendation #1 below.**
- `StalledPhase`: snake_case (`preprocess`, `extraction`, `routing`, `final_payload`). Consistent.
- `ReadinessCheckName`: kebab-case + one slash (`interpreter/venv`, `paddle-rocm-preflight`). The slash in `interpreter/venv` is the odd one out. Documented as closed-vocabulary FR-016 so changing it is breaking.
- `ProbeResult`: snake_case (`consistent` / `fell_back` / `unreachable` / `skipped`). Consistent.

**Documented null-fields**: The `cli-contract.md` "Worked examples" show `…` for elided fields in the JSON. The schema doc lists null-on-every-outcome (FR-019 / data-model §1) but the worked examples don't show the full null-on-readiness-fail or null-on-invalid-input report shape. Operators relying on `jq '.quality_status'` on a failed run will see `null` — that's correct behaviour but not visible in the CLI contract examples.

## Outcome-to-stderr cheat sheet (proposed — does NOT currently exist in runbook)

Searched both `runbook-gpu-mvp-demo.md` and `cli-contract.md` for "cheat sheet" / "stderr-line-of-record" — **no such table exists**. The runbook does have remediation tables for the Step 1 helpers but not a single "given exit code N, look at stderr line X" reference. The CLI contract has Worked Examples for 3 of the 6 exit codes (0, 1, 2). Exits 3, 4, 5 have no worked example.

| Exit | First-line-of-record on stderr | Then look at (in stderr) | Then look at (in stdout JSON) |
|---|---|---|---|
| 0 (success) | `INFO:[...] runtime: success / quality: <quality_status>` (orchestrator.py:951) | the `post-run: ollama still GPU-placed; paddle still rocm_gpu` confirmation immediately before | `.quality_status`, `.phase_timings`, `.cpu_fallback_detection` |
| 1 (readiness-failed) | the **single** `ERROR:[...] readiness check '<name>' failed — observed ..., expected ..., Remediation: ...` (orchestrator.py:576 via diagnostics.format_diagnostic_line) | preceding `INFO` lines show which checks already passed | `.failing_check_name`, `.readiness.checks[]` (find the one with `status:"fail"`) |
| 2 (invalid-input) | the **single** `ERROR:[...] invalid input: <msg>` (multiple call sites: voter-config L417, base-url L453, canonicalize L490, source.pdf L514, eager-delete L648) | none — invalid-input fails fast before readiness | `.failure_kind == "invalid-input"`, `.diagnostic` |
| 3 (pipeline-runtime-timeout) | `ERROR:[...] pipeline runtime timeout — stalled phase: <phase>` (orchestrator.py:773) | the preceding `phase: <phase> (starting)` INFO line shows when the phase began | `.stalled_phase`, `.phase_timings.<phase>` (the timed-out phase has a non-null wall-clock for partial elapsed) |
| 4 (pipeline-runtime-error OR cpu-fallback-detected) | either `ERROR:[...] phase <phase> failed: <exc>` (orchestrator.py:704/720) **OR** `ERROR:[...] post-run interrogation detected CPU fallback (ollama=..., paddle=...)` (orchestrator.py:878) | preceding INFO `phase: <phase> (starting)` line | `.runtime_outcome` (e.g. `failed_at_extraction`), `.failure_kind` distinguishes the two paths |
| 5 (artifact-schema-validation-failed) | **NONE — this is a gap**. The schema-validation check fails but the orchestrator does not emit an ERROR line for it (it only sets diagnostic_msg into the JSON report). | nothing — operator must read the JSON | `.failing_check_name=="artifact-schema-validation"` is NOT set (`failing_check_name` is only set on exits 1/2). On exit 5, the operator must find the schema-validation check inside `.readiness.checks[]` and read its `.diagnostic.observed` list. |

**Critical gap**: exit 5 has **no stderr line of record**. See recommendation #2.

## Failure-trace coherence

**Trace when pipeline fails at `extraction`** (with non-success runtime_outcome, no schema-validation, no CPU fallback):

1. `INFO:[..] readiness: ... → pass (...)` × 6
2. `INFO:[..] eager-delete: 4 artifacts removed from ...`
3. `INFO:[..] phase: preprocess (starting)`
4. `INFO:[..] phase: preprocess → 4.21s`
5. `INFO:[..] phase: extraction (starting)`
6. `ERROR:[..] phase extraction failed: <exc>`
7. **(post-pipeline readiness runs — schema-validation skipped because `runtime_outcome != None`, OK)**
8. **(CPU-fallback interrogation runs — 2 s ollama probe + 2 s paddle probe ≈ 4 s)**
9. Possibly `WARN:[..] post-run interrogation exceeded 5s budget` OR `INFO:[..] post-run: ollama still GPU-placed; paddle still rocm_gpu`
10. JSON line on stdout

**Coherence assessment**:
- Operator sees ONE `ERROR` line (line 6). Good.
- Lines 8-9 may add 4-5 seconds of silent wait + a WARN/INFO that's about a different thing (post-run device health) — potentially confusing after a phase failure.
- **The post-run probes run even when the pipeline failed**. That's load-bearing for SC-004 (silent CPU fallback detection on success path), but on a non-success path it adds noise. The orchestrator could short-circuit cpu-fallback interrogation when `runtime_outcome` is already a `failed_at_*` value AND the failure_kind is `pipeline-runtime-error` (i.e., we already know a phase failed) — saving 4-5 s and removing the trailing WARN/INFO. See recommendation #5.

**Trace when extraction succeeds but artifact-schema-validation fails (exit 5)**:

1. All `INFO` lines for readiness + phases (clean)
2. Post-pipeline `artifact-schema-validation` check runs — fails silently (no stderr emission)
3. CPU-fallback runs (probably consistent)
4. `INFO:[..] post-run: ollama still GPU-placed; paddle still rocm_gpu`
5. JSON line on stdout

The operator sees no ERROR line at all but the exit code is 5. **This is the worst UX failure in the audit.** See recommendation #2.

## New log lines from 7f4aa00 — audit

| Line | Severity | Order | Actionability | Suggested rewrite |
|---|---|---|---|---|
| `INFO: using non-localhost Ollama base URL: <url>` (B5) | INFO | emitted right after URL validation, before readiness | low — informational only | Consider promoting to **WARN** when host is not in `_LOCALHOST_HOSTS`: operator may be running against a stale `OLLAMA_BASE_URL` from their shell history without realising it. The WARN severity flags "you may not have intended this" semantics. |
| `INFO: post-run: ollama still GPU-placed; paddle still rocm_gpu` (K7) | INFO | end of run | confirmation | Good as-is. Matches the cli-contract.md worked example. Pairs with the final `runtime: success / quality: pass` line. |
| `WARN: post-run interrogation exceeded 5s budget; CPU-fallback detection inconclusive` (K3) | WARN | after pipeline complete | tells operator the result is unreliable but not what to do | Append `; consider re-running once Ollama and Paddle are responding faster.` |
| `WARN: post-run interrogation could not confirm GPU placement (ollama=..., paddle=...)` (K6) | WARN | after pipeline complete | partial — names which probe was unreachable | Append `; pipeline output is still emitted, but device-health verdict is incomplete. Re-run if reproducibility matters.` |

**Ordering nit (line 898 vs lines 865/878/889)**: The four post-run interrogation lines form an `if/elif/elif/elif` cascade. The first three (`fell_back`, `unreachable`, `budget_exceeded`) are problem lines; the fourth (`consistent`) is the good signal. In the source the elif chain is intuitive, but the JSON `cpu_fallback_detection` object will carry only ONE state per run, so the stderr emissions don't overlap — no real ordering concern.

## Multi-line vs single-line diagnostics

The new `log._sanitize` strips `\n` from interpolated values. For the readiness diagnostic line — which carries `checked`, `observed`, `expected`, `remediation` concatenated — single-line is fine, **with one caveat**: `paddle-rocm-preflight`'s `observed` is a dict (`{"preflight_error": "..."}`) that gets `repr()`'d via `format_diagnostic_line`'s `!r`. For a long ROCm traceback that's a multi-line string normally, sanitization collapses it to one line with `\\u2588` markers (the replacement char). Operator loses the stack-trace context.

**Compensation**: the JSON-side `diagnostic.observed` field preserves the original (no sanitization on JSON serialization — see `serialization.py`, where `_truncate_observed_value` only enforces the 2 KiB byte cap), so operators can recover the full message by `jq '.readiness.checks[] | select(.status=="fail") | .diagnostic.observed'`. This is correct but undocumented — no comment in the diagnostics module or the runbook explains "JSON has the long form, stderr has the short form."

**Recommendation #8 (below) is to document this dual-channel contract.**

## Top recommendations (8)

### 1. Normalize `FailureKind` enum to snake_case
**Change**: rename `"readiness-failed"` → `"readiness_failed"`, `"invalid-input"` → `"invalid_input"`, etc. in `enums.py:FailureKind` and propagate through `cli-contract.md` exit-code table.
**Why**: every other closed enum is snake_case. Operators using `jq` will guess `failed` not `readiness_failed`, but at least the kebab/snake inconsistency goes away.
**Risk**: closed-vocabulary schema_version bump (0.1.0 → 0.2.0 minor). Worth doing now before MVP rollout.

### 2. Emit an ERROR stderr line on schema-validation failure (exit 5)
**Change**: In `orchestrator.py:817-825`, when the schema-validation check fails, also emit:
```
log.error(run_id, f"artifact-schema-validation failed: {len(failures)} of 4 artifacts; first error: <error>")
```
**Why**: Today exit 5 has no stderr line of record. Operator gets a silent exit with status 5 and must read JSON to discover what happened.
**Risk**: low — purely additive logging.

### 3. Add a "stderr cheat sheet" section to `runbook-gpu-mvp-demo.md`
**Change**: Add the §"Outcome-to-stderr cheat sheet" table from this review to the runbook (after Step 5 / before Appendix). Cross-link from `cli-contract.md` "Exit codes" table.
**Why**: zero current operator-facing doc tells the colleague "given exit N, look at stderr line X." This review's table is enough; just need to add it.
**Risk**: none — pure docs.

### 4. Promote the non-localhost-OLLAMA_BASE_URL line to WARN
**Change**: `orchestrator.py:477` `log.info` → `log.warn`.
**Why**: Operators who set `OLLAMA_BASE_URL=http://my-other-machine:11434` for a one-off test and forgot to unset it will silently be running against the wrong Ollama. WARN flags "you may not have intended this."
**Risk**: very low — INFO is too quiet, ERROR would be too loud.

### 5. Short-circuit CPU-fallback probes on pipeline-runtime-error
**Change**: In `orchestrator.py:842-845`, skip post-run interrogation when `runtime_outcome in {"failed_at_preprocess", "failed_at_extraction", "failed_at_routing", "failed_at_final_payload"}` AND `failure_kind == "pipeline-runtime-error"`. Set `cpu_fallback = _all_null_cpu_fallback()` (matches the no-probe-ran state). The SC-004 invariant (catch silent CPU fallback) only matters on the success path, where the pipeline returned a 200 but actually fell back — on a phase exception, we already know it failed, no need to probe.
**Why**: 4-5 s of post-run latency + a trailing WARN/INFO line that's about a different concern. Tightens the failure narrative.
**Risk**: medium — needs a test to assert SC-004 is unaffected (it only enforces on success path per the orchestrator code). Worth doing.

### 6. Add a concrete next-step command to the timeout diagnostic and the partial-VRAM diagnostic
**Change**:
- `runtime_timeout.py:63`: append `Check 'ollama ps' to see if the model is still loaded; check 'rocm-smi' for VRAM pressure.`
- `ollama_placement.py:122`: replace "Restart Ollama on a fresh GPU context" with `Stop and re-start Ollama via scripts/start-host-ollama-rocm-wsl.sh; the model is partially or fully on CPU (size - size_vram = <delta> bytes are not on GPU).`
**Why**: turns "do something" remediation into copy-pasteable commands. Lifts the 3-scorecard checks to 4-5.
**Risk**: none — purely text changes.

### 7. Document the dual-channel diagnostic convention
**Change**: Add to `runbook-gpu-mvp-demo.md` (and to `diagnostics.py` docstring):
> Stderr lines carry a short, single-line summary of any failing readiness check. The full diagnostic — including multi-line observations like ROCm traces — is preserved in the stdout JSON report under `.readiness.checks[].diagnostic`. Use `jq '.readiness.checks[] | select(.status=="fail") | .diagnostic'` to recover the long form.
**Why**: today this is implicit and operators may assume stderr is canonical.
**Risk**: none — docs only.

### 8. Reduce the `--check-only` flag-ignored INFO noise
**Change**: `orchestrator.py:540-548` currently emits one INFO listing all three potentially-ignored flags. Split into per-flag conditional emission so the operator only sees the flag they actually set.
**Why**: cosmetic but a colleague will scan-read the line and think the demo ignored more than it did.
**Risk**: none.

## Sign-off

**NEEDS-UX-PASS.**

The MVP is fundamentally operator-friendly — fixed 6-line readiness narrative, single-line ERROR per failure for exits 1-4, clean phase progress, success cue before JSON. But three concrete gaps must close before the GPU-MVP demo is "colleague-cold-runnable":

1. **Exit 5 has no stderr line of record** (recommendation #2). Today a schema-validation failure surfaces only in the JSON.
2. **No stderr cheat sheet in the runbook** (recommendation #3). Colleague can't map exit code → "look at line X" in under 60 s.
3. **`FailureKind` kebab-case is inconsistent with everything else** (recommendation #1). Cosmetic but operator-confusing on the `jq` command line.

The other 5 recommendations are quality-of-life — none block the MVP but each individually saves 10-30 s of operator confusion on a failure path.
