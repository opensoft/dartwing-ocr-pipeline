# DemoRunReport Shape Requirements Quality Checklist: GPU MVP Demo Hardening

**Purpose**: Release-gate audit of the feature's domain-specific data shape — the closed-enum vocabularies (`runtime_outcome`, `quality_status`, `stalled_phase`, readiness check names), the null semantics across all outcomes, the `schema_version` + `pipeline_version` policy, and the stable-key contract.
**Created**: 2026-05-24
**Feature**: [spec.md](../spec.md)

## Closed Enum: `runtime_outcome`

- [ ] CHK001 Are exactly 6 values enumerated in FR-020, with no implicit "other" or "unknown"? [Completeness, Spec §FR-020]
- [ ] CHK002 Are the 4 `failed_at_<phase>` values' underscore-separated names consistent with the 4 `phase_timings` keys and the 4 `stalled_phase` values? [Consistency, Spec §FR-020/FR-025]
- [ ] CHK003 Is `success` defined precisely (all four artifacts schema-valid AND post-run GPU re-interrogation passed AND quality_status computed)? [Clarity, Spec §FR-009/FR-012]
- [ ] CHK004 Is `timeout` defined precisely (wall-clock elapsed exceeded 600 s AND `stalled_phase` is non-null)? [Clarity, Spec §FR-020]
- [ ] CHK005 Is the rule "exit code 4 = pipeline runtime failed after readiness passed" mapped explicitly to the `failed_at_<phase>` enum values? [Consistency, Spec §FR-020/FR-021]

## Closed Enum: `quality_status`

- [ ] CHK006 Are exactly 3 values enumerated (`pass` / `weak` / `review_required`)? [Completeness, Spec §FR-010]
- [ ] CHK007 Is the derivation rule from upstream signals (evidence-gate state + `manual_review_required`) to each `quality_status` value defined as a closed truth table, not a loose mapping? [Clarity, Spec §FR-010, Gap]
- [ ] CHK008 Is the behavior on `runtime_outcome != success` specified for `quality_status` — `null`, or some other sentinel? [Clarity, Spec §FR-019, Gap]
- [ ] CHK009 Is the `--with-evaluator` derivation path (evaluator output → `quality_status`) defined as either replacing the default derivation, or augmenting it? [Coverage, Spec §FR-022, Gap]

## Closed Enum: `stalled_phase`

- [ ] CHK010 Are exactly 4 values enumerated (`preprocess` / `extraction` / `routing` / `final_payload`)? [Completeness, Spec §FR-020]
- [ ] CHK011 Is `stalled_phase` defined as null/absent except when `runtime_outcome == timeout`? [Clarity, Spec §FR-020]
- [ ] CHK012 Is the rule for identifying *which* phase was stalled (the phase that was executing at the 600 s mark) unambiguous? [Clarity, Spec §FR-020]

## Closed Enum: Readiness Check Names

- [ ] CHK013 Are the 8 readiness check names enumerated identically in FR-016, the ReadinessCheck entity, US3, SC-003, and the Edge Cases? [Consistency, Spec passim]
- [ ] CHK014 Is the canonical casing/spelling (hyphenated-identifier vs prose) for each check name pinned, so report consumers can string-match? [Clarity, Spec §FR-016, Gap]
- [ ] CHK015 Is the rule "exactly one failing check is named on a readiness failure" reconciled with "all 8 checks emit per-check status"? [Consistency, Spec §FR-016/FR-026]

## Closed Enum: ReadinessCheck Status

- [ ] CHK016 Are exactly 3 values enumerated (`pass` / `fail` / `skipped`)? [Completeness, Spec §ReadinessCheck entity]
- [ ] CHK017 Is the `skipped` semantic ("upstream check failed, so this check did not run") defined precisely, with a documented dependency order between checks? [Clarity, Spec §FR-026, Gap]
- [ ] CHK018 Is the rule "every readiness check emits exactly one of the 3 status values; no check is omitted from the report" explicit? [Consistency, Spec §FR-026]

## Null Semantics

- [ ] CHK019 Is the rule "unknown or non-applicable fields are emitted as null" specified for every field of the report, or only for the runtime/quality/timing/artifact fields under `--check-only`? [Coverage, Spec §FR-019/FR-025a]
- [ ] CHK020 Is the distinction between "field present with null value" and "field absent" defined consistently across all fields? [Clarity, Spec §FR-019, Gap]
- [ ] CHK021 Is the behavior of `phase_timings` keys specified — under `--check-only`, is `phase_timings` itself `null`, or is it `{preprocess: null, extraction: null, routing: null, final_payload: null}`? [Consistency, Spec §FR-025/FR-025a]
- [ ] CHK022 Is the behavior of `artifact_paths` on a `failed_at_extraction` run specified — empty list, partial list of paths actually written, or null? [Coverage, Spec §FR-019, Gap]

