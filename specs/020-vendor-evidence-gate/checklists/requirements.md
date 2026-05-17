# Specification Quality Checklist: Deterministic Vendor-Identity Signals And Early Accept Gate

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-05-14
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

- **FR-007 (US4) behavioral shape** was resolved at `/speckit.clarify` Session 2026-05-14 Q1: shape (b) — skip-fallback for OCR-only `sufficient` runs (gated off-by-default on the GPU lane behind an opt-in CLI flag + env-var fallback per FR-012 / FR-013). No `[NEEDS CLARIFICATION]` markers remain.
- The spec deliberately accommodates any of the three FR-007 resolutions without rewriting FR-001–FR-006 or FR-008–FR-028.
- Implementation-shape decisions deferred to `/speckit.plan` were resolved as follows (see `research.md`):
  - **FR-001 signal list** (R-020.3): five signals — vendor-name-candidate, header-band token-density, OCR-detection aggregate confidence, business-suffix-presence, tax-id-shaped-token-presence. Telephone/email/postal-address-shaped tokens are explicitly deferred to a follow-on feature.
  - **FR-005 gate-rule decision table** (R-020.6): v1 explicit decision table — `sufficient` iff `has_name AND has_density AND has_confidence AND (has_suffix OR has_tax_id)`; `insufficient` iff all five at negative level; `borderline` residual. Thresholds: `DENSITY_THRESHOLD = 8`, `CONFIDENCE_THRESHOLD = 0.70`.
  - **FR-006 per-document record shape** (R-020.10): single `run_summary` line carrying aggregate `evidence_gate_state_counts` + per-document `evidence_gate_documents` array (Clarifications Session 2026-05-16 Q3 shape (a)).
  - **FR-007 CLI flag + env-var name** (R-020.1): `--evidence-gate-skip-fallback` + `DARTWING_EVIDENCE_GATE_SKIP_FALLBACK`.
  - **Benchmark subset ID** (R-020.13): same 5-doc subset used by features 017/018/019.
