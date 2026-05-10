# Scope Checklist: PPStructureV3 Module And Model Reduction

**Purpose**: Validate that requirements covering the in-scope deliverables (US1–US6), the Out of Scope subsection, the boundaries with features 014/015/016 (preserved invariants), the boundaries with features 018/019 (reserved features), CPU-default-change discipline, persisted-artifact discipline, corpus-baseline immutability, promotion-gate scope, and FR-024 deferral scope are complete, clear, and consistent. This is a release-gate checklist.
**Created**: 2026-05-09
**Feature**: [spec.md](../spec.md)
**Marker convention**: `[Gap]` = a missing requirement that should be filled. `[Deferred]` = a landing-time observation tracked under FR-024 (GPU-verification deferral) — visible but not failing the gate.

## In-Scope Deliverables (US1–US6)

- [x] CHK001 - Are US1's deliverables precisely named (live-path module audit narrative + `reduced-v1` preset on `ppstructurev3@gpu`) so reviewers can identify scope creep? [Completeness, Spec §US1, FR-001, FR-002]
- [x] CHK002 - Are US2's deliverables precisely scoped (≥2 lighter detection/recognition variants benchmarked + per-document `phase_timings.*` + vendor-identity quality numbers in research artifact)? [Clarity, Spec §US2, FR-005, FR-016]
- [x] CHK003 - Are US3's deliverables (configuration identifier on `run_summary`) bounded as the additive-only landing of three new top-level fields (`module_set_id`, `det_rec_variant_id`, `ppstructure_modules_invoked`)? [Clarity, Spec §US3, FR-008, FR-010]
- [x] CHK004 - Are US4's deliverables (CPU/CI-without-GPU non-regression) framed as protective (no-change) rather than additive, so US4 cannot be expanded mid-implementation into a CPU-side optimization? [Clarity, Spec §US4]
- [x] CHK005 - Are US5's deliverables (downstream-contract preservation: 004/005/008/009 stages accept new GPU outputs unmodified) traceable to FR-019 / FR-021 / SC-007 / SC-010? [Traceability, Spec §US5]
- [x] CHK006 - Are US6's deliverables (quality-gate guard before any GPU default change) gated on the two-metric Clarifications Q1 result (aggregate field score AND per-document pass count, both ≥ legacy on the same subset)? [Consistency, Spec §US6, FR-015, Clarifications session 2026-05-09]
- [x] CHK007 - Is the priority ranking (P1/P2/P3) of the six user stories explicit and consistent with Spec text so reviewers can flag a P3 deliverable being treated as mandatory or vice versa? [Consistency, Spec §US1–US6]

## Out of Scope Subsection Completeness

- [x] CHK008 - Is the DPI-reduction / region-first / header-first reservation for feature 018 explicitly listed in the Out of Scope subsection? [Completeness, Spec §Out of Scope, FR-025]
- [x] CHK009 - Is the OCR-only fast lane (skip layout entirely) reservation for feature 019 explicitly listed? [Completeness, Spec §Out of Scope, FR-026]
- [x] CHK010 - Is the "no CPU-side default change" boundary explicitly listed? [Completeness, Spec §Out of Scope]
- [x] CHK011 - Is the "no new persisted benchmark artifact at landing (default position)" boundary explicit, with the FR-020 escape hatch precisely conditioned on `/speckit.clarify` or `/speckit.plan` evidence that `run_summary` + harness/evaluator outputs are insufficient? [Completeness, Spec §Out of Scope, FR-020]
- [x] CHK012 - Is the "no committed corpus baseline regeneration" boundary explicit and channelled through `docs/stage1-vendor-identity/dataset-layout.md` + `labeling-guide.md`, NOT through this feature's PR? [Completeness, Spec §Out of Scope, FR-018]
- [x] CHK013 - Is the "no `schema_version` / four canonical artifact change" boundary explicit and consistent with FR-019 / SC-010? [Completeness, Spec §Out of Scope]
- [x] CHK014 - Is the FR-020 escape hatch's required deliverables (data-model.md + research.md + AMENDMENTS update) enumerated so a future scope expansion does not silently skip them? [Clarity, Spec §FR-020]

## Boundary With Features 014 / 015 / 016 (Preserved)

