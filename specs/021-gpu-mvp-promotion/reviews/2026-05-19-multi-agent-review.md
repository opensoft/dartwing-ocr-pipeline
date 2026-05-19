# Multi-Agent Review: Feature 021 GPU MVP Promotion

**Date**: 2026-05-19 · **Branch**: `021-gpu-mvp-promotion` · **HEAD**: `3201d21`
**Reviewers**: 4 parallel `general-purpose` Agent subagents (orchestrating-swarms Pattern 1)
**Scope**: implementor-doable landing across 4 commits (`1966e27`, `6829d30`, `9591df2`, `3201d21`)

## TL;DR

| Dimension | Verdict | Must-fix pre-merge | Follow-ups |
|---|---|---:|---:|
| **Code quality** | NEEDS-WORK | 1 HIGH + 2 MEDIUM | 5 LOW |
| **Spec/contract compliance** | COMPLIANT | 0 | 1 subtle FR-020 note + 3 cosmetic INFO |
| **Security/PII** | CLEAN | 0 | 0 |
| **Pre-existing-failure triage** | INDEPENDENT-OF-021 | 0 (call out in PR body) | ~10 lines of test-only patches owned by features 014/019/020 |

**Recommended action**: fix 1 HIGH + 2 MEDIUM findings (~30 minutes), then open the PR. The HIGH is a real bug (operator-typo → infinite loop). The 2 MEDIUMs are correctness-preserving cleanups.

---

## Agent 1 — Code-Quality Review

**Verdict**: NEEDS-WORK

### 1. HIGH BUG — Helper hangs on trailing flag missing value

`scripts/check-ollama-gpu-readiness.sh:36, 44`. `--voter-config` (or `--base-url`) as the **last** arg with no value drives an infinite loop. `shift 2 || true` masks `shift`'s failure when only 1 positional remains; `$#` stays at 1 forever. Confirmed with `bash -x`. The contract test doesn't cover this case.

**Fix**: inside each two-token branch, add `[ "$#" -ge 2 ] || { echo "FAIL: ... requires a value" >&2; exit 4; }` before assignment, and use plain `shift 2`.

### 2. MEDIUM — Sub-conftest skip-gate doesn't cover `tests/unit/`

`tests/unit/preprocessing/test_warmup_skip_fallback_exception.py:33-39` imports from `tests.pipeline_tests.gpu_helpers` at module top level. Currently safe (import is side-effect-free), but violates the documented "imported by `pytest.mark.gpu`-marked tests only" assumption in `gpu_helpers.py:9-12`. A future import-time side-effect would break CPU collection.

**Fix**: keep `gpu_helpers` strictly side-effect-free (add a module-level note + a `pytest --collect-only` smoke check in CI), OR move the GPU subprocess test out of `tests/unit/`.

### 3. MEDIUM — Promotion-decision regex misses plain-form variant

`tests/contract_tests/test_promotion_decision_sync.py:39-47`. Docstring claims regex matches both `**Decision**: ...` (bold) AND `Decision: ...` (plain), but `_DECISION_RE` only encodes bold form. Plain form silently doesn't match → `_extract_decision` raises AssertionError on a future plain-form edit.

**Fix**: change pattern to `r"(?:\*\*Decision\*\*|Decision)\s*:\s*([^\n_()]+?)(?:\s*[_(]|\s*$)"`, OR tighten the docstring to "bold form only".

### 4–8. LOW findings (safe as follow-ups)

- **#4** Helper emits `http://localhost:11434//api/ps` on trailing-slash `--base-url`. Fix: `base_url="${base_url%/}"`.
- **#5** `test_evidence_gate_all_suppressed_lazy_construction.py:200-206` uses `pytest.fail` (not `pytest.warns`/`pytest.xfail`) for missing `engine_init`, but the comment says "may amortize". Hard fail contradicts "soft assertion".
- **#6** 4 fixtures omit real Ollama `/api/ps` fields (`processor`, `context_length`). Harmless today; risks future placement-cross-check gap.
- **#7** Server-fixture teardown can race on slow CI: `thread.join(timeout=2)` may return with daemon still alive.
- **#8** `_VALID_DECISIONS` hand-coded; if FR-026 grows a third literal, unhelpful "not in allowed set" error rather than spec-drift flag.

### Strengths noted

- Helper: `set -u`, defensive `trap` cleanup, integer coercion (`size%.*`), `command -v` checks, mikefarah/kislyuk `yq` tolerance.
- Contract test: stdlib-only mock server, ephemeral port, handler-silencing.
- `gpu_helpers.py`: correctly named to escape pytest collection, clear failure messages, surfaces corpus-drift preconditions.
- Promotion-sync test: sound placeholder-handling (both placeholder = agree on unrecorded state).

