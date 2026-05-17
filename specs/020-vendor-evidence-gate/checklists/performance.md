# Performance Checklist: Deterministic Vendor-Identity Signals And Early Accept Gate

**Purpose**: Release-gate validation that the spec defines performance-relevant
requirements with the rigor needed for a feature whose only behavioral
surface (FR-007 skip-fallback) is a latency-harvest mechanism, under the
constitution's "no latency target as a release gate" constraint. Items
focus on: measurability of the latency-harvest claim, per-document gate
evaluation count bounds, regression-detection for CPU/GPU lanes, benchmark
fixture stability, resource cost (compile-once regex, no persisted
artifact), cross-feature comparability with features 017/018/019, and
explicit non-regression guarantees against prior-feature timing surfaces.
Every item validates the **requirements**, not the implementation.
**Created**: 2026-05-16
**Feature**: [spec.md](../spec.md)
**Depth**: Release gate
**Audience**: Reviewer (PR + performance / benchmark owner)

## Constitutional Constraint on Latency Targets

- [x] CHK001 Is the constitutional rule "no latency target as a release gate" (Stage 1 Scope Constraints) explicitly carried forward in this feature's spec/plan, so a reviewer does not expect a hard numeric SLA? [Clarity, Plan §Performance Goals / Constitution §Stage 1 Scope Constraints]
- [x] CHK002 Is the rule "no numeric latency target" stated explicitly in `plan.md § Performance Goals`, rather than implied by silence? [Clarity, Plan §Performance Goals]
- [x] CHK003 Does the spec distinguish between "latency-harvest as a measurable outcome" (acceptable per FR-015) and "latency-harvest as a release gate" (forbidden per constitution) — so a future maintainer cannot smuggle a hard SLA in under the FR-015 banner? [Clarity, Spec §FR-015 §US4 §Why this priority / Plan §Performance Goals]

## Measurability of the Latency-Harvest Outcome

