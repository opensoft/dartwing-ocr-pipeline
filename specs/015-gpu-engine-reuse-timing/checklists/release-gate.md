# Release-Gate Requirements-Quality Checklist: GPU Engine Reuse And Phase Timing

**Purpose**: All-up release-gate validation that the requirements written in `spec.md` (with the 2026-05-07 clarification session), `plan.md`, `research.md`, `data-model.md`, `contracts/run-summary-schema.md`, `contracts/module-invariants.md`, and `quickstart.md` are complete, clear, consistent, and measurable before `/speckit.tasks` and `/speckit.implement`. Items test the **requirements**, not the implementation. NFR items bounded to the explicit SC-007 budget and the "no other latency target" assumption.
**Created**: 2026-05-07
**Last updated**: 2026-05-07 (post-`/speckit.analyze` cleanup + 52-item resolution pass)
**Feature**: [spec.md](../spec.md) | depth: formal release gate | audience: PR reviewer + release approver

## Requirement Completeness — Observability surface

- [x] CHK001 Are all FR-013 phases (paddle_import, gpu_bind_probe, engine_init, optional warmup, rasterization, per-page inference, artifact_write, total) explicitly enumerated in the same order in both `spec.md §FR-013` and `contracts/run-summary-schema.md §phase_timings keys`? [Completeness, Spec §FR-013] — Resolved by single-source-of-truth notes added to `research.md`, `data-model.md`, and `contracts/run-summary-schema.md` pointing back to `spec.md §FR-013`.
- [x] CHK002 Is the canonical `phase_timings` key vocabulary (paddle_import, gpu_bind_probe, engine_init, warmup, rasterization, artifact_write, total) defined in exactly one authoritative place and cross-referenced from the others? [Consistency, Spec §FR-014] — Resolved alongside CHK001.
- [x] CHK003 Are the rules for which phase keys appear on the **first** vs. **subsequent** per-document entries explicitly stated? [Completeness, Spec §FR-015 / SC-002] — Resolved by tightening `spec.md §FR-015` to define "first successfully processed per-document entry" with explicit failed-doc behavior.
- [x] CHK004 Is the rule for the **CPU lane** absence of paddle_import / gpu_bind_probe / engine_init / warmup / per_page_inference keys stated as a positive requirement (not implied by the GPU-lane gates)? [Completeness, Spec §FR-017] — Resolved: FR-017 ("CPU and stub adapter paths MUST NOT execute GPU preflight, GPU bind probes, or GPU-specific timing instrumentation") is a positive requirement; `contracts/run-summary-schema.md §phase_timings keys` table also states "CPU lane: `paddle_import`, `gpu_bind_probe`, `engine_init`, `warmup` MUST be absent (FR-017)" and "CPU lane: array MUST be absent."
- [x] CHK005 Is the per_page_inference page numbering convention (1-based, matching `preprocess_output.json[*].pages[*].page_number`) stated as a normative requirement (not just a research-doc decision)? [Clarity, Spec §FR-014 + R-015.3] — Resolved: `spec.md §FR-014` explicitly states "where `page` is 1-based and matches the page numbering used in `preprocess_output.json`."

## Requirement Completeness — Engine reuse

