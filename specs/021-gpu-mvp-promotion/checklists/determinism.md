# Determinism Quality Checklist: GPU MVP Promotion

**Purpose**: Validate that every deterministic surface in this feature (readiness gate, jitter formula, verdict logic, helper exit codes, promotion permission, error messages, recording rules) is written so that identical inputs produce identical outputs. Constitution §III treats determinism violations as design issues, not style issues; this checklist tests whether the *spec writes determinism explicitly* rather than implying it.
**Created**: 2026-05-18
**Feature**: [spec.md](../spec.md)

This checklist tests the *requirements writing* of determinism, not the runtime behavior. Items target whether deterministic surfaces are stated unambiguously, are formula-pinned where appropriate, and resist accidental drift into model-derived or wall-clock-derived dependencies.

## Readiness Gate Determinism (FR-001 / FR-002 / Composite Verdict)

- [X] CHK001 Is the FR-001 Paddle preflight verdict required to be a deterministic function of (interpreter, ROCm runtime state, Paddle wheel state) — i.e., no random component, no wall-clock dependency? [Clarity, Spec §FR-001]
- [X] CHK002 Is the FR-002 Ollama placement check required to be a deterministic function of `/api/ps` response + voter-config `model_name`, with no retry/backoff that introduces non-determinism? [Clarity, Spec §FR-002, §R-021.6]
- [X] CHK003 Is the composite verdict (PASS / FAIL / BLOCKED) required to be a deterministic conjunction `paddle_pass AND ollama_pass`, with no allowance for "best effort" or "majority" semantics? [Clarity, Spec §Key Entities GPU Readiness Verdict]
- [X] CHK004 Is the readiness-helper invocation contract free of retry loops or wait timeouts that would make repeated invocations under identical state produce different verdicts? [Clarity, Spec §R-021.9, contracts/ollama-readiness-helper.md]
- [X] CHK005 Is the helper's exit-code → status mapping required to be a total function (every possible state maps to exactly one of `pass / fail_partial_gpu / fail_not_loaded / fail_unreachable / fail_config`)? [Completeness, Spec §R-021.9]

## Jitter Formula Determinism (FR-015 / Jitter Band Entity)

- [X] CHK006 Is the FR-015 formula `threshold = max(|legacy_run2 − legacy_run1|, |candidate_run2 − candidate_run1|)` written in a form that is a pure function of four measurements — no random sampling, no smoothing, no aggregate across documents? [Clarity, Spec §FR-015]
- [X] CHK007 Is the material-change rule `|candidate_run2 − legacy_run2| > threshold` written with strict greater-than (deterministic boundary), not `≥` (which would create an ambiguous-at-equality case)? [Clarity, Spec §FR-015]
- [X] CHK008 Is the threshold=0 edge case (R-021.3) handled deterministically — any non-zero `|Δ| > 0` is material; no fallback band, no rounding rescue? [Clarity, Spec §R-021.3]
- [X] CHK009 Is the formula's input granularity explicit (per-document × per-phase-key × per-(lane,run) tuple), so a third party cannot accidentally aggregate to a different grain? [Clarity, Consistency, Spec §FR-015]
- [X] CHK010 Is the timing unit + precision (seconds, 3 decimals per R-021.2) pinned, so the formula's numeric output is reproducible byte-for-byte from the same inputs? [Clarity, Spec §R-021.2]
- [X] CHK011 Is the direction-symmetric reading of "material change" (R-021.4) stated explicitly, so an implementor cannot interpret material decrease ≠ material increase? [Clarity, Spec §R-021.4]

## Quality-Gate Verdict Determinism (FR-019 / FR-020)

