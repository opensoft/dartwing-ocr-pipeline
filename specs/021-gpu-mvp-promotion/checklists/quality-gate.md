# Quality Gate Checklist: GPU MVP Promotion

**Purpose**: Validate that the two-metric quality-gate requirements (aggregate vendor-identity score + per-document pass count, candidate-vs-legacy non-regression on the benchmark subset) are written with the precision needed to prevent latency-driven quality loss from masking a regression.
**Created**: 2026-05-18
**Feature**: [spec.md](../spec.md)

This checklist tests the *requirements writing* of the quality gate — not the gate's verdict. Items target completeness, clarity, consistency, and measurability of FR-019 through FR-022, US4, and the Quality-Gate Verdict entity.

## Metric Definition (FR-019)

- [X] CHK001 Are the two metrics — aggregate vendor-identity score, per-document pass count — both stated explicitly in FR-019? [Completeness, Spec §FR-019]
- [X] CHK002 Is "aggregate vendor-identity score" defined in terms of the existing feature-007 evaluator (no new metric, no new evaluator flag)? [Clarity, Spec §FR-019, §Assumptions]
- [X] CHK003 Is "per-document pass count" defined in terms of the existing per-document pass flag (no new threshold, no new pass criterion introduced by this feature)? [Clarity, Spec §FR-019, §Assumptions]
- [X] CHK004 Is the comparison axis ("candidate-vs-legacy on the same subset") stated unambiguously, with no allowance for cross-subset comparison? [Consistency, Spec §FR-019, §FR-013]
- [X] CHK005 Is the metric-aggregation formula precise — i.e., is "aggregate" a sum, a mean, a sum-of-points, etc.? [Clarity, Gap]

## PASS Verdict Logic (FR-020)

- [X] CHK006 Is PASS defined as a strict conjunction (BOTH aggregate non-regressing AND per-document-pass-count non-regressing), with no allowance for one metric compensating for the other? [Clarity, Spec §FR-020]
- [X] CHK007 Is "non-regressing" defined as candidate ≥ legacy (greater-than-or-equal), not strictly greater-than? [Clarity, Spec §FR-020]
- [X] CHK008 Is the case "candidate strictly improves on one metric, ties on the other" explicitly PASS (per the ≥ rule)? [Coverage, Spec §FR-020]
- [X] CHK009 Is the case "candidate ties exactly on both metrics" explicitly PASS — i.e., a zero-improvement candidate still PASSes if it doesn't regress? [Coverage, Spec §FR-020]
- [X] CHK010 Is the operator interpretation of PASS unambiguous — PASS *permits* the promotion decision but does not perform it (FR-029)? [Consistency, Spec §FR-020, §FR-029]

## FAIL Verdict Recording (FR-021)

