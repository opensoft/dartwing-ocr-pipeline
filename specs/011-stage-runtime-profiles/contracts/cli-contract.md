# CLI Contract: Stage 1 Pipeline (Amended for 011 - Stage Runtime Profiles)

**Contract set version (artifacts)**: 1.2.0 (unchanged - this feature does **not** modify any artifact schema; FR-029)
**CLI contract version**: 1.1.0 (amends `specs/002-cli-contract/contracts/cli-contract.md` v1.0.0)
**Branch**: `011-stage-runtime-profiles`
**Date**: 2026-05-04

This document is the successor to the frozen `002-cli-contract` v1.0.0. It preserves every stable property `002` defined and adds the controller surface required by feature 011 (stage profiles, execution slicing, warm corpus mode, run timing summary, additional Ollama lane URLs). The artifact JSON Schemas under `contracts/stage1_vendor_identity/v1.2.0/` remain authoritative for on-disk shapes; this file only covers the CLI surface, exit codes, and I/O behavior.

---

## Invocation

```bash
# Contract-stable forms (harness targets either)
python -m dartwing_ocr.pipeline run [INPUT_SELECTOR] [STAGE_FLAGS] [OPTIONS]
dartwing-pipeline run [INPUT_SELECTOR] [STAGE_FLAGS] [OPTIONS]
```

Without a subcommand, the CLI prints help and exits with code `10` (`USAGE_ERROR`). The top-level command and `run` subcommand name are unchanged from `002`.

---

## Arguments

### Input selector (exactly one of)

| Argument | Type | Notes |
|----------|------|-------|
| `--input PATH` | file path | Path to a single PDF file. Cold single-document mode. (Existing.) |
| `--document-folder PATH` | directory path | Path to a per-document folder containing `source.pdf`. Cold single-document mode. (Existing.) |
| `--documents-file PATH` | file path | **NEW.** UTF-8 text file with one per-document folder path per line. Blank lines and `#`-comment lines are ignored after stripping. Activates warm-corpus mode (FR-023). |

Exactly one of `--input` / `--document-folder` / `--documents-file` MUST be provided. Providing zero or more than one exits with `USAGE_ERROR` (10) and a stage of `arguments` in the failure record.

`--documents-file` paths inside the file resolve relative to the file's parent directory (R-007). An empty corpus (zero non-comment lines) is rejected with `USAGE_ERROR` and message `empty-corpus: --documents-file <path> contains no document folders`.

### Stage profile flags (NEW - FR-003)

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--preprocess-profile VALUE` | string | `ppstructurev3@cpu` (FR-007) | Stage profile for preprocessing. |
| `--extract-profile VALUE` | string | `ollama@gpu` (FR-007) | Stage profile for extraction. |
| `--routing-profile VALUE` | string | `rules@cpu` (FR-007) | Stage profile for routing. |
| `--final-payload-profile VALUE` | string | `assembler@cpu` (FR-007) | Stage profile for final payload assembly. |
| `--stack-preset NAME` | enum | none | Convenience expansion to one profile per stage. |

**Profile value grammar** (FR-005): `stub` OR `<implementation>@<lane>`.

**Closed-set vocabulary** (FR-006, R-001):

| Stage | Accepted profile values |
|---|---|
| `preprocess` | `stub`, `ppstructurev3@cpu`, `edge-ocr@jetson` |
| `extract` | `stub`, `ollama@gpu`, `ollama@cpu`, `ollama@jetson`, `ensemble@workstation` |
| `routing` | `stub`, `rules@cpu` |
| `final_payload` | `stub`, `assembler@cpu` |

**`--stack-preset` expansion table** (FR-004A, R-003):

| Preset | preprocess | extract | routing | final_payload |
|---|---|---|---|---|
| `full-workstation` | `ppstructurev3@cpu` | `ollama@gpu` | `rules@cpu` | `assembler@cpu` |
| `cloud-workstation` | `ppstructurev3@cpu` | `ensemble@workstation` | `rules@cpu` | `assembler@cpu` |
| `edge-fast` | `edge-ocr@jetson` | `ollama@jetson` | `rules@cpu` | `assembler@cpu` |

When `--stack-preset` is combined with explicit `--<stage>-profile` flags, the explicit per-stage value wins for that stage (R-003). The originating preset name is recorded in the run summary's `stack_preset` field.

**Rejection rules** (FR-008, R-002): The CLI exits with `USAGE_ERROR` (10) before any artifact write when:

- Profile value does not match the grammar (e.g. empty string, missing `@`, multi-`@`).
- `(stage, implementation, lane)` is not in the closed vocabulary above (e.g. `ppstructurev3@gpu`, `edge-ocr@cpu`, `rules@gpu`, `ensemble@cloud`, unknown implementation names).
- `stub@cpu` / `stub@gpu` (stub is lane-less).
- `--stack-preset` value is not in the closed preset list.
- `--extract-profile ensemble@workstation` is selected inside the execution slice - accepted by argument validation, then rejected before artifact writes with a structured failure at the canonical `extraction` stage naming the deferral to FR-034 step 4 (R-013).

### Execution-slice flags (NEW - FR-004)

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--start-at STAGE` | enum: `preprocess` / `extract` / `routing` / `final_payload` | `preprocess` | Inclusive lower bound of the executed slice. |
| `--stop-after STAGE` | enum: same as above | `final_payload` | Inclusive upper bound of the executed slice. |

