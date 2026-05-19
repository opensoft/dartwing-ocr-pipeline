# Specification Quality Checklist: GPU MVP Promotion

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-05-18
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

This is an infrastructure validation / promotion / documentation feature. Several success criteria and functional requirements necessarily name concrete technology surfaces — Paddle preflight return values, Ollama GPU placement, `phase_timings.*` keys, `run_summary` field names, the `ppstructurev3@gpu` profile, the fixed five-document benchmark subset, `--gpu-warmup` and `--evidence-gate-skip-fallback` flags, the feature-020 quickstart appendices, etc. These are not implementation choices the spec is making — they are pre-existing contract surfaces from features 014–020 that this feature must reference precisely because the whole point of the feature is to close their proof points. The "technology-agnostic" criterion is interpreted in that context: the spec describes operator-facing outcomes and observable run records, not new code structure, new modules, new schemas, or new dependencies.

- Items marked incomplete require spec updates before `/speckit.clarify` or `/speckit.plan`.
- The auto-generated spec-quality checklist above is preserved; the deep release-gate items below were appended by `/speckit.checklist` after `/speckit.clarify` Session 2026-05-18 resolved five ambiguities (jitter-band formula, Ollama check mechanism, wrong-interpreter detection, canonical extraction lane, Ollama model id).

---

## Deep Requirements Quality Review

These items are "unit tests for English" — they validate the spec's writing quality, completeness, and consistency, not implementation behavior. Each item references a spec section, FR/SC/US scenario, or carries a `[Gap]` marker when checking for a missing requirement.

### Requirement Completeness

- [X] CHK001 Are all six user stories (US1–US6) each accompanied by at least one acceptance scenario and an independent-test description? [Completeness, Spec §User Scenarios]
- [X] CHK002 Does every FR (FR-001 through FR-033) have at least one user story or success criterion that references it? [Completeness, Spec §Functional Requirements]
- [X] CHK003 Are requirements documented for both halves of the GPU readiness composite verdict (Paddle preflight AND Ollama placement)? [Completeness, Spec §FR-001, §FR-002]
- [X] CHK004 Are requirements defined for the case where every benchmarked document is `borderline` or `insufficient` (the inverse of the all-`sufficient` case in FR-008 / FR-009)? [Completeness, Gap] — covered transitively: FR-007 applies per-document, so all-borderline/insufficient is the per-doc rule applied N times. No multi-doc-specific scenario added.
- [X] CHK005 Are requirements defined for what gets recorded when a benchmark run partially completes (e.g., 3 of 5 documents succeed before a runtime error)? [Completeness, Gap] — resolved by [research.md §R-021.12](../research.md): labeled "Partial Benchmark Run (K/5)" sub-block in Appendix A; partial data is forensic-only, never decisional.
- [X] CHK006 Are requirements defined for the procedural discovery surface — how does a reviewer locate the recorded Appendix A / B numbers vs. the underlying scratch run output? [Completeness, Spec §FR-023, §FR-024] — paths explicit: Appendix A/B in `specs/020-vendor-evidence-gate/quickstart.md`; scratch tree at `/tmp/021-bench/<lane>/run<N>/<doc>/` per R-021.1.
- [X] CHK007 Are requirements documented for the demo-runbook surface layer (file path, format, owner) separate from its content (FR-025)? [Completeness, Gap] — resolved by [research.md §R-021.5](../research.md): canonical path `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md`; owned by this feature; format is GitHub Markdown.
- [X] CHK008 Are requirements defined for archival of replaced/obsolete runbook content when the GPU runbook supersedes a prior CPU-permissive runbook? [Completeness, Gap] — **closed**: no prior CPU-permissive demo runbook exists at the canonical path (this feature creates the file fresh), so archival is a non-issue here. Future-feature handoff: if a later feature replaces the runbook, the replacement spec MUST address archival of the superseded content.

### Requirement Clarity

