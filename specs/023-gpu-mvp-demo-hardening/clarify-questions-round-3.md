# Speckit Clarify — Session 2026-05-24 (Round 3)

Feature: **023-gpu-mvp-demo-hardening**

Spec: `specs/023-gpu-mvp-demo-hardening/spec.md`

Rounds 1 + 2 closed 28 clarifications. Re-scanning the integrated spec surfaces 4 remaining genuinely material ambiguities, all clustered around the `DemoRunReport` emission semantics on non-success paths and one small edge case around voter-config absence. Most other "open" areas are planning detail (e.g. how `pipeline_version` is computed, `schema_version` bump rules) and should not be pulled into the spec.

Reply to each by letter (e.g. "A"), with "yes" / "recommended" to accept the recommendation, or with your own short answer (<=5 words). You can answer all 4 at once or in batches.

## Accepted Answers

- **Q1**: A, scoped to valid demo invocations — every invocation that passes CLI input validation and enters demo execution emits exactly one `DemoRunReport` JSON line on stdout for success, readiness failure, runtime failure, timeout, or `--check-only`; unknown fields are `null` and the schema shape is stable.
- **Q2**: A — `--check-only` populates readiness fields fully and emits `null` for runtime, quality, timing, and artifact fields; it uses the same `kind` and `schema_version`.
- **Q3**: A — for pipeline runs, `phase_timings` always includes `preprocess`, `extraction`, `routing`, and `final_payload`; phases not reached are `null`; `total_runtime_seconds` records elapsed wall-clock time through termination and is always present for pipeline runs.
- **Q4**: A — missing voter config is invalid input/usage and exits 2 before readiness checks or pipeline execution; because this is a usage error rather than a demo run outcome, the `DemoRunReport` stdout guarantee does not apply, stderr carries the diagnostic, and no pipeline artifacts are written.

---

## A. DemoRunReport emission semantics

### Q1. Does the demo command emit a `DemoRunReport` JSON line on **every** run mode (success, readiness-fail, runtime-fail, timeout, `--check-only`), or only on some of them?

**Recommended:** Option A — every run emits exactly one `DemoRunReport` JSON line on stdout regardless of outcome. Maximizes automation parseability and squares with the SC-009 promise ("Automation can parse the demo command output by reading stdout as exactly one JSON object whose `kind` is `demo_run_report`; no human-readable output appears on stdout"). On non-success paths, fields populated to whatever is known at termination; fields not known (e.g. `runtime_outcome` on a readiness failure, `quality_status` on a runtime failure) are emitted as `null` so the report schema shape is stable.

| Option | Description |
|--------|-------------|
| A | Every run emits exactly one `DemoRunReport` JSON line on stdout regardless of outcome; unknown fields are `null`; schema shape is stable across outcomes |
| B | Only successful runs (exit 0) emit `DemoRunReport`; failures emit only a stderr diagnostic and no stdout JSON |
| C | Success + post-readiness runtime failures emit `DemoRunReport`; pre-pipeline readiness failures emit only stderr diagnostic |
| D | Always emit, but use `kind: "demo_run_partial"` for non-success runs (distinguishes incomplete reports from full ones) |

Reply with the option letter, "yes" / "recommended", or your own short answer (<=5 words).

---

### Q2. How does `--check-only` populate `phase_timings`, `runtime_outcome`, `quality_status`, and `stalled_phase` in the `DemoRunReport` it emits?

**Recommended:** Option A — `--check-only` populates the readiness section fully (all 8 named checks with `pass` / `fail` / `skipped`), populates `interpreter_path` and `voter_config_path`, leaves `runtime_outcome`, `quality_status`, `stalled_phase`, `phase_timings`, and `total_runtime_seconds` as `null`, and leaves `artifact_paths` as `null`. Schema shape is stable with the full-run report; consumers can detect readiness-only mode by `runtime_outcome === null`.

| Option | Description |
|--------|-------------|
| A | Populate readiness fields fully; emit `null` for all runtime / quality / timing / artifact fields; same `kind` and same `schema_version` |
| B | Same as A but flip `kind` to `"demo_check_only_report"` so automation can distinguish the two modes without inspecting `runtime_outcome` |
| C | Emit a smaller, dedicated `DemoReadinessReport` shape that has no `runtime_outcome` / `quality_status` / `phase_timings` keys at all |
| D | Omit non-applicable keys entirely (sparse object); consumers must tolerate missing keys |

Reply with the option letter, "yes" / "recommended", or your own short answer (<=5 words).

---

### Q3. How is `phase_timings` shaped on a non-success run that completed some phases but not all (e.g. `runtime_outcome: failed_at_extraction` — preprocess succeeded, extraction failed)?

**Recommended:** Option A — `phase_timings` always includes all 4 phase keys; phases that ran emit their wall-clock seconds; phases that did not run emit `null`. Lets automation always read `phase_timings.preprocess` without key-presence checks, and `null` cleanly distinguishes "phase did not run" from "phase ran in 0 seconds".

| Option | Description |
|--------|-------------|
| A | Always emit all 4 keys (`preprocess`, `extraction`, `routing`, `final_payload`); phases not reached are `null`; `total_runtime_seconds` always present |
| B | Always emit all 4 keys; phases not reached are `0.0` |
| C | Emit only keys for phases that completed (partial dict); consumers detect skipped phases by missing key |
| D | Omit `phase_timings` entirely on non-success runs; only present on `runtime_outcome: success` |

Reply with the option letter, "yes" / "recommended", or your own short answer (<=5 words).

---

## B. Edge case: voter-config absence

### Q4. What happens if neither `--voter-config <path>` is supplied nor the auto-discovery path from features 005 / 021 locates a valid voter config?

**Recommended:** Option A — treat as invalid input / usage; exit code 2. The voter config is operator-supplied input (analogous to `source.pdf`); a missing input is a usage error, not a readiness check class. Matches the round-2 missing-source.pdf decision (Q10) and keeps the FR-016 closed readiness vocabulary tight.

| Option | Description |
|--------|-------------|
| A | Treat as invalid input / usage; exit code 2; mirrors round-2 missing-source.pdf semantics |
| B | Treat as readiness check failure under a new named check (e.g. `voter-config-availability`); expands FR-016 closed vocabulary |
| C | Treat as readiness check failure under the existing `interpreter/venv` check (since voter-config discovery is tied to the venv layout) |
| D | Treat as `failed_at_extraction` (let the extractor module surface its own error during pipeline runtime) |

Reply with the option letter, "yes" / "recommended", or your own short answer (<=5 words).

---

**Questions file:** `/workspace/projects/dartwing/ocr-pipeline-worktrees/023-gpu-mvp-demo-hardening/specs/023-gpu-mvp-demo-hardening/clarify-questions-round-3.md`

Answered on 2026-05-24; integrate the accepted answers above into `spec.md` before `/speckit.plan`.
