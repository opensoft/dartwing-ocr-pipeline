# Data Model: GPU MVP Demo Hardening

**Phase 1 output of [plan.md](./plan.md).** Documents the in-memory and on-the-wire entity shapes the demo command builds and emits. The four canonical *artifact* schemas (`preprocess_output.json` etc.) are unchanged (FR-014) and live under `contracts/stage1_vendor_identity/v1.3.0/`; this file describes only the new entities introduced by feature 023.

All entities are Python dataclasses (using `pydantic.dataclasses` for validation consistency with feature 005/008/009 lineage). Field types are Python type hints; JSON serialization rules follow R-023.12 (declaration-order, `ensure_ascii=False`, single-line).

---

## 1. `DemoRunReport`

The top-level stdout JSON object. Emitted exactly once per run (FR-019) with **stable key set across all outcomes** (FR-019 expanded). Unknown / non-applicable fields are emitted as explicit `null` — never omitted.

```python
@dataclass(frozen=True)
class DemoRunReport:
    kind: Literal["demo_run_report"]                  # always exactly this string (FR-019)
    schema_version: str                                # "0.1.0" initial (FR-024)
    pipeline_version: str                              # importlib.metadata version; "unknown" fallback (R-023.2)
    run_id: str                                        # UUID4 string (R-023.6)
    interpreter_path: str                              # absolute, canonicalized (FR-003)
    voter_config_path: str | None                     # path used (or attempted, on voter-config-load failure); null only when demo aborted in argparse before voter-config loading was attempted
    expected_extraction_model: str | None             # model name from voter config; null whenever voter_config_path is null
    document_folder: str | None                       # absolute canonicalized; null when ignored (--check-only)
    bounded_timeout_seconds: int                       # always 600 by default (FR-008)
    readiness: ReadinessSummary                        # always populated (FR-026)
    runtime_outcome: RuntimeOutcome | None            # null when no pipeline ran (FR-020)
    stalled_phase: StalledPhase | None                # non-null only when runtime_outcome == "timeout" (FR-020)
    failure_kind: FailureKind | None                  # non-null on failures; closed enum below
    failing_check_name: ReadinessCheckName | None     # non-null on readiness-fail (FR-016/FR-026)
    phase_timings: PhaseTimings                        # always present; all 4 keys present (FR-025)
    total_runtime_seconds: float | None               # null when no pipeline ran (FR-025)
    artifact_paths: list[str] | None                  # absolute paths to the 4 canonicals; null on --check-only / pre-pipeline-fail
    quality_status: QualityStatus | None              # null when no pipeline ran (FR-010)
    quality_status_source: Literal["gate", "evaluator"] | None  # "evaluator" when --with-evaluator augmented (R-023.20)
    cpu_fallback_detection: CPUFallbackDetection      # post-run device probe results (R-023.15); always present
    diagnostic: str | None                             # human-readable summary of the failure or success; null only if no diagnostic to surface
```

**Cross-field invariants (machine-checkable; mirrored as assertion tests in `test_report_shape.py`):**