- [x] CHK004 Is the FR-015 measurability outcome stated as a concrete observable (`evidence_gate_suppressed_fallback_count >= 1` on the benchmark for at least one fixture with opt-in active + `sufficient` decision), rather than as a qualitative claim? [Measurability, Plan §Performance Goals / Spec §FR-015]
- [x] CHK005 Are the four FR-015 benchmark observables enumerated by name ((a) per-document signal values, (b) per-document gate decision, (c) per-corpus state distribution, (d) per-corpus latency-or-quality delta vs. legacy)? [Completeness, Spec §FR-015]
- [x] CHK006 Is the rule "the FR-015 benchmark records BOTH latency AND quality deltas, never just one" stated so an asymmetric record (latency improved but quality silently regressed) is forbidden? [Clarity, Spec §FR-015]
- [x] CHK007 Does the spec define which `phase_timings.*` keys (`per_page_inference`, `total`, `paddle_import`, `engine_init`, `rasterization`, `artifact_write`, `warmup`) are expected to change vs. stay constant when skip-fallback fires? [Gap, R-020.7]
- [x] CHK008 Is the rule "latency-harvest evidence lives in `quickstart.md` Appendix A at landing time" stated so the audit trail for the measurement has a pinned home? [Clarity, Plan §Storage / R-020.13]
- [x] CHK009 Does the spec define how operators read the latency-harvest from `run_summary` ALONE (without re-running the binary), so the operator-facing observability is self-sufficient? [Clarity, Spec §US3 AC#4 / R-020.10]

## Per-Document Gate Evaluation Count Bound

- [x] CHK010 Is the rule "the gate evaluates at most TWICE per document" stated as a hard bound, with the five evaluation-count cases enumerated by configuration? [Clarity, R-020.7 §Per-document evaluation count]
- [x] CHK011 Is the rule "non-OCR-only runs and OCR-only runs without opt-in evaluate the gate EXACTLY ONCE per document" stated so the common path's cost is bounded to one evaluation? [Clarity, R-020.7]
- [x] CHK012 Is the rule "when the suppression predicate returns True, the gate evaluates EXACTLY ONCE per document (on the candidate, which becomes the final)" stated so the successful-suppression case does NOT pay double-evaluation cost? [Clarity, R-020.7 / module-invariants.md MI-12]
- [x] CHK013 Is the rule "the two-evaluation case (candidate + post-fallback) only fires when fallback fires AND the candidate decision was non-sufficient" stated as the unique condition under which two evaluations occur? [Clarity, R-020.7 / module-invariants.md MI-11]
- [x] CHK014 Does the spec quantify the gate evaluation's cost order (linear in `pages[0]` token count of `preprocess_output.json`; constant per token via compiled regex)? [Gap, R-020.3]

## Always-Emit Cost / Stub-Adapter Overhead

- [x] CHK015 Is the rule "the gate runs on stub-adapter runs and CPU runs uniformly" stated, with the per-document cost characterization (pure-Python work over `pages[0]`) documented so the always-emit overhead is auditable? [Clarity, Spec §FR-014 / R-020.3]
- [x] CHK016 Does the spec define the cost of emitting the four new `run_summary` fields when no documents reached the gate (e.g., empty corpus → only the always-emit defaults are serialized, cost O(1))? [Clarity, R-020.10]
- [x] CHK017 Is the rule "the four new `run_summary` fields are emitted in deterministic order without sorting or extra serialization passes" stated so the per-run emission overhead is constant relative to feature 019's run_summary? [Clarity, R-020.10 / run-summary-schema.md §Order of keys]

## Resource Cost (Compile-Once Regex, Memory, No Sidecar)

- [x] CHK018 Is the rule "the three regex patterns compile ONCE at module load (not per evaluation)" stated so per-document compile overhead is forbidden? [Clarity, data-model.md §6 / module-invariants.md MI-8]
- [x] CHK019 Is the rule "`VENDOR_NAME_STOP_WORDS` is a module-level `frozenset` (O(1) membership), not a list (O(n))" stated as a performance constraint? [Clarity, data-model.md §8]
- [x] CHK020 Is the rule "no in-process mutable globals; no per-call cache" stated so memory does not grow with run length? [Clarity, data-model.md §10]
- [x] CHK021 Is the rule "no new persisted artifact" stated as a I/O-cost constraint (no per-document file write, no sidecar JSON)? [Clarity, Spec §FR-021 / contract.md CHK044]
- [x] CHK022 Does the spec define the memory cost characterization of `evidence_gate_documents` accumulation across a corpus run (one dict per document — linear in corpus size; documents the worst-case for a 20-doc stage-1 corpus and the future-corpus-growth boundary)? [Gap, R-020.10 / R-020.11]

## CPU-Lane Non-Regression

- [x] CHK023 Is the rule "CPU profile and stub adapter performance MUST NOT regress against the pre-feature-020 baseline beyond the cost of the gate's pure-Python work on `pages[0]`" stated so a future hidden Paddle import or hidden GPU probe is caught as a regression? [Clarity, Spec §FR-022 §SC-009 / Plan §Performance Goals]
- [x] CHK024 Is the rule "T060 CPU regression baseline (T002 + T060) anchors CPU non-regression" stated as the enforcement mechanism? [Measurability, tasks.md T002 / T060]
- [x] CHK025 Does the spec define whether CPU evaluation latency is part of the regression baseline, or only correctness (e.g., test-pass count) — i.e., is there an acceptable CPU latency band, or only "tests pass"? [Gap]

## GPU-Lane Non-Regression

- [x] CHK026 Is the rule "feature 015's `engine_init` / `paddle_import` / `gpu_bind_probe` timing surfaces are unchanged" stated as carry-forward? [Consistency, Spec §FR-022 §SC-009]
- [x] CHK027 Is the rule "PPStructureV3 constructed exactly once per process when invoked (feature 015 FR-001)" carried forward without weakening? [Consistency, Spec §FR-022 §SC-009 / Plan §Constitution Check row V]
- [x] CHK028 Is the rule "GPU readiness probed at most once per process (feature 015 FR-004)" carried forward without weakening? [Consistency, Spec §FR-022 §SC-009]
- [x] CHK029 Is the rule "single-device-per-process guard (feature 015 FR-006)" carried forward? [Consistency, Spec §FR-022 §SC-009]
- [x] CHK030 Is the rule "warmup behavior unchanged (feature 016 FR-001 through FR-020)" carried forward? [Consistency, Spec §FR-022 §SC-009]
- [x] CHK031 Does the spec define how the skip-fallback latency-harvest interacts with feature 016's `phase_timings.warmup` semantics (e.g., does suppressing fallback also suppress a PPStructureV3 warmup cost for that document, or does warmup amortize once per process regardless)? [Gap, R-020.7]

## Feature 017/018/019 Timing-Surface Preservation

- [x] CHK032 Is the rule "`module_set_id` / `det_rec_variant_id` / `ppstructure_modules_invoked` semantics unchanged (feature 017 FR-001 / FR-008 / FR-010)" carried forward as a perf-surface invariant? [Consistency, Spec §FR-022 §SC-009]
- [x] CHK033 Is the rule "`raster_profile_id` / `region_strategy_id` / `region_strategy_fallback_count` semantics unchanged (feature 018 FR-008 / FR-009 / FR-011)" carried forward? [Consistency, Spec §FR-022 §SC-009]
- [x] CHK034 Is the rule "`preprocess_strategy_id` / `ocr_only_fallback_count` semantics unchanged (feature 019 FR-005 / FR-008)" carried forward? [Consistency, Spec §FR-022 §SC-009]
- [x] CHK035 Is the rule "no `phase_timings.evidence_gate` or any nested `phase_timings` key for gate timing" stated so feature 015/016's timing schema is not silently mutated? [Clarity, contract.md CHK042 / run-summary-schema.md §Forbidden]
- [x] CHK036 Does the spec define why the gate is NOT separately timed in `phase_timings` (rationale: "cheap pure-Python work; not separately timed in this feature") — so a future "add per-doc gate timing" change is auditable as a scope expansion? [Clarity, run-summary-schema.md §Forbidden]

## Benchmark Stability and Cross-Feature Comparability

- [x] CHK037 Is the FR-015 benchmark subset pinned to the same fixed 5-doc subset features 017/018/019 used, so per-feature latency-harvest comparison is meaningful? [Clarity, R-020.13 / Spec §FR-015]
- [x] CHK038 Is the lookup procedure for the 5-doc subset documented (T053 three-step lookup procedure), so subset drift between features is detectable? [Clarity, tasks.md T053]
- [x] CHK039 Is the rule "benchmark numbers land in `quickstart.md` Appendix A at landing time" stated so the per-feature benchmark history has a pinned location? [Clarity, Plan §Storage / R-020.13]
- [x] CHK040 Does the spec define what counts as a "meaningful" latency-harvest delta on the benchmark — i.e., does a 5ms improvement count, or is there an implicit "noise floor" below which the harvest is considered zero? [Gap]
- [x] CHK041 Is the rule "two runs of the same configuration on the same input produce identical `run_summary` field values" stated so benchmark reruns are deterministic and a single-run measurement is reliable? [Clarity, Spec §SC-003]
- [x] CHK042 Does the spec define the warm-vs-cold run discipline for benchmark measurement (i.e., is the latency-harvest measured on a cold-cache run, a warm-cache run, or both — feature 016 `phase_timings.warmup` distinguishes them)? [Gap, R-020.13 / feature 016 carry-forward]

## Promotion Gate Performance Discipline

- [x] CHK043 Is the rule "promotion of the skip-fallback default requires BOTH metrics (aggregate score AND pass count) to be `>=` legacy" stated so a perf-improving but quality-regressing candidate cannot be promoted? [Clarity, Spec §FR-016 §SC-008 / R-020.14]
- [x] CHK044 Is the rule "no perf-only metric is introduced by this feature" stated so the quality gate cannot be substituted with a pure-latency promotion criterion? [Clarity, R-020.14 §Alternatives considered]
- [x] CHK045 Does the spec define whether GPU vs CPU benchmark numbers are recorded independently (since FR-007 shape (b) is GPU-only), or whether CPU numbers are recorded but explicitly noted as "skip-fallback inactive on CPU"? [Gap, R-020.13 / Spec §FR-012]

## Regression Detection and Drift Surveillance

- [x] CHK046 Is the rule "absence of any of the four new `run_summary` fields on a run of the new binary is a regression signal" stated so a regression that silently disables the gate is detectable? [Clarity, Spec §SC-003 / module-invariants.md MI-16]
- [x] CHK047 Is the rule "two runs of the same configuration on the same input produce byte-identical `run_summary` values for all gate fields" stated so a non-determinism leak (which would also be a perf-variance leak) is detectable? [Clarity, Spec §SC-003 / module-invariants.md MI-6]
- [x] CHK048 Does the spec define how a regression in `evidence_gate_suppressed_fallback_count` would be detected over time (e.g., counter unexpectedly stays at 0 after a code change that should preserve the suppression path)? [Gap]
- [x] CHK049 Is the rule "benchmark candidate's metrics are recorded alongside the legacy candidate's metrics on the same 5-doc subset" stated so a perf regression in the candidate is directly comparable? [Clarity, Spec §FR-015 / R-020.13]

## Failure-Mode Performance

- [x] CHK050 Does the spec define the latency impact of the warn-and-proceed path (T043) on CPU runs — is it bounded to one stderr line write, or could it cascade? [Clarity, R-020.12 / module-invariants.md MI-22]
- [x] CHK051 Does the spec define what happens to `phase_timings.total` when fallback fires AND the gate evaluates twice — does the second gate evaluation get included in `total`, or is it amortized into preprocessing's per-strategy timing? [Gap, R-020.7]
- [x] CHK052 Is the rule "GPU bind failure under engaged behavioral shape MUST fail fast (no silent CPU fallback)" stated so a latency-degradation regression cannot hide behind a silent profile switch? [Consistency, Spec §Edge Cases / Spec §FR-022 §SC-009]

## Verifiability of Performance Claims

- [x] CHK053 For every performance claim (at-most-twice evaluation, compile-once regex, always-emit cost is constant, byte-identical reruns, latency-harvest is measurable), is there a named test, benchmark, or audit task that establishes it? [Measurability, tasks.md T053 / T060 / module-invariants.md MI-6]
- [x] CHK054 Is the benchmark task (T053) named as the single source of truth for latency-harvest numbers, with `quickstart.md` Appendix A as the persistence location? [Measurability, tasks.md T053 / Plan §Storage]
- [x] CHK055 Does the spec name a CPU-safe regression test that asserts the legacy non-opt-in run produces a byte-identical `preprocess_output.json` to the pre-feature-020 baseline (T048), so any CPU-side latency surprise is paired with a behavioral surprise that's caught? [Measurability, tasks.md T048]
- [x] CHK056 Is the rule "GPU performance verification is deferrable per R-020.15 without blocking CPU merge" stated as a scoping decision, NOT as a perf-blind-spot? [Clarity, Spec §FR-026 / R-020.15]

## Notes

- Check items off as completed: `[x]`
- Add comments or findings inline; reference the spec/plan/research/data-model/contract line when raising a defect
- This checklist tests **requirements quality** in the performance domain, not implementation correctness
- Performance items here are scoped to the constitution's "no latency target as a release gate" rule — checks focus on measurability, non-regression, and operator observability rather than on hitting specific SLA numbers
- Several items will surface as `[Gap]` because performance language is intentionally light per the constitutional constraint; for each `[Gap]`, the reviewer should decide whether to add explicit "intentionally unspecified" text to spec/plan or accept the silence
