# GPU MVP Demo Runbook

This runbook is the canonical operator path for the stage-1 vendor-identity GPU-required demo (feature 021). It starts with the FR-001 / FR-002 readiness gate, runs the demo using `ppstructurev3@gpu` for preprocessing and `ollama@gpu` for extraction, surfaces the seven feature-020 `run_summary` observability fields, and ends with the recorded promotion decision. CPU paths are NOT in scope here (see `docs/stage1-vendor-identity/ollama-runtime.md` for CPU/stub operational guidance).

## Prerequisites

- AMD ROCm workstation (WSL or native Linux).
- `paddlepaddle-dcu` installed in `.venv-paddle-rocm` (matching feature 014–019 conventions).
- Host Ollama started via `scripts/start-host-ollama-rocm-wsl.sh` (WSL) or the equivalent native Linux path; the extraction model named by the demo's voter config is loaded with GPU placement.
- A scratch directory `/tmp/021-bench/` available (or another explicit scratch root).
- The voter config at `configs/voter/ollama-gpu.yaml` (R-021.7) names the loaded extraction model.

**Operator skills**: this runbook assumes operator familiarity with `git`, Python venvs, and basic shell (`bash` / `zsh`). Anything beyond that floor is explained inline below.

**Demo audience**: internal pipeline engineers and reviewers. External stakeholders (compliance, legal) by invitation only — the demo surfaces internal observability fields that may carry context-sensitive information.

**Expected wall-time**: the readiness gate (Step 1) takes ≈ 30 seconds; the canonical demo command (Step 2b) takes ≈ 60–120 seconds per run on this workstation. A run that exceeds 5× expected wall-time is a finding and should be investigated before the demo continues.

## Step 1 — GPU Readiness Gate (REQUIRED)

The demo MUST NOT proceed if either of the two readiness sub-steps fails. The composite GPU Readiness Verdict (FR-001 + FR-002) is PASS only when both checks PASS.

### Step 1a — Paddle preflight (FR-001)

```bash
.venv-paddle-rocm/bin/python -m dartwing_ocr.preprocessing.preflight 2>readiness-paddle.log
```

Expected outcome: stdout shows `state: ppstructurev3_init_succeeded`. On any other state, STOP and read `readiness-paddle.log` for the named blocker. Do NOT continue under degraded conditions — the FR-004 fail-fast surface requires it.

Common blockers and remediation:

| Stderr blocker (paraphrased)                  | Likely cause                                  | Operator action                                     |
|----------------------------------------------|----------------------------------------------|----------------------------------------------------|
| `paddle_cpu_only`                             | Wrong interpreter / CPU `.venv` selected      | Re-run from `.venv-paddle-rocm/bin/python`         |
| `paddle_not_installed`                        | `paddlepaddle-dcu` not in active venv         | `pip install paddlepaddle-dcu` (workstation only)  |
| `gpu_bind_failed` / `rocm_missing`            | ROCm runtime not visible to Python            | Check `rocm-smi`; ensure HSA env is set correctly  |
| Other named state                             | See FR-010 closed list of named-cause categories | Read full `readiness-paddle.log` and remediate |

### Step 1b — Ollama placement (FR-002)

```bash
scripts/check-ollama-gpu-readiness.sh \
    --voter-config configs/voter/ollama-gpu.yaml \
    2>readiness-ollama.log
```

Expected outcome: exit 0 + a single JSON line on stdout with `"status": "pass"`. Specifically, the helper asserts that the matched-model entry in `/api/ps` has `size_vram > 0 AND size_vram == size` (fully on GPU per Clarification Q2 / FR-002). Partial CPU/GPU placement (`0 < size_vram < size`) fails the check.

Common remediation:

| Helper exit | Likely cause                         | Operator action                                                                          |
|------------:|--------------------------------------|------------------------------------------------------------------------------------------|
| `1`         | Mixed CPU/GPU placement              | Restart Ollama with GPU env set; verify with `rocm-smi` that VRAM is available           |
| `2`         | Model not loaded                     | Run `ollama run <model_name> ""` once to warm the model into Ollama, then re-check       |
| `3`         | Ollama unreachable                   | Confirm `scripts/start-host-ollama-rocm-wsl.sh` is running; check port 11434 is open     |
| `4`         | Voter config missing / malformed     | Confirm `configs/voter/ollama-gpu.yaml` exists and has a non-empty top-level `model_name` |

