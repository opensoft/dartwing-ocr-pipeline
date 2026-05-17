# Release-Readiness Checklist: GPU Warmup And MIOpen Cache Stabilization

**Purpose**: Formal pre-merge gate validating the QUALITY of requirements across spec / plan / research / data-model / contracts / quickstart. These items test whether the requirements are well-written, complete, unambiguous, and consistent — NOT whether the implementation works. Use this for go/no-go on the PR before workstation GPU verification kicks off.
**Created**: 2026-05-08
**Feature**: [spec.md](../spec.md)
**Audience**: author (self-check), PR reviewer (peer go/no-go), GPU-verification operator (does the spec give me everything I need to validate?)
**Companion checklist**: [requirements.md](./requirements.md) — earlier post-`/speckit.specify` quality gate; all items pass.

## Requirement Completeness

- [x] CHK001 Are the four FR-017 documentation items (`~/.cache/miopen`/`~/.cache/comgr` locations, clearing procedure, `phase_timings.warmup` cold-vs-warm interpretation, `MIOPEN_FIND_MODE` rationale) AND the fifth US4 Independent Test item (workspace-warning meaning + operator guidance) explicitly cross-referenced so a reviewer can confirm the docs deliverable covers all five? [Completeness, Spec §FR-017, §US4, §SC-009]
- [x] CHK002 Is the cause-class taxonomy in `WarmupError` (`FixtureLoadError` / `ClockAnomaly` / `MIOpenError` / `PaddleError` / `UnknownError`) declared in a versioned contract location (data-model.md or cli-contract.md) with a stability statement, OR explicitly marked as an internal implementation detail? [Completeness, data-model.md §WarmupError]
- [x] CHK003 Is the `DARTWING_GPU_WARMUP` env-var truthiness whitelist (`{"1", "true", "yes"}`) documented as the canonical contract — including what happens to ambiguous values like `2` or `on` — in a place a CLI-using operator will find? [Completeness, contracts/cli-contract.md §1, data-model.md §"Activation-surface state machine"]
- [x] CHK004 Are operator-set env vars (`MIOPEN_FIND_MODE`, `MIOPEN_USER_DB_PATH`, `MIOPEN_CUSTOM_CACHE_DIR`, `MIOPEN_LOG_LEVEL`) documented as taking precedence over feature-shipped defaults, and is "operator override wins" stated in the spec or just in research? [Completeness, research.md R-016.4 / R-016.5]
- [x] CHK005 Is the default warmup-input fixture path (`tests/stage1_vendor_identity/inv_001_easy/source.pdf`) treated as a hard dependency the spec or quickstart calls out, so a future fixture rename triggers a known break instead of a silent failure? [Completeness, research.md R-016.2, contracts/module-invariants.md I-8]
- [ ] CHK006 Are operator instructions for "what to do when warmup keeps failing repeatedly" (i.e., a recovery / triage path) documented somewhere? Or is the absence of such guidance intentional and stated? [Completeness, Gap]
- [x] CHK007 Is the assumption "`$HOME/.cache/` is writable on the workstation" documented as a precondition for warmup runs? [Completeness, Gap]

## Requirement Clarity

- [x] CHK008 Is "deterministic across runs" (FR-005) quantified — does it commit to a specific DPI, fixture path, image-bytes sha256, and rasterization code path, or are some of those left as "implementation detail"? [Clarity, Spec §FR-005, research.md R-016.2]
- [x] CHK009 Is the exact stderr literal for warmup failure (`error: warmup failed: <cause-class>: <message>`) and for CPU/stub warn-and-proceed (`--gpu-warmup ignored:`) part of a stable contract a test can grep against, or only example wording? [Clarity, Spec §FR-007, contracts/cli-contract.md §3]
- [x] CHK010 Is exit code **15** for warmup failure documented at spec level (FR-007 / SC-011), or only at plan/contract level? If only the latter, is the spec language ("non-zero") consistent with the contract's specific code? [Clarity, Spec §FR-007, contracts/cli-contract.md §4, research.md R-016.6]
- [x] CHK011 Is "first per-document entry whose `status == "success"`" (FR-006) precisely defined when no document succeeds — does the spec specify that `phase_timings.warmup` is then absent everywhere, or is that left implicit? [Clarity, Spec §FR-006, data-model.md §"`phase_timings.warmup`"]
- [x] CHK012 Is "before the first timed document's preprocessing" (FR-001) defined operationally — i.e., before any `measure_total` or `measure_phase` opens, with engine reuse confirmed? [Clarity, Spec §FR-001, contracts/module-invariants.md I-3]
- [x] CHK013 Is "warmup opt-in" used consistently across spec / plan / research / contracts, or is there term drift (e.g., "warmup-enabled", "GPU warmup", "warmup mode")? [Clarity, Consistency]

