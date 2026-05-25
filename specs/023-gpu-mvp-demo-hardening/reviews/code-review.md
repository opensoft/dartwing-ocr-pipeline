# Code-correctness review — feature 023

**Date:** 2026-05-25
**Reviewer:** code-reviewer-023 agent (general-purpose, swarm review)
**Branch:** 023-gpu-mvp-demo-hardening @ 1d56554
**Scope:** src/dartwing_ocr/gpu_demo/ + readiness/

## Summary
12 findings: 2 CRITICAL, 2 HIGH, 5 MEDIUM, 3 LOW.

Status: NEEDS-ATTENTION (workstation smoke run will hit C1/C2 immediately; tests pass only because the `bypass_schema_validation` fixture masks C1)

## Findings (high-signal only)

| ID | Severity | Location | Summary | Recommendation |
|----|----------|----------|---------|----------------|
| C1 | CRITICAL | readiness/schema_validation.py:38 | `artifact_validator.validate_path(path)` calls a non-existent attribute; will AttributeError on every workstation run | Use `dartwing_ocr.validator.validate_folder(folder)` or call `validate_artifact(path, contract=<name>)` with the correct per-artifact contract name |
| C2 | CRITICAL | orchestrator.py:615-622 | Post-pipeline schema-validation rewrites `runtime_outcome` unconditionally; on a phase failure (e.g. `failed_at_preprocess`) the missing artifact triggers the rewrite to `failed_at_final_payload` + exit 5, masking the real failure | Only rewrite when `runtime_outcome` is currently `"success"` (or None); short-circuit if a phase failure is already recorded |
| H1 | HIGH | orchestrator.py:699 + 135 | `getattr(options, "_preprocess_run_summary", None)` on a `frozen=True` dataclass — always None; composer cannot set it (FrozenInstanceError) | Add a mutable hand-off path (e.g. composer returns a result object the orchestrator reads, or use a non-frozen container alongside `options`) |
| H2 | HIGH | orchestrator.py:586-590 + 555-567 | Signal-handler race: SIGALRM can fire after `_run_phase` returns but before `signal.alarm(0)` runs in `finally`, raising `TimeoutError` past the outer `except TimeoutError`; same risk if signal fires inside the `except` block | Wrap the `finally` body in a try/except that swallows a late-arriving `TimeoutError`; or call `signal.alarm(0)` as the very first statement of the outer try's exit path |
| M1 | MEDIUM | orchestrator.py:250-252 | When `canonicalize_document_folder` fails because path doesn't exist, the report emits `document_folder = null`; contract (demo-report-schema.md:71) requires the **attempted** path on invalid-input outcomes | Emit `str(options.document_folder)` (un-resolved) for invalid-input rows; only `--check-only` should null this field |
| M2 | MEDIUM | orchestrator.py:127-132 + 117-124 | `PipelineUnavailable("extract", …)` / `"route"` / `"assemble"` violate the `StalledPhase` Literal (closed enum: `preprocess`, `extraction`, `routing`, `final_payload`); the wrong values are stored on `exc.phase` | Use the canonical phase names; align the default-composer raise sites with `StalledPhase` |
| M3 | MEDIUM | cpu_fallback.py:31-70 + orchestrator.py:642-645 | `pre_run_snapshot` parameter is accepted but never compared in `_probe_ollama_post_run`, and the orchestrator never threads the readiness-phase /api/ps cache through, so `pre_run_ollama_snapshot` is always `None` in the emitted report | Either delete the dead parameter or wire `base_context.cached_api_ps_body` (extracting the matching entry) into the call |
| M4 | MEDIUM | report.py:83-84 + serialization.py:107 | `pre_run_ollama_snapshot` / `post_run_ollama_snapshot` are arbitrary `dict[str, Any]` serialized with `dataclasses.asdict`; the Q5 2 KiB cap applies only to `CheckDiagnostic.observed`, so an oversized /api/ps entry could blow the report past automation buffer limits | Apply the same byte-cap helper to these two snapshot fields, or pre-truncate to `{name, size, size_vram, context_length}` (as the example JSON in data-model.md:265 already implies) |
| M5 | MEDIUM | quality_derivation.py:31-40 | On any OS/JSON read error, `_read_final_payload_manual_review` defaults to `True` (review-required) — safe — but the orchestrator already enforces a successful pipeline before calling, so on success the file must exist; silent fallback to `True` here masks an inconsistent post-pipeline state where assembly was reported successful but the file is unreadable | Treat OSError/JSONDecodeError as an internal invariant violation (raise) or surface via a diagnostic; do not silently classify success runs as review_required |
| L1 | LOW | readiness/interpreter.py:30-33 | Substring `in` match against `.venv-paddle-rocm` / `.venv-paddle-dcu` accepts any interpreter whose realpath happens to contain that fragment (e.g. `/home/user/.venv-paddle-rocm-backup/bin/python`) | Tighten to a path-component match: `Path(interpreter).parts` must contain one of the canonical names |
| L2 | LOW | orchestrator.py:368-377 | The "ignored flags under --check-only" info line compares `str(options.document_folder)` against the literal default string; any normalization difference (trailing slash, absolute vs relative) yields a misleading info message | Compare `Path(options.document_folder) != Path(DEFAULT_DOCUMENT_FOLDER)` for path equality |
| L3 | LOW | Style/clarity cluster | (a) orchestrator.py:641 `if runtime_outcome is not None` is dead — runtime_outcome is forced to `"success"` at 624-625; (b) orchestrator.py:603-605 `dataclasses.replace(base_context,)` is a no-op clone (legitimately used to break frozen state, but should carry a comment); (c) voter_config_loader.py:73 `(ModuleNotFoundError, FileNotFoundError, AttributeError)` excludes `NotADirectoryError` / `TypeError` that `importlib.resources` can raise on zip-imported packages | Combine into one cleanup pass |

