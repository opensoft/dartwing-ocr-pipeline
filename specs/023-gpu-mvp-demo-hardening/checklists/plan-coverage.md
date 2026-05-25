# Plan Coverage Verification (2026-05-25)

**Purpose:** Re-verify the 15 release-gate checklists (CHK001…CHK040 per file, 517 total items) against the Phase 0/1 planning artifacts produced by `/speckit-plan`:

- `plan.md` (architecture, constitution check, project structure)
- `research.md` (R-023.1 … R-023.20 decisions)
- `data-model.md` (entities, invariants, JSON examples)
- `contracts/cli-contract.md`, `contracts/demo-report-schema.md`, `contracts/readiness-vocabulary.md`
- `quickstart.md` (9 operator + developer paths)

**Scope:** This is a **requirements-quality verification**, not implementation testing. Each item below asks whether the plan addresses, contradicts, or leaves unspecified a requirement-quality concern raised in one of the 14 per-domain checklists. Items use the same `[Dimension, marker]` taxonomy.

**Numbering:** Continues from CHK001 within this file (each file has its own CHK series per `/speckit.checklist` conventions). Cross-references to the original checklist file use the form `[Origin: <file>:CHK###]`.

---

## A. Verification — Conflicts resolved in spec + reflected in plan

The 9 distinct conflicts triaged on 2026-05-24 (see `triage-2026-05-24.md`) were resolved at spec level. The plan should consistently inherit those resolutions. Verify each:

- [ ] CHK001 Does the plan reflect FR-016's fixed-order readiness execution (interpreter/venv → paddle → ollama-reach → ollama-version → ollama-placement → ollama-ctx → schema-validation → runtime-timeout)? [Consistency, Origin: api.md:CHK031, gpu-runtime-readiness.md:CHK036, requirements.md:CHK026 — see `contracts/readiness-vocabulary.md` §"Fixed execution order"]
- [ ] CHK002 Does the plan implement FR-017's symlink-canonicalization + exit-2 on any of the 4 delete failures? [Consistency, Origin: security.md:CHK029, idempotency.md:CHK004, requirements.md:CHK027 — see `contracts/cli-contract.md` §"Idempotency contract" + `data-model.md` §8 lifecycle]
- [ ] CHK003 Does the plan reflect FR-025's "all-4-keys-with-null-values" structure for `phase_timings`? [Consistency, Origin: data-model.md:CHK037, demo-report-shape.md:CHK040, requirements.md:CHK028 — see `data-model.md` §3 + `contracts/demo-report-schema.md` per-outcome matrix]
- [ ] CHK004 Does the plan reflect FR-020's `stalled_phase` always-present (null off timeout)? [Consistency, Origin: demo-report-shape.md:CHK040 — see `contracts/demo-report-schema.md` §"stalled_phase" field reference]
- [ ] CHK005 Does the plan classify stale-context-length runtime errors as `runtime_outcome: failed_at_extraction` with startup-script diagnostic, not a new enum? [Consistency, Origin: error-handling.md:CHK036 — see `contracts/cli-contract.md` exception-mapping table row for `OllamaContextWindowError`]
- [ ] CHK006 Does the plan reject partial-delete (exit 2 if any of the 4 eager-deletes fails) before any pipeline phase runs? [Consistency, Origin: error-handling.md:CHK038 — see `contracts/cli-contract.md` §"Idempotency contract" item 3]
- [ ] CHK007 Does the plan respect FR-008 as the single source of truth for 600 s (not duplicated in Assumptions as a tuning knob)? [Consistency, Origin: performance.md:CHK029, requirements.md:CHK025 — see `plan.md` Technical Context §"Performance Goals"]
- [ ] CHK008 Does the plan allow CPU pytest to stub Paddle preflight without requiring `.venv-paddle-rocm`? [Consistency, Origin: testing-strategy.md:CHK034 — see `research.md` R-023.4 + R-023.5 + `quickstart.md` Path 7]
- [ ] CHK009 Does the plan position feature 015's `phase_timings` as the canonical source (not optional)? [Consistency, Origin: integration.md:CHK008+CHK032, requirements.md:CHK024 — see `research.md` R-023.1 + `plan.md` Dependencies entry for feature 015]

## B. Verification — Spec ambiguities resolved + reflected in plan

- [ ] CHK010 Does the plan pin `OLLAMA_BASE_URL` (default `http://localhost:11434`) as the only Ollama discovery mechanism? [Consistency, Origin: api.md:CHK032 — see `research.md` R-023.14 + `contracts/cli-contract.md` §"Environment variables"]
- [ ] CHK011 Does the plan keep `--check-only` from implying per-doc-folder validity (no `source.pdf` check under `--check-only`)? [Consistency, Origin: error-handling.md:CHK037 — see `contracts/cli-contract.md` §"--check-only contract" item 4 + `contracts/readiness-vocabulary.md` skip rule]