1. If `runtime_outcome == "success"` → all 4 `phase_timings` values non-null, `total_runtime_seconds` non-null, `artifact_paths` is a 4-element list, `quality_status` non-null, `stalled_phase` is `null`, `failure_kind` is `null` (or `"post-run-interrogation-unreachable"` when post-run probes could not confirm GPU placement but did not detect CPU fallback, per R-023.15 — when CPU fallback IS detected, `runtime_outcome` is rewritten to `"failed_at_extraction"` and this invariant no longer applies).
2. If `runtime_outcome == "timeout"` → `stalled_phase` non-null, `total_runtime_seconds` ≥ `bounded_timeout_seconds`, `failure_kind == "pipeline-runtime-timeout"`, **`quality_status` is `null`** (audit walkthrough 2026-05-25 Q3).
3. If `runtime_outcome` matches `failed_at_<phase>` → `phase_timings.<phase>` is non-null (that phase started); later phases are `null`; `failure_kind` is non-null; **`quality_status` is `null`** (Q3 — quality is not assessed when the pipeline didn't complete).
4. If `runtime_outcome` is `null` (readiness-fail, invalid-input, or `--check-only`) → `phase_timings.*` all `null`, `total_runtime_seconds` null, `quality_status` null, `artifact_paths` null, `stalled_phase` null.
5. **`quality_status` is non-null IF AND ONLY IF `runtime_outcome == "success"`** (Q3 consolidation — combines invariants 1–4 into a single bi-conditional).
6. Under `--check-only`: `failing_check_name` is non-null iff the readiness phase failed; `document_folder` is `null` (the flag is ignored per FR-018); `failure_kind` is `null` on readiness pass, else `"readiness-failed"`.
7. `kind` is always the literal `"demo_run_report"`; never `"demo_check_only_report"` or `"demo_run_partial"` (round-3 Q2).
8. `cpu_fallback_detection` is always emitted; values are `{"ollama_post_run": "consistent" | "fell_back" | "unreachable" | "skipped", "paddle_post_run": "consistent" | "fell_back" | "unreachable" | "skipped"}`. `"skipped"` is used when the pipeline did not run (readiness-fail, invalid-input, `--check-only`).

---

## 2. `ReadinessSummary` + `ReadinessCheck`

```python
@dataclass(frozen=True)
class ReadinessSummary:
    checks: list[ReadinessCheck]   # exactly 8 entries, always in fixed order (FR-016)
    overall_passed: bool             # true iff every check that ran returned "pass" (and none returned "fail"); "skipped" does not block true
    elapsed_seconds: float           # wall-clock of the readiness phase (must be ≤ 10 s warm — SC-007)

@dataclass(frozen=True)
class ReadinessCheck:
    name: ReadinessCheckName         # closed enum (8 values)
    status: ReadinessCheckStatus     # closed enum: "pass" | "fail" | "skipped"
    elapsed_seconds: float           # wall-clock of this individual check
    diagnostic: CheckDiagnostic | None  # non-null when status == "fail"; null otherwise
```

```python
ReadinessCheckName = Literal[
    "interpreter/venv",
    "paddle-rocm-preflight",
    "ollama-reachability",
    "ollama-version",
    "ollama-model-gpu-placement",
    "ollama-context-length",
    "artifact-schema-validation",
    "pipeline-runtime-timeout",
]

ReadinessCheckStatus = Literal["pass", "fail", "skipped"]
```

**Fixed execution order (FR-016 expanded):** the `checks` list MUST be ordered exactly as the `ReadinessCheckName` literal above. When an earlier check fails, every later check has `status == "skipped"` and `diagnostic == null`. The `failing_check_name` field on `DemoRunReport` is the first check with `status == "fail"`.

```python
@dataclass(frozen=True)
class CheckDiagnostic:
    checked: str        # short prose: what was probed
    observed: object    # machine-readable value: str / int / dict / null; serialized form ≤2 KiB (Q5)
    expected: object    # machine-readable expectation: str / int / dict
    remediation: str    # one short imperative sentence (R-023.11)
```

**`observed` size cap (Q5):** When `observed` contains an embedded JSON blob (e.g., a `/api/ps` entry), the serialized JSON form MUST be ≤ 2 KiB. The serializer truncates to **≤ 2048 bytes, retreating to the last complete UTF-8 character boundary** (so the truncated string is always valid UTF-8 — never split mid-codepoint), then appends `"… [truncated]"` as the final characters of the value. The original byte length is NOT recorded in a sibling field (chosen for simplicity per Q5 option A); operators see only the truncated form. Smaller `observed` values (strings, ints, small dicts) are not affected by the cap.

---

## 3. `PhaseTimings`

```python
@dataclass(frozen=True)
class PhaseTimings:
    preprocess: float | None       # wall-clock seconds; null if not reached
    extraction: float | None       # wall-clock seconds; null if not reached
    routing: float | None          # wall-clock seconds; null if not reached
    final_payload: float | None    # wall-clock seconds; null if not reached
```

**Invariants:**

- All four keys MUST always be present (never omitted) — FR-025.
- Under `--check-only` or readiness fail: all four values are `null`.
- On pipeline success: all four values are non-null floats.
- On `runtime_outcome == "failed_at_extraction"`: `preprocess` non-null, `extraction` non-null (the failing phase still records wall-clock up to the point of failure), `routing` and `final_payload` null.
- The same logic applies to other `failed_at_<phase>` values: the failing phase has a non-null timing capturing how long it ran before failing; later phases are `null`.

---

## 4. Closed enums

```python
RuntimeOutcome = Literal[
    "success",
    "failed_at_preprocess",
    "failed_at_extraction",
    "failed_at_routing",
    "failed_at_final_payload",
    "timeout",
]

StalledPhase = Literal["preprocess", "extraction", "routing", "final_payload"]
QualityStatus = Literal["pass", "weak", "review_required"]

FailureKind = Literal[
    "readiness-failed",
    "invalid-input",
    "pipeline-runtime-timeout",
    "pipeline-runtime-error",
    "artifact-schema-validation-failed",
    "cpu-fallback-detected",
    "post-run-interrogation-unreachable",
]
```

**Mapping `RuntimeOutcome` ↔ exit code** (FR-021 closed table):

| RuntimeOutcome | failure_kind | Exit |
|---|---|---|
| `success` | `null` (or `"cpu-fallback-detected"` → exit 4) | `0` |
| `null` (readiness-fail) | `"readiness-failed"` | `1` |
| `null` (invalid-input) | `"invalid-input"` | `2` |
| `timeout` | `"pipeline-runtime-timeout"` | `3` |
| `failed_at_*` (any phase) | `"pipeline-runtime-error"` or `"cpu-fallback-detected"` | `4` |
| `failed_at_final_payload` due to schema validation | `"artifact-schema-validation-failed"` | `5` |

---

## 5. `CPUFallbackDetection`

```python
ProbeResult = Literal["consistent", "fell_back", "unreachable", "skipped"]

@dataclass(frozen=True)
class CPUFallbackDetection:
    ollama_post_run: ProbeResult     # re-probe of /api/ps for the same model
    paddle_post_run: ProbeResult     # re-invocation of feature 014 preflight
    pre_run_ollama_snapshot: dict | None   # full /api/ps entry captured at readiness (when known)
    post_run_ollama_snapshot: dict | None  # full /api/ps entry captured post-run (when probe succeeded)
```

**Invariants:**

- When `runtime_outcome == "success"` AND both probes returned `"consistent"` → run is canonically successful.
- When EITHER probe returns `"fell_back"` → `runtime_outcome` is rewritten to `"failed_at_extraction"` AND `failure_kind` is set to `"cpu-fallback-detected"` (SC-004 enforcement).
- When EITHER probe returns `"unreachable"` (but neither returned `"fell_back"`) → run is reported with its actual `runtime_outcome` but `failure_kind` becomes `"post-run-interrogation-unreachable"` if it was previously success (we can no longer claim CPU was avoided).
- `"skipped"` is used when the pipeline did not run (so a fallback is not possible).

---

## 6. `VoterConfigReference` (read-only; not re-defined)

This feature consumes the existing feature 005 / 021 voter config schema unchanged. The reader returns a typed `VoterConfigReference` with two fields used by this feature:

```python
@dataclass(frozen=True)
class VoterConfigReference:
    path: str                            # absolute path actually loaded
    model_name: str                      # the extraction model identifier passed to Ollama /api/ps lookup
    extra_voters_ignored: list[str]      # empty for single-voter configs; non-empty (names of voters past the first) when the config is multi-voter — orchestrator emits a WARN line for non-empty
```

Reading the voter config can raise `VoterConfigUnreadable` (file does not exist or unreadable), `VoterConfigMalformed` (not parseable YAML), or `VoterConfigMissingModel` (parsed but missing the model-name field). All three are caught and mapped to exit 2 (invalid-input/usage) per FR-005 expanded clause.

**Precondition: single-voter only (v0.1.0).** This feature's `VoterConfigReference` assumes the voter config defines exactly one voter (the canonical stage 1 single-voter shape per feature 005). If the voter config defines multiple voters (a future feature 005 extension), the demo selects the first voter declared in the YAML document and emits `WARN:[run_id] voter config has multiple voters; demo uses the first (model: <name>)` to stderr. Multi-voter awareness is out of scope for v0.1.0 and is a future feature. Operators with multi-voter configs MUST author a single-voter config file for the demo and pass it via `--voter-config <path>` to avoid the warning.

---

## 7. `OllamaModelStatus` (Key Entity from spec, formalized)

```python
@dataclass(frozen=True)
class OllamaModelStatus:
    name: str                  # model identifier as returned by /api/ps
    size: int                  # total model size in bytes
    size_vram: int             # bytes resident in VRAM
    context_length: int | None # null if the running Ollama version does not expose this field
```

The readiness probe builds one `OllamaModelStatus` from the matching `/api/ps` entry. The CPU-fallback post-run re-probe builds another from the same endpoint for comparison.

---

## 8. Entity lifecycle diagram (text form)

```text
demo CLI start
    │
    ├─→ argparse → flag set → CLIArgs (validate flag interactions per FR-018)
    │
    ├─→ load voter config (--voter-config or auto-discover) → VoterConfigReference  | raises → exit 2
    │
    ├─→ canonicalize --document-folder → resolved path                              | raises → exit 2
    │       (skipped under --check-only per FR-018)
    │
    ├─→ readiness phase (fixed 8-check order; --check-only stops here)
    │       │
    │       └─→ ReadinessSummary (8 ReadinessCheck entries)                          | any fail → exit 1
    │
    ├─→ eager-delete the 4 canonical artifacts in canonicalized folder              | any failure → exit 2
    │       (skipped under --check-only)
    │
    ├─→ pipeline phases (in-process composition):
    │       feature 014/018 preprocess → feature 005 extract → feature 008 route → feature 009 assemble
    │       │
    │       └─→ artifact-schema-validation per artifact (check 7 in vocabulary)
    │       └─→ each phase captures wall-clock into PhaseTimings
    │       └─→ orchestrator enforces 600 s SIGALRM budget                          | timeout → exit 3
    │
    ├─→ post-run CPU-fallback detection (R-023.15)                                   | fallback → exit 4
    │
    ├─→ optional: --with-evaluator subprocess (R-023.13)                             | sidecar missing → warn-and-skip
    │
    ├─→ assemble DemoRunReport (stable key set; FR-019)
    │
    └─→ emit single JSON line to stdout; exit per RuntimeOutcome → ExitCode mapping
```

**Interpreter/venv check ordering.** The lifecycle shows voter-config loading before the readiness phase. This is correct: the `interpreter/venv` check (check 1) is a path comparison that validates the *already-running* interpreter matches `.venv-paddle-rocm`. If the interpreter were too broken to run, the demo CLI would not start at all and no `DemoRunReport` would be emitted. The check therefore runs after voter-config loading without circularity — both depend on `import time` having succeeded, and check 1 then validates that the importing interpreter is the *expected* one.

**Checks 7–8 timing vs FR-017 eager-delete.** The eager-delete of the 4 canonical artifacts happens at run start (before phase 1). Checks 7 (`artifact-schema-validation`) and 8 (`pipeline-runtime-timeout`) execute AFTER the pipeline phases:

- Check 7 validates the just-written artifacts after the assembler completes.
- Check 8 is a `signal.alarm`-driven monitor that fires if the 600 s budget elapses during any phase.

If check 7 fails (one or more artifacts schema-invalid), the demo exits 5 with the artifacts left on disk in their as-written (invalid) state. FR-017's eager-delete does NOT re-trigger on this exit path; it only re-triggers at the start of the NEXT invocation. This is intentional — operators inspecting a failed run benefit from seeing the actual artifact content that failed validation, not an empty folder.

If check 8 fires (timeout), partial artifacts from whichever phase was executing remain in the folder per US3 AS2. Subsequent re-runs eager-delete those partial artifacts at start.

---

## 9. JSON line shape — fully populated example (success)

```json
{"kind":"demo_run_report","schema_version":"0.1.0","pipeline_version":"0.4.2","run_id":"a1b2c3d4-1234-5678-9abc-def012345678","interpreter_path":"/workspace/.venv-paddle-rocm/bin/python","voter_config_path":"/workspace/voter_config.yaml","expected_extraction_model":"qwen2.5-vl:7b","document_folder":"/workspace/tests/stage1_vendor_identity/inv_001_easy","bounded_timeout_seconds":600,"readiness":{"checks":[{"name":"interpreter/venv","status":"pass","elapsed_seconds":0.01,"diagnostic":null},{"name":"paddle-rocm-preflight","status":"pass","elapsed_seconds":2.34,"diagnostic":null},{"name":"ollama-reachability","status":"pass","elapsed_seconds":0.08,"diagnostic":null},{"name":"ollama-version","status":"pass","elapsed_seconds":0.04,"diagnostic":null},{"name":"ollama-model-gpu-placement","status":"pass","elapsed_seconds":0.05,"diagnostic":null},{"name":"ollama-context-length","status":"pass","elapsed_seconds":0.03,"diagnostic":null},{"name":"artifact-schema-validation","status":"pass","elapsed_seconds":0.12,"diagnostic":null},{"name":"pipeline-runtime-timeout","status":"pass","elapsed_seconds":0.0,"diagnostic":null}],"overall_passed":true,"elapsed_seconds":2.67},"runtime_outcome":"success","stalled_phase":null,"failure_kind":null,"failing_check_name":null,"phase_timings":{"preprocess":4.21,"extraction":18.05,"routing":0.04,"final_payload":0.08},"total_runtime_seconds":22.38,"artifact_paths":["/workspace/tests/stage1_vendor_identity/inv_001_easy/preprocess_output.json","/workspace/tests/stage1_vendor_identity/inv_001_easy/edge_extraction_output.json","/workspace/tests/stage1_vendor_identity/inv_001_easy/routing_decision.json","/workspace/tests/stage1_vendor_identity/inv_001_easy/final_structured_payload.json"],"quality_status":"pass","quality_status_source":"gate","cpu_fallback_detection":{"ollama_post_run":"consistent","paddle_post_run":"consistent","pre_run_ollama_snapshot":{"name":"qwen2.5-vl:7b","size":4906000000,"size_vram":4906000000,"context_length":2048},"post_run_ollama_snapshot":{"name":"qwen2.5-vl:7b","size":4906000000,"size_vram":4906000000,"context_length":2048}},"diagnostic":null}
```

(Whitespace shown above for readability; the actual emitted line uses `separators=(",", ":")` and is a single line followed by exactly one `\n`.)

---

## 10. JSON line shape — `--check-only` pass

```json
{"kind":"demo_run_report","schema_version":"0.1.0","pipeline_version":"0.4.2","run_id":"…","interpreter_path":"/workspace/.venv-paddle-rocm/bin/python","voter_config_path":"/workspace/voter_config.yaml","expected_extraction_model":"qwen2.5-vl:7b","document_folder":null,"bounded_timeout_seconds":600,"readiness":{"checks":[{"name":"interpreter/venv","status":"pass","elapsed_seconds":0.01,"diagnostic":null},{"name":"paddle-rocm-preflight","status":"pass","elapsed_seconds":2.34,"diagnostic":null},{"name":"ollama-reachability","status":"pass","elapsed_seconds":0.08,"diagnostic":null},{"name":"ollama-version","status":"pass","elapsed_seconds":0.04,"diagnostic":null},{"name":"ollama-model-gpu-placement","status":"pass","elapsed_seconds":0.05,"diagnostic":null},{"name":"ollama-context-length","status":"pass","elapsed_seconds":0.03,"diagnostic":null},{"name":"artifact-schema-validation","status":"skipped","elapsed_seconds":0.0,"diagnostic":null},{"name":"pipeline-runtime-timeout","status":"skipped","elapsed_seconds":0.0,"diagnostic":null}],"overall_passed":true,"elapsed_seconds":2.55},"runtime_outcome":null,"stalled_phase":null,"failure_kind":null,"failing_check_name":null,"phase_timings":{"preprocess":null,"extraction":null,"routing":null,"final_payload":null},"total_runtime_seconds":null,"artifact_paths":null,"quality_status":null,"quality_status_source":null,"cpu_fallback_detection":{"ollama_post_run":"skipped","paddle_post_run":"skipped","pre_run_ollama_snapshot":null,"post_run_ollama_snapshot":null},"diagnostic":null}
```

Note: `artifact-schema-validation` and `pipeline-runtime-timeout` are skipped under `--check-only` (FR-018 says `--check-only` covers infrastructure checks 1–6).

---

## 11. JSON line shape — readiness fail (e.g., Ollama version too old)

```json
{"kind":"demo_run_report","schema_version":"0.1.0","pipeline_version":"0.4.2","run_id":"…","interpreter_path":"/workspace/.venv-paddle-rocm/bin/python","voter_config_path":"/workspace/voter_config.yaml","expected_extraction_model":"qwen2.5-vl:7b","document_folder":"/workspace/tests/stage1_vendor_identity/inv_001_easy","bounded_timeout_seconds":600,"readiness":{"checks":[{"name":"interpreter/venv","status":"pass","elapsed_seconds":0.01,"diagnostic":null},{"name":"paddle-rocm-preflight","status":"pass","elapsed_seconds":2.34,"diagnostic":null},{"name":"ollama-reachability","status":"pass","elapsed_seconds":0.08,"diagnostic":null},{"name":"ollama-version","status":"fail","elapsed_seconds":0.04,"diagnostic":{"checked":"Ollama /api/version","observed":"0.3.12","expected":">= 0.4.0","remediation":"Upgrade Ollama to >= 0.4.0; see scripts/start-host-ollama-rocm-wsl.sh"}},{"name":"ollama-model-gpu-placement","status":"skipped","elapsed_seconds":0.0,"diagnostic":null},{"name":"ollama-context-length","status":"skipped","elapsed_seconds":0.0,"diagnostic":null},{"name":"artifact-schema-validation","status":"skipped","elapsed_seconds":0.0,"diagnostic":null},{"name":"pipeline-runtime-timeout","status":"skipped","elapsed_seconds":0.0,"diagnostic":null}],"overall_passed":false,"elapsed_seconds":2.47},"runtime_outcome":null,"stalled_phase":null,"failure_kind":"readiness-failed","failing_check_name":"ollama-version","phase_timings":{"preprocess":null,"extraction":null,"routing":null,"final_payload":null},"total_runtime_seconds":null,"artifact_paths":null,"quality_status":null,"quality_status_source":null,"cpu_fallback_detection":{"ollama_post_run":"skipped","paddle_post_run":"skipped","pre_run_ollama_snapshot":null,"post_run_ollama_snapshot":null},"diagnostic":"readiness check 'ollama-version' failed — observed 0.3.12, expected >= 0.4.0."}
```

Note: missing `size_vram` (triage C1) is detected at the `ollama-version` check, not the `ollama-model-gpu-placement` check; the latter is `skipped`.

---

This data model is the single reference for the dataclass shapes in `src/dartwing_ocr/gpu_demo/report.py`, the JSON-schema in `contracts/demo-report-schema.md`, and the assertions in `tests/integration/gpu_demo/test_report_shape.py`.
