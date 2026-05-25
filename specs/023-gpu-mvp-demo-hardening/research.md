# Research: GPU MVP Demo Hardening

**Phase 0 output of [plan.md](./plan.md).** Resolves the planning-deferred decisions from the triage record at `checklists/triage-2026-05-24.md` (138 items deferred from `/speckit.checklist` max-coverage). The spec has zero `NEEDS CLARIFICATION` items after three `/speckit.clarify` rounds, so research focuses on planning-level decisions only.

Each R-decision below records: **Decision** / **Rationale** / **Alternatives considered**.

---

## R-023.1 · Sub-module composition mechanism (subprocess vs in-process)

**Decision:** In-process Python imports. The demo orchestrator imports the existing feature 003 preprocessing entry point, the feature 005 extractor's `VoterAdapter` + reconciler, the feature 008 router, and the feature 009 assembler as Python functions/classes — not subprocess invocations.

**Rationale:**
- Avoids spawning four child Python processes per run, each paying the Paddle/HIP import cost (~5–10 s each cold).
- Lets the orchestrator capture each phase's wall-clock timing directly (FR-025 `phase_timings`) using `time.monotonic()` brackets, with no IPC roundtrip noise.
- Lets the orchestrator enforce the 600 s `signal.alarm` budget across all four phases in one process.
- The four sub-modules already expose Python APIs alongside their CLIs (e.g., `dartwing_ocr.extract.run`, `dartwing_ocr.router.route`, `dartwing_ocr.assembler.assemble`); composing them in-process is the existing pattern.

**Alternatives considered:**
- **Subprocess via existing CLIs (`dartwing-extract`, `dartwing-router`, etc.):** would preserve the exact published CLI contracts but adds 4× import latency, complicates timeout enforcement, and would interleave each sub-module's `kind: "run_summary"` stdout line with the demo's `kind: "demo_run_report"` line, violating FR-019's single-line stdout discipline.
- **Mixed (in-process for hot path, subprocess for evaluator):** the `--with-evaluator` path could legitimately subprocess feature 022's evaluator since it is off-by-default and not on the critical path; we keep that door open under R-023.13.

---

## R-023.2 · `pipeline_version` source format

**Decision:** `pipeline_version` is the string returned by `importlib.metadata.version("dartwing-ocr")` (i.e., the installed package version from `pyproject.toml`). Falls back to the literal string `"unknown"` only if the package metadata is unresolvable (extremely rare; would indicate a broken install).

**Rationale:**
- Single source of truth — `pyproject.toml` already pins the package version (features 005/008/009/020/022 lineage uses the same field).
- Stable across the in-process composition: all four sub-modules ship in the same package, so a single `dartwing-ocr` version captures the whole pipeline build.
- Cheap to compute (no subprocess, no git call).

**Alternatives considered:**
- **`git describe --tags`:** would tie reports to a specific commit, but the operator workstation may not have a complete tag history; produces noisy output on dirty trees.
- **Composed string (`pp:0.1.0,ex:0.2.0,...`):** premature once sub-modules are not independently versioned — they all release as one package today.
- **Git short SHA:** brittle on shallow clones and unhelpful for non-developer operators.

---

## R-023.3 · Sub-module exit-code translation

**Decision:** In-process composition (R-023.1) means we map **exceptions**, not exit codes. The orchestrator catches each sub-module's documented exception class and maps it to the demo's exit-code table:

| Sub-module failure | Caught as | Maps to | Notes |
|---|---|---|---|
| Feature 003 preprocess error | `PreprocessError` | exit 4, `runtime_outcome: failed_at_preprocess` | |
| Feature 014 Paddle preflight fail (pre-run) | `PaddleROCmPreflightError` | exit 1, readiness check `paddle-rocm-preflight` fail | Caught in readiness phase |
| Feature 005 voter HTTP error / JSON-repair fail | `ExtractionError` / `JSONRepairError` | exit 4, `runtime_outcome: failed_at_extraction` | |
| Feature 005 Ollama context-window error | `OllamaContextWindowError` | exit 4, `runtime_outcome: failed_at_extraction` + startup-script diagnostic | FR-006 fallback path (triage C5) |
| Feature 008 routing error | `RoutingError` | exit 4, `runtime_outcome: failed_at_routing` | |
| Feature 009 assembler invariant error | `AssemblerInvariantError` | exit 4, `runtime_outcome: failed_at_final_payload` | |
| Post-run validator failure (any of 4 artifacts) | `ValidationError` | exit 5, `runtime_outcome: failed_at_final_payload` plus readiness check `artifact-schema-validation` fail | Schema validation runs after assembler |
| Timeout (`signal.SIGALRM`) | `TimeoutError` | exit 3, `runtime_outcome: timeout`, `stalled_phase` = currently-executing phase | |
| Generic `Exception` | catch-all → re-raise after best-effort report emit | exit 4, `runtime_outcome` reflects the phase where the exception originated | |

