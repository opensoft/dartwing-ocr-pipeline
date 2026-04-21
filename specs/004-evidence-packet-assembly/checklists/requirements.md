# Specification Quality Checklist: Evidence Packet Assembly (Trijunction-Ready)

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-04-20
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

- Q1 (persistence model), Q2 (candidate signal depth), Q3 (CLI surface) were posed during /speckit.specify and resolved before the spec was finalized — see "Resolved Clarifications" in spec.md. The checklist items "No [NEEDS CLARIFICATION] markers remain" and "All functional requirements have clear acceptance criteria" passed once the answers landed in FR-008, FR-015a/b/c, and FR-020.
- One follow-on contract task is implied by Q1's resolution: a new `evidence_packet.schema.json` and an amendment to `folder.schema.json` (legalizing `evidence_packet.json` as an optional generated file). That work belongs in /speckit.plan and /speckit.tasks, not in the spec.
- Spec is ready for `/speckit.clarify` (optional) or `/speckit.plan`.

---

# Requirements Quality Deep-Dive (release-gate)

**Appended by /speckit.checklist on 2026-04-20.**
**Purpose**: Deeper unit-tests-for-English over the finalized spec, covering
completeness, clarity, consistency, measurability, scenario coverage, edge
cases, non-functional requirements, dependencies, and residual ambiguities.

## Requirement Completeness

- [x] CHK113 Are input preconditions fully enumerated (folder existence, file existence, JSON parseability, schema validity)? [Completeness, Spec §FR-001..FR-003]
- [x] CHK114 Are all three Trijunction source slots required by name in the packet contract? [Completeness, Spec §FR-004]
- [x] CHK115 Are the two sides of the packet shape (structural evidence vs. candidate signals) each enumerated with required sub-keys? [Completeness, Spec §FR-006..FR-008]
- [x] CHK116 Is every user story's acceptance-test "independent test" paragraph matched by at least one Acceptance Scenario? [Completeness, Spec §US1..US4]
- [x] CHK117 Is every Success Criterion traceable back to at least one Functional Requirement? [Traceability, Spec §SC-001..SC-009]
- [x] CHK118 Is the public Python API surface (two entry points) documented at spec level, not just plan level? [Completeness, Spec §FR-019]

## Requirement Clarity

- [x] CHK119 Is "Trijunction-ready" defined as shape-ready (not behavior-ready) with consequences spelled out? [Clarity, Spec §Assumptions]
- [x] CHK120 Is "voter-agnostic" defined with measurable criteria (no voter/model/prompt strings in the packet)? [Clarity, Spec §FR-009 §US3]
- [x] CHK121 Is "deterministic" defined with a specific measurable test (byte-identical over N runs)? [Clarity, Spec §FR-011 §SC-002]
- [x] CHK122 Is "unverified" defined as a literal provenance string, not a freeform description? [Clarity, Spec §FR-008]
- [x] CHK123 Is "debug/verbose logging" defined precisely in terms of Python's `logging` module level? [Clarity, Spec §Clarifications Q1 §FR-015b]
- [x] CHK124 Is "in-memory only" defined as "returns the packet to the caller and writes nothing to disk"? [Clarity, Spec §FR-015a]
- [x] CHK125 Are the four regex hint categories named (emails, URLs, US phones, EIN-shaped tax IDs) with the scope of each bounded? [Clarity, Spec §FR-008]

## Requirement Consistency

- [x] CHK126 Are the Trijunction source names consistent across spec, data model, and CLI contract (`paddleocr_vl`, `falcon_ocr`, `falcon_perception`)? [Consistency]
- [x] CHK127 Is the `contract_set_version` value consistent across FR-013, Research Decision 1, data-model.md, and the cli-contract? [Consistency]
- [x] CHK128 Is the "company-name stays null in stage 1" rule consistent across §FR-008, §Resolved Clarifications Q2, and data-model.md? [Consistency]
- [x] CHK129 Are the persistence-trigger rules consistent across §FR-015a, §FR-015b, §FR-020, and the cli-contract? [Consistency]
- [x] CHK130 Is the amendment path consistent between §FR-015c and `AMENDMENTS.md` step 1 (MINOR, additive)? [Consistency, Spec §Research Decision 1]
- [x] CHK131 Does the spec use the same term ("regex hint" / "candidate signal") consistently, rather than switching between synonyms? [Consistency, Spec §FR-008 §Key Entities]

## Acceptance Criteria Quality