- [X] CHK009 Is "GPU-capable interpreter" defined unambiguously enough that an operator can determine whether a given interpreter qualifies? [Clarity, Spec §Assumptions] — Assumptions §1 now defines it as `paddle.is_compiled_with_rocm() == True` (equivalently, FR-001 preflight returns `ppstructurev3_init_succeeded`).
- [X] CHK010 Is the "active voter config" referenced in FR-002 named with sufficient specificity for an operator to identify which file/key the model name is read from? [Clarity, Spec §FR-002] — Clarifications Q5 + R-021.7 name `configs/voter/ollama-gpu.yaml` with top-level `model_name` key per feature 005 voter-config schema.
- [X] CHK011 Is the FR-015 jitter-band formula written in a form a third party can re-derive without consulting source code? [Clarity, Spec §FR-015] — Formula `max(|legacy_run2 − legacy_run1|, |candidate_run2 − candidate_run1|)` with strict-greater-than material rule stated inline in FR-015.
- [X] CHK012 Is "fully on GPU" (FR-002) explicitly distinguished from partial placement (`0 < size_vram < size`) in every place the Ollama check is referenced? [Clarity, Consistency, Spec §FR-002, §Edge Cases] — FR-002 + Edge Case "Paddle preflight passes but Ollama is CPU-only" + US1 scenario 2 all use the same `size_vram > 0 AND size_vram == size` form.
- [X] CHK013 Is "explicit blocked deferral with named cause" (US2 scenario 5, FR-010, FR-022) defined with at least one worked example so reviewers can recognize a compliant deferral? [Clarity, Spec §FR-010] — FR-010 provides example "ROCm SDMA path unavailable on this kernel" or "Paddle wheel mismatch".
- [X] CHK014 Is the boundary between "demo runbook" and "operator runbook" / other operator documentation unambiguous (i.e., one canonical document is named)? [Clarity, Spec §FR-025, Gap] — R-021.5 pins `runbook-gpu-mvp-demo.md` distinct from `ollama-runtime.md`, `gpu-warmup-and-cache.md`.
- [X] CHK015 Is "material decrease" anchored in every requirement that uses it (FR-016, SC-006, US3 scenario 3) to the same FR-015 formula, with no synonym drift? [Clarity, Consistency] — FR-016 explicitly says "(per the FR-015 formula)"; SC-006 + US3-3 use the same threshold semantics.
- [X] CHK016 Is "scratch root" (FR-018) defined precisely enough that an automated check could detect a violating write into `tests/stage1_vendor_identity/`? [Clarity, Measurability] — FR-018 names `/tmp` as default scratch root; SC-011 + Polish T032 give the `git status` detection mechanism.
- [X] CHK017 Is the difference between "stay opt-in" and "promote to default" stated in operator-visible terms (which flag/env var defaults change, and which test exercises the legacy path)? [Clarity, Spec §FR-026, §FR-028] — FR-026/-028 specify the flag (`--evidence-gate-skip-fallback`) + env var (`DARTWING_EVIDENCE_GATE_SKIP_FALLBACK`); T029 names the inverted-default code location; T030 names the legacy-path test path.

### Requirement Consistency

- [X] CHK018 Do all references to the canonical extraction profile name `ollama@gpu` (FR-025, US5 narrative, US5 scenario 2, US1 scenario 3, Clarifications §2026-05-18) match without synonym drift to `full-workstation`? [Consistency, Spec §FR-025] — Q4 Clarification resolved; spec swept across the four /analyze rounds.
- [X] CHK019 Do FR-014 (record every emitted `phase_timings.*` key) and FR-017 (record `evidence_gate_state_counts` et al.) together specify a non-overlapping recording contract? [Consistency, Completeness] — Two disjoint axes: phase timings vs. gate-state metadata.
- [X] CHK020 Are the four-run discipline names ("warmup", "legacy-default ×2", "candidate ×2") consistent across PRD §Scope, FR-012, US3 narrative, and the Benchmark Run Record entity? [Consistency, Spec §FR-012] — Verified identical.
- [X] CHK021 Are the seven `run_summary` observability field names (`schema_version`, `preprocess_lane`, `preprocess_strategy_id`, `evidence_gate_id`, `evidence_gate_state_counts`, `evidence_gate_documents`, `evidence_gate_suppressed_fallback_count`) listed identically in FR-025(d) and US5 scenario 4? [Consistency, Spec §FR-025] — Verified.
- [X] CHK022 Are the five benchmark document IDs (`inv_001_easy`, `inv_002_easy`, `inv_006_medium`, `inv_011_hard`, `inv_012_hard`) reused identically in FR-011, US3 narrative, and Assumptions? [Consistency, Spec §FR-011] — Verified.
- [X] CHK023 Does FR-027 ("FAIL/BLOCKED ⇒ stay opt-in") align with FR-021 / FR-022 ("skip-fallback MUST remain opt-in" on regression/blocker) — i.e., is the requirement to keep opt-in stated only once with cross-references, or risk duplicate-source drift? [Consistency] — Aligned: FR-027 is the promotion-level rule; FR-021/-022 are the quality-gate-level restatements. No contradiction.
- [X] CHK024 Is the prohibition on automatic promotion (FR-029) consistent with the PASS-permits-promotion language in US4 scenario 3 and US6 scenario 2 (PASS enables but does not perform promotion)? [Consistency] — Consistent: PASS *permits*; explicit team decision *performs*.
- [X] CHK025 Are FR-003 ("interpreter path visible") and the Q3 clarification ("preflight is authoritative, path is forensic only") consistent — i.e., no remnant text suggests interpreter-path-matching is a gate? [Consistency, Spec §FR-003] — FR-003 now explicitly says "forensic only".

