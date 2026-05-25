# Round-2 swarm review triage — feature 023

**Date:** 2026-05-25
**Branch:** `023-gpu-mvp-demo-hardening` @ `7f4aa00`
**Swarm:** 7 specialist agents (regression-correctness, test-nontautology, contract-realignment, edge-case-fuzzing, security-deepdive, integration-readiness, observability-ux).

## Verdict

**DO NOT OPEN PR.** Round-1 fixed the round-1 bugs but introduced **one new CRITICAL** of the same class-of-bug (silent assumption breakage). The round-1 regression test that was supposed to guard the headline fix is **tautological**. Two FR-019 always-emit violations surfaced. Net assessment: the patch quality is high but the test-coverage gap that allowed round-1 bugs to land in the first place was NOT closed by the new tests, so we got bit again.

## Per-agent headline

| Agent | Findings | C | H | M | L | Status |
|---|---|---|---|---|---|---|
| regression-correctness | 12 | **1** | 3 | 5 | 3 | NEEDS-ATTENTION |
| test-nontautology | 5 | 0 | 1 | 0 | 0 | NEEDS-ATTENTION |
| contract-realignment | 6 | 0 | 0 | 0 | 6 | PASS |
| edge-case-fuzzing | 9 | 0 | 2 | 5 | 2 | NEEDS-ATTENTION |
| security-deepdive | 12 | 0 | 0 | 1 | 11 | NEEDS-ATTENTION |
| integration-readiness | 17 | 1 | 2 | … | … | NOT-READY-TO-OPEN-PR |
| observability-ux | 20 | 0 | 0 | … | … | NEEDS-UX-PASS |
| **Total** | **81** | **2** | **8** | **~18** | **~22** | |

## PR-blockers (must fix before opening)

| ID | Severity | Source | Location | One-liner | Triangulated by |
|---|---|---|---|---|---|
| **R2-1** | CRITICAL | regression R1 + integration #1 | `readiness/schema_validation.py:64` | B1 fix referenced `first.code` / `first.message` — fields that don't exist on `Violation`. Real fields are `violation_code` / `reason`. First real schema-fail will AttributeError. Test suite misses it because `bypass_schema_validation` patches `_validate_artifact` to a no-op. | 2 independent agents |
| **R2-2** | HIGH | test-nontautology B2 verdict + regression R3 | `tests/integration/gpu_demo/test_schema_validation.py::test_phase_failure_does_not_mask_as_schema_failure` + `_StubPipelineComposer` | The B2 regression test uses `bypass_schema_validation` → check 7 always returns `"pass"` → the buggy `if r.status == "fail"` code path is never exercised. **Reverting my B2 guard does NOT fail the test.** Same root cause for R2-1: stub composer + bypass fixture mask production behavior. | 2 agents (different lenses) |
| **R2-3** | HIGH | regression R4 | `orchestrator.py:705-714, :764-768` | B4 narrowed but did not fully close the SIGALRM leak. A late TimeoutError fired inside the `except` body (between alarm-cancel and `log.error`) re-enters unguarded code. FR-019 always-emit not fully guaranteed. | 1 agent |
| **R2-4** | HIGH | edge-case E2 | `serialization.py:_truncate_observed_value` | A `CheckDiagnostic.observed` containing a circular reference crashes `json.dumps` inside `_emit_report`. **No JSON line is emitted → FR-019 violation.** | 1 agent |
| **R2-5** | HIGH | edge-case E5 | `orchestrator._build_options_from_args:158` | Non-numeric `OLLAMA_CONTEXT_LENGTH` (e.g. `"2k"`) raises `ValueError` BEFORE any JSON line is emitted → FR-019 violation. | 1 agent |
| **R2-6** | HIGH | regression R3 | `_RunState.preprocess_run_summary` | B3 fix is structurally correct but has **zero CI coverage** — no stub composer ever returns a dict with a `run_summary` key. SC-004's gate-derived `quality_status` flip remains unverified. | 1 agent |
| **R2-7** | HIGH | integration #2 | `data-model.md` §6 sample reports | Three sample reports in `data-model.md` predate the new `pre_run_ollama_snapshot` / `quality_status_source` fields. Docs are stale. | 1 agent |

## Important MEDIUMs

