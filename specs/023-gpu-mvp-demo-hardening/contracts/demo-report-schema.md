# DemoRunReport JSON-line Contract

**Phase 1 contract output of [plan.md](../plan.md).** Pins the on-the-wire shape of the single `DemoRunReport` JSON line emitted on stdout (FR-019). This contract is NOT added to the contract set under `contracts/stage1_vendor_identity/v1.3.0/` — per FR-014, no contract-set bump. This file is internal documentation, not a published JSON Schema.

---

## Top-level shape

```json
{
  "kind": "demo_run_report",
  "schema_version": "0.1.0",
  "pipeline_version": "<str>",
  "run_id": "<UUID4 string>",
  "interpreter_path": "<absolute canonicalized path>",
  "voter_config_path": "<absolute path>" | null,
  "expected_extraction_model": "<str>" | null,
  "document_folder": "<absolute canonicalized path>" | null,
  "bounded_timeout_seconds": 600,
  "readiness": { … },
  "runtime_outcome": "<enum>" | null,
  "stalled_phase": "<enum>" | null,
  "failure_kind": "<enum>" | null,
  "failing_check_name": "<enum>" | null,
  "phase_timings": { "preprocess": <float>|null, "extraction": <float>|null, "routing": <float>|null, "final_payload": <float>|null },
  "total_runtime_seconds": <float> | null,
  "artifact_paths": ["<absolute path>", "<absolute path>", "<absolute path>", "<absolute path>"] | null,
  "quality_status": "<enum>" | null,
  "quality_status_source": "gate" | "evaluator" | null,
  "cpu_fallback_detection": { … },
  "diagnostic": "<str>" | null
}
```

The same **17 top-level keys** are present on every outcome (FR-019 stable-shape rule). Unknown / non-applicable values are `null`, never omitted.

---

## Field reference

### `kind` (string, required, constant)

The literal string `"demo_run_report"`. Never any other value. No `"demo_run_partial"` variant; no `"demo_check_only_report"` variant. This was a deliberate decision in round-3 Q1/Q2 — automation discriminates outcomes via the other fields (`runtime_outcome`, `failure_kind`), not via `kind`.

### `schema_version` (string, required)

The DemoRunReport schema version. Initial value `"0.1.0"`. Bumped under additive-only changes (patch), additive-with-new-required-fields (minor), or removal-of-required-field (major). The bump policy mirrors the feature 014–020 `RunSummary.SCHEMA_VERSION` lineage.

### `pipeline_version` (string, required)

The string returned by `importlib.metadata.version("dartwing-ocr")` — i.e., the installed package version from `pyproject.toml`. Fallback to the literal `"unknown"` if metadata is unresolvable. Source: R-023.2.

### `run_id` (string, required)

A UUID4 generated at command start. Used for cross-stream correlation between stdout JSON and stderr text (the first 8 hex characters appear in stderr line prefixes). Source: R-023.6.

### `interpreter_path` (string, required)

The absolute, canonicalized Python interpreter path used for the run. Captured via `os.path.realpath(sys.executable)`. Required for the `interpreter/venv` readiness diagnostic and for operator triage. Source: FR-003.

### `voter_config_path` (string | null)

The absolute path to the voter config file that was actually loaded. `null` only when the readiness phase failed before voter-config discovery completed (e.g., interpreter/venv check failed) or under invalid-input outcomes where discovery was not attempted.

### `expected_extraction_model` (string | null)

The model identifier (name + tag) extracted from the voter config; used as the lookup key into `/api/ps`. `null` whenever `voter_config_path` is `null`.

### `document_folder` (string | null)

The absolute, canonicalized path of the per-document folder that was used. `null` under `--check-only` (the flag is ignored). On invalid-input outcomes (missing source.pdf, etc.), this field captures the path that was *attempted*, not `null` — operators need to know which path failed validation.

### `bounded_timeout_seconds` (integer, required)

The 600 s pipeline-timeout budget (FR-008). Always 600 by default. Future versions might support a configurable timeout (planning decision; not in scope for v0.1.0); even then, the field would record the value actually used for this run.

### `readiness` (object, required)

See **Readiness sub-shape** below. Always populated (FR-026); even on `--check-only`, the readiness section is the primary payload of the report.

### `runtime_outcome` (string | null)

Closed enum (FR-020):
- `"success"`
- `"failed_at_preprocess"`
- `"failed_at_extraction"`
- `"failed_at_routing"`
- `"failed_at_final_payload"`
- `"timeout"`

`null` only when no pipeline ran (readiness fail, invalid input, or `--check-only`).

### `stalled_phase` (string | null)

Closed enum: `"preprocess"` | `"extraction"` | `"routing"` | `"final_payload"`. Non-null **only** when `runtime_outcome == "timeout"`. `null` for every other outcome including `--check-only`.

### `failure_kind` (string | null)

