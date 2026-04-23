# Specification Quality Checklist: PPStructureV3 Preprocessing Migration

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-04-22
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

- This is an internal infrastructure migration: the "users" are internal pipeline developers, corpus-labeling operators, and infra owners. "Business stakeholder" framing is adapted accordingly.
- Implementation-level specifics (exact engine package names, config flag names, upstream bug identifiers, fallback mechanics) live in `docs/stage1-vendor-identity/prd-ppstructurev3-migration.md` and are referenced from the spec, not duplicated. This keeps the spec testable-requirements-shaped while the PRD carries the technical narrative.
- FR-015 and a handful of Assumption/Dependency entries reference "upstream model hosters" and "upstream engine bug" in the abstract. Concrete identifiers stay in the PRD to avoid engine-specific drift inside the spec.
- Ready to proceed to `/speckit.clarify` (no pending NEEDS CLARIFICATION markers; re-run if the checklist-gate discussion below surfaces new ambiguity) or directly to `/speckit.plan` if the plan step should pick up the assumptions verbatim.

---

## Full-Spec Quality Pass (appended 2026-04-23, post-clarify Q16–Q19 + post-plan re-run)

**Purpose**: Standard-depth "unit tests for English" across the complete spec — all 22 FRs, 8 SCs, 19 clarification Q&As, 7 edge cases, 7 assumptions, 4 dependencies. Validates requirements writing quality (completeness, clarity, consistency, measurability, coverage, edge cases), NOT implementation correctness. Audience: reviewer of `/speckit.tasks` and `/speckit.analyze` re-runs.

### Requirement Completeness

- [ ] CHK001 - Are FR-016 error-recovery requirements specified for the corpus folder state (partially-regenerated or fully-untouched) when engine init fails partway through the FR-010 halt-on-fail sweep? [Completeness, Spec §FR-010, §FR-016]
- [ ] CHK002 - Does the spec require the R-012 PP-OCRv5 default recognition threshold value to be recorded in `research.md` before any corpus-regeneration commit, or only before the feature is considered complete? [Completeness, Spec §FR-007]
- [ ] CHK003 - Are requirements specified for contract-validation behavior when a block or line has `confidence = null` under the new FR-004 rule — is `null` explicitly permitted by the frozen schema? [Gap, Spec §FR-004]
- [ ] CHK004 - Are requirements documented for the case where the FR-010 sweep is resumed after a prior FR-016 halt — is "restart from the top" sufficiently specified for corpus state with pre-existing files? [Completeness, Spec §FR-010]

### Requirement Clarity

- [ ] CHK005 - Is "PP-OCRv5's default recognition threshold" in FR-007 identified by a specific attribute name (e.g., `text_rec_score_thresh`, `drop_score`), or only by reference to "engine default"? [Ambiguity, Spec §FR-007]
- [ ] CHK006 - Is "persist verbatim" in FR-004's confidence rule unambiguous about float-precision rounding applied by JSON serialization (e.g., `json.dumps` float formatting)? [Clarity, Spec §FR-004]
- [ ] CHK007 - Is "richer HTML / cell-level structure" in FR-021 enumerated as a closed list of V3 fields, or left to implementer interpretation of "beyond the schema"? [Ambiguity, Spec §FR-021]
- [ ] CHK008 - Is FR-022's opt-in mechanism named explicitly (e.g., `--write-page-images`) in the requirement text, or only referred to generically as "an explicit CLI flag"? [Clarity, Spec §FR-022]

### Requirement Consistency

- [ ] CHK009 - Do FR-003 and FR-019 use symmetric detail-string templates and symmetric downgrade semantics for their respective silent-empty conditions? [Consistency, Spec §FR-003, §FR-019]
- [ ] CHK010 - Are the FR-004 determinism axes (ordering, bbox encoding, text verbatim, confidence verbatim) aligned with R-005's implementation narrative without gap or conflict? [Consistency, Spec §FR-004]
- [ ] CHK011 - Is the Edge Case "pathological single-block page" reconciled with FR-018's trigger threshold (≥ 2 OCR lines) — i.e., no gray-zone page configuration where the Edge Case applies but FR-018 does not fire (or vice versa)? [Consistency, Spec §Edge Cases, §FR-018]
- [ ] CHK012 - Are FR-015 (no new network deps) and FR-016 (hard-fail on weight-download) consistent with the Assumptions line permitting a one-time first-run warm-up? [Consistency, Spec §FR-015, §FR-016, §Assumptions]

