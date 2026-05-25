# Error Handling / Resilience Requirements Quality Checklist: GPU MVP Demo Hardening

**Purpose**: Release-gate audit of failure-mode requirements — the closed readiness vocabulary, exit-code taxonomy, `runtime_outcome` enum, timeout/`stalled_phase` semantics, warn-and-skip behavior, eager-delete contract, and recovery semantics across every failure class.
**Created**: 2026-05-24
**Feature**: [spec.md](../spec.md)

## Closed Readiness Vocabulary

- [ ] CHK001 Are exactly 8 named readiness checks enumerated in FR-016, and is the closed-vocabulary requirement enforceable (no implicit "other" check class)? [Completeness, Spec §FR-016]
- [ ] CHK002 Is the spec explicit that adding a new readiness check is a spec change (not a planning-time addition), so the vocabulary remains stable? [Clarity, Spec §FR-016]
- [ ] CHK003 Are the 8 check names spelled identically across FR-016, the ReadinessCheck entity, US3, SC-003, and the Edge Cases? [Consistency, Spec passim]
- [ ] CHK004 Is the rule "exactly one named failing check is reported" (US3 AS1) reconciled with the requirement "all named checks emit per-check status" (FR-026) — i.e., one fails, others may pass or skip, but only one is highlighted? [Consistency, Spec §US3 AS1/FR-026]
- [ ] CHK005 Is the diagnostic format ("what was checked, what was observed, what was expected") required for every named check, including the four named in round 2/3 (ollama-context-length, ollama-version, voter-config-availability=usage)? [Completeness, Spec §US3 AS1, FR-016]

## Exit-Code Taxonomy

- [ ] CHK006 Are exactly 6 exit codes enumerated (0–5), and is each code mapped to exactly one outcome class? [Completeness, Spec §FR-021]
- [ ] CHK007 Is the rule "exit code 1 = readiness failed, regardless of which named check" reconciled with the round-3 promise that the failing check name is surfaced in the report (so automation distinguishes via report content, not exit code)? [Consistency, Spec §FR-021/FR-026]
- [ ] CHK008 Is the rule "exit code 2 = invalid input/usage" used consistently for missing `source.pdf`, missing voter config, and any other operator-input failures, with no "exit 2 also means X" overload? [Consistency, Spec §FR-027/FR-005]
- [ ] CHK009 Is the difference between exit code 3 (pipeline timeout) and exit code 4 (pipeline runtime failed) precisely defined — is a stall that happens to exceed 600 s code 3, or could it be code 4? [Clarity, Spec §FR-021]
- [ ] CHK010 Is the difference between exit code 4 (pipeline runtime failed) and exit code 5 (artifact schema validation failed) precisely defined — does an extractor that returns malformed JSON exit 4 or 5? [Clarity, Spec §FR-021, Gap]
- [ ] CHK011 Are sub-module exit-code translations specified — feature 005 (0/1/2/3/4) and feature 008 (0/1/2/3) → the demo's 0–5 closed table? [Completeness, Spec §Dependencies/FR-021]

## `runtime_outcome` Enum

