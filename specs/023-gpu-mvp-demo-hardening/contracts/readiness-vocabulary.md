# Readiness Check Vocabulary Contract

**Phase 1 contract output of [plan.md](../plan.md).** Pins the 8 named readiness checks, their fixed execution order, the dependency / skip semantics, and the per-check pass/fail predicate. Implements FR-016 (closed vocabulary + fixed order), FR-026 (per-check status), and the triage C1 resolution.

---

## Vocabulary scope note

The 8 named checks form the **closed diagnostic vocabulary** for the `failing_check_name` field and the per-check status entries in `readiness.checks[]`. They are NOT all pre-pipeline:

- **Pre-pipeline (checks 1–6)** run during the readiness phase before any pipeline work. These are the "infrastructure readiness" checks `--check-only` exercises (FR-018).
- **Runtime / post-pipeline (checks 7–8)** are gates that emit verdicts during or after pipeline execution:
  - Check 7 `artifact-schema-validation` runs after the pipeline completes, validating each of the 4 canonical artifacts.
  - Check 8 `pipeline-runtime-timeout` is a `signal.alarm` monitor that fires if the 600 s budget elapses during any pipeline phase.

The fixed-order skip rule (FR-026) applies to all 8 in declaration order: a failure at any earlier check marks every later check as `"skipped"`, even when the later check would have been a runtime monitor. This keeps the diagnostic vocabulary self-consistent across run modes.

---

## Fixed execution order

The 8 named checks MUST be executed in this order. Implementations MUST NOT parallelize or reorder them.

| # | Name | Skipped under `--check-only`? | Dependency (must pass before this runs) |
|---|------|-------------------------------|---------------|
| 1 | `interpreter/venv` | no | — |
| 2 | `paddle-rocm-preflight` | no | 1 |
| 3 | `ollama-reachability` | no | 1 |
| 4 | `ollama-version` | no | 3 |
| 5 | `ollama-model-gpu-placement` | no | 3, 4 |
| 6 | `ollama-context-length` | no | 3, 4 |
| 7 | `artifact-schema-validation` | **yes** | 1–6 + pipeline run |
| 8 | `pipeline-runtime-timeout` | **yes** | 1–6 + pipeline run |

**Skip rule (FR-026 + triage C1):** When check K fails, every check K+1 … 8 has `status == "skipped"`. The `failing_check_name` field on `DemoRunReport` is the name of check K (the first failure in the fixed order).

**`--check-only` interaction:** Checks 7 and 8 are not applicable to readiness-only mode (they exist only because the pipeline ran). Under `--check-only`, they are reported with `status == "skipped"` and `elapsed_seconds == 0.0` even when all of checks 1–6 pass.

---

## Per-check predicate reference

### 1 · `interpreter/venv`

**Probe:** Canonicalize `sys.executable` via `os.path.realpath`. Compare against the expected venv prefix (`.venv-paddle-rocm` or its successor name read from a small allowlist constant).

**Pass criterion:** Canonicalized interpreter path is under the expected venv prefix.

**Fail diagnostic:**
- `checked`: `"Python interpreter path"`
- `observed`: the resolved interpreter path
- `expected`: `"<workspace>/.venv-paddle-rocm/bin/python"` (or the canonical form for the workstation)
- `remediation`: `"Activate the Paddle ROCm venv: source .venv-paddle-rocm/bin/activate"`

### 2 · `paddle-rocm-preflight`

**Probe:** Call the feature 014 Paddle ROCm preflight entry point in-process; the preflight imports `paddlepaddle_dcu`, queries the device backend, returns a `PreflightResult`.

**Pass criterion:** `PreflightResult.device == "rocm_gpu"`.

**Fail diagnostic (single check name, two distinct shapes per Q7):**

The check name on failure is always `paddle-rocm-preflight` (FR-016 closed vocabulary is preserved). The two failure modes distinguish themselves via the `observed` shape:

- **Wheel not installed at all (ImportError):**
  - `checked`: `"Paddle ROCm wheel import"`
  - `observed`: `{"import_error": "ImportError: No module named 'paddlepaddle_dcu'"}` (or similar `ModuleNotFoundError` message)
  - `expected`: `"paddlepaddle_dcu importable from active venv"`
  - `remediation`: `"Install paddlepaddle-dcu in .venv-paddle-rocm (it is not currently importable)."`

- **Wheel installed but device check reports non-GPU (stale wheel / broken ROCm):**
  - `checked`: `"Paddle device backend"`
  - `observed`: `{"import_ok": true, "device": "cpu"}` (or `{"device": "unknown", "preflight_error": "<message>"}`)
  - `expected`: `"rocm_gpu"`
  - `remediation`: `"Reinstall paddlepaddle-dcu in .venv-paddle-rocm and verify ROCm is exposed to WSL2 (the wheel imports but the device is not the GPU)."`

