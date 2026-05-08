# GPU Observability Checklist: GPU Warmup And MIOpen Cache Stabilization

**Purpose**: Focused requirement-quality gate for the operator-facing run_summary observability surface — `phase_timings.warmup` presence rules, cold-vs-warm SC-003 signal magnitude, phase-key isolation (FR-007 / FR-009), co-location with feature-015 first-doc keys, schema additivity (FR-008), and the docs-side operator interpretation. These items test whether the requirements around what an operator reads off `run_summary` are well-written, complete, and consistent — NOT whether the emitted numbers are correct.
**Created**: 2026-05-08
**Feature**: [spec.md](../spec.md)
**Audience**: PR reviewer (peer go/no-go on the observability contract before workstation verification fills in concrete numbers)
**Companion checklists**: [requirements.md](./requirements.md), [release-readiness.md](./release-readiness.md), [failure-handling.md](./failure-handling.md). Items marked **(seeded)** close gaps surfaced by the release-readiness pass — closing them here means the matching items in `release-readiness.md` can be ticked off.

## Phase-Timing Presence Rules Quality

- [x] CHK001 Is the `phase_timings.warmup` 5-row presence truth table (opt-in absent / opt-in + non-gpu profile / opt-in + gpu + warmup OK / opt-in + gpu + warmup fails / opt-in + gpu + warmup OK + all docs fail) enumerated in a single source of truth, or is it scattered across spec FRs, data-model, and contracts? [Completeness, data-model.md §"`phase_timings.warmup`" presence rules, contracts/run-summary-schema.md §3]
- [x] CHK002 Is "first per-document entry whose `status == "success"`" precisely defined when ZERO documents succeed — i.e., is the answer "warmup is then absent everywhere" stated explicitly in the spec, or only inferable? [Clarity, Spec §FR-006, data-model.md §"`phase_timings.warmup`"]
- [x] CHK003 Is the rule "`phase_timings.warmup` lands on the FIRST successful entry only, never on any later successful entry" stated identically in spec FR-006 / SC-005, data-model.md presence rules, and contracts/run-summary-schema.md §3, with no wording drift? [Consistency, Spec §FR-006, §SC-005]
- [x] CHK004 Are the boundary conditions for "successful entry" defined — does a per-doc entry with `status: "success"` but partial phase_timings (e.g., `artifact_write` missing because of a write-time recovery) still count as the warmup-attachment target? [Edge Case, Gap]

## Cold-vs-Warm Signal Quality

- [x] CHK005 **(seeded)** Is SC-003's 2× cold-vs-warm threshold explicitly described as a placeholder with a documented amendment path — where it is finalized (research.md), by whom (workstation operator at landing), and before which gate (merge) — so the criterion's meaning is unambiguous after merge? [Acceptance Criteria, Spec §SC-003, research.md R-016.3 — closes release-readiness CHK020]
- [x] CHK006 Is the operational definition of "cold cache" vs "warm cache" in spec Definitions ("absent or empty for the active ROCm + driver + PPStructureV3 configuration" / "populated by a prior run with a compatible configuration") tight enough that an operator can identify the cache state from filesystem evidence at landing time, OR is "detect via `phase_timings.warmup.seconds` magnitude only" the binding rule? Both can't be authoritative simultaneously. [Clarity, Spec §Definitions, §SC-003, data-model.md §"MIOpen / COMGR cache state"]
- [ ] CHK007 Is the magnitude semantics "cold = MIOpen kernel-selection cost, warm = cache-hit lookup cost" stated in operator-facing form somewhere (docs deliverable plan or quickstart), so an operator triaging a borderline cold-vs-warm ratio knows what each number represents? [Completeness, US4 / FR-017, quickstart.md §1]

## Phase-Key Isolation Quality

- [x] CHK008 Are the four "warmup time MUST NOT fold into" excluded keys (`total`, `rasterization`, `per_page_inference[*].seconds`, `artifact_write`) enumerated identically in spec FR-007, SC-004, and contracts/module-invariants.md §I-4, with no key omitted in any source? [Consistency, Spec §FR-007, §SC-004]
- [x] CHK009 Is the legacy back-compat rule "`gpu_init_seconds` continues to mean `paddle_import + gpu_bind_probe + engine_init` only — warmup time is reported ONLY via `phase_timings.warmup`" (FR-009) stated with an explicit corresponding negative assertion ("warmup MUST NOT inflate `gpu_init_seconds`"), or is it only inferable from the affirmative wording? [Clarity, Spec §FR-009]
- [x] CHK010 Can SC-004's "first document's `phase_timings.total` does NOT include warmup time" be objectively verified by a future test — i.e., is the verification mechanism (e.g., `total ≈ rasterization + sum(per_page_inference[*].seconds) + artifact_write` within rounding) specified, or does the criterion lean on inspection? [Acceptance Criteria, Spec §SC-004]

