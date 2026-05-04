# Data Model: Stage Runtime Profiles / Root Master Controller (011)

**Feature**: `011-stage-runtime-profiles`
**Date**: 2026-05-04
**Scope**: In-process orchestration entities only. This feature **does not** introduce any new persisted JSON artifact or mutate the four canonical stage-1 artifact schemas (FR-029). Every entity below lives in memory for the lifetime of one CLI invocation, with the single exception of the run summary, which is serialized once to stdout at end-of-run.

The entities here mirror the spec's "Key Entities" section but pin field names, types, validation rules, and ownership boundaries so contract drafts and tests have a single source of truth.

---

## Overview

```
                    +-------------------------+
                    |   CLIInvocation         |  (existing, amended)
                    |   + new fields          |
                    +------------+------------+
                                 |
                                 v
                    +-------------------------+
                    |   ResolvedRunPlan       |  <- profile resolver +
                    |                         |      stack-preset expansion +
                    |                         |      slice control
                    +----+---------------+----+
                         |               |
              cold mode  |               |  warm-corpus mode
                         v               v
              +----------------+  +----------------------+
              | DocumentRun    |  | CorpusRun            |
              | (single)       |  | (DocumentRun list +  |
              |                |  |  WarmProfileRegistry)|
              +--------+-------+  +----------+-----------+
                       |                     |
                       | both produce        |
                       v                     v
              +----------------------------------+
              | Per-stage StageOutcome objects   |
              | (existing + timing additions)    |
              +--------------+-------------------+
                             |
                             v
              +----------------------------------+
              | RunSummary (warm-corpus only)    |
              | -> stdout JSON-Lines, last line   |
              +----------------------------------+
```

---

## Entity: `StageProfile`

The resolved execution mode for a single stage.

| Field | Type | Validation | Notes |
|---|---|---|---|
| `stage` | enum: `preprocess` / `extract` / `routing` / `final_payload` | required, closed set | One of the four canonical stages. |
| `kind` | enum: `stub` / `live` | required | `stub` => lane is `None`; `live` => lane is required. |
| `implementation` | string | required, ASCII lowercase, `[a-z0-9-]+` | E.g. `stub`, `ppstructurev3`, `edge-ocr`, `ollama`, `ensemble`, `rules`, `assembler`. |
| `lane` | enum: `cpu` / `gpu` / `jetson` / `workstation` / `None` | required iff `kind == live` | `None` only when `implementation == stub`. |
| `raw_value` | string | required | Original CLI value the user passed (e.g. `ppstructurev3@cpu`, `stub`). Preserved for run-summary recording. |

**Validation rules** (enforced by `profiles.py:resolve_profile`):

- `(stage, implementation, lane)` MUST be a member of the FR-006 closed set.
- `implementation == stub` => `lane is None` (rejects `stub@cpu`, `stub@gpu`).
- `kind` is derived: `stub` => `stub`, anything else => `live`.
- Rejection raises `ProfileValidationError` with a structured message naming the offending value, the stage flag, and the closed list of accepted values for that stage (R-002).

**Lifecycle**: Constructed once during argument resolution. Immutable thereafter.

---

## Entity: `StackPreset`

A named bundle that expands to one `StageProfile` per stage.

| Field | Type | Validation | Notes |
|---|---|---|---|
| `name` | enum: `full-workstation` / `cloud-workstation` / `edge-fast` | required | Closed set per FR-004A. |
| `expansion` | mapping `stage -> raw profile string` | required | Constant table per R-003. |

**Lifecycle**: Constructed once at argument resolution. Inert after expansion.

**Override semantics**: Per-stage `--<stage>-profile` flags overwrite the preset's mapping for that stage; the preset's `name` is still recorded in the run summary (R-003).

---

## Entity: `ExecutionSlice`

The contiguous subset of stages executed for one invocation.