### Acceptance Criteria Quality / Measurability

- [ ] CHK013 - Is SC-005's "first-run wall-clock time" definition unambiguous about whether the measurement includes the one-time ~500 MB weight-download phase, or only engine-ready execution? [Measurability, Spec §SC-005, §Assumptions]
- [ ] CHK014 - Is SC-001's "at least one vendor-identity token" check well-defined for a document whose `expected.json` has all eligible fields (`company_name.value`, address parts, phone, email, website) set to `null`? [Measurability, Edge Case, Spec §SC-001]
- [ ] CHK015 - Is SC-003's "byte-identical" assertion explicit about scoping — content only, or also filesystem metadata (mtime, ownership, permissions)? [Clarity, Spec §SC-003]
- [ ] CHK016 - Does SC-002's grep pattern depend on FR-020's vocabulary being closed, and is that coupling called out so that extending FR-020's vocabulary requires a matching SC-002 update? [Traceability, Spec §SC-002, §FR-020]

### Scenario Coverage

- [ ] CHK017 - Are requirements defined for a page where `raw_ocr_lines > 0 AND blocks > 0` but zero blocks geometrically contain any OCR line's bbox — does any FR fire, or is this a silent acceptance path? [Coverage, Gap]
- [ ] CHK018 - Are requirements specified for encrypted or password-protected PDFs encountered during an FR-010 corpus sweep — does preprocessing hard-fail (FR-016 umbrella) or skip-and-continue? [Exception Flow, Gap, Spec §FR-010, §FR-016]

### Edge Case Coverage

- [ ] CHK019 - Is the Edge Case "legitimately blank page" operationalized consistently with FR-002's operational definition of "page has legible text" (`len(raw_ocr_lines) > 0`) — does exactly one path apply per page? [Consistency, Spec §Edge Cases, §FR-002]
- [ ] CHK020 - Are requirements specified for a page where FR-018 (suspicious single-block) and FR-006 (unknown layout label) both fire simultaneously — does FR-020 ordering produce a deterministic output? [Coverage, Gap, Spec §FR-018, §FR-006, §FR-020]

### Dependencies & Assumptions

- [ ] CHK021 - Is the Assumption about "upstream model hosters" being available (Dependencies §Upstream model weights) stated in testable terms — e.g., what counts as "unreachable for > 1 week" for R-010 fallback trigger #3? [Measurability, Spec §Dependencies, R-010]

### Ambiguities & Conflicts

- [ ] CHK022 - Does FR-021's "projected into the v1.0.0 schema shape" create a forward-compatibility hazard if a future AMENDMENTS entry adds optional cell-level fields — is the intent "strict current shape" or "any v1.0.0-valid superset"? [Ambiguity, Conflict risk, Spec §FR-021]

---

**Run summary**:
- Focus areas: full-spec requirements quality (all 22 FRs, 8 SCs, edge cases, assumptions, dependencies)
- Depth: standard (22 items across 8 quality dimensions)
- Actor/timing: reviewer pre-/speckit.tasks and pre-/speckit.analyze re-runs
- Must-haves: coverage of the four 2026-04-22 clarifications (FR-004 / FR-007 / FR-021 / FR-022) explicit in CHK002, CHK003, CHK005, CHK006, CHK007, CHK008, CHK010, CHK022
- Traceability: 22 of 22 items reference a Spec §/Gap/Ambiguity marker (100%)

---

## Session 2026-04-23 Append — Post-Clarify Round 3 (CHK023–CHK040)

**Purpose**: Spec-quality items covering the three new Session 2026-04-23 clarifications (Q23 FR-010 broad halt, Q24 FR-021 strict-current-shape, Q25 zero-overlap out-of-scope) + cross-artifact consistency checks surfaced by the /speckit.analyze pass. Each item tests whether the clarification is written well — NOT whether the downstream code matches.

### Requirement Completeness — Session 2026-04-23 Clarifications

- [ ] CHK023 Is the FR-010 halt scope clarification explicit about all three exit codes (`1` / `2` / `3`) rather than relying on "any non-zero" phrasing alone? [Clarity, Spec §FR-010]
- [ ] CHK024 Is the FR-021 "strict-current-shape, as of 010's landing commit" language unambiguous about what "landing commit" means in practice — merge commit, squash commit, or feature-branch HEAD at merge? [Ambiguity, Spec §FR-021]
- [ ] CHK025 Does the spec define a quantified trigger for introducing the future `[orphan_ocr_lines]` category (e.g., "≥ 1 document in the corpus surfaces the condition") rather than leaving it at "if corpus surfaces in practice"? [Gap, Spec §Edge Cases]