## Detailed findings

### C1 — `validate_path` does not exist on the validator module
**Severity:** CRITICAL
**Location:** `src/dartwing_ocr/gpu_demo/readiness/schema_validation.py:38`
**Issue:** The schema-validation check calls `artifact_validator.validate_path(path)`, but the `dartwing_ocr.validator.artifact` module exposes `validate_artifact(path, contract, *, version=None, contract_set=None)` — there is no `validate_path` function. Any real workstation run will raise `AttributeError`, get caught by the generic `except Exception` at line 41, and be reported as `"AttributeError: module 'dartwing_ocr.validator.artifact' has no attribute 'validate_path'"`. The integration tests do not hit this because `tests/integration/gpu_demo/conftest.py:277-291` monkeypatches `_validate_artifact` via the `bypass_schema_validation` fixture.
**Why it's a bug:** Every workstation success path will be falsely reported as `artifact-schema-validation` fail. Combined with C2 (below) this also rewrites `runtime_outcome` from `success` to `failed_at_final_payload` and produces exit code 5 — so the first real workstation smoke run will appear to "schema-fail" despite a clean pipeline.
**Suggested fix:** Replace with `from dartwing_ocr import validator` then call `validator.validate_folder(context.document_folder)`. That single call already iterates the four canonical artifacts with their per-artifact contracts. Aggregate the returned `Violation` list into the diagnostic. (Or, if a per-artifact loop is preferred, map basename → ArtifactName and call `validate_artifact(path, contract=name)` per file.)

### C2 — Schema-validation rewrite masks earlier phase failures
**Severity:** CRITICAL
**Location:** `src/dartwing_ocr/gpu_demo/orchestrator.py:615-622`
**Issue:** After the pipeline phases run, `run_post_pipeline` executes regardless of whether any pipeline phase failed (runner.py:102 only skips post-pipeline when pre-pipeline failed OR under `--check-only`). The schema-validation check then fails (correctly — the artifacts are missing on a phase failure), and the orchestrator unconditionally rewrites:
```
runtime_outcome = "failed_at_final_payload"
failure_kind = "artifact-schema-validation-failed"
```
This overwrites the original `failed_at_preprocess` / `failed_at_extraction` / `failed_at_routing` outcome.
**Why it's a bug:** The exit code maps to 5 (schema-validation-failed) instead of the correct 4 (pipeline-runtime-error). Worse, `runtime_outcome` lies about which phase died — operators reading the report see "failed_at_final_payload" when preprocess crashed. The cli-contract.md exit-code table (line 79-84) explicitly distinguishes the two cases.
**Suggested fix:** Gate the rewrite on a previously-clean run:
```python
if runtime_outcome is None:  # pipeline ran to completion without phase failure
    for r in post_results:
        if r.name == "artifact-schema-validation" and r.status == "fail":
            runtime_outcome = "failed_at_final_payload"
            failure_kind = "artifact-schema-validation-failed"
            ...
```
Alternatively, short-circuit the post-pipeline schema check itself when a phase already failed (skip-on-upstream-fail symmetry).