**Validation** (R-004): Both bounds default to a full-pipeline slice. `--start-at` must not be later than `--stop-after`; otherwise `USAGE_ERROR`.

**Prerequisite-artifact validation** (FR-010, R-005): When `--start-at` is later than `preprocess`, every upstream artifact required by the start stage MUST already exist in the destination folder and validate against the installed contract set. Failures emit a structured failure record with stage `prerequisite_validation` and exit code `11` (`INPUT_NOT_FOUND`) for missing files or `30` (`SCHEMA_VALIDATION_FAILURE`) for invalid files; no downstream artifact is written.

| Start stage | Required prerequisite artifacts |
|---|---|
| `preprocess` | (none) |
| `extract` | `preprocess_output.json` |
| `routing` | `preprocess_output.json`, `edge_extraction_output.json` |
| `final_payload` | `preprocess_output.json`, `edge_extraction_output.json`, `routing_decision.json` |

**Overwrite scoping** (FR-011, R-006): Without `--overwrite`, the CLI only treats artifacts inside the slice (`output_artifacts`) as outputs-in-use. Prerequisite artifacts and downstream-untouched artifacts NEVER trigger `OUTPUT_IN_USE` errors. `--overwrite` is unchanged from `002` and continues to mean "replace existing artifacts in the selected slice".

### Failure-policy flag (NEW - FR-028)

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--on-failure MODE` | enum: `continue` / `fail-fast` | `continue` in warm-corpus mode; effective no-op in cold single-document mode | Per-document failure handling. |

In warm-corpus mode (`--documents-file`), `continue` records the failure on stderr and proceeds to the next document; `fail-fast` stops after the first failure. In cold single-document mode, the flag is accepted (case-insensitive) but does not change behavior because there is only one document (R-008, R-010).

### Ollama lane URL flags (NEW for cpu/jetson - FR-015 / FR-016 / FR-017)

| Argument | Type | Default | Env Var | Notes |
|----------|------|---------|---------|-------|
| `--ollama-url URL` | string | `http://localhost:11434` | `OLLAMA_BASE_URL` | Flag and env var preserved verbatim from `002-cli-contract` v1.0.0 (no rename, no migration). Semantics tightened: this URL is now explicitly the GPU lane endpoint and is consumed only when the resolved extract profile is `ollama@gpu`. CPU and Jetson lanes have their own dedicated flags (rows below). |
| `--ollama-cpu-url URL` | string | `http://localhost:11435` | `OLLAMA_CPU_BASE_URL` | NEW. CPU benchmark lane. |
| `--ollama-jetson-url URL` | string | `http://jetson.local:11434` | `OLLAMA_JETSON_BASE_URL` | NEW. Jetson edge lane. Documented placeholder; operator must override on real hardware. |

