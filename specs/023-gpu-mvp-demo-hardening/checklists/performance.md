# Performance Requirements Quality Checklist: GPU MVP Demo Hardening

**Purpose**: Release-gate audit of performance-related requirements — the 600 s pipeline bound, the 10 s preflight bound, phase-timing reporting, and the three-run stability promise.
**Created**: 2026-05-24
**Feature**: [spec.md](../spec.md)

## Bounded Runtime Timeout

- [ ] CHK001 Is the 600-second pipeline timeout pinned as a concrete numeric default at the spec level (not deferred to planning)? [Clarity, Spec §FR-008]
- [ ] CHK002 Is the unit of the timeout (seconds, wall-clock) unambiguous, with no possibility of being interpreted as CPU-seconds? [Clarity, Spec §FR-008]
- [ ] CHK003 Is the timeout's tunability specified — fixed at 600 s, operator-overridable via flag/env, or runbook-tuned per machine? [Completeness, Gap]
- [ ] CHK004 Is the timeout scope defined precisely (start: after readiness passes; end: when all four artifacts have been schema-validated)? [Clarity, Spec §FR-008, FR-009]
- [ ] CHK005 Are per-phase sub-budgets within the 600 s aggregate specified, or only the aggregate bound? [Completeness, Gap]

## Preflight Bound (`--check-only`)

- [ ] CHK006 Is the 10-second preflight bound pinned at the spec level (SC-007), and is the measurement protocol (wall-clock from process start to exit) defined? [Clarity, Spec §SC-007]
- [ ] CHK007 Is "correctly configured warm workstation" defined precisely enough that SC-007 is verifiable — e.g., MIOpen cache populated, Paddle wheel loaded, host Ollama responsive — or left as an interpretive phrase? [Clarity, Spec §SC-007]
- [ ] CHK008 Is the preflight upper bound on a **cold** workstation specified (Q11 round 1 noted slack for cold imports — what is the cold-case bound)? [Coverage — Non-Functional, Gap]

## Phase-Timing Reporting

- [ ] CHK009 Are the four phase keys (`preprocess`, `extraction`, `routing`, `final_payload`) consistent with the four `failed_at_<phase>` values, the `stalled_phase` enum, and the sub-module names? [Consistency, Spec §FR-020/FR-025]
- [ ] CHK010 Is the measurement protocol per phase specified (e.g., wall-clock from sub-module invocation to its exit) so different runs measure the same thing? [Clarity, Spec §FR-025]
- [ ] CHK011 Is the requirement to include all four keys with `null` for unreached phases (FR-025) consistent with the unit-of-measurement requirement (seconds vs ms)? [Consistency, Spec §FR-025]
- [ ] CHK012 Is the source of phase timings specified — own instrumentation, or composed from feature 015's `run_summary.phase_timings`? [Completeness, Spec §Dependencies, FR-025]
- [ ] CHK013 Is `total_runtime_seconds` defined as ≥ sum of phase_timings (to account for inter-phase overhead), or as exactly the sum? [Clarity, Spec §FR-025]

## Three-Run Stability (SC-006)

- [ ] CHK014 Is "three consecutive runs" defined as same-process or successive-process invocations (cache state may differ)? [Clarity, Spec §SC-006]
- [ ] CHK015 Is the tolerance for phase-timing variance across three runs specified, or only `runtime_outcome` / `quality_status` stability? [Completeness, Spec §SC-006]
- [ ] CHK016 Is cold-vs-warm cache impact on SC-006 addressed — e.g., the first of three runs may be cold, the next two warm; is that acceptable? [Coverage, Gap]
- [ ] CHK017 Is the verification protocol for SC-006 (who runs it, when, what evidence is captured) specified, so the gate it implies (start of Jetson edge-fast) has a measurable criterion? [Measurability, Spec §SC-006]

## CPU Fallback Detection (Performance Side-Channel)

- [ ] CHK018 Are requirements specified for performance-side detection of silent CPU fallback (e.g., a CPU-mode run would massively exceed phase-timing baselines)? [Coverage, Spec §FR-012, Gap]
- [ ] CHK019 Is the spec explicit that timing heuristics are *not* the primary CPU-fallback detection (FR-012 chose post-run device interrogation), so performance timings are not load-bearing here? [Clarity, Spec §FR-012]

## Performance of Readiness Checks

- [ ] CHK020 Are individual readiness checks budgeted (e.g., HTTP call ≤ 1 s, version probe ≤ 1 s) so the aggregate 10 s bound is achievable? [Completeness, Gap]
- [ ] CHK021 Are short-circuit semantics specified — when one readiness check fails, are subsequent checks skipped, or do they still run within the 10 s budget? [Completeness, Spec §FR-026, Gap]

## Performance Under Degraded Conditions

- [ ] CHK022 Are performance requirements specified for the case where the workstation is under load (other GPU workloads, high CPU)? [Coverage — Non-Functional, Gap]
- [ ] CHK023 Are performance requirements specified for the case where `header-first-v1` falls back to a slower path (e.g., document with no recognizable header)? [Coverage — Edge Case, Gap]

## Primary / Alternate / Exception / Recovery / Non-Functional Coverage

- [ ] CHK024 Are performance requirements defined for the **primary** path (one demo run, warm cache, header-first-v1, single fixture)? [Coverage — Primary, Spec §FR-008/SC-007]
- [ ] CHK025 Are performance requirements defined for **alternate** paths (`--check-only`, `--preset full-ocr`, `--with-evaluator`)? [Coverage — Alternate, Gap]
- [ ] CHK026 Are performance requirements defined for **exception** paths (readiness fail = immediate exit; timeout = exit at 600 s)? [Coverage — Exception, Spec §FR-008/FR-021]
- [ ] CHK027 Are performance **recovery** requirements defined — e.g., after a timeout, can the operator immediately re-run without waiting on caches? [Coverage — Recovery, Gap]
- [ ] CHK028 Are performance **non-functional** thresholds quantified (10 s preflight, 600 s pipeline) and not left as adjectives ("fast", "responsive")? [Coverage — Non-Functional, Spec §FR-008/SC-007]

## Ambiguities & Conflicts

- [ ] CHK029 Is the relationship between Assumption "Bounded timeout default = 600 s" and FR-008 "MUST apply a 600-second default timeout" resolved as a single source of truth, with no implication that the runbook can quietly tighten it? [Conflict, Spec §FR-008, §Assumptions]
- [ ] CHK030 Are SC-006 and SC-007 measurable independently of each other (no implicit dependency where one's pass requires the other's failure to be ignored)? [Consistency, Spec §SC-006/SC-007]


---

**Plan coverage verification (2026-05-25):** see [plan-coverage.md](./plan-coverage.md) for the cross-reference of this checklist's items against `plan.md` / `research.md` / `data-model.md` / `contracts/` / `quickstart.md`.