- [X] CHK011 Is FAIL defined as the inverse of PASS — i.e., FAIL triggers iff at least one metric regresses (candidate < legacy on aggregate, or candidate < legacy on per-doc pass count)? [Consistency, Spec §FR-021]
- [X] CHK012 Is the FAIL recording requirement explicit about *which* metric regressed AND by *how much* (magnitude, not only sign)? [Completeness, Spec §FR-021]
- [X] CHK013 Is the FAIL → "skip-fallback remains opt-in" linkage stated in both FR-021 and FR-027 (so duplication doesn't introduce drift)? [Consistency, Spec §FR-021, §FR-027]
- [X] CHK014 Is the FAIL case "candidate regresses on quality but improves on latency" explicitly addressed (latency improvement MUST NOT mask quality regression)? [Coverage, Spec §FR-021, §Risks]

## BLOCKED Verdict Recording (FR-022)

- [X] CHK015 Is BLOCKED defined as "the gate cannot run because of a named hardware or runtime cause" (not as "the gate ran and was indeterminate")? [Clarity, Spec §FR-022]
- [X] CHK016 Is the named-cause requirement stated with at least one worked example (e.g., "ROCm SDMA path unavailable on this kernel") so a reviewer can recognize a compliant BLOCKED record? [Clarity, Spec §FR-010, §FR-022]
- [X] CHK017 Is the BLOCKED → "skip-fallback remains opt-in" linkage stated in both FR-022 and FR-027? [Consistency, Spec §FR-022, §FR-027]
- [X] CHK018 Is the distinction between "BLOCKED" (gate cannot run) and "FAIL" (gate ran, regression detected) clear enough that a reviewer cannot conflate them? [Clarity, Spec §FR-021, §FR-022]
- [X] CHK019 Is the "silent skip is NOT permitted" discipline (FR-010 spirit) extended to the quality gate, even though FR-010 is in the verification surface? [Consistency, Spec §FR-010, §FR-022]

## Comparison Symmetry

- [X] CHK020 Is the same-subset rule (FR-013 echoed in the quality gate) explicit — i.e., the legacy and candidate runs being scored are the same five documents? [Consistency, Spec §FR-019, §FR-013]
- [X] CHK021 Is the same-scoring-procedure rule explicit — i.e., the same evaluator version, the same `expected.json` baselines, the same scoring rubric apply to both lanes? [Consistency, Coverage]
- [X] CHK022 Is the prohibition on cherry-picking documents (e.g., scoring only the 3 documents where candidate did well) stated explicitly or only implicit in FR-013/FR-019? [Coverage, Gap]

## Evaluator Reuse Boundary

- [X] CHK023 Is the feature-007 evaluator referenced as the single source of truth for per-document scores AND per-document pass flags? [Clarity, Spec §Assumptions, §FR-019]
- [X] CHK024 Is the evaluator's surface bounded to "use as-is" (no new metric, no new pass threshold) so a reviewer recognizes a forbidden modification? [Clarity, Spec §Assumptions, §FR-032]
- [X] CHK025 Is the relationship between the feature-007 evaluator's output (`evaluation_document.json`, `evaluation_run_summary.json`) and Appendix B's recorded numbers explicit — transcription, aggregation, or derivation? [Clarity, Gap]

## Quality-Gate Verdict Entity

- [X] CHK026 Is the Quality-Gate Verdict entity defined with all three possible states (PASS, FAIL, BLOCKED) and no implicit fourth state (e.g., "incomplete")? [Completeness, Spec §Key Entities]
- [X] CHK027 Is the verdict's recording medium (Appendix B) stated as the single canonical location, with no allowance for alternate medium? [Consistency, Spec §Key Entities, §FR-024]
- [X] CHK028 Is the PASS verdict's content requirement (per-doc scores per lane + aggregate per lane + per-doc pass count per lane + explicit non-regression comparison) complete? [Completeness, Spec §FR-024]
- [X] CHK029 Is the FAIL verdict's content requirement (which metric regressed + by how much) explicit and separate from PASS's content requirement? [Completeness, Spec §FR-024]
- [X] CHK030 Is the BLOCKED verdict's content requirement (named cause) explicit and separate from FAIL's content requirement? [Completeness, Spec §FR-024]

## Acceptance Criteria for Quality Gate

- [X] CHK031 Is SC-007's "single explicit quality-gate verdict (PASS / FAIL / BLOCKED)" measurable against Appendix B alone — i.e., can a reviewer point to one verdict line without ambiguity? [Measurability, Spec §SC-007]
- [X] CHK032 Is SC-007's required content (per-doc scores per lane, per-doc pass flags per lane, aggregate per lane, per-doc pass count per lane) testable as a closed list? [Measurability, Completeness, Spec §SC-007]

## US4 Acceptance Scenarios

- [X] CHK033 Are all five US4 scenarios (per-doc scoring, aggregate computation, PASS, FAIL, BLOCKED) each tied to at least one FR (FR-019, FR-020, FR-021, FR-022)? [Traceability, Spec §US4]
- [X] CHK034 Is US4 scenario 3 ("PASS verdict … promotion is now a permitted operator decision — but promotion still requires an explicit team decision (US6) and is not automatic") consistent with FR-029? [Consistency, Spec §US4, §FR-029]
- [X] CHK035 Is US4 scenario 4's "which metric regressed and by how much" requirement consistent with FR-021's recording rigor? [Consistency, Spec §US4, §FR-021]

## Risk Coverage

- [X] CHK036 Is the PRD §Risks item "Quality regression hidden by latency gains" mitigated by the two-metric structure being non-bypassable (no aggregate-only verdict allowed)? [Coverage, Spec §Risks, §FR-020]
- [X] CHK037 Is the case "latency improves on every document AND quality holds" treated identically to "latency improves on some, quality holds" (both PASS)? [Coverage, Consistency]
- [X] CHK038 Is the case "quality strictly improves AND latency strictly worsens" handled — is this still PASS by the two-metric definition (quality non-regressing, but the latency context is absent from the gate)? [Coverage, Gap]

## Gaps to Flag

- [X] CHK039 Is the requirement for tie-breaking when the verdict is computed against the *same* benchmark run record explicit, or is re-evaluation against the recorded artifact required? [Gap]
- [X] CHK040 Is the case "evaluator surface changed between feature 020 landing and this feature's quality-gate run" addressed (evaluator version pin, reproducibility)? [Gap, Coverage]
- [X] CHK041 Are requirements defined for what happens when the per-document pass count is undefined (e.g., a document's `expected.json` is missing)? [Gap, Edge Case]
- [X] CHK042 Is the relationship between the quality gate's `evaluation_run_summary.json` (a feature-007 artifact) and Appendix B (this feature's deliverable) explicit, so a reviewer knows which is canonical? [Gap, Traceability]

## Notes

- This checklist tests whether the quality-gate *requirements* are well-written.
- The principal failure mode is a one-sided verdict (aggregate-only or per-doc-only) that lets latency gains mask a regression; FR-020's strict conjunction is the defense, and CHK006–CHK010, CHK036 test whether the spec writes that defense unambiguously.
- Items CHK022, CHK038–CHK042 flag genuine gaps that may benefit from a future spec amendment.