Resolution order for each lane: flag > env var > documented default (R-012). The lane URL itself is consumed by the live extract adapter; it is not surfaced in run-summary metadata in this slice.

### Existing options (unchanged from `002`)

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--output-dir PATH` | directory path | See `002` Section "`--output-dir` default resolution" | Destination per-document folder (cold mode only). |
| `--document-id ID` | string | Derived from folder name | Document identifier stamped into all artifacts. |
| `--overwrite` | flag | `false` | Replace existing reserved artifact files **inside the selected slice** (semantics tightened by R-006). |
| `--pipeline-version VER` | string | Package default | Stamped into pipeline-versioned artifacts. |
| `--policy-version VER` | string | `stage1-baseline-v0` | Stamped into `routing_decision`. |
| `--contract-set-version VER` | string | `1.0.0` | Must name an installed version. |
| `--log-level LEVEL` | string | `warning` | One of `error`, `warning`, `info`, `debug`. |
| `--timeout SECONDS` | integer | `300` | Per-stage wall-clock timeout. |

### Mutual exclusion / ordering rules (NEW + AMENDED)

- Exactly one of `--input` / `--document-folder` / `--documents-file` (NEW for `--documents-file`).
- `--output-dir` is rejected with `USAGE_ERROR` when `--documents-file` is supplied (warm-corpus runs always write into the listed per-document folders).
- `--document-id` is rejected with `USAGE_ERROR` when `--documents-file` is supplied (each document's id is derived per folder name as in cold mode).
- `--start-at` and `--stop-after` apply uniformly to every document in a warm-corpus run.

---

## Frozen argument set (AMENDED)

The argument set listed in this document is the complete stage-1 surface as of CLI contract v1.1.0. The following are explicitly **still not present** and continue to require a future contract amendment:

- Image input flags (PNG, JPG, TIFF) - out of scope (FR-006: PDF input only).
- HTTP service mode flags.
- Cloud execution flags (FR-021 / FR-036 forbid remote provider integration in this slice).
- Line-item extraction flags.
- Latency/SLA gate flags.
- Voter selection flags beyond profile names - `ensemble@workstation` voter-config flags are deferred to FR-034 step 4 (R-013).
- New on-disk benchmark artifact flags (FR-030 / FR-036 forbid persisting one).

The previously-frozen "Batch/multi-document flags" exclusion from `002` is **lifted** by this amendment: `--documents-file` is the contract-blessed batch entrypoint. No other batch flag is added.

---

## Output behavior

### Cold single-document mode (`--input` / `--document-folder`)

Identical to `002-cli-contract` v1.0.0:

- On success (exit `0`): exactly four artifact files written to destination folder; one JSON line on stdout matching the `002` success-summary shape; no stdout `kind` field (R-010).
- On failure (non-zero exit): one structured JSON failure line on stderr; existing exit-code taxonomy preserved.

### Warm-corpus mode (`--documents-file`)

stdout is JSON-Lines:

1. Zero or more per-document success records (each matching the `002` success-summary shape, no `kind` field - backward compatible).
2. Exactly one end-of-run summary object as the **last** stdout line, with `kind: "run_summary"` and the schema pinned in this contract (see "Run summary schema" below).

stderr in warm-corpus mode:

- One structured `StructuredFailureRecord` line per failed document (existing `002` failure-record shape, with `failed_stage` and `exit_code` populated).
- Documents skipped because of a fail-fast abort produce no stderr record.

Process exit code in warm-corpus mode (R-008):

- `0` if every executed document succeeded AND no document was skipped due to fail-fast.
- Otherwise the highest-severity exit code observed across executed documents, using the existing `ExitCode` enum ordering.

### Run summary schema (NEW - see `data-model.md`)

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
  "documents_total": 3,
  "documents_succeeded": 2,
  "documents_failed": 1,
  "profile_initialization_seconds": {"preprocess": 12.481},
  "per_document": [
    {"document_id": "inv_001", "folder": "tests/stage1_vendor_identity/inv_001_easy", "status": "success", "stages": {"preprocess": {"rasterize_seconds": 0.214, "infer_seconds": 1.832, "write_seconds": 0.012, "total_seconds": 2.058}}},
    {"document_id": "inv_007", "folder": "tests/stage1_vendor_identity/inv_007_hard", "status": "failure", "failed_stage": "preprocess", "exit_code": 4, "message": "..."}
  ]
}
```

