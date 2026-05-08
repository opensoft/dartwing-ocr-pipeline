# Failure-Handling Checklist: GPU Warmup And MIOpen Cache Stabilization

**Purpose**: Focused requirement-quality gate for the warmup fail-fast surface — `WarmupError`, exit code 15, stderr format, forbidden-state enumeration, cause-class taxonomy, recovery, edge-case failures, and the no-silent-downgrade rule. These items test whether the requirements around failure handling are well-written, complete, and consistent — NOT whether the failure path works.
**Created**: 2026-05-08
**Feature**: [spec.md](../spec.md)
**Audience**: PR reviewer (peer go/no-go on the fail-fast contract before workstation verification)
**Companion checklists**: [requirements.md](./requirements.md), [release-readiness.md](./release-readiness.md). Items marked **(seeded)** are the failure-related gaps the release-readiness pass surfaced; closing them here means the broad checklist's items can be ticked off once those gaps are resolved.

## Failure Surface Completeness

- [x] CHK001 Are ALL entry points inside `run_warmup` that can raise (fixture-load step, clock-anomaly check, `engine.predict(...)` invocation, env-var-default application) covered by the cause-class taxonomy with no implicit "unhandled exception" gap? [Completeness, data-model.md §WarmupError]
- [ ] CHK002 **(seeded)** Is operator recovery guidance — "what to do when warmup keeps failing" — documented in the docs deliverable (`docs/stage1-vendor-identity/gpu-warmup-and-cache.md`), OR explicitly declared out of scope with a stated reason? [Completeness, Recovery, Gap, US4 / FR-017 — closes release-readiness CHK006 / CHK028]
- [x] CHK003 Are upstream feature-015 preflight failures (states `paddle_not_installed` / `paddle_cpu_only` / `gpu_not_exposed` / `gpu_exposed_paddle_cant_bind` / `ppstructurev3_init_failed`, exit codes 10–14) and feature-016's `WarmupError` (exit 15) presented as a unified, ordered failure taxonomy a reviewer can read in one place — rather than scattered across spec FR-020, cli-contract.md §4, and feature 015 docs? [Completeness, Spec §FR-020, contracts/cli-contract.md §4]

## Failure Surface Clarity

- [x] CHK004 **(seeded, sharpened)** Is the stderr literal `error: warmup failed: <cause-class>: <message>` declared as a stable contract — including: that `<cause-class>` is one of the taxonomy values, that `<message>` is the unwrapped underlying exception message, and that the literal prefix `error: warmup failed:` is what tests grep for? [Clarity, Spec §FR-007, contracts/cli-contract.md §3 — closes release-readiness CHK009]
- [x] CHK005 **(seeded)** Is exit code **15** documented at spec level (inside FR-007 or SC-011 themselves), or only at contract / research level? If the spec only says "non-zero", does the spec point at the contract as the binding source so a future spec edit cannot accidentally drift to a different code? [Clarity, Spec §FR-007, §SC-011, contracts/cli-contract.md §4 — closes release-readiness CHK010]
- [x] CHK006 Is the cause-class taxonomy (`FixtureLoadError`, `ClockAnomaly`, `MIOpenError`, `PaddleError`, `UnknownError`) declared as a closed set, an extensible open enum, or "implementation may add classes" — and is the chosen stance stated rather than inferred? [Clarity, data-model.md §WarmupError]
- [x] CHK007 Is the boundary between "MIOpen-class failures" (`MIOpenError`) and "general paddle/paddleocr failures" (`PaddleError`) precisely specified — i.e., does the spec / data-model say which exception module prefixes route to which cause-class? [Clarity, data-model.md §WarmupError, research.md R-016.6]

## Failure Surface Consistency

- [x] CHK008 Do spec §FR-007, §SC-011, contracts/cli-contract.md §3–§4, contracts/module-invariants.md §I-5, research.md §R-016.6, and data-model.md §WarmupError all reference the same exit code (15), the same stderr literal format, and the same forbidden-state list — with no field drift between sources? [Consistency, Traceability]
- [x] CHK009 Is the differentiation between preflight failure (feature 015, exit 10–14, stderr prefix `error: --preprocess-profile=ppstructurev3@gpu:`) and warmup failure (feature 016, exit 15, stderr prefix `error: warmup failed:`) stated clearly enough that an operator triaging a stderr line knows which failure path they're in without consulting source? [Consistency, Spec §FR-020, contracts/cli-contract.md §4]

## Forbidden-State Enumeration

