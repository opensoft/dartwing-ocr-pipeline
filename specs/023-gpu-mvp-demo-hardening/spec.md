# Feature Specification: GPU MVP Demo Hardening

**Feature Branch**: `023-gpu-mvp-demo-hardening`
**Created**: 2026-05-24
**Status**: Draft
**Input**: User description: "Feature 023: GPU MVP demo hardening — make the workstation full-workstation GPU lane (WSL2 AMD ROCm, host Ollama, Paddle ROCm `.venv-paddle-rocm`) deterministic and repeatable. Define and implement a canonical one-document GPU MVP smoke/demo path that proves the local GPU runtime is ready, the pipeline writes the four canonical stage 1 artifacts, and failures are reported early with actionable diagnostics instead of hanging or silently falling back to CPU. Scope is runtime/demo reliability, readiness checks, and operator-facing flow only — not evaluator scoring (feature 022) and not Jetson edge-fast (separate active OpenSpec change)."

## Clarifications

### Session 2026-05-24

- Q: What is the canonical demo command's surface? -> A: New top-level Python CLI: `python -m dartwing_ocr.gpu_demo`, optionally exposed as `dartwing-gpu-demo`.
- Q: What is the readiness-preflight surface? -> A: `--check-only` flag on the same demo CLI.
- Q: What is the exit-code taxonomy? -> A: `0` success, `1` readiness failed, `2` invalid input/usage, `3` runtime timeout, `4` runtime failed after readiness, `5` artifact schema validation failed.
- Q: How is `DemoRunReport` emitted and persisted? -> A: Single stdout JSON line with `kind: "demo_run_report"`; no new persisted artifact.
- Q: What is the `quality_status` enum? -> A: `pass` / `weak` / `review_required`.
- Q: What is the `runtime_outcome` enum? -> A: `success` / `failed_at_preprocess` / `failed_at_extraction` / `failed_at_routing` / `failed_at_final_payload` / `timeout`.
- Q: How does the command handle stale artifacts? -> A: Deterministically overwrite the four canonical artifacts on every run.
- Q: What preprocessing preset is canonical? -> A: `header-first-v1` is default; full OCR is opt-in through `--preset full-ocr`.
- Q: How is silent CPU fallback detected? -> A: Readiness checks plus post-run device interrogation of Ollama and Paddle.
- Q: What is stable enough for three consecutive runs? -> A: All artifacts schema-valid, with stable `runtime_outcome` and `quality_status`; byte identity is not required for model-influenced artifacts.
- Q: What is the readiness preflight upper bound? -> A: 10 seconds.
- Q: Should `OLLAMA_CONTEXT_LENGTH` be checked? -> A: Check it in preflight when `/api/ps` exposes it, and still catch downstream context-window errors at runtime.
- Q: What if `/api/ps` omits `size_vram`? -> A: Document a minimum supported Ollama version and fail with named `ollama-version` check when the version is too old or `size_vram` is absent.
- Q: When does the feature 022 evaluator run? -> A: Only when `--with-evaluator` is passed; default off.
- Q: Where does the canonical runbook live? -> A: Extend `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md` in place.
- Q: What smoke-test coverage is required? -> A: CPU-isolated pytest coverage with stubbed dependencies plus a workstation-only manual GPU smoke gate in the runbook.
- Q: What is the default bounded pipeline-runtime timeout? -> A: 600 seconds.
- Q: How is readiness summary represented in `DemoRunReport`? -> A: All named checks are emitted with `pass` / `fail` / `skipped`; the failing check name is surfaced separately on failure.
- Q: How is a timeout's stalled phase captured? -> A: Keep `runtime_outcome: "timeout"` and add separate `stalled_phase` enum `preprocess` / `extraction` / `routing` / `final_payload`.
- Q: Does `DemoRunReport` carry version fields? -> A: Include both `schema_version` starting at `"0.1.0"` and `pipeline_version`.
- Q: Does `DemoRunReport` include phase timings? -> A: Include `phase_timings` for `preprocess`, `extraction`, `routing`, `final_payload`, plus `total_runtime_seconds`.
- Q: How is the per-document folder selected? -> A: Default to `tests/stage1_vendor_identity/inv_001_easy/`; allow `--document-folder <path>` override.
- Q: What if `--with-evaluator` is passed without `semantic_table_truth.json`? -> A: Warn and skip evaluator, then derive `quality_status` from default sources.
- Q: How does the CLI use stdout vs stderr? -> A: stdout contains exactly one `DemoRunReport` JSON line and nothing else; stderr carries progress, warnings, and errors.
- Q: Does the CLI accept a voter-config override? -> A: Accept `--voter-config <path>` and otherwise use existing discovery.
- Q: How is missing `source.pdf` treated? -> A: Invalid input/usage, exit code 2.
- Q: When does deterministic overwrite happen? -> A: Eagerly delete the four canonical artifacts at run start; preserve partial new artifacts on timeout/failure.
- Q: Which files are in overwrite scope? -> A: Only the four canonical stage 1 artifacts.
- Q: Does every outcome emit a `DemoRunReport`? -> A: Yes; every run emits exactly one stdout JSON line, unknown fields are `null`, and schema shape is stable.
- Q: How does `--check-only` populate non-applicable report fields? -> A: Readiness fields are populated; runtime, quality, timing, and artifact fields are `null`.
- Q: How are phase timings shaped on non-success runs? -> A: Always include all four phase keys; phases not reached are `null`; `total_runtime_seconds` is present for pipeline runs.
- Q: What if no voter config is supplied or discoverable? -> A: Invalid input/usage, exit code 2.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Canonical one-command GPU MVP demo (Priority: P1)