## Requirement Consistency

- [x] CHK014 Do FR-017's four documentation items and US4's five Independent Test items align — specifically, is workspace-warning explanation (US4 item d) covered by FR-016 alongside FR-017, and is the relationship between FR-017 and FR-016 explicit? [Consistency, Spec §FR-016, §FR-017, §US4]
- [x] CHK015 Is the `phase_timings.warmup` shape `{seconds: <float>}` stated identically across spec (FR-006), data-model.md, contracts/run-summary-schema.md, and Definitions, with no field-name or rounding-precision drift? [Consistency, Spec §FR-006, contracts/run-summary-schema.md §2]
- [x] CHK016 Are FR-002 (off-by-default), FR-010 (CPU/stub warn-and-proceed), and the activation-surface truth table in data-model.md mutually consistent — e.g., does the truth table cover every (flag × env × profile) combination FR-002/FR-010 imply? [Consistency, Spec §FR-002, §FR-010, data-model.md §"Activation-surface state machine"]
- [x] CHK017 Is the "first successful per-document entry" attachment rule for `phase_timings.warmup` (FR-006) consistent with feature 015's existing rule for `paddle_import` / `gpu_bind_probe` / `engine_init`, and is the co-location explicitly stated rather than implied? [Consistency, Spec §FR-006, contracts/run-summary-schema.md §4]
- [x] CHK018 Is the codebase-level `schema_version` 0.1.2 → 0.1.3 bump specified identically in spec FR-008, research R-016.9, data-model `RunSummary.SCHEMA_VERSION`, and contracts/run-summary-schema.md §1 (no version-string mismatch)? [Consistency, Spec §FR-008, /speckit.clarify Q2]
- [x] CHK019 Is the FR-016 hybrid policy (per /speckit.clarify Q3) — "addressed by default config" + "residual / known diagnostic" dual list — required identically in research.md, the docs deliverable, and the spec, or does the docs deliverable have a stricter form (e.g., "with operator guidance" only in some places)? [Consistency, Spec §FR-016, research.md R-016.5, quickstart.md Appendix B]

## Acceptance Criteria Quality

- [x] CHK020 Is SC-003's 2× cold-vs-warm threshold explicitly described as a placeholder with a documented amendment path (where it is finalized, by whom, and before what gate), so the criterion's meaning is unambiguous after merge? [Acceptance Criteria, Spec §SC-003, research.md R-016.3]
- [x] CHK021 Are SC-001 / SC-002 / SC-005 phrased as positive AND negative assertions (warmup present in expected case, absent in non-warmup / corpus-doc-2-onward / failure cases) so a test author cannot satisfy them by checking only one direction? [Acceptance Criteria, Spec §SC-001, §SC-002, §SC-005]
- [x] CHK022 Is the SC-008 byte-identity check defined with a specific verification mechanism (sha256 of `preprocess_output.json`) and a specific reference run (same fixture, same profile, both runs in fresh processes), so "byte-identical" cannot be interpreted loosely? [Acceptance Criteria, Spec §SC-008, contracts/module-invariants.md I-10]
- [x] CHK023 Does SC-011 enumerate ALL forbidden states on warmup failure (no `phase_timings.warmup`, no per-doc `run_summary` entry, no `preprocess_output.json` for would-have-been-timed docs, no silent downgrade), or is the negation set partial? [Acceptance Criteria, Spec §SC-011]
- [x] CHK024 Is SC-010's "all feature 015 success criteria continue to hold" enumerated by ID (015 SC-001 through SC-008) so the regression check is unambiguous, rather than "feature 015 still works"? [Acceptance Criteria, Spec §SC-010]

## Scenario Coverage