---

## Agent 2 — Spec/Contract Compliance Review

**Verdict**: COMPLIANT (with operator-gated remainder as designed)

### Per-SC table

| SC | Status |
|---|---|
| SC-001 | partial / operator-gated (T008 ✓; T014/T037 pending) |
| SC-002 | ✓ verified — 7 FAIL paths in helper contract test |
| SC-003 | ⏸ operator-gated (inherited preflight stderr) |
| SC-004 | ✓ verified — all 5 placeholders converted; `@pytest.mark.skip` removed |
| SC-005 | partial — Appendix A skeleton ✓; T015–T018 operator-transcribe |
| SC-006 | ⏸ operator-gated (Findings vocabulary pinned) |
| SC-007 | partial — Appendix B skeleton ✓; T022 operator-transcribe |
| SC-008 | ✓ verified — runbook present; grep returns 0 matches |
| SC-009 | partial — sync infrastructure ✓; T028 team-gated |
| SC-010 | ✓ verified — only pre-existing failures remain |
| SC-011 | partial — T032 ✓; T014 operator-gated |

### Per-FR summary

- FR-001–FR-005 readiness: 5/5 ✓
- FR-006–FR-010 deferred verification: 5/5 ✓ (test bodies real + GPU-gated)
- FR-011–FR-018 benchmark: skeleton ✓; operator-gated remainder
- FR-019–FR-022 quality gate: T019 + T021 ✓; operator-gated
- FR-023–FR-025 docs: appendices + runbook ✓
- FR-026–FR-029 promotion: T025–T027 ✓; T028 team-gated
- FR-030–FR-033 scope: ✓ by negation (T031/T032)

### R-021.13 reconciliation — subtle FR-020 concern