As a demo operator on the configured WSL2 AMD ROCm workstation, I can start the GPU services using the documented Ollama startup script and the Paddle ROCm virtualenv, then run **one** documented command against a known invoice fixture and reliably produce all four canonical stage 1 artifacts (`preprocess_output.json`, `edge_extraction_output.json`, `routing_decision.json`, `final_structured_payload.json`), each schema-validated, within the 600-second bounded timeout.

**Why this priority**: This is the MVP slice. Without a single trustworthy demo command, every other story is academic — there is no shared reference point for "the GPU lane works" or "the GPU lane regressed."

**Independent Test**: With host Ollama running via `scripts/start-host-ollama-rocm-wsl.sh`, the configured extraction model loaded on GPU, and the Paddle ROCm preflight passing, run the documented command against the canonical demo invoice. Confirm the command exits zero within 600 seconds and that the four canonical artifacts exist in the document's per-doc folder and pass the existing folder/artifact validator.

**Acceptance Scenarios**:

1. **Given** host Ollama is running with the configured extraction model fully GPU-placed and the Paddle ROCm preflight passes, **When** the operator runs the documented canonical demo command against the canonical demo invoice, **Then** the command exits zero within 600 seconds and the four canonical stage 1 artifacts exist in the per-document folder and pass schema validation.
2. **Given** the same successful run, **When** the operator inspects the command's final report, **Then** the report identifies the interpreter path used, the Paddle device backend confirmed by the preflight, the Ollama model verified GPU-placed, the bounded timeout used, the artifact paths written, the phase timings, and a clear "runtime: success / quality: <status>" outcome.

---

### User Story 2 - Fail-fast GPU readiness preflight (Priority: P2)

As a developer or maintainer, I can run the GPU readiness preflight independently from a full pipeline run with `--check-only` on the canonical demo CLI and have it terminate within 10 seconds with a clear nonzero exit when any of the following are wrong: Python interpreter is not the Paddle ROCm virtualenv, the Paddle ROCm preflight does not confirm GPU-backed execution, host Ollama is not reachable, the extraction model identified by the active voter config is not loaded, or the loaded model is not fully GPU-placed.

**Why this priority**: Without a cheap preflight, every failure costs the full pipeline runtime cost. Operators and developers need a fast, idempotent "is the box ready?" check that proves correctness of the demo prerequisites without writing any pipeline artifacts.

**Independent Test**: With the demo prerequisites intentionally broken one at a time (wrong venv, Ollama down, model unloaded, model present but partially CPU-placed, voter config referencing a missing model), invoke the readiness preflight in isolation with `--check-only`. Confirm each broken state produces a nonzero exit within 10 seconds, identifies the failing check by name, and writes **no** pipeline artifacts.

**Acceptance Scenarios**:

