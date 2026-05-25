# CLI Contract: `python -m dartwing_ocr.gpu_demo`

**Phase 1 contract output of [plan.md](../plan.md).** Pins the operator-facing surface of the GPU MVP demo CLI. Every flag, default, exit code, and observable side-effect documented below is normative.

---

## Invocation forms

```sh
python -m dartwing_ocr.gpu_demo [OPTIONS]
dartwing-gpu-demo [OPTIONS]              # console-script equivalent (optional; same behavior)
```

Both forms accept the identical flag set and produce identical output.

---

## Closed flag set

| Flag | Type | Default | Required? | Purpose |
|---|---|---|---|---|
| `--check-only` | bool (no value) | off | no | Run readiness preflight only; skip pipeline (FR-018). |
| `--document-folder <PATH>` | string | `tests/stage1_vendor_identity/inv_001_easy/` | no | Override the canonical per-document folder (FR-027). Ignored under `--check-only`. |
| `--voter-config <PATH>` | string | (auto-discovery from features 005 / 021) | no | Explicit voter-config file (FR-005). |
| `--preset <NAME>` | string (closed set) | `header-first-v1` | no | Preprocessing preset (FR-011). Allowed values: `header-first-v1`, `full-ocr`. Ignored under `--check-only`. |
| `--with-evaluator` | bool (no value) | off | no | Invoke feature 022 evaluator after pipeline (FR-022). Ignored under `--check-only`. |

No other flags are accepted. Any unrecognized flag MUST cause the demo to exit 2 (invalid input / usage) before any side effects.

**Closed flag semantics — anti-flags (explicitly NOT supported):**

- No `--force` (FR-017 says no manual cleanup needed; deterministic overwrite is unconditional).
- No `--clean` (same).
- No `--no-readiness` (readiness is mandatory; cannot be bypassed).
- No `--verbose` / `--quiet` (R-023.7 fixes stderr severity format).
- No `--timeout <N>` (FR-008 pins 600 s; tuning is a spec change).
- No `--output <PATH>` (FR-019 mandates stdout JSON line; no file output).
- No `--config <PATH>` for a TOML/YAML config file (configuration is only via these 5 flags + env).

---

## Flag interactions