## C. Verification — Spec-resolved gaps reflected in plan

The 13 high-impact gaps resolved in the spec triage should be visibly carried forward in the plan:

- [ ] CHK012 Are all `--check-only` flag interactions (ignores `--document-folder`, `--preset`, `--with-evaluator`) reflected in the CLI contract's flag-interaction table? [Consistency, Origin: configuration.md gaps — see `contracts/cli-contract.md` §"Flag interactions"]
- [ ] CHK013 Is FR-019's UTF-8 + newline-terminated + single-object JSON discipline reflected in both the CLI contract and data-model? [Consistency, Origin: observability.md gaps — see `contracts/cli-contract.md` §"stdout / stderr discipline" + `contracts/demo-report-schema.md` §"Compatibility & versioning"]
- [ ] CHK014 Is the voter-config malformed-YAML / missing-model-field path mapped to exit 2 in the plan? [Consistency, Origin: api.md gaps — see `data-model.md` §6 + `contracts/cli-contract.md` exception-mapping table]
- [ ] CHK015 Is the fixed readiness execution order (R-023's check #) reflected in both the contract and the data-model entity? [Consistency, Origin: gpu-runtime-readiness.md gap — see `contracts/readiness-vocabulary.md` §"Fixed execution order"]
- [ ] CHK016 Is the always-emit DemoRunReport rule (FR-019 + R-023.6 run_id) shown to apply to every outcome class including invalid-input and `--check-only`? [Coverage, Origin: demo-report-shape.md gaps — see `contracts/demo-report-schema.md` §"Outcome → field-population matrix"]

## D. Verification — Planning-deferred items the plan resolved (138 → R-023 mapping)

The triage doc deferred 138 gaps to planning, grouped into 24 categories. Verify each category was addressed:

- [ ] CHK017 Sub-module composition (subprocess vs in-process) — addressed by R-023.1 (in-process); plan picks one mechanism with rationale. [Plan, Origin: api.md / integration.md gaps]
- [ ] CHK018 `pipeline_version` source — addressed by R-023.2 (`importlib.metadata.version("dartwing-ocr")` with `"unknown"` fallback). [Plan, Origin: data-model.md / integration.md / demo-report-shape.md gaps]
- [ ] CHK019 Test fixture / stub strategy — addressed by R-023.4 + R-023.18 (HTTP `MockTransport`, Paddle monkeypatch, fixture corpus folders). [Plan, Origin: testing-strategy.md gaps]
- [ ] CHK020 CI environment markers — addressed by R-023.5 (`@pytest.mark.gpu` + `pytest -m "not gpu"`; no `xfail`). [Plan, Origin: testing-strategy.md / deployment.md gaps]
- [ ] CHK021 Run-UUID / correlation ID — addressed by R-023.6 (UUID4 `run_id`; 8-hex-char stderr prefix). [Plan, Origin: observability.md gaps]
- [ ] CHK022 Log-level / verbosity flag — addressed by R-023.7 (no `--verbose`; fixed `INFO:`/`WARN:`/`ERROR:` prefixes + line-buffered stderr). [Plan, Origin: observability.md / configuration.md gaps]
- [ ] CHK023 Per-phase sub-budgets — addressed by R-023.8 (intentionally not enforced; informal budgets in `contracts/readiness-vocabulary.md`). [Plan, Origin: performance.md gap]
- [ ] CHK024 Cold-vs-warm cache budgets — addressed by R-023.9 (SC-007 is warm-only; FR-008 is cold-or-warm). [Plan, Origin: performance.md / gpu-runtime-readiness.md / idempotency.md gaps]
- [ ] CHK025 Sub-module exit-code mapping — addressed by R-023.3 (exception→exit table in `contracts/cli-contract.md`). [Plan, Origin: error-handling.md / integration.md gaps]
- [ ] CHK026 Minimum Ollama version concrete value — addressed by R-023.10 (pinned at `0.4.0`). [Plan, Origin: gpu-runtime-readiness.md / deployment.md / api.md gaps]
- [ ] CHK027 Diagnostic string format / templates — addressed by R-023.11 (closed-key shape: `checked` / `observed` / `expected` / `remediation`). [Plan, Origin: error-handling.md / observability.md / ux.md gaps]
- [ ] CHK028 Determinism of diagnostic strings — addressed by R-023.11's closed-key format (machine-comparable). [Plan, Origin: idempotency.md / observability.md gaps]
- [ ] CHK029 Field-order stability in JSON output — addressed by R-023.12 (`sort_keys=False`, declaration-order). [Plan, Origin: idempotency.md / observability.md gaps]
- [ ] CHK030 PII / secrets handling in report fields — addressed in the plan structure (no PII in stderr beyond model name; `interpreter_path` and `voter_config_path` are operator-known; sidecar warning prose pinned). [Coverage, Origin: security.md gaps — note: this remains a **partial resolution**; see new gaps below]
- [ ] CHK031 Threat-model documentation — partially addressed by `plan.md` Constitution Check + `research.md` R-023.14 non-localhost soft warning. [Coverage, Origin: security.md gaps]
- [ ] CHK032 Output sanitization (control chars, ANSI) — addressed by R-023.12 (`ensure_ascii=False` + `separators=(",",":")` + single-line discipline). [Coverage, Origin: security.md / observability.md gaps]
- [ ] CHK033 Runbook content / troubleshooting matrix — addressed by R-023.17 (3 new sections; Readiness Failure Recovery Matrix; Three-Run Stability Smoke Procedure). [Plan, Origin: deployment.md / ux.md gaps]
- [ ] CHK034 Coverage matrix as a deliverable — addressed implicitly by `quickstart.md` Path 7's test-coverage table. [Plan, Origin: testing-strategy.md gap]
- [ ] CHK035 Backwards-compat / forward-compat rules — addressed by `contracts/demo-report-schema.md` §"Compatibility & versioning" (additive→patch, new-required→minor, removal→major). [Plan, Origin: api.md / data-model.md / demo-report-shape.md gaps]
- [ ] CHK036 Flag short-form / case-sensitivity — addressed implicitly by `contracts/cli-contract.md` enumerating only long-form flags; no short-form contract. [Coverage, Origin: configuration.md gaps]
- [ ] CHK037 Recovery-action documentation per failure class — addressed by R-023.11's `remediation` field + R-023.17's runbook recovery matrix. [Plan, Origin: error-handling.md / ux.md / gpu-runtime-readiness.md / deployment.md gaps]
- [ ] CHK038 Stderr line buffering & severity prefixes — addressed by R-023.7 (`reconfigure(line_buffering=True)` + fixed prefixes). [Plan, Origin: observability.md gaps]
- [ ] CHK039 Test-to-FR traceability matrix — addressed implicitly by `quickstart.md` Path 7 coverage area table. [Plan, Origin: testing-strategy.md gap]
- [ ] CHK040 Composability with feature 011 stage-runtime profiles — addressed by R-023.19 (NOT composed; sibling CLI). [Plan, Origin: integration.md gap]

## E. Verification — Out-of-scope items respected by plan

The 9 OOS items from the triage should NOT be re-introduced by the plan:

- [ ] CHK041 Concurrent demo execution — plan does not introduce a lock file or concurrent-write guard (still operator discipline per OOS1). [Consistency, Origin: idempotency.md OOS1]
- [ ] CHK042 Auth on host Ollama — plan does not require auth; documents non-localhost target as a soft warning only (R-023.14). [Consistency, Origin: security.md OOS2]
- [ ] CHK043 Multi-workstation deployment — plan target-platform is "Workstation WSL2" only. [Consistency, Origin: deployment.md OOS3]
- [ ] CHK044 Wheel-identity verification for Paddle — plan uses feature 014's preflight as-is; no new wheel-fingerprint check. [Consistency, Origin: security.md OOS4]
- [ ] CHK045 Cache clearance procedures — plan references but does not own (`research.md` R-023.9 defers to feature 016 docs). [Consistency, Origin: idempotency.md OOS5]
- [ ] CHK046 Config file at the demo level — plan keeps configuration via CLI flags + env + voter-config YAML only; no new TOML/YAML. [Consistency, Origin: configuration.md OOS6]
- [ ] CHK047 Credential / secret storage — plan introduces no new credential surface. [Consistency, Origin: security.md OOS7]
- [ ] CHK048 Install / uninstall procedure — plan introduces no installable artifacts. [Consistency, Origin: deployment.md OOS8]
- [ ] CHK049 Keyboard navigation / a11y — plan does not introduce a UI; CLI a11y is N/A. [Consistency, Origin: ux.md OOS9]

## F. NEW plan-level findings (Gaps / Conflicts surfaced by `/speckit-plan`) — **ALL RESOLVED 2026-05-25**

All 15 findings closed by the remediation pass documented in [`remediation-plan-2026-05-25.md`](./remediation-plan-2026-05-25.md). Resolutions verified by 10 spot-check `grep`s.

### F.1 · Conflict: voter-config loading vs `interpreter/venv` check ordering

- [x] CHK050 ✅ **Resolved** — `data-model.md` §1 inline comment for `voter_config_path` rewritten to clarify the field tracks the *attempted* path on load failure, and §8 lifecycle gained an "Interpreter/venv check ordering" paragraph explaining the non-circularity (interpreter usability is implicit at `import time`; check 1 then validates the running interpreter matches the expected venv). [Conflict, Plan §data-model.md §1 vs §8]

### F.2 · Gap: Evaluator subprocess failure mode mapping

- [x] CHK051 ✅ **Resolved** — `research.md` R-023.13 gained an "Evaluator subprocess failure handling" paragraph: WARN to stderr, `quality_status_source` stays `"gate"`, demo's own exit code unchanged (pipeline outcome authoritative), 60 s subprocess budget. [Gap, Plan §research.md R-023.13/R-023.20]

### F.3 · Gap: Aggregated vs first-failing artifact-schema-validation diagnostic

- [x] CHK052 ✅ **Resolved** — `contracts/readiness-vocabulary.md` check 7 diagnostic now requires `observed` to be a list of `{path, error}` objects covering every failing artifact in canonical order. [Gap, Plan §contracts/readiness-vocabulary.md check 7]

### F.4 · Gap: Run-id prefix width and source-of-truth

- [x] CHK053 ✅ **Resolved** — `research.md` R-023.6 gained a "Prefix construction" paragraph: `run_id[0:8]` (8 hex chars before first hyphen), computed once at process start, identical across all stderr lines in a run. [Clarity, Plan §research.md R-023.6]

### F.5 · Gap: `OLLAMA_CONTEXT_LENGTH` env var consumption side

- [x] CHK054 ✅ **Resolved** — `contracts/cli-contract.md` env-var table row rewritten: required by both demo + startup script; demo defaults to requiring `2048` when unset; operator-overridable up but not down. Also clarified in `contracts/readiness-vocabulary.md` check 6 pass criterion. [Clarity, Plan §contracts/cli-contract.md vs contracts/readiness-vocabulary.md]

### F.6 · Gap: Readiness check `elapsed_seconds` decimals/precision

- [x] CHK055 ✅ **Resolved** — new `research.md` R-023.21 pins all wall-clock floats to 3 dp via `round(value, 3)` before serialization. Covers `ReadinessCheck.elapsed_seconds`, `ReadinessSummary.elapsed_seconds`, `PhaseTimings.*`, `total_runtime_seconds`. [Gap, Plan §data-model.md §2]

### F.7 · Gap: Forward compatibility of fixed-order check vocabulary

- [x] CHK056 ✅ **Resolved** — `contracts/demo-report-schema.md` §"Compatibility & versioning" gained a bullet: adding a 9th check is a minor schema_version bump; the new check slots in by dependency order; consumers MUST NOT assume a fixed `readiness.checks[]` length. [Gap, Plan §contracts/readiness-vocabulary.md]

### F.8 · Gap: Multi-voter voter-config handling

- [x] CHK057 ✅ **Resolved** — `data-model.md` §6 (`VoterConfigReference`) gained a "Precondition: single-voter only (v0.1.0)" paragraph: demo selects the first voter if config has multiple, emits a WARN; multi-voter awareness is out of scope for v0.1.0. [Gap, Plan §data-model.md §6]

### F.9 · Gap: Post-run interrogation timing budget

- [x] CHK058 ✅ **Resolved** — `research.md` R-023.15 gained a "Probe timing budget" paragraph: 2 s per probe, 5 s aggregate; `"unreachable"` on timeout; `failure_kind: "post-run-interrogation-unreachable"` set on the report; these budgets do NOT count against FR-008's 600 s pipeline timeout. [Gap, Plan §research.md R-023.15]

### F.10 · Gap: `phase_timings` precision and serialization

- [x] CHK059 ✅ **Resolved** — covered by R-023.21 (same as CHK055). [Clarity, Plan §data-model.md §3 + research.md R-023.12]

### F.11 · Gap: Test fixture symlink target stability

- [x] CHK060 ✅ **Resolved** — `research.md` R-023.18 gained a "Symlink + FR-017 canonicalization interaction" paragraph: demo never deletes `source.pdf`; the 4 canonical artifact filenames are NOT symlinked in `fixtures/ok/`; new corpus files added later are not back-propagated into the fixture. [Gap, Plan §research.md R-023.18 + FR-017 canonicalization rule]

### F.12 · Gap: `quality_status_source` value on `--with-evaluator` + sidecar-missing path

- [x] CHK061 ✅ **Resolved** — `research.md` R-023.20 gained a "Warn-and-skip outcome" paragraph: `quality_status_source` is `"gate"` (not `null`, not `"evaluator"`) on the warn-and-skip path. [Clarity, Plan §research.md R-023.20 + contracts/demo-report-schema.md]

### F.13 · Conflict: `readiness.overall_passed` interpretation under `--check-only`

- [x] CHK062 ✅ **Resolved** — `contracts/demo-report-schema.md` §"Readiness sub-shape" rewritten to drop the self-contradicting clause; new formal definition: "true iff every check that ran returned `pass` (and none returned `fail`); `skipped` does not block true." Also mirrored to `data-model.md` §2 inline comment. [Conflict, Plan §contracts/demo-report-schema.md §"Readiness sub-shape"]

### F.14 · Gap: `pipeline-runtime-timeout` as readiness check vs runtime guard

- [x] CHK063 ✅ **Resolved** — `contracts/readiness-vocabulary.md` gained a "Vocabulary scope note" header section: the 8 names are a closed diagnostic vocabulary; checks 1–6 are pre-pipeline, checks 7–8 are runtime / post-pipeline monitors. The fixed-order skip rule still applies to all 8. [Clarity / Terminology, Plan §contracts/readiness-vocabulary.md + FR-016]

### F.15 · Gap: Eager-delete order relative to readiness checks 7–8

- [x] CHK064 ✅ **Resolved** — `data-model.md` §8 gained a "Checks 7–8 timing vs FR-017 eager-delete" paragraph: check 7 (schema-validation) runs after the assembler; check 8 (timeout) is a SIGALRM monitor; both run AFTER the pipeline phases; failed check 7 → exit 5 with artifacts left on disk; FR-017 re-trigger only at the NEXT invocation's start. [Clarity, Plan §data-model.md §8 + contracts/readiness-vocabulary.md]

## G. Final coverage scorecard

| Category | Total items | Plan-covered | Open (plan gap / conflict) |
|---|---:|---:|---:|
| A — Spec conflicts resolved + reflected in plan | 9 | 9 | 0 |
| B — Spec ambiguities resolved + reflected in plan | 2 | 2 | 0 |
| C — Spec-resolved gaps reflected in plan | 5 | 5 | 0 |
| D — Planning-deferred items resolved by R-023 | 24 | 24 | 0 |
| E — Out-of-scope items respected by plan | 9 | 9 | 0 |
| F — NEW plan-level findings | 15 | **15** | **0** |
| **Total verification items** | **64** | **64** | **0** |

## H. Disposition — closed 2026-05-25

The 15 plan-level findings from the original verification (F.1 – F.15) are all closed by the remediation pass documented in [`remediation-plan-2026-05-25.md`](./remediation-plan-2026-05-25.md). 20 surgical edits across 4 planning artifacts (`data-model.md`, `research.md`, `contracts/cli-contract.md`, `contracts/demo-report-schema.md`, `contracts/readiness-vocabulary.md`). Zero source-code edits. Zero spec edits.

**Verification:** All 10 grep spot-checks from the remediation plan pass:

| # | Pattern | Target | Expected | Got |
|---|---|---|---:|---:|
| 1 | `voter-config discovery completed` | `data-model.md` | 0 (old wording removed) | 0 |
| 2 | `every check that ran returned` | `contracts/demo-report-schema.md` | 1 | 1 |
| 3 | `Vocabulary scope note` | `contracts/readiness-vocabulary.md` | 1 | 1 |
| 4 | `^## R-023.21` | `research.md` | 1 | 1 |
| 5 | `read by both demo + startup script` | `contracts/cli-contract.md` | 1 | 1 |
| 6 | `single-voter only (v0.1.0)` | `data-model.md` | 1 | 1 |
| 7 | `Probe timing budget` | `research.md` | 1 | 1 |
| 8 | `post-run-interrogation-unreachable` | `research.md` | ≥1 | 2 |
| 9 | `Warn-and-skip outcome` | `research.md` | 1 | 1 |
| 10 | `Checks 7–8 timing` | `data-model.md` | 1 | 1 |

`/speckit-tasks` is now unblocked: zero conflicts, zero ambiguities, zero planning-blocking gaps across all 64 verification items + the original 517 checklist items.

---

## Cross-reference footers added to the 15 existing checklists

After this file lands, each of the 15 existing checklists gets a one-line "Plan coverage verification: see `plan-coverage.md`" footer pointer so reviewers can navigate from any domain to this consolidated view.
