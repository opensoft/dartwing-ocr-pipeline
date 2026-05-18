# Performance-Measurement Quality Checklist: GPU MVP Promotion

**Purpose**: Validate that the performance-measurement requirements (`phase_timings.*` vocabulary, jitter band, material change, re-derivability, four-run discipline as noise-floor characterization) are written with the precision needed to produce reproducible, third-party-auditable latency evidence — without introducing an absolute latency release gate (out of scope per Stage 1 Scope Constraint).
**Created**: 2026-05-18
**Feature**: [spec.md](../spec.md), [contracts/appendix-recording.md](../contracts/appendix-recording.md)

This checklist tests the *writing quality of the performance-measurement requirements*, distinct from `benchmark.md` which tests the four-run discipline and Appendix A structure. Items target the measurability and reproducibility of the performance claim itself.

## Performance-Claim Scope

- [X] CHK001 Is the performance-claim shape explicit (non-regression on the candidate lane vs. legacy lane on a fixed five-document subset), with no implicit absolute latency target? [Clarity, Spec §FR-015, Stage 1 Scope Constraint]
- [X] CHK002 Is the prohibition on adding an absolute latency release gate stated unambiguously (Constitution §"Stage 1 Scope Constraints" says "no latency target as a release gate") — i.e., is "non-regression vs. legacy" specifically distinguished from "below T seconds"? [Consistency, Constitution §Stage 1 Scope Constraints]
- [X] CHK003 Is "GPU lane" the unit of performance comparison (not absolute hardware comparison), so a workstation change between runs doesn't invalidate prior evidence? [Coverage, Spec §FR-013]
- [X] CHK004 Is the audience of the performance claim explicit (the promotion-decision reviewer, not external stakeholders)? [Clarity, Gap]

## Phase-Key Vocabulary Quality

- [X] CHK005 Are the seven enumerated `phase_timings.*` keys (`paddle_import`, `gpu_bind_probe`, `engine_init`, `warmup`, `rasterization`, `per_page_inference`, `artifact_write`, `total`) named with feature-015 lineage so the spec doesn't accidentally introduce a new key? [Consistency, Spec §FR-014]
- [X] CHK006 Is the "when present" wording (FR-014) tied to a closed set of conditions for absence (lazy construction → `engine_init` + `warmup` absent), so a reader knows what a missing key signals? [Clarity, Spec §FR-014, §FR-008]
- [X] CHK007 Is the per-key semantic explicit (e.g., does `total` include `artifact_write`? does `per_page_inference` exclude `rasterization`?) — these are required to be derivable from feature 015's emission spec, not redefined here? [Clarity, Traceability, Spec §FR-014]
- [X] CHK008 Is the closed vocabulary requirement explicit (no `phase_timings.*` key may be added by this feature; new keys would require a feature-015 amendment)? [Consistency, Spec §FR-032]

## Jitter Formula Measurability

- [X] CHK009 Is the FR-015 jitter formula measurable from per-document, per-phase-key, per-(lane,run) numeric inputs alone (no extrinsic constants)? [Measurability, Spec §FR-015]
- [X] CHK010 Is the formula's output unit identical to the input unit (seconds in → seconds out per R-021.2), so no implicit conversion is required? [Clarity, Spec §R-021.2]
- [X] CHK011 Is the per-document, per-phase-key granularity stated everywhere — i.e., no global jitter band across documents, no cross-key aggregate? [Consistency, Spec §FR-015]
- [X] CHK012 Can the formula be applied to a key that emits in legacy run but not candidate run (lazy construction case)? — i.e., does the spec or research.md handle `LAZY` rows without forcing a numeric? [Coverage, Spec §FR-014, contracts/appendix-recording.md]

## Material-Change Direction Quality

- [X] CHK013 Is the direction-symmetric material-change rule (R-021.4) stated as MUST, so an implementor cannot interpret it as "decreases only"? [Clarity, Spec §R-021.4]
- [X] CHK014 Is the carve-out "only `per_page_inference` and `total` MAY decrease materially on suppressed documents" stated as a *permitted* direction, not a *required* direction? [Clarity, Spec §FR-016]
- [X] CHK015 Is the inverse (a *material increase* on `per_page_inference` or `total` for a suppressed document IS a finding) stated explicitly (per R-021.4)? [Coverage, Spec §R-021.4]
- [X] CHK016 Is "movement … beyond the jitter band" defined precisely enough that a reviewer can apply the `|Δ| > threshold` rule to any row without ambiguity? [Measurability, Spec §FR-016]

## Re-derivability Discipline (SC-005)

- [X] CHK017 Is SC-005's "sufficient for a third party to re-derive the promotion verdict without re-running" reproduced in the appendix-recording contract, so the SC and the recording structure are aligned? [Traceability, Spec §SC-005, contracts/appendix-recording.md]
- [X] CHK018 Is the re-derivability requirement applied to *every* numeric in Appendix A (per-doc score, aggregate, jitter band, material-change verdict — all derivable from raw phase-key numbers)? [Completeness, contracts/appendix-recording.md]
- [X] CHK019 Is the requirement explicit that Appendix A contains no externally-sourced numbers (e.g., no benchmark numbers from a different workstation, no manual operator adjustment of recorded values)? [Coverage, Gap]
- [X] CHK020 Is the "third party" audience defined operationally enough that a reviewer can dry-run the re-derivation (e.g., "any pipeline contributor with access to the recorded files")? [Clarity, Spec §SC-005]

## Four-Run Discipline as Noise-Floor Characterization

