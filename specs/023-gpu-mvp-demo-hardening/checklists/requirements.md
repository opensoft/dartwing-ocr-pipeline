# Specification Quality Checklist: GPU MVP Demo Hardening

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-05-24
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

- Items marked incomplete require spec updates before `/speckit.clarify` or `/speckit.plan`.
- Validation pass 1 (2026-05-24): all 16 items pass.
  - Content Quality: Spec stays at the operator/maintainer level. Names like `.venv-paddle-rocm`, `scripts/start-host-ollama-rocm-wsl.sh`, `OLLAMA_CONTEXT_LENGTH=2048`, and the four canonical artifact filenames appear because they are operator-visible names already in the repo, not because the spec is prescribing implementation.
  - Requirement Completeness: Zero `[NEEDS CLARIFICATION]` markers. Open decisions (timeout value, canonical fixture, smoke-vs-demo surface, stale-artifact behavior) are documented as Assumptions with sensible defaults so `/speckit.clarify` can probe them as a normal next step rather than blocking on them now.
  - Feature Readiness: Each FR maps to at least one acceptance scenario across US1–US4 (FR-001/009 → US1; FR-002/003/004/005/007/016 → US2/US3; FR-008/017 → US3; FR-010/015 → US4; FR-011/012/013/014/006 → Edge Cases + Out of Scope). SC-001 through SC-006 are all measurable without naming a framework or library.

---

# Cross-Cutting Requirements-Quality Audit (Appended 2026-05-24)

**Purpose**: Cross-cutting dimensions — Completeness, Clarity, Consistency, Acceptance Criteria Quality, Dependencies & Assumptions, Ambiguities & Conflicts — that span every per-domain checklist (`ux`, `api`, `data-model`, `security`, `performance`, `error-handling`, `observability`, `integration`, `configuration`, `idempotency`, `testing-strategy`, `deployment`, `gpu-runtime-readiness`, `demo-report-shape`).

## Completeness

- [ ] CHK001 Are all functional requirements (FR-001 through FR-027 + FR-025a) traced to at least one acceptance scenario across US1–US4 or to an Edge Case bullet? [Traceability]
- [ ] CHK002 Are all named readiness checks (8 entries) covered by at least one Edge Case bullet and one acceptance scenario? [Coverage, Spec §FR-016]
- [ ] CHK003 Are all 6 `runtime_outcome` values covered by at least one acceptance scenario or Edge Case? [Coverage, Spec §FR-020]
- [ ] CHK004 Are all 3 `quality_status` values reachable via documented derivation rules from upstream signals? [Completeness, Spec §FR-010]
- [ ] CHK005 Are all 5 CLI flags (`--check-only`, `--document-folder`, `--voter-config`, `--preset`, `--with-evaluator`) each mapped to an FR? [Traceability, Spec §FR-005/FR-011/FR-018/FR-022/FR-027]
- [ ] CHK006 Are all 6 exit codes (0–5) mapped to at least one outcome class in the FRs/Edge Cases? [Coverage, Spec §FR-021]
- [ ] CHK007 Are all four canonical stage 1 artifacts named identically across FR-009, FR-017, SC-010, and US1? [Consistency, Spec §FR-009/FR-017/SC-010/US1]

## Clarity

- [ ] CHK008 Are all numeric thresholds (600 s timeout, 10 s preflight, schema_version `"0.1.0"`) quantified rather than expressed as adjectives? [Clarity, Spec §FR-008/SC-007/FR-024]
- [ ] CHK009 Are all closed vocabularies (readiness check names, runtime_outcome, quality_status, stalled_phase, ReadinessCheck status) presented in canonical form once, with later references using the same form? [Consistency, Spec passim]
- [ ] CHK010 Are MUST / MUST NOT / MAY uses RFC-2119-aligned, so a reader does not interpret a MAY as a MUST? [Clarity, Spec passim]
- [ ] CHK011 Is each enumerated edge case mapped to (a) the failure class, (b) the resulting `runtime_outcome` or exit code, (c) the operator action? [Completeness, Spec §Edge Cases, Gap]

## Consistency

- [ ] CHK012 Are the readiness check names spelled identically (case + hyphenation) in FR-016, ReadinessCheck entity, US3, SC-003, and Edge Cases (no `Ollama-version` vs `ollama-version` drift)? [Consistency, Spec passim]
- [ ] CHK013 Are the 4 phase names spelled identically across `failed_at_<phase>` (FR-020), `stalled_phase` (FR-020), and `phase_timings` keys (FR-025)? [Consistency, Spec §FR-020/FR-025]
- [ ] CHK014 Are the four canonical artifact filenames spelled identically in every FR / SC / entity that references them? [Consistency, Spec §FR-009/FR-017/SC-010]
- [ ] CHK015 Is the term "demo command" used consistently — not interchanged with "demo path", "smoke path", "smoke/demo command" in load-bearing places? [Consistency, Spec passim]