Only proceed to Step 2 when both Step 1a AND Step 1b PASS. Capture both `readiness-paddle.log` and the helper's stdout PASS JSON for the run record (see Step 5 / Appendix A environment fingerprint).

## Step 2 — Run the Canonical Demo Command

### Step 2a — Scratch-prep the demo corpus

The pipeline writes outputs back into each per-doc folder listed in `--documents-file` (warm-corpus mode does not honor `--output-dir` per research.md §R-021.14). To preserve FR-018 / FR-025(f) / SC-011 (no committed-corpus mutation), mirror `source.pdf` for each demo document into a scratch tree first:

```bash
DEMO_DOCS=(inv_001_easy inv_002_easy)   # whichever subset the demo audience expects
for D in "${DEMO_DOCS[@]}"; do
    mkdir -p "/tmp/021-bench/demo/$D"
    cp "tests/stage1_vendor_identity/$D/source.pdf" "/tmp/021-bench/demo/$D/"
done
: >/tmp/021-bench/demo/docs.txt
for D in "${DEMO_DOCS[@]}"; do
    echo "/tmp/021-bench/demo/$D" >>/tmp/021-bench/demo/docs.txt
done
```

### Step 2b — Run the demo

```bash
.venv-paddle-rocm/bin/python -m dartwing_ocr.pipeline run \
    --documents-file /tmp/021-bench/demo/docs.txt \
    --preprocess-profile ppstructurev3@gpu \
    --preprocess-strategy ocr-only-v1 \
    --extract-profile ollama@gpu
```

Required flag set (all verified against the actual CLI):

- `--documents-file <PATH>` — text file listing scratch per-document folders (one per line, e.g., `/tmp/021-bench/demo/inv_001_easy`). MUST point at the scratch tree from Step 2a, NEVER at `tests/stage1_vendor_identity/` directly.
- `--preprocess-profile ppstructurev3@gpu` — selects the GPU preprocessing profile.
- `--preprocess-strategy ocr-only-v1` — enables the OCR-only fast lane that the evidence gate's skip-fallback acts on. Both flags are required together for the documented behavior.
- `--extract-profile ollama@gpu` — selects the GPU-backed Ollama extraction voter. The voter-config YAML at `configs/voter/ollama-gpu.yaml` is consumed by the readiness helper (Step 1b), NOT by this command.

Optional flags for documented variants:

- `--evidence-gate-skip-fallback` — enable OCR-only skip-fallback suppression (the candidate lane in feature 020 / 021 promotion evidence).
- `--gpu-warmup` — force PPStructureV3 construction even when every document is suppressed (FR-009 operator trade-off).

## Step 3 — Read the `run_summary` Line

The demo emits a single `kind: "run_summary"` JSON line on stdout (feature 015 lineage). The runbook explains each of the seven required FR-025(d) observability fields:

- **`schema_version`** — feature 020 `RunSummary.SCHEMA_VERSION` (currently `0.1.7`). Audit signal: confirms the demo is running on the feature-020 baseline.
- **`preprocess_lane`** — `gpu0` for this demo (the lane suffix is the device index; CPU lanes emit `cpu`). If this field reads `cpu`, something has gone wrong; STOP and re-run Step 1.
- **`preprocess_strategy_id`** — `ocr-only-v1` (matches the `--preprocess-strategy ocr-only-v1` flag passed in Step 2b; the `--preprocess-profile ppstructurev3@gpu` flag selects the lane, not the strategy).
- **`evidence_gate_id`** — must be `"v1"` (the closed vocabulary at landing per feature 020 R-020.2). Anything other than `"v1"` means either a future preset has been added or the serializer is buggy; STOP and investigate.
- **`evidence_gate_state_counts`** — distribution of `sufficient` / `borderline` / `insufficient` across the processed documents. Reads as a per-state count map.
- **`evidence_gate_documents`** — per-document table of decisions; cross-check against scratch outputs at `/tmp/021-bench/demo/<doc>/`.
- **`evidence_gate_suppressed_fallback_count`** — non-zero iff at least one `sufficient` document was suppressed (i.e., the demo was run with `--evidence-gate-skip-fallback` or its default-on equivalent if promote-to-default is the recorded posture; see §Promotion Decision below).

