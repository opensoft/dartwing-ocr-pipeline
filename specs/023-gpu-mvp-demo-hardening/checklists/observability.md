# Observability Requirements Quality Checklist: GPU MVP Demo Hardening

**Purpose**: Release-gate audit of observability requirements — `DemoRunReport` JSON-line emission, stdout/stderr discipline, phase timings, versioning fields, readiness summary, and the always-emit guarantee across all outcomes.
**Created**: 2026-05-24
**Feature**: [spec.md](../spec.md)

## Always-Emit Guarantee

- [ ] CHK001 Is the requirement that `DemoRunReport` is emitted on **every** outcome (success, readiness-fail, runtime-fail, timeout, `--check-only`, invalid-input) explicit and exhaustive? [Completeness, Spec §FR-019]
- [ ] CHK002 Are outcomes that exit before any line is written to stdout (e.g., crash during eager-delete) classified — does the absence of a JSON line itself count as a parseable signal? [Coverage — Exception, Gap]
- [ ] CHK003 Is the requirement that exactly one JSON line is emitted (not zero, not two) auditable by a single `wc -l <stdout>` check? [Measurability, Spec §FR-019, SC-009]

## stdout / stderr Discipline

- [ ] CHK004 Is the rule "stdout contains exactly one JSON line and nothing else" specified for every outcome including `--check-only`, readiness fail, invalid input, and timeout? [Consistency, Spec §FR-019/SC-009]
- [ ] CHK005 Is the rule "human-readable progress, warnings, and errors go to stderr" specified, and is the inverse rule "stderr contains no JSON" specified? [Completeness, Spec §FR-019]
- [ ] CHK006 Are there requirements about whether stderr lines are line-buffered (visible during long runs) or block-buffered (visible only at end), so operators see progress during the 600 s window? [Coverage — Non-Functional, Gap]
- [ ] CHK007 Is the encoding of stdout/stderr specified (UTF-8) so non-ASCII model names or paths do not break automation? [Completeness, Gap]

## JSON Line Format

- [ ] CHK008 Is the JSON line required to be a single object (not an array, not multiple concatenated objects)? [Clarity, Spec §FR-019]
- [ ] CHK009 Is the trailing newline policy specified (newline-terminated vs not)? [Coverage, Gap]
- [ ] CHK010 Is the requirement that `kind: "demo_run_report"` is a top-level field on every emitted JSON object explicit (no `"demo_check_only_report"` variant)? [Clarity, Spec §FR-019, §Round-3 Q2]
- [ ] CHK011 Is the unknown-field behavior specified — i.e., do automation consumers ignore unrecognized fields, and is the demo command free to add fields under additive `schema_version` bumps? [Coverage — Non-Functional, Gap]

## Phase Timings

- [ ] CHK012 Is the requirement to emit `phase_timings` with all 4 keys (with `null` for unreached phases) auditable from the spec alone? [Clarity, Spec §FR-025]
- [ ] CHK013 Is the relationship between `phase_timings` and feature 015's `run_summary.phase_timings` specified (same source, derived, or independent)? [Consistency, Spec §FR-025, Dependencies]
- [ ] CHK014 Is the precision of phase-timing values specified (e.g., 3 decimal places, integer milliseconds)? [Clarity, Gap]
- [ ] CHK015 Is `total_runtime_seconds` defined precisely (start point, end point, unit) so it is comparable across runs and across machines? [Clarity, Spec §FR-025]

## Readiness Summary

- [ ] CHK016 Is the readiness summary's emission requirement consistent on **every** outcome — i.e., even on a successful full pipeline run, the report still includes the readiness summary showing all 8 checks passed? [Consistency, Spec §FR-026]
- [ ] CHK017 Is the `skipped` status defined precisely enough for an observer to interpret why a particular check did not run (e.g., upstream check failed; check inapplicable in this mode)? [Clarity, Spec §FR-026]
- [ ] CHK018 Is the `failing_check_name` field's presence/absence/null semantics on a success path defined? [Clarity, Spec §FR-026]

## Versioning Fields

