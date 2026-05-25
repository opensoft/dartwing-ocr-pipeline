# UX Requirements Quality Checklist: GPU MVP Demo Hardening

**Purpose**: Release-gate audit of requirements-quality on the operator-facing CLI surface, runbook flow, diagnostics, and the "single trusted demo command" promise.
**Created**: 2026-05-24
**Feature**: [spec.md](../spec.md)
**Audience**: Author + reviewer; release gate.

## Operator Surface & Command Discoverability

- [ ] CHK001 Is the canonical demo command name explicitly specified as the single supported entry point and called out as the *only* operator-facing way to run the MVP demo? [Completeness, Spec §FR-001]
- [ ] CHK002 Is the optional console-script alias (`dartwing-gpu-demo`) explicitly marked as optional vs. required, so the runbook can be authored deterministically without ambiguity about which form to teach? [Clarity, Spec §FR-001]
- [ ] CHK003 Are all CLI flags (`--check-only`, `--document-folder`, `--voter-config`, `--preset`, `--with-evaluator`) enumerated in a single place so the operator-facing surface is closed? [Completeness, Spec §FR-005/FR-011/FR-018/FR-022/FR-027]
- [ ] CHK004 Are the relationships between flags (e.g. `--check-only` ignoring `--document-folder`, `--with-evaluator` requiring a sidecar) specified, or are flag interactions left implicit? [Completeness, Spec §FR-018/FR-022]
- [ ] CHK005 Is the order in which an operator must perform setup steps (start host Ollama → ensure model is loaded → ensure venv is active → run the demo command) documented as a sequence in the runbook, not scattered across FRs? [Clarity, Spec §FR-006/SC-001]

## Single-Command Promise (US1)

- [ ] CHK006 Is the "one documented command" wording in US1 unambiguous about whether the operator must also pre-start Ollama, or is Ollama startup part of the same command? [Clarity, Spec §US1]
- [ ] CHK007 Are success criteria specified for a fresh operator who has never seen this repo before, or only for a returning operator? [Coverage, Spec §SC-001]
- [ ] CHK008 Is the "canonical demo invoice" referenced by US1's Independent Test mapped to a specific fixture path so the test is reproducible from spec alone? [Clarity, Spec §US1, §Assumptions]

## Readiness & Diagnostics UX (US2, US3)

- [ ] CHK009 Are the structured-diagnostic fields each named check must produce (e.g., interpreter path for the interpreter/venv check, `/api/ps` excerpt for placement checks) enumerated per check, or only described as "structured context"? [Completeness, Spec §FR-016, ReadinessCheck entity]
- [ ] CHK010 Is the meaning of `pass` / `fail` / `skipped` on each individual readiness check defined precisely enough that an operator can tell a never-attempted check from an attempted-and-passed check? [Clarity, Spec §FR-026]
- [ ] CHK011 Are the operator-visible names of the closed readiness vocabulary consistent across FR-016, the ReadinessCheck entity, SC-003, and the Edge Cases section (no mixing of `ollama-version` vs "Ollama version" without a canonical-form rule)? [Consistency, Spec §FR-016]
- [ ] CHK012 Is the diagnostic format (what was checked, what was observed, what was expected) specified consistently for every named check, or only described once in US3 AS1? [Consistency, Spec §US3 AS1, FR-016]
- [ ] CHK013 Are operator-facing failure messages required to identify the failing check by name in a form the operator can grep for, or only described as "named"? [Clarity, Spec §FR-016]

## Runtime / Quality Separation (US4)

- [ ] CHK014 Are the operator-visible meanings of `pass`, `weak`, and `review_required` defined precisely enough that the operator can decide whether to escalate without parsing the underlying artifacts? [Clarity, Spec §FR-010, US4]
- [ ] CHK015 Is it specified what the operator should *do* when `runtime_outcome == success` but `quality_status == review_required`, or is operator action left implicit? [Completeness, Spec §FR-010, US4]
- [ ] CHK016 Is the "runtime: success / quality: <status>" outcome phrasing in US1 AS2 reconciled with the JSON-only stdout policy in FR-019 (i.e., does this prose appear in stderr or only as a structured field)? [Consistency, Spec §US1 AS2, FR-019]

## Output Channels & Quietness

- [ ] CHK017 Is it specified whether stderr is allowed to be empty on success, or whether at minimum a one-line "demo succeeded" message must appear, so that operators can confirm liveness without parsing JSON? [Completeness, Spec §FR-019]
- [ ] CHK018 Are operator-visible warnings (e.g. "sidecar not found, skipping evaluator") required to be distinguishable from errors on stderr (severity prefix, color, or format), or only required to be present? [Clarity, Spec §FR-022]
- [ ] CHK019 Is the operator-facing behavior on a `--check-only` run defined for the case when readiness *passes* — does stderr say "readiness OK", or does the operator infer success from exit code 0 alone? [Coverage, Spec §FR-018, FR-019]

## Documentation & Runbook Deliverable

- [ ] CHK020 Is the runbook deliverable's exact path (`docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md`) referenced from the spec so the deliverable cannot be silently dropped? [Traceability, Spec §Clarifications Session 2026-05-24]
- [ ] CHK021 Are the operator prerequisites the runbook must cover (Paddle ROCm venv, host Ollama startup script, OLLAMA_CONTEXT_LENGTH, minimum Ollama version) enumerated so the runbook author cannot accidentally omit one? [Completeness, Spec §FR-006/FR-023, Assumptions]
- [ ] CHK022 Is the operator-facing wording on the "reduced/header-first preprocessing path" required to flag this as the *currently supported* MVP GPU path, not as a permanent choice? [Clarity, Spec §FR-011]
- [ ] CHK023 Is documentation responsibility split clearly between the spec (interface contract) and the runbook (operator workflow), so neither duplicates nor contradicts the other? [Consistency, Spec §FR-001/FR-006]

## Primary / Alternate / Exception / Recovery / Non-Functional Coverage

- [ ] CHK024 Are operator-facing requirements defined for the **primary** flow (cold start, full run, success)? [Coverage — Primary, Spec §US1]
- [ ] CHK025 Are operator-facing requirements defined for the **alternate** flow (`--check-only`, `--with-evaluator`, `--preset full-ocr`, custom `--document-folder`)? [Coverage — Alternate, Spec §FR-011/FR-018/FR-022/FR-027]
- [ ] CHK026 Are operator-facing requirements defined for each **exception** class (every named readiness check failing, timeout, runtime failure)? [Coverage — Exception, Spec §FR-016/FR-020]
- [ ] CHK027 Are operator-facing **recovery** requirements defined (what the operator does next after each failure class — e.g., restart Ollama, switch venvs, upgrade Ollama)? [Coverage — Recovery, Gap]
- [ ] CHK028 Are **non-functional** operator-experience requirements (preflight feels "fast" at 10 s; demo command does not hang) specified with thresholds rather than adjectives? [Coverage — Non-Functional, Spec §SC-007/FR-008]

## Ambiguities & Conflicts

- [ ] CHK029 Is the relationship between US3's prose closed vocabulary and FR-016's prose closed vocabulary resolved without drift (same 8 named checks, identical casing/spelling)? [Consistency, Spec §US3, FR-016]
- [ ] CHK030 Is the term "demo command" used consistently throughout the spec, or does it alternate with "demo path", "smoke path", "MVP demo" in ways that could confuse the operator? [Consistency, Spec passim]


---

**Plan coverage verification (2026-05-25):** see [plan-coverage.md](./plan-coverage.md) for the cross-reference of this checklist's items against `plan.md` / `research.md` / `data-model.md` / `contracts/` / `quickstart.md`.