### H1 — `_preprocess_run_summary` cannot be set on frozen `OrchestratorOptions`
**Severity:** HIGH
**Location:** `src/dartwing_ocr/gpu_demo/orchestrator.py:699` and `:135`
**Issue:** Line 699: `run_summary = getattr(options, "_preprocess_run_summary", None)`. But `OrchestratorOptions` is declared `@dataclass(frozen=True)` (line 135), so any attempt by a composer to do `options._preprocess_run_summary = run_summary` raises `FrozenInstanceError`. The orchestrator also never receives the composer's return values (lambdas at lines 575-578 discard them), so even an out-of-band channel isn't there.
**Why it's a bug:** When the workstation composer is finally wired (issue #53), the `quality_status` derivation will always fall back to `"insufficient"` (quality_derivation.py:64) because the `evidence_gate_documents` lookup gets `None`. Every success run will report `quality_status: "review_required"`. SC-004's gate-derived quality reporting is silently broken.
**Suggested fix:** Either (a) make `_run_phase` capture the return value (e.g. `result = fn()`), pass it back to the caller via a mutable dict, and let the composer return a `PreprocessResult` that includes `run_summary`; or (b) make `OrchestratorOptions` non-frozen for the run_summary slot (less clean); or (c) add a `RunState` mutable container distinct from `OrchestratorOptions`.

### H2 — SIGALRM race against `signal.alarm(0)` and `finally`
**Severity:** HIGH
**Location:** `src/dartwing_ocr/gpu_demo/orchestrator.py:555-590`
**Issue:** Three race windows around the signal handler:
1. If SIGALRM fires INSIDE the `except TimeoutError as exc:` block (lines 579-585) — e.g. while logging — the handler raises a second `TimeoutError` that nothing catches; it propagates out of `run()`.
2. If SIGALRM fires INSIDE the `finally` block (lines 586-590) — between Python re-entry and `signal.alarm(0)` — same outcome.
3. The Python signal-handling rule: signal handlers only run between bytecode instructions. If the pipeline is deep in C code (httpx, Paddle) when 600s elapses, the TimeoutError fires only when control returns to Python. That can be many seconds late; `total_runtime_seconds` may exceed `bounded_timeout_seconds` significantly. Invariant 2 (`total_runtime_seconds ≥ bounded_timeout_seconds`) still holds, but the SLA is soft.
**Why it's a bug:** Window (1)/(2) cause an unhandled crash with no DemoRunReport on stdout — violating FR-019 (always emit). Probability is low but the timer is 600s long and the windows are wide enough to be reached eventually in CI/long-running smoke runs.
**Suggested fix:**
```python
finally:
    if hasattr(signal, "SIGALRM"):
        try:
            signal.alarm(0)
            if previous_handler is not None:
                signal.signal(signal.SIGALRM, previous_handler)
        except TimeoutError:
            pass  # late-arriving alarm; cleanup wins
```
Also wrap the `except TimeoutError` body identically. Long-term, consider a thread-based timeout (`threading.Timer` + a sentinel flag the composer checks) for portability and tighter race control.

### M1 — `document_folder` null'd on invalid-input when the path doesn't exist
**Severity:** MEDIUM
**Location:** `src/dartwing_ocr/gpu_demo/orchestrator.py:250-252`
**Issue:** `document_folder = str(options.document_folder.resolve()) if not options.check_only and options.document_folder.exists() else None`. When `canonicalize_document_folder` fails because the path is missing (line 317-318 raises `EagerDeleteError`), `_build_report` is called with that same path; `.exists()` returns False; the field becomes `null`. Contract (demo-report-schema.md:71) explicitly requires the *attempted* path on invalid-input outcomes so operators can triage the wrong path.
**Why it's a bug:** Operator sees `document_folder: null` and cannot tell which path was attempted. The outcome matrix at demo-report-schema.md:230 lists "str-or-null" for invalid-input but the body text at line 71 is the normative requirement.
**Suggested fix:** Split the condition:
```python
if options.check_only:
    folder = None
else:
    try:
        folder = str(options.document_folder.resolve())
    except (OSError, ValueError):
        folder = str(options.document_folder)
```

