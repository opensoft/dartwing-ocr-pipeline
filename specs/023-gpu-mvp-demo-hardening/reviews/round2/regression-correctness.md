# Regression + correctness deep review — round 2

**Date:** 2026-05-25
**Reviewer:** regression-reviewer-r2 (general-purpose, swarm round 2)
**Branch:** 023-gpu-mvp-demo-hardening @ 7f4aa00
**Scope:** post-triage state — did the fixes solve what they claim, and do they have second-order effects?

## Summary

12 findings: **1 CRITICAL, 3 HIGH, 5 MEDIUM, 3 LOW**.
Status: **NEEDS-ATTENTION** (one new critical bug introduced by the B1 fix — same
"called nonexistent attribute" class of error the round-1 swarm flagged, this time
on the `Violation` model. Test suite cannot catch it because every test stubs
`_validate_artifact` and never exercises the real validator path.)

## "Did the fix solve the bug?" verdicts

| Round-1 ID | Fix landed? | Closed? | Caveats |
|---|---|---|---|
| B1 | yes | **NO** | Fix calls `validate_artifact(path, contract=<name>)` correctly, but the failure-diagnostic branch reads `first.code` and `first.message`. The real `Violation` model exposes `violation_code` and `reason` (see `src/dartwing_ocr/validator/report.py:96-105`). First real schema violation → AttributeError. See R1. |
| B2 | yes | YES | `if runtime_outcome is None:` guard is correct. Regression test asserts both exit code and `runtime_outcome` string. No second-order effects detected. |
| B3 | yes | PARTIAL | Mutable `_RunState` correctly bridges composer return values. But no test exercises this path — the stub composer returns `Path`, which `_extract_run_summary` rightly ignores. There is zero coverage that `quality_status` actually flips when a composer publishes a `run_summary` dict (T7 deferred only covers stub-composer schema fidelity, not run_summary plumbing). See R3. |
| B4 | yes | PARTIAL | Two correctness gaps remain. (a) The `except` arm catches only `TimeoutError`; a late SIGALRM arriving inside the cleanup path raises `TimeoutError` and is correctly swallowed, but `KeyboardInterrupt` arriving during the same window would still propagate and skip `_emit_report`. (b) `signal.getsignal()` can return `None` ("an unknown handler is in effect" per Python docs); the `if previous_handler is not None` guard skips the restore, leaking `_on_timeout` into the parent process for any subsequent test that reuses the SIGALRM slot. Not a regression (pre-existing), but worth tracking. |
| B5 | yes | YES | Validator is correct: `urlparse('not-a-url').scheme == ''` → rejects. Localhost set covers `localhost`, `127.0.0.1`, `::1`. INFO line emits on non-localhost hosts. Tests cover both invalid-URL and non-localhost paths. Ordering (after voter-config load, before canonicalize) matches R-023.14. |
| M3 | yes | YES | `_extract_pre_run_snapshot` correctly walks the cached `/api/ps` body. The `pre_size_vram > post_size_vram` drop check is correct. The user-flagged "partial→partial" scenario cannot reach this code path because readiness check 5 (`ollama-model-gpu-placement`) requires `size_vram == size AND size_vram > 0` and would have failed first. |
| K3 | yes | PARTIAL | Forcing both probes to `unreachable` on budget-exceeded is the right semantic. But the path is effectively **dead code**: the single probe `httpx.get(timeout=2.0)` cannot consume the 5-second aggregate budget alone. The branch will not fire until a second probe is added before the budget check or the per-probe timeout is raised. Worth keeping as defensive armor; just don't expect coverage. See R5. |
| M4 | yes | YES | Projection retains only `name`/`size`/`size_vram`/`context_length` then secondary-caps via `_truncate_observed_value`. Matches Ollama `/api/ps` schema (these four fields are top-level on each model entry; `context_length` is NOT under `details` for the versions this demo targets — see `readiness/ollama_ctx_len.py:66` which already reads `entry.get("context_length")` at top level). |
| S1 | yes | YES | Symlinks at any of the four canonical artifact basenames are now rejected outright. The test fixture symlink lives at `ok/source.pdf` (not in `CANONICAL_ARTIFACT_BASENAMES`) so it is unaffected. No `source.pdf` code path treats it as a canonical artifact for the eager-delete loop. |
| S2 | yes | YES | Regex `[\x00-\x08\x0a-\x1f\x7f]` correctly preserves tab (`\x09`) and strips DEL + ESC. Docstring is misleading (it lists DEL and ESC as preserved exceptions when they are actually stripped — see R10), but the *behavior* is correct. `prefix_for(run_id)` is uuid4 hex (trusted), so leaving it un-sanitized is safe. |