1. **Given** the operator runs the canonical demo command from the wrong Python environment (interpreter not from `.venv-paddle-rocm`), **When** the readiness phase executes, **Then** the command exits nonzero before any pipeline artifact write, the failure output includes the interpreter path that was used, and the failing check is identified as the interpreter/venv check.
2. **Given** host Ollama is down or unreachable, **When** the readiness phase executes, **Then** the command exits nonzero before any pipeline artifact write and the failing check is identified as the Ollama-reachability check.
3. **Given** host Ollama is reachable but the extraction model from the active voter config does not appear in `/api/ps`, or appears with `size_vram == 0`, or appears with `size_vram < size` (i.e., partial CPU placement), **When** the readiness phase executes, **Then** the command exits nonzero before any pipeline artifact write and the failing check is identified as the Ollama-model-GPU-placement check.
4. **Given** the operator invokes `--check-only`, **When** the readiness phase completes or fails, **Then** stdout contains exactly one `DemoRunReport` JSON line with readiness fields populated and runtime, quality, timing, and artifact fields set to `null`.

---

### User Story 3 - Specific readiness diagnostics (Priority: P2)

As an operator troubleshooting a demo machine, when readiness fails I can see **which specific check failed** — interpreter/venv, Paddle ROCm preflight, Ollama reachability, Ollama model GPU placement, Ollama context length, Ollama version, artifact schema validation, or pipeline runtime timeout — together with enough context (interpreter path, voter config path, expected model name, Ollama version, `/api/ps` excerpt) to act without rerunning the command in a debugger.

**Why this priority**: Generic "GPU demo failed" output forces re-runs and tribal knowledge. A small set of named checks with structured diagnostics keeps the demo path operator-friendly and makes regression triage trivial.

**Independent Test**: Force each named failure class deterministically (wrong venv, Paddle preflight failure, Ollama down, model on CPU, intentionally corrupted artifact, oversized input to provoke timeout). Confirm each produces a distinct named failure with sufficient diagnostic context.

**Acceptance Scenarios**:

1. **Given** any readiness check fails, **When** the operator reads the command output, **Then** exactly one named failing check is reported with a short, actionable diagnostic (what was checked, what was observed, what was expected).
2. **Given** the readiness phase passes but the pipeline runtime exceeds the documented bounded timeout, **When** the timeout triggers, **Then** the command exits nonzero with a timeout diagnostic that identifies the stalled phase (preprocessing, extraction, routing, or final-payload assembly) and leaves any partially written artifacts in place for inspection.

---

### User Story 4 - Runtime success separated from extraction quality (Priority: P3)

As a maintainer, I can tell from a single demo report whether the **runtime** completed (all four canonical artifacts written and schema-valid) versus whether **extraction quality** was good enough on this run, so that a successful pipeline run with weak fields is not confused with a runtime failure (and vice versa).

**Why this priority**: This separation is needed before the demo can serve as a stable MVP integration-test checkpoint. Without it, regressions in extraction quality are mistaken for runtime regressions and runtime hangs are mistaken for quality issues, which blocks promotion to the Jetson edge-fast phase.

**Independent Test**: Use a known invoice where the GPU lane reliably writes valid artifacts but produces null/low-confidence vendor fields. Confirm the demo report shows runtime=success and a distinct quality-status field from the closed enum `pass` / `weak` / `review_required` without conflating the two outcomes.

**Acceptance Scenarios**:

1. **Given** the runtime completes within the bounded timeout and all four artifacts are schema-valid, **When** the report is generated, **Then** the report records runtime as success regardless of extraction quality.
2. **Given** the runtime completes but extraction returns null or weak vendor fields (e.g., `manual_review_required: true` in `final_structured_payload.json`), **When** the report is generated, **Then** the report records runtime as success **and** records a distinct quality-status value that surfaces the weak-extraction outcome without overriding runtime success.

---

### Edge Cases

