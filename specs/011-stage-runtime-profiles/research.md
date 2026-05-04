# Research: Stage Runtime Profiles / Root Master Controller (011)

**Feature**: `011-stage-runtime-profiles`
**Date**: 2026-05-04
**Inputs**: spec.md (with /speckit.clarify Session 2026-05-04), `.specify/memory/constitution.md` v1.3.0, existing source tree under `src/ledgerlinc_ocr/`, prior frozen contract `specs/002-cli-contract/contracts/cli-contract.md`.

The Technical Context in `plan.md` carried zero open clarification placeholders - the five interactive clarifications already pinned the warm-corpus invocation surface, default failure policy, run summary delivery channel, stack-preset expansions, and the `ensemble@workstation` deferral. This document records the smaller research decisions that the plan still needed to commit to before contract drafting (Phase 1).

Each decision uses the format **Decision / Rationale / Alternatives**. Decisions are referenced by `R-NNN` so contract and quickstart artifacts can cite them.

---

## R-001: Profile grammar parser is closed-set, not extensible at runtime

**Decision**: The profile resolver hard-codes the supported profile set per stage from FR-006 (preprocess: `stub` / `ppstructurev3@cpu` / `edge-ocr@jetson`; extract: `stub` / `ollama@gpu` / `ollama@cpu` / `ollama@jetson` / `ensemble@workstation`; routing: `stub` / `rules@cpu`; final payload: `stub` / `assembler@cpu`). New profiles require a code change plus a contract amendment.

**Rationale**: FR-005 fixes the `stub | <implementation>@<lane>` grammar; FR-006 enumerates the entire stage-1 surface; FR-008 demands rejection of unsupported combinations before any artifact write. A plugin/discovery mechanism would let an unknown implementation slip past validation. Closed-set keeps validation O(1), error messages exhaustive, and amendment governance honest.

**Alternatives**:
- Entry-point discovery (`importlib.metadata`) - adds runtime variability, defeats FR-008's pre-write fail.
- Config-file-driven vocabulary - adds a new contract surface this slice doesn't need.

---

## R-002: Profile parsing rejects `stub@<lane>` and any `<impl>@<unsupported-lane>` deterministically

**Decision**: The grammar accepts the literal token `stub` (no `@`) for every stage, and `<impl>@<lane>` only when `(stage, impl, lane)` is a member of the FR-006 set. `stub@cpu`, `stub@gpu`, and unknown implementations are rejected with a single shared usage-error code path; the error message names the offending value, the stage flag, and the closed list of accepted values for that stage.

**Rationale**: Per FR-008 + spec Edge Cases, `stub` is lane-less, and `ppstructurev3@gpu`, `edge-ocr@cpu`, `rules@gpu`, `ensemble@cloud`, etc. must fail before any artifact write. Centralizing rejection in one resolver function means the CLI test suite can table-test all rejection cases against one implementation instead of scattering checks across handlers.

**Alternatives**:
- Per-stage handler functions that each redo parsing - duplicates rejection logic and risks divergence across stages.
- Late rejection inside stage adapters - would let argument-only mistakes reach disk.

---

## R-003: Stack-preset expansion is a constant table; per-stage flags override

**Decision**: `--stack-preset` expands to the table pinned in spec.md FR-004A:
- `full-workstation` -> preprocess `ppstructurev3@cpu`, extract `ollama@gpu`, routing `rules@cpu`, final payload `assembler@cpu`.
- `cloud-workstation` -> preprocess `ppstructurev3@cpu`, extract `ensemble@workstation`, routing `rules@cpu`, final payload `assembler@cpu`.
- `edge-fast` -> preprocess `edge-ocr@jetson`, extract `ollama@jetson`, routing `rules@cpu`, final payload `assembler@cpu`.

Resolution order: start from the preset's table; for each stage where the caller passed an explicit `--<stage>-profile`, overwrite that stage's value with the explicit value. The preset name (when supplied) is recorded verbatim in the run summary alongside the resolved per-stage values.

**Rationale**: Q4 of /speckit.clarify pinned this expansion. Constant-table resolution keeps expansion auditable and avoids any conditional logic that depends on host detection.

**Alternatives**:
- Mutually-exclusive preset vs. per-stage flags (rejected as Option B during clarify) - denies callers the legitimate "swap one stage" workflow.
- Host-detection heuristics that switch presets - collapses I-Boundary by letting controller code make environment guesses.

