# Cross-Artifact Traceability Checklist: GPU MVP Promotion

**Purpose**: Validate that traceability across the feature's nine-artifact set (spec ↔ plan ↔ clarifications ↔ research ↔ data-model ↔ contracts ↔ checklists ↔ quickstart ↔ feature-020 appendices) is written with enough density and stability that a reviewer can trace any FR / SC / R-decision / CHK item to its supporting and dependent artifacts without ambiguity.
**Created**: 2026-05-18
**Feature**: [spec.md](../spec.md), [plan.md](../plan.md), [research.md](../research.md), [data-model.md](../data-model.md), [contracts/](../contracts/), [quickstart.md](../quickstart.md), [checklists/](.)

This checklist tests the *writing quality of traceability* — whether each artifact properly cross-references upstream (what it depends on) and downstream (what depends on it) artifacts.

## Spec ↔ Plan Traceability

- [X] CHK001 Is every FR (FR-001 through FR-033) in the spec referenced by at least one section in `plan.md` (Technical Context, Project Structure, or Constitution Check)? [Traceability, Spec §Functional Requirements, plan.md]
- [X] CHK002 Is every SC (SC-001 through SC-011) in the spec implicitly satisfied by a plan section (acceptance bar in Constitution Check or Phase 1 design)? [Traceability, Spec §Success Criteria, plan.md]
- [X] CHK003 Does plan.md's Summary section accurately reproduce the spec's six deliverables (readiness helper, GPU test conversions, Appendix A, Appendix B, runbook, promotion decision)? [Consistency, plan.md §Summary, Spec §User Stories]
- [X] CHK004 Are all six US priorities (P1 → P3) reflected in plan.md's implementation-order discussion? [Consistency, plan.md, Spec §User Scenarios]
- [X] CHK005 Does plan.md's Project Structure section name the actual source/test/doc paths that the spec FRs imply? [Consistency, plan.md §Project Structure]

## Spec ↔ Clarifications ↔ Research Traceability

- [X] CHK006 Are the five Clarifications session bullets (Q1 jitter, Q2 Ollama check, Q3 interpreter, Q4 extraction lane, Q5 model id) each tied to at least one FR amendment in the same Clarifications-driven edit? [Traceability, Spec §Clarifications, §FR-002, §FR-003, §FR-015, §FR-025]
- [X] CHK007 Are the 13 R-021 decisions in `research.md` each tied to either a spec FR or a checklist `[Gap]` item that motivated them? [Traceability, research.md]
- [X] CHK008 Does research.md's "Affected requirements" line on each decision name actual spec FRs / SCs / scenarios, not paraphrases? [Consistency, research.md]
- [X] CHK009 Are the Clarifications-resolved ambiguities (Q1–Q5) treated as PERMANENTLY resolved — no R-021 decision reopens or contradicts a Clarifications answer? [Consistency, research.md, Spec §Clarifications]

## Spec ↔ Data-Model Traceability

- [X] CHK010 Are the six entities in `data-model.md` (GPU Readiness Verdict, Benchmark Run Record, Jitter Band, Quality-Gate Verdict, Promotion Decision Record, Ollama Readiness Probe Result) each tied to the spec's §Key Entities or to an R-021 decision? [Traceability, data-model.md, Spec §Key Entities]
- [X] CHK011 Do the data-model entity shapes preserve every field the spec's §Key Entities enumerates (no field silently dropped)? [Completeness, data-model.md, Spec §Key Entities]
- [X] CHK012 Do the data-model validation rules ("MUST", "MUST NOT") cross-link to the FR or SC that motivates them? [Traceability, data-model.md]
- [X] CHK013 Are entity state-transitions stated explicitly (entity is immutable / re-runnable / history-preserving)? [Clarity, data-model.md]

## Spec ↔ Contracts Traceability