- [X] CHK021 Is the FR-012 four-run discipline framed as *noise-floor characterization* (the paired-run spread is the per-document, per-key noise floor) — not as "run 1 is wrong, run 2 is right"? [Clarity, Spec §FR-012]
- [X] CHK022 Is the warmup run's role (cache priming, not noise measurement) distinguished from the legacy and candidate pairs' roles (each pair measures noise)? [Clarity, Spec §FR-012]
- [X] CHK023 Is the rationale (MIOpen/COMGR cache cold-vs-warm domination — feature 016 lineage) cited so a reviewer understands why three minutes of operator time goes into discarding two of the four timing measurements? [Traceability, Spec §FR-012, §Edge Cases]
- [X] CHK024 Are the failure modes of the four-run discipline addressed (e.g., what if the second run is also cold-cache because the workstation rebooted between runs)? [Coverage, Gap]

## Run-Summary Coverage as Performance Audit Trail

- [X] CHK025 Are the five required per-document run_summary fields (gate_decision, evidence_gate_state_counts, evidence_gate_suppressed_fallback_count, ocr_only_fallback_count, preprocess_strategy_id) reproduced identically in FR-017 and US3 scenario 4? [Consistency, Completeness, Spec §FR-017]
- [X] CHK026 Is the recording requirement explicit that these fields are recorded *per document × per lane × run-2* (not just per benchmark sequence aggregate)? [Clarity, Spec §FR-017]
- [X] CHK027 Is the relationship to feature-020's `evidence_gate_documents` table explicit (Appendix A's observability table is a transcription / derivation of that field)? [Clarity, contracts/appendix-recording.md]

## Workstation Environment Performance Surface

- [X] CHK028 Is the workstation environment fingerprint (ROCm version, Paddle wheel version, Ollama version, hostname, kernel) required in Appendix A's first subsection? [Completeness, contracts/appendix-recording.md]
- [X] CHK029 Is the fingerprint required to be the *actual* runtime values (sourced from `rocm-smi`, `pip show paddlepaddle-dcu`, `ollama --version`), not operator-typed strings? [Measurability, Gap]
- [X] CHK030 Are workstation-stability assumptions explicit (e.g., no other process consuming GPU memory during the four-run sequence)? [Coverage, Gap]
- [X] CHK031 Is the interpreter path (FR-003 forensic) required in the fingerprint (so the absolute interpreter location is captured for replay)? [Completeness, Spec §FR-003]

## Performance-Comparison Symmetry

- [X] CHK032 Is the same-subset rule (FR-013) reproduced as a performance-comparison invariant (legacy and candidate use the same five documents, same source.pdf bytes, same preprocess strategy ID)? [Consistency, Spec §FR-013]
- [X] CHK033 Is the same-environment rule explicit (legacy and candidate lanes run in the same shell session, same workstation state, same Ollama placement) — or is cross-session comparison permitted with documented caveats? [Coverage, Gap]
- [X] CHK034 Is the legacy-candidate ordering required to be fixed (legacy first, candidate second, as in FR-012), so cache-warmth bias is reduced? [Clarity, Spec §FR-012]

## Performance-Findings Discipline

- [X] CHK035 Is the finding-recording requirement explicit (any cell marked `YES ↑ ⚠` or `YES` on a non-permitted phase key produces an Appendix A §Findings entry)? [Completeness, contracts/appendix-recording.md]
- [X] CHK036 Is the finding-recording requirement extended to anomalies beyond material change (e.g., lane lengths differ, document missing from one lane, recorded value out of unit range)? [Coverage, contracts/appendix-recording.md]
- [X] CHK037 Are findings required to cite the (document, phase_key, lane) triple, so each finding is uniquely identifiable? [Measurability, contracts/appendix-recording.md]

## Out-of-Scope Performance Surfaces (Drift Prevention)

- [X] CHK038 Is the spec free of language introducing an absolute latency target (e.g., "p95 < 500ms")? [Consistency, Spec-wide]
- [X] CHK039 Is the spec free of language introducing performance percentiles (p50/p95/p99) that would require multi-run aggregation beyond the four-run discipline? [Consistency, Spec-wide]
- [X] CHK040 Is the spec free of language describing performance-tuning recommendations (e.g., "lower DPI for faster preprocessing") — the feature is validation/promotion, not tuning? [Consistency, Spec §FR-032]
- [X] CHK041 Is the spec free of language requiring continuous performance monitoring or trend recording (over-time surveillance is explicitly out of scope per FR-032)? [Consistency, Spec §FR-032, §Out of Scope]

## Gaps to Flag

- [X] CHK042 Are performance-claim *invalidation* conditions documented — i.e., what changes between two runs would force re-recording Appendix A (e.g., a Paddle wheel upgrade)? [Gap]
- [X] CHK043 Is the case "one of the five benchmark documents is later relabeled or removed from the corpus" addressed — does the appendix become invalid retroactively? [Gap]
- [X] CHK044 Is the case "the four-run sequence's per-document jitter band is implausibly wide (e.g., > 1 second on `per_page_inference`)" addressed — does the spec want a re-run trigger? [Gap]
- [X] CHK045 Is the case "candidate run-2 lower than candidate run-1 by more than the jitter band ON ITSELF" (intra-lane cache warming effect) addressed — does it invalidate the pair? [Gap]

## Notes

- This checklist tests the *writing quality of performance-measurement requirements*, distinct from `benchmark.md` (which tests the four-run discipline and recording mechanics).
- The principal failure modes are: (a) accidental introduction of an absolute latency gate (CHK038–CHK041 are the defense); (b) loss of re-derivability through under-specified table shapes (CHK017–CHK020 are the defense); (c) implicit reliance on a stable workstation environment (CHK028–CHK031, CHK043).
- Items CHK042–CHK045 flag genuine gaps that may benefit from a future spec amendment or research.md decision.
