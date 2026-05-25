# Data Model Requirements Quality Checklist: GPU MVP Demo Hardening

**Purpose**: Release-gate audit of requirements covering the four Key Entities (DemoRunReport, ReadinessCheck, VoterConfig, OllamaModelStatus), their closed enums, field shapes, and the null-semantics that hold across all outcomes.
**Created**: 2026-05-24
**Feature**: [spec.md](../spec.md)

## DemoRunReport — Top-level shape

- [ ] CHK001 Is the complete list of top-level fields in `DemoRunReport` enumerated in one place, so no field can be silently added or omitted? [Completeness, Spec §FR-019/FR-024/FR-025/FR-025a/§DemoRunReport entity]
- [ ] CHK002 Is the `kind` field required to be the exact string `"demo_run_report"` on every outcome (no `"demo_run_partial"` variant)? [Clarity, Spec §FR-019]
- [ ] CHK003 Are field-order or JSON serialization requirements specified, or is automation expected to be key-order-agnostic? [Coverage, Gap]
- [ ] CHK004 Is the "stable shape across outcomes" rule (FR-019) defined precisely enough — e.g., the same key set on every outcome with `null` for unknown values — that a JSON Schema could be authored from the spec alone? [Clarity, Spec §FR-019]

## DemoRunReport — Versioning

- [ ] CHK005 Is `schema_version` required as a top-level field, with a starting value (`"0.1.0"`) and a bump rule (additive vs breaking)? [Completeness, Spec §FR-024]
- [ ] CHK006 Is `pipeline_version` defined with a source (e.g., package version, git describe, composed sub-module versions)? [Clarity, Spec §FR-024, Deferred]
- [ ] CHK007 Are `schema_version` and `pipeline_version` distinguished clearly so future readers don't conflate "report shape version" with "pipeline build version"? [Clarity, Spec §FR-024]

## DemoRunReport — Outcome / Quality fields

- [ ] CHK008 Are the six allowed values of `runtime_outcome` an exhaustive closed enum, with no implicit "other" or extension mechanism? [Completeness, Spec §FR-020]
- [ ] CHK009 Are the three allowed values of `quality_status` an exhaustive closed enum, mapped deterministically from upstream signals (evidence-gate state + `manual_review_required`)? [Completeness, Spec §FR-010]
- [ ] CHK010 Is the precise mapping rule from upstream signals to each `quality_status` value defined (e.g., what combination of evidence-gate state + `manual_review_required` produces `weak` vs `review_required`)? [Clarity, Spec §FR-010, Assumptions]
- [ ] CHK011 Is `stalled_phase` defined as present only when `runtime_outcome == "timeout"`, and absent (or `null`) otherwise? [Clarity, Spec §FR-020]
- [ ] CHK012 Are the four allowed values of `stalled_phase` an exhaustive closed enum that matches the four `failed_at_<phase>` enum values exactly (same set, just rendered without the `failed_at_` prefix)? [Consistency, Spec §FR-020]

## DemoRunReport — Readiness summary shape

- [ ] CHK013 Is the readiness summary's shape pinned (object keyed by check name, or list of `{name, status, diagnostic}` entries)? [Completeness, Spec §FR-026]
- [ ] CHK014 Is the readiness check `status` enum (`pass` / `fail` / `skipped`) defined for each of the 8 named checks individually, or only at the type level? [Clarity, Spec §FR-026, §ReadinessCheck entity]
- [ ] CHK015 Is the `failing_check_name` (or equivalent top-level field) typed precisely — single string, `null` when no failure, or absent vs present? [Clarity, Spec §FR-026]
- [ ] CHK016 Is the diagnostic-payload shape per readiness check pinned (free-text string vs structured object with fixed keys), so automation can extract context reliably? [Completeness, Spec §FR-016, §ReadinessCheck entity]

## DemoRunReport — Timing fields

- [ ] CHK017 Is `phase_timings` required to always emit all four keys (`preprocess`, `extraction`, `routing`, `final_payload`), with `null` for unreached phases? [Clarity, Spec §FR-025]
- [ ] CHK018 Is the unit of `phase_timings` values pinned (seconds, milliseconds; float vs integer)? [Clarity, Spec §FR-025]
- [ ] CHK019 Is the unit of `total_runtime_seconds` pinned and required to be a sum-or-superset of `phase_timings` (e.g., includes inter-phase overhead)? [Consistency, Spec §FR-025]
- [ ] CHK020 Is the behavior of `phase_timings` / `total_runtime_seconds` under `--check-only` specified explicitly as `null` for all keys (FR-025a) — not omitted? [Consistency, Spec §FR-025/FR-025a]