- [X] CHK014 Does each of the four `contracts/*.md` files declare its primary spec FRs in its header? [Traceability, contracts/]
- [X] CHK015 Are the contracts' Constitution refs (§I, §III, §V as relevant) named at their headers? [Traceability, contracts/]
- [X] CHK016 Does `contracts/ollama-readiness-helper.md` trace back to FR-002, R-021.6, R-021.9, R-021.10 explicitly? [Traceability, contracts/ollama-readiness-helper.md]
- [X] CHK017 Does `contracts/gpu-test-marker.md` trace back to FR-006–FR-010, SC-004, R-021.8 explicitly? [Traceability, contracts/gpu-test-marker.md]
- [X] CHK018 Does `contracts/appendix-recording.md` trace back to FR-023, FR-024, SC-005, SC-007, SC-009, R-021.1, R-021.2, R-021.11, R-021.13 explicitly? [Traceability, contracts/appendix-recording.md]
- [X] CHK019 Does `contracts/runbook.md` trace back to FR-025 (all sub-clauses), SC-008, US5 (all scenarios), R-021.5, R-021.7 explicitly? [Traceability, contracts/runbook.md]

## Spec ↔ Checklists Traceability

- [X] CHK020 Does every checklist `[Spec §...]` reference resolve to a real spec section, FR, or SC (no dangling references)? [Traceability, checklists/]
- [X] CHK021 Does every checklist `[Gap]` item flag a genuinely missing requirement (one that the post-plan artifacts don't fully address)? [Accuracy, checklists/]
- [X] CHK022 Are the 13 R-021 decisions each acknowledged in the relevant checklists' Gaps to Flag sections (a checklist saying "no, this gap is now closed by R-021.X")? [Consistency, checklists/, research.md]
- [X] CHK023 Is the relationship between the existing eight checklists and the five new domain checklists (this file + determinism, contract, performance, security) non-overlapping at the item level? [Consistency, checklists/]

## Spec ↔ Quickstart Traceability

- [X] CHK024 Does quickstart.md's Path 1–6 structure trace to the six user-story priorities (P1 → P3)? [Consistency, quickstart.md, Spec §User Scenarios]
- [X] CHK025 Are the CLI flags named in quickstart.md (e.g., `--evidence-gate-skip-fallback`, `--output-dir`, `--preprocess-profile`, `--preprocess-strategy`, `--extract-profile`, `--documents-file`, `--gpu-warmup`) traceable to feature 011 / 014 / 019 / 020 CLI surfaces, with a caveat that they may need re-pinning if a future feature changes the CLI? [Traceability, Coverage, quickstart.md]
- [X] CHK026 Does quickstart.md cross-link every contract and the data-model where relevant? [Traceability, quickstart.md]

## Cross-Feature Traceability (021 → 014/015/016/017/018/019/020 + 005, 007)

- [X] CHK027 Are dependencies on features 014–019 (GPU lineage, ROCm/MIOpen, `phase_timings.*` keys) named in plan.md Technical Context and research.md? [Traceability, plan.md, research.md]
- [X] CHK028 Are dependencies on feature 020 (vendor evidence gate, `RunSummary.SCHEMA_VERSION = 0.1.7`, opt-in surface) named in plan.md Assumptions and research.md? [Traceability, plan.md, research.md, Spec §Assumptions]
- [X] CHK029 Is the dependency on feature 005 (voter config schema with `model_name: string`) named in R-021.7? [Traceability, research.md §R-021.7]
- [X] CHK030 Is the dependency on feature 007 (vendor-identity evaluator) named in research.md §R-021.13 with the field names actually consumed? [Traceability, research.md §R-021.13]
- [X] CHK031 Are the Appendix A and Appendix B targets in feature 020's `quickstart.md` named with a stable cross-reference (filename + section heading) so a future reorganization of feature 020's quickstart doesn't break this feature's traceability? [Traceability, contracts/appendix-recording.md]

## Constitution & Architecture Traceability

- [X] CHK032 Does plan.md's Constitution Check section name every Constitution principle (§I, §II, §III, §IV, §V) explicitly, with PASS/FAIL? [Completeness, plan.md §Constitution Check]
- [X] CHK033 Does plan.md's Constitution Check name all seven Quality Gates (QG #1–#7) explicitly with PASS/FAIL? [Completeness, plan.md §Constitution Check]
- [X] CHK034 Is the post-Phase-1 Constitution Check distinct from the pre-Phase-0 check (the spec calls for re-evaluation after design)? [Coverage, plan.md §Post-Phase-1 Re-evaluation]
- [X] CHK035 Is the consistency requirement against `architecture.md` (QG #7) explicit — does plan.md confirm no `architecture.md` change is required by this feature? [Traceability, plan.md, Constitution §Quality Gates]

## Forward Traceability (021 → future features)

- [X] CHK036 Are the items deferred to a future feature (over-time surveillance for `evidence_gate_suppressed_fallback_count`, `full-workstation` preset expansion, Jetson `edge-fast`) named with sufficient specificity for a future spec author to pick them up? [Traceability, Spec §Out of Scope]
- [X] CHK037 Are the conditional FR-028 promotion-to-default artifacts (inverted default location, explicit-off flag, legacy-path test) named in data-model.md §5 with stable references so a future demotion can locate them? [Traceability, data-model.md §5]
- [X] CHK038 Is the runbook lifecycle rule (future features modifying CLI flags / `evidence_gate_id` MUST update the runbook in the same body of work) stated, so traceability holds across future features? [Coverage, contracts/runbook.md]

## Stability of References

- [X] CHK039 Are spec section references (`§FR-XXX`, `§US Y Scenario Z`) stable identifiers — i.e., would they survive a renumbering? [Coverage, Spec-wide]
- [X] CHK040 Are R-021 decision identifiers stable enough that they can be referenced from `tasks.md` (the future Phase 2 output) without ambiguity? [Coverage, research.md]
- [X] CHK041 Are checklist CHK IDs stable per file (CHK001 in `requirements.md` is different from CHK001 in `scope.md`) — is the per-file scope explicit so cross-file references aren't ambiguous? [Clarity, checklists/]
- [X] CHK042 Are contract file paths stable (relative paths `./contracts/X.md` vs. absolute) — would a reviewer following a link from quickstart.md or plan.md land on the right file? [Coverage, plan.md, quickstart.md]

## Traceability Density

- [X] CHK043 Is the average `[Spec §...]` / `[Gap]` / `[Traceability]` density across the existing 8 checklists ≥ 80% (i.e., at least 80% of items carry a reference)? [Measurability, checklists/]
- [X] CHK044 Are deep release-gate checklists (the eight original + the five new domain checklists this run added) free of items that lack any traceability marker? [Coverage, checklists/]

## Gaps to Flag

- [X] CHK045 Is a cross-reference table (FR → US scenario → checklist item → R-021 decision) needed as a separate matrix document, or is the existing in-file cross-referencing sufficient? [Gap, Coverage]
- [X] CHK046 Are requirements present for verifying traceability automatically (e.g., a CPU-safe test that parses spec.md FRs and asserts each is referenced by ≥ 1 checklist or contract)? [Gap, Coverage]
- [X] CHK047 Is the traceability handling for items deferred from feature 020 (R-020.15 → this feature's US2) explicit — does a future audit start at R-020.15 and follow the chain forward? [Gap, Coverage]
- [X] CHK048 Are bidirectional links explicit — does the spec link forward to plan/research/contracts, and do plan/research/contracts link back to the spec? [Coverage, Gap]

## Notes

- This checklist tests the *traceability writing quality* across nine artifacts. It is the audit-trail validator for the feature.
- The principal traceability failure mode is "orphaned" content — a contract, checklist item, or research decision that references nothing and is referenced by nothing. CHK001–CHK031 and CHK043–CHK044 are the defenses against orphans at the requirements-writing layer.
- Items CHK045–CHK048 flag genuine gaps that may benefit from a future cross-reference matrix or automated check.