- [X] CHK012 Is the FR-019 aggregate score formula pinned as `sum` (R-021.13), not "score" — so the formula produces one numeric output from the per-document inputs? [Clarity, Spec §R-021.13]
- [X] CHK013 Is the FR-019 per-document pass count pinned as `count` (R-021.13) over the per-document pass flag, with no allowance for weighted counts or partial credit? [Clarity, Spec §R-021.13]
- [X] CHK014 Is the FR-020 PASS rule a strict boolean conjunction `aggregate_nonregress AND pass_count_nonregress`, with no allowance for either-or, weighted, or tie-breaker semantics? [Clarity, Spec §FR-020]
- [X] CHK015 Is the verdict's "non-regression" rule defined as `candidate ≥ legacy` (≥, not strict >) so a tied candidate still produces PASS deterministically? [Clarity, Spec §FR-020]
- [X] CHK016 Is the FAIL / BLOCKED disambiguation rule deterministic — i.e., is "gate cannot run because of named cause" (BLOCKED) clearly distinguished from "gate ran and detected regression" (FAIL), so the same scenario always produces the same verdict literal? [Clarity, Spec §FR-021, §FR-022]

## Promotion Permission Determinism (FR-027 / FR-029)

- [X] CHK017 Is the FR-027 "FAIL/BLOCKED → stay opt-in" rule a deterministic implication — i.e., no escape clause that lets a FAIL verdict result in promote-to-default under any circumstance? [Clarity, Spec §FR-027]
- [X] CHK018 Is the FR-029 "PASS PERMITS but never AUTOMATES" rule deterministic — i.e., the same PASS verdict always permits both stay-opt-in and promote-to-default options, and the system never auto-flips the default without an explicit decision record? [Clarity, Spec §FR-029]
- [X] CHK019 Is the boundary "PASS does not REQUIRE promotion" symmetric — i.e., promotion-to-default is never the default action of a PASS verdict; it is always opt-in by an explicit recorded decision? [Clarity, Consistency, Spec §FR-029, §US4 Scenario 3]
- [X] CHK020 Are the promotion-decision recording-medium requirements (Appendix B + runbook) free of asynchrony — i.e., the two media must be updated atomically (or verified by the FR-026 synchronization contract test) so a reader cannot encounter a half-updated state? [Clarity, Spec §R-021.11, contracts/appendix-recording.md]

## Helper Output Determinism (R-021.9 / R-021.10)

- [X] CHK021 Is the helper's stdout output on PASS pinned to a single JSON line whose key order, field set, and timestamp format are deterministic given the same inputs (the only non-deterministic field being `timestamp_utc`, which is forensic-only)? [Clarity, Spec §R-021.9, contracts/ollama-readiness-helper.md]
- [X] CHK022 Is the helper's stderr message format pinned per exit code (one template per code), so a wrapper script can grep for the named cause reliably? [Clarity, Spec §R-021.9]
- [X] CHK023 Is the helper required to NEVER produce stdout output on a FAIL exit, and NEVER produce stderr output on a PASS exit, so stream-separated parsing is unambiguous? [Clarity, Consistency, Spec §R-021.10]
- [X] CHK024 Is the timestamp_utc field's format pinned (ISO-8601, UTC, second precision), so the only non-deterministic part of PASS output is fully constrained? [Clarity, Gap]

## Recording Determinism (Appendix A / B / Runbook)

- [X] CHK025 Is the Appendix A subsection-ordering convention deterministic — six subsections in fixed order (env fingerprint → doc subset → four-run timeline → per-doc phase tables → run_summary observability table → findings)? [Clarity, contracts/appendix-recording.md]
- [X] CHK026 Is the Appendix A per-document phase-key table's column order pinned, so two reviewers transcribing the same raw `run_summary` numbers produce identical tables? [Clarity, contracts/appendix-recording.md]
- [X] CHK027 Is the Appendix B verdict block's required-field order pinned (verdict literal → per-doc table → aggregate → pass count → regression metric → blocked cause), so the order encodes meaning? [Clarity, contracts/appendix-recording.md]
- [X] CHK028 Is the Promotion Decision Record's field set pinned (decision, gating_verdict_ref, decided_at, decided_by, rationale, promotion_artifacts) — closed schema, no implicit optional fields? [Clarity, Spec §Key Entities, data-model.md §5]
- [X] CHK029 Is the runbook's command order pinned (Step 1 readiness BEFORE Step 2 demo), so a runbook with reordered steps would fail the FR-025(a) "starts with the readiness checks" requirement? [Clarity, Consistency, Spec §FR-025(a), contracts/runbook.md]