| Field | Type | Validation | Notes |
|---|---|---|---|
| `start_at` | enum: `preprocess` / `extract` / `routing` / `final_payload` | required, default `preprocess` | Inclusive lower bound. |
| `stop_after` | enum: `preprocess` / `extract` / `routing` / `final_payload` | required, default `final_payload` | Inclusive upper bound. |
| `start_index` | int | derived | Index into canonical stage tuple. |
| `stop_index` | int | derived | Index into canonical stage tuple. |

**Validation rules**:

- `start_index <= stop_index` (R-004). Otherwise `UsageError("--start-at must not be later than --stop-after")`.
- Both flags are independently optional; defaults preserve full-pipeline behavior.

**Derived properties**:

- `prerequisite_artifacts`: tuple of artifact filenames that must exist+validate before the slice runs (empty when `start_at == preprocess`).
- `output_artifacts`: tuple of artifact filenames the slice will write (used to scope the overwrite guard, R-006).
- `untouched_artifacts`: complement of the above two (never read, never written by this run).

---

## Entity: `OllamaLaneEndpoints`

Per-lane URL resolution result.

| Field | Type | Validation | Notes |
|---|---|---|---|
| `gpu_url` | string | optional, defaults `http://localhost:11434` | Existing flag/env var (`--ollama-url` / `OLLAMA_BASE_URL`). |
| `cpu_url` | string | optional, defaults `http://localhost:11435` | New (`--ollama-cpu-url` / `OLLAMA_CPU_BASE_URL`). |
| `jetson_url` | string | optional, defaults `http://jetson.local:11434` | New (`--ollama-jetson-url` / `OLLAMA_JETSON_BASE_URL`). Documented placeholder; operator must override. |

**Validation rules**: URL format is not validated by the controller - invalid URLs surface as connection errors at extract-stage time, with stage/profile context per FR-031.

**Lookup**: `endpoints.for_lane(lane)` returns the matching URL for `cpu` / `gpu` / `jetson`.

---

## Entity: `FailurePolicy`

Run-wide outcome handling for warm-corpus runs.

| Field | Type | Validation | Notes |
|---|---|---|---|
| `mode` | enum: `continue` / `fail-fast` | required | Defaults: `continue` for warm-corpus runs, no-op for cold single-document runs (R-008, R-010). |

**Lifecycle**: Constructed once during argument resolution. Constant for the run.

---

## Entity: `ResolvedRunPlan`

Aggregate of all argument-resolution outputs. The runner takes one `ResolvedRunPlan` and executes it.

| Field | Type | Notes |
|---|---|---|
| `mode` | enum: `cold_single_document` / `warm_corpus` | Derived from which input flag was supplied (`--input` / `--document-folder` => cold; `--documents-file` => warm). |
| `documents` | tuple[`Path`, ...] | One entry in cold mode; N entries in warm mode (post-comment-strip, post-empty-rejection per R-007). |
| `profiles` | mapping `stage -> StageProfile` | Result of preset expansion + per-stage overrides. |
| `stack_preset_name` | string \| None | Recorded if the caller passed `--stack-preset`; None otherwise. |
| `slice` | `ExecutionSlice` | |
| `ollama_endpoints` | `OllamaLaneEndpoints` | |
| `failure_policy` | `FailurePolicy` | |
| `cli_invocation` | `CLIInvocation` (existing, amended) | Preserves `pipeline_version`, `policy_version`, `contract_set_version`, `log_level`, `timeout`, `overwrite`, `document_id`. |

**Validation rules** (run plan-level, after individual entities pass their own checks):

- Exactly one of `--input` / `--document-folder` / `--documents-file` is set; the others are `None`. (Spec edge cases.)
- If `slice.start_at != preprocess`, every prerequisite artifact for the start stage exists and validates against the installed contract set (R-005).
- For each `StageProfile` in `profiles` whose stage falls inside the slice: if `kind == live`, the resolver verifies the adapter target is available (R-014). `ensemble@workstation` selected inside the slice triggers a deferred-implementation fail-fast per R-013.