## Co-Location Rule Quality

- [x] CHK011 **(seeded)** Is the co-location rule "`phase_timings.warmup` lands alongside `paddle_import` / `gpu_bind_probe` / `engine_init` on the SAME first-successful-doc entry" stated explicitly AND consistently with feature 015's first-doc attachment rule (its FR-015), with no subtle redefinition of "first-successful-doc"? [Consistency, Spec §FR-006, §FR-020, contracts/run-summary-schema.md §4 — closes release-readiness CHK017]
- [x] CHK012 Is the implementation surface (one helper `attach_one_time_gpu_phases` attaches all four keys, vs. two sibling helpers) declared as a contract or as an implementation detail? The choice affects whether downstream tests can rely on "all four first-doc one-time keys present together or all absent together". [Clarity, research.md R-016.8]

## Schema Additivity Quality

- [x] CHK013 **(seeded)** Is the codebase-level `schema_version` 0.1.2 → 0.1.3 bump stated identically across spec FR-008, research R-016.9, data-model.md §"`RunSummary.SCHEMA_VERSION`", and contracts/run-summary-schema.md §1, with no version-string typo or drift between sources? [Consistency, Spec §FR-008, /speckit.clarify Q2 — closes release-readiness CHK018]
- [x] CHK014 **(seeded)** Is the `phase_timings.warmup` shape contract (`{seconds: <float>}` only, no other sub-keys, no nested objects, additionalProperties false) stated identically in spec §Definitions, data-model.md `WarmupResult` mapping, and contracts/run-summary-schema.md §2, with no field-name or type drift? [Consistency, Spec §Definitions, §FR-006 — closes release-readiness CHK015]
- [x] CHK015 Is the rounding precision (six decimal places per the existing `pipeline/timing.py` convention) stated as a contract for `phase_timings.warmup.seconds`, or only inferable from "matches the rest of the scalar `phase_timings` entries from feature 015"? [Clarity, Spec §Assumptions, contracts/run-summary-schema.md §1]

## Run-Summary Coexistence

- [x] CHK016 Is the rule "the warmup-related change touches ONLY `per_document[*].phase_timings.warmup` — top-level run_summary fields (`stack_preset`, `resolved_profiles`, `execution_slice`, `on_failure`, `documents_total`, `documents_succeeded`, `documents_failed`, `profile_initialization_seconds`, `preprocess_lane`) are unchanged" stated as an explicit contract, or only inferable from "additive to per_document"? [Completeness, contracts/run-summary-schema.md §7]

## Operator Interpretation

- [ ] CHK017 Does the docs deliverable plan require explaining HOW an operator reads `phase_timings.warmup` from `run_summary` — including a sample excerpt, what each number means in context, and when (if ever) the operator should act on a value — or does it only require explaining cache-state semantics? [Completeness, US4 / FR-017, §SC-009]
- [ ] CHK018 Is the relationship between `phase_timings.warmup`, the legacy flat `gpu_init_seconds`, and the structured `phase_timings.{paddle_import, gpu_bind_probe, engine_init}` keys explained in operator-facing documentation, so an operator reading both legacy and structured emissions in the same run_summary line cannot mistakenly double-count warmup? [Completeness, Spec §FR-009, US4 / FR-017]

## Notes

- 18 items across 7 categories (CHK001–CHK018). Numbering is local; release-readiness.md and failure-handling.md keep their own ID spaces.
- **(seeded)** items close specific gaps from `release-readiness.md` (CHK015 → here CHK014, CHK017 → here CHK011, CHK018 → here CHK013, CHK020 → here CHK005). Closing them here lets the matching release-readiness items be ticked off.
- All items use requirement-quality phrasing (`Are … specified?`, `Is … stated?`, `Do … align?`). Zero items use prohibited verbs (`Verify` / `Test` / `Confirm` / `Check`-as-action).
- Traceability: 18/18 (100%) carry at least one source reference (`[Spec §…]`, `[contracts/…]`, `[research.md R-…]`, `[data-model.md §…]`, `[quickstart.md …]`) or quality marker (`[Gap]`, `[Edge Case]`, `[Consistency]`). Above the 80% minimum.
- Recommended use: items in §Phase-Timing Presence Rules Quality + §Schema Additivity Quality are PR-blocking (the contracts they probe are the consumer-facing schema future tests assert against). §Cold-vs-Warm Signal Quality and §Operator Interpretation can be partially deferred to landing if cold-vs-warm tuning is deferred under FR-014, but the *requirements about what to document* must still be present pre-merge.
- Findings: when an item fails, comment inline with `→ failing because …` and either edit the spec / contract / data-model / docs-plan (preferred) or note as out-of-scope with a one-line reason.