`schema_version` is independent of the artifact contract set and bumps via the same amendment process. Per-document `stages` includes only the phases the slice executed; missing phases mean the stage was outside the slice or did not start due to an upstream failure on that document.

---

## Exit codes (preserved from `002`)

The existing `ExitCode` enum is unchanged. The new failure stages this feature introduces (`prerequisite_validation`, `arguments` for new mutual-exclusion errors, `corpus_validation` for empty/malformed `--documents-file`) reuse existing codes:

| Stage | Exit code |
|---|---|
| `arguments` (mutual-exclusion, unknown flag) | `10` `USAGE_ERROR` |
| `prerequisite_validation` (missing prerequisite artifact) | `11` `INPUT_NOT_FOUND` |
| `prerequisite_validation` (schema-invalid prerequisite artifact) | `30` `SCHEMA_VALIDATION_FAILURE` |
| Canonical stage name (`preprocess` / `extraction`) when an in-slice profile raises `DeferredImplementationError` (`ensemble@workstation`, `edge-ocr@jetson`, `ollama@jetson`) | `10` `USAGE_ERROR` (treated as caller-side configuration error per R-013). The stage name in the failure record matches the runner's canonical stage name, not `prerequisite_validation`. |
| `corpus_validation` (empty or unreadable `--documents-file`) | `10` `USAGE_ERROR` |
| Per-document stage failures | Existing codes; surfaced per-document in warm mode. Severity ordering for warm-corpus aggregate exit code is pinned in research.md R-008. |

---

## Determinism & reproducibility

- Profile resolution is pure-function: same args => same `ResolvedRunPlan`.
- `--stack-preset` expansion is the constant table above; no host-introspection.
- Run summary `per_document` order matches the order of documents in `--documents-file` after comment-strip (R-007).
- Timing values (`*_seconds`) are non-deterministic by nature; they are emitted to six decimal places (R-015) but are explicitly out of scope for byte-identical artifact determinism. Timing reproducibility is a harness concern.
- The four canonical artifacts continue to honor whatever determinism guarantees the per-stage modules provide today; lane changes (FR-014) MUST NOT alter artifact bytes beyond the metadata fields the contract set already permits to vary.

---

## Backwards compatibility with `002-cli-contract` v1.0.0

The amendment is strictly additive on the `run` subcommand surface. Specifically:

- All `002` flags are accepted with the same semantics. Tests written against `002` continue to pass when no new flag is supplied.
- The cold-mode stdout/stderr JSON shapes are byte-identical to `002`. No `kind` field is added in cold mode (R-010).
- `--overwrite` semantics are tightened to "slice outputs only" (R-006). This is a strict relaxation: any `002` workflow that ran the full pipeline is unaffected; workflows that previously failed `OUTPUT_IN_USE` because of unrelated downstream files now succeed when they have a slice that excludes those files. No `002` consumer should regress.
- The "Batch/multi-document flags" exclusion in `002` Section Frozen argument set is explicitly lifted by this contract amendment. `--documents-file` is the only new batch flag; no other batch flag is permitted without a further amendment.

---

## References

- spec.md - Functional Requirements (FR-001 ... FR-036) and Success Criteria.
- research.md - Decisions R-001 ... R-015.
- data-model.md - In-memory entity model and lifecycles.
- `specs/002-cli-contract/contracts/cli-contract.md` - predecessor contract; preserved property-by-property except where this document explicitly amends.
- `contracts/stage1_vendor_identity/v1.2.0/` - artifact JSON Schemas (unchanged by this feature).