## Step 4 — Demonstrate Suppression Behavior (Optional)

If the audience wants to see suppression in action, re-run Step 2b twice — once with and once without `--evidence-gate-skip-fallback`:

```bash
# Default lane (skip-fallback OFF; PPStructureV3 fallback fires on every doc).
.venv-paddle-rocm/bin/python -m dartwing_ocr.pipeline run \
    --documents-file /tmp/021-bench/demo/docs.txt \
    --preprocess-profile ppstructurev3@gpu \
    --preprocess-strategy ocr-only-v1 \
    --extract-profile ollama@gpu

# Candidate lane (skip-fallback ON; PPStructureV3 fallback suppressed on sufficient docs).
.venv-paddle-rocm/bin/python -m dartwing_ocr.pipeline run \
    --documents-file /tmp/021-bench/demo/docs.txt \
    --preprocess-profile ppstructurev3@gpu \
    --preprocess-strategy ocr-only-v1 \
    --extract-profile ollama@gpu \
    --evidence-gate-skip-fallback
```

Compare the two `run_summary` lines:

- The candidate run's `evidence_gate_suppressed_fallback_count` MUST be > 0 (one increment per `sufficient` document).
- The candidate run's per-doc `phase_timings.engine_init` and `phase_timings.warmup` keys MUST be absent on suppressed documents (lazy construction; FR-008).
- Default-lane: at least one document's `phase_timings.engine_init` key is present (PPStructureV3 fallback ran, and the one-time engine-init timing attaches to the FIRST per-doc record that constructs the engine per feature 016 amortization — later docs in the same run do NOT carry their own `engine_init` entry). `phase_timings.warmup` is conditional on this demo invoking `--gpu-warmup`; the canonical demo command above does NOT pass it, so `warmup` is legitimately absent from every record. If the operator added `--gpu-warmup` to the command, `warmup` would appear on the first record. Use the absence of `warmup` to confirm the canonical (no-warmup) invocation, not to suspect a broken run.

## Scratch Discipline

A short reminder reproducing FR-018 + FR-025(f): all output lands under `/tmp/021-bench/` (or another explicit scratch root); committed corpus under `tests/stage1_vendor_identity/` is NEVER mutated by a demo run. Operators concerned about contamination can `git status tests/stage1_vendor_identity/` after the demo and confirm zero changes.

**Cleanup discipline**: after the demo / benchmark, the operator MAY `rm -rf /tmp/021-bench/` to remove scratch outputs. Scratch retention is operator choice — the runbook does not require it but does not forbid it.

## Promotion Decision

This section mirrors the authoritative `### Promotion Decision (YYYY-MM-DD)` subsection in [feature-020 `quickstart.md` Appendix B](../../specs/020-vendor-evidence-gate/quickstart.md). Mirror content MUST agree with Appendix B on the binary `Decision:` literal; a CPU-safe contract test at `tests/contract_tests/test_promotion_decision_sync.py` verifies the agreement.

**Decision**: _(placeholder — populate from Appendix B when the team records the decision per T028. Allowed values: `stay opt-in` or `promote to default`. Default at landing: `stay opt-in`.)_

**Gating verdict**: see [Appendix B §Quality-Gate Verdict](../../specs/020-vendor-evidence-gate/quickstart.md) for the FR-019 verdict (`PASS` / `FAIL` / `BLOCKED`) that gates this decision. FR-027 — if the gating verdict is FAIL or BLOCKED, the recorded Decision MUST be `stay opt-in`; promotion is not a permitted option.

If the recorded Decision is `promote to default`, the operator can opt back to legacy behavior for a CPU-safe smoke run with:

```bash
DARTWING_EVIDENCE_GATE_SKIP_FALLBACK=0 .venv/bin/pytest tests/unit/preprocessing/test_skip_fallback_explicit_off_legacy.py -v
```

(The legacy-path test is created by T030 when promote-to-default lands. Until then, the test file does not exist.)