Flag combinations and their resolution (`triage A2` / R-023's `--check-only` semantics):

| Combination | Behavior |
|---|---|
| `--check-only` alone | Runs FR-016 checks 1–6 only; ignores `--document-folder`, `--preset`, `--with-evaluator`; emits `DemoRunReport` with all pipeline/quality/timing fields null. |
| `--check-only --document-folder X` | `X` is **ignored**; an `INFO:` stderr line is emitted noting the flag was disregarded. |
| `--check-only --preset full-ocr` | `--preset` is **ignored**; same INFO-line emission. |
| `--check-only --with-evaluator` | `--with-evaluator` is **ignored**; same INFO-line emission. |
| `--with-evaluator` (no sidecar in folder) | Pipeline runs normally; evaluator is **skipped** with a `WARN: sidecar not found, skipping evaluator` stderr line; `quality_status_source` stays `"gate"` (FR-022). |
| `--with-evaluator` (sidecar present) | Pipeline runs; evaluator runs as a subprocess after; `quality_status_source` becomes `"evaluator"`; evaluator can downgrade `quality_status` but not upgrade it (R-023.20). |
| `--voter-config X` (X exists, valid) | `X` is used; auto-discovery is bypassed entirely. |
| `--voter-config X` (X missing / malformed / no model field) | Exit 2 with named diagnostic (FR-005). |
| `--preset header-first-v1` (default) | Feature 018 header-first preset. |
| `--preset full-ocr` | Feature 018 full-OCR preset (opt-in only). |

---

## Environment variables

| Variable | Required? | Default | Purpose |
|---|---|---|---|
| `OLLAMA_BASE_URL` | no | `http://localhost:11434` | Identifies the host Ollama instance (FR-006, R-023.14). |
| `OLLAMA_CONTEXT_LENGTH` | yes (read by both demo + startup script) | `2048` | Read by `scripts/start-host-ollama-rocm-wsl.sh` to configure the running Ollama, AND read by the demo's `ollama-context-length` readiness check (FR-006, check 6 in the vocabulary) to know what minimum to require. When unset in the demo's environment, the demo defaults to requiring `2048` regardless. When set, the demo requires that the running Ollama's `/api/ps.context_length` ≥ the env var's value. |
| `PYTHONPATH` | no | (unset) | Standard Python lookup; the demo expects to be run with the package importable. |

The demo does NOT read any other environment variable. If automation needs to influence configuration, it must use the CLI flags.

**ROCm/HSA env vars (Q12 disposition):** Variables such as `HSA_OVERRIDE_GFX_VERSION`, `HIP_VISIBLE_DEVICES`, `MIOPEN_FIND_MODE`, `MIOPEN_USER_DB_PATH`, and other ROCm-stack tunables are read by `scripts/start-host-ollama-rocm-wsl.sh` (operator-managed via the startup script) and are inherited into the demo's process environment via `os.environ` for the Paddle ROCm preflight's own internal use. The demo CLI itself does NOT read, validate, or surface those values; the runbook documents that operators must not unset them between starting Ollama and running the demo.

---

## Exit codes (closed table, FR-021)

| Code | RuntimeOutcome | failure_kind | Meaning |
|------|---|---|---|
| `0` | `success` | `null` | Pipeline completed, all 4 artifacts schema-valid, no CPU fallback detected, `quality_status` derived. |
| `1` | `null` (no pipeline) | `readiness-failed` | One or more named readiness checks failed; pipeline did not run. Failing check name is in the report under `failing_check_name`. |
| `2` | `null` (no pipeline) | `invalid-input` | Bad CLI flags, missing `source.pdf`, missing/malformed voter config, symlink-escape on eager-delete target, or any other input-validation failure. Pipeline did not run. |
| `3` | `timeout` | `pipeline-runtime-timeout` | Pipeline exceeded the 600 s bounded timeout; `stalled_phase` identifies which phase was executing when the budget elapsed. Partial artifacts left in place. |
| `4` | `failed_at_<phase>` | `pipeline-runtime-error` or `cpu-fallback-detected` | Pipeline failed during a phase; `runtime_outcome` identifies the phase. Partial artifacts left in place. CPU-fallback detection (post-run interrogation) maps here when a fallback is detected even though earlier checks passed. |
| `5` | `failed_at_final_payload` | `artifact-schema-validation-failed` | One or more of the four canonical artifacts failed schema validation post-run. Partial artifacts left in place. |

No other exit codes are produced.

**Sub-module exception → exit code mapping** (operative table per R-023.3):

| Caught exception (in-process) | Exit | Diagnostic |
|---|---|---|
| `PaddleROCmPreflightError` (raised by readiness phase) | 1 | failing check = `paddle-rocm-preflight` |
| `httpx.ConnectError` to `OLLAMA_BASE_URL` | 1 | failing check = `ollama-reachability` |
| `VoterConfigUnreadable` / `VoterConfigMalformed` / `VoterConfigMissingModel` | 2 | failure_kind = `invalid-input` |
| `SourcePDFMissing` | 2 | failure_kind = `invalid-input` |
| `EagerDeleteEscapeError` | 2 | failure_kind = `invalid-input` |
| `EagerDeleteFailed` (perm / I/O) | 2 | failure_kind = `invalid-input` |
| `TimeoutError` (signal.SIGALRM after 600 s) | 3 | `stalled_phase` set |
| `PreprocessError` | 4 | `runtime_outcome = failed_at_preprocess` |
| `ExtractionError` / `JSONRepairError` | 4 | `runtime_outcome = failed_at_extraction` |
| `OllamaContextWindowError` | 4 | `runtime_outcome = failed_at_extraction`, diagnostic points at startup script (FR-006 fallback) |
| `RoutingError` | 4 | `runtime_outcome = failed_at_routing` |
| `AssemblerInvariantError` | 4 | `runtime_outcome = failed_at_final_payload` |
| `ValidationError` (post-run schema) | 5 | failing check = `artifact-schema-validation` |
| CPU fallback detected post-run | 4 | `runtime_outcome = failed_at_extraction`, `failure_kind = cpu-fallback-detected` |

---

## stdout / stderr discipline (FR-019)

**stdout:** Exactly one line. UTF-8 encoded. Single JSON object. No leading or trailing whitespace. Newline-terminated (one `\n`). No second line. Contains the `DemoRunReport` (data-model §1).

**stderr:** Human-readable progress, warnings, and errors. Each line is prefixed with severity and run-id:
```
INFO:[a1b2c3d4] readiness: paddle-rocm-preflight → pass (0.42s)
WARN:[a1b2c3d4] --with-evaluator: semantic_table_truth.json not found in /path/to/folder; skipping evaluator
ERROR:[a1b2c3d4] readiness check 'ollama-version' failed — observed 0.3.12, expected >= 0.4.0
```
- Severity is one of `INFO`, `WARN`, `ERROR`.
- The 8-char run-id prefix (first 8 hex chars of the `run_id` UUID4 in `DemoRunReport`) lets operators correlate stderr lines with the stdout JSON (R-023.6).
- Stderr is line-buffered (`sys.stderr.reconfigure(line_buffering=True)`) so progress appears in real time during the 600 s window.

**Success-path stderr signals (Q1, Q2):** On every successful exit the demo MUST emit one final stderr `INFO:` line immediately before the `DemoRunReport` JSON line on stdout:

- Full successful pipeline run: `INFO:[<run_id>] runtime: success / quality: <quality_status>` (e.g., `quality: pass`).
- Successful `--check-only` run: `INFO:[<run_id>] readiness passed (<elapsed_seconds>s)`.

This gives operators a visible "success" cue without parsing JSON, while preserving stdout's JSON-only invariant.

**Sub-module stderr propagation (Q10):** When the orchestrator invokes feature 003 preprocess / feature 005 extract / feature 008 router / feature 009 assembler in-process (R-023.1) — or the feature 022 evaluator as a subprocess (R-023.13) — any stderr output emitted by those sub-modules MUST be captured and replayed through `log.info(run_id, f"<phase>: <captured-line>")` so every stderr line carries the unified `INFO:[<run_id>]` prefix plus a phase tag from the closed set (`preprocess:` / `extraction:` / `routing:` / `final_payload:` / `evaluator:`). Sub-module stdout (their own `kind: "run_summary"` JSON lines) is consumed in-process by the orchestrator and MUST NOT appear on the demo's stdout — only the single `DemoRunReport` JSON line on stdout per FR-019.

**The demo command MUST NOT** emit any other stream — no log file, no progress bar, no temporary files outside the canonicalized per-document folder.

---

## Idempotency contract (FR-017)

1. At run start (after readiness passes; before any phase runs), eager-delete the four canonical artifact basenames in the canonicalized per-document folder:
   - `preprocess_output.json`
   - `edge_extraction_output.json`
   - `routing_decision.json`
   - `final_structured_payload.json`
2. If any of the four resolves (via symlink) to a path outside the canonicalized folder → exit 2 before any delete proceeds.
3. If any delete fails (permission, I/O) → exit 2 before any phase runs.
4. Delete is idempotent on missing files (no failure if a file does not exist).
5. No other file in the folder is touched. `source.pdf`, `expected.json`, `notes.md`, `semantic_table_truth.json`, debug PNGs, any prior `evaluation_document.json` — all preserved (SC-010).
6. Under `--check-only`: NO eager-delete (no pipeline runs).

---

## Determinism contract (SC-006)

Three consecutive invocations of the demo command from a fresh shell, against the canonical fixture, on the same workstation, with the same Ollama and voter config, MUST produce:

1. **Identical** `readiness.overall_passed` across the three runs.
2. **Identical** `runtime_outcome` across the three runs.
3. **Identical** `quality_status` across the three runs.
4. **Byte-identical** content for `preprocess_output.json`, `routing_decision.json`, `final_structured_payload.json` (the three deterministic artifacts; round-2 Q10).
5. `edge_extraction_output.json` content MAY differ (model nondeterminism is acceptable).
6. `phase_timings.*` MAY differ within reasonable variance (no enforced bound).

SC-006 is the gate for adopting the demo as the MVP integration-test checkpoint.

---

## --check-only contract (FR-018)

When `--check-only` is set:

1. Readiness checks 1–6 (interpreter/venv → ollama-context-length) execute.
2. Checks 7 (artifact-schema-validation) and 8 (pipeline-runtime-timeout) are marked `skipped` in the report (they apply only to a pipeline run).
3. **No** pipeline phase runs.
4. **No** eager-delete is performed.
5. **No** post-run device interrogation runs (`cpu_fallback_detection.*` are `"skipped"`).
6. The `DemoRunReport` is emitted with: `runtime_outcome = null`, `stalled_phase = null`, `quality_status = null`, `quality_status_source = null`, `phase_timings.* = null`, `total_runtime_seconds = null`, `artifact_paths = null`, `document_folder = null`.
7. Exit code: `0` if all 6 infrastructure checks passed; `1` if any failed.
8. Wall-clock budget: ≤ 10 s on a warm workstation (SC-007).

---

## Help and version

The CLI supports `--help` (prints help text to stdout — this is the only stdout output that is not the `DemoRunReport` line, and is explicitly an exit-without-running case) and `--version` (prints `dartwing-gpu-demo <pipeline_version>` to stdout).

Both `--help` and `--version` exit with code 0 without emitting a `DemoRunReport`. This is the only documented exception to the "stdout contains exactly one JSON line" rule.

---

## Worked examples

### Happy path (operator on configured workstation):

```sh
$ scripts/start-host-ollama-rocm-wsl.sh             # operator step (not part of demo)
$ source .venv-paddle-rocm/bin/activate              # operator step
$ python -m dartwing_ocr.gpu_demo
INFO:[a1b2c3d4] readiness: interpreter/venv → pass (0.01s)
INFO:[a1b2c3d4] readiness: paddle-rocm-preflight → pass (2.34s)
INFO:[a1b2c3d4] readiness: ollama-reachability → pass (0.08s)
INFO:[a1b2c3d4] readiness: ollama-version → pass (0.04s) — Ollama 0.4.5
INFO:[a1b2c3d4] readiness: ollama-model-gpu-placement → pass (0.05s) — qwen2.5-vl:7b fully GPU-placed
INFO:[a1b2c3d4] readiness: ollama-context-length → pass (0.03s)
INFO:[a1b2c3d4] readiness passed (2.55s)
INFO:[a1b2c3d4] eager-delete: 4 artifacts removed from /workspace/tests/stage1_vendor_identity/inv_001_easy/
INFO:[a1b2c3d4] phase: preprocess (header-first-v1) → 4.21s
INFO:[a1b2c3d4] phase: extraction → 18.05s
INFO:[a1b2c3d4] phase: routing → 0.04s
INFO:[a1b2c3d4] phase: final_payload → 0.08s
INFO:[a1b2c3d4] post-run: ollama still GPU-placed; paddle still rocm_gpu
INFO:[a1b2c3d4] runtime: success / quality: pass
{"kind":"demo_run_report",…}
$ echo $?
0
```

### Readiness fail (old Ollama):

```sh
$ python -m dartwing_ocr.gpu_demo --check-only
INFO:[…] readiness: interpreter/venv → pass (0.01s)
INFO:[…] readiness: paddle-rocm-preflight → pass (2.34s)
INFO:[…] readiness: ollama-reachability → pass (0.08s)
ERROR:[…] readiness check 'ollama-version' failed — observed 0.3.12, expected >= 0.4.0. Remediation: upgrade Ollama to >= 0.4.0.
{"kind":"demo_run_report","schema_version":"0.1.0",…,"failing_check_name":"ollama-version",…}
$ echo $?
1
```

### Invalid input (missing source.pdf):

```sh
$ python -m dartwing_ocr.gpu_demo --document-folder /tmp/no-such-folder
ERROR:[…] invalid input: source.pdf not found in /tmp/no-such-folder
{"kind":"demo_run_report","schema_version":"0.1.0",…,"failure_kind":"invalid-input",…}
$ echo $?
2
```