- [x] CHK006 Is the precise scope of "construct PPStructureV3 no more than once" defined (constructor invocation count vs. `predict()` count vs. wall-clock proxy)? [Clarity, Spec §FR-001 / §SC-001] — Resolved by `spec.md §Definitions` defining "Construct PPStructureV3" = constructor invocation, verified by counter assertion (matches T013, T019).
- [x] CHK007 Is the relationship between FR-002's two options ("preflight stops short of construction" vs. "share one process-scoped engine") and the chosen R-015.1 strategy explicit in `plan.md` so a reviewer doesn't have to read `research.md` to know which option was taken? [Completeness, Plan §Summary] — Resolved: `plan.md §Summary` already states "classify's PPStructureV3 probe persists its constructed engine into the runtime singleton (`ocr._ENGINE` / `_ENGINE_DEVICE`) instead of destroying it, so step 6 *is* the runtime engine" — explicit choice of the share-one-engine option.
- [x] CHK008 Are requirements stated for the standalone preflight CLI's `--no-init` path, specifically that it MUST NOT touch `ocr._ENGINE`? [Completeness, Data-model §CF6] — Resolved: `data-model.md §CF6` and `contracts/module-invariants.md` table both state "`classify(attempt_ppstructurev3_init=False)` MUST NOT touch `ocr._ENGINE` or `ocr._ENGINE_DEVICE`." T002 case (b) regression-tests this.
- [x] CHK009 Is "process" defined unambiguously (OS process vs. logical run vs. interpreter session)? [Clarity, Spec §FR-001/§FR-005] — Resolved by `spec.md §Definitions` defining "one process / same process" = one OS process / one Python interpreter session.
- [x] CHK010 Are requirements specified for what happens to engine reuse across multiple invocations of the same warm-corpus driver (i.e., one process, multiple `--documents-file` invocations is or is not in scope)? [Coverage, Gap] — **Out of scope for feature 015**: the current corpus driver runs one process per `--documents-file`. No long-running daemon. If a future feature introduces a daemon, it amends the spec at that time.

## Requirement Clarity

- [x] CHK011 Is "fail fast" quantified with the SC-007 ≤ 10 s budget in every place the term appears (FR-007, FR-008, Edge Cases bullet "GPU prerequisites missing")? [Clarity, Spec §FR-007] — Resolved by adding "(within the SC-007 ≤ 10 s budget)" to FR-007 and the Edge Cases "GPU prerequisites missing" bullet.
- [x] CHK012 Is "additive way only" (FR-014) defined with a concrete rule (e.g., new optional fields, no rename, no removal, schema_version bump policy)? [Clarity, Spec §FR-014] — Resolved by extending FR-014 with the concrete rule: "existing keys MUST NOT be renamed, removed, or have their type changed; new keys are added under additionalProperties; the `schema_version` MUST be bumped one patch level."
- [x] CHK013 Is "the existing run_summary stdout line" disambiguated from any other possibly-existing stdout outputs (e.g., `kind: "preflight_readout"`, `kind: "failure"`, per-doc artifact summaries)? [Clarity, Spec §FR-014 + Q1] — Resolved: FR-014 references `kind: "run_summary"` specifically, which is unambiguously distinct from other JSONL `kind` values.
- [x] CHK014 Is "monotonic clock" specified as a requirement (not just a research-doc note) so the implementation can't be tempted to use `time.time()`? [Clarity, Spec §FR-014 + R-015.4] — Resolved: FR-014 says "Durations MUST be measured from a monotonic clock (e.g. `time.perf_counter()`)" — explicit MUST.
- [x] CHK015 Is the precision rule (six-decimal-rounded seconds) stated as a requirement, or is it left to implementation discretion? [Clarity, Spec §FR-014 — possibly Gap] — Resolved by `spec.md §Definitions` adding "Phase timing precision" rule (`round(delta_ns / 1e9, 6)`).
- [x] CHK016 Is "successful per-document entry" defined precisely enough to determine which document gets the one-time GPU phase keys when the first document fails inference but later documents succeed? [Clarity, Spec §FR-015 + Edge Cases] — Resolved by tightening FR-015 to define "first successfully processed per-document entry" + explicit failed-first-doc fallthrough behavior.

## Requirement Consistency