The shape difference lets operators tell at a glance which remediation applies, without expanding the readiness vocabulary to two separate check names (closed vocab stays at 8 names).

**Test mode:** Under CPU pytest, this check is monkeypatched to return `PreflightResult.device = "rocm_gpu"` (or parameterized variants for each of the two failure shapes). The real Paddle import never happens on CI.

### 3 · `ollama-reachability`

**Probe:** HTTP GET `OLLAMA_BASE_URL/api/ps` with `httpx` and a 2-second timeout (well below the 10-second aggregate readiness budget).

**Pass criterion:** Response status is 200 and the JSON body parses successfully (the body itself is consumed by check 5).

**Fail diagnostic:**
- `checked`: `f"Ollama {OLLAMA_BASE_URL}/api/ps"`
- `observed`: the exception class name + message (`"httpx.ConnectError: All connection attempts failed"`, etc.) or the non-200 status
- `expected`: `"HTTP 200 with parseable JSON body"`
- `remediation`: `"Start host Ollama: scripts/start-host-ollama-rocm-wsl.sh"`

### 4 · `ollama-version`

**Probe:** HTTP GET `OLLAMA_BASE_URL/api/version`; parse the `version` field as `packaging.version.Version`; compare against the minimum supported version `Version("0.4.0")` (R-023.10).

**Pass criterion:** Probed version ≥ `0.4.0`.

**Fail diagnostic:**
- `checked`: `f"Ollama {OLLAMA_BASE_URL}/api/version"`
- `observed`: the version string returned (e.g., `"0.3.12"`)
- `expected`: `">= 0.4.0"`
- `remediation`: `"Upgrade Ollama to >= 0.4.0; see scripts/start-host-ollama-rocm-wsl.sh."`

This check pre-empts check 5 (`ollama-model-gpu-placement`) when the running Ollama version is too old to reliably expose `size_vram` (triage C1 / spec FR-023).

### 5 · `ollama-model-gpu-placement`

**Probe:** Re-use the `/api/ps` JSON body from check 3. Find the entry whose `name` matches `expected_extraction_model` from the voter config. Extract `size` and `size_vram` integer fields.

**Pass criterion:** Matching entry exists AND `size_vram > 0` AND `size_vram == size` (strict equality, no tolerance — FR-005).

**Fail diagnostic (model entry missing):**
- `checked`: `f"Ollama /api/ps for model '{expected_extraction_model}'"`
- `observed`: `null` (model not found)
- `expected`: `f"entry with name '{expected_extraction_model}' present"`
- `remediation`: `f"Load the model: ollama pull {expected_extraction_model} or ensure it is referenced before the demo runs."`

**Fail diagnostic (size_vram == 0 or partial placement):**
- `checked`: `f"GPU placement of '{expected_extraction_model}'"`
- `observed`: `{"size": 4906000000, "size_vram": 0}` (or partial values)
- `expected`: `"size_vram > 0 AND size_vram == size"`
- `remediation`: `"Restart Ollama on a fresh GPU context; the model is partially or fully on CPU."`

### 6 · `ollama-context-length`

**Probe:** Re-use the `/api/ps` JSON body from check 3. Find the matching model entry. Read the `context_length` field if present (the field is exposed on Ollama ≥ 0.4.0 thanks to the version-check guard).

**Pass criterion:**
- If `/api/ps` exposes `context_length`: required value ≥ `int(os.environ.get("OLLAMA_CONTEXT_LENGTH", "2048"))`. The env var is the lower bound the demo requires; when unset, the demo requires `2048`. When set above `2048`, the demo requires the higher value (operator-overridable up, not down).
- If `/api/ps` does NOT expose `context_length` (which would only happen if the Ollama version probe missed something — defensive case): the check returns `"pass"` and a soft `WARN:` stderr line, with the runtime path catching the downstream context-window error (FR-006 fallback).

**Fail diagnostic:**
- `checked`: `f"Ollama context length for '{expected_extraction_model}'"`
- `observed`: the actual `context_length` (e.g., `1024`)
- `expected`: `f">= {OLLAMA_CONTEXT_LENGTH or 2048}"`
- `remediation`: `"Restart host Ollama with OLLAMA_CONTEXT_LENGTH=2048; see scripts/start-host-ollama-rocm-wsl.sh."`

### 7 · `artifact-schema-validation`

**Probe:** After the pipeline runs (and only after all 4 phases produced their artifacts), validate each of the four canonical artifact files against its JSON Schema in `contracts/stage1_vendor_identity/v1.3.0/`. Uses the existing `dartwing_ocr.validator` API.

**Pass criterion:** All 4 artifacts validate against their schemas. Note: the validator returns a typed result; any validation error in any artifact → fail.