### M2 — `PipelineUnavailable` raised with non-Literal phase names
**Severity:** MEDIUM
**Location:** `src/dartwing_ocr/gpu_demo/orchestrator.py:117-124`
**Issue:** `_DefaultPipelineComposer.extract/route/assemble` raise `PipelineUnavailable("extract", …)`, `"route"`, `"assemble"` — but `PipelineUnavailable.__init__` is typed `phase: StalledPhase`, and `StalledPhase = Literal["preprocess", "extraction", "routing", "final_payload"]` (enums.py:23). The strings `"extract"` / `"route"` / `"assemble"` are NOT members of that closed set.
**Why it's a bug:** The `exc.phase` attribute holds a value outside its declared Literal type — a type-system violation. In practice the orchestrator's `_run_phase` handler at lines 526-531 uses the *outer* `phase` parameter (not `exc.phase`), so the wrong value is dead — but the API surface lies about its contract. If a future caller starts reading `exc.phase`, it will produce a closed-enum drift.
**Suggested fix:** Use `"preprocess"` / `"extraction"` / `"routing"` / `"final_payload"` at the raise sites. Annotate `PipelineUnavailable.phase` as `StalledPhase` and verify mypy/pyright is run.

### M3 — `pre_run_snapshot` parameter is dead in `_probe_ollama_post_run`
**Severity:** MEDIUM
**Location:** `src/dartwing_ocr/gpu_demo/cpu_fallback.py:31-70`, `orchestrator.py:642-645`
**Issue:** The `_probe_ollama_post_run(ollama_base_url, model_name, pre_run_snapshot)` parameter is declared but never read; the comparison is purely `size_vram == size` on the post-run fetch, with no diff against the pre-run snapshot. The orchestrator (line 642-645) doesn't pass `pre_run_snapshot` at all — `interrogate()` defaults to `None`, so `pre_run_ollama_snapshot` in the emitted report is always `None`.
**Why it's a bug:** R-023.15's "post-run interrogation" decision implies a diff against the readiness-time snapshot (the cached `/api/ps` from check 3) — otherwise we can't detect the case where Ollama silently dropped + reloaded the model on CPU between checks. The example JSON at data-model.md:265 also shows both snapshots populated.
**Suggested fix:** In `run()`, extract the matching entry from `base_context.cached_api_ps_body` and pass it as `pre_run_snapshot=`. Inside `_probe_ollama_post_run`, compare `pre_run_snapshot["size_vram"] == post_run["size_vram"]` and only mark `consistent` if both pre and post agree.

### M4 — Snapshot dicts bypass the Q5 2 KiB observed-cap
**Severity:** MEDIUM
**Location:** `src/dartwing_ocr/gpu_demo/report.py:83-84`, `serialization.py:107`
**Issue:** `CPUFallbackDetection.pre_run_ollama_snapshot` / `post_run_ollama_snapshot` are `Optional[dict[str, Any]]`. `serialization.py:107` serializes them via `dataclasses.asdict(report.cpu_fallback_detection)`. The 2 KiB cap (Q5) is applied only inside `_truncate_observed_value` on `CheckDiagnostic.observed`. If a future Ollama version adds large nested fields (e.g. detailed runner stats), the snapshot can balloon and blow the single-line JSON discipline (FR-019).
**Why it's a bug:** Automation that buffers the line (e.g. with a single-line readline) could fail; downstream log aggregators may truncate the JSON mid-line and corrupt the report.
**Suggested fix:** Either (a) reduce snapshot to the four documented fields (`name`, `size`, `size_vram`, `context_length`) at capture time in `_probe_ollama_post_run` and inside the planned wiring of `pre_run_snapshot`, or (b) apply `_truncate_observed_value` to each snapshot dict at serialization time.

### M5 — Silent fallback to `manual_review_required=True` on read error
**Severity:** MEDIUM
**Location:** `src/dartwing_ocr/gpu_demo/quality_derivation.py:31-40`
**Issue:** `_read_final_payload_manual_review` returns `True` on missing file, OSError, JSONDecodeError, or non-dict body. The orchestrator only calls into this on the success path (line 675 `if runtime_outcome == "success"`). On the success path the file MUST exist (assembler ran successfully), and it MUST be a dict (assembler invariants). A failure to read here means the post-pipeline state is internally inconsistent.
**Why it's a bug:** A corrupted-on-disk final payload on a "successful" run is silently demoted to `review_required` instead of escalated. Operator never sees the inconsistency. Combined with the lack of the run_summary wiring (H1), the success path is doubly silenced.
**Suggested fix:** Raise an internal exception (e.g. a dedicated `QualityDerivationError`) when the file is unreadable on the success path; let the orchestrator map it to `failed_at_final_payload` + `pipeline-runtime-error` (exit 4) with a clear diagnostic. Keep the conservative default only for the explicitly-defensive `present but non-bool` branch.