- [ ] CHK019 Is `schema_version` required to be emitted on every outcome with a non-null value (starting `"0.1.0"`)? [Completeness, Spec §FR-024]
- [ ] CHK020 Is `pipeline_version`'s emission required on every outcome (or null when not knowable, e.g., the demo failed before the version could be resolved)? [Coverage, Gap]
- [ ] CHK021 Is the `schema_version` bump policy aligned with the feature 014–020 `RunSummary.SCHEMA_VERSION` lineage, so a single conventions document covers both? [Consistency, Spec §FR-024]

## Log Levels & Verbosity

- [ ] CHK022 Is the operator-facing verbosity flag (`--verbose` / `--quiet`) specified, or is verbosity fixed? [Completeness, Gap]
- [ ] CHK023 Are the severities present on stderr (info, warning, error) distinguishable in format, or is stderr free-form prose? [Clarity, Gap]
- [ ] CHK024 Is the volume of stderr output bounded (e.g., not unbounded re-prints during model probing), so operators do not lose signal in noise? [Coverage — Non-Functional, Gap]

## Trace / Diagnostic Context

- [ ] CHK025 Is the requirement to include `interpreter_path`, `voter_config_path`, and `bounded timeout value` in the report explicit so operators have full self-reproduction context? [Completeness, Spec §US1 AS2, §DemoRunReport entity]
- [ ] CHK026 Is a run identifier (UUID, timestamp) specified for cross-correlating the report with stderr lines, or is correlation by timestamp only? [Coverage, Gap]
- [ ] CHK027 Is the post-run device interrogation result (FR-012) specified to be visible in the report (so operators can see "GPU still in use" / "fell back to CPU") rather than only influencing the success/fail decision? [Completeness, Spec §FR-012, Gap]

## Operator Visibility into Failed Phase

- [ ] CHK028 Is the requirement to identify the stalled phase on timeout reflected in *both* the report (`stalled_phase`) and the stderr diagnostic (US3 AS2 prose), so operators can find the information either way? [Consistency, Spec §FR-020/US3 AS2]
- [ ] CHK029 Is the requirement to surface the failing check name on readiness failure reflected in *both* the report (`failing_check_name`) and stderr, with identical wording? [Consistency, Spec §FR-026/US3 AS1]

## Primary / Alternate / Exception / Recovery / Non-Functional Coverage

- [ ] CHK030 Are observability requirements defined for the **primary** outcome (success report with all fields populated)? [Coverage — Primary, Spec §FR-019]
- [ ] CHK031 Are observability requirements defined for **alternate** outcomes (`--check-only`, `--with-evaluator`)? [Coverage — Alternate, Spec §FR-019/FR-022]
- [ ] CHK032 Are observability requirements defined for **exception** outcomes (each failure class produces a parseable report with the failure surfaced)? [Coverage — Exception, Spec §FR-019/FR-020]
- [ ] CHK033 Are observability **recovery** requirements defined (e.g., the report after a timeout includes the `stalled_phase` field so operators know where to look)? [Coverage — Recovery, Spec §FR-020/US3 AS2]
- [ ] CHK034 Are observability **non-functional** requirements quantified (stdout = 1 JSON line; stderr not interleaved with stdout; UTF-8 encoding)? [Coverage — Non-Functional, Spec §FR-019/SC-009]

## Ambiguities & Conflicts

- [ ] CHK035 Is the round-3 Q2 decision (`--check-only` uses the same `kind`, same `schema_version`, with null runtime/quality/timing/artifact fields) consistent with FR-019 (always emit `kind: "demo_run_report"`) and FR-025a (specific null fields under `--check-only`)? [Consistency, Spec §FR-019/FR-025a]
- [ ] CHK036 Is the spec explicit that the demo command does NOT emit a `kind: "run_summary"` line (only the underlying sub-modules do that), so automation can disambiguate the two streams? [Clarity, Spec §FR-019, Dependencies]


---

**Plan coverage verification (2026-05-25):** see [plan-coverage.md](./plan-coverage.md) for the cross-reference of this checklist's items against `plan.md` / `research.md` / `data-model.md` / `contracts/` / `quickstart.md`.
