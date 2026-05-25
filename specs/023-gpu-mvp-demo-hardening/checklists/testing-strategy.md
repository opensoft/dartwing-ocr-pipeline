# Testing Strategy Requirements Quality Checklist: GPU MVP Demo Hardening

**Purpose**: Release-gate audit of testing-strategy-related requirements quality — the CPU-isolated pytest coverage (SC-008), the workstation-only manual GPU smoke gate, fixture/stub strategy, and traceability from tests to FRs.
**Created**: 2026-05-24
**Feature**: [spec.md](../spec.md)

## CPU-Isolated Pytest Coverage

- [ ] CHK001 Is the CPU-isolated pytest coverage scope defined precisely — which surfaces are tested (CLI flow, exit-code table, readiness failure classes, report shape) and which are not? [Clarity, Spec §SC-008]
- [ ] CHK002 Is the stubbing strategy specified for Ollama (a fake HTTP server, in-process mock, recorded fixtures)? [Completeness, Gap]
- [ ] CHK003 Is the stubbing strategy specified for Paddle ROCm preflight (a fake preflight, a marker that skips Paddle import on CI)? [Completeness, Gap]
- [ ] CHK004 Are tests for every closed-vocabulary readiness check (8 named checks) required to exist, so the vocabulary is exercised end-to-end? [Coverage, Spec §FR-016/SC-008]
- [ ] CHK005 Are tests for every exit code (0–5) required to exist, so the exit-code table is exercised? [Coverage, Spec §FR-021/SC-008]
- [ ] CHK006 Are tests for every `runtime_outcome` value (6 entries) required to exist? [Coverage, Spec §FR-020/SC-008]
- [ ] CHK007 Are tests for every `quality_status` value (3 entries) required to exist? [Coverage, Spec §FR-010/SC-008]

## Report-Shape Testing

- [ ] CHK008 Are tests required to assert the stdout-JSON-only invariant (no human-readable text on stdout) on every outcome class? [Coverage, Spec §FR-019/SC-009/SC-008]
- [ ] CHK009 Are tests required to assert `schema_version` presence and value on every outcome? [Coverage, Spec §FR-024/SC-008]
- [ ] CHK010 Are tests required to assert `phase_timings` shape (all 4 keys, `null` for unreached) on partial-run outcomes? [Coverage, Spec §FR-025/SC-008]
- [ ] CHK011 Are tests required to assert `--check-only` produces the same `kind` and `schema_version` with null runtime/quality/timing/artifact fields (FR-025a)? [Coverage, Spec §FR-025a/SC-008]

## Workstation-Only GPU Smoke Gate

- [ ] CHK012 Is the workstation-only manual GPU smoke gate's execution protocol defined (who, when, what evidence)? [Clarity, Spec §SC-008]
- [ ] CHK013 Is the smoke gate's pass/fail criterion explicit — three consecutive runs satisfying SC-006? [Measurability, Spec §SC-006/SC-008]
- [ ] CHK014 Is the smoke gate's failure-handling protocol defined (what happens if it fails — block the merge? require sign-off?)? [Coverage — Recovery, Gap]
- [ ] CHK015 Is the smoke gate's evidence required to be captured in the runbook (rather than oral)? [Traceability, Spec §SC-008, Gap]

## Test-to-FR Traceability

- [ ] CHK016 Is there a requirement that every functional requirement (FR-001 through FR-027) is exercised by at least one CPU-isolated test (or explicitly justified as workstation-only)? [Traceability, Gap]
- [ ] CHK017 Is the spec explicit about which FRs are *not* CPU-testable (e.g., FR-002 Paddle ROCm preflight on a CPU CI, FR-012 post-run device interrogation)? [Coverage, Gap]
- [ ] CHK018 Is a coverage matrix (FR ↔ test name) required as a deliverable, mirroring the SC-010/FR-032 coverage matrix in feature 022? [Traceability, Spec §SC-008, Gap]

## CI vs Workstation Boundary

- [ ] CHK019 Is the CI execution environment specified (no ROCm, no Paddle GPU, no host Ollama)? [Clarity, Spec §SC-008]
- [ ] CHK020 Is the CI test skip behavior defined for tests that *cannot* run on CI (skip vs xfail vs hard-fail)? [Coverage, Gap]
- [ ] CHK021 Are workstation-only tests required to be marked (e.g., pytest marker `@pytest.mark.gpu`) so CI does not attempt them? [Completeness, Gap]

## Fixture Corpus

- [ ] CHK022 Is the use of the canonical demo fixture (`tests/stage1_vendor_identity/inv_001_easy/`) for end-to-end smoke tests specified? [Completeness, Spec §Assumptions]
- [ ] CHK023 Are additional synthetic fixtures (e.g., a fixture without `source.pdf` to exercise exit-2; a fixture without `semantic_table_truth.json` to exercise warn-and-skip) required? [Coverage, Spec §FR-022/FR-027, Gap]
- [ ] CHK024 Is the fixture-availability requirement (does the corpus contain a "GPU is not available" stub fixture for negative-path tests?) addressed? [Coverage, Gap]

## Regression Gates

- [ ] CHK025 Is the relationship between SC-008's CPU pytest coverage and the existing project test infrastructure (`tests/contract_tests/`, byte-identity baselines from feature 022) specified? [Consistency, Spec §SC-008, Gap]
- [ ] CHK026 Are byte-identity regression tests on `preprocess_output.json` / `routing_decision.json` / `final_structured_payload.json` (for the canonical fixture across three runs) required as part of SC-006 verification? [Coverage, Spec §SC-006, Gap]

## Test Resilience

- [ ] CHK027 Are tests required to be deterministic (e.g., the Ollama stub returns fixed bytes)? [Coverage — Non-Functional, Gap]
- [ ] CHK028 Are timing-sensitive tests (e.g., 10 s preflight bound) required to have a generous CI margin so flakiness is avoided? [Coverage — Non-Functional, Spec §SC-007, Gap]

## Primary / Alternate / Exception / Recovery / Non-Functional Coverage

- [ ] CHK029 Are test requirements defined for the **primary** flow (CPU stub: clean folder → all readiness pass → all phases simulated → success report)? [Coverage — Primary, Spec §SC-008]
- [ ] CHK030 Are test requirements defined for **alternate** flows (`--check-only`, `--with-evaluator`, `--preset full-ocr`, custom `--document-folder`)? [Coverage — Alternate, Spec §SC-008]
- [ ] CHK031 Are test requirements defined for **exception** flows (each readiness check failing in isolation; each phase failing; timeout)? [Coverage — Exception, Spec §SC-008]
- [ ] CHK032 Are test **recovery** requirements defined (re-run after partial failure produces clean state per FR-017)? [Coverage — Recovery, Spec §FR-017]
- [ ] CHK033 Are test **non-functional** requirements specified (CPU test suite completes in a CI-friendly time bound; tests don't require network access)? [Coverage — Non-Functional, Gap]

## Ambiguities & Conflicts

- [ ] CHK034 Is the conflict between SC-008 (CPU pytest with stubbed dependencies) and FR-002 (must run from `.venv-paddle-rocm`) resolved — i.e., is the venv requirement bypassable under stub mode? [Conflict, Spec §FR-002/SC-008]
- [ ] CHK035 Is the precedence between unit tests (per-function) and integration tests (CLI + stubs) specified so authors know where to land coverage? [Coverage, Gap]


---

**Plan coverage verification (2026-05-25):** see [plan-coverage.md](./plan-coverage.md) for the cross-reference of this checklist's items against `plan.md` / `research.md` / `data-model.md` / `contracts/` / `quickstart.md`.