- [x] CHK132 Can every Success Criterion be objectively evaluated by an automated test (no "looks right", no "reasonable")? [Measurability, Spec §SC-001..SC-009]
- [x] CHK133 Is SC-001's "well under one second" quantified (e.g. p95 latency < 500ms on a named reference profile)? [Measurability, Spec §SC-001]
- [x] CHK134 Is SC-009's "easy-bucket subset" specified by size / folder prefix so the grader knows which documents count? [Clarity, Spec §SC-009]
- [x] CHK135 Is SC-009's "correctly surface" defined (recall only? precision allowed to be low? exact-match?)? [Clarity, Spec §SC-009]
- [x] CHK136 Is SC-007's "exactly one file" measurable by listing the directory before/after? [Measurability, Spec §SC-007]

## Scenario Coverage (Primary / Alternate / Exception / Recovery / Non-Functional)

- [x] CHK137 Is the **primary** scenario (valid input, default logger) covered by at least one acceptance scenario? [Coverage, Spec §US1 AC#1]
- [x] CHK138 Is the **alternate** scenario (valid input, DEBUG logger — persistence path) covered? [Coverage, Spec §US1 AC#5 §US4 AC#2]
- [x] CHK139 Is the **exception** scenario (invalid / missing input) covered? [Coverage, Spec §Edge Cases §FR-017]
- [x] CHK140 Is the **recovery** scenario (re-run produces identical output, no cleanup required) covered? [Coverage, Spec §Edge Cases]
- [x] CHK141 Is a **non-functional** scenario (byte-identical determinism, zero-file default, exactly-one-file DEBUG) covered? [Coverage, Spec §SC-002 §SC-007]
- [x] CHK142 Are **zero-data** scenarios (zero-page, empty `document_text`) explicitly covered as a first-class case, not an afterthought? [Coverage, Spec §Edge Cases]

## Edge Case Coverage

- [x] CHK143 Are regex-spurious-match edge cases addressed (e.g. tracking number shaped like a phone)? [Coverage, Spec §Edge Cases]
- [x] CHK144 Are partial-failure / step-failure states from 003 explicitly covered in assembly requirements? [Coverage, Spec §Edge Cases §FR-018]
- [x] CHK145 Are read-only-folder edge cases covered when DEBUG is set? [Coverage, Spec §Edge Cases]
- [x] CHK146 Are re-run-with-existing-packet-file semantics covered (overwrite with identical bytes)? [Coverage, Spec §Edge Cases]
- [x] CHK147 Are duplicate regex matches in the same document covered (no-dedup rule)? [Coverage, Spec §Clarifications Q4]

## Non-Functional Requirements

- [x] CHK148 Is the latency soft target stated without being elevated to a release gate (consistent with the constitution's stage-1 rule)? [Consistency, Spec §SC-001]
- [x] CHK149 Are the zero-network / zero-GPU / zero-Ollama constraints stated explicitly? [Completeness, Spec §Dependencies §Out of Scope]
- [x] CHK150 Are logging level and log-output requirements (stderr, formatter) specified for the CLI? [Completeness, Spec §CLI Contract]
- [x] CHK151 Is backward-compat for `preprocess_output` v1.0.0 → assembler v1.1.0 stated? [Completeness, Spec §Research Decision 1]

## Dependencies & Assumptions

- [x] CHK152 Are all upstream dependencies named (003 merged on main, frozen contract set)? [Completeness, Spec §Dependencies]
- [x] CHK153 Is the downstream dependency on 005 (single-voter extraction) identified as the primary consumer of the API? [Completeness, Spec §Dependencies]
- [x] CHK154 Are all assumptions listed with a way to verify each (e.g. "confirmed: 003 PR #2 merged into main on 2026-04-20")? [Traceability, Spec §Assumptions]
- [x] CHK155 Is the "no new runtime dependencies" assumption stated so reviewers can enforce it at PR time? [Completeness, Spec §Technical Context §Dependencies]

## Ambiguities & Conflicts

- [x] CHK156 Does the spec state whether `raw_ocr_lines[]` is passed through the packet or only implicitly referenced via `pages[]`? [Resolved — data-model.md says `pages[]` is a verbatim passthrough, which includes `raw_ocr_lines`]
- [x] CHK157 Does the spec reconcile "source line/offset references when available" (spec) with the clarified "all four fields non-null" (Q5 answer)? [Resolved — Q5 supersedes "when available"; spec updated accordingly]
- [x] CHK158 Is there a rule for how `assemble_from_preprocess(document_id=None)` resolves `document_id`? [Resolved — cli-contract.md states "defaults to `preprocess_output["document_id"]`"]
- [x] CHK159 Is the behavior spelled out when a future-populated `ingestion_sources` source arrives with a `status` value NOT in the current closed vocabulary (`success`/`failure`/`not_implemented`)? [Gap — implicit "reject at schema validation"; worth stating]

## Notes (deep-dive)

- Check items off as completed: `[x]`
- Flag unresolved `[Gap]` / `[Ambiguity]` / `[Conflict]` items for spec amendment before implementation begins
- Resolved items are marked `[Resolved — …]` inline to leave a visible audit trail