- [x] CHK017 Does the spec's claim "phase timing emits in the existing run_summary stdout line" (FR-014) hold across **single-document** and **corpus** modes, given that the single-doc CLI does not currently emit a run_summary line? [Consistency, Spec §FR-014 vs. §SC-004] — Resolved by tightening FR-014: "The line is emitted by the documents-file driver in warm-corpus mode and by the single-document CLI in single-document mode (with `documents_total: 1`); both emission sites MUST use the identical shape." Implementation lives in T017 (single-doc) + T021 (corpus).
- [x] CHK018 Are the FR-013 phase list and the `contracts/run-summary-schema.md` `phase_timings keys` table identical in name and ordering? [Consistency, Spec §FR-013 ↔ Contracts] — Resolved by single-source-of-truth note in contracts pointing to FR-013.
- [x] CHK019 Does FR-016's omission rule ("absent phases MUST be omitted rather than reported as zero") align with the FR-014 explicit shape (which uses `{seconds: float}` with no `nullable: true` flag)? [Consistency, Spec §FR-014 ↔ §FR-016] — Resolved: FR-014's shape `{seconds: <float>}` (no nullable flag) plus FR-016's "MUST be omitted" combine cleanly — absent means key not in dict at all, no `null` value form needed. The contract schema in `contracts/run-summary-schema.md` reinforces this with `additionalProperties: false` on each phase record.
- [x] CHK020 Is the schema_version bump strategy (0.1.1 → 0.1.2 patch) stated identically in `plan.md`, `research.md` (R-015.4), and `contracts/run-summary-schema.md`? [Consistency] — Verified: all three documents state "0.1.1 → 0.1.2 patch bump" identically.
- [x] CHK021 Are the legacy flat keys (`stages.preprocess.{total_seconds, gpu_init_seconds, gpu_inference_seconds}`) marked as preserved-for-back-compat in **all** of: spec, plan, research, contracts? [Consistency, Spec §FR-014 + Plan + R-015.4] — Resolved by adding the explicit "Existing legacy flat keys ... MUST be preserved in 0.1.2 for one schema version" sentence to FR-014. Plan, research R-015.4, and contracts already state this.
- [x] CHK022 Does the constitution's Quality Gate #2 ("Changes that affect output contracts must update `docs/stage1-vendor-identity/schemas.md`") apply here, given the run_summary line is internal pipeline metadata (not a stage 1 artifact)? Is this distinction stated? [Consistency, Constitution §Quality Gates ↔ Spec §FR-010] — Resolved by `plan.md §Constitution Check II` row now explicitly justifying QG#2 inapplicability.

## Acceptance Criteria Quality (SC-001 through SC-008)

- [x] CHK023 Can SC-001's "exactly 1" PPStructureV3 construction count be objectively measured (e.g., is the verification mechanism — instrumentation, log evidence, counter assertion — listed in priority order or left to choice)? [Measurability, Spec §SC-001] — Resolved: SC-001 lists three acceptable mechanisms; T013 / T019 pin the choice operationally to "counter assertion against a `paddleocr.PPStructureV3` mock."
- [x] CHK024 Can SC-002's "first document only" assertion be operationalized in a test without referring to implementation details (e.g., is the criterion "no `paddle_import` key on doc 2" sufficient or does it need additional guards)? [Measurability, Spec §SC-002] — Resolved: T019's assertion list pins the operational form: doc 0 contains `{paddle_import, gpu_bind_probe, engine_init}`; doc 1 does NOT contain any of those; both contain `{rasterization, artifact_write, total, per_page_inference}`.
- [x] CHK025 Are SC-003's four sub-criteria (validates contract, `pipeline_version` ends in `.gpu0`, non-empty `document_text`, ≥3 layout blocks) all already part of the active 1.2.0 contract set, or do any need to be hoisted? [Measurability, Spec §SC-003] — Resolved by strengthening T015 to assert all four sub-criteria explicitly.
- [x] CHK026 Is SC-004's "all required phase timings listed in FR-013" precisely matched to FR-013's bulleted list, including the optional-warmup omission rule? [Measurability, Spec §SC-004 ↔ §FR-013] — Resolved: SC-004 references FR-013 directly; T025 enforces the set match.
- [x] CHK027 Can SC-005's "slowest phase identifiable from output alone" be machine-verified, or is it a reader-experience criterion only? [Measurability, Spec §SC-005] — Resolved: T026 (sort by seconds desc) operationalizes machine verification of the data-shape support; SC-005 is fundamentally a reader-experience criterion that the data shape supports.
- [x] CHK028 Can SC-006's "no GPU phase entries" on a CPU run be verified by a single negative assertion ("the set of `phase_timings` keys is a subset of {rasterization, artifact_write, total}"), and is that operational form stated? [Measurability, Spec §SC-006] — Resolved: T030 pins exactly that subset assertion.
- [x] CHK029 Is SC-007's "10 seconds wall-clock from process start" measurement boundary unambiguous (e.g., is the start the OS process start, the Python interpreter start, or first user-code line)? [Clarity, Spec §SC-007] — Resolved by tightening SC-007 to "OS exec to first non-zero exit."
- [x] CHK030 Is SC-008's "skipped or marked, not failed" requirement testable via a single CI command (`pytest`) that produces a non-failing exit code on a GPU-less host? [Measurability, Spec §SC-008] — Resolved: T031 + T034 + T041 verify exactly this.