## Versioning

- [ ] CHK023 Is `schema_version` required as a top-level string field starting at `"0.1.0"`? [Clarity, Spec §FR-024]
- [ ] CHK024 Is the `schema_version` bump policy (additive change = patch; field removal = major) defined or inherited from feature 014–020 conventions? [Consistency, Spec §FR-024, Gap]
- [ ] CHK025 Is `pipeline_version` required as a top-level string field, with a defined source (deferred to planning but must be a single value)? [Clarity, Spec §FR-024, Deferred]
- [ ] CHK026 Is the relationship between `schema_version` and `pipeline_version` defined so the two cannot be confused (one is the report shape; the other is the pipeline build)? [Clarity, Spec §FR-024]

## Stable-Key Contract

- [ ] CHK027 Is the requirement that *every* outcome emits the *same* set of top-level keys (with nulls as needed) auditable from a single canonical JSON Schema? [Completeness, Spec §FR-019]
- [ ] CHK028 Is the spec explicit that automation may rely on key-presence-with-value-null vs. key-absent semantics, or is it free to use either? [Clarity, Spec §FR-019, Gap]
- [ ] CHK029 Is the JSON key naming convention (snake_case vs camelCase) pinned, so authors cannot pick arbitrarily? [Consistency, Gap]

## Cross-Field Constraints

- [ ] CHK030 Is the constraint "when `runtime_outcome == timeout`, then `stalled_phase` is non-null" explicit? [Consistency, Spec §FR-020]
- [ ] CHK031 Is the constraint "when `runtime_outcome == success`, then `phase_timings` has non-null values for all 4 keys AND `total_runtime_seconds` is non-null AND `artifact_paths` has all 4 paths" explicit? [Completeness, Spec §FR-009/FR-025]
- [ ] CHK032 Is the constraint "when `runtime_outcome != success`, then `quality_status` is null" specified? [Coverage, Gap]
- [ ] CHK033 Is the constraint "under `--check-only`, `runtime_outcome` is null AND `quality_status` is null AND `stalled_phase` is null AND `phase_timings` is null AND `total_runtime_seconds` is null AND `artifact_paths` is null" explicit? [Completeness, Spec §FR-025a]

## Primary / Alternate / Exception / Recovery / Non-Functional Coverage

- [ ] CHK034 Is report shape defined for the **primary** outcome (`runtime_outcome: success`)? [Coverage — Primary, Spec §FR-019]
- [ ] CHK035 Is report shape defined for **alternate** outcomes (`--check-only`; `--with-evaluator`)? [Coverage — Alternate, Spec §FR-025a/FR-022]
- [ ] CHK036 Is report shape defined for **exception** outcomes (every value of `runtime_outcome`; readiness fail with each of 8 checks named; invalid input)? [Coverage — Exception, Spec §FR-019/FR-020/FR-021]
- [ ] CHK037 Is report shape defined for **recovery** outcomes (post-timeout report with `stalled_phase` populated; partial `artifact_paths`)? [Coverage — Recovery, Spec §FR-020/US3 AS2]
- [ ] CHK038 Is report shape's **non-functional** properties specified (JSON single-line; UTF-8; <X bytes; deterministic key set)? [Coverage — Non-Functional, Spec §FR-019, Gap]

## Ambiguities & Conflicts

- [ ] CHK039 Is the round-3 Q1 promise ("schema shape is stable across outcomes") consistent with FR-025a's per-field null requirements (no field set difference between `--check-only` and a full success run)? [Consistency, Spec §FR-019/FR-025a]
- [ ] CHK040 Is the conflict resolved between FR-020 (only `runtime_outcome: timeout` triggers `stalled_phase`) and the requirement that `--check-only` always emits the same keys (so `stalled_phase` must be a key on `--check-only` too — with value `null`)? [Conflict, Spec §FR-020/FR-025a]


---

**Plan coverage verification (2026-05-25):** see [plan-coverage.md](./plan-coverage.md) for the cross-reference of this checklist's items against `plan.md` / `research.md` / `data-model.md` / `contracts/` / `quickstart.md`.