### Acceptance Criteria Quality

- [X] CHK026 Are SC-001 through SC-011 each phrased as a measurable, single-state outcome (no "and/or" compound criteria that hide a multi-state success surface)? [Measurability, Spec §Success Criteria] — Each SC has a single binary state ("preceded by both checks", "abort with non-zero", etc.); content lists are coherent.
- [X] CHK027 Can SC-002 ("100% of runs abort … Zero runs silently fall back") be objectively verified from run records alone, without operator testimony? [Measurability, Spec §SC-002] — Non-zero exit + named stderr is record-checkable.
- [X] CHK028 Can SC-004 ("Zero formerly-deferred items remain silently inert") be objectively counted from the four US2 scenarios — i.e., is the universe of formerly-deferred items closed and enumerated? [Measurability, Spec §SC-004] — Closed set: US2 scenarios 1–4 plus the quality-gate test from US4 (mapped by T036 SC→task table).
- [X] CHK029 Can SC-005 ("sufficient for a third party to re-derive the promotion verdict without re-running") be operationalized — is "third party" defined, and is the re-derivation procedure implicit in the recorded data? [Measurability, Spec §SC-005] — contracts/appendix-recording.md operationalizes "third party = any pipeline contributor" + re-derivation procedure (apply FR-015 formula to recorded numbers).
- [X] CHK030 Is SC-006's "any other key crossing the jitter band … is recorded as a finding" measurable against a closed list of `phase_timings.*` keys, or open-ended (drift risk)? [Measurability, Spec §SC-006, §FR-014] — FR-014 enumerates the closed list.
- [X] CHK031 Is SC-008 ("zero CPU-fallback commands … new operator can complete the demo without source-code consultation") testable by inspection of the runbook file alone? [Measurability, Spec §SC-008] — `grep -E '@cpu|stub-voter'` returns zero matches; tasks T024 + T033 enforce.
- [X] CHK032 Is SC-009's "at least one test that passes" precise about which test framework, suite, or location holds the legacy-path test? [Measurability, Spec §SC-009, Gap] — T030 names `tests/unit/preprocessing/test_skip_fallback_explicit_off_legacy.py` running under `pytest -m 'not gpu'`.

### Scenario Coverage

- [X] CHK033 Are primary-flow requirements complete for each user story's golden path (readiness → benchmark → quality gate → record → decide)? [Coverage, Spec §User Scenarios] — Each US has an Independent Test + Acceptance Scenarios covering its golden path.
- [X] CHK034 Are alternate-flow requirements defined for the `--gpu-warmup` exception case (US2 scenario 4, FR-009, Edge Cases)? [Coverage, Alternate Flow] — US2-4 + FR-009 + Edge Case "`--gpu-warmup` is set AND every document is `sufficient`".
- [X] CHK035 Are exception-flow requirements complete for each fail-fast trigger (preflight non-success, Ollama CPU/partial, runtime error mid-benchmark)? [Coverage, Exception Flow] — Preflight via FR-001/-004; Ollama via FR-002/Edge Cases; mid-benchmark via R-021.12 partial-recording.
- [X] CHK036 Are recovery-flow requirements defined for the case where a quality-gate FAIL is observed (re-run? abandon? requalify the corpus?) — the PRD §Fallback specifies posture but not recovery actions? [Coverage, Recovery Flow, Gap] — **deferred to future ops feature**: Fallback discipline defines the operational *posture* (stay opt-in, CPU/stub baseline, blocked evidence recorded) but does NOT specify *recovery procedures* (re-run cadence, requalification triggers, abandonment criteria). The recovery-procedure surface belongs to a future ops feature, not to this validation/promotion slice.
- [X] CHK037 Are non-functional requirements present for performance jitter (FR-015), observability (FR-025 fields), reliability (fail-fast posture), and security (PII discipline preserved from feature 020)? [Coverage, Non-Functional] — All four axes covered.
- [X] CHK038 Are requirements present for the case where the demo runbook is consumed by a reviewer who never runs it (read-only audit path)? [Coverage, Audience Variant, Gap] — **deferred**: spec does not explicitly address a read-only audit consumer (the runbook is optimized for the runner-operator persona). Low-impact; the runbook content is plain English readable by an auditor without execution. No spec amendment required for this slice.

### Edge Case Coverage