- Operator runs from a Python interpreter that **is** the Paddle ROCm venv but with a stale or uninstalled Paddle ROCm wheel — readiness MUST fail at the Paddle preflight stage, not silently degrade to CPU.
- Host Ollama is reachable but the configured voter config references a model name that is not in `/api/ps` at all (model was never loaded, or was unloaded by another process) — readiness MUST fail at the Ollama-model-GPU-placement check with the missing model name in the diagnostic.
- Host Ollama was started without `OLLAMA_CONTEXT_LENGTH=2048` (or the documented value) — readiness MUST fail under the Ollama context-length check when `/api/ps` exposes the value; if the value is not exposed and the extraction request later fails with a context-window error, the demo report MUST surface this as a runtime failure with a diagnostic that points at the Ollama startup script, not as a generic extraction failure.
- Host Ollama is old enough that `/api/ps` omits `size_vram` for the configured model — readiness MUST fail under the named Ollama-version check and point the operator to the minimum supported version in the runbook.
- The target per-document folder is missing `source.pdf` — the demo command MUST treat this as invalid input/usage and exit 2 before readiness checks or pipeline execution.
- Neither `--voter-config <path>` is supplied nor the existing auto-discovery path locates a valid voter config — the demo command MUST treat this as invalid input/usage and exit 2 before readiness checks or pipeline execution.
- The resolved voter-config file exists but is unreadable, malformed YAML, or missing the model-name field this feature reads — the demo command MUST treat this as invalid input/usage and exit 2, with a diagnostic identifying which validation step failed (file open, YAML parse, schema field).
- The eager-delete of one of the four canonical artifacts at run start fails (permission error, I/O error, or a canonical filename resolves outside the per-document folder via symlink) — the demo command MUST abort with exit 2 (invalid input/usage) before any pipeline phase runs, with a diagnostic naming the artifact path that failed. No partial-delete proceeds.
- `--check-only` is invoked but a per-document-folder-specific prerequisite (e.g., missing `source.pdf`) is broken — `--check-only` MUST still report infrastructure readiness as passing if checks 1–6 pass, and MUST NOT imply the per-document folder is valid; operators MUST still verify the per-document folder before the subsequent full run.
- The Paddle ROCm preflight passes but the actual pipeline OCR call hangs past the bounded timeout — the demo command MUST exit nonzero on timeout, leave the partially written artifacts in place, and identify the stalled phase.
- The `header-first-v1` preprocessing path writes a schema-valid `preprocess_output.json` with reduced page coverage — the runbook MUST flag this as the currently supported MVP GPU path and MUST NOT imply the slower full/default OCR path is the canonical demo until that path is verified.
- An earlier failed run left stale artifacts in the per-document folder — the demo path MUST overwrite the four canonical artifacts deterministically so the operator does not have to clean up by hand to trust the outcome.
- Multiple Ollama instances are running (e.g., host Ollama plus a container-side Ollama) — readiness MUST check the host Ollama instance identified by the active configuration, not whichever instance happens to answer first.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The feature MUST define exactly one canonical workstation GPU MVP demo command path in the runbook, and that command MUST be the single supported entry point operators are told to use for the MVP demo: `python -m dartwing_ocr.gpu_demo` (optionally exposed as `dartwing-gpu-demo`).
- **FR-002**: The demo path MUST require execution from the Paddle ROCm virtualenv (`.venv-paddle-rocm` or its established successor) **and** MUST run the existing Paddle ROCm preflight to prove GPU-backed Paddle execution **before** writing any pipeline artifacts.
- **FR-003**: The readiness output MUST print the Python interpreter path actually used for the run.
- **FR-004**: The demo path MUST verify host Ollama readiness as a check independent from Paddle readiness, so that a failure in either is attributable to exactly one cause.
- **FR-005**: The Ollama readiness check MUST identify the extraction model from the **active voter config** (not a hard-coded model name) and MUST verify that the matching `/api/ps` entry exists, has `size_vram > 0`, and has `size_vram == size` (i.e., the model is **fully** GPU-placed, not partially offloaded to CPU). The CLI MUST accept `--voter-config <path>` as an explicit override and otherwise use the existing feature 005 / 021 voter-config discovery path. If neither path yields a *valid* voter config — meaning the file does not exist, cannot be opened, is not parseable YAML, or omits the model-name field this feature reads — the command MUST exit 2 as invalid input/usage before readiness checks or pipeline execution.
- **FR-006**: The runbook MUST instruct operators to start host Ollama exclusively via `scripts/start-host-ollama-rocm-wsl.sh` and MUST document the required `OLLAMA_CONTEXT_LENGTH=2048` behavior (or whatever value is recorded as required to avoid context-window failures on the supported extraction model). The readiness phase MUST identify the host Ollama instance via the `OLLAMA_BASE_URL` environment variable (default `http://localhost:11434`) — the value at this URL is the canonical host Ollama for the demo, even when other Ollama instances (e.g., a container-side Ollama) are running. The readiness phase MUST check the required context length when the active Ollama `/api/ps` response exposes it, and when `/api/ps` does NOT expose it, a downstream context-window error during extraction MUST be classified as `runtime_outcome: failed_at_extraction` with a diagnostic that names the startup script (not as a separate `runtime_outcome` value).
- **FR-007**: The demo path MUST fail fast — terminate with a clear nonzero exit before any pipeline artifact is written — if any of the following hold: Ollama is not reachable, the expected extraction model is not loaded, the expected extraction model is not fully GPU-placed.
- **FR-008**: The smoke/demo path MUST apply a 600-second default timeout to the pipeline runtime and MUST return exit code 3 on timeout with a diagnostic identifying the stalled phase, instead of hanging indefinitely.
- **FR-009**: On the successful path, the demo command MUST produce and schema-validate the four canonical stage 1 artifacts in the per-document folder: `preprocess_output.json`, `edge_extraction_output.json`, `routing_decision.json`, `final_structured_payload.json`.
- **FR-010**: The demo command MUST record whether the **pipeline runtime** completed (all four artifacts written and schema-valid) **separately** from whether **extraction quality** passed, so that a runtime-success / quality-weak outcome is distinguishable from a runtime-failure outcome. The extraction-quality field MUST use the closed enum `pass` / `weak` / `review_required`.
- **FR-011**: The demo path MUST use `header-first-v1` as the default preprocessing preset for this feature. Full/default OCR MAY remain selectable through `--preset full-ocr`, but it MUST NOT be implied to be the canonical demo path until that path is independently verified within this feature's bounded timeout.
- **FR-012**: The feature MUST NOT silently fall back to CPU when the GPU lane is requested. A CPU-mode result MUST NOT be reported as a successful GPU demo run, and the demo command MUST combine readiness checks with post-run device interrogation of host Ollama and the Paddle backend to detect fallback.
- **FR-013**: The feature MUST NOT add Jetson-specific behavior. Jetson edge-fast validation remains governed by the separate active OpenSpec change.
- **FR-014**: The feature MUST NOT change the stage 1 artifact schemas (no new contract set version) unless an existing schema-validation bug is discovered during implementation, in which case the bug fix MUST flow through the standard contract amendments process.
- **FR-015**: The feature MUST NOT expand scope into line-item extraction quality, model prompt tuning, or semantic evaluator scoring beyond what is needed to report the demo outcome's quality status as a single enumerated value.
- **FR-016**: Failure output for any readiness check MUST identify exactly one named failing check from a closed vocabulary (interpreter/venv, Paddle ROCm preflight, Ollama reachability, Ollama version, Ollama model GPU placement, Ollama context length, artifact schema validation, pipeline runtime timeout) together with a short, actionable diagnostic. Readiness checks MUST be executed in this fixed order: (1) interpreter/venv, (2) Paddle ROCm preflight, (3) Ollama reachability, (4) Ollama version, (5) Ollama model GPU placement, (6) Ollama context length, (7) artifact schema validation, (8) pipeline runtime timeout. When an earlier check fails, every later check MUST be reported with status `skipped` per FR-026; the failing check name MUST be the first failing check in this order. This ordering deterministically resolves the case where the same condition could be attributed to two checks (e.g., when `/api/ps` omits `size_vram`, the Ollama version check fails first and the GPU-placement check is `skipped`).
- **FR-017**: Re-running the demo command against the same per-document folder MUST deterministically overwrite only the four canonical artifacts on every run, without an interactive prompt and without requiring manual cleanup. The command MUST eagerly delete those four artifacts at run start by their exact basenames (`preprocess_output.json`, `edge_extraction_output.json`, `routing_decision.json`, `final_structured_payload.json`) within the resolved per-document folder — never via glob, never recursively, and never following symlinks out of that folder. The resolved per-document folder MUST be canonicalized (symlinks resolved) before the delete, and the four delete operations MUST target files that, after canonicalization, are still inside the same per-document folder; any of the four resolving to a path outside that folder MUST cause the command to exit 2 (invalid input/usage) before any delete. If a delete fails on any of the four (permission, I/O error), the command MUST abort with exit 2 before invoking any pipeline phase — no partial-delete proceeds. After successful eager delete, the command MUST preserve any newly written partial state if a later phase times out or fails.
- **FR-018**: The same canonical demo CLI MUST support a readiness-only mode through `--check-only`. This mode MUST perform readiness checks only and MUST write no pipeline artifacts. `--check-only` MUST exercise the infrastructure readiness vocabulary (checks 1–6 in FR-016: interpreter/venv, Paddle ROCm preflight, Ollama reachability, Ollama version, Ollama model GPU placement, Ollama context length) and MUST skip the document-folder-dependent checks (7 and 8). `--check-only` MUST NOT verify the presence of `source.pdf` in the per-document folder, MUST ignore `--document-folder`, `--preset`, and `--with-evaluator` (they have no effect under `--check-only`), and MUST NOT imply that a subsequent full run will succeed — a passing `--check-only` confirms infrastructure readiness only.
- **FR-019**: The demo command MUST emit exactly one machine-parseable `DemoRunReport` as a stdout JSON line with `kind: "demo_run_report"` on every run mode and outcome: success, readiness failure, runtime failure, timeout, and `--check-only`. The JSON line MUST be a single JSON object on a single line, UTF-8 encoded, terminated by exactly one `\n`, with no leading or trailing whitespace and no second line. The same top-level key set MUST be present on every outcome; unknown or non-applicable fields MUST be emitted with explicit `null` values, never omitted. The command MUST NOT persist a new report artifact in the per-document folder. stdout MUST contain only that JSON line; human-readable progress, warnings, and errors MUST go to stderr.
- **FR-020**: The demo command MUST use the closed `runtime_outcome` enum `success` / `failed_at_preprocess` / `failed_at_extraction` / `failed_at_routing` / `failed_at_final_payload` / `timeout` (the field itself is `null` only when no pipeline ran — i.e., readiness failure, invalid input/usage, or `--check-only`). The `stalled_phase` field MUST be present on every outcome (per FR-019 stable-shape rule) with closed enum `preprocess` / `extraction` / `routing` / `final_payload` when `runtime_outcome` is `timeout`, and `null` for every other outcome.
- **FR-021**: The demo command MUST use the closed exit-code table: `0` success, `1` readiness failed, `2` invalid input/usage, `3` pipeline runtime timeout, `4` pipeline runtime failed after readiness passed, `5` artifact schema validation failed.
- **FR-022**: The feature 022 semantic-quality evaluator MUST be off by default for the canonical demo command and MAY run only when the operator passes `--with-evaluator`. If `--with-evaluator` is passed but the target folder has no `semantic_table_truth.json`, the command MUST warn on stderr, skip evaluator execution, and derive `quality_status` from the default sources.
- **FR-023**: The runbook MUST document the minimum supported Ollama version required for machine-checkable GPU placement. If the probed version is below that minimum or the `/api/ps` model entry omits `size_vram`, readiness MUST fail under the named `ollama-version` check rather than assuming GPU placement.
- **FR-024**: The `DemoRunReport` MUST include `schema_version` starting at `"0.1.0"` and MUST include the pipeline build `pipeline_version`.
- **FR-025**: The `DemoRunReport` MUST always include a `phase_timings` object with all four keys present (`preprocess`, `extraction`, `routing`, `final_payload`) plus `total_runtime_seconds`. For pipeline runs, phases that ran MUST record wall-clock seconds (float) and phases not reached MUST be `null`. For `--check-only` and for readiness-failure / invalid-input outcomes, all four `phase_timings` keys MUST be `null` and `total_runtime_seconds` MUST be `null` — the keys themselves are always present, never omitted (consistent with FR-019 stable-shape rule).
- **FR-025a**: Under `--check-only`, the `DemoRunReport` MUST populate the readiness section fully (per FR-026), MUST set `runtime_outcome`, `quality_status`, `stalled_phase`, `total_runtime_seconds`, and `artifact_paths` to `null` (with the keys present, never omitted), MUST set every `phase_timings.<phase>` value to `null` (with all four keys present, per FR-025), and MUST use the same `kind: "demo_run_report"` and `schema_version` as full runs.
- **FR-026**: The readiness summary inside `DemoRunReport` MUST include all named readiness checks with status `pass` / `fail` / `skipped`; on failure, the failing check name MUST also be surfaced separately.
- **FR-027**: The demo command MUST default to `tests/stage1_vendor_identity/inv_001_easy/` as the canonical document folder and MUST accept `--document-folder <path>` to override it. If the selected folder lacks `source.pdf`, the command MUST exit 2 as invalid input/usage before readiness checks or pipeline execution.