Closed enum that disambiguates the cause class for non-success outcomes:
- `"readiness-failed"` — exit code 1
- `"invalid-input"` — exit code 2
- `"pipeline-runtime-timeout"` — exit code 3 (paired with `runtime_outcome == "timeout"`)
- `"pipeline-runtime-error"` — exit code 4 (generic phase failure)
- `"cpu-fallback-detected"` — exit code 4 (post-run interrogation rewrote a `success` to `failed_at_extraction`)
- `"artifact-schema-validation-failed"` — exit code 5
- `"post-run-interrogation-unreachable"` — paired with success or any `failed_at_*` when the post-run probe could not confirm device state

`null` on outcome `success` (when CPU-fallback detection returned `"consistent"` for both probes).

### `failing_check_name` (string | null)

Closed enum matching the 8 readiness check names. Non-null **only** when at least one readiness check failed; identifies the first failing check in the fixed execution order (FR-016 expanded). `null` on success and on non-readiness failures (`runtime_outcome == "failed_at_extraction"`, etc.).

### `phase_timings` (object, required)

Always present. Exactly 4 keys: `preprocess`, `extraction`, `routing`, `final_payload`. Values are floats (wall-clock seconds) or `null`. See data-model §3 for the value-presence rules.

### `total_runtime_seconds` (float | null)

Total pipeline wall-clock from the end of readiness phase to the end of the last phase that ran. `null` whenever no pipeline ran.

### `artifact_paths` (array of 4 strings | null)

The absolute paths to the four canonical artifacts, in their canonical order: `[preprocess_output.json, edge_extraction_output.json, routing_decision.json, final_structured_payload.json]`. `null` when no pipeline ran. On partial-pipeline failures, the paths are still listed (some may not exist on disk because the corresponding phase did not produce them).

### `quality_status` (string | null)

Closed enum (FR-010): `"pass"` | `"weak"` | `"review_required"`. `null` whenever no pipeline ran. See R-023.20 for the derivation truth-table.

### `quality_status_source` (string | null)

`"gate"` (derivation from evidence-gate + `manual_review_required`) or `"evaluator"` (when `--with-evaluator` augmented the derivation). `null` when `quality_status` is `null`.

### `cpu_fallback_detection` (object, required)

See **CPUFallbackDetection sub-shape** below. Always present (FR-019 stable-shape rule); fields are `"skipped"` when no pipeline ran.

### `diagnostic` (string | null)

A single human-readable summary string. On success: `null`. On any failure: a one-sentence summary of the primary failure. This duplicates the per-check `diagnostic.observed/expected/remediation` shape under `readiness.checks[*].diagnostic` (which is the structured form); the top-level `diagnostic` is the operator-friendly one-liner.

---

## Readiness sub-shape

```json
{
  "checks": [ … ],
  "overall_passed": true | false,
  "elapsed_seconds": <float>
}
```

- `checks`: **exactly 8 entries**, ordered as the FR-016 closed vocabulary (interpreter/venv → paddle-rocm-preflight → ollama-reachability → ollama-version → ollama-model-gpu-placement → ollama-context-length → artifact-schema-validation → pipeline-runtime-timeout). Each entry has the **ReadinessCheck sub-shape** below.
- `overall_passed`: true iff every check that ran returned `"pass"`. Formally: there is at least one check with status `"pass"`, AND no check has status `"fail"`. Status `"skipped"` is treated as "not applicable to this run mode" and does NOT block `overall_passed: true`.
  - Under `--check-only`: checks 1–6 must all be `"pass"`; checks 7–8 are `"skipped"` (not applicable); `overall_passed: true`.
  - Under a full pipeline pass: all 8 checks must be `"pass"`; `overall_passed: true`.
  - When any check has status `"fail"`: `overall_passed: false`, regardless of how many others passed or were skipped.

- `elapsed_seconds`: total wall-clock of the readiness phase. SC-007 caps this at 10 s on a warm workstation under `--check-only`.

---

## ReadinessCheck sub-shape

```json
{
  "name": "<closed enum>",
  "status": "pass" | "fail" | "skipped",
  "elapsed_seconds": <float>,
  "diagnostic": { … } | null
}
```

- `name`: one of the 8 names from FR-016 closed vocabulary.
- `status`: closed enum. `"skipped"` is used when an earlier check failed (every check after the first failure is `"skipped"`).
- `elapsed_seconds`: wall-clock for this individual check. `0.0` for skipped checks.
- `diagnostic`: object with `checked` / `observed` / `expected` / `remediation` keys (R-023.11). `null` when `status == "pass"` or `status == "skipped"`.

---

## CheckDiagnostic sub-shape

```json
{
  "checked": "<short prose>",
  "observed": <machine-readable value>,
  "expected": <machine-readable value>,
  "remediation": "<imperative sentence>"
}
```

- `checked`: short prose, e.g., `"Paddle device backend"`, `"Ollama /api/ps for qwen2.5-vl:7b"`, `"Ollama /api/version"`.
- `observed`: the value found (`"cpu"`, `null`, `"0.3.12"`, an `OllamaModelStatus`-shaped object, etc.).
- `expected`: the value required (`"rocm_gpu"`, `">= 0.4.0"`, `"size_vram == size and size_vram > 0"`).
- `remediation`: one imperative sentence ending with a period, telling the operator what to do.