- [x] CHK025 Are requirements specified for ALL primary scenarios: warmup-enabled GPU single-doc, warmup-enabled GPU corpus, warmup-disabled GPU single-doc, warmup-disabled GPU corpus? [Coverage, Spec §US1]
- [x] CHK026 Are requirements specified for the alternate scenarios: cold-cache vs warm-cache observable difference, comgr-only-cleared mixed-cache state? [Coverage, Spec §US2]
- [x] CHK027 Are exception-flow requirements specified for: warmup-pass exception, fixture-load exception, clock-anomaly exception (all of which `WarmupError` represents), AND for the upstream feature-015 GPU-prereq failure path coexisting with the warmup feature? [Coverage, Spec §FR-007, data-model.md §WarmupError, Spec §FR-020]
- [ ] CHK028 Are recovery / re-run requirements specified after a warmup failure — e.g., does the operator clear caches and retry, or investigate first? Or is recovery intentionally out of scope? [Coverage, Recovery, Gap]
- [x] CHK029 Are non-functional scenario requirements specified: cold-vs-warm signal magnitude (SC-003), default-suite-without-GPU (SC-006), GPU-prereq-fail-fast continued from feature 015 (SC-010 reference)? [Coverage, Non-Functional]

## Edge Case Coverage

- [x] CHK030 Are requirements specified for the case where MIOpen / COMGR cache directories are NOT writable (e.g., read-only `$HOME`, full disk), or is this a runtime "let MIOpen handle it" decision — and if so, is that documented? [Edge Case, Gap]
- [x] CHK031 Is the case "warmup succeeds but every per-document inference fails" addressed — specifically that `phase_timings.warmup` is then absent because no per-doc entry has `status == "success"`? [Edge Case, data-model.md §"`phase_timings.warmup`" presence rules]
- [x] CHK032 Are concurrency edge cases addressed — two parallel warmup-enabled processes writing to the same `~/.cache/miopen`? Is this a known-safe behavior of MIOpen, and is that statement documented or just assumed? [Edge Case, Gap]
- [x] CHK033 Is the case "operator passes ambiguous `DARTWING_GPU_WARMUP` value" (e.g., `2`, `on`, `enabled`, empty) specified as silently-treated-as-unset rather than as an error, in a place CI scripts can rely on? [Edge Case, contracts/cli-contract.md §1, data-model.md §"Activation-surface state machine"]
- [x] CHK034 Are requirements clear about what happens when the default warmup fixture (`inv_001_easy/source.pdf`) is multi-page in some future corpus revision — does FR-005's "same number of pages" still hold given a single-page warmup? [Edge Case, Spec §FR-005, research.md R-016.2]
- [x] CHK035 Is `KeyboardInterrupt` (operator hits Ctrl+C mid-warmup) addressed — either as out-of-scope or with a defined behavior (cache state, exit code, stderr message)? [Edge Case, Gap]

## Non-Functional & Cross-Artifact Quality

- [x] CHK036 Are warmup-related observability requirements (stderr formats, exit codes, run_summary additive key) confined to documented contract files (`cli-contract.md`, `run-summary-schema.md`, `module-invariants.md`) so a future audit can find them in one place? [Non-Functional, Traceability]
- [x] CHK037 Is the "no new persisted artifact" rule (FR-019) restated in plan / data-model / contracts so the assertion is reaffirmed, not just buried in spec? [Non-Functional, Spec §FR-019, data-model.md §"Out-of-scope entities"]
- [x] CHK038 Are the four feature-shipped MIOpen env vars (`MIOPEN_FIND_MODE`, `MIOPEN_USER_DB_PATH`, `MIOPEN_CUSTOM_CACHE_DIR`, `MIOPEN_LOG_LEVEL`) listed identically in research.md, data-model.md, and the FR-016 docs deliverable, with the same defaults and the same "operator override wins" rule? [Non-Functional, Consistency, research.md R-016.5, data-model.md §"Default env-var configuration"]
- [x] CHK039 Is the constitution Quality Gate #2 inapplicability ("schemas.md unchanged because no stage 1 output artifact contract changes") documented in plan.md so a constitution reviewer can confirm without re-deriving the argument? [Non-Functional, plan.md §Constitution Check]

## Dependencies & Assumptions