- [ ] CHK012 Are the 6 `runtime_outcome` values exhaustive (success, four failed_at_<phase>, timeout), with no implicit extension? [Completeness, Spec §FR-020]
- [ ] CHK013 Is the mapping from sub-module failure → `failed_at_<phase>` defined (e.g., feature 005's JSON-repair failure → `failed_at_extraction`)? [Coverage, Gap]
- [ ] CHK014 Is the precedence rule between `runtime_outcome` and exit code defined — e.g., when `runtime_outcome == "timeout"`, exit code MUST be 3? [Consistency, Spec §FR-020/FR-021]

## `stalled_phase` Semantics

- [ ] CHK015 Is `stalled_phase` defined as present only on `runtime_outcome: timeout`, and absent (or `null`) on all other outcomes? [Clarity, Spec §FR-020]
- [ ] CHK016 Is the rule for determining which phase is the "stalled" phase specified — the phase that was executing when the 600 s wall-clock elapsed? [Clarity, Spec §FR-020, §US3 AS2]
- [ ] CHK017 Is the `stalled_phase` enum (4 values) a strict subset of the phase names in `phase_timings` (4 keys) and the `failed_at_<phase>` suffixes (4 values)? [Consistency, Spec §FR-020/FR-025]

## Warn-and-Skip Behavior (`--with-evaluator`)

- [ ] CHK018 Is the warn-and-skip behavior for `--with-evaluator` without sidecar defined precisely — emit a stderr warning, set `quality_status` from default sources, exit code is unaffected? [Clarity, Spec §FR-022]
- [ ] CHK019 Is the warn-and-skip warning's textual form specified, so automation can grep for it? [Completeness, Gap]
- [ ] CHK020 Is the report-field behavior on warn-and-skip specified — does the report indicate that the evaluator was requested-but-skipped, or is the warning only on stderr? [Coverage, Gap]

## Eager-Delete Contract

- [ ] CHK021 Is the eager-delete sequence explicit (run start → delete four canonicals → start preprocessing), with no race with sub-module startup? [Clarity, Spec §FR-017]
- [ ] CHK022 Is the behavior specified when the eager-delete itself fails (e.g., permission error on one of the four artifact paths)? [Coverage — Exception, Gap]
- [ ] CHK023 Is the behavior specified when only some of the four artifacts exist before run start (eager-delete is idempotent on missing files)? [Clarity, Spec §FR-017, Gap]
- [ ] CHK024 Is the requirement that partial new artifacts remain after a mid-run failure (US3 AS2) reconciled with the eager-delete behavior — i.e., it's the *new* partial state that remains, never a mix of new and old? [Consistency, Spec §FR-017/US3 AS2]

## Network / Mid-Run Failure Modes

- [ ] CHK025 Are requirements specified for Ollama becoming unreachable mid-run (was reachable at readiness; goes away during extraction)? [Coverage — Exception, Gap]
- [ ] CHK026 Are requirements specified for an Ollama context-window error mid-run (FR-006 says surface as a runtime failure pointing at the startup script — what `runtime_outcome` value)? [Coverage — Exception, Spec §FR-006]
- [ ] CHK027 Are requirements specified for `/api/ps` becoming malformed between readiness time and post-run time (FR-012 post-run interrogation)? [Coverage — Exception, Gap]

## Recovery & Operator Guidance

- [ ] CHK028 Are recovery requirements defined per failure class — e.g., interpreter/venv fail → switch venvs; ollama-reachability fail → run the startup script; ollama-version fail → upgrade Ollama? [Coverage — Recovery, Gap]
- [ ] CHK029 Is the operator-visible diagnostic for each failure class required to include the specific recovery action, or only the failure description? [Completeness, Spec §FR-016]
- [ ] CHK030 Is the timeout recovery path (partial artifacts left in place for inspection) reconciled with the re-run determinism (eager-delete on next run)? [Consistency, Spec §FR-017, §US3 AS2]

## Primary / Alternate / Exception / Recovery / Non-Functional Coverage

- [ ] CHK031 Are error-handling requirements defined for the **primary** flow (no errors)? [Coverage — Primary, N/A]
- [ ] CHK032 Are error-handling requirements defined for **alternate** flows (`--with-evaluator` + no sidecar warn-and-skip; missing `--voter-config` and no auto-discovery)? [Coverage — Alternate, Spec §FR-022/FR-005]
- [ ] CHK033 Are error-handling requirements defined for every **exception** class enumerated in FR-016 + sub-module-runtime failures + timeout + invalid input + schema-validation failure? [Coverage — Exception, Spec §FR-016/FR-020/FR-021]
- [ ] CHK034 Are **recovery** requirements defined for each failure class (above)? [Coverage — Recovery, Gap]
- [ ] CHK035 Are **non-functional** error-handling properties specified (e.g., no failure mode causes a >600 s hang; no failure mode produces non-JSON stdout)? [Coverage — Non-Functional, Spec §FR-008/FR-019]

## Ambiguities & Conflicts

- [ ] CHK036 Is the case where readiness passes but a stale `OLLAMA_CONTEXT_LENGTH` causes a downstream context-window error (FR-006 fallback) classified consistently — does it count as `failed_at_extraction` or as a separate failure class? [Conflict, Spec §FR-006/FR-020]
- [ ] CHK037 Is the case where `--check-only` passes but a non-readiness condition (e.g., `source.pdf` missing) is unexamined under `--check-only` — does the operator get a misleading "ready" signal? [Ambiguity, Spec §FR-018/FR-027]
- [ ] CHK038 Is the rule for partial-deletion failure on eager-delete defined — if 2 of 4 deletes succeed before the 3rd fails, is the per-doc folder restored, left partial, or considered usage-error? [Conflict, Spec §FR-017, Gap]


---

**Plan coverage verification (2026-05-25):** see [plan-coverage.md](./plan-coverage.md) for the cross-reference of this checklist's items against `plan.md` / `research.md` / `data-model.md` / `contracts/` / `quickstart.md`.