## When Things Go Wrong

Concise table of common failure paths with named-cause remediation:

| Symptom                                                  | Likely cause                          | Remediation                                                                              |
|----------------------------------------------------------|----------------------------------------|------------------------------------------------------------------------------------------|
| Paddle preflight returns a non-success state             | Wrong interpreter, missing ROCm, …    | Read `readiness-paddle.log`; fix the named blocker; re-run Step 1a.                       |
| `check-ollama-gpu-readiness.sh` exits non-zero           | See Step 1b remediation table.         | Read the script's `FAIL:` stderr line; apply the Step 1b remediation table row matching that named cause; re-run Step 1b. |
| Demo command exits non-zero                              | Likely a missed readiness step.        | Re-run Step 1; if Step 1 passes, capture the demo stderr and escalate.                    |
| `evidence_gate_suppressed_fallback_count` is unexpectedly 0 on a `sufficient` document | Skip-fallback not enabled. | Either pass `--evidence-gate-skip-fallback` (stay-opt-in operational mode) or confirm the runbook reflects the current promotion decision. |
| Demo wall-time exceeds 5× expected (Step 2b > ~10 min)   | GPU contention, cache cold, ROCm drift | Verify exclusive GPU access (no other process consuming `rocm-smi`-reported VRAM); re-run; if persistent, raise a workstation finding. |

**Abort path** (mid-demo cleanup): `Ctrl+C` interrupts the running pipeline command. After interrupt, the operator MAY `rm -rf /tmp/021-bench/` to clean up scratch outputs. Readiness state (Paddle preflight + Ollama placement) is unchanged by the interrupt — re-running the demo from Step 2 does not require re-running Step 1 unless Ollama state has changed (e.g., the model was unloaded).

## Documentation discipline

- Runbook examples MUST use document IDs (e.g., `inv_001_easy`) and synthetic vendor strings where any vendor-identity content is shown.
- This runbook MUST NEVER include real vendor names, addresses, or other PII extracted from any document in `tests/stage1_vendor_identity/`. Feature 006's PII screening covers the corpus; the runbook MUST NOT undo that screening by reproducing screened content in example output.

## See also

- [feature-020 quickstart Appendix A](../../specs/020-vendor-evidence-gate/quickstart.md) — recorded benchmark numbers (the four-run + jitter-band tables operators populate after running T014).
- [feature-020 quickstart Appendix B](../../specs/020-vendor-evidence-gate/quickstart.md) — Quality-Gate Verdict + Promotion Decision (the authoritative copy of which this runbook mirrors).
- [docs/stage1-vendor-identity/ollama-runtime.md](./ollama-runtime.md) — host Ollama setup, WSL caveats.
- [docs/stage1-vendor-identity/gpu-warmup-and-cache.md](./gpu-warmup-and-cache.md) — `MIOPEN_FIND_MODE=2`, warmup behavior, cache locations (feature 016 lineage).
- [feature-021 `contracts/runbook.md`](../../specs/021-gpu-mvp-promotion/contracts/runbook.md) — the structural contract this runbook implements.

---

# Feature 023 extension — Canonical demo CLI

The sections below are the feature-023 addendum (per T072 / `research.md` R-023.17). They document the single canonical `python -m dartwing_ocr.gpu_demo` entry point that hardens the four-step manual demo above into a one-command operator surface, plus the failure recovery matrix, the three-run stability smoke procedure that gates Jetson edge-fast promotion, and the colleague dry-run sign-off appendix that closes SC-001.

## § Canonical Demo Command

The canonical operator command is:

```bash
.venv-paddle-rocm/bin/python -m dartwing_ocr.gpu_demo
```

(or, equivalently, the `dartwing-gpu-demo` console-script entry point when the package is installed via `pip install -e .`).

Closed five-flag surface (FR-016 / FR-018 / FR-022 / FR-027):