**Fail diagnostic:**
- `checked`: `"Schema validation of 4 canonical artifacts"`
- `observed`: a list of `{path: "<artifact path>", error: "<validator message>"}` objects covering every artifact that failed validation. Length 1–4. The list preserves the canonical artifact order (`preprocess_output.json`, `edge_extraction_output.json`, `routing_decision.json`, `final_structured_payload.json`).
- `expected`: `"all four artifacts schema-valid against v1.3.0 contract set"`
- `remediation`: `"Inspect the listed artifact(s); a multi-artifact failure usually indicates a deeper pipeline regression — start with the earliest failure in canonical order."`

Skipped under `--check-only`.

### 8 · `pipeline-runtime-timeout`

**Probe:** Wall-clock from `signal.alarm(600)` set at pipeline phase 1 start to `signal.alarm(0)` cleared after phase 4 success.

**Pass criterion:** Pipeline completed in less than 600 s.

**Fail diagnostic:**
- `checked`: `"Pipeline runtime"`
- `observed`: `f">600 seconds (stalled in phase '{stalled_phase}')"`
- `expected`: `"<= 600 seconds"`
- `remediation`: `"Inspect partial artifacts left in the per-document folder; the stalled phase is identified in 'stalled_phase'. Check Ollama and Paddle health."`

Skipped under `--check-only`.

---

## Aggregate `readiness.elapsed_seconds` budget

SC-007 caps the sum of `elapsed_seconds` for checks 1–6 (under `--check-only` mode, on a warm workstation) at **10 seconds**. Per-check informal budgets (no enforcement gate):

| Check | Warm-cache informal budget |
|---|---|
| 1 · interpreter/venv | < 0.1 s |
| 2 · paddle-rocm-preflight | < 5 s (Paddle import dominates; cold start can exceed 10 s — R-023.9) |
| 3 · ollama-reachability | < 2 s (HTTP timeout) |
| 4 · ollama-version | < 1 s |
| 5 · ollama-model-gpu-placement | < 1 s (re-uses /api/ps body) |
| 6 · ollama-context-length | < 1 s (re-uses /api/ps body) |

Checks 7 and 8 only fire on pipeline runs, so they do not count against the SC-007 10-second budget.

---

## Diagnostic shape contract (R-023.11)

Every per-check `diagnostic` field on a `"fail"` status MUST conform to:

```json
{
  "checked": "<short prose>",
  "observed": <machine-readable value or short string>,
  "expected": <machine-readable value or short string>,
  "remediation": "<imperative sentence ending with a period>"
}
```

The same diagnostic content MUST also appear on stderr as:

```
ERROR:[<8-char run_id>] readiness check '<name>' failed — observed <repr>, expected <repr>. Remediation: <remediation>
```

This consistency is enforced by `tests/integration/gpu_demo/test_readiness_failures.py` (one assertion per check class).

---

## Test coverage map

| Check | Test file | Pass-path test | Fail-path test(s) |
|---|---|---|---|
| 1 · interpreter/venv | `test_readiness_failures.py::test_interpreter_venv_*` | yes | wrong interpreter path |
| 2 · paddle-rocm-preflight | `test_readiness_failures.py::test_paddle_*` | yes | `PaddleROCmPreflightError`; device == "cpu" |
| 3 · ollama-reachability | `test_readiness_failures.py::test_ollama_reach_*` | yes | `httpx.ConnectError`; non-200; malformed JSON |
| 4 · ollama-version | `test_readiness_failures.py::test_ollama_version_*` | yes | version < 0.4.0; `/api/version` unreachable |
| 5 · ollama-model-gpu-placement | `test_readiness_failures.py::test_ollama_placement_*` | yes | model missing; `size_vram == 0`; `size_vram < size` |
| 6 · ollama-context-length | `test_readiness_failures.py::test_ollama_ctx_*` | yes | `context_length` below required value |
| 7 · artifact-schema-validation | `test_readiness_failures.py::test_schema_validation_*` | yes (full pipeline) | corrupted artifact post-pipeline |
| 8 · pipeline-runtime-timeout | `test_readiness_failures.py::test_runtime_timeout_*` | yes (warm full pipeline) | injected sleep to exceed 600 s |

Plus the order/skip tests in `test_readiness_order.py`:
- All 8 checks pass → `failing_check_name == null`, every status `"pass"`.
- Check 1 fails → checks 2–8 all `"skipped"`; `failing_check_name == "interpreter/venv"`.
- Check 4 fails → checks 1–3 `"pass"`, check 4 `"fail"`, checks 5–8 `"skipped"`; `failing_check_name == "ollama-version"`.
- `--check-only` + all pass → checks 1–6 `"pass"`, checks 7–8 `"skipped"`.
- `--check-only` + check 3 fails → checks 1–2 `"pass"`, check 3 `"fail"`, checks 4–8 `"skipped"`.