## Scenario Coverage — Primary, Alternate, Exception, Recovery

- [x] CHK031 Are requirements specified for the **primary** flow: cold single-doc GPU run, success path? [Coverage, Spec §US1] — Resolved: US1 with three acceptance scenarios.
- [x] CHK032 Are requirements specified for the **alternate** flow: warm corpus GPU run, ≥2 docs, all success? [Coverage, Spec §US2] — Resolved: US2 with three acceptance scenarios.
- [x] CHK033 Are requirements specified for the **exception** flow: GPU prereq missing → fail-fast? [Coverage, Spec §US1 AS3 + §SC-007] — Resolved: US1 AS3 + Edge Cases "GPU prerequisites missing" + SC-007.
- [x] CHK034 Are requirements specified for the **exception** flow: engine init succeeds but rasterization or inference fails on doc N? [Coverage, Spec §Edge Cases bullet 3 + Q5] — Resolved: Edge Cases bullet 3 + clarification Q5 + FR-016.
- [x] CHK035 Are requirements specified for the **recovery** flow: one corpus document fails, the run continues with subsequent documents on the same engine? [Coverage, Spec §US2 AS3 + §Edge Cases bullet 4] — Resolved: US2 AS3 + Edge Cases bullet 4.
- [x] CHK036 Are requirements specified for the **defensive** flow: a request to bind PPStructureV3 to a different device after engine is bound? [Coverage, Spec §FR-006 + §Edge Cases bullet 1] — Resolved: FR-006 + Edge Cases bullet 1 + CF4 module invariant.
- [x] CHK037 Are requirements specified for the **CPU/stub** flow: CPU profile or stub adapter on a GPU-less host? [Coverage, Spec §US4 + §FR-017–FR-019] — Resolved: US4 with three acceptance scenarios + FR-017–FR-019.

## Edge Case Coverage

- [x] CHK038 Is per-page inference timing behavior specified for **multi-page documents where one page fails mid-inference** (i.e., is `per_page_inference` truncated, gapped, or marked)? [Edge Case, Spec §Edge Cases bullet 6 + R-015.5] — Resolved: Edge Cases bullet 6 + R-015.5 + `contracts/run-summary-schema.md` "Pages whose rasterization or inference failed before timing could be captured are absent (the consumer can detect a gap by comparing to `preprocess_output.json` page list)." Failed-mid-inference test in T020.
- [x] CHK039 Is the `total_seconds` semantic specified when total runtime is dominated by the one-time GPU phases on doc 1 vs. when it is dominated by per-page inference on doc N? [Edge Case, Gap] — Resolved by extending FR-013 "Total preprocess time" entry with explicit scope: includes one-time GPU phases on the first successfully processed doc only; on subsequent docs covers per-document phases only; therefore not equal to the sum of named child phases on doc 1.
- [x] CHK040 Are requirements specified for **process termination mid-run** (SIGINT / OOM): is partial run_summary emission required, expected, or undefined? [Edge Case, Gap] — **Out of scope for feature 015**: current behavior is "may or may not emit depending on signal handler"; this feature does not redefine signal semantics. If a future feature requires reliable partial emission, that feature amends the spec.
- [x] CHK041 Are requirements specified for the case where `paddle.is_compiled_with_rocm()` introspection raises (R-014.7 conservative-CPU fallback): does the fail-fast path still meet SC-007's 10 s budget? [Edge Case, Spec §SC-007] — Resolved: existing R-014.7 (carried over from feature 014) treats introspection raises as conservative `PADDLE_CPU_ONLY` and exits the classify ladder immediately — well under the 10 s budget. The path is regression-tested by T035.