The substitution to `overall_metrics.vendor_identity_pass_rate` (instead of the spec's "sum of per-doc vendor_identity_score") is necessary because feature-007 emits no per-doc numeric score. But **on a fixed N=5 subset, `pass_rate = pass_count / 5`** — the two FR-019 metrics are mathematically equivalent and collapse to a single test under FR-020 conjunction.

The spec intended two independent signals; the substitution gives one signal twice. This is acceptable for landing (it's the only schema-emitted surface; the equivalence is documented in the test docstring) but **weakens the FR-020 conjunction protection** on this exact subset size. A magnitude-preserving alternative — e.g., sum of per-doc `comparison_summary.matched_field_count` — would restore the independent-signal property.

**Severity**: noted-but-not-blocking. Documented inline in `test_quality_gate_two_metric_evidence_gate.py` docstring; recorded in `spec.md` Notes "Deviations recorded" #2.

### Drift findings (all LOW/INFO)

- Appendix B per-doc score table header reads `legacy pass rate / candidate pass rate`; contract sample table in `appendix-recording.md` shows `legacy score / candidate score`. Cosmetic.
- `contracts/runbook.md §5` header has a triple-backtick artifact in source; not in the implemented runbook. No functional drift.
- T037 straddles Polish and US3 phase classifications in `tasks.md` (operator-gated; intentional but ambiguous).
- Paddle-preflight blocker keys in runbook (`paddle_cpu_only`, etc.) are not pinned in FR-010 closed-list category vocabulary. Operator-facing remediation table; informational only.

---

## Agent 3 — Security/PII Review

**Verdict**: CLEAN

Zero findings across 8 audit dimensions. Summary:

1. **FR-032 prohibitions** — all 8 landed files introduce zero new persisted artifacts. Helper writes only to `mktemp` with `trap` cleanup. No new `run_summary` field. No remote-cloud / Jetson / surveillance code.
2. **Credential surface** — zero hits on `Authorization|api[_-]?key|token|secret|password|bearer|credential` across landed code/docs. Helper sets no auth header. Only env var referenced is the pre-existing `DARTWING_EVIDENCE_GATE_SKIP_FALLBACK=0` (feature flag, not credential).
3. **Scratch-root PII** — `/tmp/021-bench/` correctly outside committed corpus. Both `rm -rf` invocations scoped to `/tmp/021-bench/`. Helper writes nothing to disk. Helper PASS JSON + stderr templates contain no credentials/PII/vendor content.
4. **Runbook PII discipline** — body uses only synthetic doc IDs (`inv_001_easy`, `inv_002_easy`) and placeholder tax ID `12-3456789`. Zero real vendor names / addresses / suffix-matching strings.
5. **Test fixtures** — public model identifiers only (`qwen2.5vl:7b`, `gemma2:9b`); synthetic byte counts; placeholder digests.
6. **`configs/voter/ollama-gpu.yaml`** — 19 lines; public model identifier only; no paths/hostnames/usernames.
7. **Threat-model boundary** — only network endpoints referenced are `http://localhost:11434` (helper) and `http://127.0.0.1:0/1` (test fixtures). Zero references to `OLLAMA_HOST`, `ollama.com`, `remote`, `cloud`, `jetson`.
8. **Readiness logs** — `readiness-paddle.log` and `readiness-ollama.log` capture only blocker descriptions (named-cause categories per FR-010); no credentials or PII content.

---

## Agent 4 — Pre-existing Failure Triage

**Verdict**: INDEPENDENT-OF-021

### Per-file diagnosis

**`tests/pipeline_tests/test_frozen_argument_set.py`** (1 failure):
- Root cause: CLI exposes `--evidence-gate-skip-fallback` (feature 020 US4, commit `a601a92`) and `--preprocess-strategy` (feature 019). Test's expected-union doesn't include `_AMENDMENT_019` or `_AMENDMENT_020` sets.
- Owner: features 019 + 020. Test authored under feature 011 (last touched `7f727e3`).
- Fix scope: ~5-line patch adding the two amendment sets.

**`tests/unit/preprocessing/test_version.py`** (3 failures):
- Root cause: feature 014 R-014.2 (commit `3128ccd`) added mandatory trailing `.cpu`/`.gpu<N>` lane segment to `build_pipeline_version()` output. Test's `VERSION_RE` and `.endswith(".dpi400")` assertions encode the pre-014 shape.
- Owner: feature 014. Test authored under feature 003 (last touched `9b432c0`).
- Fix scope: ~4-line patch extending `VERSION_RE` and updating `.endswith` calls.

### Reproduction at parent commit `9ab0117`

Detached HEAD at branch base, no working-tree changes → identical 4 failures. Confirmed pre-existing.

### Recommendation

Both are pre-existing maintenance debt left when features 014/019/020 amended CLI/version contracts without updating their consumers. ~10 lines of test-only edits owned by features 014/019/020 — **not feature 021**. File as a follow-up cleanup PR; call out as known pre-existing in the feature-021 PR body.

---

## Synthesis — Recommended Pre-Merge Actions

### Must-fix (before opening PR)

| # | Finding | File | Effort |
|---|---|---|---:|
| **HIGH-1** | Helper infinite-loop on trailing-flag missing value | `scripts/check-ollama-gpu-readiness.sh` | ~5 min — add `$# >= 2` check before each two-token shift |
| **MED-1** | `gpu_helpers` import-time hygiene from `tests/unit/` | `tests/pipeline_tests/gpu_helpers.py` + `tests/unit/preprocessing/test_warmup_skip_fallback_exception.py` | ~5 min — add module-level invariant note; verify import is side-effect-free; consider moving the test |
| **MED-2** | Promotion-sync regex docstring claims plain-form match it doesn't deliver | `tests/contract_tests/test_promotion_decision_sync.py:39-47` | ~5 min — extend regex to accept both forms (per docstring) or tighten docstring to bold-only |

**Total**: ~15–20 minutes of follow-up edits + a quick test re-run.

### Optional follow-ups (any time)

- LOW-4 through LOW-8 (code-quality follow-ups)
- Spec drift INFO items (cosmetic, no merge gate)
- The two pre-existing test failures (sidecar PR owned by features 014/019/020)

### Open the PR with

- The 4 implement commits (`1966e27` / `6829d30` / `9591df2` / `3201d21`)
- A PR-body callout naming the 2 pre-existing test failures as inherited-from-branch-base (cite Agent 4's diagnosis)
- A reference to this review file (`specs/021-gpu-mvp-promotion/reviews/2026-05-19-multi-agent-review.md`)
- Optional: a one-line acknowledgement of the R-021.13 conjunction-collapse note (Agent 2) — documented inline in T019's docstring already

---

## Agent metadata

| Agent | Subject | Tool uses | Duration | ID |
|---|---|---:|---:|---|
| 1 | Code quality | 32 | 5m 33s | `af4f3bdd55c8fda78` |
| 2 | Spec/contract compliance | 45 | 3m 11s | `a255ff33de34f2e4d` |
| 3 | Security/PII | 20 | 1m 25s | `ae913a6d0f05e9c8c` |
| 4 | Pre-existing failure triage | 29 | 1m 47s | `affce21950b79c675` |
| **Total** | — | **126** | **12m 16s** wall-clock (parallel) | — |

All 4 agents are still addressable via `SendMessage` for follow-up questions.