- [x] CHK010 **(seeded)** Does SC-011 enumerate ALL forbidden states on warmup failure — no `phase_timings.warmup`, no per-document `run_summary` entry for any document that would have been timed after the failure, no `preprocess_output.json` for any such document, no silent downgrade — AND does it explicitly cover the "no overall run_summary header" rule from research R-016.6, or is that rule implicit? [Acceptance Criteria, Spec §SC-011, research.md R-016.6 — closes release-readiness CHK023]
- [x] CHK011 Is the rule "no `run_summary` is emitted at all on warmup failure" (vs. "header-only run_summary with `documents_total = 0`") stated in the spec or in a versioned contract — not only as the rationale paragraph in research R-016.6? [Completeness, research.md R-016.6]

## Failure Recovery & Operator Triage

- [x] CHK012 Is the cache-state-after-failure (i.e., what's in `~/.cache/miopen` and `~/.cache/comgr` after a `WarmupError` aborts the run) specified — left as-is, partially populated, cleared, undefined? An operator re-running after failure needs a known starting state. [Recovery, Gap]
- [ ] CHK013 Is the operator's "first thing to try" after a `WarmupError` documented (e.g., "clear caches and retry once" vs "investigate cause-class first")? Or is the spec intentionally silent and that silence stated? [Recovery, Gap, US4 / FR-017]

## Failure Edge Cases

- [x] CHK014 **(seeded)** Are requirements specified for read-only `$HOME` / read-only `~/.cache/miopen` (cache-write failure during warmup) — does this surface as `WarmupError` with which cause-class, or as a non-warmup failure? [Edge Case, Gap, data-model.md §WarmupError — closes release-readiness CHK030]
- [x] CHK015 **(seeded)** Is the case "two parallel warmup-enabled processes writing the same `~/.cache/miopen`" classified as known-safe-via-MIOpen (with a documentation source) or as undefined-behavior the operator should avoid? [Edge Case, Gap — closes release-readiness CHK032]
- [x] CHK016 **(seeded)** Is operator-initiated `KeyboardInterrupt` (Ctrl+C) mid-warmup specified — exit code, stderr message, cache-state guarantee — or explicitly declared out of scope? [Edge Case, Gap — closes release-readiness CHK035]
- [x] CHK017 Are disk-full / filesystem-error scenarios during MIOpen cache write specified — do they surface as `WarmupError` (which cause-class) or as a different failure path entirely? [Edge Case, Gap]

## Failure Boundary & Acceptance-Criteria Quality

- [x] CHK018 Is "no silent fallback to a no-warmup run" (FR-007 / SC-011) testable with a concrete positive-form assertion — e.g., that on `WarmupError` no per-document entry of any kind is emitted, the process exits 15, and the documents directory is unchanged — rather than only the negative phrase "MUST NOT silently downgrade"? [Acceptance Criteria, Spec §FR-007, §SC-011, contracts/module-invariants.md §I-5]

## Notes

- 18 items across 7 categories (CHK001–CHK018). Numbering is local to this file; release-readiness.md keeps its CHK001–CHK048 space.
- Items marked **(seeded)** correspond to specific gaps from `release-readiness.md` (CHK006, CHK009, CHK010, CHK023, CHK028, CHK030, CHK032, CHK035). When these are closed here, the matching items in `release-readiness.md` should also be ticked off.
- All items use requirement-quality phrasing (`Are … specified?`, `Is … documented?`, `Do … align?`). Zero items use prohibited verbs (`Verify` / `Test` / `Confirm` / `Check`-as-action).
- Traceability: 18/18 (100%) carry at least one `[Spec §…]`, `[contracts/…]`, `[research.md …]`, `[data-model.md …]` reference, or `[Gap]`/`[Recovery]`/`[Edge Case]`/`[Consistency]` marker. Above the 80% minimum.
- Recommended use: items in §Failure Surface Completeness + §Failure Surface Clarity + §Failure Surface Consistency are PR-blocking (the contracts they probe are public surfaces shared with operators and CI). §Forbidden-State Enumeration is acceptance-criteria-blocking (SC-011 is the criterion future tests assert against). §Recovery and §Edge Cases items can be closed by either documentation update or explicit out-of-scope declaration with a one-line reason — both are acceptable resolutions per FR-014's deferral pattern.
- Findings: when an item fails, comment inline with `→ failing because …` and either edit the spec / contract / docs (preferred) or open a follow-up + mark out-of-scope.