---

## CPUFallbackDetection sub-shape

```json
{
  "ollama_post_run": "consistent" | "fell_back" | "unreachable" | "skipped",
  "paddle_post_run": "consistent" | "fell_back" | "unreachable" | "skipped",
  "pre_run_ollama_snapshot": { … } | null,
  "post_run_ollama_snapshot": { … } | null
}
```

- Probe results per R-023.15.
- `"skipped"` is used when no pipeline ran (so a post-run probe is not applicable).
- The two snapshot fields capture the `/api/ps` model entry at readiness time and post-run time, for triage. Each snapshot is a small dict with `name`, `size`, `size_vram`, `context_length` (or `null` if `/api/ps` did not expose `context_length`).

---

## Outcome → field-population matrix (normative)

The same 17 top-level keys are emitted on every outcome. Per-outcome values:

| Field | success | timeout | failed_at_<phase> | readiness-fail | invalid-input | --check-only pass | --check-only fail |
|---|---|---|---|---|---|---|---|
| `kind` | constant | constant | constant | constant | constant | constant | constant |
| `schema_version` | "0.1.0" | "0.1.0" | "0.1.0" | "0.1.0" | "0.1.0" | "0.1.0" | "0.1.0" |
| `pipeline_version` | str | str | str | str | str | str | str |
| `run_id` | UUID4 | UUID4 | UUID4 | UUID4 | UUID4 | UUID4 | UUID4 |
| `interpreter_path` | str | str | str | str | str | str | str |
| `voter_config_path` | str | str | str | str-or-null | str-or-null | str | str-or-null |
| `expected_extraction_model` | str | str | str | str-or-null | str-or-null | str | str-or-null |
| `document_folder` | str | str | str | str | str-or-null | **null** | **null** |
| `bounded_timeout_seconds` | 600 | 600 | 600 | 600 | 600 | 600 | 600 |
| `readiness` | full (8 checks) | full | full | partial (later checks `skipped`) | partial-or-not-attempted | full (6 ran, 2 skipped) | partial |
| `runtime_outcome` | "success" | "timeout" | "failed_at_<phase>" | **null** | **null** | **null** | **null** |
| `stalled_phase` | null | "<phase>" | null | null | null | null | null |
| `failure_kind` | null (or "post-run-interrogation-unreachable") | "pipeline-runtime-timeout" | "pipeline-runtime-error" / "cpu-fallback-detected" / "artifact-schema-validation-failed" | "readiness-failed" | "invalid-input" | null | "readiness-failed" |
| `failing_check_name` | null | null | null | str | null | null | str |
| `phase_timings.{preprocess,extraction,routing,final_payload}` | floats | mix (timed phases float, untimed null) | mix | all null | all null | all null | all null |
| `total_runtime_seconds` | float | float | float | null | null | null | null |
| `artifact_paths` | 4 paths | 4 paths (some may not exist on disk) | 4 paths (some may not exist on disk) | null | null | null | null |
| `quality_status` | enum | null | null | null | null | null | null |
| `quality_status_source` | "gate" or "evaluator" | null | null | null | null | null | null |
| `cpu_fallback_detection.*` | "consistent" / "consistent" | mix | mix | "skipped" / "skipped" | "skipped" / "skipped" | "skipped" / "skipped" | "skipped" / "skipped" |
| `diagnostic` | null | str | str | str | str | null | str |

Every cell is enforced by `tests/integration/gpu_demo/test_report_shape.py` (one assertion per cell per outcome class).

---

## Compatibility & versioning

- The schema is **additive** under patch bumps (e.g., 0.1.1 adds an optional new top-level field with default null). Consumers MUST ignore unknown top-level keys.
- Required-field removal or rename is a **major** bump (1.0.0).
- The closed-vocabulary changes (`runtime_outcome` adds a new value, `failure_kind` adds a new value) are **minor** bumps (0.2.0).
- **Adding a 9th (or Nth) readiness check** is an additive vocabulary change → **minor** schema_version bump (e.g., 0.1.x → 0.2.0). The new check is inserted into the fixed-order vocabulary at a position determined by its dependencies (e.g., a new check that depends on Ollama reachability slots after check 3 but before any check depending on it). Existing 8 names retain their existing positions; consumers iterating `readiness.checks[]` by position must not assume a fixed length, only that the order respects declared dependencies.
- **`CheckDiagnostic.observed` byte cap (Q5):** any embedded JSON blob inside `observed` is truncated at 2 KiB with a trailing `"… [truncated]"` sentinel. Producers MUST enforce this cap before JSON-serializing the diagnostic. This keeps the `DemoRunReport` JSON line size bounded for automation that buffers it.
- **`quality_status` non-null iff `runtime_outcome == "success"` (Q3):** the cross-field bi-conditional. Consumers can treat a `quality_status` of `null` as authoritative evidence the pipeline did not complete, without inspecting `runtime_outcome` separately.
- Consumers SHOULD check `schema_version` and refuse to parse on a major-version mismatch.
- Producers MUST emit `schema_version` on every report.