### Key Entities *(include if feature involves data)*

- **ReadinessCheck**: One named check from a closed, enumerated vocabulary (interpreter/venv, Paddle ROCm preflight, Ollama reachability, Ollama model GPU placement, Ollama context length, Ollama version, artifact schema validation, pipeline runtime timeout) with a status (`pass` / `fail` / `skipped`) and, on failure, a short diagnostic plus structured context (e.g., interpreter path, voter config path, expected model name, Ollama version, `/api/ps` excerpt).
- **DemoRunReport**: The single composite outcome produced by the canonical demo command and emitted as a stdout JSON line with `kind: "demo_run_report"` (not persisted as a new artifact). It is emitted exactly once for every outcome, including readiness failures and `--check-only`, with stable keys and `null` for unknown or non-applicable values. Records `schema_version`, `pipeline_version`, the interpreter path, the active voter config path, the expected extraction model, the readiness summary (all named checks and their statuses), the failing check name when applicable, the bounded timeout value, the artifact paths written, `phase_timings`, `total_runtime_seconds`, the runtime outcome (`success` / `failed_at_preprocess` / `failed_at_extraction` / `failed_at_routing` / `failed_at_final_payload` / `timeout`), optional `stalled_phase` for timeouts, and the extraction-quality status (`pass` / `weak` / `review_required`) as a separate enumerated field.
- **VoterConfig (reused)**: The same voter-configuration document already used by the stage 1 extractor (feature 005) and the GPU MVP promotion work (feature 021). This feature reads it to identify the expected extraction model name; this feature does not change its schema.
- **OllamaModelStatus**: The subset of a `/api/ps` entry relevant to GPU-placement verification — the model `name`, `size`, `size_vram`, and context-length field when exposed — as observed at readiness check time and after the run for fallback detection.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A fresh operator following only the runbook can execute the GPU MVP smoke/demo path end-to-end (start Ollama, run the canonical command, see the four artifacts and the demo report) without needing any undocumented commands or tribal knowledge.
- **SC-002**: On the successful path, the demo command validates all four canonical stage 1 artifacts against their current schemas and refuses to report runtime success if any of the four is missing or schema-invalid.
- **SC-003**: Each of the named readiness-failure classes (interpreter/venv, Paddle ROCm preflight, Ollama reachability, Ollama model GPU placement, Ollama context length, Ollama version) is detected and reported **before** any expensive pipeline run and **before** any pipeline artifact is written.
- **SC-004**: A run that completes only because the pipeline fell back to CPU is never reported as a successful GPU demo run.
- **SC-005**: Pipeline-runtime success and extraction-quality status are reported as two distinct fields in the demo report; an operator can determine each independently without parsing prose.
- **SC-006**: The documented demo path is stable enough — same operator, same machine, same fixture, three consecutive runs — to be adopted as the MVP integration-test checkpoint that gates the start of Jetson edge-fast implementation. "Stable enough" means all four canonical artifacts are schema-valid on each run and the `DemoRunReport` has the same readiness verdict, `runtime_outcome`, and `quality_status` on all three runs; byte identity is not required for model-influenced artifacts.
- **SC-007**: The readiness-only mode (`--check-only`) completes within 10 seconds on a correctly configured warm workstation.
- **SC-008**: The CPU-isolated pytest coverage exercises the CLI flow, exit-code table, readiness failure classes, and report shape with stubbed Paddle/Ollama dependencies, while the runbook records the workstation-only manual GPU smoke gate. The FR-002 `.venv-paddle-rocm` requirement governs operator runs; tests MAY stub the Paddle ROCm preflight (so CI without ROCm can still cover the readiness vocabulary) and MAY run from any Python environment, provided the stubs satisfy the same contract the venv-resident preflight would.
- **SC-009**: Automation can parse the demo command output for every run mode and outcome by reading stdout as exactly one JSON object whose `kind` is `demo_run_report`; no human-readable output appears on stdout.
- **SC-010**: A repeated run after stale artifacts exist deletes and rewrites only the four canonical stage 1 artifacts, leaving `source.pdf`, `expected.json`, `notes.md`, `semantic_table_truth.json`, evaluation outputs, and debug images untouched.

