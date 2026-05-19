# Failure Handling Checklist: GPU MVP Promotion

**Purpose**: Validate that the failure-handling requirements (fail-fast posture, blocked-verdict recording, no-silent-skip discipline, named-cause requirement, quality-regression handling, procedural findings, Fallback compatibility) are written with the precision needed to preserve the "GPU paths stay explicit and fail-fast" guarantee.
**Created**: 2026-05-18
**Feature**: [spec.md](../spec.md)

This checklist tests the *requirements writing* of the failure-handling surface — not the failure handlers themselves. Items target completeness, clarity, consistency, and measurability of FR-001/FR-004 fail-fast, FR-010/FR-022 blocked recording, SC-002/SC-004 acceptance bars, and the Fallback discipline.

## Fail-Fast Posture (FR-001 / FR-004 / SC-002)

- [X] CHK001 Is "fail fast" defined operationally as "non-zero exit AND named-prerequisite error message", not just "stops running"? [Clarity, Spec §FR-004, §SC-002]
- [X] CHK002 Is the fail-fast trigger surface complete — is the spec explicit that FR-001 (preflight) + FR-002 (Ollama) together cover ALL fail-fast triggers, not just SOME? [Completeness, Spec §FR-004]
- [X] CHK003 Is the fail-fast prohibition "MUST NOT silently substitute the CPU profile or write a GPU-labelled artifact when running on CPU" stated identically in FR-004 and SC-002? [Consistency, Spec §FR-004, §SC-002]
- [X] CHK004 Is the fail-fast requirement extended to BOTH benchmark runs and demo runs (FR-018 + FR-025), not only benchmark runs? [Coverage, Spec §FR-004, §FR-025]
- [X] CHK005 Is the case "preflight succeeds, Ollama check fails AFTER preflight passes but BEFORE the demo command runs" handled — does fail-fast still trigger at the Ollama check, or only at the first GPU operation? [Coverage, Gap]
- [X] CHK006 Is the error message format required to be machine-parseable (e.g., structured), or is human-readable text sufficient? [Clarity, Gap]
- [X] CHK007 Is the prohibition on partial GPU-labelled artifacts stated in operational terms — could a reviewer detect a violating partial write (e.g., a half-written `preprocess_output.json` under a GPU strategy ID)? [Measurability, Spec §FR-004]

## Blocked-Verdict Discipline (FR-010 / FR-022)

- [X] CHK008 Is "blocked" defined consistently across FR-010 (verification deferral) and FR-022 (quality-gate deferral) — same semantics, same recording rigor? [Consistency, Spec §FR-010, §FR-022]
- [X] CHK009 Is the "named cause" requirement enumerated with at least one worked example (e.g., "ROCm SDMA path unavailable on this kernel", "Paddle wheel mismatch")? [Clarity, Spec §FR-010]
- [X] CHK010 Is the prohibition "silent skips are NOT permitted" stated in both FR-010 and US2 scenario 5 (and implicitly in FR-022)? [Consistency, Spec §FR-010, §US2 Scenario 5, §FR-022]
- [X] CHK011 Is the recording medium for blocked verdicts specified — Appendix A (benchmark blocked) vs. Appendix B (quality-gate blocked) vs. the deferral marker in the deferred test file? [Clarity, Coverage]
- [X] CHK012 Is the boundary between "fail-fast" (gate refuses to run) and "blocked" (gate ran/was attempted but cannot produce a verdict) explicit? [Clarity, Gap]
- [X] CHK013 Is the case "blocked on one US (e.g., US3) but not blocked on a related US (e.g., US4)" addressed — does each US carry its own blocked verdict independently? [Coverage, Spec §FR-010]
- [X] CHK014 Is the requirement that a blocked verdict for US3 (benchmark) implies a blocked or FAIL verdict for US4 (quality gate) — or are they independent? [Consistency, Coverage]

## No-Silent-Skip Discipline (SC-004)