- [x] CHK040 Are all spec Assumptions still valid given /speckit.clarify outcomes — specifically, does the spec note that the previously-deferred CPU+opt-in OR (FR-010) and FR-016 OR are now collapsed by /speckit.clarify Q1 / Q3, so a reader doesn't see contradictions between Assumptions and the Clarifications log? [Assumption, Spec §Clarifications, §Assumptions]
- [x] CHK041 Is the dependency on feature 015's `_adopt_engine` / `_ENGINE` singleton stated as a hard prerequisite the spec assumes is shipped, with a pointer to the relevant FRs (015 FR-001 / FR-006 → 016 FR-003 / FR-020)? [Assumption, Spec §Assumptions, §FR-003, §FR-020]
- [x] CHK042 Is the "no new pinned dependency" claim (plan.md Technical Context) verifiable — i.e., is `pyproject.toml` listed as the source of truth and explicitly unchanged by this feature? [Assumption, plan.md §Technical Context]

## Documentation Deliverable Quality (US4 / FR-017 / FR-016)

- [x] CHK043 Does the docs deliverable (`docs/stage1-vendor-identity/gpu-warmup-and-cache.md`) have its filename, location, and ownership pinned in plan.md so a reviewer can find it before merge — even though the file content is filled at landing time? [Documentation, plan.md §Project Structure]
- [x] CHK044 Are the FR-016 hybrid dual lists ("addressed by default config" + "residual / known diagnostic") required to follow a specified format (e.g., env var name + purpose; warning text + meaning + operator guidance), or is the format left to the writer's discretion? [Documentation, Clarity, Spec §FR-016, quickstart.md Appendix B]
- [x] CHK045 Is SC-009's pass criterion ("documentation answers all five questions from US4's Independent Test") testable as written — i.e., can a reviewer mechanically check each of the five against the docs, or is the test subjective? [Acceptance Criteria, Spec §SC-009]

## Deferred-Verification & Release Gating

- [x] CHK046 Is FR-014's deferral path ("if workstation GPU verification cannot be performed before merge, deferred items MUST be captured in the feature's tasks/quickstart") required to land as concrete entries in `tasks.md` (when /speckit.tasks runs) and Appendix A of quickstart.md, so deferred items cannot be quietly skipped? [Deferred Verification, Spec §FR-014, quickstart.md §Appendix A]
- [x] CHK047 Is the workstation cold-vs-warm tuning workflow (quickstart Appendix A) required to land WITH numbers filled before merge if GPU verification IS performed, or is it acceptable to land empty? [Release Gate, quickstart.md §Appendix A]
- [x] CHK048 Is the FR-015 amendment path (re-tune `MIOPEN_FIND_MODE` if measurements warrant) required to be exercised before merge, OR is the feature allowed to ship with the placeholder default and the amendment path used post-landing? Is this clearly documented? [Release Gate, Spec §FR-015, research.md R-016.4]

## Notes

- 48 items across 11 quality dimensions (sequential CHK001–CHK048; numbering is feature-local, not shared with `requirements.md`'s passing items).
- Every item asks about the **quality of requirements writing**, never about implementation behavior. Items use `Are … specified?`, `Is … documented?`, `Do … align?` rather than `Verify`, `Test`, `Confirm`.
- Traceability: 47/48 items (≈98%) carry at least one of `[Spec §X.Y]`, `[research.md R-…]`, `[contracts/…]`, `[data-model.md §…]`, `[quickstart.md §…]`, or a marker (`[Gap]`, `[Consistency]`, `[Coverage]`, `[Edge Case]`). The single exception (CHK013) is a term-drift question intentionally cross-cutting.
- Markers used: `[Completeness]`, `[Clarity]`, `[Consistency]`, `[Coverage]`, `[Edge Case]`, `[Acceptance Criteria]`, `[Non-Functional]`, `[Assumption]`, `[Documentation]`, `[Recovery]`, `[Traceability]`, `[Gap]`. `[Conflict]` is not currently raised — none observed during this pass.
- Recommended use order:
  1. **Author** runs items in §Requirement Completeness, §Acceptance Criteria Quality, §Documentation Deliverable Quality before opening PR.
  2. **Reviewer** runs items in §Requirement Clarity, §Requirement Consistency, §Scenario Coverage, §Edge Case Coverage during PR review.
  3. **GPU-verification operator** runs items in §Deferred-Verification & Release Gating, §Documentation Deliverable Quality, §Dependencies & Assumptions before signing off the workstation run + merging.
- This checklist is intentionally separate from the post-`/speckit.specify` `requirements.md`. Don't merge the two; both should remain in `checklists/` for audit.
- Findings: when an item fails, comment inline with `→ failing because …` and either fix the requirement (preferred) or open a follow-up (acceptable per FR-014 for verification items only).