## Non-Functional Requirements (bounded to SC-007 + "no latency target")

- [x] CHK042 Is the absence of a numeric latency target stated as a positive non-requirement (not just an omission), so future readers don't infer one from the ~103 s reference? [NFR, Spec §Assumption 1 + Constitution §Stage 1] — Resolved: spec Assumption 1 ("commits to making latency observable and removing duplicated init, not to a specific numeric latency target") + Constitution Stage 1 Scope ("no latency target as a release gate") are both positive statements.
- [x] CHK043 Is SC-007's 10 s budget the **only** numeric latency NFR in this feature, and is its scope (failure path only) explicit? [NFR Clarity, Spec §SC-007] — Resolved: SC-007's text scopes itself to "GPU prerequisites are missing or Paddle cannot bind"; no other SC carries a numeric latency. Spec Assumption 1 + Constitution combine to make this the single explicit numeric latency NFR.
- [x] CHK044 Are observability NFRs (e.g., human-readability of run_summary line, structured-log compatibility) stated as requirements or left implicit? [NFR Coverage, Gap] — **Deferred (acceptable)**: existing `--pretty-stdout` flag covers human readability for diagnostic use; structured-log compatibility is implicit in the JSONL line format (one JSON object per line) which feature 011/014 established. No new NFR needed.

## Dependencies & Assumptions