**Rationale:** Each sub-module already raises typed exceptions that planning can wire to the closed exit-code table directly. No exit-code translation across processes is required.

**Alternatives considered:**
- **Sub-module return codes (if we'd chosen subprocess composition):** would have required a translation matrix per sub-module; rejected with R-023.1.
- **Single generic `runtime_outcome: failed`:** loses phase resolution that US3 AS2 mandates.

---

## R-023.4 · Test stubbing strategy

**Decision:**
- **Paddle ROCm preflight stub:** a fixture in `tests/integration/gpu_demo/conftest.py` monkeypatches the feature 014 preflight entry point to return a synthetic `PreflightResult(device="rocm_gpu", ...)` (and parameterized variants for failure modes). No Paddle import in CI.
- **Ollama HTTP stub:** an in-process `httpx.MockTransport` mounted on the demo's HTTP client returns canned `/api/version` and `/api/ps` responses keyed by test scenario. No network in CI.
- **Voter-config stub:** test fixtures write minimal YAML files into a `tmp_path` and pass `--voter-config <tmp_path>/voter_config.yaml`. No reliance on feature 005's auto-discovery in CI.
- **Per-doc-folder stub:** test fixtures populate `tmp_path/inv_XXX_easy/` with synthetic `source.pdf` (4-byte PDF magic for the missing-PDF positive path; a real one-page PDF for the canonical happy path) and let the orchestrator's eager-delete + phase invocations operate against it.

**Rationale:** Mirrors the CPU-isolation testing pattern proven by feature 020 (vendor evidence gate) and feature 022 (semantic quality gate). No new test-framework dependency. Pytest markers `@pytest.mark.cpu` (default) and `@pytest.mark.gpu` (workstation-only) gate test selection on CI.

**Alternatives considered:**
- **`pytest-httpx` plugin:** redundant — `httpx.MockTransport` from the existing dependency is sufficient.
- **Fake Ollama HTTP server (e.g., FastAPI test server):** overkill; adds latency and a moving target.

---

## R-023.5 · CI environment markers and skip behavior

**Decision:**
- **CI pytest invocation:** `pytest tests/integration/gpu_demo/ -m "not gpu"` — runs every CPU-isolated test, skips workstation-only smoke.
- **Workstation pytest invocation:** `pytest tests/integration/gpu_demo/ -m "gpu"` — runs the workstation-only smoke; documented in the runbook.
- **No `xfail` on CI:** tests that cannot run on CI are explicitly marked `@pytest.mark.gpu` and skipped via the `-m` filter. We do not use `xfail` because it would mask regressions in the stubbed path.

**Rationale:** Mirrors feature 020 / 022 test-marker convention. Keeps the SC-008 CI coverage promise auditable from a single pytest selector.

**Alternatives considered:**
- **Auto-detect ROCm and skip silently:** would hide accidental ROCm-host CI runs that should be `@pytest.mark.gpu` but aren't tagged.
- **`pytest.importorskip("paddlepaddle_dcu")`:** rejected — paddle import is what we're stubbing; skipping when paddle is absent would un-cover the readiness vocabulary tests we want to exercise.

---

## R-023.6 · Run-correlation identifier

**Decision:** The `DemoRunReport` includes a top-level `run_id` field — a UUID4 string generated at command start. Stderr progress lines are prefixed with the first 8 hex chars of the same UUID (e.g., `[a1b2c3d4] readiness: paddle-rocm-preflight → pass (0.42s)`) so post-hoc log correlation across stdout JSON + stderr text is trivial.

**Prefix construction.** The 8-character stderr prefix is `run_id[0:8]` — the UUID4's first hex segment (8 characters before the first hyphen). For example, `run_id = "a1b2c3d4-1234-5678-9abc-def012345678"` → prefix `a1b2c3d4`. The prefix is computed once at process start and is identical across every stderr line within the same run. Automation that needs the full UUID reads it from `DemoRunReport.run_id` (always 36 characters including hyphens, lowercase hex).

**Rationale:** Cheap (one `uuid.uuid4()` call), unique across runs without coordination, and gives operators a grep target when comparing the JSON report to the live stderr stream.

**Alternatives considered:**
- **Timestamp only:** sub-millisecond collisions possible if automation runs two demos within the same wall-clock millisecond; the eager-delete + same-folder guard makes that pathological but the UUID costs nothing.
- **Sequential counter persisted in a file:** would introduce a stateful side effect that violates FR-017's "only the four canonical artifacts" overwrite scope.

---

## R-023.7 · Log levels and verbosity

**Decision:** No `--verbose` or `--quiet` flag. Stderr severity is encoded as a fixed prefix: `INFO:`, `WARN:`, `ERROR:` per line. Stderr is line-buffered (`sys.stderr.reconfigure(line_buffering=True)`) so operators see progress during the 600 s window.

**Rationale:**
- The operator surface is already tight (5 flags); adding verbosity knobs is scope creep.
- Severity prefixes give automation a grep target (`grep '^WARN:'` etc.) without requiring a logging framework.
- The structured `DemoRunReport` carries the full machine-readable detail; stderr is the human-readable progress channel.

**Alternatives considered:**
- **Python `logging` module with `--log-level`:** adds dependency on a configuration knob the operator does not need.
- **Rich-format stderr (colors, spinners):** rejected — automation that grabs `stderr` would have to strip ANSI codes; not worth the operator gloss for an MVP demo.

---

## R-023.8 · Per-phase sub-budgets within the 600 s aggregate

**Decision:** **No per-phase sub-budgets** in this feature. The 600 s aggregate is the only enforced timeout. Phase-level wall-clock numbers are captured in `phase_timings` (FR-025) for post-run analysis but are not enforced budgets.

**Rationale:**
- The MVP demo is a single fixture on a known workstation; per-phase budgets would require benchmarking each phase under cold and warm cache conditions and would risk timing-driven flakiness in `--check-only` cadence.
- A per-phase budget would also need a per-phase `runtime_outcome` value or a new diagnostic class — both expand the closed vocabularies the spec deliberately pins.
- Operators can derive per-phase regressions from `phase_timings` deltas across SC-006's three-run baseline; no enforcement gate is needed yet.

**Alternatives considered:**
- **Per-phase soft budgets (warn-on-exceed, don't fail):** would couple this feature to phase-level benchmark numbers that the runbook does not yet pin.

---

## R-023.9 · Cold vs warm cache budgets and SC-007 measurement

**Decision:**
- The 10 s `--check-only` bound (SC-007) is **warm-cache only**. A cold-cache cold-start (first invocation after a fresh shell, MIOpen cache empty) may exceed 10 s and is **not** a SC-007 violation; the runbook documents this.
- The 600 s pipeline bound (FR-008) is **cold-or-warm**. No distinction.
- `DemoRunReport.phase_timings` always reports raw wall-clock — no normalization. SC-006 stability is checked against `runtime_outcome` + `quality_status`, not against timings (per round-2 Q10 decision).

**Cold-cache informal target (audit walkthrough 2026-05-25 Q9):** The runbook documents an **informal 30-second cold-cache target** for `--check-only` — not a spec-level success criterion, not enforced, just an operator expectation. If an operator sees `--check-only` exceeding 30 s on a cold start, they should suspect a deeper issue (e.g., MIOpen cache wiped, ROCm misconfigured) rather than acceptable cold-start latency. SC-007's warm-only bound remains the gate.

**Rationale:** Cold-vs-warm distinction would require either probing the MIOpen cache state (brittle) or running a synthetic warmup before the readiness preflight (defeats the "fast" purpose of `--check-only`). The runbook captures the operator expectation in plain prose; the spec doesn't need a new enum value.

**Alternatives considered:**
- **Two SC entries (warm 10 s, cold 30 s):** rejected as spec scope creep; planning can amend if the cold-start case becomes a regular regression.
- **Auto-warm step before `--check-only`:** rejected — `--check-only` is supposed to be cheap; pre-warming Paddle would make it pay the same cost as a half-pipeline.

---

## R-023.10 · Minimum Ollama version

**Decision:** Minimum supported Ollama version is **`0.4.0`** (the first release that documented stable `size_vram` on `/api/ps` entries). The runbook records this; the `ollama-version` readiness check (FR-023) probes `/api/version` and parses the `version` field as a `packaging.version.Version`, comparing against `Version("0.4.0")`.

**Rationale:**
- Pre-`0.4.0` Ollama releases do not consistently expose `size_vram`, which is the FR-005 placement criterion. Failing fast under the named `ollama-version` check (rather than failing later under `ollama-model-gpu-placement` with a confusing "size_vram missing" diagnostic) is the round-3 Q4 / triage C1 resolution.
- `packaging>=23` is already transitively pulled by `pip` and `setuptools`; no new pinned dependency.

**Alternatives considered:**
- **Defer to the runbook entirely (no code probe):** would mean an old Ollama on the workstation produces a misleading `ollama-model-gpu-placement` failure instead of the diagnostic operators need. Spec FR-023 explicitly mandates a coded check.
- **Lower bound (`0.3.x`):** rejected — would require client-side defensive parsing of `size_vram` that masks the original issue.

---

## R-023.11 · Diagnostic string format and determinism

**Decision:** Each readiness check produces a diagnostic dict with a closed set of keys:
- `checked`: short prose ("Paddle device backend"; "Ollama /api/ps for `qwen2.5-vl:7b`")
- `observed`: machine-readable value where possible (`"cpu"`, `null`, `{"size": 4906000000, "size_vram": 0}`, `"0.3.12"`)
- `expected`: machine-readable expected value (`"rocm_gpu"`, `">= 0.4.0"`, `"size_vram == size and size_vram > 0"`)
- `remediation`: one short imperative sentence ("Run scripts/start-host-ollama-rocm-wsl.sh", "Upgrade Ollama to >= 0.4.0", "Activate .venv-paddle-rocm")

The diagnostic dict is emitted both inside the `DemoRunReport` JSON (under `readiness.checks[<name>].diagnostic`) and as a single stderr line (`ERROR: readiness check 'ollama-version' failed — observed 0.3.12, expected >= 0.4.0. Remediation: upgrade Ollama to >= 0.4.0.`).

**Rationale:**
- Closed-key shape lets automation grep specific fields.
- `remediation` field captures the per-failure-class recovery action the triage gap list called out.
- Same diagnostic in both stdout JSON and stderr satisfies the FR-029-style observability gap (mirrored from observability checklist CHK028).

**Alternatives considered:**
- **Free-form diagnostic string:** loses structured grep targets and re-introduces the "different wording in different places" risk the spec consistency checklist flags.
- **Per-check custom diagnostic shape:** rejected — uniformity helps consumers.

---

## R-023.12 · Field-order stability in JSON output

**Decision:** `DemoRunReport` is serialized using `json.dumps(report_dict, sort_keys=False, ensure_ascii=False, separators=(",", ":"))` with the field order pinned by the dataclass declaration order (which matches the order in `contracts/demo-report-schema.md`). Nested dicts (`phase_timings`, `readiness.checks[]`) use the same fixed declaration order.

**Rationale:**
- Stable order makes byte-comparison of the JSON line tractable for SC-006 stability checks on the deterministic phases (preprocess / routing / final_payload), even though we do not require byte-identity (round-2 Q10).
- `ensure_ascii=False` preserves non-ASCII characters in voter-config paths or model names without `\uXXXX` escaping that breaks operator readability.

**Alternatives considered:**
- **`sort_keys=True`:** alphabetizes the output, which is consumer-friendly but breaks the spec's explicit field-presence-order story (FR-019 says "same key set on every outcome" implies an authored order, not an alphabetical one).
- **JSON Lines with indented pretty-printing:** rejected — FR-019 says single line.

---

## R-023.13 · `--with-evaluator` invocation mechanism

**Decision:** The `--with-evaluator` flag invokes the feature 022 evaluator **as a subprocess** via the existing `python -m dartwing_ocr.evaluator` CLI (or its `dartwing-evaluator` console-script equivalent), capturing its exit code and reading the resulting `evaluation_document.json` from the per-doc folder. The subprocess is the **only** subprocess in the demo path; the four core phases stay in-process (R-023.1).

**Subprocess invocation pin-down (audit walkthrough 2026-05-25 Q6):** The exact subprocess invocation is:

```python
subprocess.run(
    [sys.executable, "-m", "dartwing_ocr.evaluator",
     "evaluate-document", "--folder", str(document_folder), "--quiet"],
    cwd=str(document_folder),
    env=os.environ.copy(),            # inherits the demo's full environment unchanged
    capture_output=True,               # capture stderr; stdout is the evaluator's run_summary JSON line
    timeout=60.0,                      # R-023.13 budget
    check=False,                       # demo handles non-zero exit per the failure-handling clause below
)
```

- The evaluator subcommand name (`evaluate-document`) is the feature 022 CLI's existing per-document entry point.
- `--quiet` suppresses the evaluator's own progress lines; only the evaluator's final stdout JSON line is consumed.
- `cwd=document_folder` so any relative paths in the evaluator's internal logic resolve against the per-doc folder.
- Captured stderr is replayed through `log.info(run_id, f"evaluator: <line>")` per the Q10 sub-module stderr propagation rule (see `contracts/cli-contract.md`).

**Evaluator subprocess failure handling.** If the evaluator subprocess exits non-zero, fails to start (missing binary, PATH issue), or crashes (signal kill):

- The demo emits a `WARN:[run_id] --with-evaluator: evaluator subprocess failed with exit <N> / signal <S>; falling back to gate-derived quality_status` stderr line.
- `quality_status_source` stays `"gate"` in the `DemoRunReport` (the evaluator did not produce a verdict).
- The demo's own exit code is NOT modified by the evaluator failure — the pipeline outcome remains authoritative. A successful pipeline + failed evaluator subprocess still exits `0`; a failed pipeline + failed evaluator subprocess still exits per the pipeline failure (3 / 4 / 5).
- The evaluator subprocess has its own 60 s wall-clock budget; exceeding it is treated identically to a non-zero exit.

This preserves the "evaluator is off the critical path" property (per FR-022).

**Rationale:**
- The evaluator is off by default (FR-022) and not on the critical path; the subprocess cost is acceptable when explicitly requested.
- Keeps the evaluator's CPU-only Python isolation independent of the demo's Paddle ROCm process (the evaluator was deliberately authored CPU-only in feature 022).
- Avoids pulling the evaluator's import graph into every demo run.

**Alternatives considered:**
- **In-process import of the evaluator:** would force the demo to carry the evaluator's import cost on every run, defeating the "off by default" intent.
- **Skip subprocess; use the evaluator's Python API directly only when `--with-evaluator`:** same import-cost concern as above.

---

## R-023.14 · `OLLAMA_BASE_URL` discovery and validation

**Decision:** The demo reads `OLLAMA_BASE_URL` from the environment (default `http://localhost:11434`) and uses it as the **only** Ollama probe target. Validation:
- URL parsed via `urllib.parse.urlparse`; scheme must be `http` or `https`; host non-empty.
- If host is **not** `localhost` / `127.0.0.1` and not a known WSL2-host hostname, readiness emits an `INFO:` stderr line noting the non-localhost target but does not fail (the constitution's "workstation-only" assumption is documented, not enforced in code).
- Invalid URL syntax → exit 2 (invalid input/usage).

**Rationale:**
- Pins the multi-Ollama disambiguation (triage A1 / FR-006).
- Non-localhost targets are operator-supplied and may be legitimate (e.g., a second workstation across a LAN); a soft warning preserves flexibility while signaling the constitution assumption.

**Alternatives considered:**
- **Hard-fail on non-localhost:** rejected — would block legitimate cross-workstation testing during operator setup.
- **No validation at all:** rejected — invalid URLs would surface as opaque `httpx.ConnectError` mid-readiness instead of a clear exit-2 usage error.

---

## R-023.15 · CPU-fallback detection — concrete probes

**Decision:** Post-run device interrogation (FR-012) runs **two** probes after the pipeline completes (or fails):
1. **Ollama re-probe:** call `/api/ps` again, find the same model identity (name + tag), assert `size_vram == size` AND `size_vram > 0`. Any deviation flips the run from `runtime_outcome: success` to `runtime_outcome: failed_at_extraction` with diagnostic `cpu-fallback-detected` and the pre-run / post-run `/api/ps` excerpts attached.
2. **Paddle device re-probe:** re-invoke the feature 014 preflight; if the post-run backend is not `rocm_gpu`, same flip applies.

Both probes are best-effort: if either Ollama or Paddle is now unreachable (e.g., Ollama crashed during the run), the demo reports `runtime_outcome: failed_at_extraction` with a different diagnostic (`post-run-interrogation-unreachable`) — not a CPU-fallback diagnosis. This avoids false positives where an environmental crash is mistaken for fallback.

**Probe timing budget.** Each of the two post-run probes has a **2-second wall-clock timeout** (matching the readiness HTTP timeout). The combined post-run interrogation phase has a **5-second aggregate budget**. These budgets do NOT count against the 600 s pipeline timeout (FR-008) — post-run interrogation happens after the pipeline completes (or fails / times out).

- Probe timeout exceeded → result is `"unreachable"`, not `"fell_back"`.
- Combined budget exceeded → both probes are marked `"unreachable"`; demo emits `WARN:[run_id] post-run interrogation exceeded 5s budget; CPU-fallback detection inconclusive`.
- An `"unreachable"` result does NOT downgrade a `success` outcome to `failed_at_extraction`. It DOES set `failure_kind: "post-run-interrogation-unreachable"` on the report so operators know the SC-004 guarantee was best-effort, not confirmed.

**Rationale:**
- Symmetric with the pre-run readiness checks — reuses the same predicate functions.
- Distinguishes "GPU vanished" from "we silently went to CPU" cleanly.
- Falsifies SC-004 in a single deterministic check.

**Alternatives considered:**
- **Timing heuristic (run took > N s → suspect CPU):** rejected per round-2 Q9.
- **Single re-probe of Ollama only:** misses the Paddle CPU-fallback path (where preprocessing went to CPU but Ollama was always GPU).

---

## R-023.16 · CI test runtime budget

**Decision:** The full CPU-isolated pytest suite for this feature targets **≤ 60 s wall-clock on CI** (no Paddle import; no network; only stubs). Individual test fixtures favor `tmp_path` over network mocks; assertions are exact JSON-line bytes where deterministic (the three deterministic phases, per R-023.12).

**Rationale:**
- Keeps the demo's test pack small enough that it doesn't dominate the repo's overall CI time.
- 60 s comfortably accommodates ~50 test functions across the 14 test files at ~1 s budget each.

**Alternatives considered:**
- **No explicit budget:** invites slow-test creep.
- **Stricter 30 s:** would require shared fixture caching that complicates the conftest and crowds the simpler pytest-fixture-per-test pattern.

---

## R-023.17 · Runbook update strategy

**Decision:** Extend `docs/stage1-vendor-identity/runbook-gpu-mvp-demo.md` in place per Q15 (round 1 clarification), with three new sections appended at the end plus a colleague-dry-run appendix per Q11 (audit walkthrough 2026-05-25):
- **§ Canonical Demo Command** — the `python -m dartwing_ocr.gpu_demo` form, defaults, and all 5 flags with default values and worked examples.
- **§ Readiness Failure Recovery Matrix** — one row per FR-016 closed-vocabulary check, listing the diagnostic shape (R-023.11) and the operator action (close the gap raised by the triage recovery-action gaps).
- **§ Three-Run Stability Smoke Procedure (SC-006)** — the workstation-only manual gate: pre-run state, three consecutive command invocations, the three `DemoRunReport` lines captured to a scratch file, the byte-comparison rule for the three deterministic artifacts, the operator sign-off block.
- **§ Appendix: Colleague Dry-Run Sign-Off (Q11)** — a one-page checklist for SC-001 verification. A colleague who has not previously run the demo follows the runbook end-to-end on a fresh shell; gaps they encounter (undocumented commands, ambiguous prerequisites, missing remediation steps) are recorded inline; the colleague signs a dated line at the bottom. No new spec-level SC; the appendix is process documentation only.

The runbook prerequisites (Paddle venv, host Ollama startup script, OLLAMA_CONTEXT_LENGTH, minimum Ollama version) are consolidated into a single "Prerequisites" subsection that this feature adds at the top of the existing runbook.

**Rationale:**
- Single-file runbook avoids documentation fragmentation.
- The Recovery Matrix discharges the cluster of triage gaps under "Recovery-action documentation per failure class".
- The Three-Run Stability section makes SC-006 operationally measurable.

**Alternatives considered:**
- **New file (`runbook-gpu-mvp-demo-canonical.md`):** rejected per Q15.
- **Replace feature 021 runbook contents:** rejected — feature 021 is the upstream historical record; we extend.

---

## R-023.18 · Pytest fixture corpus for negative-path tests

**Decision:** Synthetic test fixtures live under `tests/integration/gpu_demo/fixtures/`:

| Fixture folder | Purpose |
|---|---|
| `ok/` | Valid `source.pdf` (real 1-page invoice from existing corpus); used by happy-path tests |
| `missing_source_pdf/` | Folder exists but contains no `source.pdf`; exit-2 path |
| `malformed_voter_config/` | Folder + bad-YAML voter config in same dir; exit-2 path |
| `symlink_escape/` | Folder with a `preprocess_output.json` symlink that resolves outside the folder; exit-2 FR-017 guard |
| `with_evaluator_no_sidecar/` | Folder + valid `source.pdf` but no `semantic_table_truth.json`; warn-and-skip path |
| `with_evaluator_with_sidecar/` | Folder + valid `source.pdf` + minimal sidecar; evaluator-invoked path |

The "real PDF" used in `ok/` is `tests/stage1_vendor_identity/inv_001_easy/source.pdf` — symlinked, not copied, so a corpus update is automatically picked up.

**Symlink + FR-017 canonicalization interaction.** The `fixtures/ok/` folder contains a symlink at `fixtures/ok/source.pdf` pointing to `tests/stage1_vendor_identity/inv_001_easy/source.pdf`. The other six fixture folders (`missing_source_pdf/`, `malformed_voter_config/`, `symlink_escape/`, etc.) own their own files.

FR-017's canonicalization rule applies to the per-document folder path supplied via `--document-folder`. The symlinked `source.pdf` inside the folder is not affected by canonicalization because:

- The demo never deletes `source.pdf` (it is preserved per SC-010 — only the 4 canonical artifact filenames are eligible for eager-delete).
- The 4 canonical artifact filenames (`preprocess_output.json`, etc.) are NOT symlinked in `fixtures/ok/` — each test invocation writes them fresh into the canonicalized folder.

If the canonical corpus is updated (e.g., feature 022's labeling round adds a `notes.md`), the fixture continues to symlink the same `source.pdf` file. New files added to the canonical corpus are not symlinked into the fixture; tests that need them author their own copies. This keeps the fixture stable against unrelated corpus changes.

**Rationale:**
- Each fixture maps 1:1 to a closed exit-code or `runtime_outcome` value the tests need to cover.
- Symlink to the canonical fixture keeps the negative-path fixtures lightweight and avoids divergence.

**Alternatives considered:**
- **Generate fixtures at test time via `tmp_path`:** rejected — symlink-escape and malformed-YAML tests need stable on-disk shapes that are easier to author once than to re-create per test.

---

## R-023.19 · Composability with feature 011 stage-runtime profiles

**Decision:** **Not composed.** The demo CLI is a sibling of the feature 011 stage-runtime CLI, not a profile of it. The two share no code at runtime; the demo composes the lower-level sub-modules (003/005/008/009/014/018) directly.

**Rationale:**
- Feature 011 profiles select runtime *modes* (full-workstation / cloud-workstation / edge-fast). The demo is a fixed mode (full-workstation) with a fixed preset (header-first-v1) and a fixed fixture default.
- Wrapping the demo as a feature-011 profile would force operators through the more complex feature-011 surface for what is supposed to be a one-command experience (FR-001).
- The two CLIs can coexist; nothing in the spec prevents a future "feature 011 profile that internally invokes the demo" if the use case arises.

**Alternatives considered:**
- **`python -m dartwing_ocr.runtime --profile gpu-mvp-demo`:** rejected during round-1 clarification (Q1 chose Option A: new top-level CLI).

---

## R-023.20 · `quality_status` derivation truth-table

**Decision:** `quality_status` is derived from two inputs:

| Evidence-gate state (feature 020) | `manual_review_required` (feature 009 final payload) | `quality_status` |
|---|---|---|
| `sufficient` | `false` | `pass` |
| `sufficient` | `true` | `review_required` |
| `borderline` | `false` | `weak` |
| `borderline` | `true` | `review_required` |
| `insufficient` | `false` | `review_required` |
| `insufficient` | `true` | `review_required` |

When `--with-evaluator` is supplied AND the evaluator returns a result, the evaluator's `semantic_table_quality_passed` field augments — but does not replace — the above derivation: if the table above says `pass` but the evaluator says `failed`, the result is downgraded to `weak`. The evaluator can never upgrade `review_required` to `pass`.

**Warn-and-skip outcome.** When `--with-evaluator` is supplied AND the per-document folder lacks `semantic_table_truth.json`, the evaluator subprocess is NOT invoked (warn-and-skip per FR-022). In this case `quality_status_source` is `"gate"` in the report (the gate-derived value is the actual source) — NOT `null` and NOT `"evaluator"`. This is consistent with the warn-and-skip behavior being "the operator wanted evaluator but the demo fell back to gate-only derivation".

**Rationale:**
- Mirrors the spec's plain-prose mapping from round-1 Q5 (`pass = sufficient gate AND no manual_review_required`).
- The "evaluator can downgrade but not upgrade" rule preserves the safety property that manual review is never silently skipped.

**Alternatives considered:**
- **Three-axis lattice (gate × review × evaluator):** more expressive but loses the operator-readable two-input mental model.

---

## R-023.21 · Float precision for wall-clock fields

**Decision:** All wall-clock float fields in `DemoRunReport` are rounded to **3 decimal places** (millisecond resolution) before JSON serialization. Applies to:

- `ReadinessCheck.elapsed_seconds`
- `ReadinessSummary.elapsed_seconds`
- `PhaseTimings.preprocess`, `.extraction`, `.routing`, `.final_payload`
- `total_runtime_seconds`

Rounding uses Python's `round(value, 3)` (banker's rounding, IEEE 754). Serialization uses standard `json.dumps` for these floats — `round()` returns a Python `float`, and `json.dumps` produces a stable string form for 3-decimal floats (e.g., `0.123`, `2.500`, `18.050`).

**Rationale:**
- Millisecond resolution is sufficient for SC-006 operator-visible comparison across three runs; raw nanosecond precision would surface IEEE-754 noise that varies by CPU scheduler.
- Stable byte form of `DemoRunReport` lines is not a hard requirement (SC-006 byte-identity applies to the 4 artifacts, not the report line), but the 3-dp rounding makes spot-comparison of report lines tractable for triage.
- 3 dp is consistent with feature 015's `run_summary.phase_timings` precision in the existing implementations.

**Alternatives considered:**
- **Microsecond (6 dp):** unnecessary precision; introduces noise in operator-readable diff.
- **Integer milliseconds (no dp):** loses sub-millisecond signal that may matter for the `interpreter/venv` check.
- **No rounding:** invites IEEE-754 noise in the JSON line.

---

## Summary

21 R-decisions resolve the planning-deferred items from the triage record (mostly composition mechanism, version/diagnostic format, test strategy, observability micro-details, runbook layout) and the plan-coverage findings of 2026-05-25 (CHK051, CHK052, CHK053, CHK054, CHK055/CHK059, CHK056, CHK057, CHK058, CHK060, CHK061, CHK064). Together with the 32 spec clarifications and the triage applied to the spec, planning has no remaining `NEEDS CLARIFICATION` items.

**Next:** Phase 1 produces `data-model.md` (entities and field shapes), `contracts/cli-contract.md` (CLI surface), `contracts/demo-report-schema.md` (JSON-line schema), `contracts/readiness-vocabulary.md` (8-check fixed-order vocabulary), and `quickstart.md` (operator + developer walk-through).