---

## R-004: Execution slice is a half-open index range over a fixed stage tuple

**Decision**: The runner holds a fixed canonical stage tuple `("preprocess", "extract", "routing", "final_payload")`. `--start-at` and `--stop-after` parse to indices into that tuple; bounds are inclusive on both ends per FR-004 (so `--start-at extract --stop-after extract` runs only extract). Defaults: `--start-at preprocess --stop-after final_payload`. `--start-at` must not be greater than `--stop-after`; violation is a usage error.

**Rationale**: A single ordered tuple avoids string comparisons during stage selection and makes "stages before slice" / "stages after slice" trivial set operations. Keeps the existing runner's `_STAGE_SEQUENCE` shape.

**Alternatives**:
- Encode each stage's predecessors as a graph - overkill for a four-stage linear pipeline.
- Allow non-contiguous slices (skip middle stages) - explicitly out of scope per FR-009 ("contiguous stage slice").

---

## R-005: Prerequisite-artifact validation reuses `ledgerlinc_ocr.validator.artifact.validate_artifact`

**Decision**: When `--start-at` is later than `preprocess`, the runner computes the set of upstream artifact filenames required by the start stage (preprocess -> none; extract -> `preprocess_output.json`; routing -> `+ edge_extraction_output.json`; final_payload -> `+ routing_decision.json`) and validates each one against the installed contract set via the existing `validate_artifact(...)` function. A missing file or a schema-invalid file fails before any downstream write, with `stage="prerequisite_validation"` and a message naming the unmet prerequisite (FR-010).

**Rationale**: FR-010 requires both existence and schema validity. The validator module already handles both, with structured violation reporting. Reusing it avoids a parallel validation path that could drift from the contract set.

**Alternatives**:
- Re-implement bare-bones JSON-existence check - would silently let a corrupted upstream artifact through.
- Run preprocessing as a no-op when its artifact already exists - defeats the slicing semantics and risks overwriting in-place.

---

## R-006: Overwrite guard scopes to the slice's outputs only

**Decision**: The overwrite guard checks only the artifacts the slice will *write* (i.e., the canonical filenames at slice indices `[start_at..stop_after]`). Files outside that index range are treated as prerequisites or downstream-untouched and never trigger `OUTPUT_IN_USE`. Without `--overwrite`, an existing output-in-slice still fails fast as today.

**Rationale**: FR-011 + spec Acceptance Scenario 5. The current implementation in `pipeline/cli.py:_check_filesystem_state` checks all four `RESERVED_ARTIFACT_NAMES` regardless of slice; after this feature, that check is reformulated to take the resolved slice into account.

**Alternatives**:
- Treat all four files as outputs always - blocks legitimate `--start-at routing` reruns whenever upstream artifacts exist.
- Treat all four files as never-blocked - silently overwrites artifacts the caller did not opt into replacing.

---

## R-007: `--documents-file` parsing strips blanks and `#`-comments; rejects empty corpus

**Decision**: `parse_documents_file(path)` reads the file as UTF-8, splits on `\n`, strips each line, and discards lines that are empty after strip OR begin with `#` after strip. Remaining entries are resolved relative to the file's parent directory (so a relative path inside the file resolves predictably regardless of the caller's cwd). Duplicate entries are preserved in order - corpus duplication is the harness's call, not the controller's. After parsing, an empty list is rejected with a usage error (`empty-corpus`).

**Rationale**: Aligns with the spec's new edge cases for `--documents-file` (mutual exclusion, missing file, invalid listed folders, empty/comment-only file). Comment support keeps human-edited corpus lists tractable. Rejecting an empty list prevents silent no-op runs that would otherwise emit only the `kind: "run_summary"` line and exit 0.

**Alternatives**:
- Allow empty file as a no-op success - violates "fail before silent success" pattern used throughout stage 1 CLIs.
- Resolve paths relative to caller cwd - surprising when corpus files travel with the docs.

---

## R-008: `--on-failure` defaults vary by mode and serialize to per-document records