### L1 — Interpreter venv check uses substring matching
**Severity:** LOW
**Location:** `src/dartwing_ocr/gpu_demo/readiness/interpreter.py:30-33`
**Issue:** `ok = any(name in interpreter for name in _EXPECTED_VENV_NAMES)` matches any path whose realpath contains `.venv-paddle-rocm` or `.venv-paddle-dcu` as a substring. False positives include `/home/user/.venv-paddle-rocm-backup/bin/python` or `/opt/.venv-paddle-rocm.old/bin/python`.
**Why it's a bug:** A subtle misconfiguration (operator copy-and-renamed venv) silently passes the readiness gate.
**Suggested fix:** Use `Path(interpreter).parts` and match exact parent-directory names.

### L2 — Default-folder equality check uses raw-string compare
**Severity:** LOW
**Location:** `src/dartwing_ocr/gpu_demo/orchestrator.py:368-377`
**Issue:** `str(options.document_folder) != "tests/stage1_vendor_identity/inv_001_easy"` triggers the "ignoring under --check-only" info line whenever the path representation differs from the literal default — e.g. `Path("./tests/stage1_vendor_identity/inv_001_easy")` or `Path("/abs/tests/stage1_vendor_identity/inv_001_easy")`. Cosmetic but misleading.
**Suggested fix:** Compare with `Path(DEFAULT_DOCUMENT_FOLDER)` and use `Path.__eq__` (component-wise) or resolve both sides first.

### L3 — Style/clarity cluster
**Severity:** LOW
**Locations:**
- `orchestrator.py:641` — `if runtime_outcome is not None` is dead; line 624-625 forces it to `"success"`.
- `orchestrator.py:603-605` — `dataclasses.replace(base_context,)` clones nothing; this is intentional (to bypass frozen state via `object.__setattr__`) but undocumented — add a comment.
- `voter_config_loader.py:73` — exception list `(ModuleNotFoundError, FileNotFoundError, AttributeError)` misses `NotADirectoryError` and `TypeError` that `importlib.resources` may raise on zip-imported packages.
- `evaluator_subprocess.py:73` — `(completed.stderr or "")[-256:]` is byte-naive if stderr has non-ASCII codepoints near the 256-char boundary (negligible in practice — text mode decodes to str).
**Suggested fix:** Single cleanup pass — none individually critical.

## What was reviewed
- `src/dartwing_ocr/gpu_demo/orchestrator.py` (lifecycle, exception flow, signal handling)
- `src/dartwing_ocr/gpu_demo/readiness/` (all 8 checks + runner + base)
- `src/dartwing_ocr/gpu_demo/cpu_fallback.py`
- `src/dartwing_ocr/gpu_demo/evaluator_subprocess.py`
- `src/dartwing_ocr/gpu_demo/quality_derivation.py` + `quality_status.py`
- `src/dartwing_ocr/gpu_demo/voter_config_loader.py`
- `src/dartwing_ocr/gpu_demo/folder_canonicalize.py`
- `src/dartwing_ocr/gpu_demo/serialization.py`
- `src/dartwing_ocr/gpu_demo/report.py` + `enums.py` + `exit_codes.py`
- `src/dartwing_ocr/gpu_demo/cli.py` + `__main__.py`
- `src/dartwing_ocr/gpu_demo/log.py` + `run_id.py` + `version.py` + `diagnostics.py`
- Cross-referenced against `data-model.md` §1 cross-field invariants, `contracts/demo-report-schema.md` outcome matrix, `contracts/cli-contract.md` exit-code mapping, and `src/dartwing_ocr/validator/` public API

## What was deliberately NOT reviewed
- The intentionally-stubbed `_DefaultPipelineComposer` body (tracked as issue #53)
- Test files themselves (out of scope — separate agent reviews tests)
- Spec/plan/contracts internal consistency (already analyzed via /speckit.analyze five times)
- The latent orchestrator `TimeoutError` ordering bug that was resolved in commit 1d56554