## DemoRunReport — Path fields

- [ ] CHK021 Are the four canonical artifact paths (`preprocess_output.json` etc.) emitted as relative paths, absolute paths, or operator-chosen? [Clarity, Gap]
- [ ] CHK022 Is the `interpreter_path` field required to be the resolved interpreter (canonicalized) or the literal `argv[0]`-style path that may include symlinks? [Clarity, Spec §FR-003]
- [ ] CHK023 Is the `voter_config_path` field required to be the path actually used (after `--voter-config` override or auto-discovery), so triage can reproduce the discovery? [Completeness, Spec §FR-005]

## ReadinessCheck Entity

- [ ] CHK024 Is the closed vocabulary of check names (8 entries) consistent in casing/formatting between FR-016, the ReadinessCheck entity, SC-003, and the Edge Cases section? [Consistency, Spec §FR-016/§ReadinessCheck/SC-003]
- [ ] CHK025 Is `skipped` defined precisely as "the check did not run because an earlier required check failed" (vs. "the check was opted out")? [Clarity, Spec §FR-026]
- [ ] CHK026 Is the dependency order between checks (e.g., interpreter/venv runs before Paddle preflight; ollama-reachability runs before ollama-version) specified so `skipped` is deterministically attributable? [Completeness, Gap]

## OllamaModelStatus Entity

- [ ] CHK027 Is `OllamaModelStatus` defined as a snapshot taken at two specific points (readiness time AND post-run), with field-level requirements on what must be captured at each? [Completeness, Spec §FR-012, §OllamaModelStatus entity]
- [ ] CHK028 Is the "context-length field when exposed" wording resolved into a precise required/optional designation? [Clarity, Spec §OllamaModelStatus entity]

## VoterConfig (reused)

- [ ] CHK029 Is the spec explicit that this feature does NOT change the VoterConfig schema (no new fields read, no new fields written), so feature 005's contract holds? [Completeness, Spec §VoterConfig entity]

## Nullability & Field-Presence Rules

- [ ] CHK030 Is the difference between "field present with value `null`" and "field absent" specified consistently across `phase_timings`, `stalled_phase`, `quality_status`, `artifact_paths`, `runtime_outcome`? [Clarity, Spec §FR-019/FR-025/FR-025a]
- [ ] CHK031 Is there a rule for whether automation may rely on key-presence vs. value-presence to detect outcome class? [Clarity, Spec §FR-019]

## Primary / Alternate / Exception / Recovery / Non-Functional Coverage

- [ ] CHK032 Is data-model shape defined for the **primary** outcome (`runtime_outcome: success` + all fields populated)? [Coverage — Primary, Spec §FR-019]
- [ ] CHK033 Is data-model shape defined for **alternate** outcomes (`--check-only` mode with null runtime fields; `--with-evaluator` adding evaluator-derived `quality_status`)? [Coverage — Alternate, Spec §FR-025a/FR-022]
- [ ] CHK034 Is data-model shape defined for **exception** outcomes (each `failed_at_<phase>` value, readiness-failed, invalid-input/usage)? [Coverage — Exception, Spec §FR-020/FR-021]
- [ ] CHK035 Are **recovery**-related fields (e.g., partial artifact paths on timeout) explicitly required to be populated when applicable? [Coverage — Recovery, Spec §US3 AS2]
- [ ] CHK036 Are data-model **non-functional** properties (JSON-line size bounds, encoding = UTF-8, line-feed termination) specified? [Coverage — Non-Functional, Gap]

## Ambiguities & Conflicts

- [ ] CHK037 Is the precedence between FR-025 ("phase_timings includes all four keys with null for unreached") and FR-025a (`phase_timings` set to `null` under `--check-only`) resolved — is it `null` per-key, the whole field `null`, or both representations are acceptable? [Conflict, Spec §FR-025/FR-025a]
- [ ] CHK038 Is the relationship between the report's `bounded timeout value` field and `total_runtime_seconds` defined (e.g., timeout value is the limit, total_runtime is the elapsed time)? [Clarity, Spec §DemoRunReport entity, FR-008]
- [ ] CHK039 Is the meaning of `artifact_paths` on a runtime-success-but-quality-weak run defined (all four paths present), separately from a `failed_at_extraction` run (only `preprocess_output.json` path present)? [Coverage, Spec §FR-019, Gap]


---

**Plan coverage verification (2026-05-25):** see [plan-coverage.md](./plan-coverage.md) for the cross-reference of this checklist's items against `plan.md` / `research.md` / `data-model.md` / `contracts/` / `quickstart.md`.