## Acceptance Criteria Quality

- [ ] CHK016 Are all SC-001 through SC-010 quantifiable or testable (no SC contains "fast", "reliable", "good"; all use numeric or enumerated criteria)? [Measurability, Spec §SC-001..SC-010]
- [ ] CHK017 Does each acceptance scenario (US1–US4 AS1/AS2/AS3) include Given/When/Then with no ambiguous antecedents? [Clarity, Spec §US1..US4]
- [ ] CHK018 Are SC-001 ("fresh operator") and SC-006 ("three consecutive runs") given concrete verification protocols, not just outcome promises? [Measurability, Spec §SC-001/SC-006]
- [ ] CHK019 Is every "MUST NOT" requirement (FR-012, FR-013, FR-014, FR-015) accompanied by a positive criterion an audit can verify? [Measurability, Spec §FR-012..FR-015]

## Dependencies & Assumptions

- [ ] CHK020 Is each Dependency (features 005, 014, 015, 018, 019, 020, 021, 022, host Ollama startup script) traced to at least one FR or Acceptance Scenario where it is invoked? [Traceability, Spec §Dependencies]
- [ ] CHK021 Is each Assumption tested or testable in the CPU-isolated pytest coverage (SC-008), or explicitly out of test scope? [Traceability, Spec §Assumptions/SC-008]
- [ ] CHK022 Are the assumed values (canonical fixture, header-first-v1 preset, OLLAMA_CONTEXT_LENGTH=2048, ~600 s timeout) all promoted to FR/SC level, or explicitly left at Assumption level with rationale? [Consistency, Spec §Assumptions, FR-008/FR-011/FR-027]
- [ ] CHK023 Is the "minimum Ollama version" Assumption (Spec §Assumptions L193, deferred to planning) marked as a planning-time blocker rather than a spec-time blocker? [Clarity, Spec §Assumptions]

## Ambiguities & Conflicts (Cross-Domain)

- [ ] CHK024 Is the Dependencies-section "feature 015 timing fields the demo report *may* surface" reconciled with FR-025's "MUST include phase_timings"? [Conflict, Spec §FR-025/Dependencies]
- [ ] CHK025 Is the Assumptions-section "Bounded timeout default = 600 s" reconciled with FR-008's "MUST apply a 600-second default timeout"? [Consistency, Spec §FR-008/Assumptions]
- [ ] CHK026 Is the FR-005 GPU-placement rule reconciled with the FR-023 minimum-Ollama-version rule, so missing `size_vram` cannot both pass and fail? [Conflict, Spec §FR-005/FR-023]
- [ ] CHK027 Is the FR-017 eager-delete contract reconciled with FR-027's `--document-folder <path>` operator-chosen target (no path-traversal escalation possible)? [Conflict, Spec §FR-017/FR-027]
- [ ] CHK028 Is the FR-025 "always include all 4 phase_timings keys" reconciled with FR-025a's "phase_timings null under `--check-only`" — is the structure null or all-null-values? [Conflict, Spec §FR-025/FR-025a]

## Scenario Class Coverage Sweep (All 5 Classes, All 14 Per-Domain Files)

- [ ] CHK029 Is **Primary** scenario coverage present in every per-domain checklist (ux, api, data-model, security, performance, error-handling, observability, integration, configuration, idempotency, testing-strategy, deployment, gpu-runtime-readiness, demo-report-shape)? [Coverage, Cross-File]
- [ ] CHK030 Is **Alternate** scenario coverage present in every per-domain checklist? [Coverage, Cross-File]
- [ ] CHK031 Is **Exception** scenario coverage present in every per-domain checklist? [Coverage, Cross-File]
- [ ] CHK032 Is **Recovery** scenario coverage present in every per-domain checklist? [Coverage, Cross-File]
- [ ] CHK033 Is **Non-Functional** scenario coverage present in every per-domain checklist? [Coverage, Cross-File]

## Final Audit Hooks

- [ ] CHK034 Are all `[Gap]` markers across all 14 per-domain checklists triaged before `/speckit.plan` runs — addressed in spec, deferred to planning with rationale, or accepted as out-of-scope? [Traceability]
- [ ] CHK035 Are all `[Conflict]` markers across all 14 per-domain checklists resolved before `/speckit.plan` runs (otherwise planning will inherit the conflict)? [Traceability]
- [ ] CHK036 Are all `[Ambiguity]` markers across all 14 per-domain checklists either clarified in spec or pinned to a follow-on `/speckit.clarify` round? [Traceability]


---

**Plan coverage verification (2026-05-25):** see [plan-coverage.md](./plan-coverage.md) for the cross-reference of this checklist's items against `plan.md` / `research.md` / `data-model.md` / `contracts/` / `quickstart.md`.