- [X] CHK015 Is "Zero formerly-deferred items remain silently inert" measurable against a closed list of feature-020 deferrals (US2 scenarios 1–4)? [Measurability, Spec §SC-004]
- [X] CHK016 Is the universe of "formerly-deferred items" enumerated (sufficient skip-fallback, borderline fallback, all-suppressed lazy construction, `--gpu-warmup` exception), so a reviewer can count completion? [Completeness, Spec §SC-004, §US2]
- [X] CHK017 Is the discipline "explicit deferral marker that names the blocker" reproducible — can a reviewer recognize a compliant marker from text alone? [Clarity, Spec §US2 Scenario 5]
- [X] CHK018 Is the requirement extended to NEW deferrals introduced by this feature (e.g., if US3 cannot run, the deferral is recorded explicitly in Appendix A)? [Coverage, Spec §FR-023]

## Named-Cause Requirement

- [X] CHK019 Is "named cause" precise enough to exclude generic phrases like "hardware unavailable" or "runtime error"? [Clarity, Spec §FR-010]
- [X] CHK020 Are the categories of acceptable named causes enumerated (hardware drift, ROCm/MIOpen state, Paddle wheel mismatch, Ollama unavailability, interpreter mismatch)? [Completeness, Gap]
- [X] CHK021 Is the case "the blocker resolves itself between recording and re-run" addressed — should the recorded blocked verdict be re-evaluated, or is it frozen in time? [Coverage, Gap]
- [X] CHK022 Is the named cause required to map to an actionable next step (operator can remediate or escalate), or is description sufficient? [Coverage, Spec §SC-002]

## Quality-Regression Handling (FR-021)

- [X] CHK023 Is the FAIL recording requirement "specific metric AND magnitude" measurable from Appendix B alone? [Measurability, Spec §FR-021]
- [X] CHK024 Is the FAIL → "skip-fallback remains opt-in regardless of latency improvement" rule stated unambiguously, with no exception for marginal regressions? [Clarity, Spec §FR-021]
- [X] CHK025 Is the case "candidate regresses on one document but the aggregate still ≥ legacy" handled — is per-document pass count regression treated independently? [Coverage, Spec §FR-020, §FR-021]
- [X] CHK026 Is the requirement to record the regressing document's per-doc score explicit, so a reviewer can attribute the regression to a specific document? [Coverage, Gap]
- [X] CHK027 Is the requirement for a regression-cause analysis explicit, or only the regression description (delta and direction)? [Coverage, Gap]

## Procedural Findings (Corpus Mutation)

- [X] CHK028 Is the Edge Case "benchmark run accidentally targets committed corpus folders" mapped to a recording requirement — is the finding written into Appendix A as a procedural finding? [Coverage, Spec §Edge Cases]
- [X] CHK029 Is the consequence "the run output is invalid for Appendix A/B until re-run against scratch" stated unambiguously? [Clarity, Spec §Edge Cases]
- [X] CHK030 Is the detection mechanism for a procedural finding explicit (e.g., the operator notices, `git status` shows mutations, CI flags drift)? [Coverage, Gap]
- [X] CHK031 Is the re-run obligation defined — must the operator restart the four-run sequence from warmup, or only re-run the contaminated lane? [Coverage, Gap]

## Fallback Discipline (PRD §Fallback)

- [X] CHK032 Is the Fallback blockquote at the spec head consistent with FR-027 (FAIL/BLOCKED → stay opt-in) and FR-022 (BLOCKED named cause)? [Consistency, Spec §Fallback]
- [X] CHK033 Is the Fallback's four-part posture ("skip-fallback stays off, CPU/stub CI baseline, GPU paths explicit and fail-fast, failed/blocked evidence recorded") complete? [Completeness, Spec §Fallback]
- [X] CHK034 Is the Fallback compatible with the FR-028 explicit-off legacy path requirement (which only applies when promotion is chosen)? [Consistency, Spec §Fallback, §FR-028]
- [X] CHK035 Is "feature-complete but not GPU-promoted" defined operationally — what changes between "feature-complete" and "GPU-promoted" in terms of artifacts, runbook, defaults? [Clarity, Spec §Fallback]
- [X] CHK036 Is the case "Fallback engaged but the team later wants to re-attempt promotion" addressed — does the spec require a fresh four-run + quality-gate, or can previously-blocked evidence be amended? [Coverage, Gap]