## New findings (introduced by the fixes OR uncovered while reviewing them)

| ID | Severity | Location | Summary | Recommendation |
|----|----------|----------|---------|----------------|
| R1 | **CRITICAL** | `readiness/schema_validation.py:64` | B1 fix references `first.code` / `first.message` — fields that do NOT exist on `Violation`. Real attributes are `violation_code` / `reason`. First real schema-fail → AttributeError. | Change to `f"{first.violation_code} at {first.field_path or '/'}: {first.reason}"`. Add a test using a real `validate_artifact` call against a known-bad artifact (retire `bypass_schema_validation` for one path). |
| R2 | HIGH | `readiness/schema_validation.py:58` | The bare `except Exception` wrapping `validate_artifact()` catches `InvalidArtifactNameError` (the validator's own taxonomy) silently and emits it as a flat string. An operator can't tell schema-fail from contract-mapping-misalignment from validator-bug. | Catch `InvalidArtifactNameError` separately and surface "contract mapping drift" as a distinct diagnostic. The first-violation branch should similarly handle the no-violations-no-pass case (line 65 fallback "validator returned not-passed with no violations" exists but is untested). |
| R3 | HIGH | `orchestrator.py:937` + `_RunState.preprocess_run_summary` | B3 fix removed a structurally-broken `getattr(frozen_options, "_preprocess_run_summary")` channel. No test covers the new channel. `_RunState.preprocess_run_summary` is only ever `None` in CI because no test composer returns a dict with a `run_summary` key. SC-004's gate-derived `quality_status` flip is therefore not regression-guarded by CI even after the fix. | Extend `_StubPipelineComposer.preprocess` to optionally return `{"run_summary": {"evidence_gate_documents": {...}}}` and add a test asserting `quality_status` flips from default-insufficient. Until then, B3 is "fixed but not verified". |
| R4 | HIGH | `orchestrator.py:705-714` (TimeoutError re-raise) + `:764-768` (cancel-on-entry) | A SIGALRM that fires between the `_run_phase()` return and the alarm-cancel in the outer `except TimeoutError` block raises `TimeoutError` into the cancel code, which swallows it. Correct. But a SIGALRM that fires AFTER `signal.alarm(0)` in the `except` body (because the alarm was already delivered and queued) re-raises into the unguarded body of the same `except` arm (lines 769-773), with no protection. The `finally` block's wrapper catches it, but `runtime_outcome` / `stalled_phase` are then partially set with no `_emit_report` guarantee if the `finally` itself swallows another late alarm. Empirically rare but the FR-019 always-emit invariant is the whole point of B4. | Move the entire `except TimeoutError as exc:` body inside a single `try: ... finally:` so any late `TimeoutError` from `runtime_outcome = ...` or `log.error(...)` is captured into the cleanup. Even better: cancel alarm at the very top of `run()`'s pipeline-phase try block via a context manager that masks SIGALRM during cleanup. |
| R5 | MEDIUM | `cpu_fallback.py:138-153` | K3 budget-exceeded branch is unreachable with the current single-probe layout: 1 probe × 2.0 s timeout = 2.0 s max wall, vs 5.0 s aggregate budget. The fix is correct but is effectively dead code today. Worse: the test suite has **zero coverage** for this branch (`grep -rn 'budget_exceeded\|aggregate.budget' tests/` returns nothing). | Either (a) shrink `_AGGREGATE_BUDGET_SECONDS` to 1.5 s so a single slow probe can trip it (and verify R-023.15 still permits) OR (b) add a deterministic test that monkey-patches `time.monotonic` to simulate budget exhaustion. |
| R6 | MEDIUM | `orchestrator.py:633` | `--check-only` success path does `report = dataclasses.replace(report, document_folder=None)` AFTER `_format_document_folder_for_report` already returns `None` for `check_only`. The replace is dead code. Cosmetic but the duplication makes M1/K5's invariant harder to reason about. | Drop the `dataclasses.replace` line; the formatter is now the single source of truth. |
| R7 | MEDIUM | `orchestrator.py:806-807` | `object.__setattr__(post_ctx, "runtime_timeout_observed", ...)` bypasses `ReadinessContext`'s `frozen=True` to inject runtime-timeout state. Same pattern as the pre-fix `getattr(frozen_options, ...)` anti-pattern B3 was supposed to retire. Adding `slots=True` to `ReadinessContext` (a plausible future hardening) would break this silently with no test catching it. | Either (a) add `runtime_timeout_observed` / `stalled_phase` as proper `Optional` fields on `ReadinessContext` and use `dataclasses.replace`, or (b) extend `_RunState` with these fields and have the post-pipeline checks read from `_RunState` directly. |
| R8 | MEDIUM | `orchestrator.py:473-480` | The non-localhost INFO emission re-imports `urlparse` and re-parses the URL after `_validate_ollama_base_url` already parsed it. Two parses, two import-from-stdlib. The validator could return the parsed result instead of just the string. | Make `_validate_ollama_base_url` return `(candidate, parsed)` or a small dataclass; have the caller read `parsed.hostname`. Eliminates duplicate parsing and the `from urllib.parse import urlparse as _urlparse` shadow import inside `run()`. |
| R9 | MEDIUM | `readiness/schema_validation.py:62-65` | The "validator returned not-passed with no violations" fallback message at line 65 is a defensive guard for an impossible state in the current validator (`ValidationOutcome.build` sets `passed = not errors and not sub_has_error` — if `passed=False`, `errors` is non-empty OR a sub-report failed). But sub-report failures populate `sub_reports`, not `violations`, so an actual sub-report failure WILL trip this fallback in the wild. Operator sees "no violations" and is misled. | Walk `outcome.sub_reports` recursively to surface the first leaf violation, or change the message to "schema validation failed via sub-report (see validator logs)". |
| R10 | LOW | `log.py:21-24` docstring | Docstring says regex strips "C0 controls (0x00-0x1F) **except** printable tab (0x09), the DEL byte (0x7F), and the ANSI CSI introducer (0x1B)." DEL (`\x7f`) and ESC (`\x1b`) are actually IN the regex (correctly stripped). Only tab is exempted. | Reword to "Strips C0 controls (0x00-0x1F) except printable tab (0x09); also strips DEL (0x7F)." |
| R11 | LOW | `orchestrator.py:749` | `signal.getsignal(signal.SIGALRM)` can return `None` ("if an unknown handler is in effect" per Python docs); the cleanup at line 784 skips the restore in that case (`if previous_handler is not None`). The previous _on_timeout handler then leaks into whatever pytest test runs next, which can fire a stale TimeoutError into an unrelated test if pytest reuses the SIGALRM slot. Pre-existing behavior, not introduced by 7f4aa00, but the B4 fix touches this code without addressing it. | Treat `None` the same as `SIG_DFL`: `signal.signal(SIGALRM, previous_handler or signal.SIG_DFL)`. |
| R12 | LOW | `cpu_fallback.py:73-75` | "Model no longer loaded" returns `fell_back` with `entry=None`, so `post_run_ollama_snapshot` becomes `None` in the report. `_cap_snapshot_dicts` then projects nothing — correct. But operators reading the report see `failure_kind=cpu-fallback-detected` and `post_run_ollama_snapshot=null`, which is semantically odd: the model is *gone*, not fallen back. | Add a distinct ProbeResult value or include a diagnostic note ("model unloaded between readiness and post-run probe"). |

## Detailed findings (high-signal only)

### R1 — CRITICAL: B1 fix repeats the round-1 class-of-bug (`first.code` / `first.message` don't exist)

`src/dartwing_ocr/gpu_demo/readiness/schema_validation.py:64`:

```python
if outcome.violations:
    first = outcome.violations[0]
    return f"{first.code} at {first.field_path or '/'}: {first.message}"
```

But `src/dartwing_ocr/validator/report.py:96-105` defines `Violation` with fields:

```python
class Violation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    severity: Severity
    target: str
    field_path: str = ""
    violation_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    reason: str = Field(min_length=1)
    expected: str | None = None
    source_file: str | None = None
```

`first.code` raises `AttributeError`. The B1 fix replaced one nonexistent-attribute bug (`validator.validate_path`) with another (`Violation.code`). It is undetected because every gpu_demo test stubs `_validate_artifact` directly (`conftest.py:287-301`, `test_schema_validation.py:50-56`) — the real validator path is never exercised.

This is a **direct repeat of the round-1 pattern**: code wrote against an imagined API surface that does not match the actual module. The first swarm flagged C1/B1 against `validator.validate_path`; this round-2 finding flags the same class against `Violation.code` / `Violation.message`.

**Fix:** change to `first.violation_code` and `first.reason`. **Add a real-validator integration test** that retires `bypass_schema_validation` for one schema-fail path so this class of drift is caught in CI.

### R4 — HIGH: B4 reduces the TimeoutError leak window but doesn't fully close it

The fix wraps `signal.alarm(0)` + handler restore in `try/except TimeoutError: pass` at three sites (orchestrator.py:764-768, :779-783, :784-788). What it doesn't protect:

1. **Lines 769-773** (inside the outer `except TimeoutError as exc:` body): the assignments `runtime_outcome = "timeout"`, `stalled_phase = ...`, `failure_kind = ...`, `diagnostic_msg = str(exc)`, and `log.error(...)` all run *after* the alarm-cancel at :764-768. If a queued SIGALRM was delivered between phase-return and the cancel call (extremely tight window, but Python doesn't atomically deliver signals), it raises `TimeoutError` into this body. The `finally` block at :774-788 catches its own late alarms but cannot rescue a `TimeoutError` raised from line 770.
2. **`KeyboardInterrupt` race:** if an operator hits Ctrl-C during the cleanup window, KeyboardInterrupt is unhandled. FR-019 requires always-emit; this is a real (if rare) violation path.

**Fix:** wrap the entire `except TimeoutError as exc:` body in `try: ... finally:`, or use a context manager that masks SIGALRM via `signal.pthread_sigmask(SIG_BLOCK, [SIGALRM])` during cleanup.

### R7 — MEDIUM: B3 fix retires one frozen-dataclass-mutation hack, leaves another untouched

The B3 fix (`_RunState`) explicitly retired the `getattr(frozen_options, "_preprocess_run_summary", None)` channel as "structurally broken". But the same anti-pattern still lives at orchestrator.py:806-807 where `object.__setattr__` is used to attach `runtime_timeout_observed` to a frozen `ReadinessContext`. This is fragile in the same way: any future `slots=True` hardening of `ReadinessContext` (a likely OpenSpec audit suggestion) would silently break it, with no test catching the regression.

**Fix:** add `runtime_timeout_observed: bool = False` and `stalled_phase: Optional[StalledPhase] = None` as proper fields on `ReadinessContext`, then use `dataclasses.replace(base_context, runtime_timeout_observed=...)` — symmetric with how `cached_api_ps_body` is already threaded. Removes the `object.__setattr__` hack.

## Pattern analysis — what kind of bug is most likely to still remain?

Round-1 bugs shared one root: **silent assumption breakage** — code that asserted an API surface (function exists, attribute settable, no race, no prior state) without verification. The 7f4aa00 fix retired most of them but the underlying habit shows up twice more:

1. **R1** is the round-1 pattern repeated against a different module (`Violation`).
2. **R7** is the round-1 pattern preserved at a different site (`object.__setattr__` on a frozen `ReadinessContext`).

Other places where this habit is *likely* to bite next, even though no concrete bug was found this round:

- `_extract_pre_run_snapshot` (orchestrator.py:184-192) trusts `cached_api_ps_body` is a `dict` with a `models: list`. The check is correct, but only because Ollama happens to use those names today. If Ollama 0.5+ renames `models` → `model_instances`, the snapshot silently goes `None` and the M3 diff stops working, with no test catching it.
- `_DefaultPipelineComposer.preprocess` raises with hard-coded phase strings (`"preprocess"`); the StalledPhase literal type is checked by static analysis but not by any runtime test. A typo here ("preproces") would only surface on a real workstation run.
- `dataclasses.asdict(report.cpu_fallback_detection)` (serialization.py:108) assumes the dict-result is structurally what `_cap_snapshot_dicts` expects (top-level keys `pre_run_ollama_snapshot` / `post_run_ollama_snapshot`). If `CPUFallbackDetection` ever gains a nested-dict field, the cap could miss it.

The systemic fix is **at least one CI test per readiness check that exercises the real validator/probe against a known-bad fixture**. Every test currently uses a stub at the seam where the bug would land.

## Sign-off

**NEEDS-ATTENTION.** R1 is a PR-blocker — it would surface as AttributeError on the first workstation run that actually fails schema validation, with the same opaque-failure mode the round-1 swarm was trying to retire. R3/R4 are HIGH and worth one more commit before opening the PR. R5/R6/R7/R8/R9 can ride a small follow-up commit or be batched with the next round of polish.

The good news: B2, B5, M3, M4, S1, S2 are genuinely closed. The B1 fix delivered the right architectural shape (basename mapping, real validator call, contract-set version awareness) but mis-named two attributes on the violation model.

**Recommended ordering:**

1. Fix R1 (rename `code`→`violation_code`, `message`→`reason`) and add a real-validator integration test that retires `bypass_schema_validation` for one path.
2. Fix R3 (extend stub composer to publish `run_summary`; add `quality_status` flip assertion).
3. Fix R4 (wrap `except TimeoutError` body in `try/finally`).
4. Cosmetic batch: R6, R8, R10, R11.
5. Architectural batch (can wait for the next feature cycle): R7, R9, R12.