### Consistency Between FR-021 and Frozen Contract Policy

- [ ] CHK026 Is the relationship between FR-021 strict-current-shape and the frozen `contract_set_version = "1.0.0"` explicit — does a schema widening always require a contract set version bump, an AMENDMENTS entry, or both? [Consistency, Spec §FR-021 §Assumptions]
- [ ] CHK027 Are requirements specified for the coordination between AMENDMENTS adoption and preprocessing code changes — can AMENDMENTS land without a matching preprocessing PR, or must they co-land? [Gap, Spec §FR-021]
- [ ] CHK028 Is the interaction between Session 2026-04-22 Q17 (FR-021 original "projected into v1.0.0 shape") and Session 2026-04-23 Q24 (FR-021 strict-current-shape tightening) explicitly consistent — does the later session supersede the earlier? [Consistency, Spec §Clarifications]

### Cross-Artifact Traceability

- [ ] CHK029 Are the Session 2026-04-23 clarifications reflected in plan.md's Constraints list (FR-010 broad halt, FR-021 strict-current-shape, zero-overlap edge case out-of-scope)? [Traceability, Spec §Clarifications → plan.md]
- [ ] CHK030 Are the Session 2026-04-23 clarifications reflected in research.md's R-006 (halt scope) and R-014 (projection boundary)? [Traceability, Spec §Clarifications → research.md]
- [ ] CHK031 Are the Session 2026-04-23 clarifications reflected in data-model.md's `Table` entity section? [Traceability, Spec §Clarifications → data-model.md]
- [ ] CHK032 Are the Session 2026-04-23 clarifications reflected in tasks.md — do T035 (sweep) and T052 (tables projection) match the clarified rules without further edits required? [Traceability, Spec §Clarifications → tasks.md]
- [ ] CHK033 Is the CLI contract (`contracts/cli-contract.md`) updated or intentionally left unchanged for FR-010's broadened halt — and is the reasoning explicit? [Traceability, Spec §FR-010, contracts/]

### Clarification-Session Document Quality

- [ ] CHK034 Is the `### Session YYYY-MM-DD` header pattern consistent across all three sessions (2026-04-22 round 1, 2026-04-22 round 2, 2026-04-23)? [Consistency, Spec §Clarifications]
- [ ] CHK035 Does any FR reference the Session 2026-04-23 clarifications by question number (Q23/Q24/Q25) so back-traceability is mechanical, or only by session date? [Traceability, Spec §Clarifications]
- [ ] CHK036 Does the Session 2026-04-23 clarifications section match the quality bar of prior sessions — Q → A bullets with explicit option-selection language, no hedging? [Consistency, Spec §Clarifications]

### Residual Gaps Flagged by /speckit.analyze

- [ ] CHK037 Is the "pivot cost" of the FR-017 fallback (doc-only) still captured after the Session 2026-04-23 broader halt rule — do any new failure modes change the pivot trigger criteria? [Coverage, Spec §FR-017 §FR-010]
- [ ] CHK038 Is the `paddle.seed(0)` determinism axis (R-005) referenced from an FR, or only from research.md? [Gap, Spec §FR-005, research §R-005] 
- [ ] CHK039 Is SC-001's ≥ 3 blocks + vendor-identity-token check required as a scripted (automated) assertion, or left as a quickstart §3 manual walk? [Coverage, Spec §SC-001]
- [ ] CHK040 Do all three checklist files (`determinism.md`, `failure-handling.md`, `requirements.md`) share a consistent pass-tracking pattern (`[ ]` → `[X]` + resolution-notes section) so reviewers can triage at a glance? [Consistency, checklists/]

---

**Run summary (Session 2026-04-23 append)**:
- Focus areas: Session 2026-04-23 clarifications (FR-010 halt, FR-021 strict-current-shape, zero-overlap edge case) + cross-artifact traceability surfaced by /speckit.analyze
- Depth: standard (18 new items CHK023–CHK040)
- Actor/timing: reviewer pre-merge of the combined clarify+plan+tasks change set
- Traceability: 18 of 18 new items reference Spec §/Gap/Ambiguity/Traceability marker (100%)