| ID | Severity | Source | One-liner |
|---|---|---|---|
| **R2-8** | MEDIUM | security D1 | `_validate_ollama_base_url` accepts `http://user:pass@host:11434`; credentials echo into stderr + JSON. Reject non-empty userinfo. |
| **R2-9** | MEDIUM | edge-case E4 | `_validate_ollama_base_url` returns trimmed value but caller discards it; `OLLAMA_BASE_URL=" ..."` carries trailing whitespace downstream. |
| **R2-10** | MEDIUM | regression R5 | K3 budget-exceeded branch is dead code today (1 probe × 2s < 5s aggregate). Either tighten the budget or simulate exhaustion in tests. |
| **R2-11** | MEDIUM | regression R7 | `ReadinessContext` uses the same `object.__setattr__` frozen-bypass hack B3 was supposed to retire. Add proper fields. |
| **R2-12** | MEDIUM | regression R9 | Sub-report failures populate `outcome.sub_reports` not `outcome.violations`; the "no violations" fallback in `_validate_artifact` would mislead operators. |
| **R2-13** | MEDIUM | security D4/D12 | `_cap_snapshot_dicts` silently degrades `dict → str` on overflow — violates `dict | None` type contract; cascades to downstream JSON consumers. |
| **R2-14** | MEDIUM | observability | `FailureKind` is kebab-case while every other closed enum is snake_case → `jq` inconsistency. |
| **R2-15** | MEDIUM | observability | Exit 5 (artifact-schema-validation-failed) emits **no stderr ERROR line of record** — operator must read JSON to learn what happened. |
| **R2-16** | MEDIUM | observability | Phase-failure cascade keeps running CPU-fallback probes after a `failed_at_extraction`, muddying the narrative with an unrelated WARN/INFO. Short-circuit on pipeline-runtime-error. |
| **R2-17** | MEDIUM | integration #3 | Runbook says "expected ~5× the warm wall-clock (~10 min on cold cache)" — disagrees with the 600s SIGALRM. Cold-cache run hits timeout before operator can tell hang from cold. |

## Polish / cosmetic

23 LOW findings aggregated across contract (6 doc-only K-touch-ups), security (11 LOWs around credentials, C1 controls, hard links, env allowlist), regression (3 LOWs around log docstring, signal restore None case, model-unloaded probe naming), and edge-case (UTF-8 lead-byte at 2 KiB, voter[1:] non-dict drop). Hold for a single polish pass once blockers are closed.

## Cross-finding triangulation (high-confidence signals)

These findings were independently flagged by ≥2 agents:

- **R2-1 (Violation field names)** — regression R1 + integration #1. Same line, same fix, same root cause as round-1 B1. **2 agents reading different artifacts converged.**
- **R2-2 (tautological B2 test)** — test-nontautology B2 verdict + regression R3 implication. Both trace to the `bypass_schema_validation` fixture + the too-trivial stub composer (the "by design" gap deferred from round-1's T7).
- **OLLAMA_BASE_URL hardening** — security D1 (credentials) + edge-case E4 (trim) + observability (non-localhost INFO wording) — three agents touched the URL validator. The validator earned a follow-up pass.

## The pattern

Round-1 bugs were "silent assumption breakage": code that called methods/fields/properties that did not exist on the API it imported from, or accessed attributes that could not be set due to frozen-dataclass constraints. **Round-1 fixes broke at exactly two new sites in exactly the same way**:

- R2-1: same as round-1 B1 (validator API field names assumed)
- R2-11: same as round-1 H1 (frozen-dataclass `__setattr__` hack still used elsewhere)

**Root cause analysis:** the test suite cannot catch this class of bug because every test stubs the production code path at exactly the boundary where the assumption would surface. The fix that round-1 deferred (T7: hand-author one realistic stub artifact + retire `bypass_schema_validation` for at least one happy-path test) is the SAME fix that would have caught R2-1 before commit.

## Recommended fix order

1. **R2-1 (CRITICAL)** + retire `bypass_schema_validation` for one happy-path test using a realistic stub artifact — closes the test-coverage root cause that allowed R2-1 to land. ~1 hour.
2. **R2-2** — drop `bypass_schema_validation` from the B2 regression test (or use a selective `_validate_artifact` stub that fails for one specific path). ~5 min once R2-1's realistic artifact is in.
3. **R2-3, R2-4, R2-5** — FR-019 always-emit safety net: wrap `_emit_report` in a defensive try, wrap `_build_options_from_args` env parsing in try/except → exit 2, complete the B4 SIGALRM mask. ~45 min total.
4. **R2-6** — extend `_StubPipelineComposer.preprocess` to optionally return a `run_summary` dict and add a test asserting `quality_status` flips. ~30 min.
5. **R2-7** — refresh three sample reports in `data-model.md`. ~15 min.
6. **R2-8 through R2-17** — apply the mediums as a single second commit; most are 1-line changes. ~90 min total.
7. **Polish** — 23 LOWs in a final commit. Skip unless on a long session.

Total estimated fix budget: **~3.5 hours** to PR-ready.

## Sign-off

**HOLD PR.** R2-1 will fail on the first real workstation smoke. R2-2 means the B2 fix has no actual regression guard. R2-4/R2-5 break FR-019 (the entire point of the always-emit invariant). The MVP is structurally sound but the test surface allowed round-1 fixes to introduce a same-class regression — the next commit needs to close that root-cause gap.