- [X] CHK039 Are all 9 listed Edge Cases each tied to at least one FR that produces the required behavior? [Coverage, Spec §Edge Cases] — (1) Paddle-pass/Ollama-CPU→FR-002, (2) Ollama-pass/Paddle-fail→FR-001, (3) wrong-interpreter→FR-001/-004, (4) all-sufficient/no-warmup→FR-008, (5) warmup+all-sufficient→FR-009, (6) first-run-cold→FR-012, (7) latency-up/quality-down→FR-020/-021, (8) corpus-mutation→FR-018, (9) GPU-unavailable→Fallback.
- [X] CHK040 Is the "first run after a long cache-cold interval dominates timing" edge case mapped to a discardable run in the four-run discipline (FR-012)? [Coverage, Spec §Edge Cases, §FR-012] — Yes, FR-012 + the rationale link.
- [X] CHK041 Is the "accidentally targets committed corpus folders" edge case mapped to an enforceable rule (FR-018) and a procedural-finding recording requirement? [Coverage, Spec §Edge Cases, §FR-018] — Edge Case + FR-018 + SC-011 + Polish T032 (`git status`).
- [X] CHK042 Is the "GPU hardware unavailable for the entire promotion attempt" edge case mapped to the full Fallback discipline (skip-fallback off, CPU/stub CI baseline, GPU paths fail-fast, blocked evidence recorded)? [Coverage, Spec §Edge Cases, §Fallback] — Fallback blockquote at spec front-matter covers all four.

### Non-Functional Requirements

- [X] CHK043 Are performance-measurement requirements (FR-014 phase keys + FR-015 jitter formula) sufficient to reproduce the comparison without re-instrumenting? [Non-Functional, Performance] — Enumerated phase-key list + pinned formula = reproducible.
- [X] CHK044 Are observability requirements (FR-025(d), FR-003 interpreter visibility) sufficient to reconstruct lane and interpreter facts from any single benchmark/demo run record? [Non-Functional, Observability] — FR-025(d) gives 7 fields; FR-003 + Paddle preflight stderr provides interpreter; T015 records both into Appendix A env fingerprint.
- [X] CHK045 Are reliability requirements (FR-001 preflight, FR-002 Ollama check, FR-004 fail-fast) sufficient to prevent silent CPU runs under GPU labels? [Non-Functional, Reliability] — Composite verdict gate prevents silent CPU.
- [X] CHK046 Are PII/security requirements preserved at the feature-020 level (no new persisted artifact, no new credential surface) — i.e., does FR-032 cover the security-surface preservation? [Non-Functional, Security, Spec §FR-032] — FR-032 enumerates all new-product-behavior prohibitions.

### Dependencies & Assumptions

- [X] CHK047 Are all six Assumptions individually testable — i.e., could a reviewer falsify each assumption against the actual workstation state? [Dependency, Spec §Assumptions] — Each Assumption is testable (ROCm via preflight; Ollama via `/api/ps`; 5-doc subset via filesystem; feature-020 via `git log`; evaluator via import; full-workstation by absence). Spec actually carries 8 Assumptions; the "six" in this CHK is the original count and is conservatively encompassed.
- [X] CHK048 Is the dependency on feature 020 (PR #38 + stacked PRs on `main`) explicit enough that a reviewer can verify it before this feature is approved for landing? [Dependency, Spec §Assumptions] — Assumptions §4 + §5 name the specific PRs and emitted symbols.
- [X] CHK049 Is the dependency on the feature 007 evaluator surface bounded (used as-is) versus modifying it (out of scope)? [Dependency, Spec §Assumptions, §FR-019] — Assumptions §6: "This feature uses the existing evaluator surface; it does not modify it."
- [X] CHK050 Is the dependency on `scripts/start-host-ollama-rocm-wsl.sh` (host Ollama) named, and is the script's role in the readiness gate vs. ambient prerequisite distinguished? [Dependency, Spec §Assumptions] — Assumptions §2 names it as the ambient startup path; the readiness gate (FR-002) is the check, not the startup script.

### Ambiguities & Conflicts

- [X] CHK051 Is every term resolved by Session 2026-05-18 Clarifications applied uniformly across the spec (no residual ambiguity in sections not explicitly edited)? [Ambiguity, Spec §Clarifications] — Verified by the four /speckit.analyze rounds (zero open findings).
- [X] CHK052 Is there any residual conflict between Assumptions §"`full-workstation` not used" and historical references to `full-workstation` in PRD §Scope item "extraction: `ollama@gpu` or the `full-workstation` preset"? [Conflict, Spec §Assumptions] — Q4 Clarification reconciled; PRD reference is historical context.
- [X] CHK053 Is the procedural-finding handling for a `tests/stage1_vendor_identity/` mutation (Edge Cases) explicit about invalidating the Appendix A/B entry, or only about the operator's awareness? [Ambiguity, Spec §Edge Cases] — Edge Case: "the run output is invalid for Appendix A/B until re-run against scratch".
- [X] CHK054 Is the spec free of "may", "should", or "could" used in normative positions — every requirement uses "MUST" / "MUST NOT" without softer hedges? [Clarity, Spec-wide] — All FRs use MUST/MUST NOT. The few "should"s in Edge Cases are in descriptive narrative explaining expected behavior, not in normative requirements.