- [x] CHK015 - Is "all feature 014 / 015 / 016 guarantees continue to hold" reasserted in FR-021 and SC-009 with the named guarantees enumerated by FR-number reference? [Completeness, Spec §FR-021, SC-009]
- [x] CHK016 - Are the named guarantees (PPStructureV3 single-engine-per-process, GPU-readiness probed once, single-device guard, no silent CPU fallback, warmup behavior unchanged, `pipeline_version` ending in `.gpu0` / `.cpu0`) listed in FR-021 with traceable feature-15/16 references? [Traceability, Spec §FR-021]
- [x] CHK017 - Is the relationship to feature 016's `--gpu-warmup` explicit (orthogonal to this feature's `--module-set` / `--det-rec-variant` flags; can be combined freely on `ppstructurev3@gpu`)? [Consistency, Plan §Summary, contracts/cli-contract.md §1, R-017.1]
- [x] CHK018 - Is the relationship to feature 015's `phase_timings.*` shape explicit (no rename, removal, or retype of the eight existing keys)? [Consistency, Spec §Edge Cases, FR-009]
- [x] CHK019 - Is the relationship to feature 014's `--preprocess-profile` explicit (this feature's flags select within `ppstructurev3@gpu` orthogonally, not as a new profile)? [Consistency, R-017.1 alternatives]
- [x] CHK020 - Is the prohibition on collapsing this feature's flags into a profile-suffix syntax (e.g., `ppstructurev3@gpu+reduced+ppocrv5-mobile`) explicit, so a future refactor cannot silently merge them? [Clarity, R-017.1 alternatives]

## Boundary With Features 018 / 019 (Reserved)

- [x] CHK021 - Is feature 018's exclusive scope (rasterization DPI, region-first / header-first processing) precisely named in FR-025 so this feature cannot drift into it? [Clarity, Spec §FR-025]
- [x] CHK022 - Is feature 019's exclusive scope (OCR-only fast lane bypassing layout for vendor-identity-only paths) precisely named in FR-026? [Clarity, Spec §FR-026]
- [x] CHK023 - Are FR-025 and FR-026 reasserted in plan.md's Constraints section so reviewers reading the plan can flag scope creep? [Coverage, Plan §Technical Context Constraints]
- [x] CHK024 - Is the prohibition on adding a "lite layout detector" or "single-page invoice optimizer" disguised as a `module_set_id` preset explicit (i.e., is the closed `module_set_id` vocabulary `legacy` + `reduced-v1` only at landing, with future presets requiring a future feature)? [Clarity, R-017.2, /speckit.clarify Q4]

## CPU Lane Scope Discipline

- [x] CHK025 - Is "this feature is configuration-only on the runtime side and additive-only on the `run_summary` side" framed as a binding scope invariant covering the entire feature? [Clarity, Spec §Out of Scope]
- [x] CHK026 - Is the prohibition on importing GPU-only preset code from CPU/stub paths binding (FR-014), with a precisely-defined import-guarding mechanism deferred to plan? [Completeness, Spec §FR-014, R-017.6]
- [x] CHK027 - Is the warn-and-proceed pattern for CPU/stub + GPU-only flag fully enumerated as four required behaviors (warn + no module-disable + no model swap + same exit status)? [Coverage, Spec §FR-013, contracts/cli-contract.md §3]
- [x] CHK028 - Is the prohibition on the warn-and-proceed branch silently mutating any preprocess_output.json field (i.e., CPU/stub `preprocess_output.json` MUST be byte-identical with or without the GPU-only flags set) explicit? [Consistency, Spec §US4, FR-013]

## Persisted-Artifact Discipline

- [x] CHK029 - Is the prohibition on adding a new persisted artifact at landing explicit and consistent across FR-020, the Out of Scope subsection, Plan §Storage, and R-017.13? [Consistency]
- [x] CHK030 - Are the locations of the FR-001 audit narrative (research.md Appendix B) and FR-005 benchmark numbers (quickstart.md Appendix A) precisely named so a reviewer can verify the narratives land in those exact files? [Clarity, R-017.13]
- [x] CHK031 - Is the prohibition on landing the audit narrative or benchmark numbers as a new docs/stage1-vendor-identity/ page (which would be operator-facing reference, not landing-time evidence) explicit? [Clarity, R-017.13]
- [x] CHK032 - Is the prohibition on placing landing-time evidence in `contracts/stage1_vendor_identity/AMENDMENTS.md` explicit (since no canonical artifact contract changes)? [Consistency, FR-019, FR-020]