---

## Entity: `WarmProfileRegistry`

Per-process warm instances of live stage profiles.

| Field | Type | Notes |
|---|---|---|
| `instances` | mapping `(stage, implementation, lane) -> warm instance` | Lazily populated on first use. |
| `initialization_timings_ns` | mapping `stage -> int` | Nanosecond cost of the one-time `initialize()` per stage. |

**Lifecycle**:

- Constructed at the start of `CorpusRun.execute()`.
- `get_or_initialize(profile)` returns the warmed instance for a live profile, calling the adapter's `initialize()` exactly once per `(stage, implementation, lane)` triple (R-011).
- `close()` is invoked unconditionally at the end of the corpus run (success, failure-with-continue, or fail-fast). Failures during `close()` are logged at WARN but never propagated.

**Invariants**:

- For any given `(stage, implementation, lane)`, `initialize()` is called at most once across the entire CLI invocation. SC-009 is verified by asserting `len(initialization_timings_ns)` <= 1 per stage in the corresponding test.
- The registry is **not** module-global. Each `CorpusRun` has its own registry (R-011).

---

## Entity: `StageTiming`

Captured per-stage, per-document timing.

| Field | Type | Notes |
|---|---|---|
| `stage` | enum: `preprocess` / `extract` / `routing` / `final_payload` | |
| `phases_ns` | mapping `phase -> int` | Stage-specific phase timings; nanoseconds. See phase keys per stage. |
| `total_ns` | int | Stage adapter wall-clock from entry to exit. |

**Per-stage phase keys** (R-009 informed by FR-027):

- `preprocess`: `rasterize`, `infer`, `write` -> seconds in summary.
- `extract`: `infer`, `write`.
- `routing`: `compute`, `write`.
- `final_payload`: `compute`, `write`.

Adapters are responsible for measuring the appropriate phases; the registry coalesces missing phases into `total_ns`. Phase keys not listed above are tolerated (forward-compatibility for future adapters) and pass through to the run summary verbatim.

**Serialization** (R-015): `phases_ns[k]` and `total_ns` are converted to seconds at run-summary emission via `round(ns / 1e9, 6)`. Internal arithmetic stays in nanoseconds.

---

## Entity: `DocumentRun`

The execution context for a single per-document folder.

| Field | Type | Notes |
|---|---|---|
| `folder` | `Path` | Per-document folder. |
| `document_id` | string | Derived from folder name (existing rule) or explicit `--document-id`. |
| `slice` | `ExecutionSlice` | Same slice as the run plan. |
| `profiles` | mapping `stage -> StageProfile` | Same profiles as the run plan. |
| `stage_timings` | mapping `stage -> StageTiming` | Populated as stages execute. |
| `outcome` | `DocumentOutcome` | See below. |

**Lifecycle**:

- Constructed once per document.
- `execute(registry)` runs each stage inside the slice via the registered adapter. On the first error, sets `outcome` to a failure record and returns; downstream stages in the slice are not executed for the failed document.

---

## Entity: `DocumentOutcome`

| Field | Type | Notes |
|---|---|---|
| `status` | enum: `success` / `failure` | |
| `failed_stage` | string \| None | Set on failure; mirrors existing `StructuredFailureRecord.stage`. |
| `exit_code` | `ExitCode` enum value | Existing enum from `pipeline/exit_codes.py`. `SUCCESS` for success outcomes. |
| `message` | string | Human-readable cause; empty for success. |
| `artifacts_written` | tuple[`Path`, ...] | Paths of artifacts the slice successfully wrote before any failure. |

**Cold-mode shape**: identical to the existing `RunResult` from `pipeline/runner.py` so the cold path keeps emitting the existing `002-cli-contract` stdout/stderr records without changes.

---

## Entity: `CorpusRun`