## Out of Scope

- Jetson edge-fast implementation, packaging, or validation.
- New stage 1 artifact schema versions or contract-set bumps (any schema work this feature touches is bug-fix only, per FR-014).
- Broad multi-document corpus benchmarking (single canonical fixture is the demo target).
- Cloud inference paths (provider-managed or otherwise).
- Full line-item extraction quality work.
- Changes to feature 022 semantic-quality scoring behavior; the evaluator may be invoked only through the optional `--with-evaluator` flag and is off by default.
- Making Docker Desktop expose the ROCm GPU on WSL (the WSL container Ollama path remains CPU-only and is explicitly **not** the GPU demo target).
- Changes to the host-Ollama startup script's environment-variable contract beyond documenting `OLLAMA_CONTEXT_LENGTH=2048` as the required value.

## Assumptions

- **Hardware/runtime baseline**: The workstation has the AMD `gfx1151` GPU exposed to WSL2 via ROCm and the existing `scripts/start-host-ollama-rocm-wsl.sh` is the only supported host-Ollama startup path on this workstation (per `docs/stage1-vendor-identity/ollama-runtime.md` and `docs/ollama-rocm-wsl-gfx1151-fix.md`).
- **Paddle ROCm venv exists**: `.venv-paddle-rocm` is already provisioned with a working `paddlepaddle-dcu` install per feature 014/015/016 lineage. Bootstrapping that venv is out of scope.
- **Canonical demo fixture**: The MVP demo defaults to the first easy stage 1 fixture (`tests/stage1_vendor_identity/inv_001_easy/`), with `--document-folder <path>` available for explicit override. This is the same fixture other recent GPU features (014–019) benchmarked against.
- **Reduced/header-first preset**: The canonical demo default is the feature 018 `header-first-v1` preset. No new preset is introduced in scope. Full/default OCR remains opt-in through `--preset full-ocr`.
- **Bounded timeout default**: FR-008 is the authoritative source for the 600-second pipeline-runtime timeout default; this assumption restates the FR for reader convenience and does not introduce a tuning knob — any change to the default is a spec change to FR-008.
- **Host Ollama identification**: The host Ollama instance is identified by the `OLLAMA_BASE_URL` environment variable (default `http://localhost:11434`); the demo never probes other URLs and never depends on Ollama instance auto-discovery beyond this variable.
- **Readiness-only surface**: User Story 2's "small GPU smoke test" is fulfilled by `--check-only` on the same canonical demo CLI, not by a separate CLI or shell script.
- **Quality-status source**: By default, the demo report's quality-status field is derived from existing artifact contents already produced by features 005/008/009/020 (e.g., `manual_review_required`, evidence-gate state) rather than by rerunning the feature 022 evaluator. The evaluator may be invoked with `--with-evaluator` when a sidecar is present, but it is not on the critical path of the demo command.
- **Voter config discovery**: The active voter config is the one already discovered by the stage 1 extractor (feature 005) and the GPU MVP promotion runbook (feature 021). No new discovery logic is introduced.
- **Stale-artifact behavior**: The canonical demo command deterministically overwrites the four canonical artifacts on every run.
- **`OLLAMA_CONTEXT_LENGTH=2048`**: This value comes from recent manual validation on this workstation. If the operative value changes (e.g., due to a model change), the runbook is the source of truth and this spec stays consistent because FR-006 references "the documented required value."
- **Minimum Ollama version**: Planning pinned the minimum supported Ollama version at `0.4.0` (R-023.10 in `research.md`), the first release with stable `size_vram` exposure on `/api/ps`. Older versions are unsupported for this demo gate; the readiness `ollama-version` check (FR-023) probes `/api/version` and fails on versions below this bound.
- **No Docker GPU path**: Container Ollama on WSL Docker Desktop is CPU-only and is explicitly outside the GPU demo target, per `docs/stage1-vendor-identity/ollama-runtime.md`.