## Corpus Baseline Immutability Scope

- [x] CHK033 - Are committed corpus baselines under `tests/stage1_vendor_identity/*/` (including `preprocess_output.json`, `expected.json`, evaluator outputs) named off-limits to this feature's PR? [Completeness, Spec §FR-018, SC-006]
- [x] CHK034 - Is the legitimate channel for legitimate baseline regeneration (`docs/stage1-vendor-identity/dataset-layout.md` + `labeling-guide.md` flow) named so reviewers can identify off-channel changes? [Clarity, Spec §FR-018]
- [x] CHK035 - Is the verification mechanism for SC-006 (PR diff against `main` on baseline paths) executable as written, so a reviewer can run the check mechanically? [Measurability, Spec §SC-006]

## Promotion-Gate Scope

- [x] CHK036 - Is the gate's scope (offline release-gate procedure, NOT a runtime check inside the pipeline) explicit so a future implementer does not wire the gate into routing or assembly logic? [Clarity, R-017.10]
- [x] CHK037 - Is the gate's metric source (existing evaluator outputs only — `evaluation_run_summary.json` aggregate field score + per-document pass count from `docs/stage1-vendor-identity/scoring.md`; no new metric introduced) explicit? [Completeness, FR-015, R-017.10]
- [x] CHK038 - Is the gate's same-corpus-subset rule explicit (the same fixed 5-doc subset measured under legacy is the comparison base for every candidate)? [Completeness, FR-015, R-017.11]
- [x] CHK039 - Is the gate-failure-rejects-promotion outcome explicit (legacy default remains; candidate stays opt-in only) and consistent across FR-015, FR-017, US6, and SC-008? [Consistency]
- [x] CHK040 - Is the candidate-stays-selectable-on-gate-failure outcome explicit and traceable to FR-017 (legacy AND non-promoted candidates BOTH remain selectable via explicit configuration)? [Clarity, FR-017]

## FR-024 Deferral Scope Discipline

- [x] CHK041 - Is the FR-024 GPU-verification deferral scope precisely listed (which FR-numbers are deferrable: FR-001 audit, FR-005 benchmark, FR-008-related GPU `run_summary` checks, FR-015 promotion gate, plus the GPU-marked test categories from FR-022)? [Coverage, Spec §FR-024]
- [x] CHK042 - Is "deferral does not block CPU-safe implementation merge" explicit so a reviewer does not block the PR on missing GPU verification? [Clarity, Spec §FR-024]
- [x] CHK043 - Is the prohibition on "quietly skipping deferred verification" explicit (deferred items MUST be captured in `tasks.md` and `quickstart.md` Appendix A so the verification cannot vanish from the audit trail)? [Completeness, Spec §FR-024]
- [x] CHK044 - Is the relationship to feature 016's FR-014 (deferral precedent for `--gpu-warmup` SC-003 cold-vs-warm verification) explicit, so this feature's deferral inherits the same anti-skip discipline rather than inventing a new one? [Traceability, Spec §FR-024]

## Landing-Time Scope Observations [Deferred under FR-024]

- [x] CHK045 - Are the actual sub-modules invoked by `legacy` and `reduced-v1` recorded in research.md Appendix B at landing time, so the spec's "candidate set" in Assumptions ("table, formula, chart, document orientation, seal — to be confirmed by the FR-001 audit") is reconciled with reality? [Deferred, Spec §Assumptions, R-017.7, research.md Appendix B]
- [x] CHK046 - Is the actual promotion decision at landing (keep legacy default OR promote a specific `module_set_id` × `det_rec_variant_id` candidate) recorded in quickstart.md Appendix A.3, with the two-metric evidence supporting the decision? [Deferred, R-017.10, FR-015, quickstart.md Appendix A.3]
- [x] CHK047 - Are the exact medium-difficulty and hard-difficulty corpus document names confirmed at landing (provisional `inv_007_medium`, `inv_015_hard`, `inv_018_hard` in R-017.11) and pinned in `tests/pipeline/test_det_rec_variant_benchmark.py`'s parameterization? [Deferred, R-017.11]