**Decision**:
- Default in warm-corpus mode (`--documents-file`) is `continue`. Default in cold single-document mode (`--document-folder` / `--input`) is effectively `fail-fast` because there is only one document.
- Accepted values: `continue` and `fail-fast` (canonical), with case-insensitive parse.
- A failed document in `continue` mode emits a structured per-document failure record on stderr (same shape as today's `002` `StructuredFailureRecord`) and the run continues with the next document. After the last document, the `kind: "run_summary"` object on stdout reports `failure_count`, `success_count`, and per-document outcome rows.
- Process exit code in warm-corpus + `continue` mode is `0` if and only if every document produced a schema-valid full-slice artifact set; otherwise the exit code is the highest-severity per-document failure code observed (matches existing `ExitCode` enum ordering).

**Rationale**: Q2 of /speckit.clarify pinned the default; FR-028 mandates per-document failure context; the existing `StructuredFailureRecord` already serializes the right fields, so the corpus path reuses it without inventing a new failure format.

**Alternatives**:
- Always exit `0` when `continue` is chosen and surface the count via the run summary alone - masks failures from CI/`set -e` callers.
- Always exit non-zero on first failure even in `continue` - makes `--on-failure continue` semantically meaningless.

---

## R-009: Run summary is the last line on stdout and is JSON-Lines compatible

**Decision**: stdout in warm-corpus mode is JSON-Lines: one JSON object per line, no array wrapper. Per-document success records keep their existing single-line `002` shape (no `kind` field - backward-compatible). The end-of-run `kind: "run_summary"` object is the **last** line on stdout.

The run summary object shape (pinned here for the CLI contract):

```json
{
  "kind": "run_summary",
  "schema_version": "0.1.0",
  "stack_preset": "full-workstation",
  "resolved_profiles": {
    "preprocess": "ppstructurev3@cpu",
    "extract": "ollama@gpu",
    "routing": "rules@cpu",
    "final_payload": "assembler@cpu"
  },
  "execution_slice": {"start_at": "preprocess", "stop_after": "final_payload"},
  "on_failure": "continue",
  "documents_total": 20,
  "documents_succeeded": 19,
  "documents_failed": 1,
  "profile_initialization_seconds": {"preprocess": 12.481},
  "per_document": [
    {
      "document_id": "inv_001",
      "folder": "tests/stage1_vendor_identity/inv_001_easy",
      "status": "success",
      "stages": {
        "preprocess": {"rasterize_seconds": 0.214, "infer_seconds": 1.832, "write_seconds": 0.012, "total_seconds": 2.058},
        "extract":    {"infer_seconds": 4.107, "write_seconds": 0.009, "total_seconds": 4.116},
        "routing":    {"compute_seconds": 0.003, "write_seconds": 0.002, "total_seconds": 0.005},
        "final_payload": {"compute_seconds": 0.004, "write_seconds": 0.003, "total_seconds": 0.007}
      }
    },
    {
      "document_id": "inv_007",
      "folder": "tests/stage1_vendor_identity/inv_007_hard",
      "status": "failure",
      "failed_stage": "preprocess",
      "exit_code": 4,
      "message": "PPStructureV3 init failed: ..."
    }
  ]
}
```

`schema_version` exists so the harness can detect future shape bumps without parsing the whole document. `profile_initialization_seconds` is keyed by stage so future warm-extract or warm-routing profiles can extend it without reshaping the object.

**Rationale**: Q3 of /speckit.clarify pinned stdout + `kind: "run_summary"`. JSON-Lines is what the harness already parses for the per-document `002` record; reusing the format avoids a JSON-array wrapper that would couple per-document emission to end-of-run buffering and break streaming consumers.

**Alternatives**:
- Single end-of-run JSON document containing both the per-document records and the summary - forces buffering and breaks `tail -f` style monitoring.
- Stderr summary - collides with the failure-record stream and diverges from the `002` "no stdout on failure" rule for individual documents.

---

## R-010: Cold single-document mode preserves the existing `002` stdout shape exactly

**Decision**: When the runner is invoked with `--document-folder` / `--input` (cold single-document mode), stdout still emits exactly the existing `002-cli-contract` success record on stdout (no `kind` field, no `run_summary` line). `--on-failure` is accepted but is a no-op in cold mode (single document failure is already surfaced through exit code + stderr failure record). Lane/profile resolution and run timing capture still happen, but timing is not emitted in cold mode unless an explicit opt-in flag (out of scope here) is added later.

**Rationale**: FR-002 preserves the frozen success/failure record shapes. Adding `kind: "run_summary"` in cold mode would silently break harness scripts that today consume one stdout JSON line per `run` invocation. Keeping the cold path bit-identical to `002` honors the contract amendment principle.

**Alternatives**:
- Always emit a run summary, even for one document - breaks `002` consumers.
- Drop `--on-failure` from cold mode entirely - surprising surface asymmetry; better to accept-and-noop with a one-line note in the contract doc.

---

## R-011: Warm-profile lifecycle is per-process and stage-scoped

**Decision**: A `WarmProfileRegistry` object lives for the lifetime of a single CLI invocation. On the first document that needs a given live preprocessing profile (e.g. `ppstructurev3@cpu`), the registry calls the adapter's `initialize()` once, records the wall-clock cost as `profile_initialization_seconds.preprocess`, and stores the warmed instance. Subsequent documents call `process(folder)` on the same instance. The registry is *not* a global; it does not persist between CLI invocations and does not survive a process restart. After the warm-corpus loop exits, the registry's `close()` releases any held resources (file handles, GPU contexts) before stdout summary emission.

**Rationale**: FR-023 + FR-024 + SC-009. Per-process warmth is the simplest model that meets "exactly once per process, not N times" and avoids cross-invocation state that would make CI runs non-reproducible. Stage-scoped (instead of one global pool) keeps each stage's lifecycle independent - relevant when FR-024's "design MAY later reuse the same lifecycle for live extraction profiles" lands.

**Alternatives**:
- Module-level singleton - pollutes test isolation; pytest reuses processes between cases.
- Server-mode subprocess that persists across invocations - explicitly out of scope (FR-030: no new persisted benchmark artifact, no model-runtime ownership shift).

---

## R-012: Ollama lane URL resolution table

**Decision**: Three explicit lane URL resolution chains, each with the same precedence order:

| Lane | Flag | Env Var | Documented Default |
|---|---|---|---|
| `gpu` | `--ollama-url` | `OLLAMA_BASE_URL` | `http://localhost:11434` (existing) |
| `cpu` | `--ollama-cpu-url` | `OLLAMA_CPU_BASE_URL` | `http://localhost:11435` (new - non-conflicting port for the optional CPU container) |
| `jetson` | `--ollama-jetson-url` | `OLLAMA_JETSON_BASE_URL` | `http://jetson.local:11434` (new - documented placeholder; operator must override on real Jetson hardware) |

Resolution: flag > env var > documented default. The selected URL is recorded in run summary metadata.

**Rationale**: FR-015 / FR-016 / FR-017 require explicit per-lane URLs. The CPU lane's default port `11435` matches the existing `.devcontainer/docker-compose.yml --profile ollama` convention so the WSL CPU container can be reached without extra config. The Jetson default is a documented placeholder rather than auto-discovery - fail-fast on a missing real endpoint is preferred over silent fallback per FR-018.

**Alternatives**:
- One shared `--ollama-url` with a `--lane` flag - collapses lane-URL precedence and breaks FR-015's separation requirement.
- Auto-discovery via mDNS/Avahi for Jetson - adds runtime variability and a new dependency for a path the harness should configure explicitly.

---

## R-013: `ensemble@workstation` is name-only in this slice

**Decision**: This slice adds `ensemble@workstation` to the closed-set extract-profile vocabulary so that argument validation accepts it and so `--stack-preset cloud-workstation` can expand to it. When `ensemble@workstation` is selected in this slice, the resolver immediately returns a single `MissingEndpointError` with stage `prerequisite_validation` and a message naming the unconfigured voter set ("`ensemble@workstation` requires voter endpoints; configuration is delivered in the secondary-lane slice (FR-034 step 4) - set the explicit per-stage profile or `--stack-preset` to a supported workstation preset"). No voter-config flags, env vars, or files are introduced in this feature.

**Rationale**: Q5 of /speckit.clarify chose deferral. FR-022A requires recognition + fail-fast naming. Implementing a real ensemble voter set without endpoint configuration in this slice would either (a) need a placeholder URL surface that must be redesigned in step 4 or (b) silently use the GPU lane's URL, both of which violate FR-018's no-silent-degradation rule.

**Alternatives**:
- Implement endpoint configuration now - pre-empts the secondary-lane slice and risks freezing flag names before the ensemble shape is firm.
- Leave `ensemble@workstation` out of validation entirely - would force `--stack-preset cloud-workstation` to fail on parse, blocking the metadata/preset surface from landing in slice 1.

---

## R-014: Adapter-target functions live in the existing per-stage modules, not in `pipeline/`

**Decision**: The pipeline package exposes a profile->adapter registry that maps `(stage, impl, lane)` tuples to small adapter callables. Each adapter wraps an existing module's entry point:

- `("preprocess", "ppstructurev3", "cpu")` -> wraps `ledgerlinc_ocr.preprocessing.pipeline.run_preprocessing(folder, ...)` (existing).
- `("extract", "ollama", "gpu")` / `("extract", "ollama", "cpu")` / `("extract", "ollama", "jetson")` -> wraps `ledgerlinc_ocr.extract.pipeline.run_extraction(folder, ollama_url, ...)` with the resolved lane URL.
- `("routing", "rules", "cpu")` -> wraps `ledgerlinc_ocr.router.pipeline.route(folder, ...)` (existing).
- `("final_payload", "assembler", "cpu")` -> wraps `ledgerlinc_ocr.assembler.pipeline.assemble(folder, ...)` (existing).
- `("preprocess", "edge-ocr", "jetson")` / `("extract", "ensemble", "workstation")` -> adapter raises `DeferredImplementationError` with FR-034 step 4 reference. Validation passes; execution fails fast with a named profile.

Stub callables remain in `pipeline/stages.py` and are returned for any `stub` profile selection.

**Rationale**: Constitution Q-Gate 1 + FR-033 - the controller is orchestration, not stage logic. Keeping adapter targets in their existing modules preserves the boundary and avoids duplicating already-tested entry points. Wrapping rather than calling directly lets the registry inject timing instrumentation uniformly.

**Alternatives**:
- Inline each stage's logic into `pipeline/stages.py` - collapses the runtime boundary and duplicates code already covered by per-stage test suites.
- Move stage logic out and have stages depend on `pipeline/` - inverts the dependency direction and creates a circular import risk.

---

## R-015: Timing capture uses `time.monotonic_ns()`; persisted seconds are floats with 6-decimal precision

**Decision**: Per-stage timing is captured via `time.monotonic_ns()` deltas at adapter entry/exit boundaries; the registry stores nanosecond integers internally and converts to seconds at summary emission with `round(ns / 1e9, 6)`. `time.time()` is **not** used for timing because system clock adjustments could yield negative deltas.

**Rationale**: `monotonic_ns` is the stdlib-recommended path for measuring durations. Six-decimal seconds is more than enough resolution for stage-level timing (microsecond floor) while staying readable in JSON. Keeping nanosecond integers internally avoids accumulated float drift across documents.

**Alternatives**:
- `time.perf_counter()` - equivalent monotonicity; chose `monotonic_ns` for integer arithmetic.
- Wall-clock via `datetime.now()` - unsuitable for durations.

---

## Open follow-ups (intentional deferrals)

The following are tracked here so they do not get rediscovered as gaps during /speckit.tasks or /speckit.implement; they are **not** unresolved clarifications.

- **`ensemble@workstation` endpoint configuration surface** - deferred to FR-034 step 4 per R-013 and spec Q5.
- **Live `edge-ocr@jetson` and `ollama@jetson` implementation** - recognition only in this slice (R-014); live adapters land in step 4.
- **`cloud-workstation` voter-set metadata schema** - pinned in run summary (R-009) but the artifact-metadata side (FR-022) for distinguishing stacks lives in the artifact contract amendment, not this slice.
- **Architecture / ollama-runtime doc updates** (Q-Gate 3) - listed as a Phase 1 deliverable in plan.md and will be picked up by /speckit.tasks; the controller layer, `--documents-file` warm path, and CPU/Jetson Ollama lane env vars need to be reflected in `docs/stage1-vendor-identity/architecture.md` and `docs/stage1-vendor-identity/ollama-runtime.md`.

---

## Summary

All clarification placeholders from the plan template's Technical Context were resolved either by the /speckit.clarify session (Q1-Q5) or by the 15 research decisions above. No open ambiguity remains for the controller foundation slice (FR-034 step 1) or the warm `ppstructurev3@cpu` corpus slice (FR-034 step 2). Phase 1 contracts can be drafted directly from this file plus spec.md without further investigation.