## Dependencies

- **Feature 005 (single-voter extraction)** — voter-config discovery and the extractor's HTTP call to host Ollama.
- **Feature 014 (Paddle GPU preprocessing)** — the existing Paddle ROCm preflight that FR-002 mandates be invoked.
- **Feature 015 (GPU engine reuse + timing)** — existing `run_summary` timing fields are the canonical source for the `phase_timings` and `total_runtime_seconds` fields the `DemoRunReport` MUST include (per FR-025).
- **Feature 018 (DPI / region-first preprocess)** — the `header-first-v1` preset used by the reduced MVP GPU preprocessing path (FR-011).
- **Feature 019 (OCR-only fast lane)** — establishes the OCR-only profile this feature may compose with for the demo path.
- **Feature 020 (vendor evidence gate)** — provides the deterministic evidence-gate state consumed when populating the demo report's quality-status field.
- **Feature 021 (GPU MVP promotion)** — defines the four-run benchmark / runbook this feature hardens into a single canonical demo command.
- **Feature 022 (OCR semantic quality gate)** — already shipped; its evaluator may be optionally invoked but is not on the critical path of the demo command (per Assumptions).
- **Host Ollama startup script** — `scripts/start-host-ollama-rocm-wsl.sh` is treated as the canonical-and-only supported host Ollama startup path.