- [x] CHK045 Is the assumption "Existing run metadata / run summary surfaces accept additive phase-timing fields without requiring schema or contract-set changes" validated against feature 014's actual run_summary schema (0.1.1) rather than left as an unverified assertion? [Assumption, Spec §Assumption 2] — Resolved: feature 014 already added `preprocess_lane`, `gpu_init_seconds`, `gpu_inference_seconds`, `gpu_lane_forced_abort` additively at the same SCHEMA_VERSION 0.1.0 → 0.1.1 boundary; that establishes the precedent that additivity works on this surface.
- [x] CHK046 Is the dependency on `paddlepaddle-dcu` workstation-only install path documented as a non-CI prerequisite (so CI exclusion doesn't surprise) and consistent with feature 014's R-014 decisions? [Dependency, Spec §Assumption 4] — Resolved: spec Assumption 4 + plan §Technical Context both explicitly mark the wheel as "workstation-only optional install, already proven in feature 014."
- [x] CHK047 Is the dependency on `time.perf_counter()` monotonic-clock semantics stated as a portable Python stdlib guarantee (not platform-conditional)? [Dependency, Plan §Technical Context + R-015.4] — Resolved: `time.perf_counter()` / `time.perf_counter_ns()` is CPython stdlib (PEP 564), monotonic on all supported platforms. Plan and research both name it; spec Definitions block reaffirms the precision rule.
- [x] CHK048 Is the dependency on the existing CF4 single-device-per-process invariant from feature 014 explicit, with a forward reference (so a future feature touching it knows what breaks)? [Dependency, Data-model §CF4] — Resolved: `data-model.md` and `contracts/module-invariants.md` both list CF4 explicitly with the "Existing — pre-feature-015 tests, unchanged" attribution; the new CF5 invariant is documented to coexist with CF4, making the dependency forward-traceable.

## Ambiguities & Conflicts

- [x] CHK049 The User Story 3 acceptance scenario 4 says phase timing "travels through existing run metadata or run summary channels in an additive way only" while FR-014 (post-clarification) pins it to the run_summary stdout line specifically — is this softer earlier wording acceptable, or should it be tightened to match FR-014? [Conflict, Spec §US3 AS4 vs §FR-014] — Resolved by tightening US3 AS4 to reference `kind: "run_summary"` per FR-014.
- [x] CHK050 Is the term "preprocess profile" used consistently across `ppstructurev3@gpu` (slug form), `preprocess_lane: "gpu0"` (run_summary form), and `device="gpu:0"` (Paddle form), with the mapping documented in one place? [Ambiguity, Spec §FR-009 + Plan] — Resolved by adding the "Preprocess profile terminology mapping" table to `spec.md §Definitions`.
- [x] CHK051 Does the spec's explicit "warmup is a reserved phase only" (Q2) conflict with FR-013's positional inclusion of warmup in the FR-013 phase list? Is the wording "reserved-but-listed" unambiguous? [Ambiguity, Spec §FR-013 vs §Clarification Q2] — Resolved: FR-013's warmup line now reads "Optional MIOpen/COMGR warmup (reserved phase only — feature 015 does not introduce a synthetic warmup pass; surfaced only if some other code path actually performs warmup, otherwise omitted per FR-016)." The "reserved-but-listed" intent is unambiguous.
- [x] CHK052 Are requirements resolved for the case where a future feature implements warmup, and that future feature's compatibility with this feature's "warmup omitted by default" rule is preserved? [Forward compatibility, Gap] — **Deferred (acceptable)**: a future feature that implements warmup must amend FR-012 to remove the "synthetic warmup pass out of scope" line and amend FR-013 to drop the "reserved phase only" qualifier. The currently-emitted shape (`warmup` key absent unless performed) is forward-compatible with that future amendment because consumers built against 0.1.2 already tolerate `warmup` being either absent or present per FR-016.

## Notes

- Items prefixed with `[Spec §X]` reference an existing requirement; items with `[Gap]`, `[Ambiguity]`, `[Conflict]`, or `[Assumption]` flag missing or unstable language.
- ≥80% traceability target: 50/52 items (96%) carry an explicit `[Spec §…]` / `[Plan]` / `[Constitution]` / `[Contracts]` / `[Data-model]` / `[Gap]` / `[Conflict]` reference. **Achieved.**
- All 52 items now resolved or consciously deferred with rationale captured in-line.
- Lingering deferred items (CHK010, CHK040, CHK044, CHK052) are explicitly out-of-scope for feature 015 and do NOT block `/speckit.implement`.

## Resolution Log (chronological)

### Round 1 — post-`/speckit.analyze` cleanup (2026-05-07)

Resolved 9 items via the analyze remediation pass:

- CHK001 / CHK002 / CHK018 (D1) — single-source-of-truth notes added to research.md, data-model.md, contracts/run-summary-schema.md.
- CHK006 (A1) — "Construct PPStructureV3" definition added to spec.md.
- CHK009 (A2) — "one process / same process" definition added to spec.md.
- CHK015 (A3) — "Phase timing precision" definition added to spec.md.
- CHK022 (K1) — QG#2 inapplicability justified in plan.md.
- CHK029 (A4) — SC-007 measurement boundary pinned.
- CHK049 (C1) — US3 AS4 tightened to reference `kind: "run_summary"`.

### Round 2 — 52-item resolution pass (2026-05-07)

Resolved the remaining 43 items:

- **6 items required new spec edits**:
  - CHK011 — added "(within the SC-007 ≤ 10 s budget)" to FR-007 + Edge Cases bullet.
  - CHK012 — added concrete additive-only rule (no rename, no removal, no type change, patch-version-only bump) to FR-014.
  - CHK016 — tightened FR-015 to "first successfully processed per-document entry" with explicit failed-doc fallthrough.
  - CHK017 — tightened FR-014 to cover both single-doc CLI and warm-corpus driver emission sites.
  - CHK021 — added explicit legacy-flat-keys preservation sentence to FR-014.
  - CHK039 — tightened FR-013 "Total preprocess time" with explicit per-doc scope semantics.
  - CHK050 — added "Preprocess profile terminology mapping" table to spec.md §Definitions.
- **33 items already adequately stated** in the source artifacts (verified by inspection): CHK003, CHK004, CHK005, CHK007, CHK008, CHK013, CHK014, CHK019, CHK020, CHK023–CHK028, CHK030–CHK038, CHK041–CHK043, CHK045–CHK048, CHK051.
- **4 items consciously deferred** with rationale captured in-line: CHK010 (multi-invocation daemon — out of scope), CHK040 (SIGINT/OOM partial emission — out of scope), CHK044 (extra observability NFRs — covered by `--pretty-stdout`), CHK052 (forward-compat for future warmup — currently-emitted shape is already forward-compatible).