## Anti-Determinism Surfaces (drift-prevention)

- [X] CHK030 Is the spec free of language permitting models to participate in any decision (readiness, jitter, verdict, promotion) — i.e., does no requirement say "the model decides" or "with the model's confidence"? [Consistency, Spec-wide, Constitution §III]
- [X] CHK031 Is the spec free of wall-clock-dependent decisions (e.g., "if the run takes > T seconds, fail") — i.e., is every threshold derived from measured per-pair data (FR-015), not from absolute wall-clock fences? [Consistency, Spec-wide]
- [X] CHK032 Is the spec free of `should` / `may` (soft) language in normative positions — i.e., is every deterministic rule written with `MUST` or `MUST NOT`, never `should` / `may`? [Clarity, Spec-wide]
- [X] CHK033 Are the deterministic surfaces (readiness gate, jitter, verdict, promotion permission) each cross-linked to Constitution §III "Deterministic Control Over Model Output" — at least implicitly, by avoiding model-output dependencies? [Traceability, Constitution §III]

## Coverage Across Phases

- [X] CHK034 Is the determinism discipline applied uniformly across the spec (the gate, the formula, the verdict, the promotion decision) — no carve-out for "best effort" anywhere? [Consistency, Spec-wide]
- [X] CHK035 Is the determinism discipline applied to the Phase 1 contracts as well as the spec (the helper's exit codes, the marker contract's CI gating, the appendix-recording table shapes, the runbook section order)? [Consistency, contracts/]
- [X] CHK036 Is the determinism discipline reflected in the test surface (the converted GPU tests assert against deterministic shapes: counters, presence/absence of phase keys, score values — not against wall-clock proxies)? [Consistency, contracts/gpu-test-marker.md]

## Gaps to Flag

- [X] CHK037 Is the case "two consecutive `/api/ps` requests during the same Ollama lifetime returning different placement data" addressed — does the spec want a single-shot probe (R-021.9 says yes, no retry) or rule out the case explicitly? [Coverage, Spec §R-021.9]
- [X] CHK038 Is the case "the same benchmark run executed twice on the same workstation producing different `phase_timings.*` values due to MIOpen cache cold-vs-warm" addressed — the four-run discipline mitigates it, but is the deterministic *eventual* convergence stated? [Coverage, Spec §FR-012, Edge Cases]
- [X] CHK039 Is the floating-point comparison surface for the jitter formula resilient to FP rounding (e.g., if `legacy_run2 = 0.842` but actual stored value is `0.8420000000000001`)? Currently the spec pins 3 decimals for recording but not for computation — could two reviewers using different precision tools disagree on `is_material`? [Gap, Clarity, Spec §R-021.2]
- [X] CHK040 Are determinism guarantees extended to the FR-028 explicit-off legacy-path test (if landed)? I.e., the test's pass/fail must be a pure function of the inverted default + the explicit-off flag, with no env-state dependency. [Coverage, Spec §FR-028, §SC-009]

## Notes

- This checklist is the holistic determinism gate. Individual determinism aspects appear in `benchmark.md`, `quality-gate.md`, `gpu-readiness.md`, and `failure-handling.md`; this file tests whether the determinism *discipline* is uniformly written across the spec and contracts.
- The principal failure mode is silent introduction of a wall-clock or model-derived decision (e.g., a "retry until it works" loop or a "confidence-weighted" verdict). CHK030–CHK033 are the defenses at the requirements-writing layer.
- Items CHK037–CHK040 flag genuine gaps that may benefit from a research.md amendment or planning-time decision.