## Recovery Posture

- [X] CHK037 Are recovery actions specified for each failure mode — preflight non-success (resolve prerequisite, re-run), Ollama CPU-only (re-load model on GPU, re-check), quality gate FAIL (analyze, decide, re-run if applicable)? [Coverage, Recovery Flow]
- [X] CHK038 Is the case "the entire promotion attempt is aborted" addressed — does the spec specify what to keep (blocked evidence) and what to discard (incomplete Appendix A/B drafts)? [Coverage, Gap]
- [X] CHK039 Is the rollback path for an over-eager promote-to-default change explicit (revert the default flip, update Appendix B and runbook to record the reversion)? [Coverage, Gap]

## Acceptance Criteria for Failure Handling

- [X] CHK040 Is SC-002's "100% / Zero" framing testable from run records alone (no operator testimony required)? [Measurability, Spec §SC-002]
- [X] CHK041 Is SC-004's "Zero formerly-deferred items remain silently inert" testable by reading the deferred test files plus the Appendix B deferral entries? [Measurability, Spec §SC-004]
- [X] CHK042 Is SC-011's "Zero benchmark or demo runs mutate the committed corpus" testable by inspecting commits / `git status` snapshots taken during/after runs? [Measurability, Spec §SC-011]

## Cross-Surface Consistency

- [X] CHK043 Is the language "fail fast" / "silent skip" / "blocked" / "FAIL" / "BLOCKED" used consistently across FR-004, FR-010, FR-021, FR-022, Edge Cases, Fallback, US2, US4, and Success Criteria — no synonym drift? [Consistency, Spec-wide]
- [X] CHK044 Is the verb tense / agency consistent ("System MUST fail fast" vs. "the run aborts" vs. "the operator stops")? [Consistency, Clarity]
- [X] CHK045 Are the failure recording media (Appendix A, Appendix B, deferral marker in test files, runbook) each named with a stable reference so a reviewer can audit completeness? [Traceability, Spec §FR-010, §FR-022, §FR-023, §FR-024]

## Gaps to Flag

- [X] CHK046 Are requirements defined for partial-progress recording — e.g., 3 of 5 benchmark documents succeed, then the 4th fails? Is Appendix A allowed to record the 3 successful documents, or is the entire run invalid? [Gap, Coverage]
- [X] CHK047 Are requirements defined for failure-mode telemetry — does the spec want failure-cause histograms recorded across attempts, or only the latest verdict? [Gap, Out of Scope verification]
- [X] CHK048 Is the "operator visible error message" requirement (FR-004, SC-002) specific about log destination (stderr, stdout, log file, all of the above)? [Gap, Clarity]
- [X] CHK049 Are requirements defined for the case "fail-fast triggers but the operator has already started a demo audience session" — does the spec want a graceful interrupt or only a hard exit? [Gap, UX]

## Notes

- This checklist tests whether the failure-handling *requirements* are well-written.
- The principal failure modes for this surface are: (a) a silent CPU fallback masquerading as GPU success, (b) a "deferred" test that fades into inertia without a tracking record, (c) a quality regression hidden by latency gains. CHK001–CHK007, CHK015–CHK018, and CHK023–CHK027 are the respective defenses at the requirements-writing layer.
- Items CHK005, CHK012, CHK020–CHK022, CHK026–CHK027, CHK030–CHK031, CHK036, CHK038–CHK039, CHK046–CHK049 flag genuine gaps that may benefit from a spec amendment or planning-time decision.