Wrapper around a list of `DocumentRun`s plus the warm registry.

| Field | Type | Notes |
|---|---|---|
| `documents` | tuple[`Path`, ...] | From `ResolvedRunPlan.documents`. |
| `registry` | `WarmProfileRegistry` | |
| `failure_policy` | `FailurePolicy` | |
| `runs` | list[`DocumentRun`] | Built lazily as documents execute. |

**Execute loop** (R-008):

```
for folder in documents:
    document_run = DocumentRun.for_folder(folder, slice, profiles)
    document_run.execute(registry)
    runs.append(document_run)
    if document_run.outcome.status == "failure" and failure_policy.mode == "fail-fast":
        break
registry.close()
emit_run_summary(runs, registry)
```

**Exit code**: `0` if every executed document produced success **and** no document was skipped due to fail-fast; otherwise `max(severity_of(run.outcome.exit_code) for run in runs)` per R-008.

---

## Entity: `RunSummary`

The single end-of-run JSON object emitted on stdout in warm-corpus mode.

| Field | Type | Notes |
|---|---|---|
| `kind` | constant string `"run_summary"` | Discriminator (R-009). |
| `schema_version` | string `"0.1.0"` | Bumps independently of artifact contract set. |
| `stack_preset` | string \| null | The preset name if `--stack-preset` was supplied; otherwise null. |
| `resolved_profiles` | mapping `stage -> raw profile string` | Final per-stage values, post-override. |
| `execution_slice` | `{start_at, stop_after}` | |
| `on_failure` | enum: `continue` / `fail-fast` | |
| `documents_total` | int | `len(documents)` post-comment-strip. |
| `documents_succeeded` | int | |
| `documents_failed` | int | |
| `profile_initialization_seconds` | mapping `stage -> float` | One entry per warmed live profile (R-011). Absent stages are not warmed. |
| `per_document` | list[`RunSummaryDocument`] | One entry per attempted document, ordered as executed. |

### Sub-entity: `RunSummaryDocument`

| Field | Type | Notes |
|---|---|---|
| `document_id` | string | |
| `folder` | string | Folder path as supplied (relative or absolute, matching the input). |
| `status` | enum: `success` / `failure` | |
| `stages` | mapping `stage -> {phase_seconds, total_seconds}` | Present on success; subset of phases up through the failed stage on failure. |
| `failed_stage` | string | Present on failure only. |
| `exit_code` | int | Present on failure only; uses existing `ExitCode` enum integer. |
| `message` | string | Present on failure only. |

**Serialization**:

- One JSON object per stdout line (JSON-Lines).
- Per-document success records keep their existing `002-cli-contract` shape (no `kind` field).
- The `RunSummary` object is the **last** stdout line in warm-corpus mode (R-009).

---

## State transitions

The controller has no long-lived state machine; the only sequenced state is per-`DocumentRun`:

```
DocumentRun states:
    PENDING -> RUNNING_STAGE_<n> -> {SUCCESS | FAILURE_AT_STAGE_<n>}
```

A `DocumentRun` cannot move from `FAILURE_AT_STAGE_<n>` to a downstream stage. A `CorpusRun` cannot resume a `DocumentRun` after `close()` is called.

---

## What this feature does NOT introduce

To honor FR-029, FR-030, and FR-036, this feature explicitly does not add:

- Any new on-disk JSON artifact (run summary lives only on stdout).
- Any new field, enum value, or rule in the four canonical artifact schemas.
- Any new persisted benchmark format.
- Any cross-process state (warm registry is per-process).
- Any voter-set / ensemble configuration entity (deferred per R-013 to FR-034 step 4).

These exclusions are testable: `tests/contract_tests/` MUST continue to pass against the existing `contracts/stage1_vendor_identity/v1.2.0/` schemas without modification, and the per-document folder layout enforced by `validator validate folder` MUST remain unchanged.