| Flag | Default | Purpose |
|---|---|---|
| `--check-only` | off | Run only the FR-016 readiness checks 1–6 (infrastructure readiness); skip pipeline phases; emit stable-shape `DemoRunReport` with runtime/quality/timing fields `null`. ≤ 10 s on a warm workstation (SC-007). |
| `--document-folder PATH` | `tests/stage1_vendor_identity/inv_001_easy` | Per-document folder containing `source.pdf`. Ignored under `--check-only` per FR-018. |
| `--voter-config PATH` | auto-discover (feature 005 / 021) | Override the active voter config (FR-005). |
| `--preset NAME` | `header-first-v1` | Preprocessing preset (FR-011). `full-ocr` is opt-in. Ignored under `--check-only`. |
| `--with-evaluator` | off | Invoke the feature 022 semantic-quality evaluator subprocess (FR-022; R-023.13). Warn-and-skip when `semantic_table_truth.json` is absent. |

Consolidated prerequisites (operator must verify BEFORE invoking the demo):

| # | Prerequisite | Verification |
|---|---|---|
| 1 | `.venv-paddle-rocm` active (interpreter under that venv's prefix) | `which python` shows `.../.venv-paddle-rocm/bin/python` |
| 2 | Host Ollama started via `scripts/start-host-ollama-rocm-wsl.sh` (WSL) or equivalent native path | `curl -s http://localhost:11434/api/ps` returns `models: [...]` |
| 3 | `OLLAMA_CONTEXT_LENGTH=2048` set when Ollama was started | exported in the same shell that ran the startup script |
| 4 | Minimum Ollama version `>= 0.4.0` (R-023.10 — first release with stable `size_vram` on `/api/ps`) | `curl -s http://localhost:11434/api/version` |
| 5 | Cold-cache `--check-only` budget: ≤ 30 s informal (warm: ≤ 10 s SC-007) | first run after fresh shell may exceed 10 s; > 30 s warrants investigation |

stdout / stderr discipline (FR-019, audit walkthrough Q1/Q2/Q8/Q10):

- **stdout**: exactly one `DemoRunReport` JSON line (UTF-8, newline-terminated, no second line). Pipe through `| jq` for inspection.
- **stderr**: human-readable progress, warnings, errors. Severity prefix + 8-hex run-id prefix: `INFO:[a1b2c3d4] readiness: paddle-rocm-preflight → pass (2.34s)`. On success: a final `INFO:[<run_id>] runtime: success / quality: <status>` line. On `--check-only` pass: `INFO:[<run_id>] readiness passed (<elapsed>s)`.

Closed exit-code table (FR-021):

| Exit | Meaning |
|---|---|
| `0` | Success — pipeline completed, all four canonical artifacts schema-valid, post-run device interrogation confirms GPU placement |
| `1` | Readiness failed — `failing_check_name` in the report identifies which of the 8 named checks failed |
| `2` | Invalid input / usage — missing `source.pdf`, missing or malformed voter config, symlink-escape on eager-delete |
| `3` | Pipeline runtime timeout (600 s ceiling) — `stalled_phase` identifies the phase executing when the budget elapsed |
| `4` | Pipeline runtime error (incl. CPU-fallback detected by post-run interrogation) |
| `5` | Artifact schema validation failed (one or more of the four canonicals post-run) |

## § Readiness Failure Recovery Matrix

One row per named check in the FR-016 closed vocabulary. The operator action column matches the `remediation` field of the corresponding `CheckDiagnostic`.

| Check name | Likely cause | Operator action |
|---|---|---|
| `interpreter/venv` | Operator forgot to `source .venv-paddle-rocm/bin/activate` | `source .venv-paddle-rocm/bin/activate` then re-run |
| `paddle-rocm-preflight` (ImportError) | `paddlepaddle-dcu` not installed in active venv | `.venv-paddle-rocm/bin/pip install paddlepaddle-dcu` |
| `paddle-rocm-preflight` (device != rocm_gpu) | Stale wheel / broken ROCm exposure | Reinstall `paddlepaddle-dcu`; verify `/dev/dri/render*` permissions; check `HSA_OVERRIDE_GFX_VERSION` env var |
| `ollama-reachability` | Host Ollama not running | `scripts/start-host-ollama-rocm-wsl.sh` |
| `ollama-version` | Running Ollama < 0.4.0 (no stable `size_vram` on `/api/ps`) | Upgrade Ollama to ≥ 0.4.0; restart via the startup script |
| `ollama-model-gpu-placement` (model missing) | Voter config references a model that's not loaded | `ollama pull <model>`; ensure it's referenced before the demo runs |
| `ollama-model-gpu-placement` (`size_vram == 0` / `size_vram < size`) | Model on CPU or partially offloaded | Restart Ollama on a fresh GPU context; check VRAM headroom |
| `ollama-context-length` | `OLLAMA_CONTEXT_LENGTH` env var missing or below 2048 when Ollama was started | Re-export `OLLAMA_CONTEXT_LENGTH=2048` and re-run the startup script |
| `artifact-schema-validation` | Pipeline produced a malformed canonical artifact post-run (regression in features 003/005/008/009) | Inspect the listed artifact(s); see `observed` field for the full failure list in canonical order |
| `pipeline-runtime-timeout` | One phase stalled past 600 s (typically a model hang during extraction) | `stalled_phase` identifies the phase; check Ollama health, GPU temperature, model size |

## § Three-Run Stability Smoke Procedure (SC-006)

This is the workstation manual gate that adopts the demo as the MVP integration-test checkpoint and gates the start of Jetson edge-fast implementation. Execute three consecutive demo runs against `tests/stage1_vendor_identity/inv_001_easy/` (or your nominated canonical fixture) and validate identical outcomes.

```bash
# Three consecutive runs, capturing the JSON line each time.
for i in 1 2 3; do
  .venv-paddle-rocm/bin/python -m dartwing_ocr.gpu_demo \
    > /tmp/023-smoke/run${i}.json 2> /tmp/023-smoke/run${i}.log
done
```

### Acceptance criteria (operator sign-off below)

The smoke run is **PASS** if **all** of these hold:

- [ ] All three runs exit `0`.
- [ ] All three `DemoRunReport` lines have `runtime_outcome == "success"`.
- [ ] All three `quality_status` values are identical (one of `pass` / `weak` / `review_required`).
- [ ] All three `readiness.overall_passed` are `true`.
- [ ] Byte-identical content for `preprocess_output.json`, `routing_decision.json`, `final_structured_payload.json` across the three runs (the three deterministic artifacts per round-2 Q10). `edge_extraction_output.json` is allowed to vary (model nondeterminism).

### Sign-off block

Fill in and commit alongside the merged feature 023 PR:

```
SC-006 three-run stability smoke
================================
Date         : YYYY-MM-DD
Operator     : <name / handle>
Workstation  : <hostname / hardware tag>
Ollama ver   : <output of /api/version>
Paddle wheel : <pip show paddlepaddle-dcu | grep Version>
Run 1 outcome: <runtime_outcome> / <quality_status> / <readiness.overall_passed>
Run 2 outcome: <runtime_outcome> / <quality_status> / <readiness.overall_passed>
Run 3 outcome: <runtime_outcome> / <quality_status> / <readiness.overall_passed>
Three-artifact byte-identity: PASS / FAIL
Result: PASS / FAIL
Notes  : <anything notable>
Signed : <operator handle>
```

After SC-006 passes, the demo is the MVP integration-test checkpoint. The Jetson edge-fast implementation may begin.

## § Appendix: Colleague Dry-Run Sign-Off (audit walkthrough Q11)

SC-001 promises that a fresh operator following only this runbook can execute the demo end-to-end without undocumented commands or tribal knowledge. This appendix is the process gate that validates that promise.

Procedure (one-time, before the feature 023 PR merges):

1. A colleague who has NOT previously run the demo (or who has not run it in ≥ 30 days) follows this runbook end-to-end on a fresh shell.
2. The colleague records any of the following inline (in a copy of this runbook or as a PR comment): commands that needed inference, prerequisites that weren't documented, error messages with no documented remediation, deltas between expected and actual output.
3. The colleague signs the block below with the date.

```
Colleague dry-run sign-off
==========================
Date    : YYYY-MM-DD
Reviewer: <name / handle>
Gaps    : <count> (see inline notes / PR comments)
Verdict : OK to merge / Needs runbook fixes (list gaps)
Signed  : <reviewer handle>
```

This is a process gate, not a spec-level SC. The result is not a `runtime_outcome` value and does not affect the canonical artifact contracts.
